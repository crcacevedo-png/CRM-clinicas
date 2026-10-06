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
    return f"cortexia_{plan_code}_{cycle}"


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
      - A monthly recurring Price with lookup_key `cortexia_<code>_monthly`
      - A yearly recurring Price with lookup_key `cortexia_<code>_yearly` (if price_yearly > 0)
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

    # Pre-fetch all active products so we can match by metadata OR by name.
    # name-match catches products the user created manually in Stripe before
    # running the first sync (very common on live mode).
    all_products = []
    try:
        for p in stripe.Product.list(active=True, limit=100).auto_paging_iter():
            all_products.append(p)
    except Exception as e:
        logger.error(f"sync_stripe_catalog: cannot list products: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Stripe inaccesible: {type(e).__name__}: {str(e)[:200]}")

    def _find_product_for(code: str, plan_name: str):
        """Smart matching: metadata.plan_code → exact name → name contains code."""
        plan_lower = (plan_name or '').lower()
        code_lower = (code or '').lower()
        # Pass 1: metadata.plan_code (fast path for already-synced products)
        for p in all_products:
            try:
                meta = p.metadata or {}
                meta_code = meta.get('plan_code') if hasattr(meta, 'get') else None
            except Exception:
                meta_code = None
            if meta_code == code:
                return p, 'metadata'
        # Pass 2: product name contains plan code or plan name (case-insensitive)
        for p in all_products:
            n = (getattr(p, 'name', '') or '').lower()
            if code_lower and code_lower in n:
                return p, 'name_code'
            if plan_lower and plan_lower in n:
                return p, 'name_plan'
        return None, None

    for plan in plans:
        code = plan.get('code')
        price_monthly = float(plan.get('price_monthly') or 0)
        price_yearly = float(plan.get('price_yearly') or 0)
        if not code or price_monthly <= 0:
            stats["skipped"] += 1
            continue
        try:
            product, match_by = _find_product_for(code, plan.get('name'))

            if not product:
                create_kwargs = {
                    "name": f"Cortexia Medical {plan.get('name') or code}",
                    "metadata": {"managed_by": "cortexia_medical", "plan_code": code},
                }
                # tax_code requires Stripe Tax to be enabled on the account.
                # If disabled it raises — retry without tax_code.
                try:
                    product = stripe.Product.create(tax_code=tax_code, **create_kwargs)
                except Exception as tax_err:
                    logger.warning(f"Product.create with tax_code failed for {code}, retrying without: {tax_err}")
                    product = stripe.Product.create(**create_kwargs)
                stats["products"] += 1
            else:
                # If we matched by name (user-created product), backfill
                # metadata.plan_code so the next sync is instant.
                if match_by != 'metadata':
                    try:
                        existing_meta = {}
                        try:
                            m = product.metadata or {}
                            existing_meta = {k: m[k] for k in m} if hasattr(m, 'keys') else {}
                        except Exception:
                            existing_meta = {}
                        existing_meta.update({"plan_code": code, "managed_by": "cortexia_medical"})
                        stripe.Product.modify(product.id, metadata=existing_meta)
                        logger.info(f"sync_stripe_catalog: linked existing Stripe product {product.id} to plan '{code}' by {match_by}")
                    except Exception as link_err:
                        logger.warning(f"Could not backfill metadata for {product.id}: {link_err}")
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
            # Verbose error with type name so operators can diagnose live-mode issues
            err_detail = f"{type(e).__name__}: {str(e)[:180]}" if str(e) else type(e).__name__
            logger.error(f"sync_stripe_catalog plan={code} failed: {err_detail}", exc_info=True)
            stats["errors"].append(f"{code}: {err_detail}")

    return {"ok": True, "configured": True, "counters": stats}


def _ensure_price(product_id: str, lookup_key: str, amount_cents: int, interval: str, stats: dict) -> str:
    """Reuse an existing active price if amount/interval match, else create a new one.

    Tries two matching paths so operator-created prices (no `lookup_key` set) are
    still reused instead of duplicated:
      1. Exact `lookup_key` match
      2. Any recurring price on the product with matching amount+interval+currency
         (we backfill the `lookup_key` so future syncs are instant).
    """
    # Path 1: exact lookup_key match
    existing = stripe.Price.list(lookup_keys=[lookup_key], active=True, limit=1).data
    if existing:
        p = existing[0]
        recurring = getattr(p, 'recurring', None) or {}
        rec_interval = recurring.get('interval') if hasattr(recurring, 'get') else None
        if p.unit_amount == amount_cents and p.currency == 'usd' and rec_interval == interval:
            stats["prices_reused"] += 1
            return p.id
        # Price mismatch — deactivate the old one and create fresh.
        stripe.Price.modify(p.id, active=False, lookup_key=None)

    # Path 2: match by amount+interval on this product (handles operator-created
    # prices without lookup_key). First one found wins; we backfill lookup_key.
    for p in stripe.Price.list(product=product_id, active=True, limit=100).auto_paging_iter():
        if p.unit_amount != amount_cents or p.currency != 'usd':
            continue
        recurring = getattr(p, 'recurring', None) or {}
        rec_interval = recurring.get('interval') if hasattr(recurring, 'get') else None
        if rec_interval != interval:
            continue
        try:
            stripe.Price.modify(p.id, lookup_key=lookup_key, transfer_lookup_key=True)
            logger.info(f"_ensure_price: linked existing Stripe price {p.id} as {lookup_key}")
        except Exception as link_err:
            logger.warning(f"_ensure_price could not backfill lookup_key on {p.id}: {link_err}")
        stats["prices_reused"] += 1
        return p.id

    # Nothing matched — create a new price
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

@router.get("/billing/payment-status")
async def payment_status(ctx=Depends(require_clinic_member)):
    """Current clinic's payment-block state (for banner + full-screen gate).

    IMPORTANT: this endpoint is under /billing/ so the payment-block gate in
    core.py lets it through even when the clinic is blocked — otherwise the
    frontend couldn't fetch the state to show the block screen.

    Enriched with Smart Retry info: `last_attempt_count`, `last_failure_message`,
    `next_retry_at` from the most recent entry in `payment_attempts`.
    """
    clinic_id = ctx["member"]["clinic_id"]
    c = sdb.table('clinics').select(
        'is_payment_blocked,payment_grace_until,is_courtesy,stripe_subscription_status,payment_blocked_at,name'
    ).eq('id', clinic_id).single().execute().data

    # Pull the most recent attempt for banner enrichment
    last_attempt = None
    try:
        res = sdb.table('payment_attempts').select(
            'status,attempt_count,failure_message,failure_code,next_attempt_at,attempted_at,amount_due,currency'
        ).eq('clinic_id', clinic_id).order('attempted_at', desc=True).limit(1).execute()
        rows = res.data or []
        if rows:
            last_attempt = rows[0]
    except Exception:
        pass

    return {
        "is_payment_blocked": bool(c.get('is_payment_blocked')),
        "payment_grace_until": c.get('payment_grace_until'),
        "is_courtesy": bool(c.get('is_courtesy')),
        "stripe_subscription_status": c.get('stripe_subscription_status'),
        "clinic_name": c.get('name'),
        "last_attempt_count": (last_attempt or {}).get('attempt_count') if last_attempt and last_attempt.get('status') == 'failed' else None,
        "last_failure_message": (last_attempt or {}).get('failure_message') if last_attempt and last_attempt.get('status') == 'failed' else None,
        "next_retry_at": (last_attempt or {}).get('next_attempt_at') if last_attempt and last_attempt.get('status') == 'failed' else None,
    }


@router.get("/billing/payment-attempts")
async def my_payment_attempts(ctx=Depends(require_clinic_member), limit: int = 20):
    """Return the clinic's recent Stripe payment attempts (failed + succeeded).

    Under /billing/ so blocked clinics can still inspect their retry history.
    """
    clinic_id = ctx["member"]["clinic_id"]
    try:
        res = sdb.table('payment_attempts').select(
            'id,status,attempt_count,failure_code,failure_message,amount_due,currency,'
            'next_attempt_at,attempted_at,stripe_invoice_id'
        ).eq('clinic_id', clinic_id).order('attempted_at', desc=True).limit(max(1, min(limit, 100))).execute()
        return {"attempts": res.data or []}
    except Exception as e:
        logger.warning(f"my_payment_attempts failed: {e}")
        return {"attempts": []}


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
        elif etype == 'invoice.payment_succeeded':
            _apply_payment_success(obj)
    except Exception as e:
        logger.error(f"webhook handler failed for {etype}: {e}", exc_info=True)
        # Return 500 so Stripe retries recoverable failures instead of silently
        # leaving our billing state out of sync.
        raise HTTPException(status_code=500, detail="webhook handler error")
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


def _log_payment_attempt(clinic_id: str, invoice_obj, status: str) -> dict | None:
    """Record a Stripe payment attempt in `payment_attempts`.

    Returns the inserted row or None on failure. `status` is one of
    'failed' | 'succeeded' | 'action_required'. Reads attempt_count,
    next_payment_attempt, last_payment_error from the Stripe invoice object
    (dict or Stripe object) and persists them for audit + dunning UI.
    """
    def g(k, default=None):
        return invoice_obj.get(k, default) if isinstance(invoice_obj, dict) else getattr(invoice_obj, k, default)

    try:
        last_err = g('last_payment_error') or {}
        if not isinstance(last_err, dict):
            last_err = {
                'code': getattr(last_err, 'code', None),
                'message': getattr(last_err, 'message', None),
            }
        next_at_ts = g('next_payment_attempt')
        next_at_iso = (
            datetime.fromtimestamp(next_at_ts, tz=timezone.utc).isoformat()
            if next_at_ts else None
        )
        amount_due = g('amount_due')
        row = {
            "id": str(uuid.uuid4()),
            "clinic_id": clinic_id,
            "stripe_invoice_id": g('id'),
            "stripe_subscription_id": g('subscription'),
            "stripe_charge_id": g('charge'),
            "attempt_count": g('attempt_count') or 0,
            "status": status,
            "failure_code": last_err.get('code') if isinstance(last_err, dict) else None,
            "failure_message": last_err.get('message') if isinstance(last_err, dict) else None,
            "amount_due": (amount_due / 100.0) if isinstance(amount_due, (int, float)) else None,
            "currency": (g('currency') or '').upper() or None,
            "next_attempt_at": next_at_iso,
            "attempted_at": now_iso(),
        }
        sdb.table('payment_attempts').insert(row).execute()
        return row
    except Exception as e:
        logger.warning(f"log_payment_attempt failed: {e}")
        return None


def _apply_payment_failure(invoice_obj):
    def g(k, default=None):
        return invoice_obj.get(k, default) if isinstance(invoice_obj, dict) else getattr(invoice_obj, k, default)
    sub_id = g('subscription')
    if not sub_id:
        return
    try:
        rows = sdb.table('clinics').select('id,is_courtesy,payment_grace_until').eq('stripe_subscription_id', sub_id).execute().data or []
        for r in rows:
            # Log the attempt even for courtesy clinics (audit trail)
            attempt = _log_payment_attempt(r['id'], invoice_obj, 'failed')
            if r.get('is_courtesy'):
                continue  # courtesy clinics never enter the blocking flow

            # Smart Retries: let Stripe's dunning schedule drive the grace
            # window. Add a 24h buffer after the last expected retry so the
            # clinic has time to react even if the final attempt fires right
            # at the window edge. If Stripe exhausted retries (no next_attempt),
            # fall back to a short 3-day grace before the daily cron blocks.
            next_at_ts = g('next_payment_attempt')
            if next_at_ts:
                grace_dt = datetime.fromtimestamp(next_at_ts, tz=timezone.utc) + timedelta(days=1)
            else:
                grace_dt = datetime.now(timezone.utc) + timedelta(days=3)
            # Never shrink an existing grace window — keep whichever is later
            current = r.get('payment_grace_until')
            if current:
                try:
                    cur_dt = datetime.fromisoformat(current.replace('Z', '+00:00'))
                    if cur_dt > grace_dt:
                        grace_dt = cur_dt
                except Exception:
                    pass
            grace_until = grace_dt.isoformat()

            sdb.table('clinics').update({
                "stripe_subscription_status": "past_due",
                "payment_grace_until": grace_until,
                "updated_at": now_iso(),
            }).eq('id', r['id']).execute()

            attempt_count = (attempt or {}).get('attempt_count') or 0
            _send_payment_failed_emails(
                r['id'],
                grace_until,
                attempt_count=attempt_count,
                next_attempt_at=(attempt or {}).get('next_attempt_at'),
            )
    except Exception as e:
        logger.warning(f"apply payment failure failed: {e}")


def _apply_payment_success(invoice_obj):
    """Clear block + grace on successful payment and log a success attempt."""
    def g(k, default=None):
        return invoice_obj.get(k, default) if isinstance(invoice_obj, dict) else getattr(invoice_obj, k, default)
    sub_id = g('subscription')
    if not sub_id:
        return
    try:
        rows = sdb.table('clinics').select('id').eq('stripe_subscription_id', sub_id).execute().data or []
        for r in rows:
            _log_payment_attempt(r['id'], invoice_obj, 'succeeded')
        sdb.table('clinics').update({
            "stripe_subscription_status": "active",
            "payment_grace_until": None,
            "is_payment_blocked": False,
            "payment_blocked_at": None,
            "is_active": True,
            "updated_at": now_iso(),
        }).eq('stripe_subscription_id', sub_id).execute()
    except Exception as e:
        logger.warning(f"apply payment success failed: {e}")


def _send_payment_failed_emails(clinic_id: str, grace_until: str, attempt_count: int = 0, next_attempt_at: str | None = None):
    """Email all active clinic_admins about the failed payment with Smart Retry context."""
    try:
        from services.email_service import send_email
        admins = sdb.table('clinic_members').select('email,first_name').eq('clinic_id', clinic_id).eq('role', 'clinic_admin').eq('is_active', True).is_('deleted_at', 'null').execute().data or []
        clinic = sdb.table('clinics').select('name').eq('id', clinic_id).maybe_single().execute()
        clinic_name = (clinic.data or {}).get('name', 'tu clínica') if clinic else 'tu clínica'

        attempt_line = (
            f"<p>Este fue el intento #{attempt_count}. "
            + (f"Stripe lo intentará de nuevo automáticamente el <strong>{next_attempt_at[:10]}</strong>." if next_attempt_at else "No quedan reintentos automáticos — es necesario actualizar la tarjeta cuanto antes.")
            + "</p>"
        ) if attempt_count else ""

        for a in admins:
            if not a.get('email'):
                continue
            try:
                send_email(
                    to=a['email'],
                    subject=f"⚠ Pago vencido en {clinic_name}",
                    html=(
                        f"<p>Hola {a.get('first_name','')},</p>"
                        f"<p>El cobro mensual de tu clínica <strong>{clinic_name}</strong> no pudo completarse. "
                        f"Tienes hasta el <strong>{grace_until[:10]}</strong> para actualizar tu método de pago, "
                        f"de lo contrario tu cuenta será bloqueada.</p>"
                        f"{attempt_line}"
                        f"<p>Entra al sistema y presiona <strong>Actualizar método de pago</strong> en el banner rojo "
                        f"para abrir el portal de Stripe.</p>"
                    ),
                )
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"send payment failed emails: {e}")


def _send_payment_blocked_emails(clinic_id: str):
    try:
        from services.email_service import send_email
        admins = sdb.table('clinic_members').select('email,first_name').eq('clinic_id', clinic_id).eq('role', 'clinic_admin').eq('is_active', True).is_('deleted_at', 'null').execute().data or []
        clinic = sdb.table('clinics').select('name').eq('id', clinic_id).maybe_single().execute()
        clinic_name = (clinic.data or {}).get('name', 'tu clínica') if clinic else 'tu clínica'
        for a in admins:
            if not a.get('email'):
                continue
            try:
                send_email(
                    to=a['email'],
                    subject=f"🔒 {clinic_name} bloqueada por falta de pago",
                    html=f"<p>Hola {a.get('first_name','')},</p><p>Tu clínica <strong>{clinic_name}</strong> ha sido bloqueada temporalmente por falta de pago. Para restaurar el acceso, actualiza tu método de pago desde la pantalla de inicio y Stripe aplicará el cobro pendiente.</p>",
                )
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"send payment blocked emails: {e}")


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
    courtesy_count = 0
    by_plan: dict = {}
    rows = []
    for c in clinics:
        plan_code = c.get('plan')
        p = plans.get(plan_code, {})
        price_monthly = float(p.get('price_monthly') or 0)
        price_yearly = float(p.get('price_yearly') or 0)
        is_active = bool(c.get('is_active'))
        is_courtesy = bool(c.get('is_courtesy'))
        cycle = c.get('billing_cycle') or 'monthly'
        monthly_eq = price_yearly / 12 if cycle == 'yearly' and price_yearly else price_monthly
        has_sub = bool(c.get('stripe_subscription_id'))
        if is_courtesy:
            courtesy_count += 1
        elif has_sub and c.get('stripe_subscription_status') in ('active', 'trialing'):
            mrr += monthly_eq
            with_sub += 1
        if is_active:
            active_count += 1
        agg = by_plan.setdefault(plan_code or 'sin_plan', {
            "plan_code": plan_code, "plan_name": p.get('name') or plan_code,
            "price_monthly": price_monthly,
            "count": 0, "paying_count": 0, "courtesy_count": 0, "mrr": 0.0,
            "synced": bool(p.get('stripe_price_monthly')),
        })
        agg["count"] += 1
        if is_courtesy:
            agg["courtesy_count"] += 1
        elif has_sub and c.get('stripe_subscription_status') in ('active', 'trialing'):
            agg["mrr"] += monthly_eq
            agg["paying_count"] += 1
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
            "is_courtesy": is_courtesy,
            "is_payment_blocked": bool(c.get('is_payment_blocked')),
            "payment_grace_until": c.get('payment_grace_until'),
        })

    return {
        "stripe_configured": STRIPE_ENABLED,
        "summary": {
            "total_clinics": len(clinics),
            "active_clinics": active_count,
            "with_subscription": with_sub,
            "courtesy": courtesy_count,
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


@router.get("/admin/billing/retry-dashboard")
async def retry_dashboard(user=Depends(require_super_admin)):
    """Smart Retries dashboard — clinics currently in dunning + MRR at risk.

    Powers the "En reintento" tab in Cobros. For each clinic with a payment
    attempt currently in `failed` status (and no successful attempt afterwards),
    returns: last failure, retry attempt_count, Stripe's next_payment_attempt,
    grace deadline, estimated MRR at risk.
    """
    plans = _plans_map()
    # Candidate clinics: past_due / unpaid / incomplete, not courtesy
    try:
        clinics = sdb.table('clinics').select(
            'id,name,plan,billing_cycle,is_courtesy,is_payment_blocked,'
            'payment_grace_until,payment_blocked_at,stripe_subscription_status,'
            'stripe_subscription_id'
        ).in_('stripe_subscription_status', ['past_due', 'unpaid', 'incomplete']) \
         .is_('deleted_at', 'null') \
         .eq('is_courtesy', False) \
         .execute().data or []
    except Exception as e:
        logger.warning(f"retry_dashboard clinics query failed: {e}")
        clinics = []

    rows = []
    mrr_at_risk = 0.0
    for c in clinics:
        # Most recent attempt for this clinic
        last_attempt = None
        try:
            la = sdb.table('payment_attempts').select(
                'status,attempt_count,failure_code,failure_message,amount_due,currency,'
                'next_attempt_at,attempted_at,stripe_invoice_id'
            ).eq('clinic_id', c['id']).order('attempted_at', desc=True).limit(1).execute()
            lrows = la.data or []
            if lrows:
                last_attempt = lrows[0]
        except Exception:
            pass

        p = plans.get(c.get('plan'), {})
        price_monthly = float(p.get('price_monthly') or 0)
        price_yearly = float(p.get('price_yearly') or 0)
        cycle = c.get('billing_cycle') or 'monthly'
        monthly_eq = price_yearly / 12 if cycle == 'yearly' and price_yearly else price_monthly
        mrr_at_risk += monthly_eq

        rows.append({
            "clinic_id": c.get('id'),
            "clinic_name": c.get('name'),
            "plan_code": c.get('plan'),
            "plan_name": p.get('name') or c.get('plan'),
            "monthly_price": round(monthly_eq, 2),
            "stripe_status": c.get('stripe_subscription_status'),
            "is_payment_blocked": bool(c.get('is_payment_blocked')),
            "payment_grace_until": c.get('payment_grace_until'),
            "payment_blocked_at": c.get('payment_blocked_at'),
            "last_attempt_count": (last_attempt or {}).get('attempt_count') or 0,
            "last_failure_code": (last_attempt or {}).get('failure_code'),
            "last_failure_message": (last_attempt or {}).get('failure_message'),
            "last_amount_due": (last_attempt or {}).get('amount_due'),
            "last_currency": (last_attempt or {}).get('currency'),
            "next_retry_at": (last_attempt or {}).get('next_attempt_at'),
            "last_attempted_at": (last_attempt or {}).get('attempted_at'),
        })

    # Sort: blocked first, then by grace deadline (soonest first)
    def _sort_key(r):
        if r['is_payment_blocked']:
            return (0, r.get('payment_blocked_at') or '')
        return (1, r.get('payment_grace_until') or 'z')

    rows.sort(key=_sort_key)

    return {
        "summary": {
            "clinics_in_retry": len([r for r in rows if not r['is_payment_blocked']]),
            "clinics_blocked": len([r for r in rows if r['is_payment_blocked']]),
            "mrr_at_risk": round(mrr_at_risk, 2),
        },
        "clinics": rows,
    }


@router.get("/admin/billing/payment-attempts")
async def admin_payment_attempts(
    clinic_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    user=Depends(require_super_admin),
):
    """Super-admin view of recent payment attempts (for audit + CS)."""
    try:
        q = sdb.table('payment_attempts').select('*')
        if clinic_id:
            q = q.eq('clinic_id', clinic_id)
        if status:
            q = q.eq('status', status)
        res = q.order('attempted_at', desc=True).limit(max(1, min(limit, 500))).execute()
        rows = res.data or []
        clinic_ids = list({r.get('clinic_id') for r in rows if r.get('clinic_id')})
        name_map = {}
        if clinic_ids:
            cs = sdb.table('clinics').select('id,name').in_('id', clinic_ids).execute().data or []
            name_map = {c['id']: c['name'] for c in cs}
        for r in rows:
            r['clinic_name'] = name_map.get(r.get('clinic_id'), '—')
        return {"attempts": rows}
    except Exception as e:
        logger.error(f"admin_payment_attempts error: {e}")
        raise HTTPException(status_code=500, detail="Error")
