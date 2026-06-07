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
    CLINICAL_ROLES, require_clinical_role,
    validate_uuid,
)

# ============== MEDICAL RECORDS ROUTES ==============

class MedicalRecordCreate(BaseModel):
    patient_id: str
    appointment_id: Optional[str] = None
    chief_complaint: Optional[str] = None
    present_illness: Optional[str] = None
    review_of_systems: Optional[dict] = None
    blood_pressure_systolic: Optional[int] = None
    blood_pressure_diastolic: Optional[int] = None
    heart_rate: Optional[int] = None
    respiratory_rate: Optional[int] = None
    temperature: Optional[float] = None
    oxygen_saturation: Optional[float] = None
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    bmi: Optional[float] = None
    physical_exam: Optional[dict] = None
    diagnoses: Optional[list] = None
    treatment_plan: Optional[str] = None
    procedures: Optional[str] = None
    notes: Optional[str] = None
    private_notes: Optional[str] = None
    status: Optional[str] = "draft"

class AddendumCreate(BaseModel):
    text: str

@router.get("/clinic/icd10/search")
async def search_icd10(q: str = "", limit: int = 20, ctx=Depends(require_clinic_member)):
    """Search ICD-10 codes by code or description, accessible by all clinic members"""
    try:
        if not q or len(q) < 2:
            result = sdb.table('icd10_codes').select('id,code,description_es,category,is_common').eq('is_common', True).order('code').limit(limit).execute()
        else:
            from services.input_sanitizer import sanitize_postgrest_search
            qs = sanitize_postgrest_search(q)
            result = sdb.table('icd10_codes').select('id,code,description_es,category,is_common').or_(f'code.ilike.%{qs}%,description_es.ilike.%{qs}%').order('code').limit(limit).execute()
        return result.data or []
    except Exception as e:
        logger.error(f"Search ICD10 error: {e}")
        raise HTTPException(status_code=500, detail="Error al buscar códigos CIE-10")

@router.post("/clinic/medical-records")
async def create_medical_record(data: MedicalRecordCreate, ctx=Depends(require_clinic_member)):
    """Create a new medical record - only doctors/clinic_admin"""
    require_clinical_role(ctx)
    clinic_id = ctx["member"]["clinic_id"]
    member = ctx["member"]
    try:
        patient = sdb.table('patients').select('id').eq('id', data.patient_id).eq('clinic_id', clinic_id).maybe_single().execute()
        if not patient.data:
            raise HTTPException(status_code=404, detail="Paciente no encontrado")

        now = now_iso()
        record_id = str(uuid.uuid4())
        doc = {
            "id": record_id,
            "clinic_id": clinic_id,
            "patient_id": data.patient_id,
            "doctor_id": member["id"],
            "appointment_id": data.appointment_id,
            "status": data.status or "draft",
            "chief_complaint": data.chief_complaint,
            "present_illness": data.present_illness,
            "review_of_systems": data.review_of_systems or {},
            "blood_pressure_systolic": data.blood_pressure_systolic,
            "blood_pressure_diastolic": data.blood_pressure_diastolic,
            "heart_rate": data.heart_rate,
            "respiratory_rate": data.respiratory_rate,
            "temperature": data.temperature,
            "oxygen_saturation": int(data.oxygen_saturation) if data.oxygen_saturation is not None else None,
            "weight_kg": data.weight_kg,
            "height_cm": data.height_cm,
            "bmi": data.bmi,
            "physical_exam": data.physical_exam or {},
            "diagnoses": data.diagnoses or [],
            "treatment_plan": data.treatment_plan,
            "procedures": data.procedures,
            "notes": data.notes,
            "private_notes": data.private_notes,
            "addenda": [],
            "created_at": now,
            "updated_at": now,
        }
        if data.status == "finalized":
            doc["finalized_at"] = now

        sdb.table('medical_records').insert(doc).execute()
        return {"id": record_id, "message": "Registro médico creado"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create medical record error: {e}")
        raise HTTPException(status_code=500, detail=f"Error al crear registro médico: {str(e)}")

@router.get("/clinic/patients/{patient_id}/medical-records")
async def list_patient_medical_records(
    patient_id: str,
    doctor_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    ctx=Depends(require_clinic_member)
):
    """List medical records for a patient with role-based filtering"""
    clinic_id = ctx["member"]["clinic_id"]
    role = ctx["member"].get("role", "")

    if role in ("receptionist",):
        raise HTTPException(status_code=403, detail="No tiene acceso a historias clínicas")

    try:
        query = sdb.table('medical_records').select('*').eq('patient_id', patient_id).eq('clinic_id', clinic_id).order('created_at', desc=True)

        if doctor_id:
            query = query.eq('doctor_id', doctor_id)
        if date_from:
            query = query.gte('created_at', date_from)
        if date_to:
            query = query.lte('created_at', date_to + "T23:59:59Z")

        result = query.execute()
        records = result.data or []

        # Enrich with doctor names (batch fetch to avoid N+1)
        if records:
            doctor_ids = list({r.get('doctor_id') for r in records if r.get('doctor_id')})
            doctors_map = {}
            if doctor_ids:
                docs = sdb.table('clinic_members').select('id,first_name,last_name').in_('id', doctor_ids).execute()
                doctors_map = {x['id']: f"{x['first_name']} {x['last_name']}" for x in (docs.data or [])}
            for r in records:
                r['doctor_name'] = doctors_map.get(r.get('doctor_id'), '')
                # Strip private_notes for assistant role
                if role not in CLINICAL_ROLES:
                    r.pop('private_notes', None)

        return records
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"List medical records error: {e}")
        raise HTTPException(status_code=500, detail="Error al listar registros médicos")

@router.get("/clinic/medical-records/{record_id}")
async def get_medical_record(record_id: str, ctx=Depends(require_clinic_member)):
    """Get a single medical record"""
    validate_uuid(record_id, "record_id")
    clinic_id = ctx["member"]["clinic_id"]
    role = ctx["member"].get("role", "")

    if role in ("receptionist",):
        raise HTTPException(status_code=403, detail="No tiene acceso a historias clínicas")

    try:
        result = sdb.table('medical_records').select('*').eq('id', record_id).eq('clinic_id', clinic_id).maybe_single().execute()
        data = getattr(result, 'data', None) if result else None
        if not data:
            raise HTTPException(status_code=404, detail="Registro no encontrado")

        record = data
        doc = sdb.table('clinic_members').select('first_name,last_name').eq('id', record.get('doctor_id', '')).maybe_single().execute()
        doc_data = getattr(doc, 'data', None) if doc else None
        record['doctor_name'] = f"{doc_data['first_name']} {doc_data['last_name']}" if doc_data else ""

        patient = sdb.table('patients').select('first_name,last_name').eq('id', record.get('patient_id', '')).maybe_single().execute()
        patient_data = getattr(patient, 'data', None) if patient else None
        record['patient_name'] = f"{patient_data['first_name']} {patient_data['last_name']}" if patient_data else ""

        if role not in CLINICAL_ROLES:
            record.pop('private_notes', None)

        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get medical record error: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener registro")

@router.put("/clinic/medical-records/{record_id}")
async def update_medical_record(record_id: str, data: MedicalRecordCreate, ctx=Depends(require_clinic_member)):
    """Update a draft medical record"""
    require_clinical_role(ctx)
    clinic_id = ctx["member"]["clinic_id"]
    try:
        existing = sdb.table('medical_records').select('id,status,doctor_id').eq('id', record_id).eq('clinic_id', clinic_id).maybe_single().execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Registro no encontrado")
        if existing.data['status'] == 'finalized':
            raise HTTPException(status_code=400, detail="No se puede editar un registro finalizado. Use addendum.")

        update_data = {"updated_at": now_iso()}
        for field, val in data.model_dump().items():
            if val is not None and field != 'patient_id':
                # Convert oxygen_saturation to int for database compatibility
                if field == 'oxygen_saturation':
                    update_data[field] = int(val)
                else:
                    update_data[field] = val

        if update_data.get('status') == 'finalized':
            update_data['finalized_at'] = now_iso()

        sdb.table('medical_records').update(update_data).eq('id', record_id).execute()
        return {"message": "Registro actualizado"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update medical record error: {e}")
        raise HTTPException(status_code=500, detail="Error al actualizar registro")

@router.put("/clinic/medical-records/{record_id}/finalize")
async def finalize_medical_record(record_id: str, ctx=Depends(require_clinic_member)):
    """Finalize a medical record (no further edits allowed)"""
    require_clinical_role(ctx)
    clinic_id = ctx["member"]["clinic_id"]
    try:
        existing = sdb.table('medical_records').select('id,status').eq('id', record_id).eq('clinic_id', clinic_id).maybe_single().execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Registro no encontrado")
        if existing.data['status'] == 'finalized':
            raise HTTPException(status_code=400, detail="Registro ya finalizado")

        now = now_iso()
        sdb.table('medical_records').update({
            "status": "finalized",
            "finalized_at": now,
            "updated_at": now,
        }).eq('id', record_id).execute()
        return {"message": "Consulta finalizada"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Finalize record error: {e}")
        raise HTTPException(status_code=500, detail="Error al finalizar registro")

@router.post("/clinic/medical-records/{record_id}/addendum")
async def add_addendum(record_id: str, data: AddendumCreate, ctx=Depends(require_clinic_member)):
    """Add an addendum to a finalized record"""
    require_clinical_role(ctx)
    clinic_id = ctx["member"]["clinic_id"]
    member = ctx["member"]
    try:
        existing = sdb.table('medical_records').select('id,addenda').eq('id', record_id).eq('clinic_id', clinic_id).maybe_single().execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Registro no encontrado")

        addenda = existing.data.get('addenda') or []
        addenda.append({
            "text": data.text,
            "doctor_id": member["id"],
            "doctor_name": f"{member['first_name']} {member['last_name']}",
            "created_at": now_iso(),
        })

        sdb.table('medical_records').update({
            "addenda": addenda,
            "updated_at": now_iso(),
        }).eq('id', record_id).execute()
        return {"message": "Addendum agregado"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Add addendum error: {e}")
        raise HTTPException(status_code=500, detail="Error al agregar addendum")

