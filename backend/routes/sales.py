"""Auto-extracted from server.py — DO NOT EDIT MANUALLY without checking server.py."""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File

router = APIRouter()

from core import sdb, supabase_admin, require_clinic_member, now_iso, logger, validate_uuid, fetch_clinic_logo_image, assert_patient_in_clinic, assert_doctor_in_clinic

from routes.commissions import _compute_commissions_for_sale

# ============== SALES / POS ROUTES ==============

# --- Services CRUD ---
@router.get("/clinic/sales/services")
async def list_services(q: str = "", category: str = "", active_only: bool = False, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        query = sdb.table('services').select('*').eq('clinic_id', clinic_id)
        if active_only:
            query = query.eq('is_active', True)
        if category:
            query = query.eq('category', category)
        if q:
            from services.input_sanitizer import sanitize_postgrest_search
            qs = sanitize_postgrest_search(q)
            query = query.or_(f'name.ilike.%{qs}%,code.ilike.%{qs}%')
        result = query.order('name').execute()
        return result.data or []
    except Exception as e:
        logger.error(f"List services error: {e}")
        raise HTTPException(status_code=500, detail="Error al listar servicios")

@router.post("/clinic/sales/services")
async def create_service(data: dict, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    if not data.get("name"):
        raise HTTPException(status_code=400, detail="Nombre requerido")
    try:
        doc = {
            "id": str(uuid.uuid4()), "clinic_id": clinic_id,
            "code": data.get("code"), "name": data["name"],
            "description": data.get("description"), "category": data.get("category"),
            "price": data.get("price", 0), "tax_rate": data.get("tax_rate", 12),
            "duration_minutes": data.get("duration_minutes"),
            "is_active": data.get("is_active", True),
        }
        sdb.table('services').insert(doc).execute()
        return {"id": doc["id"], "message": "Servicio creado"}
    except Exception as e:
        logger.error(f"Create service error: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@router.put("/clinic/sales/services/{service_id}")
async def update_service(service_id: str, data: dict, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        allowed = ['code','name','description','category','price','tax_rate','duration_minutes','is_active']
        update = {k: v for k, v in data.items() if k in allowed}
        update['updated_at'] = now_iso()
        sdb.table('services').update(update).eq('id', service_id).eq('clinic_id', clinic_id).execute()
        return {"message": "Servicio actualizado"}
    except Exception as e:
        logger.error(f"Update service error: {e}")
        raise HTTPException(status_code=500, detail="Error")

# --- Cash Registers ---
@router.get("/clinic/sales/cash-registers")
async def list_cash_registers(branch_id: str = "", ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        query = sdb.table('cash_registers').select('*').eq('clinic_id', clinic_id).eq('is_active', True)
        if branch_id:
            query = query.eq('branch_id', branch_id)
        result = query.order('name').execute()
        regs = result.data or []
        for r in regs:
            b = sdb.table('branches').select('name').eq('id', r['branch_id']).maybe_single().execute()
            b_data = getattr(b, 'data', None) if b else None
            r['branch_name'] = b_data['name'] if b_data else ''
        return regs
    except Exception as e:
        logger.error(f"List cash registers error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@router.post("/clinic/sales/cash-registers")
async def create_cash_register(data: dict, ctx=Depends(require_clinic_member)):
    if ctx["member"]["role"] != "clinic_admin":
        raise HTTPException(status_code=403, detail="Solo administradores")
    clinic_id = ctx["member"]["clinic_id"]
    if not data.get("name") or not data.get("branch_id"):
        raise HTTPException(status_code=400, detail="Nombre y sucursal requeridos")
    try:
        doc = {
            "id": str(uuid.uuid4()), "clinic_id": clinic_id,
            "branch_id": data["branch_id"], "name": data["name"], "is_active": True,
        }
        sdb.table('cash_registers').insert(doc).execute()
        return {"id": doc["id"], "message": "Caja creada"}
    except Exception as e:
        logger.error(f"Create cash register error: {e}")
        raise HTTPException(status_code=500, detail="Error")

# --- Cash Sessions ---
@router.get("/clinic/sales/cash-session/current")
async def get_current_cash_session(ctx=Depends(require_clinic_member)):
    """Get the current open cash session for the logged-in member."""
    clinic_id = ctx["member"]["clinic_id"]
    member_id = ctx["member"]["id"]
    try:
        result = sdb.table('cash_sessions').select('*').eq('clinic_id', clinic_id).eq('opened_by', member_id).eq('status', 'open').order('opened_at', desc=True).limit(1).execute()
        if not result.data:
            return {"session": None}
        session = result.data[0]
        # Enrich with register/branch
        cr = sdb.table('cash_registers').select('name,branch_id').eq('id', session['cash_register_id']).maybe_single().execute()
        cr_data = getattr(cr, 'data', None) if cr else None
        session['cash_register_name'] = cr_data['name'] if cr_data else ''
        if cr_data:
            b = sdb.table('branches').select('name').eq('id', cr_data['branch_id']).maybe_single().execute()
            b_data = getattr(b, 'data', None) if b else None
            session['branch_name'] = b_data['name'] if b_data else ''
            session['branch_id'] = cr_data['branch_id']
        return {"session": session}
    except Exception as e:
        logger.error(f"Get current cash session error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@router.post("/clinic/sales/cash-session/open")
async def open_cash_session(data: dict, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    member_id = ctx["member"]["id"]
    register_id = data.get("cash_register_id")
    if not register_id:
        raise HTTPException(status_code=400, detail="Caja requerida")
    try:
        # Ensure no other open session for this member
        existing = sdb.table('cash_sessions').select('id').eq('clinic_id', clinic_id).eq('opened_by', member_id).eq('status', 'open').execute()
        if existing.data:
            raise HTTPException(status_code=400, detail="Ya tiene una sesión de caja abierta")
        doc = {
            "id": str(uuid.uuid4()), "clinic_id": clinic_id,
            "cash_register_id": register_id, "opened_by": member_id,
            "opening_amount": data.get("opening_amount", 0),
            "opened_at": now_iso(), "status": "open",
            "notes": data.get("notes"),
        }
        sdb.table('cash_sessions').insert(doc).execute()
        return {"id": doc["id"], "message": "Caja abierta"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Open cash session error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@router.post("/clinic/sales/cash-session/{session_id}/close")
async def close_cash_session(session_id: str, data: dict, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    member_id = ctx["member"]["id"]
    actual_amount = round(float(data.get("actual_amount", 0)), 2)
    try:
        session = sdb.table('cash_sessions').select('*').eq('id', session_id).eq('clinic_id', clinic_id).single().execute().data
        if session['status'] != 'open':
            raise HTTPException(status_code=400, detail="Sesión ya cerrada")
        # Calculate expected = opening + sum of cash payments during this session
        opening = round(float(session.get('opening_amount') or 0), 2)
        sales_in_session = sdb.table('sales').select('id').eq('cash_session_id', session_id).neq('status', 'cancelled').execute()
        sale_ids = [s['id'] for s in (sales_in_session.data or [])]
        cash_total = 0.0
        if sale_ids:
            pays = sdb.table('payments').select('amount,payment_method').in_('sale_id', sale_ids).eq('payment_method', 'cash').execute()
            cash_total = round(sum(float(p.get('amount') or 0) for p in (pays.data or [])), 2)
        expected = round(opening + cash_total, 2)
        difference = round(actual_amount - expected, 2)
        sdb.table('cash_sessions').update({
            "status": "closed", "closed_at": now_iso(), "closed_by": member_id,
            "expected_amount": expected, "actual_amount": actual_amount,
            "difference": difference, "notes": data.get("notes") or session.get('notes'),
        }).eq('id', session_id).execute()
        return {"message": "Caja cerrada", "expected": expected, "actual": actual_amount, "difference": difference}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Close cash session error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@router.get("/clinic/sales/cash-session/{session_id}/summary")
async def cash_session_summary(session_id: str, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        session = sdb.table('cash_sessions').select('*').eq('id', session_id).eq('clinic_id', clinic_id).single().execute().data
        sales_in = sdb.table('sales').select('id,total').eq('cash_session_id', session_id).neq('status', 'cancelled').execute()
        sale_ids = [s['id'] for s in (sales_in.data or [])]
        totals = {"cash": 0.0, "credit_card": 0.0, "debit_card": 0.0, "transfer": 0.0, "credit": 0.0, "check": 0.0, "other": 0.0}
        if sale_ids:
            pays = sdb.table('payments').select('amount,payment_method').in_('sale_id', sale_ids).execute()
            for p in (pays.data or []):
                m = p.get('payment_method') or 'other'
                key = m if m in totals else 'other'
                totals[key] = totals.get(key, 0) + float(p.get('amount') or 0)
        opening = round(float(session.get('opening_amount') or 0), 2)
        totals = {k: round(v, 2) for k, v in totals.items()}
        expected = round(opening + totals['cash'], 2)
        return {
            "session": session,
            "opening": opening,
            "totals": totals,
            "expected": expected,
            "sales_count": len(sale_ids),
            "sales_total": round(sum(float(s.get('total') or 0) for s in (sales_in.data or [])), 2),
        }
    except Exception as e:
        logger.error(f"Cash session summary error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@router.get("/clinic/sales/cash-sessions")
async def list_cash_sessions(branch_id: str = "", date_from: str = "", date_to: str = "", page: int = 1, limit: int = 30, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        query = sdb.table('cash_sessions').select('*', count='exact').eq('clinic_id', clinic_id)
        if date_from: query = query.gte('opened_at', date_from)
        if date_to: query = query.lte('opened_at', date_to + "T23:59:59Z")
        offset = (page - 1) * limit
        result = query.order('opened_at', desc=True).range(offset, offset + limit - 1).execute()
        sessions = result.data or []
        for s in sessions:
            cr = sdb.table('cash_registers').select('name,branch_id').eq('id', s['cash_register_id']).maybe_single().execute()
            cr_data = getattr(cr, 'data', None) if cr else None
            s['cash_register_name'] = cr_data['name'] if cr_data else ''
            if cr_data and (not branch_id or cr_data['branch_id'] == branch_id):
                b = sdb.table('branches').select('name').eq('id', cr_data['branch_id']).maybe_single().execute()
                b_data = getattr(b, 'data', None) if b else None
                s['branch_name'] = b_data['name'] if b_data else ''
                s['branch_id'] = cr_data['branch_id']
            mb = sdb.table('clinic_members').select('first_name,last_name').eq('id', s['opened_by']).maybe_single().execute()
            mb_data = getattr(mb, 'data', None) if mb else None
            s['opened_by_name'] = f"{mb_data['first_name']} {mb_data['last_name']}" if mb_data else ''
        if branch_id:
            sessions = [s for s in sessions if s.get('branch_id') == branch_id]
        return {"sessions": sessions, "total": result.count or 0, "page": page, "pages": ((result.count or 0) + limit - 1) // limit}
    except Exception as e:
        logger.error(f"List cash sessions error: {e}")
        raise HTTPException(status_code=500, detail="Error")

# --- Sales (POS) ---
def _generate_sale_number(clinic_id: str) -> str:
    from datetime import datetime as dt
    prefix = dt.now(timezone.utc).strftime('%Y%m%d')
    today_start = dt.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    res = sdb.table('sales').select('id', count='exact').eq('clinic_id', clinic_id).gte('created_at', today_start).execute()
    seq = (res.count or 0) + 1
    return f"V-{prefix}-{seq:04d}"

@router.post("/clinic/sales")
async def create_sale(data: dict, ctx=Depends(require_clinic_member)):
    """Create a sale, items, payments. Decrement product stock via inventory_movements (trigger updates stock)."""
    clinic_id = ctx["member"]["clinic_id"]
    member = ctx["member"]
    items = data.get("items", [])
    payments = data.get("payments", [])
    if not items:
        raise HTTPException(status_code=400, detail="Debe agregar al menos un ítem")
    if not data.get("branch_id"):
        raise HTTPException(status_code=400, detail="Sucursal requerida")
    # Validate branch belongs to this clinic (tenant isolation)
    _br = sdb.table('branches').select('id').eq('id', data["branch_id"]).eq('clinic_id', clinic_id).maybe_single().execute()
    if not getattr(_br, 'data', None):
        raise HTTPException(status_code=400, detail="Sucursal inválida")
    # Validate optional patient/doctor belong to this clinic (IDOR guard)
    if data.get("patient_id"):
        assert_patient_in_clinic(data["patient_id"], clinic_id)
    if data.get("doctor_id"):
        assert_doctor_in_clinic(data["doctor_id"], clinic_id)
    # If a cash session is provided, force the sale's branch_id to match the session's branch.
    # This prevents the silent mismatch where a user has an open cash session in branch A but
    # the UI's active branch is B — sales must follow the cash session, not the global selector.
    cash_session_id = data.get("cash_session_id")
    if cash_session_id:
        try:
            cs = sdb.table('cash_sessions').select('id,cash_register_id,status').eq('id', cash_session_id).maybe_single().execute()
            cs_data = getattr(cs, 'data', None) if cs else None
            if not cs_data:
                raise HTTPException(status_code=400, detail="Sesión de caja no encontrada")
            if cs_data.get('status') != 'open':
                raise HTTPException(status_code=400, detail="La sesión de caja no está abierta")
            cr = sdb.table('cash_registers').select('branch_id').eq('id', cs_data['cash_register_id']).maybe_single().execute()
            cr_data = getattr(cr, 'data', None) if cr else None
            session_branch = (cr_data or {}).get('branch_id')
            if session_branch and data["branch_id"] != session_branch:
                raise HTTPException(status_code=400, detail="La sucursal de la venta no coincide con la sucursal de la caja abierta")
        except HTTPException:
            raise
        except Exception as _e:
            logger.warning(f"Could not validate cash session branch: {_e}")
    valid_methods = {"cash", "credit_card", "debit_card", "transfer", "credit", "check", "other"}
    for p in payments:
        m = p.get("payment_method")
        if m and m not in valid_methods:
            raise HTTPException(status_code=400, detail=f"Método de pago inválido: {m}")
    # Validate item numeric ranges (no negative/invalid values)
    for it in items:
        try:
            _q = float(it.get("quantity") or 0)
            _u = float(it.get("unit_price") or 0)
            _d = float(it.get("discount_pct") or 0)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Valores numéricos inválidos en un ítem")
        if _q <= 0:
            raise HTTPException(status_code=400, detail="La cantidad de cada ítem debe ser mayor a 0")
        if _u < 0:
            raise HTTPException(status_code=400, detail="El precio unitario no puede ser negativo")
        if _d < 0 or _d > 100:
            raise HTTPException(status_code=400, detail="El descuento debe estar entre 0 y 100%")
    for p in payments:
        try:
            _pa = float(p.get("amount") or 0)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Monto de pago inválido")
        if _pa < 0:
            raise HTTPException(status_code=400, detail="El monto de pago no puede ser negativo")
    try:
        # Compute totals
        subtotal = 0.0
        tax_total = 0.0
        for it in items:
            qty = float(it.get("quantity") or 0)
            unit = float(it.get("unit_price") or 0)
            disc_pct = float(it.get("discount_pct") or 0)
            line = qty * unit
            line_after_disc = line - (line * disc_pct / 100)
            tr = float(it.get("tax_rate") or 0)
            line_tax = line_after_disc * (tr / 100)
            subtotal += line_after_disc
            tax_total += line_tax
            it["_subtotal"] = line_after_disc
            it["_tax"] = line_tax
        discount_amount = float(data.get("discount_amount") or 0)
        if discount_amount > 0:
            subtotal -= discount_amount
        total = round(subtotal + tax_total, 2)
        amount_paid = round(sum(float(p.get("amount") or 0) for p in payments), 2)
        amount_due = max(0.0, round(total - amount_paid, 2))
        if amount_paid <= 0 and total > 0:
            payment_status = 'pending'
        elif amount_paid >= total:
            payment_status = 'paid'
        else:
            payment_status = 'partial'

        # If the sale has a pending balance (partial or unpaid), require a registered patient
        # because accounts_receivable.patient_id is NOT NULL and the AR record must be created.
        if amount_due > 0 and not data.get("patient_id"):
            raise HTTPException(
                status_code=400,
                detail="Para registrar pagos parciales o crédito, selecciona un paciente registrado en el carrito (no basta con el nombre del cliente)."
            )

        sale_id = str(uuid.uuid4())
        sale_number = _generate_sale_number(clinic_id)
        now = now_iso()
        sale_doc = {
            "id": sale_id, "clinic_id": clinic_id, "branch_id": data["branch_id"],
            "cash_session_id": data.get("cash_session_id"),
            "patient_id": data.get("patient_id"), "appointment_id": data.get("appointment_id"),
            "doctor_id": data.get("doctor_id"),
            "sale_number": sale_number,
            "document_type": data.get("document_type", "receipt"),
            "customer_name": data.get("customer_name"),
            "customer_id": data.get("customer_id"),
            "customer_address": data.get("customer_address"),
            "customer_email": data.get("customer_email"),
            "subtotal": round(subtotal + discount_amount, 2),
            "discount_amount": discount_amount,
            "tax_amount": round(tax_total, 2),
            "total": total,
            "amount_paid": amount_paid,
            "amount_due": amount_due,
            "payment_status": payment_status,
            "status": "completed",
            "cashier_id": member["id"],
            "notes": data.get("notes"),
            "created_at": now, "updated_at": now,
        }
        sdb.table('sales').insert(sale_doc).execute()

        # From this point on, if anything fails, rollback the sale + cascading rows.
        try:
            # Insert sale_items
            for idx, it in enumerate(items):
                qty = float(it.get("quantity") or 0)
                unit = float(it.get("unit_price") or 0)
                disc_pct = float(it.get("discount_pct") or 0)
                line = qty * unit
                disc_amount = round(line * disc_pct / 100, 2)
                tr = float(it.get("tax_rate") or 0)
                line_subtotal = round(line - disc_amount, 2)
                line_tax = round(line_subtotal * (tr / 100), 2)
                line_total = round(line_subtotal + line_tax, 2)
                sdb.table('sale_items').insert({
                    "id": str(uuid.uuid4()), "sale_id": sale_id,
                    "product_id": it.get("product_id"), "service_id": it.get("service_id"),
                    "description": it.get("description") or it.get("name"),
                    "quantity": qty, "unit_price": unit,
                    "discount_pct": disc_pct, "discount_amount": disc_amount,
                    "tax_rate": tr, "tax_amount": line_tax,
                    "subtotal": line_subtotal, "total": line_total,
                    "sort_order": idx,
                }).execute()
                # If product, register an inventory_movement (negative qty); trigger updates stock
                if it.get("product_id"):
                    sdb.table('inventory_movements').insert({
                        "id": str(uuid.uuid4()), "clinic_id": clinic_id, "product_id": it["product_id"],
                        "branch_id": data["branch_id"], "movement_type": "sale",
                        "quantity": -int(round(qty)), "unit_cost": unit,
                        "reference_type": "sale", "reference_id": sale_id,
                        "performed_by": member["id"], "created_at": now,
                    }).execute()

            # Insert payments
            for p in payments:
                amt = round(float(p.get("amount") or 0), 2)
                if amt <= 0:
                    continue
                sdb.table('payments').insert({
                    "id": str(uuid.uuid4()), "clinic_id": clinic_id, "sale_id": sale_id,
                    "payment_method": p.get("payment_method", "cash"),
                    "amount": amt, "reference": p.get("reference"),
                    "notes": p.get("notes"), "received_by": member["id"],
                    "paid_at": now, "created_at": now,
                }).execute()
        except Exception as inner_e:
            # Rollback: delete payments, inventory movements (ref this sale), sale_items, sale
            logger.error(f"Sale post-insert failed, rolling back {sale_id}: {inner_e}", exc_info=True)
            try: sdb.table('payments').delete().eq('sale_id', sale_id).execute()
            except Exception: pass
            try: sdb.table('inventory_movements').delete().eq('reference_id', sale_id).eq('reference_type', 'sale').execute()
            except Exception: pass
            try: sdb.table('sale_items').delete().eq('sale_id', sale_id).execute()
            except Exception: pass
            try: sdb.table('sales').delete().eq('id', sale_id).execute()
            except Exception: pass
            raise HTTPException(status_code=500, detail="Error al registrar la venta")

        # If amount_due > 0 → also create accounts_receivable record (best-effort; ignore if table missing)
        if amount_due > 0:
            try:
                from datetime import datetime as dt, timedelta
                due_default = (dt.now(timezone.utc) + timedelta(days=30)).date().isoformat()
                installments = int(data.get("ar_installments") or 0)
                sdb.table('accounts_receivable').insert({
                    "id": str(uuid.uuid4()), "clinic_id": clinic_id, "sale_id": sale_id,
                    "patient_id": data.get("patient_id"),
                    "original_amount": total, "paid_amount": amount_paid, "balance": amount_due,
                    "due_date": data.get("ar_due_date") or due_default,
                    "status": "pending",
                    "has_payment_plan": installments > 1, "installments": installments,
                    "created_at": now, "updated_at": now,
                }).execute()
            except Exception as _e:
                # Surface the error so the user knows the AR wasn't created
                logger.error(f"AR create failed for sale {sale_id}: {_e}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail="Venta creada pero no se pudo crear la cuenta por cobrar"
                )

        # Compute commissions for the sale's doctor (best-effort)
        if data.get("doctor_id"):
            try:
                inserted_items = sdb.table('sale_items').select('id,product_id,service_id,subtotal,quantity').eq('sale_id', sale_id).execute().data or []
                _compute_commissions_for_sale(clinic_id, sale_id, data["doctor_id"], inserted_items, data.get("branch_id"))
            except Exception as _e:
                logger.warning(f"Commission compute skipped: {_e}")

        # Generate receipt PDF (best-effort)
        try:
            await generate_sale_pdf(sale_id, clinic_id)
        except Exception as _e:
            logger.warning(f"Receipt PDF generation failed: {_e}")

        return {"id": sale_id, "sale_number": sale_number, "total": total, "amount_due": amount_due, "payment_status": payment_status}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create sale error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al procesar la venta")

@router.get("/clinic/sales")
async def list_sales(
    date_from: str = "", date_to: str = "", branch_id: str = "",
    cashier_id: str = "", payment_method: str = "", status: str = "",
    page: int = 1, limit: int = 30, ctx=Depends(require_clinic_member)
):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        query = sdb.table('sales').select('*', count='exact').eq('clinic_id', clinic_id)
        if date_from: query = query.gte('created_at', date_from)
        if date_to: query = query.lte('created_at', date_to + "T23:59:59Z")
        if branch_id: query = query.eq('branch_id', branch_id)
        if cashier_id: query = query.eq('cashier_id', cashier_id)
        if status: query = query.eq('status', status)
        offset = (page - 1) * limit
        result = query.order('created_at', desc=True).range(offset, offset + limit - 1).execute()
        sales = result.data or []
        # Batch lookup maps to avoid N+1 (cashier, branch, sale_items, payments)
        sale_ids = [s['id'] for s in sales]
        cashier_ids = list({s['cashier_id'] for s in sales if s.get('cashier_id')})
        branch_ids = list({s['branch_id'] for s in sales if s.get('branch_id')})

        cashier_map = {}
        if cashier_ids:
            cb = sdb.table('clinic_members').select('id,first_name,last_name').in_('id', cashier_ids).execute()
            for m in (cb.data or []):
                cashier_map[m['id']] = f"{m['first_name']} {m['last_name']}"

        branch_map = {}
        if branch_ids:
            br = sdb.table('branches').select('id,name').in_('id', branch_ids).execute()
            for b in (br.data or []):
                branch_map[b['id']] = b['name']

        items_by_sale = {sid: [] for sid in sale_ids}
        if sale_ids:
            items = sdb.table('sale_items').select('sale_id,description').in_('sale_id', sale_ids).execute()
            for it in (items.data or []):
                sid = it.get('sale_id')
                if sid in items_by_sale:
                    items_by_sale[sid].append(it.get('description') or '—')

        methods_by_sale = {sid: set() for sid in sale_ids}
        if sale_ids:
            pays = sdb.table('payments').select('sale_id,payment_method').in_('sale_id', sale_ids).execute()
            for p in (pays.data or []):
                sid = p.get('sale_id')
                if sid in methods_by_sale:
                    methods_by_sale[sid].add(p['payment_method'])

        for s in sales:
            s['cashier_name'] = cashier_map.get(s.get('cashier_id'), '')
            s['branch_name'] = branch_map.get(s.get('branch_id'), '')
            descs = items_by_sale.get(s['id'], [])
            s['items_summary'] = ', '.join(descs[:2]) + (f' +{len(descs)-2} más' if len(descs) > 2 else '')
            s['payment_methods'] = list(methods_by_sale.get(s['id'], set()))
        # Optional filter by payment_method (post-fetch since payments are separate)
        if payment_method:
            sales = [s for s in sales if payment_method in (s.get('payment_methods') or [])]
        return {"sales": sales, "total": result.count or 0, "page": page, "pages": ((result.count or 0) + limit - 1) // limit}
    except Exception as e:
        logger.error(f"List sales error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@router.get("/clinic/sales/daily-summary")
@router.get("/clinic/sales/dashboard")
async def daily_sales_summary(date: str = "", branch_id: str = "", ctx=Depends(require_clinic_member)):
    """Summary cards for /ventas/del-dia."""
    clinic_id = ctx["member"]["clinic_id"]
    try:
        from datetime import datetime as dt, date as dt_date
        target = dt_date.fromisoformat(date) if date else dt_date.today()
        d_from = dt.combine(target, dt.min.time(), tzinfo=timezone.utc).isoformat()
        d_to = (dt.combine(target, dt.min.time(), tzinfo=timezone.utc).replace(hour=23, minute=59, second=59)).isoformat()
        q = sdb.table('sales').select('*').eq('clinic_id', clinic_id).gte('created_at', d_from).lte('created_at', d_to).neq('status', 'cancelled')
        if branch_id:
            q = q.eq('branch_id', branch_id)
        sales = q.execute().data or []
        sale_ids = [s['id'] for s in sales]
        total_sales = sum(float(s.get('total') or 0) for s in sales)
        pending_due = sum(float(s.get('amount_due') or 0) for s in sales if (s.get('amount_due') or 0) > 0)
        cash_total = card_total = transfer_total = 0.0
        if sale_ids:
            pays = sdb.table('payments').select('amount,payment_method').in_('sale_id', sale_ids).execute().data or []
            for p in pays:
                amt = float(p.get('amount') or 0)
                m = p.get('payment_method')
                if m == 'cash': cash_total += amt
                elif m in ('credit_card', 'debit_card'): card_total += amt
                elif m == 'transfer': transfer_total += amt
        return {
            "date": target.isoformat(),
            "count": len(sales),
            "total": round(total_sales, 2),
            "cash": round(cash_total, 2),
            "card": round(card_total, 2),
            "transfer": round(transfer_total, 2),
            "pending_due": round(pending_due, 2),
        }
    except Exception as e:
        logger.error(f"Daily summary error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@router.get("/clinic/sales/{sale_id}")
async def get_sale(sale_id: str, ctx=Depends(require_clinic_member)):
    validate_uuid(sale_id, "sale_id")
    clinic_id = ctx["member"]["clinic_id"]
    try:
        sale_resp = sdb.table('sales').select('*').eq('id', sale_id).eq('clinic_id', clinic_id).maybe_single().execute()
        sale = getattr(sale_resp, 'data', None) if sale_resp else None
        if not sale:
            raise HTTPException(status_code=404, detail="Venta no encontrada")
        items = sdb.table('sale_items').select('*').eq('sale_id', sale_id).order('sort_order').execute().data or []
        pays = sdb.table('payments').select('*').eq('sale_id', sale_id).order('paid_at').execute().data or []
        sale['items'] = items
        sale['payments'] = pays
        if sale.get('cashier_id'):
            cb = sdb.table('clinic_members').select('first_name,last_name').eq('id', sale['cashier_id']).maybe_single().execute()
            cb_data = getattr(cb, 'data', None) if cb else None
            sale['cashier_name'] = f"{cb_data['first_name']} {cb_data['last_name']}" if cb_data else ''
        return sale
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get sale error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@router.post("/clinic/sales/{sale_id}/cancel")
async def cancel_sale(sale_id: str, data: dict, ctx=Depends(require_clinic_member)):
    if ctx["member"]["role"] not in ("clinic_admin", "doctor"):
        raise HTTPException(status_code=403, detail="No autorizado")
    clinic_id = ctx["member"]["clinic_id"]
    member_id = ctx["member"]["id"]
    try:
        sale = sdb.table('sales').select('*').eq('id', sale_id).eq('clinic_id', clinic_id).single().execute().data
        if sale.get('status') == 'cancelled':
            raise HTTPException(status_code=400, detail="Venta ya anulada")
        # Reverse inventory movements: insert opposite-sign movements
        items = sdb.table('sale_items').select('product_id,quantity').eq('sale_id', sale_id).execute().data or []
        now = now_iso()
        for it in items:
            if it.get('product_id') and it.get('quantity'):
                sdb.table('inventory_movements').insert({
                    "id": str(uuid.uuid4()), "clinic_id": clinic_id, "product_id": it['product_id'],
                    "branch_id": sale['branch_id'], "movement_type": "return",
                    "quantity": float(it['quantity']),
                    "reference_type": "sale_cancellation", "reference_id": sale_id,
                    "performed_by": member_id, "created_at": now,
                    "notes": "Anulación de venta",
                }).execute()
        sdb.table('sales').update({
            "status": "cancelled",
            "cancellation_reason": data.get("reason"),
            "updated_at": now,
        }).eq('id', sale_id).execute()
        return {"message": "Venta anulada"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cancel sale error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@router.get("/clinic/sales/{sale_id}/pdf-url")
async def get_sale_pdf_url(sale_id: str, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        sale = sdb.table('sales').select('id').eq('id', sale_id).eq('clinic_id', clinic_id).maybe_single().execute()
        sale_data = getattr(sale, 'data', None) if sale else None
        if not sale_data:
            raise HTTPException(status_code=404, detail="Venta no encontrada")
        path = f"{clinic_id}/sales/{sale_id}.pdf"
        from services.signed_url_cache import get_or_create_signed_url
        url = get_or_create_signed_url('patient-files', path, ttl=3600)
        if not url:
            url = await generate_sale_pdf(sale_id, clinic_id)
        return {"url": url or ""}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get sale PDF URL error: {e}")
        raise HTTPException(status_code=500, detail="Error")

async def generate_sale_pdf(sale_id: str, clinic_id: str) -> Optional[str]:
    """Generate a sale receipt PDF."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table as RLTable, TableStyle, HRFlowable
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
        import io

        sale = sdb.table('sales').select('*').eq('id', sale_id).single().execute().data
        items = sdb.table('sale_items').select('*').eq('sale_id', sale_id).order('sort_order').execute().data or []
        payments = sdb.table('payments').select('*').eq('sale_id', sale_id).execute().data or []
        clinic = sdb.table('clinics').select('name,address,city,phone,email,logo_url').eq('id', clinic_id).single().execute().data
        cashier = None
        if sale.get('cashier_id'):
            cashier_res = sdb.table('clinic_members').select('first_name,last_name').eq('id', sale['cashier_id']).maybe_single().execute()
            cashier = getattr(cashier_res, 'data', None) if cashier_res else None

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=18*mm, bottomMargin=18*mm, leftMargin=18*mm, rightMargin=18*mm)
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name='ClinicName2', fontSize=15, leading=18, alignment=TA_CENTER, fontName='Helvetica-Bold', textColor=colors.HexColor('#0F1A2E')))
        styles.add(ParagraphStyle(name='ClinicInfo2', fontSize=8, leading=10, alignment=TA_CENTER, textColor=colors.grey))
        styles.add(ParagraphStyle(name='DocTitle', fontSize=12, leading=14, alignment=TA_CENTER, fontName='Helvetica-Bold', textColor=colors.HexColor('#0D9488')))
        styles.add(ParagraphStyle(name='Lbl2', fontSize=8, leading=10, textColor=colors.grey))
        styles.add(ParagraphStyle(name='Val2', fontSize=9, leading=11, fontName='Helvetica-Bold'))
        styles.add(ParagraphStyle(name='Footer2', fontSize=8, leading=10, alignment=TA_CENTER, textColor=colors.grey))

        elements = []
        logo_flow = fetch_clinic_logo_image(clinic.get('logo_url'), max_h_mm=18)
        if logo_flow is not None:
            elements.append(logo_flow)
            elements.append(Spacer(1, 2*mm))
        elements.append(Paragraph(clinic.get('name', 'Clínica'), styles['ClinicName2']))
        addr = ', '.join(filter(None, [clinic.get('address'), clinic.get('city')]))
        contact = ' | '.join(filter(None, [clinic.get('phone'), clinic.get('email')]))
        if addr: elements.append(Paragraph(addr, styles['ClinicInfo2']))
        if contact: elements.append(Paragraph(contact, styles['ClinicInfo2']))
        elements.append(Spacer(1, 3*mm))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#0D9488')))
        elements.append(Spacer(1, 3*mm))
        doc_label = "FACTURA" if sale.get('document_type') == 'invoice' else "RECIBO"
        elements.append(Paragraph(f"{doc_label} — {sale.get('sale_number','')}", styles['DocTitle']))
        elements.append(Spacer(1, 3*mm))

        from datetime import datetime as dt
        d = dt.fromisoformat(sale['created_at'].replace('Z', '+00:00')) if sale.get('created_at') else dt.now(timezone.utc)
        meta = [
            ['Fecha:', d.strftime('%d/%m/%Y %H:%M'), 'Cajero:', f"{cashier['first_name']} {cashier['last_name']}" if cashier else '—'],
            ['Cliente:', sale.get('customer_name') or '—', 'NIT/DPI:', sale.get('customer_id') or 'CF'],
        ]
        mt = RLTable(meta, colWidths=[55, 200, 50, 150])
        mt.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.grey),
            ('TEXTCOLOR', (2, 0), (2, -1), colors.grey),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica-Bold'),
            ('FONTNAME', (3, 0), (3, -1), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        elements.append(mt)
        elements.append(Spacer(1, 4*mm))

        # Items table
        rows = [['#', 'Descripción', 'Cant.', 'P.Unit', 'Subtotal']]
        for idx, it in enumerate(items, 1):
            rows.append([str(idx), it.get('description', '—'), str(it.get('quantity', 0)), f"Q{float(it.get('unit_price') or 0):.2f}", f"Q{float(it.get('total') or 0):.2f}"])
        items_table = RLTable(rows, colWidths=[20, 280, 50, 60, 70])
        items_table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F1A2E')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (2, 0), (4, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LINEBELOW', (0, 0), (-1, 0), 0.5, colors.grey),
            ('LINEBELOW', (0, -1), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(items_table)
        elements.append(Spacer(1, 4*mm))

        # Totals
        tot_rows = [
            ['', 'Subtotal:', f"Q{float(sale.get('subtotal') or 0):.2f}"],
        ]
        if float(sale.get('discount_amount') or 0) > 0:
            tot_rows.append(['', 'Descuento:', f"-Q{float(sale['discount_amount']):.2f}"])
        if float(sale.get('tax_amount') or 0) > 0:
            tot_rows.append(['', 'IVA:', f"Q{float(sale['tax_amount']):.2f}"])
        tot_rows.append(['', 'TOTAL:', f"Q{float(sale.get('total') or 0):.2f}"])
        tt = RLTable(tot_rows, colWidths=[300, 100, 80])
        tt.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (1, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (1, -1), (-1, -1), 12),
            ('TEXTCOLOR', (1, -1), (-1, -1), colors.HexColor('#0D9488')),
            ('LINEABOVE', (1, -1), (-1, -1), 1, colors.HexColor('#0D9488')),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
        ]))
        elements.append(tt)
        elements.append(Spacer(1, 5*mm))

        # Payments
        if payments:
            elements.append(Paragraph("<b>Pagos:</b>", styles['Lbl2']))
            for p in payments:
                method_label = {'cash':'Efectivo','credit_card':'Tarjeta crédito','debit_card':'Tarjeta débito','transfer':'Transferencia','credit':'Crédito','check':'Cheque','other':'Otro'}.get(p.get('payment_method'), p.get('payment_method'))
                line = f"{method_label}: Q{float(p.get('amount') or 0):.2f}"
                if p.get('reference'):
                    line += f" — Ref: {p['reference']}"
                elements.append(Paragraph(line, styles['Val2']))
            if float(sale.get('amount_due') or 0) > 0:
                elements.append(Paragraph(f"<font color='red'><b>Saldo pendiente: Q{float(sale['amount_due']):.2f}</b></font>", styles['Val2']))
            elements.append(Spacer(1, 6*mm))

        elements.append(HRFlowable(width="60%", thickness=0.5, color=colors.HexColor('#CBD5E1'), hAlign='CENTER'))
        elements.append(Spacer(1, 2*mm))
        elements.append(Paragraph("GRACIAS POR SU PREFERENCIA", styles['Footer2']))

        doc.build(elements)
        pdf_bytes = buf.getvalue()
        buf.close()

        path = f"{clinic_id}/sales/{sale_id}.pdf"
        supabase_admin.storage.from_('patient-files').upload(path, pdf_bytes, {"content-type": "application/pdf", "upsert": "true"})
        signed = supabase_admin.storage.from_('patient-files').create_signed_url(path, 3600)
        url = signed.get('signedURL') or signed.get('signedUrl', '')
        sdb.table('sales').update({"pdf_url": url, "updated_at": now_iso()}).eq('id', sale_id).execute()
        return url
    except Exception as e:
        logger.error(f"Generate sale PDF error: {e}")
        return None


