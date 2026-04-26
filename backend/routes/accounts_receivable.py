"""Auto-extracted from server.py — DO NOT EDIT MANUALLY without checking server.py."""
import uuid
from datetime import datetime, timezone, timedelta, date
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File

router = APIRouter()

from core import sdb, supabase_admin, require_clinic_member, now_iso, logger

# ============== ACCOUNTS RECEIVABLE ROUTES ==============

def _enrich_ar(ar_list):
    """Attach patient_name, sale_number, days_overdue, and color status to a list of AR rows."""
    from datetime import datetime as dt, date
    today = dt.now(timezone.utc).date()
    for ar in ar_list:
        if ar.get('patient_id'):
            p = sdb.table('patients').select('first_name,last_name,phone,national_id').eq('id', ar['patient_id']).maybe_single().execute()
            p_data = getattr(p, 'data', None) if p else None
            ar['patient_name'] = f"{p_data['first_name']} {p_data['last_name']}" if p_data else 'Sin paciente'
            ar['patient_phone'] = p_data.get('phone') if p_data else ''
            ar['patient_national_id'] = p_data.get('national_id') if p_data else ''
        else:
            ar['patient_name'] = 'Sin paciente'
            ar['patient_phone'] = ''
            ar['patient_national_id'] = ''
        if ar.get('sale_id'):
            s = sdb.table('sales').select('sale_number,customer_name,created_at').eq('id', ar['sale_id']).maybe_single().execute()
            s_data = getattr(s, 'data', None) if s else None
            ar['sale_number'] = s_data['sale_number'] if s_data else None
            ar['sale_created_at'] = s_data['created_at'] if s_data else None
            if not ar.get('patient_id') and s_data:
                ar['patient_name'] = s_data.get('customer_name') or 'Cliente'
        # Compute overdue
        days = 0
        traffic = 'green'
        if ar.get('due_date'):
            try:
                dd = date.fromisoformat(ar['due_date'])
                days = (today - dd).days
                if days > 0: traffic = 'red'
                elif days >= -7: traffic = 'amber'
            except Exception:
                pass
        ar['days_overdue'] = days
        ar['traffic'] = traffic
    return ar_list

@router.get("/clinic/accounts-receivable/dashboard")
async def ar_dashboard(branch_id: str = "", ctx=Depends(require_clinic_member)):
    """Cards: total por cobrar, pacientes con deuda, vencidas, a vencer en 30 días."""
    clinic_id = ctx["member"]["clinic_id"]
    try:
        from datetime import datetime as dt, date, timedelta
        today = dt.now(timezone.utc).date()
        in_30 = today + timedelta(days=30)
        ars = sdb.table('accounts_receivable').select('balance,due_date,status,patient_id').eq('clinic_id', clinic_id).neq('status', 'paid').execute().data or []
        total_balance = sum(float(a.get('balance') or 0) for a in ars)
        patients_with_debt = len({a.get('patient_id') for a in ars if a.get('patient_id')})
        overdue_count = 0
        overdue_total = 0.0
        upcoming_count = 0
        upcoming_total = 0.0
        for a in ars:
            if not a.get('due_date'): continue
            try:
                dd = date.fromisoformat(a['due_date'])
            except Exception:
                continue
            bal = float(a.get('balance') or 0)
            if dd < today:
                overdue_count += 1
                overdue_total += bal
            elif dd <= in_30:
                upcoming_count += 1
                upcoming_total += bal
        return {
            "total_balance": round(total_balance, 2),
            "patients_with_debt": patients_with_debt,
            "overdue": {"count": overdue_count, "amount": round(overdue_total, 2)},
            "upcoming_30d": {"count": upcoming_count, "amount": round(upcoming_total, 2)},
        }
    except Exception as e:
        logger.error(f"AR dashboard error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@router.get("/clinic/accounts-receivable/aging")
async def ar_aging_report(ctx=Depends(require_clinic_member)):
    """Aging buckets: current, 1-30, 31-60, 61-90, 90+"""
    clinic_id = ctx["member"]["clinic_id"]
    try:
        from datetime import datetime as dt, date
        today = dt.now(timezone.utc).date()
        ars = sdb.table('accounts_receivable').select('balance,due_date,status').eq('clinic_id', clinic_id).neq('status', 'paid').execute().data or []
        buckets = {"current": {"count": 0, "amount": 0.0},
                   "d1_30": {"count": 0, "amount": 0.0},
                   "d31_60": {"count": 0, "amount": 0.0},
                   "d61_90": {"count": 0, "amount": 0.0},
                   "d90_plus": {"count": 0, "amount": 0.0}}
        for a in ars:
            bal = float(a.get('balance') or 0)
            days = 0
            if a.get('due_date'):
                try:
                    days = (today - date.fromisoformat(a['due_date'])).days
                except Exception:
                    days = 0
            if days <= 0: key = 'current'
            elif days <= 30: key = 'd1_30'
            elif days <= 60: key = 'd31_60'
            elif days <= 90: key = 'd61_90'
            else: key = 'd90_plus'
            buckets[key]["count"] += 1
            buckets[key]["amount"] = round(buckets[key]["amount"] + bal, 2)
        return buckets
    except Exception as e:
        logger.error(f"AR aging error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@router.get("/clinic/accounts-receivable/installments")
async def list_pending_installments(days_ahead: int = 90, ctx=Depends(require_clinic_member)):
    """All pending installments ordered by due_date."""
    clinic_id = ctx["member"]["clinic_id"]
    try:
        from datetime import datetime as dt, date, timedelta
        today = dt.now(timezone.utc).date()
        cutoff = (today + timedelta(days=days_ahead)).isoformat()
        # Get clinic AR ids first
        ar_ids = [a['id'] for a in (sdb.table('accounts_receivable').select('id').eq('clinic_id', clinic_id).execute().data or [])]
        if not ar_ids:
            return []
        ins = sdb.table('payment_plan_installments').select('*').in_('account_receivable_id', ar_ids).neq('status', 'paid').lte('due_date', cutoff).order('due_date').execute().data or []
        # Enrich each installment with AR + patient
        for i in ins:
            ar = sdb.table('accounts_receivable').select('patient_id,sale_id,balance').eq('id', i['account_receivable_id']).maybe_single().execute()
            ar_data = getattr(ar, 'data', None) if ar else None
            if ar_data and ar_data.get('patient_id'):
                p = sdb.table('patients').select('first_name,last_name').eq('id', ar_data['patient_id']).maybe_single().execute()
                p_data = getattr(p, 'data', None) if p else None
                i['patient_name'] = f"{p_data['first_name']} {p_data['last_name']}" if p_data else ''
            else:
                i['patient_name'] = ''
            try:
                dd = date.fromisoformat(i['due_date']) if i.get('due_date') else today
                i['days_to_due'] = (dd - today).days
            except Exception:
                i['days_to_due'] = 0
        return ins
    except Exception as e:
        logger.error(f"List installments error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@router.get("/clinic/accounts-receivable")
async def list_accounts_receivable(
    status: str = "", patient_id: str = "", q: str = "",
    only_overdue: bool = False, page: int = 1, limit: int = 30,
    ctx=Depends(require_clinic_member),
):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        from datetime import datetime as dt, date
        today = dt.now(timezone.utc).date()
        query = sdb.table('accounts_receivable').select('*', count='exact').eq('clinic_id', clinic_id)
        if status:
            query = query.eq('status', status)
        if patient_id:
            query = query.eq('patient_id', patient_id)
        if only_overdue:
            query = query.lt('due_date', today.isoformat()).neq('status', 'paid')
        offset = (page - 1) * limit
        result = query.order('due_date', desc=False).range(offset, offset + limit - 1).execute()
        ars = _enrich_ar(result.data or [])
        if q:
            qlow = q.lower()
            ars = [a for a in ars if qlow in (a.get('patient_name') or '').lower() or qlow in (a.get('sale_number') or '').lower()]
        return {"accounts": ars, "total": result.count or 0, "page": page, "pages": ((result.count or 0) + limit - 1) // limit}
    except Exception as e:
        logger.error(f"List AR error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@router.post("/clinic/accounts-receivable")
async def create_manual_ar(data: dict, ctx=Depends(require_clinic_member)):
    """Manually create an AR record (e.g. for legacy debt not tied to a system sale)."""
    clinic_id = ctx["member"]["clinic_id"]
    member = ctx["member"]
    patient_id = data.get("patient_id")
    if not patient_id:
        raise HTTPException(status_code=400, detail="Paciente requerido")
    try:
        amount = float(data.get("amount") or 0)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Monto inválido")
    if amount <= 0:
        raise HTTPException(status_code=400, detail="El monto debe ser mayor a 0")
    due_date = data.get("due_date")
    if not due_date:
        raise HTTPException(status_code=400, detail="Fecha de vencimiento requerida")
    try:
        installments = max(1, int(data.get("installments") or 1))
        notes = (data.get("notes") or "").strip()
        ar_id = str(uuid.uuid4())
        now = now_iso()
        sdb.table('accounts_receivable').insert({
            "id": ar_id, "clinic_id": clinic_id, "sale_id": None,
            "patient_id": patient_id,
            "original_amount": amount, "paid_amount": 0, "balance": amount,
            "due_date": due_date, "status": "pending",
            "has_payment_plan": installments > 1, "installments": installments,
            "notes": notes or None,
            "created_at": now, "updated_at": now,
        }).execute()
        logger.info(f"Manual AR {ar_id} created by member {member['id']} for patient {patient_id} amount {amount}")
        return {"id": ar_id, "balance": amount, "due_date": due_date}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create manual AR error: {e}")
        raise HTTPException(status_code=500, detail=f"Error al crear cuenta por cobrar: {str(e)[:200]}")

@router.get("/clinic/accounts-receivable/{ar_id}")
async def get_account_receivable(ar_id: str, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        ar = sdb.table('accounts_receivable').select('*').eq('id', ar_id).eq('clinic_id', clinic_id).single().execute().data
        ar_list = _enrich_ar([ar])
        ar = ar_list[0]
        # Sale detail
        if ar.get('sale_id'):
            sale = sdb.table('sales').select('*').eq('id', ar['sale_id']).maybe_single().execute()
            ar['sale'] = getattr(sale, 'data', None) if sale else None
            if ar['sale']:
                items = sdb.table('sale_items').select('description,quantity,unit_price,total').eq('sale_id', ar['sale_id']).execute().data or []
                ar['sale']['items'] = items
        # Payments tied to this AR
        pays = sdb.table('payments').select('*').eq('account_receivable_id', ar_id).order('paid_at').execute().data or []
        # Also fetch the original sale payments (paid at time of sale) for context
        if ar.get('sale_id'):
            sale_pays = sdb.table('payments').select('*').eq('sale_id', ar['sale_id']).is_('account_receivable_id', None).execute().data or []
            ar['initial_payments'] = sale_pays
        ar['ar_payments'] = pays
        # Installments if has plan
        if ar.get('has_payment_plan'):
            ins = sdb.table('payment_plan_installments').select('*').eq('account_receivable_id', ar_id).order('installment_number').execute().data or []
            ar['installments_list'] = ins
        else:
            ar['installments_list'] = []
        return ar
    except Exception as e:
        logger.error(f"Get AR error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@router.post("/clinic/accounts-receivable/{ar_id}/payment")
async def register_ar_payment(ar_id: str, data: dict, ctx=Depends(require_clinic_member)):
    """Register a partial/full payment against an AR."""
    clinic_id = ctx["member"]["clinic_id"]
    member_id = ctx["member"]["id"]
    amount = float(data.get("amount") or 0)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Monto inválido")
    valid_methods = {"cash", "credit_card", "debit_card", "transfer", "credit", "check", "other"}
    method = data.get("payment_method", "cash")
    if method not in valid_methods:
        raise HTTPException(status_code=400, detail=f"Método inválido: {method}")
    try:
        ar = sdb.table('accounts_receivable').select('*').eq('id', ar_id).eq('clinic_id', clinic_id).single().execute().data
        if ar['status'] == 'paid':
            raise HTTPException(status_code=400, detail="Cuenta ya pagada")
        new_paid = round(float(ar.get('paid_amount') or 0) + amount, 2)
        new_balance = round(float(ar.get('original_amount') or 0) - new_paid, 2)
        new_status = 'paid' if new_balance <= 0.001 else 'partial'
        now = now_iso()
        # Insert payment
        sdb.table('payments').insert({
            "id": str(uuid.uuid4()), "clinic_id": clinic_id,
            "sale_id": ar.get('sale_id'), "account_receivable_id": ar_id,
            "payment_method": method, "amount": amount,
            "reference": data.get("reference"), "notes": data.get("notes"),
            "received_by": member_id, "paid_at": now, "created_at": now,
        }).execute()
        # Update AR
        sdb.table('accounts_receivable').update({
            "paid_amount": new_paid, "balance": max(0.0, new_balance),
            "status": new_status, "updated_at": now,
        }).eq('id', ar_id).execute()
        # If sale exists, also keep its amounts in sync
        if ar.get('sale_id'):
            try:
                sale = sdb.table('sales').select('amount_paid,amount_due,total').eq('id', ar['sale_id']).single().execute().data
                sale_paid = round(float(sale.get('amount_paid') or 0) + amount, 2)
                sale_due = max(0.0, round(float(sale.get('total') or 0) - sale_paid, 2))
                sale_status = 'paid' if sale_due <= 0.001 else 'partial'
                sdb.table('sales').update({"amount_paid": sale_paid, "amount_due": sale_due, "payment_status": sale_status, "updated_at": now}).eq('id', ar['sale_id']).execute()
            except Exception as _e:
                logger.warning(f"Sale sync skipped: {_e}")
        return {"message": "Pago registrado", "new_balance": max(0.0, new_balance), "status": new_status}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Register AR payment error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@router.post("/clinic/accounts-receivable/{ar_id}/payment-plan")
async def create_payment_plan(ar_id: str, data: dict, ctx=Depends(require_clinic_member)):
    """Convert AR into a payment plan with installments."""
    clinic_id = ctx["member"]["clinic_id"]
    n_installments = int(data.get("installments") or 0)
    if n_installments < 2:
        raise HTTPException(status_code=400, detail="Mínimo 2 cuotas")
    if n_installments > 60:
        raise HTTPException(status_code=400, detail="Máximo 60 cuotas")
    first_due = data.get("first_due_date")
    if not first_due:
        raise HTTPException(status_code=400, detail="Fecha de primera cuota requerida")
    frequency = data.get("frequency", "monthly")  # weekly, biweekly, monthly
    try:
        ar = sdb.table('accounts_receivable').select('*').eq('id', ar_id).eq('clinic_id', clinic_id).single().execute().data
        balance = float(ar.get('balance') or 0)
        if balance <= 0:
            raise HTTPException(status_code=400, detail="Cuenta sin saldo")
        # Compute installment amount (last one absorbs rounding)
        custom_amount = data.get("amount_per_installment")
        per_amount = round(balance / n_installments, 2) if not custom_amount else float(custom_amount)
        total_planned = round(per_amount * (n_installments - 1), 2)
        last_amount = round(balance - total_planned, 2)
        # Compute due dates
        from datetime import date as dt_date, timedelta
        from dateutil.relativedelta import relativedelta
        d0 = dt_date.fromisoformat(first_due)
        def _due_for(i):
            if frequency == 'weekly': return d0 + timedelta(days=7 * i)
            if frequency == 'biweekly': return d0 + timedelta(days=14 * i)
            return d0 + relativedelta(months=i)  # monthly = true calendar months
        # Remove any pre-existing installments for this AR
        sdb.table('payment_plan_installments').delete().eq('account_receivable_id', ar_id).execute()
        for i in range(n_installments):
            amt = last_amount if i == n_installments - 1 else per_amount
            sdb.table('payment_plan_installments').insert({
                "id": str(uuid.uuid4()),
                "account_receivable_id": ar_id,
                "installment_number": i + 1,
                "amount": amt,
                "due_date": _due_for(i).isoformat(),
                "paid_amount": 0,
                "status": "pending",
            }).execute()
        sdb.table('accounts_receivable').update({
            "has_payment_plan": True, "installments": n_installments, "updated_at": now_iso(),
        }).eq('id', ar_id).execute()
        return {"message": "Plan de pagos creado", "installments": n_installments}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create payment plan error: {e}")
        raise HTTPException(status_code=500, detail="Error")


