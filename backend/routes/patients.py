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
    validate_uuid,
)

# ============== PATIENT ROUTES (CLINIC) ==============

@router.get("/clinic/patients/search")
async def search_patients(q: str = "", ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        if not q or len(q) < 2:
            result = sdb.table('patients').select('id,first_name,last_name,phone,national_id').eq('clinic_id', clinic_id).eq('is_active', True).order('first_name').limit(20).execute()
        else:
            result = sdb.table('patients').select('id,first_name,last_name,phone,national_id').eq('clinic_id', clinic_id).eq('is_active', True).or_(f'first_name.ilike.%{q}%,last_name.ilike.%{q}%,national_id.ilike.%{q}%,phone.ilike.%{q}%').limit(20).execute()
        return result.data or []
    except Exception as e:
        logger.error(f"Search patients error: {e}")
        raise HTTPException(status_code=500, detail="Error al buscar pacientes")

@router.get("/clinic/patients")
async def list_patients(
    q: str = "",
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 25,
    ctx=Depends(require_clinic_member)
):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        query = sdb.table('patients').select('id,first_name,last_name,phone,email,national_id,date_of_birth,gender,is_active,created_at', count='exact').eq('clinic_id', clinic_id)

        if q:
            query = query.or_(f'first_name.ilike.%{q}%,last_name.ilike.%{q}%,national_id.ilike.%{q}%,phone.ilike.%{q}%')
        if status == 'active':
            query = query.eq('is_active', True)
        elif status == 'inactive':
            query = query.eq('is_active', False)

        offset = (page - 1) * limit
        result = query.order('first_name').range(offset, offset + limit - 1).execute()
        patients = result.data or []

        # Enrich with visit counts and last visit
        for p in patients:
            apts = sdb.table('appointments').select('starts_at', count='exact').eq('patient_id', p['id']).eq('status', 'completed').execute()
            p['visit_count'] = apts.count or 0
            last = sdb.table('appointments').select('starts_at').eq('patient_id', p['id']).neq('status', 'cancelled').order('starts_at', desc=True).limit(1).execute()
            p['last_visit'] = last.data[0]['starts_at'] if last.data else None

        return {
            "patients": patients,
            "total": result.count or 0,
            "page": page,
            "limit": limit,
            "pages": ((result.count or 0) + limit - 1) // limit,
        }
    except Exception as e:
        logger.error(f"List patients error: {e}")
        raise HTTPException(status_code=500, detail="Error al listar pacientes")

@router.post("/clinic/patients")
async def create_patient(data: PatientFullCreate, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        now = now_iso()
        patient_id = str(uuid.uuid4())
        doc = {
            "id": patient_id,
            "clinic_id": clinic_id,
            "first_name": data.first_name,
            "last_name": data.last_name,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
        # Optional fields
        optional = ['date_of_birth','gender','national_id','nationality','phone','phone_secondary',
                     'email','address','city','state','country',
                     'emergency_contact_name','emergency_contact_relation','emergency_contact_phone',
                     'blood_type','allergies','chronic_conditions','current_medications',
                     'insurance_provider','insurance_policy_number','insurance_expiry','notes']
        for field in optional:
            val = getattr(data, field, None)
            if val is not None:
                doc[field] = val

        sdb.table('patients').insert(doc).execute()
        return {"id": patient_id, "first_name": data.first_name, "last_name": data.last_name, "message": "Paciente creado exitosamente"}
    except Exception as e:
        logger.error(f"Create patient error: {e}")
        raise HTTPException(status_code=500, detail=f"Error al crear paciente: {str(e)}")

@router.get("/clinic/patients/{patient_id}")
async def get_patient(patient_id: str, ctx=Depends(require_clinic_member)):
    validate_uuid(patient_id, "patient_id")
    clinic_id = ctx["member"]["clinic_id"]
    try:
        result = sdb.table('patients').select('*').eq('id', patient_id).eq('clinic_id', clinic_id).maybe_single().execute()
        data = getattr(result, 'data', None) if result else None
        if not data:
            raise HTTPException(status_code=404, detail="Paciente no encontrado")

        patient = data
        # Remove search_vector from response
        patient.pop('search_vector', None)

        # Get visit stats
        completed = sdb.table('appointments').select('id', count='exact').eq('patient_id', patient_id).eq('status', 'completed').execute()
        total_apts = sdb.table('appointments').select('id', count='exact').eq('patient_id', patient_id).neq('status', 'cancelled').execute()
        last = sdb.table('appointments').select('starts_at,reason,doctor_id').eq('patient_id', patient_id).neq('status', 'cancelled').order('starts_at', desc=True).limit(1).execute()
        next_apt = sdb.table('appointments').select('starts_at,reason,doctor_id').eq('patient_id', patient_id).eq('status', 'scheduled').gte('starts_at', now_iso()).order('starts_at').limit(1).execute()

        # Get recent appointments
        recent = sdb.table('appointments').select('*').eq('patient_id', patient_id).order('starts_at', desc=True).limit(20).execute()
        for apt in (recent.data or []):
            d = sdb.table('clinic_members').select('first_name,last_name').eq('id', apt.get('doctor_id','')).maybe_single().execute()
            apt['doctor_name'] = f"{d.data['first_name']} {d.data['last_name']}" if d.data else ""

        # Get files
        files = []
        try:
            file_list = supabase_admin.storage.from_('patient-files').list(f"{clinic_id}/{patient_id}")
            for f in (file_list or []):
                if f.get('name'):
                    files.append({
                        "name": f['name'],
                        "size": f.get('metadata', {}).get('size', 0) if f.get('metadata') else 0,
                        "created_at": f.get('created_at', ''),
                        "content_type": f.get('metadata', {}).get('mimetype', '') if f.get('metadata') else '',
                    })
        except Exception:
            pass

        return {
            "patient": patient,
            "stats": {
                "completed_visits": completed.count or 0,
                "total_appointments": total_apts.count or 0,
                "last_visit": last.data[0] if last.data else None,
                "next_appointment": next_apt.data[0] if next_apt.data else None,
            },
            "appointments": recent.data or [],
            "files": files,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get patient error: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener paciente")

@router.put("/clinic/patients/{patient_id}")
async def update_patient(patient_id: str, data: PatientFullCreate, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        existing = sdb.table('patients').select('id').eq('id', patient_id).eq('clinic_id', clinic_id).maybe_single().execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Paciente no encontrado")

        update_data = {"updated_at": now_iso()}
        for field, val in data.model_dump().items():
            if val is not None:
                update_data[field] = val

        sdb.table('patients').update(update_data).eq('id', patient_id).execute()
        updated = sdb.table('patients').select('*').eq('id', patient_id).single().execute()
        updated.data.pop('search_vector', None)
        return updated.data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update patient error: {e}")
        raise HTTPException(status_code=500, detail="Error al actualizar paciente")

@router.put("/clinic/patients/{patient_id}/toggle-active")
async def toggle_patient_active(patient_id: str, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        patient = sdb.table('patients').select('is_active').eq('id', patient_id).eq('clinic_id', clinic_id).maybe_single().execute()
        if not patient.data:
            raise HTTPException(status_code=404, detail="Paciente no encontrado")
        new_val = not patient.data['is_active']
        sdb.table('patients').update({"is_active": new_val, "updated_at": now_iso()}).eq('id', patient_id).execute()
        return {"is_active": new_val}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Toggle patient error: {e}")
        raise HTTPException(status_code=500, detail="Error")



# ============== PATIENT FILE ROUTES ==============

@router.post("/clinic/patients/{patient_id}/files")
async def upload_patient_file(patient_id: str, file: UploadFile = File(...), ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        # Validate patient
        patient = sdb.table('patients').select('id').eq('id', patient_id).eq('clinic_id', clinic_id).maybe_single().execute()
        if not patient.data:
            raise HTTPException(status_code=404, detail="Paciente no encontrado")

        # Validate file
        allowed = ['image/jpeg', 'image/png', 'application/pdf', 'application/dicom']
        if file.content_type not in allowed:
            raise HTTPException(status_code=400, detail="Tipo no permitido. Permitidos: JPG, PNG, PDF, DICOM")

        content = await file.read()
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Archivo excede 10MB")

        # Upload to Supabase Storage
        path = f"{clinic_id}/{patient_id}/{file.filename}"
        supabase_admin.storage.from_('patient-files').upload(path, content, {"content-type": file.content_type, "upsert": "true"})

        return {"message": "Archivo subido", "name": file.filename, "size": len(content), "content_type": file.content_type}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload file error: {e}")
        raise HTTPException(status_code=500, detail=f"Error al subir archivo: {str(e)}")

@router.get("/clinic/patients/{patient_id}/files/{filename}/url")
async def get_file_url(patient_id: str, filename: str, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        path = f"{clinic_id}/{patient_id}/{filename}"
        signed = supabase_admin.storage.from_('patient-files').create_signed_url(path, 3600)
        return {"url": signed.get('signedURL') or signed.get('signedUrl', '')}
    except Exception as e:
        logger.error(f"Get file URL error: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener URL")

@router.delete("/clinic/patients/{patient_id}/files/{filename}")
async def delete_patient_file(patient_id: str, filename: str, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        path = f"{clinic_id}/{patient_id}/{filename}"
        supabase_admin.storage.from_('patient-files').remove([path])
        return {"message": "Archivo eliminado"}
    except Exception as e:
        logger.error(f"Delete file error: {e}")
        raise HTTPException(status_code=500, detail="Error al eliminar archivo")
