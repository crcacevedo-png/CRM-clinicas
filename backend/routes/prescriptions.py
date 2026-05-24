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
    get_plan_limits, parse_presentations, fetch_clinic_logo_image,
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

        if prescriptions:
            patient_ids = list({p['patient_id'] for p in prescriptions if p.get('patient_id')})
            doctor_ids = list({p['doctor_id'] for p in prescriptions if p.get('doctor_id')})
            presc_ids = [p['id'] for p in prescriptions]

            # Batch fetch patients, doctors, items
            patients_map = {}
            if patient_ids:
                pats = sdb.table('patients').select('id,first_name,last_name').in_('id', patient_ids).execute()
                patients_map = {x['id']: f"{x['first_name']} {x['last_name']}" for x in (pats.data or [])}
            doctors_map = {}
            if doctor_ids:
                docs = sdb.table('clinic_members').select('id,first_name,last_name').in_('id', doctor_ids).execute()
                doctors_map = {x['id']: f"{x['first_name']} {x['last_name']}" for x in (docs.data or [])}
            items_count = {}
            if presc_ids:
                items = sdb.table('prescription_items').select('prescription_id').in_('prescription_id', presc_ids).execute()
                for it in (items.data or []):
                    items_count[it['prescription_id']] = items_count.get(it['prescription_id'], 0) + 1

            for p in prescriptions:
                p['patient_name'] = patients_map.get(p.get('patient_id'), '')
                p['doctor_name'] = doctors_map.get(p.get('doctor_id'), '')
                p['item_count'] = items_count.get(p['id'], 0)

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
        from reportlab.lib.pagesizes import A5, landscape
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
        clinic = sdb.table('clinics').select('name,address,city,phone,email,prescription_footer,logo_url').eq('id', clinic_id).single().execute().data
        items = sdb.table('prescription_items').select('*').eq('prescription_id', presc_id).order('sort_order').execute().data or []

        # Build PDF — A5 landscape (210x148mm) for compact, professional prescription
        buffer = io.BytesIO()
        # Page dimensions for landscape A5
        page_w, page_h = landscape(A5)  # ~595.28 x 419.53 pts
        # Leave bottom space (~28mm) for the signature block, drawn via canvas callback
        SIG_BAND_HEIGHT = 28 * mm
        doc = SimpleDocTemplate(
            buffer, pagesize=landscape(A5),
            topMargin=8*mm,
            bottomMargin=SIG_BAND_HEIGHT + 4*mm,
            leftMargin=12*mm, rightMargin=12*mm,
        )

        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name='ClinicName', fontSize=14, leading=16, alignment=TA_LEFT, fontName='Helvetica-Bold', textColor=colors.HexColor('#0D9488')))
        styles.add(ParagraphStyle(name='ClinicInfo', fontSize=7.5, leading=9, alignment=TA_LEFT, textColor=colors.grey))
        styles.add(ParagraphStyle(name='DoctorInfo', fontSize=8.5, leading=11, alignment=TA_LEFT, textColor=colors.HexColor('#334155')))
        styles.add(ParagraphStyle(name='PatientLabel', fontSize=8, leading=10, textColor=colors.grey))
        styles.add(ParagraphStyle(name='PatientValue', fontSize=10, leading=13, fontName='Helvetica-Bold'))
        styles.add(ParagraphStyle(name='RxSymbol', fontSize=22, leading=24, fontName='Helvetica-Bold', textColor=colors.HexColor('#0D9488')))
        styles.add(ParagraphStyle(name='MedName', fontSize=9.5, leading=12, fontName='Helvetica-Bold', textColor=colors.HexColor('#1E293B')))
        styles.add(ParagraphStyle(name='MedDetail', fontSize=8.5, leading=10.5, textColor=colors.HexColor('#475569')))
        styles.add(ParagraphStyle(name='Footer', fontSize=7.5, leading=9, alignment=TA_CENTER, textColor=colors.grey))
        styles.add(ParagraphStyle(name='SignLine', fontSize=9, leading=12, alignment=TA_CENTER, fontName='Helvetica-Bold'))

        elements = []

        # --- HEADER: clinic name+contact on the LEFT, logo on the RIGHT ---
        clinic_addr = ', '.join(filter(None, [clinic.get('address'), clinic.get('city')]))
        clinic_contact = ' | '.join(filter(None, [clinic.get('phone'), clinic.get('email')]))
        left_lines = [Paragraph(clinic.get('name', 'Clínica'), styles['ClinicName'])]
        if clinic_addr:
            left_lines.append(Paragraph(clinic_addr, styles['ClinicInfo']))
        if clinic_contact:
            left_lines.append(Paragraph(clinic_contact, styles['ClinicInfo']))

        logo_flow = fetch_clinic_logo_image(clinic.get('logo_url'), max_h_mm=15)
        right_cell = logo_flow if logo_flow is not None else ""
        if logo_flow is not None:
            logo_flow.hAlign = 'RIGHT'

        # Table widths: ~186mm available content width on A5 landscape with 12mm margins
        header_tbl = RLTable([[left_lines, right_cell]], colWidths=[130*mm, 56*mm])
        header_tbl.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        elements.append(header_tbl)
        elements.append(Spacer(1, 2*mm))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#0D9488')))
        elements.append(Spacer(1, 2*mm))

        # --- DOCTOR + PATIENT + DATE in a single compact row ---
        dr_name = f"Dr. {doctor.get('first_name', '')} {doctor.get('last_name', '')}".strip()
        dr_sub_parts = []
        if doctor.get('specialty'):
            dr_sub_parts.append(doctor['specialty'])
        if doctor.get('license_number'):
            dr_sub_parts.append(f"Col. {doctor['license_number']}")
        dr_sub = ' · '.join(dr_sub_parts)
        doctor_block = f"<b>{dr_name}</b>" + (f"<br/><font color='#64748B' size='7.5'>{dr_sub}</font>" if dr_sub else "")

        # Date
        issued = presc.get('issued_at') or presc.get('created_at', '')
        date_str = ""
        if issued:
            from datetime import datetime as dt
            try:
                d = dt.fromisoformat(issued.replace('Z', '+00:00'))
                date_str = d.strftime('%d/%m/%Y')
            except Exception:
                date_str = issued[:10]

        patient_name = f"{patient.get('first_name', '')} {patient.get('last_name', '')}".strip()

        # Calculate age
        age_str = ""
        if patient.get('date_of_birth'):
            from datetime import date
            try:
                dob = date.fromisoformat(patient['date_of_birth'])
                today = date.today()
                age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
                age_str = f"{age} años"
            except Exception:
                age_str = ""

        patient_block_lines = ["<font color='#64748B' size='7.5'>Paciente</font>", f"<b>{patient_name}</b>"]
        if age_str:
            patient_block_lines.append(f"<font color='#64748B' size='7.5'>{age_str}</font>")
        patient_block = '<br/>'.join(patient_block_lines)

        date_block = f"<font color='#64748B' size='7.5'>Fecha</font><br/><b>{date_str}</b>"

        info_tbl = RLTable(
            [[Paragraph(doctor_block, styles['DoctorInfo']),
              Paragraph(patient_block, styles['DoctorInfo']),
              Paragraph(date_block, styles['DoctorInfo'])]],
            colWidths=[78*mm, 78*mm, 30*mm]
        )
        info_tbl.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ]))
        elements.append(info_tbl)
        elements.append(Spacer(1, 2*mm))

        # --- DIAGNOSIS (inline, compact) ---
        if presc.get('diagnosis'):
            elements.append(Paragraph(f"<b>Diagnóstico:</b> {presc['diagnosis']}", styles['MedDetail']))
            elements.append(Spacer(1, 1.5*mm))

        elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#CBD5E1')))
        elements.append(Spacer(1, 2*mm))

        # --- Rx SYMBOL ---
        elements.append(Paragraph("Rx", styles['RxSymbol']))
        elements.append(Spacer(1, 1.5*mm))

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
            elements.append(Spacer(1, 1.5*mm))

        # --- GENERAL INSTRUCTIONS ---
        if presc.get('general_instructions'):
            elements.append(Spacer(1, 1.5*mm))
            elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#CBD5E1')))
            elements.append(Spacer(1, 1.5*mm))
            elements.append(Paragraph("<b>Indicaciones generales:</b>", styles['MedDetail']))
            elements.append(Paragraph(presc['general_instructions'], styles['MedDetail']))

        # --- SIGNATURE & FOOTER drawn at fixed bottom of page (always anchored, regardless of content length) ---
        footer_text = clinic.get('prescription_footer') or ""
        license_no = doctor.get('license_number') or ""

        def _draw_signature(canvas, _doc):
            from reportlab.lib import colors as _c
            canvas.saveState()
            # Signature line: centered, ~35% width, at y ≈ 22mm from bottom
            line_width = page_w * 0.35
            line_x = (page_w - line_width) / 2
            line_y = 22 * mm
            canvas.setStrokeColorRGB(0, 0, 0)
            canvas.setLineWidth(0.5)
            canvas.line(line_x, line_y, line_x + line_width, line_y)
            # Doctor name (bold, centered) just below the line
            canvas.setFont('Helvetica-Bold', 9)
            canvas.setFillColor(_c.black)
            canvas.drawCentredString(page_w / 2, line_y - 5 * mm, dr_name)
            # Colegiado number (smaller, grey)
            if license_no:
                canvas.setFont('Helvetica', 7.5)
                canvas.setFillColor(_c.grey)
                canvas.drawCentredString(page_w / 2, line_y - 9 * mm, f"Colegiado No. {license_no}")
            # Clinic footer at very bottom (centered, grey)
            if footer_text:
                canvas.setFont('Helvetica', 7.5)
                canvas.setFillColor(_c.grey)
                canvas.drawCentredString(page_w / 2, 6 * mm, footer_text[:200])
            canvas.restoreState()

        doc.build(elements, onFirstPage=_draw_signature, onLaterPages=_draw_signature)
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

        # Auto-send PDF to patient by email (best-effort, never blocks the response)
        try:
            patient_email = (patient.get('email') or '').strip()
            if patient_email and '@' in patient_email:
                from services.email_service import send_email
                from services.email_templates import prescription_issued
                # Compute display date in clinic locale (simple ISO -> dd/mm/yyyy)
                _issued = presc.get('issued_at') or presc.get('created_at', '')
                _date_display = _issued[:10]
                try:
                    from datetime import datetime as _dt
                    _date_display = _dt.fromisoformat(_issued.replace('Z', '+00:00')).strftime('%d/%m/%Y')
                except Exception:
                    pass
                tmpl = prescription_issued(
                    patient_name=f"{patient.get('first_name','')} {patient.get('last_name','')}".strip() or "Paciente",
                    clinic_name=clinic.get('name') or "Cortexia Medical",
                    doctor_name=f"Dr. {doctor.get('first_name','')} {doctor.get('last_name','')}".strip(),
                    date_str=_date_display,
                    diagnosis=presc.get('diagnosis'),
                    item_count=len(items),
                )
                send_result = await send_email(
                    to=patient_email,
                    subject=tmpl['subject'],
                    html=tmpl['html'],
                    text=tmpl['text'],
                    attachments=[{"filename": f"receta-{presc_id[:8]}.pdf", "content": pdf_bytes}],
                )
                if send_result.get('ok'):
                    sdb.table('prescriptions').update({
                        "sent_via": "email",
                        "sent_at": now_iso(),
                        "updated_at": now_iso(),
                    }).eq('id', presc_id).execute()
                    logger.info(f"Prescription {presc_id} emailed to {patient_email} (msg_id={send_result.get('id')})")
                else:
                    logger.warning(f"Prescription {presc_id} email failed: {send_result.get('error')}")
        except Exception as mail_err:
            logger.warning(f"Prescription email side-effect failed: {mail_err}")

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

