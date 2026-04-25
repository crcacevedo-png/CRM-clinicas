from fastapi import FastAPI, APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from supabase import create_client, Client
import os
import logging
import secrets
import string
from pathlib import Path
from pydantic import BaseModel, EmailStr
from pydantic_settings import BaseSettings
from typing import List, Optional
import uuid
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Settings
class Settings(BaseSettings):
    supabase_url: str = os.environ.get('SUPABASE_URL', '')
    supabase_anon_key: str = os.environ.get('SUPABASE_ANON_KEY', '')
    supabase_service_role_key: str = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
    super_admin_email: str = os.environ.get('SUPER_ADMIN_EMAIL', '')
    super_admin_password: str = os.environ.get('SUPER_ADMIN_PASSWORD', '')

settings = Settings()

# Supabase clients
supabase_user: Client = create_client(settings.supabase_url, settings.supabase_anon_key)
supabase_admin: Client = create_client(settings.supabase_url, settings.supabase_service_role_key)

# Shorthand for DB operations (service role bypasses RLS)
sdb = supabase_admin

# Create the main app
app = FastAPI(title="Clinic CRM Super Admin API")
api_router = APIRouter(prefix="/api")
security = HTTPBearer()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============== MODELS ==============

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    user_type: str
    user_id: str
    email: str
    clinic_id: Optional[str] = None

class ClinicCreate(BaseModel):
    name: str
    country: str
    city: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    timezone: Optional[str] = None
    plan: str = "free"
    admin_name: str
    admin_lastname: str
    admin_email: EmailStr
    admin_phone: Optional[str] = None
    admin_password: str

class ClinicUpdate(BaseModel):
    name: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    timezone: Optional[str] = None
    plan: Optional[str] = None
    is_active: Optional[bool] = None

class ClinicMemberCreate(BaseModel):
    name: str
    lastname: str
    email: EmailStr
    phone: Optional[str] = None
    password: str
    role: str = "staff"

class UserUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None
    clinic_id: Optional[str] = None

class MedicationCreate(BaseModel):
    generic_name: str
    brand_name: Optional[str] = None
    presentations: Optional[str] = ""
    category: Optional[str] = None

class MedicationBulkImport(BaseModel):
    medications: List[MedicationCreate]

class LabStudyCreate(BaseModel):
    name: str
    category: Optional[str] = None
    preparation: Optional[str] = None

class LabStudyBulkImport(BaseModel):
    studies: List[LabStudyCreate]

class ICD10CodeCreate(BaseModel):
    code: str
    description_es: str
    category: Optional[str] = None
    is_common: bool = False

class ICD10BulkImport(BaseModel):
    codes: List[ICD10CodeCreate]

# ============== HELPERS ==============

def generate_slug(name: str) -> str:
    slug = name.lower().replace(" ", "-").replace(".", "").replace(",", "")
    return ''.join(c for c in slug if c.isalnum() or c == '-')

def generate_password(length: int = 12) -> str:
    characters = string.ascii_letters + string.digits + "!@#$%"
    return ''.join(secrets.choice(characters) for _ in range(length))

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def get_plan_limits(plan: str) -> dict:
    limits = {
        "free": {"max_users": 3, "max_patients": 100, "max_storage_mb": 512},
        "basic": {"max_users": 5, "max_patients": 500, "max_storage_mb": 2048},
        "professional": {"max_users": 10, "max_patients": 1000, "max_storage_mb": 5120},
        "premium": {"max_users": 25, "max_patients": 5000, "max_storage_mb": 10240},
        "enterprise": {"max_users": 50, "max_patients": 10000, "max_storage_mb": 51200},
    }
    return limits.get(plan, limits["free"])

def parse_presentations(val) -> list:
    if isinstance(val, list):
        return val
    if isinstance(val, str) and val.strip():
        return [p.strip() for p in val.split(',') if p.strip()]
    return []

def get_auth_users_map() -> dict:
    """Get map of user_id -> {email, last_sign_in_at} from Supabase Auth"""
    users = supabase_admin.auth.admin.list_users()
    result = {}
    for u in users:
        last_sign = None
        if hasattr(u, 'last_sign_in_at') and u.last_sign_in_at:
            last_sign = u.last_sign_in_at if isinstance(u.last_sign_in_at, str) else u.last_sign_in_at.isoformat()
        result[u.id] = {"email": u.email, "last_sign_in_at": last_sign}
    return result

def enrich_member(member: dict, auth_map: dict) -> dict:
    """Transform Supabase clinic_member to frontend-compatible format"""
    auth_data = auth_map.get(member.get("user_id"), {})
    return {
        "id": member["id"],
        "user_id": member.get("user_id"),
        "clinic_id": member.get("clinic_id"),
        "name": member.get("first_name", ""),
        "lastname": member.get("last_name", ""),
        "email": auth_data.get("email", ""),
        "phone": member.get("phone"),
        "role": member.get("role"),
        "specialty": member.get("specialty"),
        "is_active": member.get("is_active", True),
        "last_login": auth_data.get("last_sign_in_at"),
        "created_at": member.get("created_at"),
        "updated_at": member.get("updated_at"),
    }

# ============== AUTH HELPERS ==============

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        response = supabase_admin.auth.get_user(token)
        if response and response.user:
            return response.user
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        logger.error(f"Token validation error: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")

async def require_super_admin(user=Depends(get_current_user)):
    result = sdb.table('super_admins').select('id').eq('user_id', user.id).execute()
    if not result.data:
        raise HTTPException(status_code=403, detail="Super admin access required")
    return user

# ============== INITIALIZATION ==============

@app.on_event("startup")
async def startup_event():
    """Initialize super admin on startup"""
    try:
        result = sdb.table('super_admins').select('id').eq('email', settings.super_admin_email).execute()
        if not result.data:
            try:
                response = supabase_admin.auth.admin.create_user({
                    "email": settings.super_admin_email,
                    "password": settings.super_admin_password,
                    "email_confirm": True
                })
                if response.user:
                    now = now_iso()
                    sdb.table('super_admins').insert({
                        "id": str(uuid.uuid4()),
                        "user_id": response.user.id,
                        "first_name": "Admin",
                        "last_name": "Super",
                        "email": settings.super_admin_email,
                        "is_active": True,
                        "created_at": now,
                        "updated_at": now,
                    }).execute()
                    logger.info(f"Super admin created: {settings.super_admin_email}")
            except Exception as e:
                logger.warning(f"Could not create super admin in Supabase Auth: {e}")
                try:
                    users = supabase_admin.auth.admin.list_users()
                    for u in users:
                        if u.email == settings.super_admin_email:
                            now = now_iso()
                            sdb.table('super_admins').insert({
                                "id": str(uuid.uuid4()),
                                "user_id": u.id,
                                "first_name": "Admin",
                                "last_name": "Super",
                                "email": settings.super_admin_email,
                                "is_active": True,
                                "created_at": now,
                                "updated_at": now,
                            }).execute()
                            logger.info(f"Super admin linked: {settings.super_admin_email}")
                            break
                except Exception as e2:
                    logger.error(f"Error linking super admin: {e2}")
    except Exception as e:
        logger.error(f"Startup error: {e}")

# ============== AUTH ROUTES ==============

@api_router.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    try:
        response = supabase_user.auth.sign_in_with_password({
            "email": request.email,
            "password": request.password
        })

        if not response.session:
            raise HTTPException(status_code=401, detail="Credenciales invalidas")

        user_id = response.user.id

        # Check user type in Supabase tables
        sa = sdb.table('super_admins').select('id').eq('user_id', user_id).execute()
        if sa.data:
            return LoginResponse(
                access_token=response.session.access_token,
                refresh_token=response.session.refresh_token,
                user_type="super_admin",
                user_id=user_id,
                email=request.email
            )

        cm = sdb.table('clinic_members').select('clinic_id').eq('user_id', user_id).eq('is_active', True).execute()
        if cm.data:
            return LoginResponse(
                access_token=response.session.access_token,
                refresh_token=response.session.refresh_token,
                user_type="clinic_member",
                user_id=user_id,
                email=request.email,
                clinic_id=cm.data[0].get("clinic_id")
            )

        raise HTTPException(status_code=403, detail="No tienes acceso al sistema")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=401, detail="Error de autenticacion")

@api_router.post("/auth/logout")
async def logout(user=Depends(get_current_user)):
    try:
        supabase_user.auth.sign_out()
    except Exception:
        pass
    return {"message": "Sesion cerrada correctamente"}

# ============== DASHBOARD ROUTES ==============

@api_router.get("/admin/dashboard")
async def get_dashboard_stats(user=Depends(require_super_admin)):
    try:
        active = sdb.table('clinics').select('id', count='exact').eq('is_active', True).execute()
        inactive = sdb.table('clinics').select('id', count='exact').eq('is_active', False).execute()
        users_count = sdb.table('clinic_members').select('id', count='exact').execute()
        patients_count = sdb.table('patients').select('id', count='exact').execute()

        recent = sdb.table('clinics').select('*').order('created_at', desc=True).limit(10).execute()
        recent_clinics = recent.data or []

        for clinic in recent_clinics:
            uc = sdb.table('clinic_members').select('id', count='exact').eq('clinic_id', clinic['id']).execute()
            pc = sdb.table('patients').select('id', count='exact').eq('clinic_id', clinic['id']).execute()
            clinic["users_count"] = uc.count or 0
            clinic["patients_count"] = pc.count or 0

        return {
            "active_clinics": active.count or 0,
            "inactive_clinics": inactive.count or 0,
            "total_users": users_count.count or 0,
            "total_patients": patients_count.count or 0,
            "recent_clinics": recent_clinics
        }
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener estadisticas")

# ============== CLINIC ROUTES ==============

@api_router.get("/admin/clinics")
async def list_clinics(
    search: Optional[str] = None,
    country: Optional[str] = None,
    plan: Optional[str] = None,
    status: Optional[str] = None,
    user=Depends(require_super_admin)
):
    try:
        query = sdb.table('clinics').select('*')

        if search:
            query = query.ilike('name', f'%{search}%')
        if country:
            query = query.eq('country', country)
        if plan:
            query = query.eq('plan', plan)
        if status:
            query = query.eq('is_active', status == "active")

        result = query.order('created_at', desc=True).execute()
        clinics = result.data or []

        for clinic in clinics:
            uc = sdb.table('clinic_members').select('id', count='exact').eq('clinic_id', clinic['id']).execute()
            pc = sdb.table('patients').select('id', count='exact').eq('clinic_id', clinic['id']).execute()
            clinic["users_count"] = uc.count or 0
            clinic["patients_count"] = pc.count or 0

        return clinics
    except Exception as e:
        logger.error(f"List clinics error: {e}")
        raise HTTPException(status_code=500, detail="Error al listar clinicas")

@api_router.post("/admin/clinics")
async def create_clinic(data: ClinicCreate, user=Depends(require_super_admin)):
    try:
        # 1. Create user in Supabase Auth
        try:
            auth_response = supabase_admin.auth.admin.create_user({
                "email": data.admin_email,
                "password": data.admin_password,
                "email_confirm": True
            })
            if not auth_response.user:
                raise HTTPException(status_code=400, detail="Error al crear usuario en Supabase")
            admin_user_id = auth_response.user.id
        except Exception as e:
            logger.error(f"Supabase user creation error: {e}")
            raise HTTPException(status_code=400, detail=f"Error al crear usuario: {str(e)}")

        # 2. Create clinic
        clinic_id = str(uuid.uuid4())
        now = now_iso()
        limits = get_plan_limits(data.plan)
        tz = data.timezone or 'America/Guatemala'

        clinic_doc = {
            "id": clinic_id,
            "name": data.name,
            "slug": generate_slug(data.name),
            "country": data.country,
            "city": data.city or "",
            "address": data.address or "",
            "phone": data.phone or "",
            "email": data.email or "",
            "timezone": tz,
            "schedule_start": "08:00:00",
            "schedule_end": "17:00:00",
            "slot_duration": 30,
            "working_days": [1, 2, 3, 4, 5],
            "plan": data.plan,
            "max_users": limits["max_users"],
            "max_patients": limits["max_patients"],
            "max_storage_mb": limits["max_storage_mb"],
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }

        sdb.table('clinics').insert(clinic_doc).execute()

        # 3. Create clinic member
        member_doc = {
            "id": str(uuid.uuid4()),
            "user_id": admin_user_id,
            "clinic_id": clinic_id,
            "role": "clinic_admin",
            "first_name": data.admin_name,
            "last_name": data.admin_lastname,
            "phone": data.admin_phone or "",
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }

        sdb.table('clinic_members').insert(member_doc).execute()

        return {
            "message": "Clinica creada exitosamente",
            "clinic": clinic_doc,
            "admin_credentials": {
                "email": data.admin_email,
                "password": data.admin_password
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create clinic error: {e}")
        raise HTTPException(status_code=500, detail="Error al crear clinica")

@api_router.get("/admin/clinics/{clinic_id}")
async def get_clinic(clinic_id: str, user=Depends(require_super_admin)):
    try:
        try:
            result = sdb.table('clinics').select('*').eq('id', clinic_id).maybe_single().execute()
        except Exception:
            raise HTTPException(status_code=404, detail="Clinica no encontrada")
        if not result.data:
            raise HTTPException(status_code=404, detail="Clinica no encontrada")

        clinic = result.data

        # Get members
        members_result = sdb.table('clinic_members').select('*').eq('clinic_id', clinic_id).execute()
        auth_map = get_auth_users_map()
        members = [enrich_member(m, auth_map) for m in (members_result.data or [])]

        # Get stats
        patients_count = sdb.table('patients').select('id', count='exact').eq('clinic_id', clinic_id).execute()

        stats = {
            "total_patients": patients_count.count or 0,
            "total_appointments": 0,
            "total_prescriptions": 0,
            "members_count": len(members)
        }

        return {
            "clinic": clinic,
            "members": members,
            "stats": stats,
            "activity": []
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get clinic error: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener clinica")

@api_router.put("/admin/clinics/{clinic_id}")
async def update_clinic(clinic_id: str, data: ClinicUpdate, user=Depends(require_super_admin)):
    try:
        existing = sdb.table('clinics').select('id').eq('id', clinic_id).maybe_single().execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Clinica no encontrada")

        update_data = {k: v for k, v in data.model_dump().items() if v is not None}
        update_data["updated_at"] = now_iso()

        if "name" in update_data:
            update_data["slug"] = generate_slug(update_data["name"])

        if "plan" in update_data:
            limits = get_plan_limits(update_data["plan"])
            update_data.update(limits)

        sdb.table('clinics').update(update_data).eq('id', clinic_id).execute()

        updated = sdb.table('clinics').select('*').eq('id', clinic_id).single().execute()
        return updated.data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update clinic error: {e}")
        raise HTTPException(status_code=500, detail="Error al actualizar clinica")

@api_router.post("/admin/clinics/{clinic_id}/members")
async def add_clinic_member(clinic_id: str, data: ClinicMemberCreate, user=Depends(require_super_admin)):
    try:
        existing = sdb.table('clinics').select('id').eq('id', clinic_id).maybe_single().execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Clinica no encontrada")

        # Create user in Supabase Auth
        try:
            auth_response = supabase_admin.auth.admin.create_user({
                "email": data.email,
                "password": data.password,
                "email_confirm": True
            })
            if not auth_response.user:
                raise HTTPException(status_code=400, detail="Error al crear usuario")
            new_user_id = auth_response.user.id
        except Exception as e:
            logger.error(f"Supabase user creation error: {e}")
            raise HTTPException(status_code=400, detail=f"Error al crear usuario: {str(e)}")

        now = now_iso()
        member_doc = {
            "id": str(uuid.uuid4()),
            "user_id": new_user_id,
            "clinic_id": clinic_id,
            "role": data.role,
            "first_name": data.name,
            "last_name": data.lastname,
            "phone": data.phone or "",
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }

        sdb.table('clinic_members').insert(member_doc).execute()

        return {
            "message": "Usuario creado exitosamente",
            "credentials": {
                "email": data.email,
                "password": data.password
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Add member error: {e}")
        raise HTTPException(status_code=500, detail="Error al agregar miembro")

# ============== USER ROUTES ==============

@api_router.get("/admin/users")
async def list_users(
    search: Optional[str] = None,
    clinic_id: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    user=Depends(require_super_admin)
):
    try:
        query = sdb.table('clinic_members').select('*')

        if search:
            query = query.or_(f'first_name.ilike.%{search}%,last_name.ilike.%{search}%')
        if clinic_id:
            query = query.eq('clinic_id', clinic_id)
        if role:
            query = query.eq('role', role)
        if status:
            query = query.eq('is_active', status == "active")

        result = query.order('created_at', desc=True).execute()
        members = result.data or []

        auth_map = get_auth_users_map()
        enriched = []
        for m in members:
            enriched_m = enrich_member(m, auth_map)
            # Add clinic name
            clinic = sdb.table('clinics').select('name').eq('id', m.get('clinic_id', '')).maybe_single().execute()
            enriched_m["clinic_name"] = clinic.data["name"] if clinic.data else "N/A"
            enriched.append(enriched_m)

        # If searching by email, filter in Python
        if search:
            search_lower = search.lower()
            enriched = [u for u in enriched if (
                search_lower in u.get("name", "").lower() or
                search_lower in u.get("lastname", "").lower() or
                search_lower in u.get("email", "").lower()
            )]

        return enriched
    except Exception as e:
        logger.error(f"List users error: {e}")
        raise HTTPException(status_code=500, detail="Error al listar usuarios")

@api_router.put("/admin/users/{member_id}")
async def update_user(member_id: str, data: UserUpdate, user=Depends(require_super_admin)):
    try:
        existing = sdb.table('clinic_members').select('id').eq('id', member_id).maybe_single().execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        update_data = {k: v for k, v in data.model_dump().items() if v is not None}
        update_data["updated_at"] = now_iso()

        sdb.table('clinic_members').update(update_data).eq('id', member_id).execute()

        updated = sdb.table('clinic_members').select('*').eq('id', member_id).single().execute()
        auth_map = get_auth_users_map()
        return enrich_member(updated.data, auth_map)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update user error: {e}")
        raise HTTPException(status_code=500, detail="Error al actualizar usuario")

@api_router.post("/admin/users/{member_id}/reset-password")
async def reset_user_password(member_id: str, user=Depends(require_super_admin)):
    try:
        member = sdb.table('clinic_members').select('user_id').eq('id', member_id).maybe_single().execute()
        if not member.data:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        new_password = generate_password()

        try:
            supabase_admin.auth.admin.update_user_by_id(
                member.data["user_id"],
                {"password": new_password}
            )
        except Exception as e:
            logger.error(f"Reset password error: {e}")
            raise HTTPException(status_code=400, detail="Error al resetear contrasena")

        return {
            "message": "Contrasena reseteada exitosamente",
            "new_password": new_password
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reset password error: {e}")
        raise HTTPException(status_code=500, detail="Error al resetear contrasena")

# ============== CATALOG ROUTES ==============

# Medications
@api_router.get("/admin/catalogs/medications")
async def list_medications(user=Depends(require_super_admin)):
    result = sdb.table('medications').select('*').is_('clinic_id', 'null').order('generic_name').execute()
    return result.data or []

@api_router.post("/admin/catalogs/medications")
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

@api_router.put("/admin/catalogs/medications/{med_id}")
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

@api_router.delete("/admin/catalogs/medications/{med_id}")
async def deactivate_medication(med_id: str, user=Depends(require_super_admin)):
    sdb.table('medications').update({"is_active": False}).eq('id', med_id).execute()
    return {"message": "Medicamento desactivado"}

@api_router.post("/admin/catalogs/medications/bulk")
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
@api_router.get("/admin/catalogs/lab-studies")
async def list_lab_studies(user=Depends(require_super_admin)):
    result = sdb.table('lab_studies').select('*').is_('clinic_id', 'null').order('name').execute()
    return result.data or []

@api_router.post("/admin/catalogs/lab-studies")
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

@api_router.put("/admin/catalogs/lab-studies/{study_id}")
async def update_lab_study(study_id: str, data: LabStudyCreate, user=Depends(require_super_admin)):
    update_data = {
        "name": data.name,
        "category": data.category or "General",
        "preparation": data.preparation or "",
    }
    sdb.table('lab_studies').update(update_data).eq('id', study_id).execute()
    result = sdb.table('lab_studies').select('*').eq('id', study_id).single().execute()
    return result.data

@api_router.delete("/admin/catalogs/lab-studies/{study_id}")
async def deactivate_lab_study(study_id: str, user=Depends(require_super_admin)):
    sdb.table('lab_studies').update({"is_active": False}).eq('id', study_id).execute()
    return {"message": "Estudio desactivado"}

@api_router.post("/admin/catalogs/lab-studies/bulk")
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
@api_router.get("/admin/catalogs/icd10")
async def list_icd10_codes(user=Depends(require_super_admin)):
    result = sdb.table('icd10_codes').select('*').order('code').execute()
    return result.data or []

@api_router.post("/admin/catalogs/icd10")
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

@api_router.put("/admin/catalogs/icd10/{code_id}")
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

@api_router.put("/admin/catalogs/icd10/{code_id}/toggle-common")
async def toggle_icd10_common(code_id: int, user=Depends(require_super_admin)):
    code = sdb.table('icd10_codes').select('is_common').eq('id', code_id).maybe_single().execute()
    if not code.data:
        raise HTTPException(status_code=404, detail="Codigo no encontrado")

    new_value = not code.data.get("is_common", False)
    sdb.table('icd10_codes').update({"is_common": new_value}).eq('id', code_id).execute()
    return {"is_common": new_value}

@api_router.post("/admin/catalogs/icd10/bulk")
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

@api_router.post("/admin/catalogs/icd10/seed")
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

# ============== CLINIC MEMBER AUTH ==============

async def require_clinic_member(user=Depends(get_current_user)):
    result = sdb.table('clinic_members').select('id,clinic_id,role,first_name,last_name').eq('user_id', user.id).eq('is_active', True).maybe_single().execute()
    if not result.data:
        raise HTTPException(status_code=403, detail="Acceso de miembro de clinica requerido")
    return {"auth_user": user, "member": result.data}

# ============== CLINIC MEMBER MODELS ==============

class AppointmentCreate(BaseModel):
    patient_id: str
    doctor_id: str
    starts_at: str
    duration_minutes: int = 30
    reason: Optional[str] = None
    notes: Optional[str] = None

class AppointmentUpdate(BaseModel):
    starts_at: Optional[str] = None
    duration_minutes: Optional[int] = None
    reason: Optional[str] = None
    notes: Optional[str] = None
    doctor_id: Optional[str] = None

class AppointmentStatusUpdate(BaseModel):
    status: str
    cancellation_reason: Optional[str] = None

class PatientQuickCreate(BaseModel):
    first_name: str
    last_name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    national_id: Optional[str] = None

class PatientFullCreate(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    national_id: Optional[str] = None
    nationality: Optional[str] = None
    phone: Optional[str] = None
    phone_secondary: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_relation: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    blood_type: Optional[str] = None
    allergies: Optional[List[str]] = None
    chronic_conditions: Optional[List[str]] = None
    current_medications: Optional[List[str]] = None
    insurance_provider: Optional[str] = None
    insurance_policy_number: Optional[str] = None
    insurance_expiry: Optional[str] = None
    notes: Optional[str] = None

# ============== CLINIC CONFIG ROUTES ==============

@api_router.get("/clinic/config")
async def get_clinic_config(ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        clinic = sdb.table('clinics').select('id,name,schedule_start,schedule_end,slot_duration,working_days,timezone').eq('id', clinic_id).single().execute()

        members = sdb.table('clinic_members').select('id,first_name,last_name,role,specialty').eq('clinic_id', clinic_id).eq('is_active', True).execute()

        doctors = [m for m in (members.data or []) if m["role"] in ("doctor", "clinic_admin")]

        return {
            "clinic": clinic.data,
            "members": members.data or [],
            "doctors": doctors,
            "current_member": ctx["member"],
        }
    except Exception as e:
        logger.error(f"Clinic config error: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener configuracion")

# ============== CLINIC SETTINGS ROUTES ==============

class ClinicSettingsUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    timezone: Optional[str] = None
    schedule_start: Optional[str] = None
    schedule_end: Optional[str] = None
    slot_duration: Optional[int] = None
    working_days: Optional[list] = None
    prescription_footer: Optional[str] = None
    prescription_validity_days: Optional[int] = None

class MemberInvite(BaseModel):
    email: str
    first_name: str
    last_name: str
    role: str = "doctor"
    specialty: Optional[str] = None

class MemberUpdate(BaseModel):
    role: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    specialty: Optional[str] = None
    license_number: Optional[str] = None
    phone: Optional[str] = None

@api_router.get("/clinic/settings")
async def get_clinic_settings(ctx=Depends(require_clinic_member)):
    """Get full clinic settings (admin only)"""
    clinic_id = ctx["member"]["clinic_id"]
    try:
        clinic = sdb.table('clinics').select('*').eq('id', clinic_id).single().execute()
        return clinic.data
    except Exception as e:
        logger.error(f"Get clinic settings error: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener configuración")

@api_router.put("/clinic/settings")
async def update_clinic_settings(data: ClinicSettingsUpdate, ctx=Depends(require_clinic_member)):
    """Update clinic settings (admin only)"""
    if ctx["member"]["role"] != "clinic_admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden editar configuración")
    clinic_id = ctx["member"]["clinic_id"]
    try:
        update = {k: v for k, v in data.model_dump().items() if v is not None}
        update["updated_at"] = now_iso()
        sdb.table('clinics').update(update).eq('id', clinic_id).execute()
        return {"message": "Configuración actualizada"}
    except Exception as e:
        logger.error(f"Update clinic settings error: {e}")
        raise HTTPException(status_code=500, detail="Error al actualizar configuración")

@api_router.post("/clinic/settings/logo")
async def upload_clinic_logo(file: UploadFile = File(...), ctx=Depends(require_clinic_member)):
    """Upload clinic logo"""
    if ctx["member"]["role"] != "clinic_admin":
        raise HTTPException(status_code=403, detail="Solo administradores")
    clinic_id = ctx["member"]["clinic_id"]
    try:
        contents = await file.read()
        if len(contents) > 2 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Logo máximo 2MB")
        ext = file.filename.split('.')[-1].lower() if '.' in file.filename else 'png'
        path = f"{clinic_id}/logo.{ext}"
        supabase_admin.storage.from_('patient-files').upload(path, contents, {"content-type": file.content_type or "image/png", "upsert": "true"})
        signed = supabase_admin.storage.from_('patient-files').create_signed_url(path, 31536000)
        logo_url = signed.get('signedURL') or signed.get('signedUrl', '')
        sdb.table('clinics').update({"logo_url": logo_url, "updated_at": now_iso()}).eq('id', clinic_id).execute()
        return {"logo_url": logo_url}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload logo error: {e}")
        raise HTTPException(status_code=500, detail="Error al subir logo")

@api_router.get("/clinic/members")
async def list_clinic_members(ctx=Depends(require_clinic_member)):
    """List all clinic members"""
    clinic_id = ctx["member"]["clinic_id"]
    try:
        result = sdb.table('clinic_members').select('id,user_id,first_name,last_name,role,specialty,license_number,phone,is_active,created_at').eq('clinic_id', clinic_id).order('created_at').execute()
        members = result.data or []
        # Get emails from auth
        for m in members:
            if m.get('user_id'):
                try:
                    u = supabase_admin.auth.admin.get_user_by_id(m['user_id'])
                    m['email'] = u.user.email if u and u.user else ''
                except:
                    m['email'] = ''
            else:
                m['email'] = ''
        return members
    except Exception as e:
        logger.error(f"List members error: {e}")
        raise HTTPException(status_code=500, detail="Error al listar miembros")

@api_router.post("/clinic/members/invite")
async def invite_member(data: MemberInvite, ctx=Depends(require_clinic_member)):
    """Invite a new member to the clinic"""
    if ctx["member"]["role"] != "clinic_admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden invitar miembros")
    clinic_id = ctx["member"]["clinic_id"]
    try:
        # Check plan limits
        clinic = sdb.table('clinics').select('max_users').eq('id', clinic_id).single().execute()
        current_count = sdb.table('clinic_members').select('id', count='exact').eq('clinic_id', clinic_id).eq('is_active', True).execute()
        if (current_count.count or 0) >= (clinic.data.get('max_users') or 999):
            raise HTTPException(status_code=400, detail="Límite de usuarios alcanzado para su plan")

        # Create auth user or get existing
        temp_password = f"Temp{uuid.uuid4().hex[:8]}!"
        try:
            auth_user = supabase_admin.auth.admin.create_user({
                "email": data.email,
                "password": temp_password,
                "email_confirm": True,
            })
            user_id = auth_user.user.id
        except Exception:
            # User may already exist
            users = supabase_admin.auth.admin.list_users()
            user_id = None
            for u in users:
                if u.email == data.email:
                    user_id = u.id
                    break
            if not user_id:
                raise HTTPException(status_code=400, detail="Error al crear usuario")

        # Check if already a member
        existing = sdb.table('clinic_members').select('id,is_active').eq('clinic_id', clinic_id).eq('user_id', user_id).maybe_single().execute()
        if existing and existing.data:
            if existing.data.get('is_active'):
                raise HTTPException(status_code=400, detail="El usuario ya es miembro de esta clínica")
            else:
                sdb.table('clinic_members').update({
                    "is_active": True, "role": data.role,
                    "first_name": data.first_name, "last_name": data.last_name,
                    "specialty": data.specialty, "updated_at": now_iso(),
                }).eq('id', existing.data['id']).execute()
                return {"message": "Miembro reactivado", "id": existing.data['id']}

        member_id = str(uuid.uuid4())
        sdb.table('clinic_members').insert({
            "id": member_id, "clinic_id": clinic_id, "user_id": user_id,
            "role": data.role, "first_name": data.first_name,
            "last_name": data.last_name, "specialty": data.specialty,
            "is_active": True, "created_at": now_iso(), "updated_at": now_iso(),
        }).execute()
        return {"message": "Miembro invitado exitosamente", "id": member_id, "temp_password": temp_password}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Invite member error: {e}")
        raise HTTPException(status_code=500, detail=f"Error al invitar miembro: {str(e)}")

@api_router.put("/clinic/members/{member_id}")
async def update_member(member_id: str, data: MemberUpdate, ctx=Depends(require_clinic_member)):
    """Update a clinic member"""
    clinic_id = ctx["member"]["clinic_id"]
    current_role = ctx["member"]["role"]
    current_id = ctx["member"]["id"]

    # Only admin can change roles; members can edit their own profile
    is_self = member_id == current_id
    if not is_self and current_role != "clinic_admin":
        raise HTTPException(status_code=403, detail="No tiene permiso")
    try:
        update = {}
        if data.role is not None and current_role == "clinic_admin" and not is_self:
            update["role"] = data.role
        if data.first_name is not None: update["first_name"] = data.first_name
        if data.last_name is not None: update["last_name"] = data.last_name
        if data.specialty is not None: update["specialty"] = data.specialty
        if data.license_number is not None: update["license_number"] = data.license_number
        if data.phone is not None: update["phone"] = data.phone
        update["updated_at"] = now_iso()

        sdb.table('clinic_members').update(update).eq('id', member_id).eq('clinic_id', clinic_id).execute()
        return {"message": "Miembro actualizado"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update member error: {e}")
        raise HTTPException(status_code=500, detail="Error al actualizar miembro")

@api_router.put("/clinic/members/{member_id}/toggle")
async def toggle_member(member_id: str, ctx=Depends(require_clinic_member)):
    """Activate/deactivate a member"""
    if ctx["member"]["role"] != "clinic_admin":
        raise HTTPException(status_code=403, detail="Solo administradores")
    if member_id == ctx["member"]["id"]:
        raise HTTPException(status_code=400, detail="No puede desactivarse a sí mismo")
    clinic_id = ctx["member"]["clinic_id"]
    try:
        existing = sdb.table('clinic_members').select('id,is_active').eq('id', member_id).eq('clinic_id', clinic_id).maybe_single().execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Miembro no encontrado")
        new_status = not existing.data.get('is_active', True)
        sdb.table('clinic_members').update({"is_active": new_status, "updated_at": now_iso()}).eq('id', member_id).execute()
        return {"is_active": new_status, "message": "Miembro activado" if new_status else "Miembro desactivado"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Toggle member error: {e}")
        raise HTTPException(status_code=500, detail="Error")

# ============== APPOINTMENT ROUTES ==============

@api_router.get("/clinic/appointments")
async def list_appointments(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    doctor_id: Optional[str] = None,
    status: Optional[str] = None,
    patient_search: Optional[str] = None,
    ctx=Depends(require_clinic_member)
):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        query = sdb.table('appointments').select('*').eq('clinic_id', clinic_id)

        if start_date:
            query = query.gte('starts_at', start_date)
        if end_date:
            query = query.lte('starts_at', end_date)
        if doctor_id:
            query = query.eq('doctor_id', doctor_id)
        if status:
            query = query.eq('status', status)

        result = query.order('starts_at').execute()
        appointments = result.data or []

        # Enrich with patient and doctor names
        patient_ids = list({a["patient_id"] for a in appointments if a.get("patient_id")})
        doctor_ids = list({a["doctor_id"] for a in appointments if a.get("doctor_id")})

        patient_map = {}
        if patient_ids:
            for pid in patient_ids:
                p = sdb.table('patients').select('id,first_name,last_name').eq('id', pid).maybe_single().execute()
                if p.data:
                    patient_map[pid] = f"{p.data['first_name']} {p.data['last_name']}"

        doctor_map = {}
        if doctor_ids:
            for did in doctor_ids:
                d = sdb.table('clinic_members').select('id,first_name,last_name').eq('id', did).maybe_single().execute()
                if d.data:
                    doctor_map[did] = f"{d.data['first_name']} {d.data['last_name']}"

        for apt in appointments:
            apt["patient_name"] = patient_map.get(apt.get("patient_id"), "Desconocido")
            apt["doctor_name"] = doctor_map.get(apt.get("doctor_id"), "Desconocido")

        # Filter by patient name if needed
        if patient_search:
            search_lower = patient_search.lower()
            appointments = [a for a in appointments if search_lower in a.get("patient_name", "").lower()]

        return appointments
    except Exception as e:
        logger.error(f"List appointments error: {e}")
        raise HTTPException(status_code=500, detail="Error al listar citas")

@api_router.post("/clinic/appointments")
async def create_appointment(data: AppointmentCreate, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    member = ctx["member"]
    try:
        from datetime import datetime as dt, timedelta
        import re

        starts = dt.fromisoformat(data.starts_at.replace('Z', '+00:00'))
        if starts.tzinfo is None:
            from zoneinfo import ZoneInfo
            starts = starts.replace(tzinfo=ZoneInfo('UTC'))
        ends = starts + timedelta(minutes=data.duration_minutes)

        # Validate clinic hours
        clinic = sdb.table('clinics').select('schedule_start,schedule_end,working_days,timezone').eq('id', clinic_id).single().execute()
        c = clinic.data

        # Convert to clinic local time for validation
        from zoneinfo import ZoneInfo
        clinic_tz = ZoneInfo(c.get('timezone') or 'America/Guatemala')
        local_start = starts.astimezone(clinic_tz)
        local_end = ends.astimezone(clinic_tz)

        start_time = local_start.strftime("%H:%M:%S")
        end_time = local_end.strftime("%H:%M:%S")
        day_of_week = local_start.isoweekday()

        if day_of_week not in (c.get("working_days") or [1,2,3,4,5]):
            raise HTTPException(status_code=400, detail="La clinica no opera este dia")

        if start_time < c["schedule_start"] or end_time > c["schedule_end"]:
            raise HTTPException(status_code=400, detail=f"Fuera del horario de la clinica ({c['schedule_start']} - {c['schedule_end']})")

        # Check conflicts for this doctor
        conflicts = sdb.table('appointments').select('id').eq('clinic_id', clinic_id).eq('doctor_id', data.doctor_id).neq('status', 'cancelled').lt('starts_at', ends.isoformat()).gt('ends_at', starts.isoformat()).execute()

        if conflicts.data:
            raise HTTPException(status_code=409, detail="El doctor ya tiene una cita en ese horario")

        now = now_iso()
        apt_id = str(uuid.uuid4())
        doc = {
            "id": apt_id,
            "clinic_id": clinic_id,
            "patient_id": data.patient_id,
            "doctor_id": data.doctor_id,
            "created_by": member["id"],
            "starts_at": starts.isoformat(),
            "ends_at": ends.isoformat(),
            "duration_minutes": data.duration_minutes,
            "reason": data.reason or "",
            "notes": data.notes or "",
            "status": "scheduled",
            "created_at": now,
            "updated_at": now,
        }

        sdb.table('appointments').insert(doc).execute()

        # Return enriched
        patient = sdb.table('patients').select('first_name,last_name').eq('id', data.patient_id).maybe_single().execute()
        doctor = sdb.table('clinic_members').select('first_name,last_name').eq('id', data.doctor_id).maybe_single().execute()
        doc["patient_name"] = f"{patient.data['first_name']} {patient.data['last_name']}" if patient.data else ""
        doc["doctor_name"] = f"{doctor.data['first_name']} {doctor.data['last_name']}" if doctor.data else ""

        # Sync to Google Calendar (non-blocking)
        try:
            await sync_appointment_to_gcal(doc, "create")
        except Exception as gcal_err:
            logger.warning(f"Google Calendar sync failed (create): {gcal_err}")

        return doc
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create appointment error: {e}")
        raise HTTPException(status_code=500, detail="Error al crear cita")

@api_router.put("/clinic/appointments/{apt_id}")
async def update_appointment(apt_id: str, data: AppointmentUpdate, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        existing = sdb.table('appointments').select('*').eq('id', apt_id).eq('clinic_id', clinic_id).maybe_single().execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Cita no encontrada")

        update_data = {k: v for k, v in data.model_dump().items() if v is not None}

        if "starts_at" in update_data:
            from datetime import datetime as dt, timedelta
            from zoneinfo import ZoneInfo
            starts = dt.fromisoformat(update_data["starts_at"].replace('Z', '+00:00'))
            if starts.tzinfo is None:
                starts = starts.replace(tzinfo=ZoneInfo('UTC'))
            dur = update_data.get("duration_minutes", existing.data["duration_minutes"])
            ends = starts + timedelta(minutes=dur)
            update_data["ends_at"] = ends.isoformat()

            # Validate clinic hours in clinic timezone
            clinic = sdb.table('clinics').select('schedule_start,schedule_end,working_days,timezone').eq('id', clinic_id).single().execute()
            c = clinic.data
            clinic_tz = ZoneInfo(c.get('timezone') or 'America/Guatemala')
            local_start = starts.astimezone(clinic_tz)
            local_end = ends.astimezone(clinic_tz)
            start_time = local_start.strftime("%H:%M:%S")
            end_time = local_end.strftime("%H:%M:%S")
            day_of_week = local_start.isoweekday()
            if day_of_week not in (c.get("working_days") or [1,2,3,4,5]):
                raise HTTPException(status_code=400, detail="La clinica no opera este dia")
            if start_time < c["schedule_start"] or end_time > c["schedule_end"]:
                raise HTTPException(status_code=400, detail=f"Fuera del horario de la clinica ({c['schedule_start']} - {c['schedule_end']})")

            doctor_id = update_data.get("doctor_id", existing.data["doctor_id"])
            conflicts = sdb.table('appointments').select('id').eq('clinic_id', clinic_id).eq('doctor_id', doctor_id).neq('status', 'cancelled').neq('id', apt_id).lt('starts_at', ends.isoformat()).gt('ends_at', starts.isoformat()).execute()
            if conflicts.data:
                raise HTTPException(status_code=409, detail="Conflicto de horario con otra cita")

        update_data["updated_at"] = now_iso()
        sdb.table('appointments').update(update_data).eq('id', apt_id).execute()

        updated = sdb.table('appointments').select('*').eq('id', apt_id).single().execute()
        apt = updated.data
        patient = sdb.table('patients').select('first_name,last_name').eq('id', apt["patient_id"]).maybe_single().execute()
        doctor = sdb.table('clinic_members').select('first_name,last_name').eq('id', apt["doctor_id"]).maybe_single().execute()
        apt["patient_name"] = f"{patient.data['first_name']} {patient.data['last_name']}" if patient.data else ""
        apt["doctor_name"] = f"{doctor.data['first_name']} {doctor.data['last_name']}" if doctor.data else ""

        # Sync to Google Calendar (non-blocking)
        try:
            await sync_appointment_to_gcal(apt, "update")
        except Exception as gcal_err:
            logger.warning(f"Google Calendar sync failed (update): {gcal_err}")

        return apt
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update appointment error: {e}")
        raise HTTPException(status_code=500, detail="Error al actualizar cita")

@api_router.put("/clinic/appointments/{apt_id}/status")
async def change_appointment_status(apt_id: str, data: AppointmentStatusUpdate, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        existing = sdb.table('appointments').select('id').eq('id', apt_id).eq('clinic_id', clinic_id).maybe_single().execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Cita no encontrada")

        valid_statuses = ["scheduled", "confirmed", "in_progress", "completed", "cancelled", "no_show"]
        if data.status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Estado invalido. Opciones: {', '.join(valid_statuses)}")

        update = {"status": data.status, "updated_at": now_iso()}
        if data.status == "cancelled" and data.cancellation_reason:
            update["cancellation_reason"] = data.cancellation_reason

        sdb.table('appointments').update(update).eq('id', apt_id).execute()

        # If cancelled, delete from Google Calendar
        if data.status == "cancelled":
            try:
                apt_full = sdb.table('appointments').select('id,doctor_id,google_event_id').eq('id', apt_id).maybe_single().execute()
                if apt_full.data and apt_full.data.get('google_event_id'):
                    await sync_appointment_to_gcal(apt_full.data, "delete")
            except Exception as gcal_err:
                logger.warning(f"Google Calendar sync failed (cancel): {gcal_err}")

        return {"message": "Estado actualizado", "status": data.status}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Change status error: {e}")
        raise HTTPException(status_code=500, detail="Error al cambiar estado")

# ============== PATIENT ROUTES (CLINIC) ==============

@api_router.get("/clinic/patients/search")
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

@api_router.get("/clinic/patients")
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

@api_router.post("/clinic/patients")
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

@api_router.get("/clinic/patients/{patient_id}")
async def get_patient(patient_id: str, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        result = sdb.table('patients').select('*').eq('id', patient_id).eq('clinic_id', clinic_id).maybe_single().execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Paciente no encontrado")

        patient = result.data
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

@api_router.put("/clinic/patients/{patient_id}")
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

@api_router.put("/clinic/patients/{patient_id}/toggle-active")
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

# ============== CONSULTATION TEMPLATES ROUTES ==============

class TemplateCreate(BaseModel):
    name: str
    category: str = "general"
    description: Optional[str] = None
    template_data: dict = {}
    sort_order: int = 0

@api_router.get("/clinic/templates")
async def list_templates(ctx=Depends(require_clinic_member)):
    """List templates: global (clinic_id=null) + clinic-specific"""
    clinic_id = ctx["member"]["clinic_id"]
    try:
        global_t = sdb.table('consultation_templates').select('*').is_('clinic_id', 'null').eq('is_active', True).order('sort_order').execute()
        clinic_t = sdb.table('consultation_templates').select('*').eq('clinic_id', clinic_id).eq('is_active', True).order('sort_order').execute()
        templates = (global_t.data or []) + (clinic_t.data or [])
        return templates
    except Exception as e:
        logger.error(f"List templates error: {e}")
        raise HTTPException(status_code=500, detail="Error al listar plantillas")

@api_router.post("/clinic/templates")
async def create_template(data: TemplateCreate, ctx=Depends(require_clinic_member)):
    """Create a clinic-specific template"""
    require_clinical_role(ctx)
    clinic_id = ctx["member"]["clinic_id"]
    try:
        doc = {
            "id": str(uuid.uuid4()),
            "clinic_id": clinic_id,
            "name": data.name,
            "category": data.category,
            "description": data.description,
            "template_data": data.template_data,
            "is_active": True,
            "sort_order": data.sort_order,
        }
        sdb.table('consultation_templates').insert(doc).execute()
        return {"id": doc["id"], "message": "Plantilla creada"}
    except Exception as e:
        logger.error(f"Create template error: {e}")
        raise HTTPException(status_code=500, detail="Error al crear plantilla")

@api_router.put("/clinic/templates/{template_id}")
async def update_template(template_id: str, data: TemplateCreate, ctx=Depends(require_clinic_member)):
    """Update a clinic-specific template (cannot edit global templates)"""
    require_clinical_role(ctx)
    clinic_id = ctx["member"]["clinic_id"]
    try:
        existing = sdb.table('consultation_templates').select('id,clinic_id').eq('id', template_id).maybe_single().execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Plantilla no encontrada")
        if existing.data.get('clinic_id') is None:
            raise HTTPException(status_code=403, detail="No se pueden editar plantillas globales")
        if existing.data.get('clinic_id') != clinic_id:
            raise HTTPException(status_code=403, detail="No tiene permiso para editar esta plantilla")

        update_data = {k: v for k, v in data.model_dump().items() if v is not None}
        update_data["updated_at"] = now_iso()
        sdb.table('consultation_templates').update(update_data).eq('id', template_id).execute()
        return {"message": "Plantilla actualizada"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update template error: {e}")
        raise HTTPException(status_code=500, detail="Error al actualizar plantilla")

@api_router.delete("/clinic/templates/{template_id}")
async def delete_template(template_id: str, ctx=Depends(require_clinic_member)):
    """Deactivate a clinic-specific template"""
    require_clinical_role(ctx)
    clinic_id = ctx["member"]["clinic_id"]
    try:
        existing = sdb.table('consultation_templates').select('id,clinic_id').eq('id', template_id).maybe_single().execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Plantilla no encontrada")
        if existing.data.get('clinic_id') is None:
            raise HTTPException(status_code=403, detail="No se pueden eliminar plantillas globales")
        if existing.data.get('clinic_id') != clinic_id:
            raise HTTPException(status_code=403, detail="No tiene permiso")
        sdb.table('consultation_templates').update({"is_active": False, "updated_at": now_iso()}).eq('id', template_id).execute()
        return {"message": "Plantilla eliminada"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete template error: {e}")
        raise HTTPException(status_code=500, detail="Error al eliminar plantilla")

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

CLINICAL_ROLES = ["doctor", "clinic_admin"]

def require_clinical_role(ctx):
    role = ctx["member"].get("role", "")
    if role not in CLINICAL_ROLES:
        raise HTTPException(status_code=403, detail="Acceso restringido a médicos y administradores clínicos")
    return ctx

@api_router.get("/clinic/icd10/search")
async def search_icd10(q: str = "", limit: int = 20, ctx=Depends(require_clinic_member)):
    """Search ICD-10 codes by code or description, accessible by all clinic members"""
    try:
        if not q or len(q) < 2:
            result = sdb.table('icd10_codes').select('id,code,description_es,category,is_common').eq('is_common', True).order('code').limit(limit).execute()
        else:
            result = sdb.table('icd10_codes').select('id,code,description_es,category,is_common').or_(f'code.ilike.%{q}%,description_es.ilike.%{q}%').order('code').limit(limit).execute()
        return result.data or []
    except Exception as e:
        logger.error(f"Search ICD10 error: {e}")
        raise HTTPException(status_code=500, detail="Error al buscar códigos CIE-10")

@api_router.post("/clinic/medical-records")
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

@api_router.get("/clinic/patients/{patient_id}/medical-records")
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

        # Enrich with doctor names
        for r in records:
            doc = sdb.table('clinic_members').select('first_name,last_name').eq('id', r.get('doctor_id', '')).maybe_single().execute()
            r['doctor_name'] = f"{doc.data['first_name']} {doc.data['last_name']}" if doc.data else ""
            # Strip private_notes for assistant role
            if role not in CLINICAL_ROLES:
                r.pop('private_notes', None)

        return records
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"List medical records error: {e}")
        raise HTTPException(status_code=500, detail="Error al listar registros médicos")

@api_router.get("/clinic/medical-records/{record_id}")
async def get_medical_record(record_id: str, ctx=Depends(require_clinic_member)):
    """Get a single medical record"""
    clinic_id = ctx["member"]["clinic_id"]
    role = ctx["member"].get("role", "")

    if role in ("receptionist",):
        raise HTTPException(status_code=403, detail="No tiene acceso a historias clínicas")

    try:
        result = sdb.table('medical_records').select('*').eq('id', record_id).eq('clinic_id', clinic_id).maybe_single().execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Registro no encontrado")

        record = result.data
        doc = sdb.table('clinic_members').select('first_name,last_name').eq('id', record.get('doctor_id', '')).maybe_single().execute()
        record['doctor_name'] = f"{doc.data['first_name']} {doc.data['last_name']}" if doc.data else ""

        patient = sdb.table('patients').select('first_name,last_name').eq('id', record.get('patient_id', '')).maybe_single().execute()
        record['patient_name'] = f"{patient.data['first_name']} {patient.data['last_name']}" if patient.data else ""

        if role not in CLINICAL_ROLES:
            record.pop('private_notes', None)

        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get medical record error: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener registro")

@api_router.put("/clinic/medical-records/{record_id}")
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

@api_router.put("/clinic/medical-records/{record_id}/finalize")
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

@api_router.post("/clinic/medical-records/{record_id}/addendum")
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

@api_router.get("/clinic/medications/search")
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

@api_router.post("/clinic/medications")
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

@api_router.get("/clinic/prescriptions")
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

@api_router.get("/clinic/prescriptions/{presc_id}")
async def get_prescription(presc_id: str, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        result = sdb.table('prescriptions').select('*').eq('id', presc_id).eq('clinic_id', clinic_id).maybe_single().execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Receta no encontrada")
        presc = result.data
        pat = sdb.table('patients').select('*').eq('id', presc['patient_id']).maybe_single().execute()
        presc['patient'] = pat.data if pat.data else {}
        if presc['patient']:
            presc['patient'].pop('search_vector', None)
        doc = sdb.table('clinic_members').select('first_name,last_name,specialty,license_number').eq('id', presc['doctor_id']).maybe_single().execute()
        presc['doctor'] = doc.data if doc.data else {}
        items = sdb.table('prescription_items').select('*').eq('prescription_id', presc_id).order('sort_order').execute()
        presc['items'] = items.data or []
        return presc
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get prescription error: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener receta")

@api_router.post("/clinic/prescriptions")
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

@api_router.put("/clinic/prescriptions/{presc_id}")
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

@api_router.put("/clinic/prescriptions/{presc_id}/send")
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

@api_router.get("/clinic/prescriptions/{presc_id}/pdf-url")
async def get_prescription_pdf_url(presc_id: str, ctx=Depends(require_clinic_member)):
    """Get a fresh signed URL for the prescription PDF"""
    clinic_id = ctx["member"]["clinic_id"]
    try:
        presc = sdb.table('prescriptions').select('id').eq('id', presc_id).eq('clinic_id', clinic_id).maybe_single().execute()
        if not presc.data:
            raise HTTPException(status_code=404, detail="Receta no encontrada")
        path = f"{clinic_id}/prescriptions/{presc_id}.pdf"
        signed = supabase_admin.storage.from_('patient-files').create_signed_url(path, 3600)
        return {"url": signed.get('signedURL') or signed.get('signedUrl', '')}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get PDF URL error: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener URL del PDF")

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

@api_router.get("/clinic/lab-studies")
async def list_lab_studies(ctx=Depends(require_clinic_member)):
    """List all lab studies grouped by category"""
    clinic_id = ctx["member"]["clinic_id"]
    try:
        result = sdb.table('lab_studies').select('id,name,category,preparation').or_(f'clinic_id.is.null,clinic_id.eq.{clinic_id}').eq('is_active', True).order('category').order('name').execute()
        return result.data or []
    except Exception as e:
        logger.error(f"List lab studies error: {e}")
        raise HTTPException(status_code=500, detail="Error al listar estudios")

@api_router.get("/clinic/lab-orders")
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

        for o in orders:
            pat = sdb.table('patients').select('first_name,last_name').eq('id', o['patient_id']).maybe_single().execute()
            o['patient_name'] = f"{pat.data['first_name']} {pat.data['last_name']}" if pat.data else ""
            doc = sdb.table('clinic_members').select('first_name,last_name').eq('id', o['doctor_id']).maybe_single().execute()
            o['doctor_name'] = f"{doc.data['first_name']} {doc.data['last_name']}" if doc.data else ""
            items = sdb.table('lab_order_items').select('study_name,category').eq('lab_order_id', o['id']).execute()
            o['item_count'] = len(items.data or [])
            o['study_summary'] = ', '.join([i['study_name'] for i in (items.data or [])[:3]])
            if len(items.data or []) > 3:
                o['study_summary'] += f' +{len(items.data) - 3} más'

        return {"orders": orders, "total": result.count or 0, "page": page, "pages": ((result.count or 0) + limit - 1) // limit}
    except Exception as e:
        logger.error(f"List lab orders error: {e}")
        raise HTTPException(status_code=500, detail="Error al listar órdenes")

@api_router.get("/clinic/lab-orders/{order_id}")
async def get_lab_order(order_id: str, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        result = sdb.table('lab_orders').select('*').eq('id', order_id).eq('clinic_id', clinic_id).maybe_single().execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Orden no encontrada")
        order = result.data
        pat = sdb.table('patients').select('*').eq('id', order['patient_id']).maybe_single().execute()
        order['patient'] = pat.data if pat.data else {}
        if order['patient']:
            order['patient'].pop('search_vector', None)
        doc = sdb.table('clinic_members').select('first_name,last_name,specialty,license_number').eq('id', order['doctor_id']).maybe_single().execute()
        order['doctor'] = doc.data if doc.data else {}
        items = sdb.table('lab_order_items').select('*').eq('lab_order_id', order_id).order('sort_order').execute()
        order['items'] = items.data or []
        return order
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get lab order error: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener orden")

@api_router.post("/clinic/lab-orders")
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

@api_router.get("/clinic/lab-orders/{order_id}/pdf-url")
async def get_lab_order_pdf_url(order_id: str, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        order = sdb.table('lab_orders').select('id').eq('id', order_id).eq('clinic_id', clinic_id).maybe_single().execute()
        if not order.data:
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
        signed = supabase_admin.storage.from_('patient-files').create_signed_url(path, 86400)
        pdf_url = signed.get('signedURL') or signed.get('signedUrl', '')
        sdb.table('lab_orders').update({"pdf_url": pdf_url, "updated_at": now_iso()}).eq('id', order_id).execute()
        return pdf_url
    except Exception as e:
        logger.error(f"Generate lab order PDF error: {e}")
        return None

# ============== PATIENT FILE ROUTES ==============

@api_router.post("/clinic/patients/{patient_id}/files")
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

@api_router.get("/clinic/patients/{patient_id}/files/{filename}/url")
async def get_file_url(patient_id: str, filename: str, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        path = f"{clinic_id}/{patient_id}/{filename}"
        signed = supabase_admin.storage.from_('patient-files').create_signed_url(path, 3600)
        return {"url": signed.get('signedURL') or signed.get('signedUrl', '')}
    except Exception as e:
        logger.error(f"Get file URL error: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener URL")

@api_router.delete("/clinic/patients/{patient_id}/files/{filename}")
async def delete_patient_file(patient_id: str, filename: str, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        path = f"{clinic_id}/{patient_id}/{filename}"
        supabase_admin.storage.from_('patient-files').remove([path])
        return {"message": "Archivo eliminado"}
    except Exception as e:
        logger.error(f"Delete file error: {e}")
        raise HTTPException(status_code=500, detail="Error al eliminar archivo")

@api_router.get("/clinic/dashboard")
async def clinic_dashboard_stats(ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        from datetime import datetime as dt, timedelta
        now = dt.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        month_start = today_start.replace(day=1)

        # Today's appointments
        today_apts = sdb.table('appointments').select('*').eq('clinic_id', clinic_id).gte('starts_at', today_start.isoformat()).lt('starts_at', today_end.isoformat()).neq('status', 'cancelled').order('starts_at').execute()
        apts = today_apts.data or []

        pending_today = len([a for a in apts if a.get('status') in ('scheduled', 'confirmed')])

        # Next upcoming appointment
        next_apt = None
        upcoming = sdb.table('appointments').select('*').eq('clinic_id', clinic_id).gte('starts_at', now.isoformat()).neq('status', 'cancelled').order('starts_at').limit(1).execute()
        if upcoming.data:
            next_apt = upcoming.data[0]

        # New patients this month
        new_patients_month = sdb.table('patients').select('id', count='exact').eq('clinic_id', clinic_id).gte('created_at', month_start.isoformat()).execute()

        # Prescriptions issued this month
        rx_month = sdb.table('prescriptions').select('id', count='exact').eq('clinic_id', clinic_id).eq('status', 'issued').gte('issued_at', month_start.isoformat()).execute()

        # Recent patients (last 5 with completed visits)
        recent_apts = sdb.table('appointments').select('patient_id').eq('clinic_id', clinic_id).eq('status', 'completed').order('updated_at', desc=True).limit(10).execute()
        seen_ids = []
        recent_patients = []
        for ra in (recent_apts.data or []):
            pid = ra['patient_id']
            if pid not in seen_ids and len(recent_patients) < 5:
                seen_ids.append(pid)
                p = sdb.table('patients').select('id,first_name,last_name,phone').eq('id', pid).maybe_single().execute()
                if p.data:
                    recent_patients.append(p.data)

        # If not enough from completed, fill with recently created patients
        if len(recent_patients) < 5:
            extra = sdb.table('patients').select('id,first_name,last_name,phone').eq('clinic_id', clinic_id).order('created_at', desc=True).limit(5).execute()
            for p in (extra.data or []):
                if p['id'] not in seen_ids and len(recent_patients) < 5:
                    seen_ids.append(p['id'])
                    recent_patients.append(p)

        # Activity log (recent actions)
        activity = []

        # Recent appointments (created)
        recent_created_apts = sdb.table('appointments').select('id,patient_id,created_at,starts_at').eq('clinic_id', clinic_id).order('created_at', desc=True).limit(5).execute()
        for a in (recent_created_apts.data or []):
            p = sdb.table('patients').select('first_name,last_name').eq('id', a['patient_id']).maybe_single().execute()
            pname = f"{p.data['first_name']} {p.data['last_name']}" if p.data else "Paciente"
            activity.append({
                "type": "appointment",
                "message": f"Cita agendada para {pname}",
                "timestamp": a['created_at'],
            })

        # Recent prescriptions
        recent_rx = sdb.table('prescriptions').select('id,patient_id,created_at,status').eq('clinic_id', clinic_id).eq('status', 'issued').order('created_at', desc=True).limit(5).execute()
        for r in (recent_rx.data or []):
            p = sdb.table('patients').select('first_name,last_name').eq('id', r['patient_id']).maybe_single().execute()
            pname = f"{p.data['first_name']} {p.data['last_name']}" if p.data else "Paciente"
            activity.append({
                "type": "prescription",
                "message": f"Receta emitida para {pname}",
                "timestamp": r['created_at'],
            })

        # Recent patients registered
        recent_pats = sdb.table('patients').select('id,first_name,last_name,created_at').eq('clinic_id', clinic_id).order('created_at', desc=True).limit(5).execute()
        for p in (recent_pats.data or []):
            activity.append({
                "type": "patient",
                "message": f"Paciente registrado: {p['first_name']} {p['last_name']}",
                "timestamp": p['created_at'],
            })

        # Sort activity by timestamp desc, take top 10
        activity.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        activity = activity[:10]

        # Enrich today's appointments
        for apt in apts:
            p = sdb.table('patients').select('first_name,last_name').eq('id', apt["patient_id"]).maybe_single().execute()
            d = sdb.table('clinic_members').select('first_name,last_name').eq('id', apt["doctor_id"]).maybe_single().execute()
            apt["patient_name"] = f"{p.data['first_name']} {p.data['last_name']}" if p.data else ""
            apt["doctor_name"] = f"{d.data['first_name']} {d.data['last_name']}" if d.data else ""

        # Enrich next appointment
        if next_apt:
            p = sdb.table('patients').select('first_name,last_name').eq('id', next_apt["patient_id"]).maybe_single().execute()
            next_apt["patient_name"] = f"{p.data['first_name']} {p.data['last_name']}" if p.data else ""

        return {
            "today_appointments": apts,
            "today_count": len(apts),
            "pending_today": pending_today,
            "new_patients_month": new_patients_month.count or 0,
            "rx_issued_month": rx_month.count or 0,
            "next_appointment": next_apt,
            "recent_patients": recent_patients,
            "activity": activity,
            "current_member": ctx["member"],
        }
    except Exception as e:
        logger.error(f"Clinic dashboard error: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener dashboard")

# ============== GOOGLE CALENDAR INTEGRATION ==============

from cryptography.fernet import Fernet
import base64
import hashlib
from fastapi.responses import RedirectResponse

def get_fernet():
    raw_key = os.environ.get('ENCRYPTION_KEY', 'default-key-change-me')
    key = base64.urlsafe_b64encode(hashlib.sha256(raw_key.encode()).digest())
    return Fernet(key)

def encrypt_token(token: str) -> str:
    if not token: return ""
    return get_fernet().encrypt(token.encode()).decode()

def decrypt_token(encrypted: str) -> str:
    if not encrypted: return ""
    try:
        return get_fernet().decrypt(encrypted.encode()).decode()
    except Exception:
        return ""

GOOGLE_SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_google_flow():
    from google_auth_oauthlib.flow import Flow
    client_config = {
        "web": {
            "client_id": os.environ.get('GOOGLE_CLIENT_ID', ''),
            "client_secret": os.environ.get('GOOGLE_CLIENT_SECRET', ''),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [os.environ.get('GOOGLE_REDIRECT_URI', '')],
        }
    }
    flow = Flow.from_client_config(client_config, scopes=GOOGLE_SCOPES)
    flow.redirect_uri = os.environ.get('GOOGLE_REDIRECT_URI', '')
    return flow

def get_google_service(access_token: str, refresh_token: str):
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ.get('GOOGLE_CLIENT_ID', ''),
        client_secret=os.environ.get('GOOGLE_CLIENT_SECRET', ''),
        scopes=GOOGLE_SCOPES,
    )
    return build('calendar', 'v3', credentials=creds), creds

@api_router.get("/google-calendar/auth-url")
async def google_calendar_auth_url(ctx=Depends(require_clinic_member)):
    """Generate Google OAuth2 authorization URL"""
    user_id = ctx["auth_user"].id
    try:
        flow = get_google_flow()
        auth_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent',
            state=user_id,
        )
        return {"auth_url": auth_url}
    except Exception as e:
        logger.error(f"Google auth URL error: {e}")
        raise HTTPException(status_code=500, detail="Error al generar URL de autenticación")

@api_router.get("/google-calendar/callback")
async def google_calendar_callback(code: str = "", state: str = "", error: str = ""):
    """Handle Google OAuth2 callback"""
    if error:
        logger.error(f"Google callback error: {error}")
        frontend_url = os.environ.get('GOOGLE_REDIRECT_URI', '').replace('/api/google-calendar/callback', '')
        return RedirectResponse(url=f"{frontend_url}/dashboard?gcal_error=denied")

    if not code or not state:
        return RedirectResponse(url="/dashboard?gcal_error=missing_params")

    user_id = state
    try:
        flow = get_google_flow()
        flow.fetch_token(code=code)
        credentials = flow.credentials

        enc_access = encrypt_token(credentials.token)
        enc_refresh = encrypt_token(credentials.refresh_token or "")
        expires_at = credentials.expiry.isoformat() if credentials.expiry else None

        # Check if integration exists
        existing = sdb.table('user_integrations').select('id').eq('user_id', user_id).eq('provider', 'google_calendar').maybe_single().execute()

        now = now_iso()
        if existing.data:
            sdb.table('user_integrations').update({
                "access_token": enc_access,
                "refresh_token": enc_refresh,
                "token_expires_at": expires_at,
                "is_active": True,
                "calendar_id": "primary",
                "updated_at": now,
            }).eq('id', existing.data['id']).execute()
        else:
            sdb.table('user_integrations').insert({
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "provider": "google_calendar",
                "access_token": enc_access,
                "refresh_token": enc_refresh,
                "token_expires_at": expires_at,
                "is_active": True,
                "calendar_id": "primary",
                "metadata": {},
                "created_at": now,
                "updated_at": now,
            }).execute()

        frontend_url = os.environ.get('GOOGLE_REDIRECT_URI', '').replace('/api/google-calendar/callback', '')
        return RedirectResponse(url=f"{frontend_url}/dashboard?gcal_success=true")
    except Exception as e:
        logger.error(f"Google callback token error: {e}")
        return RedirectResponse(url="/dashboard?gcal_error=token_error")

@api_router.get("/google-calendar/status")
async def google_calendar_status(ctx=Depends(require_clinic_member)):
    """Check if current user has Google Calendar connected"""
    user_id = ctx["auth_user"].id
    try:
        result = sdb.table('user_integrations').select('id,is_active,calendar_id,created_at').eq('user_id', user_id).eq('provider', 'google_calendar').maybe_single().execute()
        if result.data and result.data.get('is_active'):
            return {"connected": True, "calendar_id": result.data.get('calendar_id', 'primary'), "since": result.data.get('created_at')}
        return {"connected": False}
    except Exception as e:
        logger.error(f"Google calendar status error: {e}")
        return {"connected": False}

@api_router.get("/google-calendar/calendars")
async def list_google_calendars(ctx=Depends(require_clinic_member)):
    """List available Google calendars for the user"""
    user_id = ctx["auth_user"].id
    try:
        integration = sdb.table('user_integrations').select('*').eq('user_id', user_id).eq('provider', 'google_calendar').eq('is_active', True).maybe_single().execute()
        if not integration.data:
            raise HTTPException(status_code=400, detail="Google Calendar no conectado")

        access_token = decrypt_token(integration.data.get('access_token', ''))
        refresh_token = decrypt_token(integration.data.get('refresh_token', ''))
        service, creds = get_google_service(access_token, refresh_token)

        calendar_list = service.calendarList().list().execute()
        calendars = [{"id": c['id'], "summary": c['summary'], "primary": c.get('primary', False)} for c in calendar_list.get('items', [])]

        # Update tokens if refreshed
        if creds.token != access_token:
            sdb.table('user_integrations').update({
                "access_token": encrypt_token(creds.token),
                "token_expires_at": creds.expiry.isoformat() if creds.expiry else None,
                "updated_at": now_iso(),
            }).eq('id', integration.data['id']).execute()

        return calendars
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"List calendars error: {e}")
        raise HTTPException(status_code=500, detail="Error al listar calendarios")

@api_router.put("/google-calendar/settings")
async def update_google_calendar_settings(data: dict, ctx=Depends(require_clinic_member)):
    """Update calendar selection and sync toggle"""
    user_id = ctx["auth_user"].id
    try:
        integration = sdb.table('user_integrations').select('id').eq('user_id', user_id).eq('provider', 'google_calendar').maybe_single().execute()
        if not integration.data:
            raise HTTPException(status_code=404, detail="Integración no encontrada")

        update = {"updated_at": now_iso()}
        if "calendar_id" in data:
            update["calendar_id"] = data["calendar_id"]
        if "is_active" in data:
            update["is_active"] = data["is_active"]

        sdb.table('user_integrations').update(update).eq('id', integration.data['id']).execute()
        return {"message": "Configuración actualizada"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update settings error: {e}")
        raise HTTPException(status_code=500, detail="Error al actualizar configuración")

@api_router.delete("/google-calendar/disconnect")
async def disconnect_google_calendar(ctx=Depends(require_clinic_member)):
    """Disconnect Google Calendar"""
    user_id = ctx["auth_user"].id
    try:
        sdb.table('user_integrations').update({
            "is_active": False,
            "access_token": None,
            "refresh_token": None,
            "token_expires_at": None,
            "updated_at": now_iso(),
        }).eq('user_id', user_id).eq('provider', 'google_calendar').execute()
        return {"message": "Google Calendar desconectado"}
    except Exception as e:
        logger.error(f"Disconnect error: {e}")
        raise HTTPException(status_code=500, detail="Error al desconectar")

async def sync_appointment_to_gcal(appointment_data: dict, action: str = "create"):
    """Sync an appointment to Google Calendar for the doctor"""
    try:
        doctor_id = appointment_data.get('doctor_id')
        if not doctor_id:
            return

        # Get doctor's user_id
        member = sdb.table('clinic_members').select('user_id').eq('id', doctor_id).maybe_single().execute()
        if not member.data or not member.data.get('user_id'):
            return

        user_id = member.data['user_id']

        # Check if doctor has active Google Calendar integration
        integration = sdb.table('user_integrations').select('*').eq('user_id', user_id).eq('provider', 'google_calendar').eq('is_active', True).maybe_single().execute()
        if not integration.data:
            return

        access_token = decrypt_token(integration.data.get('access_token', ''))
        refresh_token = decrypt_token(integration.data.get('refresh_token', ''))
        if not access_token:
            return

        calendar_id = integration.data.get('calendar_id') or 'primary'

        service, creds = get_google_service(access_token, refresh_token)

        # Update tokens if refreshed
        if creds.token != access_token:
            sdb.table('user_integrations').update({
                "access_token": encrypt_token(creds.token),
                "token_expires_at": creds.expiry.isoformat() if creds.expiry else None,
                "updated_at": now_iso(),
            }).eq('id', integration.data['id']).execute()

        patient_name = appointment_data.get('patient_name', 'Paciente')
        reason = appointment_data.get('reason', '')

        event_body = {
            'summary': f"Cita: {patient_name}",
            'description': f"Motivo: {reason}" if reason else "Cita médica",
            'start': {'dateTime': appointment_data.get('starts_at'), 'timeZone': 'UTC'},
            'end': {'dateTime': appointment_data.get('ends_at'), 'timeZone': 'UTC'},
        }

        if action == "create":
            event = service.events().insert(calendarId=calendar_id, body=event_body).execute()
            event_id = event.get('id')
            if event_id:
                sdb.table('appointments').update({"google_event_id": event_id}).eq('id', appointment_data['id']).execute()
            logger.info(f"Google Calendar event created: {event_id}")

        elif action == "update":
            google_event_id = appointment_data.get('google_event_id')
            if google_event_id:
                service.events().update(calendarId=calendar_id, eventId=google_event_id, body=event_body).execute()
                logger.info(f"Google Calendar event updated: {google_event_id}")

        elif action == "delete":
            google_event_id = appointment_data.get('google_event_id')
            if google_event_id:
                try:
                    service.events().delete(calendarId=calendar_id, eventId=google_event_id).execute()
                    logger.info(f"Google Calendar event deleted: {google_event_id}")
                except Exception:
                    pass

    except Exception as e:
        logger.error(f"Google Calendar sync error: {e}")

# ============== INVENTORY ROUTES ==============

# --- Product Categories ---
@api_router.get("/clinic/inventory/categories")
async def list_product_categories(ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        result = sdb.table('product_categories').select('*').eq('clinic_id', clinic_id).order('sort_order').order('name').execute()
        return result.data or []
    except Exception as e:
        logger.error(f"List categories error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@api_router.post("/clinic/inventory/categories")
async def create_product_category(data: dict, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        doc = {"id": str(uuid.uuid4()), "clinic_id": clinic_id, "name": data["name"],
               "description": data.get("description"), "parent_id": data.get("parent_id"),
               "is_active": True, "sort_order": data.get("sort_order", 0)}
        sdb.table('product_categories').insert(doc).execute()
        return {"id": doc["id"], "message": "Categoría creada"}
    except Exception as e:
        logger.error(f"Create category error: {e}")
        raise HTTPException(status_code=500, detail="Error")

# --- Products ---
@api_router.get("/clinic/inventory/products")
async def list_products(q: str = "", category_id: str = "", low_stock: str = "", page: int = 1, limit: int = 20, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        query = sdb.table('products').select('*', count='exact').eq('clinic_id', clinic_id)
        if q:
            query = query.or_(f'name.ilike.%{q}%,sku.ilike.%{q}%,barcode.ilike.%{q}%')
        if category_id:
            query = query.eq('category_id', category_id)
        offset = (page - 1) * limit
        result = query.order('name').range(offset, offset + limit - 1).execute()
        products = result.data or []
        for p in products:
            stock = sdb.table('inventory_stock').select('quantity,branch_id').eq('product_id', p['id']).execute()
            p['total_stock'] = sum(s.get('quantity', 0) for s in (stock.data or []))
            p.pop('search_vector', None)
            if p.get('category_id'):
                cat = sdb.table('product_categories').select('name').eq('id', p['category_id']).maybe_single().execute()
                cat_data = getattr(cat, 'data', None) if cat else None
                p['category_name'] = cat_data['name'] if cat_data else ''
            else:
                p['category_name'] = ''
        if low_stock == 'true':
            products = [p for p in products if p['total_stock'] <= (p.get('min_stock') or 0)]
        return {"products": products, "total": result.count or 0, "page": page, "pages": ((result.count or 0) + limit - 1) // limit}
    except Exception as e:
        logger.error(f"List products error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@api_router.post("/clinic/inventory/products")
async def create_product(data: dict, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        doc = {
            "id": str(uuid.uuid4()), "clinic_id": clinic_id,
            "sku": data.get("sku"), "barcode": data.get("barcode"), "name": data["name"],
            "description": data.get("description"), "brand": data.get("brand"),
            "presentation": data.get("presentation"), "category_id": data.get("category_id"),
            "medication_id": data.get("medication_id"),
            "cost_price": data.get("cost_price", 0), "sale_price": data.get("sale_price", 0),
            "tax_rate": data.get("tax_rate", 12), "unit": data.get("unit", "unidad"),
            "min_stock": data.get("min_stock", 0), "max_stock": data.get("max_stock"),
            "requires_prescription": data.get("requires_prescription", False),
            "has_expiration": data.get("has_expiration", False),
            "is_active": data.get("is_active", True),
        }
        sdb.table('products').insert(doc).execute()
        return {"id": doc["id"], "message": "Producto creado"}
    except Exception as e:
        logger.error(f"Create product error: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@api_router.put("/clinic/inventory/products/{product_id}")
async def update_product(product_id: str, data: dict, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        allowed = ['sku','barcode','name','description','brand','presentation','category_id','medication_id','cost_price','sale_price','tax_rate','unit','min_stock','max_stock','requires_prescription','has_expiration','is_active']
        update = {k: v for k, v in data.items() if k in allowed}
        update['updated_at'] = now_iso()
        sdb.table('products').update(update).eq('id', product_id).eq('clinic_id', clinic_id).execute()
        return {"message": "Producto actualizado"}
    except Exception as e:
        logger.error(f"Update product error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@api_router.get("/clinic/inventory/products/search")
async def search_products(q: str = "", ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        query = sdb.table('products').select('id,name,sku,brand,sale_price,cost_price,has_expiration').eq('clinic_id', clinic_id).eq('is_active', True)
        if q and len(q) >= 2:
            query = query.or_(f'name.ilike.%{q}%,sku.ilike.%{q}%')
        result = query.order('name').limit(20).execute()
        return result.data or []
    except Exception as e:
        logger.error(f"Search products error: {e}")
        raise HTTPException(status_code=500, detail="Error")

# --- Stock ---
@api_router.get("/clinic/inventory/stock")
async def list_stock(branch_id: str = "", category_id: str = "", ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        query = sdb.table('inventory_stock').select('*').eq('clinic_id', clinic_id)
        if branch_id:
            query = query.eq('branch_id', branch_id)
        result = query.execute()
        stocks = result.data or []
        for s in stocks:
            p = sdb.table('products').select('name,sku,min_stock,category_id').eq('id', s['product_id']).maybe_single().execute()
            p_data = getattr(p, 'data', None) if p else None
            if p_data:
                s['product_name'] = p_data['name']
                s['sku'] = p_data['sku']
                s['min_stock'] = p_data.get('min_stock', 0)
                s['category_id'] = p_data.get('category_id')
            else:
                s['product_name'] = '?'
                s['sku'] = ''
                s['min_stock'] = 0
            b = sdb.table('branches').select('name').eq('id', s['branch_id']).maybe_single().execute()
            b_data = getattr(b, 'data', None) if b else None
            s['branch_name'] = b_data['name'] if b_data else ''
            qty = s.get('quantity', 0)
            ms = s.get('min_stock', 0)
            s['status'] = 'critical' if qty <= 0 else ('low' if qty <= ms else 'ok')
        if category_id:
            stocks = [s for s in stocks if s.get('category_id') == category_id]
        return stocks
    except Exception as e:
        logger.error(f"List stock error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@api_router.get("/clinic/inventory/alerts")
async def get_inventory_alerts(ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        low_stock = []
        expiring = []
        # Low stock: products where any branch has qty <= min_stock
        products = sdb.table('products').select('id,name,sku,min_stock').eq('clinic_id', clinic_id).eq('is_active', True).execute()
        for p in (products.data or []):
            stocks = sdb.table('inventory_stock').select('quantity,branch_id').eq('product_id', p['id']).execute()
            for s in (stocks.data or []):
                if s.get('quantity', 0) <= (p.get('min_stock') or 0):
                    b = sdb.table('branches').select('name').eq('id', s['branch_id']).maybe_single().execute()
                    b_data = getattr(b, 'data', None) if b else None
                    low_stock.append({**p, "quantity": s['quantity'], "branch_id": s['branch_id'], "branch_name": b_data['name'] if b_data else ''})
        # Expiring: batches expiring in 60 days
        from datetime import datetime as dt, timedelta
        cutoff = (dt.now(timezone.utc) + timedelta(days=60)).isoformat()
        batches = sdb.table('inventory_batches').select('*').eq('clinic_id', clinic_id).eq('is_active', True).lt('expiration_date', cutoff).order('expiration_date').limit(20).execute()
        for b in (batches.data or []):
            p = sdb.table('products').select('name,sku').eq('id', b['product_id']).maybe_single().execute()
            p_data = getattr(p, 'data', None) if p else None
            br = sdb.table('branches').select('name').eq('id', b['branch_id']).maybe_single().execute()
            br_data = getattr(br, 'data', None) if br else None
            expiring.append({**b, "product_name": p_data['name'] if p_data else '', "sku": p_data['sku'] if p_data else '', "branch_name": br_data['name'] if br_data else ''})
        return {"low_stock": low_stock, "expiring": expiring}
    except Exception as e:
        logger.error(f"Inventory alerts error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@api_router.post("/clinic/inventory/adjust")
async def adjust_stock(data: dict, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    member = ctx["member"]
    try:
        product_id = data["product_id"]
        branch_id = data["branch_id"]
        new_qty = data["new_quantity"]
        reason = data.get("reason", "adjustment")
        notes = data.get("notes", "")
        existing_res = sdb.table('inventory_stock').select('id,quantity').eq('product_id', product_id).eq('branch_id', branch_id).maybe_single().execute()
        existing = getattr(existing_res, 'data', None) if existing_res else None
        old_qty = existing['quantity'] if existing else 0
        diff = new_qty - old_qty
        # Insert only the movement; a Postgres trigger on inventory_movements
        # automatically upserts inventory_stock by summing quantities.
        sdb.table('inventory_movements').insert({
            "id": str(uuid.uuid4()), "clinic_id": clinic_id, "product_id": product_id,
            "branch_id": branch_id, "movement_type": "adjustment", "quantity": diff,
            "notes": f"{reason}: {notes}".strip(': '), "performed_by": member["id"],
            "created_at": now_iso(),
        }).execute()
        return {"message": "Stock ajustado", "old": old_qty, "new": new_qty, "diff": diff}
    except Exception as e:
        logger.error(f"Adjust stock error: {e}")
        raise HTTPException(status_code=500, detail="Error")

# --- Movements ---
@api_router.get("/clinic/inventory/movements")
async def list_movements(product_id: str = "", branch_id: str = "", movement_type: str = "", date_from: str = "", date_to: str = "", page: int = 1, limit: int = 30, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        query = sdb.table('inventory_movements').select('*', count='exact').eq('clinic_id', clinic_id)
        if product_id: query = query.eq('product_id', product_id)
        if branch_id: query = query.eq('branch_id', branch_id)
        if movement_type: query = query.eq('movement_type', movement_type)
        if date_from: query = query.gte('created_at', date_from)
        if date_to: query = query.lte('created_at', date_to + "T23:59:59Z")
        offset = (page - 1) * limit
        result = query.order('created_at', desc=True).range(offset, offset + limit - 1).execute()
        movements = result.data or []
        for m in movements:
            p = sdb.table('products').select('name,sku').eq('id', m['product_id']).maybe_single().execute()
            p_data = getattr(p, 'data', None) if p else None
            m['product_name'] = p_data['name'] if p_data else ''
            m['sku'] = p_data.get('sku', '') if p_data else ''
            b = sdb.table('branches').select('name').eq('id', m['branch_id']).maybe_single().execute()
            b_data = getattr(b, 'data', None) if b else None
            m['branch_name'] = b_data['name'] if b_data else ''
            if m.get('performed_by'):
                mb = sdb.table('clinic_members').select('first_name,last_name').eq('id', m['performed_by']).maybe_single().execute()
                mb_data = getattr(mb, 'data', None) if mb else None
                m['performed_by_name'] = f"{mb_data['first_name']} {mb_data['last_name']}" if mb_data else ''
            else:
                m['performed_by_name'] = ''
        return {"movements": movements, "total": result.count or 0, "page": page, "pages": ((result.count or 0) + limit - 1) // limit}
    except Exception as e:
        logger.error(f"List movements error: {e}")
        raise HTTPException(status_code=500, detail="Error")

# --- Suppliers ---
@api_router.get("/clinic/inventory/suppliers")
async def list_suppliers(ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        result = sdb.table('suppliers').select('*').eq('clinic_id', clinic_id).order('name').execute()
        return result.data or []
    except Exception as e:
        logger.error(f"List suppliers error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@api_router.post("/clinic/inventory/suppliers")
async def create_supplier(data: dict, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        doc = {"id": str(uuid.uuid4()), "clinic_id": clinic_id, "name": data["name"],
               "tax_id": data.get("tax_id"), "contact_person": data.get("contact_person"),
               "phone": data.get("phone"), "email": data.get("email"),
               "address": data.get("address"), "notes": data.get("notes"), "is_active": True}
        sdb.table('suppliers').insert(doc).execute()
        return {"id": doc["id"], "message": "Proveedor creado"}
    except Exception as e:
        logger.error(f"Create supplier error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@api_router.put("/clinic/inventory/suppliers/{supplier_id}")
async def update_supplier(supplier_id: str, data: dict, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        allowed = ['name','tax_id','contact_person','phone','email','address','notes','is_active']
        update = {k: v for k, v in data.items() if k in allowed}
        sdb.table('suppliers').update(update).eq('id', supplier_id).eq('clinic_id', clinic_id).execute()
        return {"message": "Proveedor actualizado"}
    except Exception as e:
        logger.error(f"Update supplier error: {e}")
        raise HTTPException(status_code=500, detail="Error")

# --- Purchase Orders ---
@api_router.get("/clinic/inventory/purchase-orders")
async def list_purchase_orders(status: str = "", page: int = 1, limit: int = 20, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        query = sdb.table('purchase_orders').select('*', count='exact').eq('clinic_id', clinic_id)
        if status: query = query.eq('status', status)
        offset = (page - 1) * limit
        result = query.order('created_at', desc=True).range(offset, offset + limit - 1).execute()
        orders = result.data or []
        for o in orders:
            b = sdb.table('branches').select('name').eq('id', o['branch_id']).maybe_single().execute()
            b_data = getattr(b, 'data', None) if b else None
            o['branch_name'] = b_data['name'] if b_data else ''
            items = sdb.table('purchase_order_items').select('id', count='exact').eq('purchase_order_id', o['id']).execute()
            o['item_count'] = items.count or 0
        return {"orders": orders, "total": result.count or 0, "page": page, "pages": ((result.count or 0) + limit - 1) // limit}
    except Exception as e:
        logger.error(f"List POs error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@api_router.post("/clinic/inventory/purchase-orders")
async def create_purchase_order(data: dict, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    member = ctx["member"]
    try:
        now = now_iso()
        po_id = str(uuid.uuid4())
        items = data.get('items', [])
        subtotal = sum(i.get('subtotal', 0) for i in items)
        tax = subtotal * (data.get('tax_rate', 12) / 100)
        total = subtotal + tax
        status = data.get('status', 'pending')

        sdb.table('purchase_orders').insert({
            "id": po_id, "clinic_id": clinic_id, "branch_id": data["branch_id"],
            "order_number": data.get("order_number", f"PO-{now[:10]}"),
            "supplier_name": data.get("supplier_name", ""),
            "supplier_id": data.get("supplier_id"),
            "subtotal": subtotal, "tax_amount": tax, "total": total,
            "status": status, "notes": data.get("notes"),
            "created_by": member["id"], "created_at": now, "updated_at": now,
        }).execute()

        for item in items:
            sdb.table('purchase_order_items').insert({
                "id": str(uuid.uuid4()), "purchase_order_id": po_id,
                "product_id": item["product_id"], "quantity": item["quantity"],
                "unit_cost": item.get("unit_cost", 0),
                "subtotal": item.get("subtotal", item["quantity"] * item.get("unit_cost", 0)),
                "batch_number": item.get("batch_number"),
                "expiration_date": item.get("expiration_date"),
            }).execute()

        # If status is 'received', process stock entries
        if status == 'received':
            await process_po_receive(po_id, clinic_id, data["branch_id"], member["id"])

        return {"id": po_id, "message": "Orden creada"}
    except Exception as e:
        logger.error(f"Create PO error: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

async def process_po_receive(po_id: str, clinic_id: str, branch_id: str, performed_by: str):
    """Process receiving a purchase order - insert movement (trigger updates stock) and create batches"""
    items = sdb.table('purchase_order_items').select('*').eq('purchase_order_id', po_id).execute()
    for item in (items.data or []):
        pid = item['product_id']
        qty = item['quantity']
        # Insert movement; Postgres trigger on inventory_movements upserts inventory_stock automatically.
        sdb.table('inventory_movements').insert({
            "id": str(uuid.uuid4()), "clinic_id": clinic_id, "product_id": pid,
            "branch_id": branch_id, "movement_type": "purchase",
            "quantity": qty, "unit_cost": item.get('unit_cost'),
            "reference_type": "purchase_order", "reference_id": po_id,
            "performed_by": performed_by, "created_at": now_iso(),
        }).execute()
        # Create batch if has expiration
        if item.get('expiration_date') or item.get('batch_number'):
            sdb.table('inventory_batches').insert({
                "id": str(uuid.uuid4()), "clinic_id": clinic_id, "product_id": pid,
                "branch_id": branch_id, "batch_number": item.get('batch_number', ''),
                "quantity": qty, "expiration_date": item.get('expiration_date'),
                "cost_price": item.get('unit_cost'), "received_at": now_iso(), "is_active": True,
            }).execute()
    # Mark PO as received
    sdb.table('purchase_orders').update({"status": "received", "received_at": now_iso(), "updated_at": now_iso()}).eq('id', po_id).execute()

# ============== BRANCH ROUTES ==============

class BranchCreate(BaseModel):
    name: str
    code: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    schedule_start: Optional[str] = None
    schedule_end: Optional[str] = None
    is_main: bool = False
    is_active: bool = True

@api_router.get("/clinic/branches")
async def list_branches(ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        result = sdb.table('branches').select('*').eq('clinic_id', clinic_id).order('is_main', desc=True).order('name').execute()
        branches = result.data or []
        for b in branches:
            mb = sdb.table('member_branches').select('member_id', count='exact').eq('branch_id', b['id']).execute()
            b['member_count'] = mb.count or 0
        return branches
    except Exception as e:
        logger.error(f"List branches error: {e}")
        raise HTTPException(status_code=500, detail="Error al listar sucursales")

@api_router.post("/clinic/branches")
async def create_branch(data: BranchCreate, ctx=Depends(require_clinic_member)):
    if ctx["member"]["role"] != "clinic_admin":
        raise HTTPException(status_code=403, detail="Solo administradores")
    clinic_id = ctx["member"]["clinic_id"]
    try:
        clinic = sdb.table('clinics').select('plan,max_users').eq('id', clinic_id).single().execute()
        plan_code = clinic.data.get('plan', 'basic')
        plan = sdb.table('plans').select('max_branches').eq('code', plan_code).maybe_single().execute()
        max_branches = plan.data.get('max_branches', 1) if plan.data else 1
        current = sdb.table('branches').select('id', count='exact').eq('clinic_id', clinic_id).execute()
        if (current.count or 0) >= max_branches:
            raise HTTPException(status_code=400, detail=f"Has alcanzado el límite de sucursales de tu plan ({max_branches}). Actualiza a un plan superior.")

        now = now_iso()
        branch_id = str(uuid.uuid4())
        if data.is_main:
            sdb.table('branches').update({"is_main": False, "updated_at": now}).eq('clinic_id', clinic_id).eq('is_main', True).execute()
        doc = {
            "id": branch_id, "clinic_id": clinic_id,
            "name": data.name, "code": data.code,
            "address": data.address, "city": data.city, "state": data.state,
            "phone": data.phone, "email": data.email,
            "schedule_start": data.schedule_start, "schedule_end": data.schedule_end,
            "is_main": data.is_main, "is_active": data.is_active,
            "created_at": now, "updated_at": now,
        }
        sdb.table('branches').insert(doc).execute()
        return {"id": branch_id, "message": "Sucursal creada"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create branch error: {e}")
        raise HTTPException(status_code=500, detail="Error al crear sucursal")

@api_router.put("/clinic/branches/{branch_id}")
async def update_branch(branch_id: str, data: BranchCreate, ctx=Depends(require_clinic_member)):
    if ctx["member"]["role"] != "clinic_admin":
        raise HTTPException(status_code=403, detail="Solo administradores")
    clinic_id = ctx["member"]["clinic_id"]
    try:
        now = now_iso()
        if data.is_main:
            sdb.table('branches').update({"is_main": False, "updated_at": now}).eq('clinic_id', clinic_id).eq('is_main', True).execute()
        update = {k: v for k, v in data.model_dump().items() if v is not None}
        update["updated_at"] = now
        sdb.table('branches').update(update).eq('id', branch_id).eq('clinic_id', clinic_id).execute()
        return {"message": "Sucursal actualizada"}
    except Exception as e:
        logger.error(f"Update branch error: {e}")
        raise HTTPException(status_code=500, detail="Error al actualizar sucursal")

@api_router.get("/clinic/branches/{branch_id}/members")
async def list_branch_members(branch_id: str, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        mb = sdb.table('member_branches').select('member_id,is_primary').eq('branch_id', branch_id).execute()
        assigned = {r['member_id']: r['is_primary'] for r in (mb.data or [])}
        all_members = sdb.table('clinic_members').select('id,first_name,last_name,role,is_active').eq('clinic_id', clinic_id).eq('is_active', True).execute()
        result = []
        for m in (all_members.data or []):
            result.append({**m, "assigned": m['id'] in assigned, "is_primary": assigned.get(m['id'], False)})
        return result
    except Exception as e:
        logger.error(f"List branch members error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@api_router.put("/clinic/branches/{branch_id}/members")
async def set_branch_members(branch_id: str, data: dict, ctx=Depends(require_clinic_member)):
    if ctx["member"]["role"] != "clinic_admin":
        raise HTTPException(status_code=403, detail="Solo administradores")
    try:
        members = data.get('members', [])
        sdb.table('member_branches').delete().eq('branch_id', branch_id).execute()
        for m in members:
            sdb.table('member_branches').insert({
                "branch_id": branch_id, "member_id": m['member_id'],
                "is_primary": m.get('is_primary', False),
            }).execute()
        return {"message": "Miembros actualizados"}
    except Exception as e:
        logger.error(f"Set branch members error: {e}")
        raise HTTPException(status_code=500, detail="Error")

# ============== FEATURE FLAGS ROUTES ==============

@api_router.get("/clinic/features")
async def get_clinic_features(ctx=Depends(require_clinic_member)):
    """Get all active features for the current clinic (plan + overrides)"""
    clinic_id = ctx["member"]["clinic_id"]
    try:
        clinic = sdb.table('clinics').select('plan').eq('id', clinic_id).single().execute()
        plan_code = clinic.data.get('plan', 'basic')

        plan = sdb.table('plans').select('id').eq('code', plan_code).maybe_single().execute()
        plan_features = []
        if plan.data:
            pf = sdb.table('plan_features').select('feature_id').eq('plan_id', plan.data['id']).execute()
            plan_feature_ids = [r['feature_id'] for r in (pf.data or [])]
            if plan_feature_ids:
                feats = sdb.table('features').select('code').in_('id', plan_feature_ids).eq('is_active', True).execute()
                plan_features = [f['code'] for f in (feats.data or [])]

        overrides = sdb.table('clinic_feature_overrides').select('feature_id,is_enabled').eq('clinic_id', clinic_id).execute()
        override_map = {}
        if overrides.data:
            feat_ids = [o['feature_id'] for o in overrides.data]
            if feat_ids:
                feats = sdb.table('features').select('id,code').in_('id', feat_ids).execute()
                id_to_code = {f['id']: f['code'] for f in (feats.data or [])}
                for o in overrides.data:
                    code = id_to_code.get(o['feature_id'])
                    if code:
                        override_map[code] = o['is_enabled']

        all_features = set(plan_features)
        for code, enabled in override_map.items():
            if enabled:
                all_features.add(code)
            else:
                all_features.discard(code)

        return {"features": sorted(all_features), "plan": plan_code}
    except Exception as e:
        logger.error(f"Get clinic features error: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener features")

# --- ADMIN: Plans management ---

@api_router.get("/admin/plans")
async def admin_list_plans(user=Depends(require_super_admin)):
    try:
        plans = sdb.table('plans').select('*').order('sort_order').execute()
        return plans.data or []
    except Exception as e:
        logger.error(f"List plans error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@api_router.put("/admin/plans/{plan_id}")
async def admin_update_plan(plan_id: str, data: dict, user=Depends(require_super_admin)):
    try:
        allowed = ['name', 'description', 'price_monthly', 'price_yearly', 'max_users', 'max_patients', 'max_storage_mb', 'max_branches']
        update = {k: v for k, v in data.items() if k in allowed and v is not None}
        update['updated_at'] = now_iso()
        sdb.table('plans').update(update).eq('id', plan_id).execute()
        return {"message": "Plan actualizado"}
    except Exception as e:
        logger.error(f"Update plan error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@api_router.get("/admin/features")
async def admin_list_features(user=Depends(require_super_admin)):
    try:
        features = sdb.table('features').select('*').order('category').order('sort_order').execute()
        return features.data or []
    except Exception as e:
        logger.error(f"List features error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@api_router.get("/admin/plans/{plan_id}/features")
async def admin_get_plan_features(plan_id: str, user=Depends(require_super_admin)):
    try:
        pf = sdb.table('plan_features').select('feature_id').eq('plan_id', plan_id).execute()
        return [r['feature_id'] for r in (pf.data or [])]
    except Exception as e:
        logger.error(f"Get plan features error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@api_router.put("/admin/plans/{plan_id}/features")
async def admin_set_plan_features(plan_id: str, data: dict, user=Depends(require_super_admin)):
    """Set features for a plan (replaces all)"""
    try:
        feature_ids = data.get('feature_ids', [])
        sdb.table('plan_features').delete().eq('plan_id', plan_id).execute()
        for fid in feature_ids:
            sdb.table('plan_features').insert({"plan_id": plan_id, "feature_id": fid}).execute()
        return {"message": "Features actualizados"}
    except Exception as e:
        logger.error(f"Set plan features error: {e}")
        raise HTTPException(status_code=500, detail="Error")

# --- ADMIN: Clinic feature overrides ---

@api_router.get("/admin/clinics/{clinic_id}/features")
async def admin_get_clinic_features(clinic_id: str, user=Depends(require_super_admin)):
    try:
        clinic = sdb.table('clinics').select('plan').eq('id', clinic_id).single().execute()
        plan_code = clinic.data.get('plan', 'basic')
        plan = sdb.table('plans').select('id').eq('code', plan_code).maybe_single().execute()

        plan_feature_ids = []
        if plan.data:
            pf = sdb.table('plan_features').select('feature_id').eq('plan_id', plan.data['id']).execute()
            plan_feature_ids = [r['feature_id'] for r in (pf.data or [])]

        all_features = sdb.table('features').select('*').order('category').order('sort_order').execute()
        overrides = sdb.table('clinic_feature_overrides').select('feature_id,is_enabled').eq('clinic_id', clinic_id).execute()
        override_map = {o['feature_id']: o['is_enabled'] for o in (overrides.data or [])}

        result = []
        for f in (all_features.data or []):
            result.append({
                **f,
                "in_plan": f['id'] in plan_feature_ids,
                "override": override_map.get(f['id']),
            })
        return {"features": result, "plan": plan_code, "plan_feature_ids": plan_feature_ids}
    except Exception as e:
        logger.error(f"Get clinic features admin error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@api_router.put("/admin/clinics/{clinic_id}/features/{feature_id}")
async def admin_toggle_clinic_feature(clinic_id: str, feature_id: str, data: dict, user=Depends(require_super_admin)):
    """Toggle a feature override for a clinic"""
    try:
        is_enabled = data.get('is_enabled')
        if is_enabled is None:
            sdb.table('clinic_feature_overrides').delete().eq('clinic_id', clinic_id).eq('feature_id', feature_id).execute()
            return {"message": "Override eliminado"}
        existing = sdb.table('clinic_feature_overrides').select('id').eq('clinic_id', clinic_id).eq('feature_id', feature_id).maybe_single().execute()
        if existing and existing.data:
            sdb.table('clinic_feature_overrides').update({"is_enabled": is_enabled}).eq('id', existing.data['id']).execute()
        else:
            sdb.table('clinic_feature_overrides').insert({
                "clinic_id": clinic_id, "feature_id": feature_id, "is_enabled": is_enabled,
            }).execute()
        return {"message": "Override actualizado"}
    except Exception as e:
        logger.error(f"Toggle clinic feature error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@api_router.put("/admin/clinics/{clinic_id}/plan")
async def admin_change_clinic_plan(clinic_id: str, data: dict, user=Depends(require_super_admin)):
    """Change a clinic's plan"""
    try:
        plan_code = data.get('plan')
        if not plan_code:
            raise HTTPException(status_code=400, detail="Plan requerido")
        plan = sdb.table('plans').select('id,max_users,max_patients,max_storage_mb,max_branches').eq('code', plan_code).maybe_single().execute()
        if not plan.data:
            raise HTTPException(status_code=404, detail="Plan no encontrado")
        sdb.table('clinics').update({
            "plan": plan_code,
            "max_users": plan.data['max_users'],
            "max_patients": plan.data['max_patients'],
            "max_storage_mb": plan.data['max_storage_mb'],
            "updated_at": now_iso(),
        }).eq('id', clinic_id).execute()
        return {"message": "Plan actualizado"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Change clinic plan error: {e}")
        raise HTTPException(status_code=500, detail="Error")

# ============== UTILITY ROUTES ==============

@api_router.get("/")
async def root():
    return {"message": "Clinic CRM Super Admin API"}

# ============== SALES / POS ROUTES ==============

# --- Services CRUD ---
@api_router.get("/clinic/sales/services")
async def list_services(q: str = "", category: str = "", active_only: bool = False, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        query = sdb.table('services').select('*').eq('clinic_id', clinic_id)
        if active_only:
            query = query.eq('is_active', True)
        if category:
            query = query.eq('category', category)
        if q:
            query = query.or_(f'name.ilike.%{q}%,code.ilike.%{q}%')
        result = query.order('name').execute()
        return result.data or []
    except Exception as e:
        logger.error(f"List services error: {e}")
        raise HTTPException(status_code=500, detail="Error al listar servicios")

@api_router.post("/clinic/sales/services")
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

@api_router.put("/clinic/sales/services/{service_id}")
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
@api_router.get("/clinic/sales/cash-registers")
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

@api_router.post("/clinic/sales/cash-registers")
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
@api_router.get("/clinic/sales/cash-session/current")
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

@api_router.post("/clinic/sales/cash-session/open")
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

@api_router.post("/clinic/sales/cash-session/{session_id}/close")
async def close_cash_session(session_id: str, data: dict, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    member_id = ctx["member"]["id"]
    actual_amount = float(data.get("actual_amount", 0))
    try:
        session = sdb.table('cash_sessions').select('*').eq('id', session_id).eq('clinic_id', clinic_id).single().execute().data
        if session['status'] != 'open':
            raise HTTPException(status_code=400, detail="Sesión ya cerrada")
        # Calculate expected = opening + sum of cash payments during this session
        opening = float(session.get('opening_amount') or 0)
        sales_in_session = sdb.table('sales').select('id').eq('cash_session_id', session_id).neq('status', 'cancelled').execute()
        sale_ids = [s['id'] for s in (sales_in_session.data or [])]
        cash_total = 0.0
        if sale_ids:
            pays = sdb.table('payments').select('amount,payment_method').in_('sale_id', sale_ids).eq('payment_method', 'cash').execute()
            cash_total = sum(float(p.get('amount') or 0) for p in (pays.data or []))
        expected = opening + cash_total
        difference = actual_amount - expected
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

@api_router.get("/clinic/sales/cash-session/{session_id}/summary")
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
        opening = float(session.get('opening_amount') or 0)
        expected = opening + totals['cash']
        return {
            "session": session,
            "opening": opening,
            "totals": totals,
            "expected": expected,
            "sales_count": len(sale_ids),
            "sales_total": sum(float(s.get('total') or 0) for s in (sales_in.data or [])),
        }
    except Exception as e:
        logger.error(f"Cash session summary error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@api_router.get("/clinic/sales/cash-sessions")
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

@api_router.post("/clinic/sales")
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
    valid_methods = {"cash", "credit_card", "debit_card", "transfer", "credit", "check", "other"}
    for p in payments:
        m = p.get("payment_method")
        if m and m not in valid_methods:
            raise HTTPException(status_code=400, detail=f"Método de pago inválido: {m}")
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
                        "quantity": -qty, "unit_cost": unit,
                        "reference_type": "sale", "reference_id": sale_id,
                        "performed_by": member["id"], "created_at": now,
                    }).execute()

            # Insert payments
            for p in payments:
                amt = float(p.get("amount") or 0)
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
            logger.error(f"Sale post-insert failed, rolling back {sale_id}: {inner_e}")
            try: sdb.table('payments').delete().eq('sale_id', sale_id).execute()
            except Exception: pass
            try: sdb.table('inventory_movements').delete().eq('reference_id', sale_id).eq('reference_type', 'sale').execute()
            except Exception: pass
            try: sdb.table('sale_items').delete().eq('sale_id', sale_id).execute()
            except Exception: pass
            try: sdb.table('sales').delete().eq('id', sale_id).execute()
            except Exception: pass
            raise HTTPException(status_code=500, detail=f"Error al registrar venta: {str(inner_e)}")

        # If amount_due > 0 → also create accounts_receivable record (best-effort; ignore if table missing)
        if amount_due > 0:
            try:
                from datetime import datetime as dt, timedelta
                due_default = (dt.now(timezone.utc) + timedelta(days=30)).date().isoformat()
                sdb.table('accounts_receivable').insert({
                    "id": str(uuid.uuid4()), "clinic_id": clinic_id, "sale_id": sale_id,
                    "patient_id": data.get("patient_id"),
                    "original_amount": total, "paid_amount": amount_paid, "balance": amount_due,
                    "due_date": data.get("ar_due_date") or due_default,
                    "status": "pending",
                    "has_payment_plan": False, "installments": 0,
                    "created_at": now, "updated_at": now,
                }).execute()
            except Exception as _e:
                logger.warning(f"AR create skipped: {_e}")

        # Generate receipt PDF (best-effort)
        try:
            await generate_sale_pdf(sale_id, clinic_id)
        except Exception as _e:
            logger.warning(f"Receipt PDF generation failed: {_e}")

        return {"id": sale_id, "sale_number": sale_number, "total": total, "amount_due": amount_due, "payment_status": payment_status}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create sale error: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@api_router.get("/clinic/sales")
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
        # Enrich
        for s in sales:
            cb = sdb.table('clinic_members').select('first_name,last_name').eq('id', s['cashier_id']).maybe_single().execute() if s.get('cashier_id') else None
            cb_data = getattr(cb, 'data', None) if cb else None
            s['cashier_name'] = f"{cb_data['first_name']} {cb_data['last_name']}" if cb_data else ''
            br = sdb.table('branches').select('name').eq('id', s['branch_id']).maybe_single().execute() if s.get('branch_id') else None
            br_data = getattr(br, 'data', None) if br else None
            s['branch_name'] = br_data['name'] if br_data else ''
            items = sdb.table('sale_items').select('description').eq('sale_id', s['id']).limit(3).execute()
            descs = [i.get('description') or '—' for i in (items.data or [])]
            s['items_summary'] = ', '.join(descs[:2]) + (f' +{len(descs)-2} más' if len(descs) > 2 else '')
            pays = sdb.table('payments').select('payment_method').eq('sale_id', s['id']).execute()
            methods = list({p['payment_method'] for p in (pays.data or [])})
            s['payment_methods'] = methods
        # Optional filter by payment_method (post-fetch since payments are separate)
        if payment_method:
            sales = [s for s in sales if payment_method in (s.get('payment_methods') or [])]
        return {"sales": sales, "total": result.count or 0, "page": page, "pages": ((result.count or 0) + limit - 1) // limit}
    except Exception as e:
        logger.error(f"List sales error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@api_router.get("/clinic/sales/daily-summary")
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

@api_router.get("/clinic/sales/{sale_id}")
async def get_sale(sale_id: str, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        sale = sdb.table('sales').select('*').eq('id', sale_id).eq('clinic_id', clinic_id).single().execute().data
        items = sdb.table('sale_items').select('*').eq('sale_id', sale_id).order('sort_order').execute().data or []
        pays = sdb.table('payments').select('*').eq('sale_id', sale_id).order('paid_at').execute().data or []
        sale['items'] = items
        sale['payments'] = pays
        if sale.get('cashier_id'):
            cb = sdb.table('clinic_members').select('first_name,last_name').eq('id', sale['cashier_id']).maybe_single().execute()
            cb_data = getattr(cb, 'data', None) if cb else None
            sale['cashier_name'] = f"{cb_data['first_name']} {cb_data['last_name']}" if cb_data else ''
        return sale
    except Exception as e:
        logger.error(f"Get sale error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@api_router.post("/clinic/sales/{sale_id}/cancel")
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

@api_router.get("/clinic/sales/{sale_id}/pdf-url")
async def get_sale_pdf_url(sale_id: str, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        sale = sdb.table('sales').select('id').eq('id', sale_id).eq('clinic_id', clinic_id).maybe_single().execute()
        sale_data = getattr(sale, 'data', None) if sale else None
        if not sale_data:
            raise HTTPException(status_code=404, detail="Venta no encontrada")
        path = f"{clinic_id}/sales/{sale_id}.pdf"
        try:
            signed = supabase_admin.storage.from_('patient-files').create_signed_url(path, 3600)
            return {"url": signed.get('signedURL') or signed.get('signedUrl', '')}
        except Exception:
            # Try regenerating
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
        clinic = sdb.table('clinics').select('name,address,city,phone,email').eq('id', clinic_id).single().execute().data
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
        signed = supabase_admin.storage.from_('patient-files').create_signed_url(path, 86400)
        url = signed.get('signedURL') or signed.get('signedUrl', '')
        sdb.table('sales').update({"pdf_url": url, "updated_at": now_iso()}).eq('id', sale_id).execute()
        return url
    except Exception as e:
        logger.error(f"Generate sale PDF error: {e}")
        return None


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

@api_router.get("/clinic/accounts-receivable/dashboard")
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

@api_router.get("/clinic/accounts-receivable/aging")
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

@api_router.get("/clinic/accounts-receivable/installments")
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

@api_router.get("/clinic/accounts-receivable")
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

@api_router.get("/clinic/accounts-receivable/{ar_id}")
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

@api_router.post("/clinic/accounts-receivable/{ar_id}/payment")
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

@api_router.post("/clinic/accounts-receivable/{ar_id}/payment-plan")
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


@api_router.get("/health")
async def health():
    return {"status": "healthy"}

@api_router.post("/generate-password")
async def api_generate_password(user=Depends(require_super_admin)):
    return {"password": generate_password()}

# Include the router
app.include_router(api_router)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)
