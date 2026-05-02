"""Full clinic data export.

Endpoint `GET /api/clinic/export/full` (clinic_admin only) returns a ZIP
containing one JSON file per table (filtered by clinic_id) plus all
attachments stored in Supabase Storage under the clinic's tree.
"""
import io
import json
import zipfile
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from core import sdb, supabase_admin, require_clinic_admin, logger

router = APIRouter()

# Tables that have clinic_id column directly. Order roughly preserves FK deps.
DIRECT_TABLES = [
    "clinics",  # special-cased: only the user's clinic row
    "branches",
    "clinic_members",
    "clinic_feature_overrides",
    "patients",
    "appointments",
    "medical_records",
    "prescriptions",
    "lab_orders",
    "product_categories",
    "products",
    "services",
    "suppliers",
    "purchase_orders",
    "inventory_stock",
    "inventory_batches",
    "inventory_movements",
    "sales",
    "payments",
    "accounts_receivable",
    "cash_registers",
    "cash_sessions",
    "expenses",
    "commission_settings",
    "commissions_earned",
    "attachments",
    "activity_logs",
    "notification_logs",
]

# Child tables joined via parent_table.id
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
    if isinstance(o, (datetime,)):
        return o.isoformat()
    return str(o)


def _fetch_all(table: str, eq_col: str, eq_val):
    """Page through Supabase results to bypass the 1000 row default limit."""
    PAGE = 1000
    out = []
    offset = 0
    while True:
        q = sdb.table(table).select("*").eq(eq_col, eq_val).range(offset, offset + PAGE - 1)
        res = q.execute()
        rows = res.data or []
        out.extend(rows)
        if len(rows) < PAGE:
            break
        offset += PAGE
    return out


def _fetch_in(table: str, in_col: str, in_values: list):
    """Page through results filtered by `in_col IN (in_values)`. Splits in batches of 200."""
    if not in_values:
        return []
    out = []
    BATCH = 200
    for i in range(0, len(in_values), BATCH):
        chunk = in_values[i:i + BATCH]
        offset = 0
        PAGE = 1000
        while True:
            res = sdb.table(table).select("*").in_(in_col, chunk).range(offset, offset + PAGE - 1).execute()
            rows = res.data or []
            out.extend(rows)
            if len(rows) < PAGE:
                break
            offset += PAGE
    return out


@router.get("/clinic/export/full")
async def export_full(ctx=Depends(require_clinic_admin)):
    """Stream a ZIP with all clinic data (JSON tables + storage files).

    Restricted to `clinic_admin` role.
    """
    clinic_id = ctx["member"]["clinic_id"]
    member = ctx["member"]
    started = datetime.now(timezone.utc)

    # Build ZIP in memory. Clinic data should be small enough; if it grows,
    # switch to a temporary file.
    buf = io.BytesIO()
    manifest = {
        "version": "1.0",
        "clinic_id": clinic_id,
        "exported_at": started.isoformat(),
        "exported_by_member_id": member.get("id"),
        "tables": {},
        "storage": {"bucket": STORAGE_BUCKET, "files_count": 0, "files_total_bytes": 0, "errors": []},
    }

    try:
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
            # 1) Direct tables
            id_index = {}  # table -> list of ids (for child join)
            for t in DIRECT_TABLES:
                try:
                    if t == "clinics":
                        res = sdb.table("clinics").select("*").eq("id", clinic_id).execute()
                        rows = res.data or []
                    else:
                        rows = _fetch_all(t, "clinic_id", clinic_id)
                    zf.writestr(f"data/{t}.json", json.dumps(rows, indent=2, ensure_ascii=False, default=_json_default))
                    manifest["tables"][t] = len(rows)
                    id_index[t] = [r["id"] for r in rows if r.get("id")]
                except Exception as e:
                    logger.error(f"Export: failed to dump {t}: {e}")
                    manifest["tables"][t] = {"error": str(e)}

            # 2) Child tables (filter by parent ids)
            for child, fk_col, parent in CHILD_TABLES:
                try:
                    parent_ids = id_index.get(parent, [])
                    rows = _fetch_in(child, fk_col, parent_ids)
                    zf.writestr(f"data/{child}.json", json.dumps(rows, indent=2, ensure_ascii=False, default=_json_default))
                    manifest["tables"][child] = len(rows)
                except Exception as e:
                    logger.error(f"Export: failed to dump {child}: {e}")
                    manifest["tables"][child] = {"error": str(e)}

            # 3) Attachments — download from Supabase Storage
            attachments = []
            try:
                attachments = _fetch_all("attachments", "clinic_id", clinic_id)
            except Exception as e:
                manifest["storage"]["errors"].append(f"attachments query: {e}")

            for att in attachments:
                path = att.get("storage_path")
                if not path:
                    continue
                try:
                    # supabase-py storage download returns raw bytes
                    data = supabase_admin.storage.from_(STORAGE_BUCKET).download(path)
                    if isinstance(data, dict) and data.get("error"):
                        manifest["storage"]["errors"].append({"path": path, "error": str(data["error"])})
                        continue
                    # Place under files/<storage_path> keeping its tree
                    zf.writestr(f"files/{path}", data)
                    manifest["storage"]["files_count"] += 1
                    manifest["storage"]["files_total_bytes"] += len(data)
                except Exception as e:
                    manifest["storage"]["errors"].append({"path": path, "error": str(e)[:200]})

            # 4) Manifest
            manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
            manifest["duration_seconds"] = (datetime.now(timezone.utc) - started).total_seconds()
            zf.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False, default=_json_default))

            # Friendly README
            readme = (
                f"# Export de clínica\n\n"
                f"Clinic ID: {clinic_id}\n"
                f"Generado: {manifest['finished_at']}\n"
                f"Tablas: {len(manifest['tables'])}\n"
                f"Archivos adjuntos: {manifest['storage']['files_count']}\n\n"
                f"Estructura:\n"
                f"  - `data/<tabla>.json` — un archivo por tabla (filtrado a esta clínica)\n"
                f"  - `files/<patient_id>/...` — archivos del bucket {STORAGE_BUCKET}\n"
                f"  - `manifest.json` — metadatos del export\n"
            )
            zf.writestr("README.md", readme)

    except Exception as e:
        logger.error(f"Export full failed: {e}")
        raise HTTPException(status_code=500, detail=f"Error al generar export: {e}")

    buf.seek(0)
    filename = f"clinic_export_{clinic_id[:8]}_{started.strftime('%Y%m%d_%H%M%S')}.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Export-Tables": str(len(manifest["tables"])),
            "X-Export-Files": str(manifest["storage"]["files_count"]),
        },
    )
