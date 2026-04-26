"""Auto-extracted from server.py."""
import uuid
import logging
from datetime import datetime, timezone, timedelta, date
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Body, Request
from pydantic import BaseModel

router = APIRouter()

# Shared deps from server module (imported at file-load time, after server.py finishes init)
from server import (
    sdb, supabase_admin, supabase_user, logger, now_iso,
    generate_password, generate_slug, enrich_member, get_auth_users_map,
    get_plan_limits, parse_presentations,
    require_clinic_member, require_super_admin, get_current_user,
    LoginRequest, LoginResponse, ClinicCreate, ClinicUpdate, ClinicMemberCreate, UserUpdate,
    MedicationCreate, MedicationBulkImport, LabStudyCreate, LabStudyBulkImport,
    ICD10CodeCreate, ICD10BulkImport,
    AppointmentCreate, AppointmentUpdate, AppointmentStatusUpdate,
    PatientQuickCreate, PatientFullCreate,
)

# ============== CATALOG ROUTES ==============

# Medications
@router.get("/admin/catalogs/medications")
async def list_medications(user=Depends(require_super_admin)):
    result = sdb.table('medications').select('*').is_('clinic_id', 'null').order('generic_name').execute()
    return result.data or []

@router.post("/admin/catalogs/medications")
async def create_medication(data: MedicationCreate, user=Depends(require_super_admin)):
    now = now_iso()
    doc = {
        "id": str(uuid.uuid4()),
        "clinic_id": None,
        "generic_name": data.generic_name,
        "brand_name": data.brand_name or "",
        "presentations": parse_presentations(data.presentations),
        "category": data.category or "",
        "is_active": True,
        "created_at": now,
    }
    result = sdb.table('medications').insert(doc).execute()
    return result.data[0] if result.data else doc

@router.put("/admin/catalogs/medications/{med_id}")
async def update_medication(med_id: str, data: MedicationCreate, user=Depends(require_super_admin)):
    update_data = {
        "generic_name": data.generic_name,
        "brand_name": data.brand_name or "",
        "presentations": parse_presentations(data.presentations),
        "category": data.category or "",
    }
    sdb.table('medications').update(update_data).eq('id', med_id).execute()
    result = sdb.table('medications').select('*').eq('id', med_id).single().execute()
    return result.data

@router.delete("/admin/catalogs/medications/{med_id}")
async def deactivate_medication(med_id: str, user=Depends(require_super_admin)):
    sdb.table('medications').update({"is_active": False}).eq('id', med_id).execute()
    return {"message": "Medicamento desactivado"}

@router.post("/admin/catalogs/medications/bulk")
async def bulk_import_medications(data: MedicationBulkImport, user=Depends(require_super_admin)):
    now = now_iso()
    imported = 0
    errors = []

    for med in data.medications:
        try:
            doc = {
                "id": str(uuid.uuid4()),
                "clinic_id": None,
                "generic_name": med.generic_name,
                "brand_name": med.brand_name or "",
                "presentations": parse_presentations(med.presentations),
                "category": med.category or "",
                "is_active": True,
                "created_at": now,
            }
            sdb.table('medications').insert(doc).execute()
            imported += 1
        except Exception as e:
            errors.append(f"{med.generic_name}: {str(e)}")

    return {"imported": imported, "errors": errors, "total": len(data.medications)}

# Lab Studies
@router.get("/admin/catalogs/lab-studies")
async def list_lab_studies(user=Depends(require_super_admin)):
    result = sdb.table('lab_studies').select('*').is_('clinic_id', 'null').order('name').execute()
    return result.data or []

@router.post("/admin/catalogs/lab-studies")
async def create_lab_study(data: LabStudyCreate, user=Depends(require_super_admin)):
    now = now_iso()
    doc = {
        "id": str(uuid.uuid4()),
        "clinic_id": None,
        "name": data.name,
        "category": data.category or "General",
        "preparation": data.preparation or "",
        "is_active": True,
        "created_at": now,
    }
    result = sdb.table('lab_studies').insert(doc).execute()
    return result.data[0] if result.data else doc

@router.put("/admin/catalogs/lab-studies/{study_id}")
async def update_lab_study(study_id: str, data: LabStudyCreate, user=Depends(require_super_admin)):
    update_data = {
        "name": data.name,
        "category": data.category or "General",
        "preparation": data.preparation or "",
    }
    sdb.table('lab_studies').update(update_data).eq('id', study_id).execute()
    result = sdb.table('lab_studies').select('*').eq('id', study_id).single().execute()
    return result.data

@router.delete("/admin/catalogs/lab-studies/{study_id}")
async def deactivate_lab_study(study_id: str, user=Depends(require_super_admin)):
    sdb.table('lab_studies').update({"is_active": False}).eq('id', study_id).execute()
    return {"message": "Estudio desactivado"}

@router.post("/admin/catalogs/lab-studies/bulk")
async def bulk_import_lab_studies(data: LabStudyBulkImport, user=Depends(require_super_admin)):
    now = now_iso()
    imported = 0
    errors = []

    for study in data.studies:
        try:
            doc = {
                "id": str(uuid.uuid4()),
                "clinic_id": None,
                "name": study.name,
                "category": study.category or "General",
                "preparation": study.preparation or "",
                "is_active": True,
                "created_at": now,
            }
            sdb.table('lab_studies').insert(doc).execute()
            imported += 1
        except Exception as e:
            errors.append(f"{study.name}: {str(e)}")

    return {"imported": imported, "errors": errors, "total": len(data.studies)}

# ICD-10 Codes
@router.get("/admin/catalogs/icd10")
async def list_icd10_codes(user=Depends(require_super_admin)):
    result = sdb.table('icd10_codes').select('*').order('code').execute()
    return result.data or []

@router.post("/admin/catalogs/icd10")
async def create_icd10_code(data: ICD10CodeCreate, user=Depends(require_super_admin)):
    doc = {
        "code": data.code,
        "description_en": data.description_es,
        "description_es": data.description_es,
        "category": data.category or "",
        "is_common": data.is_common,
    }
    result = sdb.table('icd10_codes').insert(doc).execute()
    return result.data[0] if result.data else doc

@router.put("/admin/catalogs/icd10/{code_id}")
async def update_icd10_code(code_id: int, data: ICD10CodeCreate, user=Depends(require_super_admin)):
    update_data = {
        "code": data.code,
        "description_es": data.description_es,
        "description_en": data.description_es,
        "category": data.category or "",
        "is_common": data.is_common,
    }
    sdb.table('icd10_codes').update(update_data).eq('id', code_id).execute()
    result = sdb.table('icd10_codes').select('*').eq('id', code_id).single().execute()
    return result.data

@router.put("/admin/catalogs/icd10/{code_id}/toggle-common")
async def toggle_icd10_common(code_id: int, user=Depends(require_super_admin)):
    code = sdb.table('icd10_codes').select('is_common').eq('id', code_id).maybe_single().execute()
    if not code.data:
        raise HTTPException(status_code=404, detail="Codigo no encontrado")

    new_value = not code.data.get("is_common", False)
    sdb.table('icd10_codes').update({"is_common": new_value}).eq('id', code_id).execute()
    return {"is_common": new_value}

@router.post("/admin/catalogs/icd10/bulk")
async def bulk_import_icd10(data: ICD10BulkImport, user=Depends(require_super_admin)):
    imported = 0
    errors = []

    # Get existing codes
    existing = sdb.table('icd10_codes').select('code').execute()
    existing_codes = {r['code'] for r in (existing.data or [])}

    for code in data.codes:
        try:
            if code.code in existing_codes:
                errors.append(f"{code.code}: Ya existe")
                continue

            doc = {
                "code": code.code,
                "description_en": code.description_es,
                "description_es": code.description_es,
                "category": code.category or "",
                "is_common": code.is_common,
            }
            sdb.table('icd10_codes').insert(doc).execute()
            imported += 1
            existing_codes.add(code.code)
        except Exception as e:
            errors.append(f"{code.code}: {str(e)}")

    return {"imported": imported, "errors": errors, "total": len(data.codes)}

# ============== ICD-10 SEED ==============

@router.post("/admin/catalogs/icd10/seed")
async def seed_icd10_codes(user=Depends(require_super_admin)):
    """Precarga codigos CIE-10 comunes"""
    from icd10_data import ICD10_CODES

    # Get existing codes
    existing = sdb.table('icd10_codes').select('code').execute()
    existing_codes = {r['code'] for r in (existing.data or [])}

    imported = 0
    skipped = 0
    batch = []

    for code_data in ICD10_CODES:
        if code_data["code"] in existing_codes:
            skipped += 1
            continue

        batch.append({
            "code": code_data["code"],
            "description_en": code_data["description_es"],
            "description_es": code_data["description_es"],
            "category": code_data.get("category", ""),
            "is_common": code_data.get("is_common", False),
        })

    # Batch insert in chunks of 50
    for i in range(0, len(batch), 50):
        chunk = batch[i:i+50]
        try:
            sdb.table('icd10_codes').insert(chunk).execute()
            imported += len(chunk)
        except Exception as e:
            logger.error(f"Batch insert error at offset {i}: {e}")
            # Try one by one for this chunk
            for doc in chunk:
                try:
                    sdb.table('icd10_codes').insert(doc).execute()
                    imported += 1
                except Exception as e2:
                    logger.error(f"Insert error for {doc['code']}: {e2}")

    total = sdb.table('icd10_codes').select('id', count='exact').execute()

    return {
        "message": "Base de datos CIE-10 precargada",
        "imported": imported,
        "skipped": skipped,
        "total_in_database": total.count or 0
    }

