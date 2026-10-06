"""One-shot: archive orphan Stripe prices on the two synced products.

An orphan price is defined as:
  - active=True
  - attached to a product that one of our plans points to via stripe_product_id
  - but its price_id is NOT one of the plan's stripe_price_monthly or
    stripe_price_yearly values

Typically these are the manually-created prices the operator had on Stripe
before the first sync (e.g. $39 and $79 monthly) that got duplicated when
the sync created new recurring prices with lookup_keys.

Why archive instead of delete:
  - Stripe does NOT allow deleting a Price that has ever been used.
  - Archived (`active=False`) prices stop appearing in new checkouts but
    historical invoices and subscriptions keep working.

Safety:
  - Only touches products referenced by our `plans` table — never random
    products in the Stripe account.
  - Prints the full list first, requires typed `yes` on stdin to proceed.
  - Dry-run by default: pass `--apply` to actually archive.

Usage:
    cd /app/backend && python -m services.cleanup_orphan_prices           # dry-run
    cd /app/backend && python -m services.cleanup_orphan_prices --apply   # confirm + archive
"""
from __future__ import annotations

import logging
import os
import sys

import stripe
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from core import sdb  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("cleanup")


def _fmt_amount(amount_cents, currency):
    if amount_cents is None:
        return "—"
    return f"{amount_cents / 100:.2f} {(currency or '').upper()}"


def main():
    apply = "--apply" in sys.argv

    api_key = os.environ.get("STRIPE_API_KEY") or ""
    if not api_key or api_key == "sk_test_emergent":
        log.error("STRIPE_API_KEY is empty or placeholder.")
        sys.exit(1)
    stripe.api_key = api_key

    try:
        acct = stripe.Account.retrieve()
        log.info(f"Connected to Stripe account id={acct.id} country={acct.country}")
    except Exception as e:
        log.error(f"Cannot authenticate: {e}")
        sys.exit(1)

    plans = sdb.table("plans").select("*").execute().data or []
    managed_products = {}
    kept_price_ids = set()
    for p in plans:
        pid = p.get("stripe_product_id")
        if not pid:
            continue
        managed_products[pid] = p.get("code")
        for field in ("stripe_price_monthly", "stripe_price_yearly"):
            if p.get(field):
                kept_price_ids.add(p[field])

    if not managed_products:
        log.info("No managed products found in `plans`. Nothing to do.")
        return

    log.info(f"Managed products: {managed_products}")
    log.info(f"Kept price ids: {kept_price_ids}")

    orphans = []
    for pid, code in managed_products.items():
        for price in stripe.Price.list(product=pid, active=True, limit=100).auto_paging_iter():
            if price.id in kept_price_ids:
                continue
            orphans.append({
                "price_id": price.id,
                "product_id": pid,
                "plan_code": code,
                "amount": price.unit_amount,
                "currency": price.currency,
                "lookup_key": price.lookup_key,
                "recurring": bool(getattr(price, "recurring", None)),
            })

    if not orphans:
        log.info("✅ No orphan prices found. Catalog is clean.")
        return

    print("\n" + "=" * 70)
    print(f"Found {len(orphans)} orphan active price(s) to archive:")
    print("=" * 70)
    for o in orphans:
        print(
            f"  [{o['plan_code']:<12}] {o['price_id']}  "
            f"{_fmt_amount(o['amount'], o['currency']):>12}  "
            f"lookup_key={o['lookup_key'] or '(none)'}  "
            f"recurring={o['recurring']}"
        )
    print("=" * 70)

    if not apply:
        print("\nDry-run only. Re-run with --apply to archive these prices.")
        return

    print("\nType `yes` to archive all of them (sets active=False in Stripe), anything else to cancel:")
    try:
        answer = input("> ").strip().lower()
    except EOFError:
        answer = ""
    if answer != "yes":
        print("Cancelled. Nothing was changed.")
        return

    had_errors = False
    for o in orphans:
        try:
            stripe.Price.modify(o["price_id"], active=False)
            log.info(f"ARCHIVED {o['price_id']} ({o['plan_code']}, {_fmt_amount(o['amount'], o['currency'])})")
        except Exception as e:
            had_errors = True
            log.error(f"FAILED to archive {o['price_id']}: {e}")

    if had_errors:
        sys.exit(1)
    log.info("✅ All orphan prices archived successfully.")


if __name__ == "__main__":
    main()
