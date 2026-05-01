"""Auto-extracted from server.py — DO NOT EDIT MANUALLY without checking server.py."""
import uuid
from datetime import datetime, timezone, timedelta, date
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File

router = APIRouter()

from core import sdb, supabase_admin, require_clinic_member, now_iso, logger

# ============== EXPENSES ROUTES ==============

EXPENSE_CATEGORIES = ['rent','utilities','salaries','supplies','equipment','marketing','professional_services','taxes','maintenance','other']
EXPENSE_CATEGORY_LABELS = {
    'rent':'Alquiler','utilities':'Servicios públicos','salaries':'Salarios','supplies':'Suministros',
    'equipment':'Equipo','marketing':'Marketing','professional_services':'Servicios profesionales',
    'taxes':'Impuestos','maintenance':'Mantenimiento','other':'Otro'
}

@router.get("/clinic/expenses/dashboard")
async def expenses_dashboard(branch_id: str = "", ctx=Depends(require_clinic_member)):
    """Cards: este mes, mes anterior, top categoría, pendientes."""
    clinic_id = ctx["member"]["clinic_id"]
    try:
        from datetime import datetime as dt, date as dt_date
        today = dt.now(timezone.utc).date()
        first_this = today.replace(day=1)
        if first_this.month == 1:
            first_prev = first_this.replace(year=first_this.year - 1, month=12)
        else:
            first_prev = first_this.replace(month=first_this.month - 1)
        q = sdb.table('expenses').select('amount,total,category,payment_status,expense_date').eq('clinic_id', clinic_id)
        if branch_id:
            q = q.eq('branch_id', branch_id)
        all_expenses = q.execute().data or []
        this_month = sum(float(e.get('total') or 0) for e in all_expenses if e.get('expense_date') and dt_date.fromisoformat(e['expense_date']) >= first_this)
        prev_month = sum(float(e.get('total') or 0) for e in all_expenses if e.get('expense_date') and first_prev <= dt_date.fromisoformat(e['expense_date']) < first_this)
        # Top category this month
        cat_totals = {}
        for e in all_expenses:
            if e.get('expense_date') and dt_date.fromisoformat(e['expense_date']) >= first_this:
                k = e.get('category') or 'other'
                cat_totals[k] = cat_totals.get(k, 0) + float(e.get('total') or 0)
        top_cat = max(cat_totals.items(), key=lambda x: x[1]) if cat_totals else (None, 0)
        # Pending
        pending_total = sum(float(e.get('total') or 0) for e in all_expenses if e.get('payment_status') == 'pending')
        pending_count = sum(1 for e in all_expenses if e.get('payment_status') == 'pending')
        delta_pct = ((this_month - prev_month) / prev_month * 100) if prev_month > 0 else None
        return {
            "this_month": round(this_month, 2),
            "prev_month": round(prev_month, 2),
            "delta_pct": round(delta_pct, 1) if delta_pct is not None else None,
            "top_category": {"key": top_cat[0], "label": EXPENSE_CATEGORY_LABELS.get(top_cat[0], top_cat[0]) if top_cat[0] else None, "amount": round(top_cat[1], 2)},
            "pending": {"count": pending_count, "amount": round(pending_total, 2)},
        }
    except Exception as e:
        logger.error(f"Expenses dashboard error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@router.get("/clinic/expenses/by-category")
@router.get("/clinic/expenses/categories")
async def expenses_by_category(date_from: str = "", date_to: str = "", branch_id: str = "", ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        q = sdb.table('expenses').select('total,category').eq('clinic_id', clinic_id)
        if date_from: q = q.gte('expense_date', date_from)
        if date_to: q = q.lte('expense_date', date_to)
        if branch_id: q = q.eq('branch_id', branch_id)
        rows = q.execute().data or []
        totals = {}
        for r in rows:
            k = r.get('category') or 'other'
            totals[k] = totals.get(k, 0) + float(r.get('total') or 0)
        result = [{"category": k, "label": EXPENSE_CATEGORY_LABELS.get(k, k), "amount": round(v, 2), "count": sum(1 for x in rows if (x.get('category') or 'other') == k)} for k, v in totals.items()]
        result.sort(key=lambda x: x['amount'], reverse=True)
        grand_total = round(sum(r['amount'] for r in result), 2)
        return {"categories": result, "total": grand_total}
    except Exception as e:
        logger.error(f"Expenses by category error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@router.get("/clinic/expenses/by-supplier")
async def expenses_by_supplier(date_from: str = "", date_to: str = "", ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        q = sdb.table('expenses').select('total,supplier_id').eq('clinic_id', clinic_id)
        if date_from: q = q.gte('expense_date', date_from)
        if date_to: q = q.lte('expense_date', date_to)
        rows = q.execute().data or []
        sup_totals = {}
        sup_count = {}
        for r in rows:
            sid = r.get('supplier_id')
            if not sid: continue
            sup_totals[sid] = sup_totals.get(sid, 0) + float(r.get('total') or 0)
            sup_count[sid] = sup_count.get(sid, 0) + 1
        result = []
        for sid, amount in sup_totals.items():
            sup = sdb.table('suppliers').select('name').eq('id', sid).maybe_single().execute()
            sup_data = getattr(sup, 'data', None) if sup else None
            result.append({"supplier_id": sid, "supplier_name": sup_data['name'] if sup_data else 'Desconocido', "amount": round(amount, 2), "count": sup_count[sid]})
        result.sort(key=lambda x: x['amount'], reverse=True)
        return {"suppliers": result, "total": round(sum(r['amount'] for r in result), 2)}
    except Exception as e:
        logger.error(f"Expenses by supplier error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@router.get("/clinic/expenses")
async def list_expenses(
    date_from: str = "", date_to: str = "", category: str = "",
    branch_id: str = "", supplier_id: str = "", payment_status: str = "",
    q: str = "", page: int = 1, limit: int = 30,
    ctx=Depends(require_clinic_member),
):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        query = sdb.table('expenses').select('*', count='exact').eq('clinic_id', clinic_id)
        if date_from: query = query.gte('expense_date', date_from)
        if date_to: query = query.lte('expense_date', date_to)
        if category: query = query.eq('category', category)
        if branch_id: query = query.eq('branch_id', branch_id)
        if supplier_id: query = query.eq('supplier_id', supplier_id)
        if payment_status: query = query.eq('payment_status', payment_status)
        if q: query = query.or_(f'description.ilike.%{q}%,document_number.ilike.%{q}%,subcategory.ilike.%{q}%')
        offset = (page - 1) * limit
        result = query.order('expense_date', desc=True).range(offset, offset + limit - 1).execute()
        expenses = result.data or []
        for e in expenses:
            e['category_label'] = EXPENSE_CATEGORY_LABELS.get(e.get('category'), e.get('category'))
            if e.get('supplier_id'):
                sup = sdb.table('suppliers').select('name').eq('id', e['supplier_id']).maybe_single().execute()
                sup_data = getattr(sup, 'data', None) if sup else None
                e['supplier_name'] = sup_data['name'] if sup_data else ''
            else:
                e['supplier_name'] = ''
            if e.get('branch_id'):
                br = sdb.table('branches').select('name').eq('id', e['branch_id']).maybe_single().execute()
                br_data = getattr(br, 'data', None) if br else None
                e['branch_name'] = br_data['name'] if br_data else ''
            else:
                e['branch_name'] = ''
            if e.get('registered_by'):
                mb = sdb.table('clinic_members').select('first_name,last_name').eq('id', e['registered_by']).maybe_single().execute()
                mb_data = getattr(mb, 'data', None) if mb else None
                e['registered_by_name'] = f"{mb_data['first_name']} {mb_data['last_name']}" if mb_data else ''
        return {"expenses": expenses, "total": result.count or 0, "page": page, "pages": ((result.count or 0) + limit - 1) // limit}
    except Exception as e:
        logger.error(f"List expenses error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@router.post("/clinic/expenses")
async def create_expense(data: dict, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    member_id = ctx["member"]["id"]
    if not data.get("category"):
        raise HTTPException(status_code=400, detail="Categoría requerida")
    if data["category"] not in EXPENSE_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Categoría inválida: {data['category']}")
    if not data.get("description"):
        raise HTTPException(status_code=400, detail="Descripción requerida")
    valid_methods = {"cash", "credit_card", "debit_card", "transfer", "credit", "check", "other"}
    pm = data.get("payment_method")
    if pm and pm not in valid_methods:
        raise HTTPException(status_code=400, detail=f"Método de pago inválido: {pm}")
    valid_statuses = {"pending", "partial", "paid"}
    ps = data.get("payment_status", "paid")
    if ps not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Estado inválido: {ps}")
    try:
        amount = round(float(data.get("amount") or 0), 2)
        tax = round(float(data.get("tax_amount") or 0), 2)
        total = round(amount + tax, 2)
        now = now_iso()
        from datetime import date as dt_date
        doc = {
            "id": str(uuid.uuid4()), "clinic_id": clinic_id,
            "branch_id": data.get("branch_id"),
            "category": data["category"], "subcategory": data.get("subcategory"),
            "supplier_id": data.get("supplier_id"),
            "description": data["description"],
            "amount": amount, "tax_amount": tax, "total": total,
            "payment_method": pm, "payment_status": ps,
            "document_type": data.get("document_type"), "document_number": data.get("document_number"),
            "expense_date": data.get("expense_date") or dt_date.today().isoformat(),
            "registered_by": member_id, "notes": data.get("notes"),
            "created_at": now, "updated_at": now,
        }
        sdb.table('expenses').insert(doc).execute()
        return {"id": doc["id"], "message": "Gasto registrado", "total": total}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create expense error: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@router.put("/clinic/expenses/{expense_id}")
async def update_expense(expense_id: str, data: dict, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    if data.get("payment_method"):
        valid_methods = {"cash","credit_card","debit_card","transfer","credit","check","other"}
        if data["payment_method"] not in valid_methods:
            raise HTTPException(status_code=400, detail="Método inválido")
    if data.get("category") and data["category"] not in EXPENSE_CATEGORIES:
        raise HTTPException(status_code=400, detail="Categoría inválida")
    if data.get("payment_status") and data["payment_status"] not in {"pending", "partial", "paid"}:
        raise HTTPException(status_code=400, detail="Estado inválido")
    try:
        allowed = ['branch_id','category','subcategory','supplier_id','description','amount','tax_amount','payment_method','payment_status','document_type','document_number','expense_date','notes']
        update = {k: v for k, v in data.items() if k in allowed}
        # Recompute total if amount/tax changed
        if 'amount' in update or 'tax_amount' in update:
            existing = sdb.table('expenses').select('amount,tax_amount').eq('id', expense_id).single().execute().data
            new_amount = float(update.get('amount', existing.get('amount') or 0))
            new_tax = float(update.get('tax_amount', existing.get('tax_amount') or 0))
            update['total'] = round(new_amount + new_tax, 2)
            update['amount'] = new_amount
            update['tax_amount'] = new_tax
        update['updated_at'] = now_iso()
        sdb.table('expenses').update(update).eq('id', expense_id).eq('clinic_id', clinic_id).execute()
        return {"message": "Gasto actualizado"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update expense error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@router.delete("/clinic/expenses/{expense_id}")
async def delete_expense(expense_id: str, ctx=Depends(require_clinic_member)):
    if ctx["member"]["role"] != "clinic_admin":
        raise HTTPException(status_code=403, detail="Solo administradores")
    clinic_id = ctx["member"]["clinic_id"]
    try:
        sdb.table('expenses').delete().eq('id', expense_id).eq('clinic_id', clinic_id).execute()
        return {"message": "Gasto eliminado"}
    except Exception as e:
        logger.error(f"Delete expense error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@router.post("/clinic/expenses/{expense_id}/attachment")
async def upload_expense_attachment(expense_id: str, file: UploadFile = File(...), ctx=Depends(require_clinic_member)):
    """Upload a receipt/invoice file for an expense to Supabase Storage."""
    clinic_id = ctx["member"]["clinic_id"]
    try:
        # Validate expense exists
        exp = sdb.table('expenses').select('id').eq('id', expense_id).eq('clinic_id', clinic_id).maybe_single().execute()
        if not (getattr(exp, 'data', None) if exp else None):
            raise HTTPException(status_code=404, detail="Gasto no encontrado")
        ext = (file.filename or '').rsplit('.', 1)[-1].lower() if '.' in (file.filename or '') else 'bin'
        if ext not in ('pdf', 'png', 'jpg', 'jpeg', 'webp'):
            raise HTTPException(status_code=400, detail="Tipo de archivo no permitido")
        contents = await file.read()
        if len(contents) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Archivo excede 10MB")
        path = f"{clinic_id}/expenses/{expense_id}/receipt.{ext}"
        supabase_admin.storage.from_('patient-files').upload(path, contents, {"content-type": file.content_type or "application/octet-stream", "upsert": "true"})
        signed = supabase_admin.storage.from_('patient-files').create_signed_url(path, 86400 * 7)
        url = signed.get('signedURL') or signed.get('signedUrl', '')
        sdb.table('expenses').update({"attachment_url": url, "updated_at": now_iso()}).eq('id', expense_id).execute()
        return {"url": url, "path": path}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload expense attachment error: {e}")
        raise HTTPException(status_code=500, detail="Error al subir archivo")

@router.get("/clinic/expenses/{expense_id}/attachment-url")
async def get_expense_attachment_url(expense_id: str, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        exp = sdb.table('expenses').select('id,attachment_url').eq('id', expense_id).eq('clinic_id', clinic_id).maybe_single().execute()
        exp_data = getattr(exp, 'data', None) if exp else None
        if not exp_data:
            raise HTTPException(status_code=404, detail="Gasto no encontrado")
        if not exp_data.get('attachment_url'):
            return {"url": ""}
        # Look up by listing files in path
        for ext in ('pdf','png','jpg','jpeg','webp'):
            try:
                signed = supabase_admin.storage.from_('patient-files').create_signed_url(f"{clinic_id}/expenses/{expense_id}/receipt.{ext}", 3600)
                url = signed.get('signedURL') or signed.get('signedUrl')
                if url:
                    return {"url": url}
            except Exception:
                continue
        return {"url": exp_data.get('attachment_url') or ""}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get expense attachment URL error: {e}")
        raise HTTPException(status_code=500, detail="Error")


