"""SaaS billing routes (Stripe).

NOTE: This is the ROUTE scaffold only. The Stripe API integration will be
wired in later — the checkout / portal endpoints currently return a clear
"not configured yet" placeholder so the UI can render the full flow.

Real data endpoints (plan overview, per-clinic subscription) DO work now and
read from the existing `clinics` / `plans` tables.
"""
import os
import logging
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from core import sdb, require_super_admin, require_clinic_member, logger

router = APIRouter()

STRIPE_ENABLED = bool(os.environ.get("STRIPE_API_KEY"))
_NOT_CONFIGURED = {
    "ok": False,
    "configured": False,
    "message": "La pasarela de pago (Stripe) aún no está configurada. Se habilitará próximamente.",
    "checkout_url": None,
}


def _plans_map() -> dict:
    try:
        res = sdb.table('plans').select('code,name,price_monthly,price_yearly').execute()
        return {p['code']: p for p in (res.data or [])}
    except Exception as e:
        logger.warning(f"billing plans_map failed: {e}")
        return {}


# ============== CLINIC-FACING (Configuración → Plan) ==============

@router.get("/billing/subscription")
async def my_subscription(ctx=Depends(require_clinic_member)):
    """Current clinic's plan + billing status (real data, no Stripe yet)."""
    clinic_id = ctx["member"]["clinic_id"]
    clinic = sdb.table('clinics').select(
        'id,name,plan,plan_expires_at,is_active,max_users,max_patients,max_storage_mb'
    ).eq('id', clinic_id).single().execute()
    c = clinic.data or {}
    plan_code = c.get('plan')
    plan = _plans_map().get(plan_code, {})
    return {
        "clinic_id": clinic_id,
        "plan_code": plan_code,
        "plan_name": plan.get('name') or plan_code,
        "price_monthly": plan.get('price_monthly'),
        "price_yearly": plan.get('price_yearly'),
        "currency": "USD",
        "status": "active" if c.get('is_active') else "suspended",
        "expires_at": c.get('plan_expires_at'),
        "stripe_configured": STRIPE_ENABLED,
        "limits": {
            "max_users": c.get('max_users'),
            "max_patients": c.get('max_patients'),
            "max_storage_mb": c.get('max_storage_mb'),
        },
    }


class CheckoutRequest(BaseModel):
    plan_code: str | None = None
    billing_cycle: str | None = "monthly"  # monthly | yearly


@router.post("/billing/checkout")
async def create_checkout(payload: CheckoutRequest, ctx=Depends(require_clinic_member)):
    """Start a Stripe Checkout session. STUB — returns not-configured for now."""
    if not STRIPE_ENABLED:
        return _NOT_CONFIGURED
    # TODO: create Stripe Checkout session and return its URL.
    return _NOT_CONFIGURED


@router.post("/billing/portal")
async def billing_portal(ctx=Depends(require_clinic_member)):
    """Open the Stripe customer billing portal. STUB — not configured yet."""
    if not STRIPE_ENABLED:
        return _NOT_CONFIGURED
    return _NOT_CONFIGURED


# ============== SUPER-ADMIN (Cobros) ==============

@router.get("/admin/billing/overview")
async def billing_overview(user=Depends(require_super_admin)):
    """Billing overview across all clinics: plan mix + MRR estimate (real data)."""
    plans = _plans_map()
    res = sdb.table('clinics').select(
        'id,name,plan,plan_expires_at,is_active,created_at'
    ).order('created_at', desc=True).execute()
    clinics = res.data or []

    mrr = 0.0
    active_count = 0
    by_plan: dict[str, dict] = {}
    rows = []
    for c in clinics:
        plan_code = c.get('plan')
        p = plans.get(plan_code, {})
        price = float(p.get('price_monthly') or 0)
        is_active = bool(c.get('is_active'))
        if is_active:
            mrr += price
            active_count += 1
        agg = by_plan.setdefault(plan_code or 'sin_plan', {"plan_code": plan_code, "plan_name": p.get('name') or plan_code, "count": 0, "mrr": 0.0})
        agg["count"] += 1
        if is_active:
            agg["mrr"] += price
        rows.append({
            "clinic_id": c.get('id'),
            "name": c.get('name'),
            "plan_code": plan_code,
            "plan_name": p.get('name') or plan_code,
            "price_monthly": price,
            "currency": "USD",
            "status": "active" if is_active else "suspended",
            "expires_at": c.get('plan_expires_at'),
        })

    return {
        "stripe_configured": STRIPE_ENABLED,
        "summary": {
            "total_clinics": len(clinics),
            "active_clinics": active_count,
            "mrr": round(mrr, 2),
            "arr": round(mrr * 12, 2),
        },
        "by_plan": list(by_plan.values()),
        "clinics": rows,
    }


@router.post("/admin/billing/stripe/connect")
async def stripe_connect(user=Depends(require_super_admin)):
    """Connect the platform Stripe account. STUB — not configured yet."""
    return {
        "ok": False,
        "configured": STRIPE_ENABLED,
        "message": "Configura STRIPE_API_KEY en el backend para habilitar los cobros. (Integración pendiente)",
    }
