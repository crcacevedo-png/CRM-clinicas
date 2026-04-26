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

# ============== PRESCRIPTION ROUTES ==============

class PrescriptionItemInput(BaseModel):
    medication_name: str
    presentation: Optional[str] = None
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    route: Optional[str] = None
    duration: Optional[str] = None
    instructions: Optional[str] = None
    sort_order: int = 0

class PrescriptionCreate(BaseModel):
    patient_id: str
    medical_record_id: Optional[str] = None
    diagnosis: Optional[str] = None
    general_instructions: Optional[str] = None
    items: List[PrescriptionItemInput] = []
    status: str = "draft"

@router.get("/clinic/medications/search")
async def search_medications(q: str = "", ctx=Depends(require_clinic_member)):
    """Search medications by generic or brand name"""
    clinic_id = ctx["member"]["clinic_id"]
    try:
        if not q or len(q) < 2:
            result = sdb.table('medications').select('id,generic_name,brand_name,presentations,category').or_(f'clinic_id.is.null,clinic_id.eq.{clinic_id}').eq('is_active', True).order('generic_name').limit(20).execute()
        else:
            result = sdb.table('medications').select('id,generic_name,brand_name,presentations,category').or_(f'clinic_id.is.null,clinic_id.eq.{clinic_id}').eq('is_active', True).or_(f'generic_name.ilike.%{q}%,brand_name.ilike.%{q}%').order('generic_name').limit(20).execute()
        return result.data or []
    except Exception as e:
        logger.error(f"Search medications error: {e}")
        raise HTTPException(status_code=500, detail="Error al buscar medicamentos")

@router.post("/clinic/medications")
async def create_clinic_medication(data: MedicationCreate, ctx=Depends(require_clinic_member)):
    """Create a new medication for this clinic"""
    clinic_id = ctx["member"]["clinic_id"]
    try:
        doc = {
            "id": str(uuid.uuid4()),
            "clinic_id": clinic_id,
            "generic_name": data.generic_name,
            "brand_name": data.brand_name,
            "presentations": parse_presentations(data.presentations),
            "category": data.category,
            "is_active": True,
            "created_at": now_iso(),
        }
        sdb.table('medications').insert(doc).execute()
        return {"id": doc["id"], "message": "Medicamento creado"}
    except Exception as e:
        logger.error(f"Create medication error: {e}")
        raise HTTPException(status_code=500, detail="Error al crear medicamento")

@router.get("/clinic/prescriptions")
async def list_prescriptions(
    patient_id: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1, limit: int = 20,
    ctx=Depends(require_clinic_member)
):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        query = sdb.table('prescriptions').select('*', count='exact').eq('clinic_id', clinic_id)
        if patient_id:
            query = query.eq('patient_id', patient_id)
        if status:
            query = query.eq('status', status)
        offset = (page - 1) * limit
        result = query.order('created_at', desc=True).range(offset, offset + limit - 1).execute()
        prescriptions = result.data or []

        for p in prescriptions:
            pat = sdb.table('patients').select('first_name,last_name').eq('id', p['patient_id']).maybe_single().execute()
            p['patient_name'] = f"{pat.data['first_name']} {pat.data['last_name']}" if pat.data else ""
            doc = sdb.table('clinic_members').select('first_name,last_name').eq('id', p['doctor_id']).maybe_single().execute()
            p['doctor_name'] = f"{doc.data['first_name']} {doc.data['last_name']}" if doc.data else ""
            items = sdb.table('prescription_items').select('id').eq('prescription_id', p['id']).execute()
            p['item_count'] = len(items.data or [])

        return {"prescriptions": prescriptions, "total": result.count or 0, "page": page, "pages": ((result.count or 0) + limit - 1) // limit}
    except Exception as e:
        logger.error(f"List prescriptions error: {e}")
        raise HTTPException(status_code=500, detail="Error al listar recetas")

@router.get("/clinic/prescriptions/{presc_id}")
async def get_prescription(presc_id: str, ctx=Depends(require_clinic_member)):
    validate_uuid(presc_id, "presc_id")
    clinic_id = ctx["member"]["clinic_id"]
    try:
        result = sdb.table('prescriptions').select('*').eq('id', presc_id).eq('clinic_id', clinic_id).maybe_single().execute()
        data = getattr(result, 'data', None) if result else None
        if not data:
            raise HTTPException(status_code=404, detail="Receta no encontrada")
        presc = data
        pat = sdb.table('patients').select('*').eq('id', presc['patient_id']).maybe_single().execute()
        pat_data = getattr(pat, 'data', None) if pat else None
        presc['patient'] = pat_data or {}
        if presc['patient']:
            presc['patient'].pop('search_vector', None)
        doc = sdb.table('clinic_members').select('first_name,last_name,specialty,license_number').eq('id', presc['doctor_id']).maybe_single().execute()
        doc_data = getattr(doc, 'data', None) if doc else None
        presc['doctor'] = doc_data or {}
        items = sdb.table('prescription_items').select('*').eq('prescription_id', presc_id).order('sort_order').execute()
        presc['items'] = items.data or []
        return presc
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get prescription error: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener receta")

@router.post("/clinic/prescriptions")
async def create_prescription(data: PrescriptionCreate, ctx=Depends(require_clinic_member)):
    require_clinical_role(ctx)
    clinic_id = ctx["member"]["clinic_id"]
    member = ctx["member"]
    try:
        now = now_iso()
        presc_id = str(uuid.uuid4())
        doc = {
            "id": presc_id, "clinic_id": clinic_id,
            "patient_id": data.patient_id, "doctor_id": member["id"],
            "medical_record_id": data.medical_record_id,
            "diagnosis": data.diagnosis,
            "general_instructions": data.general_instructions,
            "status": data.status or "draft",
            "created_at": now, "updated_at": now,
        }
        if data.status == "issued":
            doc["issued_at"] = now
        sdb.table('prescriptions').insert(doc).execute()

        for i, item in enumerate(data.items):
            sdb.table('prescription_items').insert({
                "id": str(uuid.uuid4()),
                "prescription_id": presc_id,
                "medication_name": item.medication_name,
                "presentation": item.presentation,
                "dosage": item.dosage,
                "frequency": item.frequency,
                "route": item.route,
                "duration": item.duration,
                "instructions": item.instructions,
                "sort_order": i,
            }).execute()

        # Generate PDF if issued
        pdf_url = None
        if data.status == "issued":
            pdf_url = await generate_prescription_pdf(presc_id, clinic_id)

        return {"id": presc_id, "pdf_url": pdf_url, "message": "Receta creada"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create prescription error: {e}")
        raise HTTPException(status_code=500, detail=f"Error al crear receta: {str(e)}")

@router.put("/clinic/prescriptions/{presc_id}")
async def update_prescription(presc_id: str, data: PrescriptionCreate, ctx=Depends(require_clinic_member)):
    require_clinical_role(ctx)
    clinic_id = ctx["member"]["clinic_id"]
    try:
        existing = sdb.table('prescriptions').select('id,status').eq('id', presc_id).eq('clinic_id', clinic_id).maybe_single().execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Receta no encontrada")
        if existing.data['status'] == 'issued':
            raise HTTPException(status_code=400, detail="No se puede editar una receta emitida")

        now = now_iso()
        update_data = {
            "diagnosis": data.diagnosis,
            "general_instructions": data.general_instructions,
            "status": data.status or "draft",
            "updated_at": now,
        }
        if data.status == "issued":
            update_data["issued_at"] = now

        sdb.table('prescriptions').update(update_data).eq('id', presc_id).execute()

        # Replace items
        sdb.table('prescription_items').delete().eq('prescription_id', presc_id).execute()
        for i, item in enumerate(data.items):
            sdb.table('prescription_items').insert({
                "id": str(uuid.uuid4()),
                "prescription_id": presc_id,
                "medication_name": item.medication_name,
                "presentation": item.presentation,
                "dosage": item.dosage,
                "frequency": item.frequency,
                "route": item.route,
                "duration": item.duration,
                "instructions": item.instructions,
                "sort_order": i,
            }).execute()

        pdf_url = None
        if data.status == "issued":
            pdf_url = await generate_prescription_pdf(presc_id, clinic_id)

        return {"id": presc_id, "pdf_url": pdf_url, "message": "Receta actualizada"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update prescription error: {e}")
        raise HTTPException(status_code=500, detail="Error al actualizar receta")

@router.put("/clinic/prescriptions/{presc_id}/send")
async def mark_prescription_sent(presc_id: str, ctx=Depends(require_clinic_member)):
    """Mark prescription as sent via WhatsApp (placeholder for n8n integration)"""
    clinic_id = ctx["member"]["clinic_id"]
    try:
        existing = sdb.table('prescriptions').select('id,status').eq('id', presc_id).eq('clinic_id', clinic_id).maybe_single().execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Receta no encontrada")
        sdb.table('prescriptions').update({
            "sent_via": "whatsapp", "sent_at": now_iso(), "updated_at": now_iso(),
        }).eq('id', presc_id).execute()
        return {"message": "Receta marcada como enviada"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Send prescription error: {e}")
        raise HTTPException(status_code=500, detail="Error")

async def generate_prescription_pdf(presc_id: str, clinic_id: str) -> Optional[str]:
    """Generate a prescription PDF and upload to Supabase Storage"""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import inch, mm
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table as RLTable, TableStyle, HRFlowable
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
        import io

        # Fetch all data
        presc = sdb.table('prescriptions').select('*').eq('id', presc_id).single().execute().data
        patient = sdb.table('patients').select('*').eq('id', presc['patient_id']).single().execute().data
        doctor = sdb.table('clinic_members').select('first_name,last_name,specialty,license_number').eq('id', presc['doctor_id']).single().execute().data
        clinic = sdb.table('clinics').select('name,address,city,phone,email,prescription_footer').eq('id', clinic_id).single().execute().data
        items = sdb.table('prescription_items').select('*').eq('prescription_id', presc_id).order('sort_order').execute().data or []

        # Calculate age
        age_str = ""
        if patient.get('date_of_birth'):
            from datetime import date
            dob = date.fromisoformat(patient['date_of_birth'])
            today = date.today()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            age_str = f"{age} años"

        # Build PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter,
                                topMargin=20*mm, bottomMargin=25*mm,
                                leftMargin=20*mm, rightMargin=20*mm)

        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name='ClinicName', fontSize=16, leading=20, alignment=TA_CENTER, fontName='Helvetica-Bold', textColor=colors.HexColor('#0D9488')))
        styles.add(ParagraphStyle(name='ClinicInfo', fontSize=8, leading=10, alignment=TA_CENTER, textColor=colors.grey))
        styles.add(ParagraphStyle(name='DoctorInfo', fontSize=9, leading=12, alignment=TA_LEFT, textColor=colors.HexColor('#334155')))
        styles.add(ParagraphStyle(name='PatientLabel', fontSize=8, leading=10, textColor=colors.grey))
        styles.add(ParagraphStyle(name='PatientValue', fontSize=10, leading=13, fontName='Helvetica-Bold'))
        styles.add(ParagraphStyle(name='RxSymbol', fontSize=28, leading=32, fontName='Helvetica-Bold', textColor=colors.HexColor('#0D9488')))
        styles.add(ParagraphStyle(name='MedName', fontSize=10, leading=13, fontName='Helvetica-Bold', textColor=colors.HexColor('#1E293B')))
        styles.add(ParagraphStyle(name='MedDetail', fontSize=9, leading=11, textColor=colors.HexColor('#475569')))
        styles.add(ParagraphStyle(name='Footer', fontSize=8, leading=10, alignment=TA_CENTER, textColor=colors.grey))
        styles.add(ParagraphStyle(name='SignLine', fontSize=10, leading=14, alignment=TA_CENTER, fontName='Helvetica-Bold'))

        elements = []

        # --- HEADER ---
        elements.append(Paragraph(clinic.get('name', 'Clínica'), styles['ClinicName']))
        clinic_addr = ', '.join(filter(None, [clinic.get('address'), clinic.get('city')]))
        clinic_contact = ' | '.join(filter(None, [clinic.get('phone'), clinic.get('email')]))
        if clinic_addr:
            elements.append(Paragraph(clinic_addr, styles['ClinicInfo']))
        if clinic_contact:
            elements.append(Paragraph(clinic_contact, styles['ClinicInfo']))
        elements.append(Spacer(1, 4*mm))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#0D9488')))
        elements.append(Spacer(1, 4*mm))

        # --- DOCTOR INFO ---
        dr_name = f"Dr. {doctor.get('first_name', '')} {doctor.get('last_name', '')}"
        dr_lines = [dr_name]
        if doctor.get('specialty'):
            dr_lines.append(doctor['specialty'])
        if doctor.get('license_number'):
            dr_lines.append(f"No. Colegiado: {doctor['license_number']}")
        elements.append(Paragraph('<br/>'.join(dr_lines), styles['DoctorInfo']))
        elements.append(Spacer(1, 4*mm))

        # --- PATIENT & DATE ---
        issued = presc.get('issued_at') or presc.get('created_at', '')
        date_str = ""
        if issued:
            from datetime import datetime as dt
            try:
                d = dt.fromisoformat(issued.replace('Z', '+00:00'))
                date_str = d.strftime('%d/%m/%Y')
            except:
                date_str = issued[:10]

        patient_name = f"{patient.get('first_name', '')} {patient.get('last_name', '')}"
        patient_data = [
            ['Paciente:', patient_name, 'Fecha:', date_str],
            ['Edad:', age_str, 'DPI:', patient.get('national_id', '—')],
        ]
        pt = RLTable(patient_data, colWidths=[55, 200, 45, 150])
        pt.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica'),
            ('FONTNAME', (2, 0), (2, -1), 'Helvetica'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica-Bold'),
            ('FONTNAME', (3, 0), (3, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.grey),
            ('TEXTCOLOR', (2, 0), (2, -1), colors.grey),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        elements.append(pt)
        elements.append(Spacer(1, 3*mm))

        # --- DIAGNOSIS ---
        if presc.get('diagnosis'):
            elements.append(Paragraph(f"<b>Diagnóstico:</b> {presc['diagnosis']}", styles['MedDetail']))
            elements.append(Spacer(1, 3*mm))

        elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#CBD5E1')))
        elements.append(Spacer(1, 4*mm))

        # --- Rx SYMBOL ---
        elements.append(Paragraph("Rx", styles['RxSymbol']))
        elements.append(Spacer(1, 3*mm))

        # --- MEDICATIONS ---
        for idx, item in enumerate(items, 1):
            med_line = f"{idx}. {item['medication_name']}"
            if item.get('presentation'):
                med_line += f" — {item['presentation']}"
            elements.append(Paragraph(med_line, styles['MedName']))

            details = []
            if item.get('dosage'):
                details.append(f"Dosis: {item['dosage']}")
            if item.get('frequency'):
                details.append(f"Frecuencia: {item['frequency']}")
            if item.get('route'):
                route_labels = {'oral':'Oral','intramuscular':'Intramuscular','intravenosa':'Intravenosa','topica':'Tópica','inhalada':'Inhalada','sublingual':'Sublingual','rectal':'Rectal','oftalmica':'Oftálmica'}
                details.append(f"Vía: {route_labels.get(item['route'], item['route'])}")
            if item.get('duration'):
                details.append(f"Duración: {item['duration']}")
            if details:
                elements.append(Paragraph(' | '.join(details), styles['MedDetail']))
            if item.get('instructions'):
                elements.append(Paragraph(f"<i>{item['instructions']}</i>", styles['MedDetail']))
            elements.append(Spacer(1, 3*mm))

        # --- GENERAL INSTRUCTIONS ---
        if presc.get('general_instructions'):
            elements.append(Spacer(1, 3*mm))
            elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#CBD5E1')))
            elements.append(Spacer(1, 3*mm))
            elements.append(Paragraph("<b>Indicaciones generales:</b>", styles['MedDetail']))
            elements.append(Paragraph(presc['general_instructions'], styles['MedDetail']))

        # --- SIGNATURE ---
        elements.append(Spacer(1, 20*mm))
        elements.append(HRFlowable(width="40%", thickness=0.5, color=colors.black, hAlign='CENTER'))
        elements.append(Spacer(1, 2*mm))
        elements.append(Paragraph(dr_name, styles['SignLine']))
        if doctor.get('license_number'):
            elements.append(Paragraph(f"Colegiado No. {doctor['license_number']}", styles['Footer']))

        # --- FOOTER ---
        footer_text = clinic.get('prescription_footer')
        if footer_text:
            elements.append(Spacer(1, 10*mm))
            elements.append(Paragraph(footer_text, styles['Footer']))

        doc.build(elements)
        pdf_bytes = buffer.getvalue()
        buffer.close()

        # Upload to Supabase Storage
        path = f"{clinic_id}/prescriptions/{presc_id}.pdf"
        supabase_admin.storage.from_('patient-files').upload(path, pdf_bytes, {"content-type": "application/pdf", "upsert": "true"})

        # Get signed URL
        signed = supabase_admin.storage.from_('patient-files').create_signed_url(path, 86400)
        pdf_url = signed.get('signedURL') or signed.get('signedUrl', '')

        # Save URL in prescription
        sdb.table('prescriptions').update({"pdf_url": pdf_url, "updated_at": now_iso()}).eq('id', presc_id).execute()

        return pdf_url
    except Exception as e:
        logger.error(f"Generate PDF error: {e}")
        return None

@router.get("/clinic/prescriptions/{presc_id}/pdf-url")
async def get_prescription_pdf_url(presc_id: str, ctx=Depends(require_clinic_member)):
    """Get a fresh signed URL for the prescription PDF"""
    validate_uuid(presc_id, "presc_id")
    clinic_id = ctx["member"]["clinic_id"]
    try:
        presc = sdb.table('prescriptions').select('id').eq('id', presc_id).eq('clinic_id', clinic_id).maybe_single().execute()
        presc_data = getattr(presc, 'data', None) if presc else None
        if not presc_data:
            raise HTTPException(status_code=404, detail="Receta no encontrada")
        path = f"{clinic_id}/prescriptions/{presc_id}.pdf"
        signed = supabase_admin.storage.from_('patient-files').create_signed_url(path, 3600)
        return {"url": signed.get('signedURL') or signed.get('signedUrl', '')}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get PDF URL error: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener URL del PDF")

