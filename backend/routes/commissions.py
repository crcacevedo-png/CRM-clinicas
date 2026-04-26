"""Auto-extracted from server.py — DO NOT EDIT MANUALLY without checking server.py."""
import uuid
from datetime import datetime, timezone, timedelta, date
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File

router = APIRouter()

from core import sdb, supabase_admin, require_clinic_member, now_iso, logger

# ============== COMMISSIONS ROUTES ==============

# --- Settings (rules per doctor) ---
@router.get("/clinic/commissions/settings")
async def list_commission_settings(doctor_id: str = "", active_only: bool = False, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        q = sdb.table('commission_settings').select('*').eq('clinic_id', clinic_id)
        if doctor_id: q = q.eq('doctor_id', doctor_id)
        if active_only: q = q.eq('is_active', True)
        rows = q.order('created_at', desc=True).execute().data or []
        # Enrich
        for r in rows:
            mb = sdb.table('clinic_members').select('first_name,last_name').eq('id', r['doctor_id']).maybe_single().execute()
            mb_data = getattr(mb, 'data', None) if mb else None
            r['doctor_name'] = f"Dr(a). {mb_data['first_name']} {mb_data['last_name']}" if mb_data else 'Médico desconocido'
            if r.get('service_id'):
                s = sdb.table('services').select('name').eq('id', r['service_id']).maybe_single().execute()
                s_data = getattr(s, 'data', None) if s else None
                r['service_name'] = s_data['name'] if s_data else ''
            if r.get('product_id'):
                p = sdb.table('products').select('name').eq('id', r['product_id']).maybe_single().execute()
                p_data = getattr(p, 'data', None) if p else None
                r['product_name'] = p_data['name'] if p_data else ''
        return rows
    except Exception as e:
        logger.error(f"List commission settings error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@router.post("/clinic/commissions/settings")
async def create_commission_setting(data: dict, ctx=Depends(require_clinic_member)):
    if ctx["member"]["role"] != "clinic_admin":
        raise HTTPException(status_code=403, detail="Solo administradores")
    clinic_id = ctx["member"]["clinic_id"]
    if not data.get("doctor_id"):
        raise HTTPException(status_code=400, detail="Médico requerido")
    applies_to = data.get("applies_to")
    if applies_to not in ('all_consultations', 'all_products', 'service', 'product'):
        raise HTTPException(status_code=400, detail="applies_to inválido")
    calc = data.get("calculation_type")
    if calc not in ('percentage', 'fixed'):
        raise HTTPException(status_code=400, detail="calculation_type inválido")
    if calc == 'percentage' and not (data.get("percentage") and float(data["percentage"]) > 0):
        raise HTTPException(status_code=400, detail="Porcentaje requerido")
    if calc == 'percentage' and float(data.get("percentage") or 0) > 100:
        raise HTTPException(status_code=400, detail="Porcentaje no puede exceder 100%")
    if calc == 'fixed' and not (data.get("fixed_amount") and float(data["fixed_amount"]) > 0):
        raise HTTPException(status_code=400, detail="Monto fijo requerido")
    if applies_to == 'service' and not data.get("service_id"):
        raise HTTPException(status_code=400, detail="Servicio requerido")
    if applies_to == 'product' and not data.get("product_id"):
        raise HTTPException(status_code=400, detail="Producto requerido")
    try:
        from datetime import date as dt_date
        doc = {
            "id": str(uuid.uuid4()), "clinic_id": clinic_id,
            "doctor_id": data["doctor_id"], "applies_to": applies_to,
            "calculation_type": calc,
            "percentage": float(data.get("percentage") or 0) if calc == 'percentage' else None,
            "fixed_amount": float(data.get("fixed_amount") or 0) if calc == 'fixed' else None,
            "service_id": data.get("service_id") if applies_to == 'service' else None,
            "product_id": data.get("product_id") if applies_to == 'product' else None,
            "is_active": data.get("is_active", True),
            "effective_from": data.get("effective_from") or dt_date.today().isoformat(),
            "effective_to": data.get("effective_to"),
        }
        sdb.table('commission_settings').insert(doc).execute()
        return {"id": doc["id"], "message": "Regla creada"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create commission setting error: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@router.put("/clinic/commissions/settings/{rule_id}")
async def update_commission_setting(rule_id: str, data: dict, ctx=Depends(require_clinic_member)):
    if ctx["member"]["role"] != "clinic_admin":
        raise HTTPException(status_code=403, detail="Solo administradores")
    clinic_id = ctx["member"]["clinic_id"]
    if data.get("applies_to") and data["applies_to"] not in ('all_consultations', 'all_products', 'service', 'product'):
        raise HTTPException(status_code=400, detail="applies_to inválido")
    if data.get("calculation_type") and data["calculation_type"] not in ('percentage', 'fixed'):
        raise HTTPException(status_code=400, detail="calculation_type inválido")
    try:
        allowed = ['applies_to','calculation_type','percentage','fixed_amount','service_id','product_id','is_active','effective_from','effective_to']
        update = {k: v for k, v in data.items() if k in allowed}
        update['updated_at'] = now_iso()
        sdb.table('commission_settings').update(update).eq('id', rule_id).eq('clinic_id', clinic_id).execute()
        return {"message": "Regla actualizada"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update commission setting error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@router.delete("/clinic/commissions/settings/{rule_id}")
async def delete_commission_setting(rule_id: str, ctx=Depends(require_clinic_member)):
    if ctx["member"]["role"] != "clinic_admin":
        raise HTTPException(status_code=403, detail="Solo administradores")
    clinic_id = ctx["member"]["clinic_id"]
    try:
        sdb.table('commission_settings').delete().eq('id', rule_id).eq('clinic_id', clinic_id).execute()
        return {"message": "Regla eliminada"}
    except Exception as e:
        logger.error(f"Delete commission setting error: {e}")
        raise HTTPException(status_code=500, detail="Error")

# --- Auto-calculation helper (called after a sale is committed) ---
def _compute_commissions_for_sale(clinic_id: str, sale_id: str, doctor_id: str, items: list, branch_id: str):
    """For each item in the sale find applicable commission rules and insert commissions_earned rows."""
    from datetime import date as dt_date
    today = dt_date.today().isoformat()
    rules = sdb.table('commission_settings').select('*').eq('clinic_id', clinic_id).eq('doctor_id', doctor_id).eq('is_active', True).lte('effective_from', today).order('created_at', desc=True).execute().data or []
    # Filter by effective_to
    rules = [r for r in rules if not r.get('effective_to') or r['effective_to'] >= today]
    if not rules:
        return 0
    inserted = 0
    now = now_iso()
    for it in items:
        # Determine which rule applies (priority: specific > general)
        match = None
        if it.get('service_id'):
            for r in rules:
                if r.get('applies_to') == 'service' and r.get('service_id') == it['service_id']:
                    match = r; break
            if not match:
                for r in rules:
                    if r.get('applies_to') == 'all_consultations':
                        match = r; break
        elif it.get('product_id'):
            for r in rules:
                if r.get('applies_to') == 'product' and r.get('product_id') == it['product_id']:
                    match = r; break
            if not match:
                for r in rules:
                    if r.get('applies_to') == 'all_products':
                        match = r; break
        if not match:
            continue
        base = float(it.get('subtotal') or 0)  # pre-tax line subtotal
        if match['calculation_type'] == 'percentage':
            commission = round(base * (float(match.get('percentage') or 0) / 100), 2)
        else:
            commission = round(float(match.get('fixed_amount') or 0) * float(it.get('quantity') or 1), 2)
        if commission <= 0:
            continue
        sdb.table('commissions_earned').insert({
            "id": str(uuid.uuid4()), "clinic_id": clinic_id,
            "doctor_id": doctor_id, "sale_id": sale_id,
            "sale_item_id": it.get('id'),
            "base_amount": base, "commission_amount": commission,
            "status": "earned", "earned_at": now, "created_at": now,
        }).execute()
        inserted += 1
    return inserted

# --- Earned commissions (list + filters) ---
@router.get("/clinic/commissions/earned")
async def list_commissions_earned(
    doctor_id: str = "", status: str = "",
    date_from: str = "", date_to: str = "",
    page: int = 1, limit: int = 50,
    ctx=Depends(require_clinic_member),
):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        q = sdb.table('commissions_earned').select('*', count='exact').eq('clinic_id', clinic_id)
        if doctor_id: q = q.eq('doctor_id', doctor_id)
        if status: q = q.eq('status', status)
        if date_from: q = q.gte('earned_at', date_from)
        if date_to: q = q.lte('earned_at', date_to + "T23:59:59Z")
        offset = (page - 1) * limit
        result = q.order('earned_at', desc=True).range(offset, offset + limit - 1).execute()
        rows = result.data or []
        for r in rows:
            mb = sdb.table('clinic_members').select('first_name,last_name').eq('id', r['doctor_id']).maybe_single().execute()
            mb_data = getattr(mb, 'data', None) if mb else None
            r['doctor_name'] = f"{mb_data['first_name']} {mb_data['last_name']}" if mb_data else ''
            if r.get('sale_id'):
                s = sdb.table('sales').select('sale_number,customer_name').eq('id', r['sale_id']).maybe_single().execute()
                s_data = getattr(s, 'data', None) if s else None
                r['sale_number'] = s_data['sale_number'] if s_data else ''
                r['customer_name'] = s_data.get('customer_name') if s_data else ''
            if r.get('sale_item_id'):
                si = sdb.table('sale_items').select('description').eq('id', r['sale_item_id']).maybe_single().execute()
                si_data = getattr(si, 'data', None) if si else None
                r['item_description'] = si_data['description'] if si_data else ''
        return {"commissions": rows, "total": result.count or 0, "page": page, "pages": ((result.count or 0) + limit - 1) // limit}
    except Exception as e:
        logger.error(f"List commissions earned error: {e}")
        raise HTTPException(status_code=500, detail="Error")

# --- Dashboard (per-doctor totals) ---
@router.get("/clinic/commissions/dashboard")
async def commissions_dashboard(
    date_from: str = "", date_to: str = "", doctor_id: str = "",
    ctx=Depends(require_clinic_member)
):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        from datetime import datetime as dt
        if not date_from:
            date_from = dt.now(timezone.utc).date().replace(day=1).isoformat()
        if not date_to:
            today = dt.now(timezone.utc).date()
            date_to = today.isoformat()
        q = sdb.table('commissions_earned').select('doctor_id,base_amount,commission_amount,status').eq('clinic_id', clinic_id).gte('earned_at', date_from).lte('earned_at', date_to + "T23:59:59Z")
        if doctor_id: q = q.eq('doctor_id', doctor_id)
        rows = q.execute().data or []
        total_earned = sum(float(r.get('commission_amount') or 0) for r in rows)
        total_paid = sum(float(r.get('commission_amount') or 0) for r in rows if r.get('status') == 'paid')
        total_pending = sum(float(r.get('commission_amount') or 0) for r in rows if r.get('status') == 'earned')
        # Per-doctor table
        by_doctor = {}
        for r in rows:
            d = r['doctor_id']
            if d not in by_doctor:
                by_doctor[d] = {"doctor_id": d, "base_total": 0.0, "earned_total": 0.0, "paid_total": 0.0, "pending_total": 0.0, "count": 0}
            by_doctor[d]["base_total"] += float(r.get('base_amount') or 0)
            by_doctor[d]["earned_total"] += float(r.get('commission_amount') or 0)
            by_doctor[d]["count"] += 1
            if r.get('status') == 'paid':
                by_doctor[d]["paid_total"] += float(r.get('commission_amount') or 0)
            else:
                by_doctor[d]["pending_total"] += float(r.get('commission_amount') or 0)
        # Enrich with names
        for d, v in by_doctor.items():
            mb = sdb.table('clinic_members').select('first_name,last_name').eq('id', d).maybe_single().execute()
            mb_data = getattr(mb, 'data', None) if mb else None
            v['doctor_name'] = f"Dr(a). {mb_data['first_name']} {mb_data['last_name']}" if mb_data else 'Médico'
            for k in ('base_total','earned_total','paid_total','pending_total'):
                v[k] = round(v[k], 2)
        return {
            "date_from": date_from, "date_to": date_to,
            "total_earned": round(total_earned, 2),
            "total_paid": round(total_paid, 2),
            "total_pending": round(total_pending, 2),
            "by_doctor": list(by_doctor.values()),
        }
    except Exception as e:
        logger.error(f"Commissions dashboard error: {e}")
        raise HTTPException(status_code=500, detail="Error")

# --- Bulk pay commissions ---
@router.post("/clinic/commissions/pay")
async def pay_commissions(data: dict, ctx=Depends(require_clinic_member)):
    if ctx["member"]["role"] != "clinic_admin":
        raise HTTPException(status_code=403, detail="Solo administradores")
    clinic_id = ctx["member"]["clinic_id"]
    ids = data.get("commission_ids") or []
    if not ids:
        raise HTTPException(status_code=400, detail="Seleccione al menos una comisión")
    try:
        # Update each row, only if status='earned' to prevent double-payment
        rows = sdb.table('commissions_earned').select('id,commission_amount,status').in_('id', ids).eq('clinic_id', clinic_id).execute().data or []
        eligible_ids = [r['id'] for r in rows if r.get('status') == 'earned']
        if not eligible_ids:
            raise HTTPException(status_code=400, detail="Ninguna comisión elegible (ya pagadas)")
        total = sum(float(r.get('commission_amount') or 0) for r in rows if r['id'] in eligible_ids)
        now = now_iso()
        sdb.table('commissions_earned').update({
            "status": "paid", "paid_at": now,
            "payment_reference": data.get("payment_reference") or '',
        }).in_('id', eligible_ids).execute()
        return {"message": f"{len(eligible_ids)} comisión(es) pagada(s)", "count": len(eligible_ids), "total": round(total, 2)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Pay commissions error: {e}")
        raise HTTPException(status_code=500, detail="Error")

# --- PDF Report ---
@router.get("/clinic/commissions/report-pdf")
async def commissions_report_pdf(doctor_id: str = "", date_from: str = "", date_to: str = "", ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table as RLTable, TableStyle, HRFlowable
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER
        import io
        from datetime import datetime as dt
        if not date_from:
            date_from = dt.now(timezone.utc).date().replace(day=1).isoformat()
        if not date_to:
            date_to = dt.now(timezone.utc).date().isoformat()
        q = sdb.table('commissions_earned').select('*').eq('clinic_id', clinic_id).gte('earned_at', date_from).lte('earned_at', date_to + "T23:59:59Z")
        if doctor_id: q = q.eq('doctor_id', doctor_id)
        rows = q.order('earned_at').execute().data or []
        # Enrich
        for r in rows:
            mb = sdb.table('clinic_members').select('first_name,last_name').eq('id', r['doctor_id']).maybe_single().execute()
            mb_data = getattr(mb, 'data', None) if mb else None
            r['doctor_name'] = f"{mb_data['first_name']} {mb_data['last_name']}" if mb_data else ''
            if r.get('sale_id'):
                s = sdb.table('sales').select('sale_number').eq('id', r['sale_id']).maybe_single().execute()
                s_data = getattr(s, 'data', None) if s else None
                r['sale_number'] = s_data['sale_number'] if s_data else ''
            if r.get('sale_item_id'):
                si = sdb.table('sale_items').select('description').eq('id', r['sale_item_id']).maybe_single().execute()
                si_data = getattr(si, 'data', None) if si else None
                r['item_description'] = si_data['description'] if si_data else ''
        clinic = sdb.table('clinics').select('name,address,city,phone,email').eq('id', clinic_id).single().execute().data
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=18*mm, bottomMargin=18*mm, leftMargin=15*mm, rightMargin=15*mm)
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name='ClinicNameC', fontSize=14, alignment=TA_CENTER, fontName='Helvetica-Bold', textColor=colors.HexColor('#0F1A2E')))
        styles.add(ParagraphStyle(name='TitleC', fontSize=13, alignment=TA_CENTER, fontName='Helvetica-Bold', textColor=colors.HexColor('#0D9488'), spaceAfter=4))
        styles.add(ParagraphStyle(name='SubC', fontSize=9, alignment=TA_CENTER, textColor=colors.grey))
        styles.add(ParagraphStyle(name='SecC', fontSize=10, fontName='Helvetica-Bold', spaceAfter=4))

        elements = []
        elements.append(Paragraph(clinic.get('name', 'Clínica'), styles['ClinicNameC']))
        elements.append(Paragraph("Reporte de comisiones por médico", styles['TitleC']))
        elements.append(Paragraph(f"Período: {date_from} a {date_to}", styles['SubC']))
        elements.append(Spacer(1, 4*mm))
        elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#CBD5E1')))
        elements.append(Spacer(1, 4*mm))

        # Group by doctor
        by_doctor = {}
        for r in rows:
            by_doctor.setdefault(r['doctor_id'], []).append(r)
        grand_total = 0.0
        for did, drows in by_doctor.items():
            doc_name = drows[0].get('doctor_name', '')
            sub_total = round(sum(float(x.get('commission_amount') or 0) for x in drows), 2)
            grand_total += sub_total
            elements.append(Paragraph(f"Dr(a). {doc_name} — Q{sub_total:.2f}", styles['SecC']))
            tbl = [['Fecha','Venta #','Item','Base','Comisión','Estado']]
            for r in drows:
                d = (r.get('earned_at') or '')[:10]
                tbl.append([d, r.get('sale_number','—'), (r.get('item_description') or '—')[:40], f"Q{float(r.get('base_amount') or 0):.2f}", f"Q{float(r.get('commission_amount') or 0):.2f}", 'Pagada' if r.get('status') == 'paid' else 'Pendiente'])
            t = RLTable(tbl, colWidths=[60, 60, 200, 60, 65, 60])
            t.setStyle(TableStyle([
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F1A2E')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (3, 0), (4, -1), 'RIGHT'),
                ('ALIGN', (5, 0), (5, -1), 'CENTER'),
                ('LINEBELOW', (0, 0), (-1, -1), 0.3, colors.HexColor('#E2E8F0')),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            elements.append(t)
            elements.append(Spacer(1, 5*mm))

        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#0D9488')))
        elements.append(Spacer(1, 2*mm))
        elements.append(Paragraph(f"<b>Total general: Q{grand_total:.2f}</b>", styles['SecC']))
        doc.build(elements)
        pdf_bytes = buf.getvalue()
        buf.close()

        path = f"{clinic_id}/reports/commissions_{date_from}_{date_to}_{doctor_id or 'all'}_{int(dt.now(timezone.utc).timestamp())}.pdf"
        supabase_admin.storage.from_('patient-files').upload(path, pdf_bytes, {"content-type": "application/pdf", "upsert": "true"})
        signed = supabase_admin.storage.from_('patient-files').create_signed_url(path, 3600)
        return {"url": signed.get('signedURL') or signed.get('signedUrl', ''), "count": len(rows), "total": round(grand_total, 2)}
    except Exception as e:
        logger.error(f"Commissions PDF error: {e}")
        raise HTTPException(status_code=500, detail=f"Error al generar PDF: {str(e)}")


