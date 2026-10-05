"""Idempotent one-shot migration that converts legacy POS payments with
method='insurance' into Accounts Receivable charges to the insurer.

Rationale: historically a "Pago con Seguro" was captured as a payment line
with method='insurance' in `payments`, which inflated real cash in caja and
polluted the "insurance report" (promises counted as collected). The new
design treats insurance as a receivable to the insurer, collected later
through a real AR payment when the insurer deposits.

For each legacy sale that has one or more payment rows with method='insurance':
  1. Compute insurance_total (sum of those legacy insurance payments).
  2. Compute real_paid (sum of the non-insurance payments).
  3. Delete the legacy insurance payment rows (they stop counting in caja).
  4. Reduce `sales.amount_paid` by insurance_total and set `amount_due` so that
     amount_paid + amount_due = total. Status is recomputed.
  5. If an AR already exists for the sale: update it to add the insurer label
     (insurance_name, insurance_amount) and bump its balance by insurance_total
     (so insurer debt is now visible). If no AR exists: create one with the
     insurer label and the insurance balance pending.

Idempotent: all operations only run if there are legacy insurance payment rows
left for the sale. A second run finds no legacy rows and does nothing.

The migration is safe to call per-clinic or globally.
"""
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


def migrate_insurance_payments(clinic_id: Optional[str] = None) -> dict:
    """Convert legacy payment_method='insurance' rows into AR charges.

    Args:
      clinic_id: if given, only migrate that clinic; otherwise all clinics.

    Returns:
      dict with counts: sales_touched, insurance_payments_deleted,
      ars_created, ars_updated, total_insurer_debt_q.
    """
    from core import sdb, now_iso

    counters = {
        "sales_touched": 0,
        "insurance_payments_deleted": 0,
        "ars_created": 0,
        "ars_updated": 0,
        "total_insurer_debt": 0.0,
        "errors": [],
    }

    # 1) Find all legacy insurance payment rows (optionally scoped to a clinic)
    try:
        q = sdb.table('payments').select('*').eq('payment_method', 'insurance')
        if clinic_id:
            q = q.eq('clinic_id', clinic_id)
        legacy_rows = q.execute().data or []
    except Exception as e:
        logger.error(f"migrate_insurance_payments: list legacy rows failed: {e}")
        counters["errors"].append(f"list_legacy: {str(e)[:200]}")
        return counters

    if not legacy_rows:
        logger.info("migrate_insurance_payments: nothing to migrate")
        return counters

    # Group legacy rows by sale_id
    by_sale: dict[str, list[dict]] = {}
    for p in legacy_rows:
        sid = p.get('sale_id')
        if not sid:
            # Orphan insurance payment — just delete it
            try:
                sdb.table('payments').delete().eq('id', p['id']).execute()
                counters["insurance_payments_deleted"] += 1
            except Exception as e:
                counters["errors"].append(f"orphan_delete_{p.get('id')}: {str(e)[:200]}")
            continue
        by_sale.setdefault(sid, []).append(p)

    now = now_iso()
    for sale_id, rows in by_sale.items():
        try:
            # Fetch sale
            sale = sdb.table('sales').select('*').eq('id', sale_id).maybe_single().execute()
            sale_data = getattr(sale, 'data', None) if sale else None
            if not sale_data:
                # Sale was already deleted — just remove the orphan payments
                for p in rows:
                    try:
                        sdb.table('payments').delete().eq('id', p['id']).execute()
                        counters["insurance_payments_deleted"] += 1
                    except Exception:
                        pass
                continue

            sale_clinic_id = sale_data.get('clinic_id')
            total = float(sale_data.get('total') or 0)
            insurance_total = round(sum(float(p.get('amount') or 0) for p in rows), 2)
            # Pick the most frequent insurance name across the rows
            name_counts: dict[str, int] = {}
            for p in rows:
                nm = (p.get('insurance_name') or '').strip()
                if nm:
                    name_counts[nm] = name_counts.get(nm, 0) + 1
            insurer_name = max(name_counts.items(), key=lambda x: x[1])[0] if name_counts else 'Seguro'

            # Delete legacy insurance payment rows
            legacy_ids = [p['id'] for p in rows]
            try:
                sdb.table('payments').delete().in_('id', legacy_ids).execute()
                counters["insurance_payments_deleted"] += len(legacy_ids)
            except Exception as e:
                counters["errors"].append(f"delete_payments_{sale_id}: {str(e)[:200]}")
                continue

            # Recompute sale totals from remaining payments (non-insurance)
            remaining = sdb.table('payments').select('amount').eq('sale_id', sale_id).execute().data or []
            new_amount_paid = round(sum(float(x.get('amount') or 0) for x in remaining), 2)
            new_amount_due = round(max(0.0, total - new_amount_paid), 2)
            new_status = 'paid' if new_amount_due <= 0.01 else ('pending' if new_amount_paid <= 0 else 'partial')
            try:
                sdb.table('sales').update({
                    "amount_paid": new_amount_paid,
                    "amount_due": new_amount_due,
                    "payment_status": new_status,
                    "updated_at": now,
                }).eq('id', sale_id).execute()
            except Exception as e:
                counters["errors"].append(f"update_sale_{sale_id}: {str(e)[:200]}")

            # Create or update the AR
            existing_ar = sdb.table('accounts_receivable').select('*').eq('sale_id', sale_id).maybe_single().execute()
            ar_data = getattr(existing_ar, 'data', None) if existing_ar else None

            if ar_data:
                # Bump balance by the insurer debt; attach insurance label.
                try:
                    cur_balance = float(ar_data.get('balance') or 0)
                    cur_insurance_amount = float(ar_data.get('insurance_amount') or 0)
                    new_balance = round(cur_balance + insurance_total, 2)
                    new_insurance_amount = round(cur_insurance_amount + insurance_total, 2)
                    patient_portion = round(new_balance - new_insurance_amount, 2)
                    notes_parts = []
                    if new_insurance_amount > 0:
                        notes_parts.append(f"Cargo a {insurer_name}: Q{new_insurance_amount:.2f}")
                    if patient_portion > 0:
                        notes_parts.append(f"Saldo del paciente: Q{patient_portion:.2f}")
                    notes_parts.append("(Ajustado por migración retroactiva de seguros)")
                    sdb.table('accounts_receivable').update({
                        "balance": new_balance,
                        "insurance_name": ar_data.get('insurance_name') or insurer_name,
                        "insurance_amount": new_insurance_amount,
                        "status": "pending" if new_balance > 0.01 else "paid",
                        "notes": " · ".join(notes_parts),
                        "updated_at": now,
                    }).eq('id', ar_data['id']).execute()
                    counters["ars_updated"] += 1
                except Exception as e:
                    counters["errors"].append(f"update_ar_{sale_id}: {str(e)[:200]}")
            else:
                # New AR requires a patient_id (NOT NULL). Skip legacy walk-ins
                # (customer_name only, no patient_id) but still record them in the log.
                if not sale_data.get('patient_id'):
                    counters["errors"].append(
                        f"skip_ar_no_patient_{sale_id}: cargo a {insurer_name} Q{insurance_total:.2f} (venta a cliente sin paciente registrado — insurance payment removed from caja, AR not created)"
                    )
                    continue
                try:
                    due_default = (datetime.now(timezone.utc) + timedelta(days=30)).date().isoformat()
                    sdb.table('accounts_receivable').insert({
                        "id": str(uuid.uuid4()),
                        "clinic_id": sale_clinic_id,
                        "sale_id": sale_id,
                        "patient_id": sale_data.get('patient_id'),
                        "original_amount": total,
                        "paid_amount": new_amount_paid,
                        "balance": insurance_total,
                        "due_date": due_default,
                        "status": "pending" if insurance_total > 0.01 else "paid",
                        "has_payment_plan": False,
                        "installments": 0,
                        "insurance_name": insurer_name,
                        "insurance_amount": insurance_total,
                        "notes": f"Cargo a {insurer_name}: Q{insurance_total:.2f} (Creado por migración retroactiva de seguros)",
                        "created_at": now,
                        "updated_at": now,
                    }).execute()
                    counters["ars_created"] += 1
                except Exception as e:
                    counters["errors"].append(f"create_ar_{sale_id}: {str(e)[:200]}")

            counters["sales_touched"] += 1
            counters["total_insurer_debt"] += insurance_total

        except Exception as e:
            logger.error(f"migrate_insurance_payments sale={sale_id} failed: {e}")
            counters["errors"].append(f"sale_{sale_id}: {str(e)[:200]}")

    counters["total_insurer_debt"] = round(counters["total_insurer_debt"], 2)
    logger.info(f"migrate_insurance_payments done: {counters}")
    return counters
