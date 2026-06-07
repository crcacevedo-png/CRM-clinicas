"""Auto-extracted from server.py."""
import uuid
import logging
from datetime import datetime, timezone, timedelta, date
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Body, Request
from pydantic import BaseModel

router = APIRouter()

from core import (
    sdb, supabase_admin, supabase_user, logger, now_iso,
    generate_password, generate_slug, enrich_member, get_auth_users_map,
    get_plan_limits, parse_presentations,
    require_clinic_member, require_super_admin, get_current_user,
    LoginRequest, LoginResponse, ClinicCreate, ClinicUpdate, ClinicMemberCreate, UserUpdate,
    MedicationCreate, MedicationBulkImport, LabStudyCreate, LabStudyBulkImport,
    ICD10CodeCreate, ICD10BulkImport,
    AppointmentCreate, AppointmentUpdate, AppointmentStatusUpdate,
    PatientQuickCreate, PatientFullCreate,
    require_clinical_role,
    validate_uuid,
)

# ============== LAB ORDER ROUTES ==============

class LabOrderItemInput(BaseModel):
    study_id: Optional[str] = None
    study_name: str
    category: str = ""

class LabOrderCreate(BaseModel):
    patient_id: str
    medical_record_id: Optional[str] = None
    presumptive_diagnosis: Optional[str] = None
    special_instructions: Optional[str] = None
    priority: str = "routine"
    notes: Optional[str] = None
    items: List[LabOrderItemInput] = []
    status: str = "pending"

@router.get("/clinic/lab-studies")
async def list_lab_studies(ctx=Depends(require_clinic_member)):
    """List all lab studies grouped by category"""
    clinic_id = ctx["member"]["clinic_id"]
    try:
        result = sdb.table('lab_studies').select('id,name,category,preparation').or_(f'clinic_id.is.null,clinic_id.eq.{clinic_id}').eq('is_active', True).order('category').order('name').execute()
        return result.data or []
    except Exception as e:
        logger.error(f"List lab studies error: {e}")
        raise HTTPException(status_code=500, detail="Error al listar estudios")

@router.get("/clinic/lab-orders")
async def list_lab_orders(
    patient_id: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1, limit: int = 20,
    ctx=Depends(require_clinic_member)
):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        query = sdb.table('lab_orders').select('*', count='exact').eq('clinic_id', clinic_id)
        if patient_id:
            query = query.eq('patient_id', patient_id)
        if status:
            query = query.eq('status', status)
        offset = (page - 1) * limit
        result = query.order('created_at', desc=True).range(offset, offset + limit - 1).execute()
        orders = result.data or []

        if orders:
            patient_ids = list({o['patient_id'] for o in orders if o.get('patient_id')})
            doctor_ids = list({o['doctor_id'] for o in orders if o.get('doctor_id')})
            order_ids = [o['id'] for o in orders]

            patients_map = {}
            if patient_ids:
                pats = sdb.table('patients').select('id,first_name,last_name').in_('id', patient_ids).execute()
                patients_map = {x['id']: f"{x['first_name']} {x['last_name']}" for x in (pats.data or [])}
            doctors_map = {}
            if doctor_ids:
                docs = sdb.table('clinic_members').select('id,first_name,last_name').in_('id', doctor_ids).execute()
                doctors_map = {x['id']: f"{x['first_name']} {x['last_name']}" for x in (docs.data or [])}
            items_by_order = {}
            if order_ids:
                items = sdb.table('lab_order_items').select('lab_order_id,study_name,category').in_('lab_order_id', order_ids).execute()
                for it in (items.data or []):
                    items_by_order.setdefault(it['lab_order_id'], []).append(it)

            for o in orders:
                o['patient_name'] = patients_map.get(o.get('patient_id'), '')
                o['doctor_name'] = doctors_map.get(o.get('doctor_id'), '')
                its = items_by_order.get(o['id'], [])
                o['item_count'] = len(its)
                o['study_summary'] = ', '.join([i['study_name'] for i in its[:3]])
                if len(its) > 3:
                    o['study_summary'] += f' +{len(its) - 3} más'

        return {"orders": orders, "total": result.count or 0, "page": page, "pages": ((result.count or 0) + limit - 1) // limit}
    except Exception as e:
        logger.error(f"List lab orders error: {e}")
        raise HTTPException(status_code=500, detail="Error al listar órdenes")

@router.get("/clinic/lab-orders/{order_id}")
async def get_lab_order(order_id: str, ctx=Depends(require_clinic_member)):
    validate_uuid(order_id, "order_id")
    clinic_id = ctx["member"]["clinic_id"]
    try:
        result = sdb.table('lab_orders').select('*').eq('id', order_id).eq('clinic_id', clinic_id).maybe_single().execute()
        data = getattr(result, 'data', None) if result else None
        if not data:
            raise HTTPException(status_code=404, detail="Orden no encontrada")
        order = data
        pat = sdb.table('patients').select('*').eq('id', order['patient_id']).maybe_single().execute()
        pat_data = getattr(pat, 'data', None) if pat else None
        order['patient'] = pat_data or {}
        if order['patient']:
            order['patient'].pop('search_vector', None)
        doc = sdb.table('clinic_members').select('first_name,last_name,specialty,license_number').eq('id', order['doctor_id']).maybe_single().execute()
        doc_data = getattr(doc, 'data', None) if doc else None
        order['doctor'] = doc_data or {}
        items = sdb.table('lab_order_items').select('*').eq('lab_order_id', order_id).order('sort_order').execute()
        order['items'] = items.data or []
        return order
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get lab order error: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener orden")

@router.post("/clinic/lab-orders")
async def create_lab_order(data: LabOrderCreate, ctx=Depends(require_clinic_member)):
    require_clinical_role(ctx)
    clinic_id = ctx["member"]["clinic_id"]
    member = ctx["member"]
    try:
        now = now_iso()
        order_id = str(uuid.uuid4())
        doc = {
            "id": order_id, "clinic_id": clinic_id,
            "patient_id": data.patient_id, "doctor_id": member["id"],
            "medical_record_id": data.medical_record_id,
            "presumptive_diagnosis": data.presumptive_diagnosis,
            "special_instructions": data.special_instructions,
            "priority": data.priority or "routine",
            "notes": data.notes,
            "status": data.status or "pending",
            "ordered_at": now, "created_at": now, "updated_at": now,
        }
        sdb.table('lab_orders').insert(doc).execute()

        for i, item in enumerate(data.items):
            sdb.table('lab_order_items').insert({
                "id": str(uuid.uuid4()),
                "lab_order_id": order_id,
                "study_id": item.study_id,
                "study_name": item.study_name,
                "category": item.category,
                "sort_order": i,
            }).execute()

        pdf_url = None
        if data.status == "pending":
            pdf_url = await generate_lab_order_pdf(order_id, clinic_id)

        return {"id": order_id, "pdf_url": pdf_url, "message": "Orden creada"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create lab order error: {e}")
        raise HTTPException(status_code=500, detail=f"Error al crear orden: {str(e)}")

@router.get("/clinic/lab-orders/{order_id}/pdf-url")
async def get_lab_order_pdf_url(order_id: str, ctx=Depends(require_clinic_member)):
    validate_uuid(order_id, "order_id")
    clinic_id = ctx["member"]["clinic_id"]
    try:
        order = sdb.table('lab_orders').select('id').eq('id', order_id).eq('clinic_id', clinic_id).maybe_single().execute()
        order_data = getattr(order, 'data', None) if order else None
        if not order_data:
            raise HTTPException(status_code=404, detail="Orden no encontrada")
        path = f"{clinic_id}/lab-orders/{order_id}.pdf"
        signed = supabase_admin.storage.from_('patient-files').create_signed_url(path, 3600)
        return {"url": signed.get('signedURL') or signed.get('signedUrl', '')}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get lab PDF URL error: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener URL del PDF")

async def generate_lab_order_pdf(order_id: str, clinic_id: str) -> Optional[str]:
    """Generate a lab order PDF and upload to Supabase Storage"""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import mm
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER
        import io

        order = sdb.table('lab_orders').select('*').eq('id', order_id).single().execute().data
        patient = sdb.table('patients').select('*').eq('id', order['patient_id']).single().execute().data
        doctor = sdb.table('clinic_members').select('first_name,last_name,specialty,license_number').eq('id', order['doctor_id']).single().execute().data
        clinic = sdb.table('clinics').select('name,address,city,phone,email,prescription_footer').eq('id', clinic_id).single().execute().data
        items = sdb.table('lab_order_items').select('*').eq('lab_order_id', order_id).order('sort_order').execute().data or []

        # Get preparation info for each study
        study_ids = [i['study_id'] for i in items if i.get('study_id')]
        preparations = {}
        if study_ids:
            for sid in study_ids:
                s = sdb.table('lab_studies').select('preparation').eq('id', sid).maybe_single().execute()
                if s.data and s.data.get('preparation'):
                    preparations[sid] = s.data['preparation']

        age_str = ""
        if patient.get('date_of_birth'):
            from datetime import date
            dob = date.fromisoformat(patient['date_of_birth'])
            today = date.today()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            age_str = f"{age} años"

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=20*mm, bottomMargin=25*mm, leftMargin=20*mm, rightMargin=20*mm)

        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name='ClinicName', fontSize=16, leading=20, alignment=TA_CENTER, fontName='Helvetica-Bold', textColor=colors.HexColor('#0D9488')))
        styles.add(ParagraphStyle(name='ClinicInfo', fontSize=8, leading=10, alignment=TA_CENTER, textColor=colors.grey))
        styles.add(ParagraphStyle(name='DoctorInfo', fontSize=9, leading=12, textColor=colors.HexColor('#334155')))
        styles.add(ParagraphStyle(name='SectionTitle', fontSize=11, leading=14, fontName='Helvetica-Bold', textColor=colors.HexColor('#0D9488')))
        styles.add(ParagraphStyle(name='CatTitle', fontSize=10, leading=13, fontName='Helvetica-Bold', textColor=colors.HexColor('#334155')))
        styles.add(ParagraphStyle(name='StudyName', fontSize=9, leading=12, textColor=colors.HexColor('#1E293B')))
        styles.add(ParagraphStyle(name='Prep', fontSize=8, leading=10, textColor=colors.HexColor('#64748B'), leftIndent=15))
        styles.add(ParagraphStyle(name='Footer', fontSize=8, leading=10, alignment=TA_CENTER, textColor=colors.grey))
        styles.add(ParagraphStyle(name='SignLine', fontSize=10, leading=14, alignment=TA_CENTER, fontName='Helvetica-Bold'))
        styles.add(ParagraphStyle(name='Detail', fontSize=9, leading=11, textColor=colors.HexColor('#475569')))
        styles.add(ParagraphStyle(name='Priority', fontSize=10, leading=13, fontName='Helvetica-Bold', textColor=colors.HexColor('#DC2626') if order.get('priority') == 'urgent' else colors.HexColor('#334155')))

        elements = []

        # Header
        elements.append(Paragraph(clinic.get('name', 'Clínica'), styles['ClinicName']))
        clinic_addr = ', '.join(filter(None, [clinic.get('address'), clinic.get('city')]))
        clinic_contact = ' | '.join(filter(None, [clinic.get('phone'), clinic.get('email')]))
        if clinic_addr: elements.append(Paragraph(clinic_addr, styles['ClinicInfo']))
        if clinic_contact: elements.append(Paragraph(clinic_contact, styles['ClinicInfo']))
        elements.append(Spacer(1, 4*mm))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#0D9488')))
        elements.append(Spacer(1, 4*mm))

        # Doctor
        dr_name = f"Dr. {doctor.get('first_name', '')} {doctor.get('last_name', '')}"
        dr_lines = [dr_name]
        if doctor.get('specialty'): dr_lines.append(doctor['specialty'])
        if doctor.get('license_number'): dr_lines.append(f"No. Colegiado: {doctor['license_number']}")
        elements.append(Paragraph('<br/>'.join(dr_lines), styles['DoctorInfo']))
        elements.append(Spacer(1, 4*mm))

        # Title and Priority
        elements.append(Paragraph("ORDEN DE LABORATORIO", styles['SectionTitle']))
        priority_label = "URGENTE" if order.get('priority') == 'urgent' else "Rutina"
        elements.append(Paragraph(f"Prioridad: {priority_label}", styles['Priority']))
        elements.append(Spacer(1, 3*mm))

        # Patient info
        patient_name = f"{patient.get('first_name', '')} {patient.get('last_name', '')}"
        elements.append(Paragraph(f"<b>Paciente:</b> {patient_name}  |  <b>Edad:</b> {age_str}  |  <b>DPI:</b> {patient.get('national_id', '—')}", styles['Detail']))

        # Date
        ordered = order.get('ordered_at', order.get('created_at', ''))
        date_str = ""
        if ordered:
            from datetime import datetime as dt
            try:
                d = dt.fromisoformat(ordered.replace('Z', '+00:00'))
                date_str = d.strftime('%d/%m/%Y')
            except:
                date_str = ordered[:10]
        elements.append(Paragraph(f"<b>Fecha:</b> {date_str}", styles['Detail']))

        if order.get('presumptive_diagnosis'):
            elements.append(Paragraph(f"<b>Diagnóstico presuntivo:</b> {order['presumptive_diagnosis']}", styles['Detail']))
        elements.append(Spacer(1, 4*mm))
        elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#CBD5E1')))
        elements.append(Spacer(1, 4*mm))

        # Studies grouped by category
        elements.append(Paragraph("Estudios solicitados:", styles['SectionTitle']))
        elements.append(Spacer(1, 2*mm))

        grouped = {}
        for item in items:
            cat = item.get('category', 'Otros')
            if cat not in grouped: grouped[cat] = []
            grouped[cat].append(item)

        all_preps = []
        idx = 1
        for cat, cat_items in grouped.items():
            elements.append(Paragraph(cat, styles['CatTitle']))
            for item in cat_items:
                elements.append(Paragraph(f"{idx}. {item['study_name']}", styles['StudyName']))
                prep = preparations.get(item.get('study_id'))
                if prep:
                    all_preps.append(f"{item['study_name']}: {prep}")
                idx += 1
            elements.append(Spacer(1, 2*mm))

        # Special instructions
        if order.get('special_instructions'):
            elements.append(Spacer(1, 3*mm))
            elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#CBD5E1')))
            elements.append(Spacer(1, 3*mm))
            elements.append(Paragraph("<b>Indicaciones especiales:</b>", styles['Detail']))
            elements.append(Paragraph(order['special_instructions'], styles['Detail']))

        # Consolidated preparations
        if all_preps:
            elements.append(Spacer(1, 3*mm))
            elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#CBD5E1')))
            elements.append(Spacer(1, 3*mm))
            elements.append(Paragraph("<b>Instrucciones de preparación:</b>", styles['Detail']))
            for p in all_preps:
                elements.append(Paragraph(f"• {p}", styles['Prep']))

        # Signature
        elements.append(Spacer(1, 20*mm))
        elements.append(HRFlowable(width="40%", thickness=0.5, color=colors.black, hAlign='CENTER'))
        elements.append(Spacer(1, 2*mm))
        elements.append(Paragraph(dr_name, styles['SignLine']))
        if doctor.get('license_number'):
            elements.append(Paragraph(f"Colegiado No. {doctor['license_number']}", styles['Footer']))

        doc.build(elements)
        pdf_bytes = buffer.getvalue()
        buffer.close()

        path = f"{clinic_id}/lab-orders/{order_id}.pdf"
        supabase_admin.storage.from_('patient-files').upload(path, pdf_bytes, {"content-type": "application/pdf", "upsert": "true"})
        signed = supabase_admin.storage.from_('patient-files').create_signed_url(path, 3600)
        pdf_url = signed.get('signedURL') or signed.get('signedUrl', '')
        sdb.table('lab_orders').update({"pdf_url": pdf_url, "updated_at": now_iso()}).eq('id', order_id).execute()
        return pdf_url
    except Exception as e:
        logger.error(f"Generate lab order PDF error: {e}")
        return None

