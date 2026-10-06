"""One-shot migration: rebrand the Stripe catalog from "ClinicWise" to
"Cortexia Medical".

What it does on the LIVE Stripe account tied to STRIPE_API_KEY:
  1. For each plan row in `plans` that has a stripe_product_id:
     - Rename the Stripe product to "Cortexia Medical <name>"
     - Set metadata.managed_by = "cortexia_medical" (keeps plan_code)
  2. For each monthly/yearly price referenced by a plan:
     - Clear the old `clinicwise_*` lookup_key on the price (if present)
     - Set the new `cortexia_*` lookup_key via transfer_lookup_key=True
       (this moves the key from any other price that had it, idempotent)
  3. Does NOT touch active subscriptions — they reference price_id directly
  4. Does NOT create new products or prices

Idempotent: safe to re-run. Prints a per-row summary and exits with 0 on
success, 1 if any row failed.

Usage:
    cd /app/backend && python -m services.rebrand_migration
"""
from __future__ import annotations

import logging
import os
import sys

import stripe
from dotenv import load_dotenv

# Load backend .env so STRIPE_API_KEY is picked up when run standalone
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from core import sdb  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("rebrand")


OLD_PREFIX = "clinicwise_"
NEW_PREFIX = "cortexia_"


def _new_lookup_key(plan_code: str, cycle: str) -> str:
    return f"{NEW_PREFIX}{plan_code}_{cycle}"


def _rename_price_lookup_key(price_id: str, new_lk: str) -> str:
    """Set `new_lk` on `price_id`, transferring from any other price that owns it.

    Stripe's `transfer_lookup_key=True` on a Price.modify call will atomically
    move the lookup_key from whichever price currently holds it to this one.
    If this price already owns the key, it's a no-op.
    """
    stripe.Price.modify(price_id, lookup_key=new_lk, transfer_lookup_key=True)
    return new_lk


def rebrand_product(plan: dict) -> dict:
    code = plan.get("code")
    name = plan.get("name") or code
    product_id = plan.get("stripe_product_id")
    if not product_id:
        return {"code": code, "status": "skipped", "reason": "no stripe_product_id"}

    try:
        prod = stripe.Product.retrieve(product_id)
    except Exception as e:
        return {"code": code, "status": "error", "reason": f"product fetch: {e}"}

    target_name = f"Cortexia Medical {name}"
    needs_name = (prod.name or "") != target_name
    try:
        meta = dict(prod.metadata or {})
    except Exception:
        meta = {}
    needs_meta = meta.get("managed_by") != "cortexia_medical"

    update_payload = {}
    if needs_name:
        update_payload["name"] = target_name
    if needs_meta:
        meta["managed_by"] = "cortexia_medical"
        meta["plan_code"] = code
        update_payload["metadata"] = meta

    if update_payload:
        try:
            stripe.Product.modify(product_id, **update_payload)
        except Exception as e:
            return {"code": code, "status": "error", "reason": f"product modify: {e}"}

    # Prices
    renamed = []
    for cycle, price_field in (("monthly", "stripe_price_monthly"), ("yearly", "stripe_price_yearly")):
        price_id = plan.get(price_field)
        if not price_id:
            continue
        new_lk = _new_lookup_key(code, cycle)
        try:
            _rename_price_lookup_key(price_id, new_lk)
            renamed.append(new_lk)
        except stripe.error.InvalidRequestError as e:
            # If the error is "lookup_key already in use" without transfer, that's
            # a config problem that needs a human. We fail loud instead of guessing.
            return {"code": code, "status": "error", "reason": f"price {price_id} ({cycle}): {e}"}
        except Exception as e:
            return {"code": code, "status": "error", "reason": f"price {price_id} ({cycle}): {e}"}

    return {
        "code": code,
        "status": "ok",
        "renamed_product": bool(needs_name),
        "updated_metadata": bool(needs_meta),
        "lookup_keys": renamed,
    }


def main():
    api_key = os.environ.get("STRIPE_API_KEY") or ""
    if not api_key or api_key == "sk_test_emergent":
        log.error("STRIPE_API_KEY is empty or placeholder — set the LIVE key in backend/.env or run against production.")
        sys.exit(1)
    stripe.api_key = api_key
    try:
        acct = stripe.Account.retrieve()
        log.info(f"Connected to Stripe account id={acct.id} country={acct.country}")
    except Exception as e:
        log.error(f"Cannot authenticate against Stripe: {e}")
        sys.exit(1)

    plans = sdb.table("plans").select("*").execute().data or []
    log.info(f"Loaded {len(plans)} plans from DB")

    had_errors = False
    for p in plans:
        result = rebrand_product(p)
        if result["status"] == "ok":
            log.info(
                f"[{result['code']}] OK  product_renamed={result['renamed_product']} "
                f"metadata_updated={result['updated_metadata']} prices={result['lookup_keys']}"
            )
        elif result["status"] == "skipped":
            log.info(f"[{result['code']}] SKIP ({result['reason']})")
        else:
            had_errors = True
            log.error(f"[{result['code']}] FAIL ({result['reason']})")

    sys.exit(1 if had_errors else 0)


if __name__ == "__main__":
    main()
