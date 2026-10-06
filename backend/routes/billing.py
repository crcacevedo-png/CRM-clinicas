"""SaaS subscription billing — real Stripe integration.

Flow B (BYOK): reads `STRIPE_API_KEY` from env. The operator can set their own
key in Manage → Secrets (Emergent platform) once ready; the pre-injected
`sk_test_emergent` sandbox works for testing.

Lifecycle:
  1. Super Admin opens Cobros → sees status + hits "Sincronizar planes" (one-off)
     to create Stripe Products+Prices from the `plans` table (idempotent).
  2. Clinic Admin opens Configuración → Plan, picks a plan + billing cycle,
     hits "Actualizar plan" → POST /api/billing/checkout → gets Checkout URL.
  3. On success, webhook `checkout.session.completed` writes
     stripe_customer_id + stripe_subscription_id + plan + plan_expires_at
     to the clinic row.
  4. Clinic Admin can open "Portal de facturación" (Stripe Customer Portal)
     to update card / download invoices / cancel.
  5. Webhooks `customer.subscription.updated/deleted` + `invoice.payment_failed`
     keep clinic status in sync.
"""
import os
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from core import sdb, require_super_admin, require_clinic_member, now_iso, logger

router = APIRouter()

STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_ENABLED = bool(STRIPE_API_KEY)
if STRIPE_ENABLED:
    stripe.api_key = STRIPE_API_KEY


def _not_configured_resp():
    return {
        "ok": False,
        "configured": False,
        "message": "La pasarela de pago no está configurada. El operador debe agregar STRIPE_API_KEY en Manage → Secrets.",
        "checkout_url": None,
    }


def _lookup_key(plan_code: str, cycle: str) -> str:
    return f"clinicwise_{plan_code}_{cycle}"


def _price_id_for(plan_code: str, cycle: str) -> Optional[str]:
    """Resolve the Stripe price ID for (plan, cycle).

    First try the DB cache (plans.stripe_price_monthly / yearly); then fallback
    to Stripe lookup_keys. Returns None if the plan isn't synced yet.
    """
    if not STRIPE_ENABLED:
        return None
    try:
        row = sdb.table('plans').select('*').eq('code', plan_code).maybe_single().execute()
        p = getattr(row, 'data', None)
        if p:
            cached = p.get('stripe_price_monthly') if cycle == 'monthly' else p.get('stripe_price_yearly')
            if cached:
                return cached
    except Exception:
        pass
    # Fallback: live lookup
    try:
        res = stripe.Price.list(lookup_keys=[_lookup_key(plan_code, cycle)], active=True, limit=1).data
        if res:
            return res[0].id
    except Exception as e:
        logger.warning(f"stripe price lookup failed: {e}")
    return None


def _plans_map() -> dict:
    try:
        res = sdb.table('plans').select('*').execute()
        return {p['code']: p for p in (res.data or [])}
    except Exception as e:
        logger.warning(f"billing plans_map failed: {e}")
        return {}


@router.get("/plans")
async def list_plans(ctx=Depends(require_clinic_member)):
    """Public (any clinic member) — plans catalog for the Billing UI."""
    try:
        res = sdb.table('plans').select(
            'code,name,price_monthly,price_yearly,stripe_price_monthly,stripe_price_yearly'
        ).order('price_monthly').execute()
        return res.data or []
    except Exception as e:
        logger.error(f"list_plans failed: {e}")
        return []


# ============== SETUP (Super Admin) ==============

@router.post("/admin/billing/sync-stripe-catalog")
async def sync_stripe_catalog(user=Depends(require_super_admin)):
    """Idempotently create Stripe Products + Prices from the `plans` table.

    For each plan row with price_monthly > 0, we create:
      - A Product (identified by metadata.plan_code = <code>)
      - A monthly recurring Price with lookup_key `clinicwise_<code>_monthly`
      - A yearly recurring Price with lookup_key `clinicwise_<code>_yearly` (if price_yearly > 0)
    Then we persist product_id/price_ids back into `plans`.
    """
    if not STRIPE_ENABLED:
        return _not_configured_resp()
    try:
        plans = sdb.table('plans').select('*').execute().data or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error leyendo planes: {e}")

    stats = {"products": 0, "prices_created": 0, "prices_reused": 0, "skipped": 0, "errors": []}
    tax_code = "txcd_10103001"  # SaaS

    for plan in plans:
        code = plan.get('code')
        price_monthly = float(plan.get('price_monthly') or 0)
        price_yearly = float(plan.get('price_yearly') or 0)
        if not code or price_monthly <= 0:
            stats["skipped"] += 1
            continue
        try:
            # Find or create product by metadata.plan_code
            product = None
            for p in stripe.Product.list(active=True, limit=100).auto_paging_iter():
                if p.metadata.get('plan_code') == code:
                    product = p
                    break
            if not product:
                product = stripe.Product.create(
                    name=f"ClinicWise · {plan.get('name') or code}",
                    tax_code=tax_code,
                    metadata={"managed_by": "clinicwise", "plan_code": code},
                )
                stats["products"] += 1
            else:
                stats["products"] += 1  # count reused as well

            # --- Monthly price
            monthly_id = _ensure_price(
                product.id,
                lookup_key=_lookup_key(code, 'monthly'),
                amount_cents=int(round(price_monthly * 100)),
                interval='month',
                stats=stats,
            )
            yearly_id = None
            if price_yearly > 0:
                yearly_id = _ensure_price(
                    product.id,
                    lookup_key=_lookup_key(code, 'yearly'),
                    amount_cents=int(round(price_yearly * 100)),
                    interval='year',
                    stats=stats,
                )

            sdb.table('plans').update({
                "stripe_product_id": product.id,
                "stripe_price_monthly": monthly_id,
                "stripe_price_yearly": yearly_id,
            }).eq('code', code).execute()
        except Exception as e:
            logger.error(f"sync_stripe_catalog plan={code} failed: {e}")
            stats["errors"].append(f"{code}: {str(e)[:150]}")

    return {"ok": True, "configured": True, "counters": stats}


def _ensure_price(product_id: str, lookup_key: str, amount_cents: int, interval: str, stats: dict) -> str:
    """Reuse an existing active price if amount matches, else create a new one."""
    existing = stripe.Price.list(lookup_keys=[lookup_key], active=True, limit=1).data
    if existing:
        p = existing[0]
        if p.unit_amount == amount_cents and p.currency == 'usd' and p.recurring and p.recurring.interval == interval:
            stats["prices_reused"] += 1
            return p.id
        # Price mismatch — deactivate the old one and create a new one with the same lookup_key.
        stripe.Price.modify(p.id, active=False, lookup_key=None)
    new_price = stripe.Price.create(
        product=product_id,
        unit_amount=amount_cents,
        currency='usd',
        lookup_key=lookup_key,
        transfer_lookup_key=True,
        recurring={"interval": interval},
    )
    stats["prices_created"] += 1
    return new_price.id


# ============== CLINIC-FACING ==============

@router.get("/billing/subscription")
async def my_subscription(ctx=Depends(require_clinic_member)):
    """Current clinic's plan + billing status (reads clinic row + Stripe status if any)."""
    clinic_id = ctx["member"]["clinic_id"]
    row = sdb.table('clinics').select(
        'id,name,plan,plan_expires_at,is_active,max_users,max_patients,max_storage_mb,'
        'stripe_customer_id,stripe_subscription_id,stripe_subscription_status,billing_cycle'
    ).eq('id', clinic_id).single().execute()
    c = row.data or {}
    plan_code = c.get('plan')
    plan = _plans_map().get(plan_code, {})
    sub_status = c.get('stripe_subscription_status')
    # Pull live subscription metadata if we have a sub id
    sub_info = None
    if STRIPE_ENABLED and c.get('stripe_subscription_id'):
        try:
            sub = stripe.Subscription.retrieve(c['stripe_subscription_id'])
            sub_info = {
                "id": sub.id,
                "status": sub.status,
                "cancel_at_period_end": sub.cancel_at_period_end,
                "current_period_end": sub.current_period_end,
            }
            sub_status = sub.status
        except Exception as e:
            logger.warning(f"stripe sub retrieve failed: {e}")
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
        "stripe_subscription_status": sub_status,
        "stripe_subscription": sub_info,
        "billing_cycle": c.get('billing_cycle'),
        "has_customer": bool(c.get('stripe_customer_id')),
        "limits": {
            "max_users": c.get('max_users'),
            "max_patients": c.get('max_patients'),
            "max_storage_mb": c.get('max_storage_mb'),
        },
    }


class CheckoutRequest(BaseModel):
    plan_code: str
    billing_cycle: str = "monthly"  # monthly | yearly
    origin_url: str


@router.post("/billing/checkout")
async def create_checkout(payload: CheckoutRequest, ctx=Depends(require_clinic_member)):
    """Create a Stripe Checkout session for a subscription plan."""
    if not STRIPE_ENABLED:
        return _not_configured_resp()
    if payload.billing_cycle not in ("monthly", "yearly"):
        raise HTTPException(status_code=400, detail="billing_cycle debe ser monthly o yearly")
    price_id = _price_id_for(payload.plan_code, payload.billing_cycle)
    if not price_id:
        raise HTTPException(
            status_code=400,
            detail="El plan aún no está sincronizado con Stripe. El Super Admin debe presionar 'Sincronizar planes' en Cobros."
        )
    clinic_id = ctx["member"]["clinic_id"]
    clinic = sdb.table('clinics').select('*').eq('id', clinic_id).single().execute().data

    # Create (or reuse) Stripe Customer tied to our clinic_id
    customer_id = clinic.get('stripe_customer_id')
    if not customer_id:
        try:
            customer = stripe.Customer.create(
                name=clinic.get('name'),
                email=ctx.get("user", {}).get("email") if isinstance(ctx, dict) else None,
                metadata={"clinic_id": clinic_id},
            )
            customer_id = customer.id
            sdb.table('clinics').update({"stripe_customer_id": customer_id, "updated_at": now_iso()}).eq('id', clinic_id).execute()
        except Exception as e:
            logger.error(f"stripe customer create failed: {e}")
            raise HTTPException(status_code=500, detail="Error creando cliente Stripe")

    origin = (payload.origin_url or "").rstrip('/')
    success_url = f"{origin}/dashboard/configuracion?billing=success&session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin}/dashboard/configuracion?billing=cancel"
    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer=customer_id,
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "clinic_id": clinic_id,
                "plan_code": payload.plan_code,
                "billing_cycle": payload.billing_cycle,
            },
            subscription_data={
                "metadata": {
                    "clinic_id": clinic_id,
                    "plan_code": payload.plan_code,
                    "billing_cycle": payload.billing_cycle,
                },
            },
        )
    except Exception as e:
        logger.error(f"stripe checkout create failed: {e}")
        raise HTTPException(status_code=500, detail=f"Error creando sesión de pago: {str(e)[:120]}")

    # Insert transaction row BEFORE redirecting
    try:
        sdb.table('billing_transactions').insert({
            "id": str(uuid.uuid4()),
            "clinic_id": clinic_id,
            "session_id": session.id,
            "customer_id": customer_id,
            "plan_code": payload.plan_code,
            "billing_cycle": payload.billing_cycle,
            "status": "initiated",
            "payment_status": "pending",
            "currency": "USD",
            "metadata": {"plan_code": payload.plan_code, "cycle": payload.billing_cycle},
            "created_at": now_iso(), "updated_at": now_iso(),
        }).execute()
    except Exception as e:
        logger.warning(f"billing_transactions insert failed (continuing): {e}")

    return {"ok": True, "configured": True, "checkout_url": session.url, "session_id": session.id}


@router.get("/billing/status/{session_id}")
async def billing_status(session_id: str):
    """Public — frontend polls this after redirect from Stripe success URL."""
    try:
        row = sdb.table('billing_transactions').select('*').eq('session_id', session_id).maybe_single().execute()
        rec = getattr(row, 'data', None)
        if not rec:
            raise HTTPException(status_code=404, detail="Transacción no encontrada")

        # Webhook fallback — if still pending, ask Stripe directly
        if STRIPE_ENABLED and rec.get('payment_status') != 'paid':
            try:
                s = stripe.checkout.Session.retrieve(session_id)
                if s.payment_status == 'paid' or s.status == 'complete':
                    _apply_checkout_completion(s)
                    rec = sdb.table('billing_transactions').select('*').eq('session_id', session_id).single().execute().data
            except Exception as e:
                logger.warning(f"stripe session retrieve for status failed: {e}")

        return {
            "session_id": rec['session_id'],
            "status": rec.get('status'),
            "payment_status": rec.get('payment_status'),
            "plan_code": rec.get('plan_code'),
            "billing_cycle": rec.get('billing_cycle'),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"billing_status error: {e}")
        raise HTTPException(status_code=500, detail="Error consultando estado")


@router.post("/billing/portal")
async def billing_portal(payload: dict, ctx=Depends(require_clinic_member)):
    """Open the Stripe Customer Portal for the current clinic."""
    if not STRIPE_ENABLED:
        return _not_configured_resp()
    clinic_id = ctx["member"]["clinic_id"]
    clinic = sdb.table('clinics').select('stripe_customer_id').eq('id', clinic_id).single().execute().data
    if not clinic.get('stripe_customer_id'):
        raise HTTPException(status_code=400, detail="Primero debes activar un plan para abrir el portal de facturación.")
    origin = (payload.get('origin_url') or '').rstrip('/')
    return_url = f"{origin}/dashboard/configuracion"
    try:
        sess = stripe.billing_portal.Session.create(
            customer=clinic['stripe_customer_id'],
            return_url=return_url,
        )
        return {"ok": True, "configured": True, "portal_url": sess.url}
    except Exception as e:
        logger.error(f"stripe portal failed: {e}")
        raise HTTPException(status_code=500, detail=f"Error abriendo portal: {str(e)[:120]}")


# ============== WEBHOOK ==============

@router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """Stripe → us. Keeps our DB in sync with subscription lifecycle events.

    Requires STRIPE_WEBHOOK_SECRET to be configured. Any unsigned/invalid
    request is rejected with 400 — unsigned payloads are NEVER trusted.
    """
    if not STRIPE_ENABLED:
        raise HTTPException(status_code=503, detail="Stripe no está configurado")
    if not STRIPE_WEBHOOK_SECRET:
        # Hard reject when the secret is missing — never trust unsigned bodies.
        logger.warning("stripe webhook rejected: STRIPE_WEBHOOK_SECRET not configured")
        raise HTTPException(status_code=400, detail="Firma inválida")
    payload = await request.body()
    sig = request.headers.get('stripe-signature', '')
    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        logger.warning(f"stripe webhook sig verify failed: {e}")
        raise HTTPException(status_code=400, detail="Firma inválida")

    etype = event.get('type') if isinstance(event, dict) else event['type']
    try:
        obj = event['data']['object'] if isinstance(event, dict) else event.data.object
    except (KeyError, AttributeError, TypeError):
        logger.warning(f"stripe webhook malformed event: {etype}")
        return {"status": "ignored"}
    try:
        if etype == 'checkout.session.completed':
            _apply_checkout_completion(obj)
        elif etype in ('customer.subscription.updated', 'customer.subscription.created'):
            _apply_subscription_update(obj)
        elif etype == 'customer.subscription.deleted':
            _apply_subscription_cancellation(obj)
        elif etype == 'invoice.payment_failed':
            _apply_payment_failure(obj)
    except Exception as e:
        logger.error(f"webhook handler failed for {etype}: {e}", exc_info=True)
    return {"status": "ok"}


def _apply_checkout_completion(session_obj):
    """session_obj may be a dict (webhook) or a Stripe object."""
    def g(k, default=None):
        return session_obj.get(k, default) if isinstance(session_obj, dict) else getattr(session_obj, k, default)

    session_id = g('id')
    metadata = g('metadata') or {}
    clinic_id = metadata.get('clinic_id')
    plan_code = metadata.get('plan_code')
    billing_cycle = metadata.get('billing_cycle')
    subscription_id = g('subscription')
    customer_id = g('customer')

    # Idempotent: skip if already paid
    try:
        existing = sdb.table('billing_transactions').select('payment_status').eq('session_id', session_id).maybe_single().execute()
        if existing and getattr(existing, 'data', None) and existing.data.get('payment_status') == 'paid':
            return
    except Exception:
        pass

    sdb.table('billing_transactions').update({
        "status": "completed",
        "payment_status": "paid",
        "subscription_id": subscription_id,
        "customer_id": customer_id,
        "updated_at": now_iso(),
    }).eq('session_id', session_id).execute()

    # Compute plan_expires_at from the subscription period
    expires_at = None
    if subscription_id:
        try:
            sub = stripe.Subscription.retrieve(subscription_id)
            if sub.current_period_end:
                expires_at = datetime.fromtimestamp(sub.current_period_end, tz=timezone.utc).isoformat()
            status = sub.status
        except Exception as e:
            logger.warning(f"sub retrieve on checkout.completed failed: {e}")
            status = 'active'
    else:
        status = 'active'

    if clinic_id:
        update_payload = {
            "stripe_customer_id": customer_id,
            "stripe_subscription_id": subscription_id,
            "stripe_subscription_status": status,
            "billing_cycle": billing_cycle,
            "is_active": True,
            "updated_at": now_iso(),
        }
        if plan_code:
            update_payload["plan"] = plan_code
        if expires_at:
            update_payload["plan_expires_at"] = expires_at
        sdb.table('clinics').update(update_payload).eq('id', clinic_id).execute()


def _apply_subscription_update(sub_obj):
    def g(k, default=None):
        return sub_obj.get(k, default) if isinstance(sub_obj, dict) else getattr(sub_obj, k, default)
    sub_id = g('id')
    status = g('status')
    cpe = g('current_period_end')
    expires_at = datetime.fromtimestamp(cpe, tz=timezone.utc).isoformat() if cpe else None
    try:
        rows = sdb.table('clinics').select('id').eq('stripe_subscription_id', sub_id).execute().data or []
        for r in rows:
            update_payload = {"stripe_subscription_status": status, "updated_at": now_iso()}
            if expires_at:
                update_payload["plan_expires_at"] = expires_at
            if status in ('active', 'trialing'):
                update_payload["is_active"] = True
            elif status in ('canceled', 'incomplete_expired', 'unpaid'):
                update_payload["is_active"] = False
            sdb.table('clinics').update(update_payload).eq('id', r['id']).execute()
    except Exception as e:
        logger.warning(f"apply sub update failed: {e}")


def _apply_subscription_cancellation(sub_obj):
    def g(k, default=None):
        return sub_obj.get(k, default) if isinstance(sub_obj, dict) else getattr(sub_obj, k, default)
    sub_id = g('id')
    try:
        sdb.table('clinics').update({
            "stripe_subscription_status": "canceled",
            "is_active": False,
            "updated_at": now_iso(),
        }).eq('stripe_subscription_id', sub_id).execute()
    except Exception as e:
        logger.warning(f"apply sub cancel failed: {e}")


def _apply_payment_failure(invoice_obj):
    def g(k, default=None):
        return invoice_obj.get(k, default) if isinstance(invoice_obj, dict) else getattr(invoice_obj, k, default)
    sub_id = g('subscription')
    if not sub_id:
        return
    try:
        sdb.table('clinics').update({
            "stripe_subscription_status": "past_due",
            "updated_at": now_iso(),
        }).eq('stripe_subscription_id', sub_id).execute()
    except Exception as e:
        logger.warning(f"apply payment failure failed: {e}")


# ============== SUPER-ADMIN (Cobros) ==============

@router.get("/admin/billing/overview")
async def billing_overview(user=Depends(require_super_admin)):
    """Billing overview across all clinics: plan mix + MRR + Stripe status."""
    plans = _plans_map()
    res = sdb.table('clinics').select(
        'id,name,plan,plan_expires_at,is_active,created_at,'
        'stripe_customer_id,stripe_subscription_id,stripe_subscription_status,billing_cycle'
    ).is_('deleted_at', 'null').order('created_at', desc=True).execute()
    clinics = res.data or []

    mrr = 0.0
    active_count = 0
    with_sub = 0
    by_plan: dict = {}
    rows = []
    for c in clinics:
        plan_code = c.get('plan')
        p = plans.get(plan_code, {})
        price_monthly = float(p.get('price_monthly') or 0)
        price_yearly = float(p.get('price_yearly') or 0)
        is_active = bool(c.get('is_active'))
        cycle = c.get('billing_cycle') or 'monthly'
        # MRR normalization: yearly / 12
        monthly_eq = price_yearly / 12 if cycle == 'yearly' and price_yearly else price_monthly
        has_sub = bool(c.get('stripe_subscription_id'))
        if has_sub and c.get('stripe_subscription_status') in ('active', 'trialing'):
            mrr += monthly_eq
            with_sub += 1
        if is_active:
            active_count += 1
        agg = by_plan.setdefault(plan_code or 'sin_plan', {
            "plan_code": plan_code, "plan_name": p.get('name') or plan_code,
            "count": 0, "mrr": 0.0,
            "synced": bool(p.get('stripe_price_monthly')),
        })
        agg["count"] += 1
        if has_sub and c.get('stripe_subscription_status') in ('active', 'trialing'):
            agg["mrr"] += monthly_eq
        rows.append({
            "clinic_id": c.get('id'),
            "name": c.get('name'),
            "plan_code": plan_code,
            "plan_name": p.get('name') or plan_code,
            "price_monthly": price_monthly,
            "currency": "USD",
            "status": "active" if is_active else "suspended",
            "expires_at": c.get('plan_expires_at'),
            "stripe_customer_id": c.get('stripe_customer_id'),
            "stripe_subscription_id": c.get('stripe_subscription_id'),
            "stripe_subscription_status": c.get('stripe_subscription_status'),
            "billing_cycle": cycle,
        })

    return {
        "stripe_configured": STRIPE_ENABLED,
        "summary": {
            "total_clinics": len(clinics),
            "active_clinics": active_count,
            "with_subscription": with_sub,
            "mrr": round(mrr, 2),
            "arr": round(mrr * 12, 2),
        },
        "by_plan": list(by_plan.values()),
        "clinics": rows,
    }


@router.get("/admin/billing/transactions")
async def billing_transactions(limit: int = 50, user=Depends(require_super_admin)):
    """Recent Stripe transactions log."""
    try:
        res = sdb.table('billing_transactions').select('*').order('created_at', desc=True).limit(limit).execute()
        rows = res.data or []
        # Attach clinic name
        clinic_ids = list({r.get('clinic_id') for r in rows if r.get('clinic_id')})
        name_map = {}
        if clinic_ids:
            cs = sdb.table('clinics').select('id,name').in_('id', clinic_ids).execute().data or []
            name_map = {c['id']: c['name'] for c in cs}
        for r in rows:
            r['clinic_name'] = name_map.get(r.get('clinic_id'), '—')
        return {"transactions": rows}
    except Exception as e:
        logger.error(f"billing_transactions error: {e}")
        raise HTTPException(status_code=500, detail="Error")
