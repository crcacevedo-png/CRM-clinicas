"""Super Admin SaaS metrics dashboard.

Single endpoint that aggregates all KPIs needed by the founder/operator
to monitor the health of the SaaS: growth, activation, engagement,
financial, and operations.

Endpoint: GET /api/admin/dashboard/saas
"""
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException

from core import sdb, logger, require_super_admin

router = APIRouter()


@router.post("/admin/email/test")
async def test_email(to: str, user=Depends(require_super_admin)):
    """Send a test email to verify Resend integration is working.

    Usage:  POST /api/admin/email/test?to=you@example.com
    """
    from services.email_service import send_email
    html = """<div style="font-family:sans-serif;padding:20px;">
      <h2 style="color:#0D9488;">Cortexia Medical — Test email</h2>
      <p>Si recibes este correo, la integración con Resend está funcionando correctamente. ✅</p>
      <p style="color:#64748B;font-size:12px;margin-top:24px;">Enviado por Super Admin desde el panel de administración.</p>
    </div>"""
    result = await send_email(to=to, subject="Test: Cortexia Medical email", html=html, text="Resend integration OK")
    return result

# Fallback monthly prices per plan code (used when the `plans` table has no
# `price_monthly` column). Adjust freely without touching DB.
PLAN_MONTHLY_USD = {
    "free": 0.0,
    "basic": 29.0,
    "professional": 79.0,
    "enterprise": 199.0,
}

ENGAGEMENT_WEIGHTS = {
    "appointments": 1.0,
    "prescriptions": 1.5,
    "sales": 2.0,
    "patients": 0.5,
}


def _iso(d: datetime) -> str:
    return d.astimezone(timezone.utc).isoformat()


def _fetch_count(table: str, *, gte: str | None = None, lte: str | None = None,
                 column: str = "created_at", eq: dict | None = None) -> int:
    q = sdb.table(table).select('id', count='exact')
    if gte:
        q = q.gte(column, gte)
    if lte:
        q = q.lt(column, lte)
    if eq:
        for k, v in eq.items():
            q = q.eq(k, v)
    try:
        return q.execute().count or 0
    except Exception:
        return 0


def _plan_price(plan_code: str | None) -> float:
    return PLAN_MONTHLY_USD.get((plan_code or "free").lower(), 0.0)


def _distinct_clinic_ids(table: str, *, gte: str | None = None) -> set[str]:
    """Return distinct clinic_ids present in a table (optionally created after `gte`)."""
    out: set[str] = set()
    page = 0
    PAGE = 1000
    while True:
        q = sdb.table(table).select('clinic_id').range(page * PAGE, (page + 1) * PAGE - 1)
        if gte:
            q = q.gte('created_at', gte)
        try:
            res = q.execute()
        except Exception:
            break
        rows = res.data or []
        for r in rows:
            cid = r.get('clinic_id')
            if cid:
                out.add(cid)
        if len(rows) < PAGE:
            break
        page += 1
    return out


@router.get("/admin/dashboard/saas")
async def saas_dashboard(user=Depends(require_super_admin)):
    """Comprehensive SaaS KPIs (Phase 1: Bloques 1, 2, 3, 4, 6)."""
    try:
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        d7 = now - timedelta(days=7)
        d14 = now - timedelta(days=14)
        d30 = now - timedelta(days=30)
        d60 = now - timedelta(days=60)
        d90 = now - timedelta(days=90)
        prev_d30_start = now - timedelta(days=60)
        prev_d30_end = now - timedelta(days=30)

        # ============ CLINICS BASE DATASET ============
        clinics_res = sdb.table('clinics').select(
            'id,name,plan,country,state,city,is_active,created_at,plan_expires_at'
        ).execute()
        clinics = clinics_res.data or []
        active_clinics = [c for c in clinics if c.get('is_active')]
        active_ids = {c['id'] for c in active_clinics}
        total_clinics = len(clinics)

        # ============ BLOCK 1 — GROWTH ============
        # MRR / ARR
        mrr = sum(_plan_price(c.get('plan')) for c in active_clinics)
        arr = mrr * 12

        # Nuevas clínicas (today / 7d / 30d / previous 30d for MoM)
        def created_in(rows: list, gte: datetime, lt: datetime | None = None) -> int:
            n = 0
            for r in rows:
                ts = r.get('created_at')
                if not ts:
                    continue
                try:
                    t = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                except Exception:
                    continue
                if t >= gte and (lt is None or t < lt):
                    n += 1
            return n

        new_today = created_in(clinics, today_start)
        new_d7 = created_in(clinics, d7)
        new_d30 = created_in(clinics, d30)
        prev_d30 = created_in(clinics, prev_d30_start, prev_d30_end)
        mom_pct = round(((new_d30 - prev_d30) / prev_d30) * 100, 1) if prev_d30 else None

        # Funnel onboarding
        clinic_ids_set = {c['id'] for c in clinics}
        cl_with_patient = _distinct_clinic_ids('patients') & clinic_ids_set
        cl_with_appointment = _distinct_clinic_ids('appointments') & clinic_ids_set
        cl_with_sale = _distinct_clinic_ids('sales') & clinic_ids_set
        funnel = {
            "registered": total_clinics,
            "with_patient": len(cl_with_patient),
            "with_appointment": len(cl_with_appointment),
            "with_sale": len(cl_with_sale),
        }

        # Geographic distribution (by country)
        geo = defaultdict(lambda: {"count": 0, "active": 0, "mrr": 0.0})
        for c in clinics:
            co = (c.get('country') or '—').lower()
            geo[co]["count"] += 1
            if c.get('is_active'):
                geo[co]["active"] += 1
                geo[co]["mrr"] += _plan_price(c.get('plan'))
        geo_list = sorted(
            [{"country": k, **v, "mrr": round(v["mrr"], 2)} for k, v in geo.items()],
            key=lambda x: -x["count"]
        )

        # ============ BLOCK 2 — ACTIVATION ============
        # DAU/WAU/MAU using activity_logs.user_id distinct
        def distinct_users_since(gte: datetime) -> int:
            seen = set()
            page = 0
            PAGE = 1000
            while True:
                try:
                    res = sdb.table('activity_logs').select('user_id') \
                        .gte('created_at', _iso(gte)) \
                        .range(page * PAGE, (page + 1) * PAGE - 1).execute()
                except Exception:
                    break
                rows = res.data or []
                for r in rows:
                    u = r.get('user_id')
                    if u:
                        seen.add(u)
                if len(rows) < PAGE:
                    break
                page += 1
            return len(seen)

        dau = distinct_users_since(today_start)
        wau = distinct_users_since(d7)
        mau = distinct_users_since(d30)
        sticky_ratio_pct = round((dau / mau) * 100, 1) if mau else 0.0

        # Inactive clinics (no activity in 7/14/30 days) — based on last activity_log
        # Strategy: pull distinct clinic_ids with activity in each window, subtract
        cl_active_7 = _distinct_clinic_ids('activity_logs', gte=_iso(d7)) & active_ids
        cl_active_14 = _distinct_clinic_ids('activity_logs', gte=_iso(d14)) & active_ids
        cl_active_30 = _distinct_clinic_ids('activity_logs', gte=_iso(d30)) & active_ids
        inactive_clinics = {
            "d7": len(active_ids - cl_active_7),
            "d14": len(active_ids - cl_active_14),
            "d30": len(active_ids - cl_active_30),
        }

        # Module adoption %
        module_tables = [
            ("appointments", "Citas"),
            ("medical_records", "Consultas"),
            ("prescriptions", "Recetas"),
            ("lab_orders", "Laboratorio"),
            ("sales", "Ventas"),
            ("expenses", "Gastos"),
            ("inventory_stock", "Inventario"),
            ("accounts_receivable", "Cuentas por cobrar"),
            ("commissions_earned", "Comisiones"),
        ]
        active_total = max(len(active_ids), 1)
        module_adoption = []
        for tbl, label in module_tables:
            ids = _distinct_clinic_ids(tbl) & active_ids
            module_adoption.append({
                "module": label,
                "clinics": len(ids),
                "pct": round((len(ids) / active_total) * 100, 1),
            })

        # Free → Paid conversion (clinics whose plan changed in last 30/60/90 days)
        # We don't track plan changes historically yet — best-effort: count clinics
        # currently on paid plans created MORE than X days ago (proxy for upgrades).
        free_to_paid = {"d30": 0, "d60": 0, "d90": 0}
        for c in active_clinics:
            p = (c.get('plan') or 'free').lower()
            if p == 'free':
                continue
            ts = c.get('created_at')
            if not ts:
                continue
            try:
                t = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            except Exception:
                continue
            if t > d30:
                free_to_paid["d30"] += 1
            if t > d60:
                free_to_paid["d60"] += 1
            if t > d90:
                free_to_paid["d90"] += 1

        # ============ BLOCK 3 — ENGAGEMENT ============
        def count_window(table: str, gte: datetime) -> int:
            return _fetch_count(table, gte=_iso(gte))

        engagement_periods = {
            "today": {
                "appointments": count_window('appointments', today_start),
                "prescriptions": count_window('prescriptions', today_start),
                "sales": count_window('sales', today_start),
                "patients": count_window('patients', today_start),
            },
            "d7": {
                "appointments": count_window('appointments', d7),
                "prescriptions": count_window('prescriptions', d7),
                "sales": count_window('sales', d7),
                "patients": count_window('patients', d7),
            },
            "d30": {
                "appointments": count_window('appointments', d30),
                "prescriptions": count_window('prescriptions', d30),
                "sales": count_window('sales', d30),
                "patients": count_window('patients', d30),
            },
        }

        # Top/Bottom 10 clinics by engagement score (last 30d)
        scores = defaultdict(lambda: {"appointments": 0, "prescriptions": 0, "sales": 0, "patients": 0})
        for table in ("appointments", "prescriptions", "sales", "patients"):
            page = 0
            PAGE = 1000
            while True:
                try:
                    res = sdb.table(table).select('clinic_id').gte('created_at', _iso(d30)) \
                        .range(page * PAGE, (page + 1) * PAGE - 1).execute()
                except Exception:
                    break
                rows = res.data or []
                for r in rows:
                    cid = r.get('clinic_id')
                    if cid:
                        scores[cid][table] += 1
                if len(rows) < PAGE:
                    break
                page += 1

        # Ensure every active clinic appears (even with score 0)
        for cid in active_ids:
            _ = scores[cid]

        clinic_meta = {c['id']: c for c in clinics}
        rated = []
        for cid, s in scores.items():
            meta = clinic_meta.get(cid)
            if not meta:
                continue
            score = sum(s[k] * ENGAGEMENT_WEIGHTS.get(k, 1.0) for k in s)
            rated.append({
                "id": cid,
                "name": meta.get('name'),
                "plan": meta.get('plan'),
                "country": meta.get('country'),
                "score": round(score, 1),
                **s,
            })
        rated.sort(key=lambda x: -x["score"])
        top10 = rated[:10]
        bottom10 = [x for x in rated if x["id"] in active_ids][-10:][::-1]

        # Appointment status distribution (last 30d)
        apt_status_counts = defaultdict(int)
        page = 0
        PAGE = 1000
        total_apts_30 = 0
        while True:
            try:
                res = sdb.table('appointments').select('status').gte('created_at', _iso(d30)) \
                    .range(page * PAGE, (page + 1) * PAGE - 1).execute()
            except Exception:
                break
            rows = res.data or []
            for r in rows:
                apt_status_counts[r.get('status') or 'unknown'] += 1
                total_apts_30 += 1
            if len(rows) < PAGE:
                break
            page += 1
        appointment_status = [
            {"status": k, "count": v, "pct": round((v / total_apts_30) * 100, 1) if total_apts_30 else 0}
            for k, v in sorted(apt_status_counts.items(), key=lambda x: -x[1])
        ]

        # ============ BLOCK 4 — FINANCIAL ============
        mrr_by_plan_map = defaultdict(lambda: {"clinics": 0, "mrr": 0.0})
        for c in active_clinics:
            p = (c.get('plan') or 'free').lower()
            mrr_by_plan_map[p]["clinics"] += 1
            mrr_by_plan_map[p]["mrr"] += _plan_price(p)
        mrr_by_plan = sorted(
            [{"plan": k, "clinics": v["clinics"], "mrr": round(v["mrr"], 2)} for k, v in mrr_by_plan_map.items()],
            key=lambda x: -x["mrr"]
        )

        # Plans expiring soon
        expiring_soon = {"d7": [], "d14": [], "d30": []}
        for c in active_clinics:
            exp = c.get('plan_expires_at')
            if not exp:
                continue
            try:
                t = datetime.fromisoformat(exp.replace('Z', '+00:00'))
            except Exception:
                continue
            if t < now:
                continue  # already expired
            days = (t - now).total_seconds() / 86400
            entry = {"clinic_id": c['id'], "name": c.get('name'), "plan": c.get('plan'), "days": round(days, 1)}
            if days <= 7:
                expiring_soon["d7"].append(entry)
            if days <= 14:
                expiring_soon["d14"].append(entry)
            if days <= 30:
                expiring_soon["d30"].append(entry)

        # AR total (sum of accounts_receivable.balance across clinics)
        ar_total = 0.0
        page = 0
        while True:
            try:
                res = sdb.table('accounts_receivable').select('balance').range(page * PAGE, (page + 1) * PAGE - 1).execute()
            except Exception:
                break
            rows = res.data or []
            for r in rows:
                try:
                    ar_total += float(r.get('balance') or 0)
                except Exception:
                    pass
            if len(rows) < PAGE:
                break
            page += 1
        ar_total = round(ar_total, 2)

        # ============ BLOCK 6 — OPERATIONS ============
        # Plan limits: best-effort — show clinics nearing usage of patients table
        # (limits would normally be from plans.* — using a simple proxy here).
        PLAN_PATIENT_LIMITS = {"free": 50, "basic": 200, "professional": 1000, "enterprise": None}
        patients_count_by_clinic = defaultdict(int)
        page = 0
        while True:
            try:
                res = sdb.table('patients').select('clinic_id').range(page * PAGE, (page + 1) * PAGE - 1).execute()
            except Exception:
                break
            rows = res.data or []
            for r in rows:
                cid = r.get('clinic_id')
                if cid:
                    patients_count_by_clinic[cid] += 1
            if len(rows) < PAGE:
                break
            page += 1

        plan_limit_warnings = []
        for c in active_clinics:
            p = (c.get('plan') or 'free').lower()
            limit = PLAN_PATIENT_LIMITS.get(p)
            if limit is None:
                continue
            used = patients_count_by_clinic.get(c['id'], 0)
            pct = (used / limit) * 100 if limit else 0
            if pct >= 80:
                plan_limit_warnings.append({
                    "clinic_id": c['id'],
                    "name": c.get('name'),
                    "plan": p,
                    "metric": "patients",
                    "used": used,
                    "limit": limit,
                    "pct": round(pct, 1),
                })
        plan_limit_warnings.sort(key=lambda x: -x["pct"])

        # Last export timestamp per clinic (from activity_logs if you log it; otherwise null)
        # Placeholder for now.
        return {
            "generated_at": now.isoformat(),
            "growth": {
                "mrr": round(mrr, 2),
                "arr": round(arr, 2),
                "total_clinics": total_clinics,
                "active_clinics": len(active_clinics),
                "inactive_clinics": total_clinics - len(active_clinics),
                "new_clinics": {
                    "today": new_today,
                    "d7": new_d7,
                    "d30": new_d30,
                    "prev_d30": prev_d30,
                    "mom_pct": mom_pct,
                },
                "funnel": funnel,
                "geo": geo_list,
                "free_to_paid": free_to_paid,
            },
            "activation": {
                "dau": dau,
                "wau": wau,
                "mau": mau,
                "sticky_ratio_pct": sticky_ratio_pct,
                "inactive_clinics": inactive_clinics,
                "module_adoption": module_adoption,
            },
            "engagement": {
                "periods": engagement_periods,
                "top10": top10,
                "bottom10": bottom10,
                "appointment_status": appointment_status,
                "total_appointments_30d": total_apts_30,
            },
            "financial": {
                "mrr_by_plan": mrr_by_plan,
                "expiring_soon_counts": {k: len(v) for k, v in expiring_soon.items()},
                "expiring_soon_d30": expiring_soon["d30"][:20],
                "ar_total": ar_total,
            },
            "ops": {
                "plan_limit_warnings": plan_limit_warnings[:20],
            },
        }
    except Exception as e:
        logger.error(f"saas_dashboard error: {e}")
        raise HTTPException(status_code=500, detail="Error al generar dashboard")
