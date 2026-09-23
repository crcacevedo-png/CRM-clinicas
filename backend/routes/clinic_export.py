"""Full clinic data export — background job architecture.

Flow:
    1. `POST /api/clinic/export/full` → creates an `export_jobs` row (status='queued'),
       returns `job_id`. Kicks off an asyncio task to process it.
    2. Background task builds the ZIP into a tempfile, uploads it to Supabase
       Storage under `exports/<clinic_id>/<job_id>.zip`, creates a signed URL
       (24h), updates the row to status='done' + signed_url.
    3. `GET /api/clinic/export/jobs/{job_id}` → returns current status/URL for polling.
    4. `GET /api/clinic/export/jobs` → returns recent jobs for this clinic.

Why background: the old `/export/full` streamed a ZIP built in memory. With
larger clinics (>1000 patients) that would OOM the pod. Now the ZIP is
written to a tempfile (bounded disk usage) and the request thread returns
in <100ms.

Multi-pod safety: only one pod picks up a job at a time via
`pg_try_advisory_xact_lock(job_uuid_hash)`.
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import tempfile
import zipfile
import logging
import uuid
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List

from core import sdb, supabase_admin, require_clinic_admin, logger, now_iso

router = APIRouter()

DIRECT_TABLES = [
    "clinics", "branches", "clinic_members", "clinic_feature_overrides",
    "patients", "appointments", "medical_records", "prescriptions", "lab_orders",
    "product_categories", "products", "services", "suppliers", "purchase_orders",
    "inventory_stock", "inventory_batches", "inventory_movements",
    "sales", "payments", "accounts_receivable",
    "cash_registers", "cash_sessions",
    "expenses", "commission_settings", "commissions_earned",
    "attachments", "activity_logs", "notification_logs",
]

CHILD_TABLES = [
    ("sale_items", "sale_id", "sales"),
    ("prescription_items", "prescription_id", "prescriptions"),
    ("lab_order_items", "lab_order_id", "lab_orders"),
    ("purchase_order_items", "purchase_order_id", "purchase_orders"),
    ("member_branches", "member_id", "clinic_members"),
    ("payment_plan_installments", "account_receivable_id", "accounts_receivable"),
]

STORAGE_BUCKET = "patient-files"


def _json_default(o):
    if isinstance(o, datetime):
        return o.isoformat()
    return str(o)


def _execute_retry(build_query, retries: int = 3):
    """Run a PostgREST query with retries on transient httpx connection errors.

    The module-level supabase client keeps httpx keepalive connections open; under
    concurrent load (e.g. the browser polling several endpoints while an export
    runs) the server may close an idle connection, so the next `.execute()` raises
    `RemoteProtocolError: Server disconnected`. Retrying re-establishes a fresh
    connection and succeeds.
    """
    import time
    import httpx
    transient = (
        httpx.RemoteProtocolError, httpx.ReadError, httpx.ConnectError,
        httpx.WriteError, httpx.PoolTimeout, httpx.ConnectTimeout, httpx.ReadTimeout,
    )
    for attempt in range(retries):
        try:
            return build_query().execute()
        except transient as e:
            if attempt == retries - 1:
                raise
            logger.warning(f"export fetch retry {attempt + 1}/{retries} after {type(e).__name__}: {e}")
            time.sleep(0.4 * (attempt + 1))


def _fetch_all(table: str, eq_col: str, eq_val):
    PAGE = 1000
    out, offset = [], 0
    while True:
        res = _execute_retry(lambda: sdb.table(table).select("*").eq(eq_col, eq_val).range(offset, offset + PAGE - 1))
        rows = res.data or []
        out.extend(rows)
        if len(rows) < PAGE:
            break
        offset += PAGE
    return out


def _fetch_in(table: str, in_col: str, in_values: list):
    if not in_values:
        return []
    out = []
    BATCH = 200
    for i in range(0, len(in_values), BATCH):
        chunk = in_values[i:i + BATCH]
        offset, PAGE = 0, 1000
        while True:
            res = _execute_retry(lambda: sdb.table(table).select("*").in_(in_col, chunk).range(offset, offset + PAGE - 1))
            rows = res.data or []
            out.extend(rows)
            if len(rows) < PAGE:
                break
            offset += PAGE
    return out


def _build_zip_to_tempfile(clinic_id: str, on_progress) -> tuple[str, dict]:
    """Build the full-clinic ZIP into a tempfile. Returns (temp_path, manifest)."""
    started = datetime.now(timezone.utc)
    manifest = {
        "version": "1.0",
        "clinic_id": clinic_id,
        "exported_at": started.isoformat(),
        "tables": {},
        "storage": {"bucket": STORAGE_BUCKET, "files_count": 0, "files_total_bytes": 0, "errors": []},
    }
    fd, tmp_path = tempfile.mkstemp(prefix=f"export_{clinic_id[:8]}_", suffix=".zip")
    os.close(fd)  # close the raw fd — zipfile will reopen the path

    with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        # 1) Direct tables
        id_index: dict[str, list] = {}
        total_direct = len(DIRECT_TABLES)
        for i, t in enumerate(DIRECT_TABLES):
            try:
                if t == "clinics":
                    res = _execute_retry(lambda: sdb.table("clinics").select("*").eq("id", clinic_id))
                    rows = res.data or []
                else:
                    rows = _fetch_all(t, "clinic_id", clinic_id)
                zf.writestr(f"data/{t}.json", json.dumps(rows, indent=2, ensure_ascii=False, default=_json_default))
                manifest["tables"][t] = len(rows)
                id_index[t] = [r["id"] for r in rows if r.get("id")]
            except Exception as e:
                logger.error(f"Export: failed to dump {t}: {e}")
                manifest["tables"][t] = {"error": str(e)}
            on_progress({"phase": "direct_tables", "done": i + 1, "total": total_direct})

        # 2) Child tables
        total_child = len(CHILD_TABLES)
        for i, (child, fk_col, parent) in enumerate(CHILD_TABLES):
            try:
                parent_ids = id_index.get(parent, [])
                rows = _fetch_in(child, fk_col, parent_ids)
                zf.writestr(f"data/{child}.json", json.dumps(rows, indent=2, ensure_ascii=False, default=_json_default))
                manifest["tables"][child] = len(rows)
            except Exception as e:
                logger.error(f"Export: failed to dump {child}: {e}")
                manifest["tables"][child] = {"error": str(e)}
            on_progress({"phase": "child_tables", "done": i + 1, "total": total_child})

        # 3) Attachments
        attachments = []
        try:
            attachments = _fetch_all("attachments", "clinic_id", clinic_id)
        except Exception as e:
            manifest["storage"]["errors"].append(f"attachments query: {e}")

        total_att = len(attachments)
        for i, att in enumerate(attachments):
            path = att.get("storage_path")
            if not path:
                continue
            try:
                data = supabase_admin.storage.from_(STORAGE_BUCKET).download(path)
                if isinstance(data, dict) and data.get("error"):
                    manifest["storage"]["errors"].append({"path": path, "error": str(data["error"])})
                    continue
                zf.writestr(f"files/{path}", data)
                manifest["storage"]["files_count"] += 1
                manifest["storage"]["files_total_bytes"] += len(data)
            except Exception as e:
                manifest["storage"]["errors"].append({"path": path, "error": str(e)[:200]})
            if (i + 1) % 25 == 0 or (i + 1) == total_att:
                on_progress({"phase": "attachments", "done": i + 1, "total": total_att})

        # 4) Manifest + README
        manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
        manifest["duration_seconds"] = (datetime.now(timezone.utc) - started).total_seconds()
        zf.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False, default=_json_default))
        readme = (
            f"# Export de clínica\n\n"
            f"Clinic ID: {clinic_id}\n"
            f"Generado: {manifest['finished_at']}\n"
            f"Tablas: {len(manifest['tables'])}\n"
            f"Archivos adjuntos: {manifest['storage']['files_count']}\n"
        )
        zf.writestr("README.md", readme)

    return tmp_path, manifest


async def _run_export_job(job_id: str, clinic_id: str):
    """Process an export job in the background.

    Uses `pg_try_advisory_xact_lock` on a hash of job_id so if two pods pick
    up the same job (very unlikely with UUIDs), only one proceeds.
    """
    from core import run_sql
    # Convert job_id UUID → int64 for advisory lock
    lock_id = int(uuid.UUID(job_id).int >> 65)  # cast to 63 bits
    try:
        # Try to claim the job
        r = run_sql("SELECT pg_try_advisory_lock(%s) AS ok", (lock_id,), fetch=True)
        if not (r and r[0].get("ok")):
            logger.info(f"Export job {job_id} already being processed by another worker")
            return

        sdb.table('export_jobs').update({
            "status": "running",
            "started_at": now_iso(),
        }).eq('id', job_id).execute()

        # Progress callback
        def on_progress(update: dict):
            try:
                sdb.table('export_jobs').update({"progress": update}).eq('id', job_id).execute()
            except Exception:
                pass

        # Build ZIP (blocking work — run in threadpool to keep event loop free)
        loop = asyncio.get_event_loop()
        tmp_path, manifest = await loop.run_in_executor(
            None, _build_zip_to_tempfile, clinic_id, on_progress
        )

        try:
            size = os.path.getsize(tmp_path)
            # Upload to Supabase Storage under exports/<clinic>/<job>.zip
            storage_path = f"{clinic_id}/exports/{job_id}.zip"
            with open(tmp_path, "rb") as f:
                data = f.read()
            supabase_admin.storage.from_(STORAGE_BUCKET).upload(
                storage_path, data,
                {"content-type": "application/zip", "upsert": "true"},
            )
            # 24h signed URL for download
            signed = supabase_admin.storage.from_(STORAGE_BUCKET).create_signed_url(storage_path, 86400)
            signed_url = signed.get('signedURL') or signed.get('signedUrl', '')
            expires_at = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()

            sdb.table('export_jobs').update({
                "status": "done",
                "finished_at": now_iso(),
                "file_path": storage_path,
                "file_size": size,
                "signed_url": signed_url,
                "url_expires_at": expires_at,
                "progress": {"phase": "done", "manifest": manifest},
            }).eq('id', job_id).execute()

            logger.info(f"Export job {job_id} finished: {size} bytes → {storage_path}")
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass

    except Exception as e:
        logger.error(f"Export job {job_id} failed: {e}")
        try:
            sdb.table('export_jobs').update({
                "status": "failed",
                "finished_at": now_iso(),
                "error": str(e)[:500],
            }).eq('id', job_id).execute()
        except Exception:
            pass
    finally:
        try:
            run_sql("SELECT pg_advisory_unlock(%s)", (lock_id,))
        except Exception:
            pass


@router.post("/clinic/export/full")
async def start_export_job(ctx=Depends(require_clinic_admin)):
    """Queue a background job that builds a full-clinic ZIP.

    Returns immediately with `job_id`. Poll `/clinic/export/jobs/{id}` for
    progress and the signed download URL.
    """
    clinic_id = ctx["member"]["clinic_id"]
    member = ctx["member"]
    from core import get_current_user  # noqa: F401 — imported for type hint clarity
    job_id = str(uuid.uuid4())

    # Prevent stampede: reject if this clinic has a queued/running job already
    active = sdb.table('export_jobs').select('id,status').eq('clinic_id', clinic_id).in_('status', ['queued', 'running']).execute()
    if active.data:
        raise HTTPException(status_code=409, detail=f"Ya hay un export en curso ({active.data[0]['status']}). Espera a que termine.")

    sdb.table('export_jobs').insert({
        "id": job_id,
        "clinic_id": clinic_id,
        "requested_by": member.get("user_id"),
        "requested_email": member.get("email"),
        "status": "queued",
    }).execute()

    # Fire the background task. Not awaited on purpose.
    asyncio.create_task(_run_export_job(job_id, clinic_id))

    # Audit
    try:
        from services.audit import log_audit, actor_from_ctx
        await log_audit(
            action="clinic_data_export_queued",
            entity="clinic",
            entity_id=clinic_id,
            **actor_from_ctx(ctx),
            meta={"job_id": job_id},
        )
    except Exception:
        pass

    return {"job_id": job_id, "status": "queued"}


@router.get("/clinic/export/jobs")
async def list_export_jobs(ctx=Depends(require_clinic_admin)):
    """Recent export jobs (last 20) for this clinic."""
    clinic_id = ctx["member"]["clinic_id"]
    res = sdb.table('export_jobs').select('id,status,created_at,started_at,finished_at,file_size,url_expires_at,error,progress').eq('clinic_id', clinic_id).order('created_at', desc=True).limit(20).execute()
    return {"jobs": res.data or []}


@router.get("/clinic/export/jobs/{job_id}")
async def get_export_job(job_id: str, ctx=Depends(require_clinic_admin)):
    """Poll a job by id. Returns signed URL once status=done."""
    clinic_id = ctx["member"]["clinic_id"]
    res = sdb.table('export_jobs').select('*').eq('id', job_id).eq('clinic_id', clinic_id).maybe_single().execute()
    data = getattr(res, 'data', None)
    if not data:
        raise HTTPException(status_code=404, detail="Job no encontrado")

    # If the signed URL is close to expiring, refresh it
    if data.get('status') == 'done' and data.get('file_path'):
        try:
            expires = data.get('url_expires_at')
            need_refresh = True
            if expires:
                exp_dt = datetime.fromisoformat(expires.replace('Z', '+00:00'))
                need_refresh = (exp_dt - datetime.now(timezone.utc)).total_seconds() < 300
            if need_refresh:
                signed = supabase_admin.storage.from_(STORAGE_BUCKET).create_signed_url(data['file_path'], 86400)
                url = signed.get('signedURL') or signed.get('signedUrl', '')
                if url:
                    new_exp = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
                    sdb.table('export_jobs').update({"signed_url": url, "url_expires_at": new_exp}).eq('id', job_id).execute()
                    data['signed_url'] = url
                    data['url_expires_at'] = new_exp
        except Exception as e:
            logger.warning(f"Refresh export signed URL failed: {e}")

    return data


# ============================================================================
# EXCEL EXPORT — full database as a multi-sheet .xlsx (clinic_admin only)
# ============================================================================

def _xl_cell(v):
    """Coerce any value into an Excel-safe cell value."""
    from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
    if v is None:
        return ""
    if isinstance(v, bool):
        return "Sí" if v else "No"
    if isinstance(v, (dict, list)):
        v = json.dumps(v, ensure_ascii=False, default=_json_default)
    elif not isinstance(v, (int, float, str)):
        v = str(v)
    if isinstance(v, str):
        if len(v) > 32000:
            v = v[:32000] + "…"
        v = ILLEGAL_CHARACTERS_RE.sub("", v)
    return v


def _prettify(k: str) -> str:
    return str(k).replace("_", " ").strip().capitalize()


def _write_sheet(wb, title, rows, computed=None, drop=None):
    """Create a worksheet from a list of row dicts.

    `computed` = list of (header_label, fn(row)) columns placed first (e.g. resolved
    patient/doctor names). `drop` = raw keys to omit.
    """
    from openpyxl.styles import Font
    ws = wb.create_sheet(title[:31])
    drop = set(drop or [])
    computed = computed or []
    if not rows:
        ws.append(["(sin datos)"])
        return
    keys, seen = [], set()
    for r in rows:
        for k in r.keys():
            if k not in seen and k not in drop:
                keys.append(k)
                seen.add(k)
    header = [label for label, _ in computed] + [_prettify(k) for k in keys]
    ws.append(header)
    for r in rows:
        row = [_xl_cell(fn(r)) for _, fn in computed] + [_xl_cell(r.get(k)) for k in keys]
        ws.append(row)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    ws.freeze_panes = "A2"


def _parse_dt(s):
    """Parse an ISO date (YYYY-MM-DD) or datetime string into an aware datetime."""
    if not s or not isinstance(s, str):
        return None
    try:
        s = s.strip()
        if len(s) == 10:  # date only
            return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def _date_bounds(start_date, end_date):
    """Return (start_dt, end_dt) aware datetimes. end_date given as a bare date
    is expanded to the end of that day so the range is inclusive."""
    start_dt = _parse_dt(start_date) if start_date else None
    end_dt = None
    if end_date:
        e = str(end_date).strip()
        if len(e) == 10:
            d = _parse_dt(e)
            if d:
                end_dt = d + timedelta(days=1) - timedelta(microseconds=1)
        else:
            end_dt = _parse_dt(e)
    return start_dt, end_dt


def _in_range(row, start_dt, end_dt):
    """True if row.created_at falls within [start_dt, end_dt]. Rows lacking a
    parseable created_at are kept (fail-open) to avoid silently dropping data."""
    if start_dt is None and end_dt is None:
        return True
    dt = _parse_dt(row.get("created_at"))
    if dt is None:
        return True
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    if start_dt and dt < start_dt:
        return False
    if end_dt and dt > end_dt:
        return False
    return True


def _build_excel_bytes(clinic_id: str, start_date=None, end_date=None, sheets=None) -> bytes:
    """Build the database Excel workbook (one sheet per dataset).

    `start_date`/`end_date` (ISO date or datetime strings, optional) filter the
    dated data sheets by their `created_at`. Undated reference sheets (Equipo,
    Sucursales, Clínica) are always included in full. `sheets` (optional list of
    canonical keys) restricts which sheets are generated; None = all.
    """
    from openpyxl import Workbook

    selected = set(sheets) if sheets else None  # None = all sheets

    def want(key):
        return selected is None or key in selected

    start_dt, end_dt = _date_bounds(start_date, end_date)

    def dfilter(rows):
        if start_dt is None and end_dt is None:
            return rows
        return [r for r in rows if _in_range(r, start_dt, end_dt)]

    # Patients & members are always fetched — needed for the computed
    # "Paciente"/"Médico" columns on other sheets even if unselected.
    patients = _fetch_all("patients", "clinic_id", clinic_id)
    members = _fetch_all("clinic_members", "clinic_id", clinic_id)

    pmap = {p["id"]: f"{p.get('first_name', '')} {p.get('last_name', '')}".strip() for p in patients}
    dmap = {m["id"]: f"{m.get('first_name', '')} {m.get('last_name', '')}".strip() for m in members}
    pac = ("Paciente", lambda r: pmap.get(r.get("patient_id"), ""))
    doc = ("Médico", lambda r: dmap.get(r.get("doctor_id"), ""))

    wb = Workbook()
    wb.remove(wb.active)  # drop the default empty sheet

    if want("patients"):
        _write_sheet(wb, "Pacientes", dfilter(patients))
    if want("medical_records"):
        mr = dfilter(_fetch_all("medical_records", "clinic_id", clinic_id))
        _write_sheet(wb, "Evaluaciones Médicas", mr, computed=[pac, doc])
    if want("prescriptions"):
        prescriptions = dfilter(_fetch_all("prescriptions", "clinic_id", clinic_id))
        _write_sheet(wb, "Recetas", prescriptions, computed=[pac, doc])
        pitems = _fetch_in("prescription_items", "prescription_id", [p["id"] for p in prescriptions if p.get("id")])
        _write_sheet(wb, "Recetas - Medicamentos", pitems)
    if want("lab_orders"):
        lab_orders = dfilter(_fetch_all("lab_orders", "clinic_id", clinic_id))
        _write_sheet(wb, "Laboratorio", lab_orders, computed=[pac, doc])
        litems = _fetch_in("lab_order_items", "lab_order_id", [l["id"] for l in lab_orders if l.get("id")])
        _write_sheet(wb, "Laboratorio - Estudios", litems)
    if want("appointments"):
        appointments = dfilter(_fetch_all("appointments", "clinic_id", clinic_id))
        _write_sheet(wb, "Citas", appointments, computed=[pac, doc])
    if want("members"):
        _write_sheet(wb, "Equipo", members, drop=["user_id"])
    if want("branches"):
        _write_sheet(wb, "Sucursales", _fetch_all("branches", "clinic_id", clinic_id))
    if want("clinic"):
        clinic = (_execute_retry(lambda: sdb.table("clinics").select("*").eq("id", clinic_id)).data) or []
        _write_sheet(wb, "Clínica", clinic)

    # openpyxl requires at least one visible sheet on save
    if not wb.sheetnames:
        ws = wb.create_sheet("Sin datos")
        ws.append(["No se seleccionaron hojas para exportar"])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


@router.get("/clinic/export/excel")
async def export_excel(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    sheets: Optional[List[str]] = Query(None),
    ctx=Depends(require_clinic_admin),
):
    """Download the clinic database as a multi-sheet Excel file.

    Optional filters:
      - `start_date` / `end_date`: ISO date (YYYY-MM-DD) or datetime. Filter the
        dated data sheets (Pacientes, Evaluaciones, Recetas, Laboratorio, Citas)
        by their `created_at`. Reference sheets (Equipo, Sucursales, Clínica)
        are always full.
      - `sheets`: repeated query param of sheet keys to include. Omit = all.
        Keys: patients, medical_records, prescriptions, lab_orders,
        appointments, members, branches, clinic.
    """
    clinic_id = ctx["member"]["clinic_id"]
    loop = asyncio.get_event_loop()
    try:
        data = await loop.run_in_executor(
            None, _build_excel_bytes, clinic_id, start_date, end_date, sheets
        )
    except Exception as e:
        logger.error(f"Excel export failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al generar el Excel")

    try:
        from services.audit import log_audit, actor_from_ctx
        await log_audit(
            action="clinic_data_export_excel", entity="clinic", entity_id=clinic_id,
            meta={"start_date": start_date, "end_date": end_date, "sheets": sheets},
            **actor_from_ctx(ctx),
        )
    except Exception:
        pass

    from fastapi.responses import StreamingResponse
    fname = f"base_datos_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.xlsx"
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
