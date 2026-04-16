from fastapi import FastAPI, APIRouter, HTTPException, Depends
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
        ends = starts + timedelta(minutes=data.duration_minutes)

        # Validate clinic hours
        clinic = sdb.table('clinics').select('schedule_start,schedule_end,working_days,timezone').eq('id', clinic_id).single().execute()
        c = clinic.data

        start_time = starts.strftime("%H:%M:%S")
        end_time = ends.strftime("%H:%M:%S")
        day_of_week = starts.isoweekday()

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
            starts = dt.fromisoformat(update_data["starts_at"].replace('Z', '+00:00'))
            dur = update_data.get("duration_minutes", existing.data["duration_minutes"])
            ends = starts + timedelta(minutes=dur)
            update_data["ends_at"] = ends.isoformat()

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
            result = sdb.table('patients').select('id,first_name,last_name,phone,national_id').eq('clinic_id', clinic_id).eq('is_active', True).or_(f'first_name.ilike.%{q}%,last_name.ilike.%{q}%,national_id.ilike.%{q}%').limit(20).execute()
        return result.data or []
    except Exception as e:
        logger.error(f"Search patients error: {e}")
        raise HTTPException(status_code=500, detail="Error al buscar pacientes")

@api_router.post("/clinic/patients")
async def quick_create_patient(data: PatientQuickCreate, ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        now = now_iso()
        patient_id = str(uuid.uuid4())
        doc = {
            "id": patient_id,
            "clinic_id": clinic_id,
            "first_name": data.first_name,
            "last_name": data.last_name,
            "phone": data.phone or "",
            "email": data.email or "",
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
        if data.date_of_birth:
            doc["date_of_birth"] = data.date_of_birth
        if data.gender:
            doc["gender"] = data.gender
        if data.national_id:
            doc["national_id"] = data.national_id

        sdb.table('patients').insert(doc).execute()
        return {"id": patient_id, "first_name": data.first_name, "last_name": data.last_name}
    except Exception as e:
        logger.error(f"Create patient error: {e}")
        raise HTTPException(status_code=500, detail="Error al crear paciente")

@api_router.get("/clinic/patients")
async def list_patients(q: str = "", ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        query = sdb.table('patients').select('id,first_name,last_name,phone,email,national_id,date_of_birth,gender,is_active,created_at').eq('clinic_id', clinic_id)
        if q:
            query = query.or_(f'first_name.ilike.%{q}%,last_name.ilike.%{q}%,national_id.ilike.%{q}%')
        result = query.order('first_name').limit(100).execute()
        return result.data or []
    except Exception as e:
        logger.error(f"List patients error: {e}")
        raise HTTPException(status_code=500, detail="Error al listar pacientes")

@api_router.get("/clinic/dashboard")
async def clinic_dashboard_stats(ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        from datetime import datetime as dt, timedelta
        today_start = dt.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        today_apts = sdb.table('appointments').select('*').eq('clinic_id', clinic_id).gte('starts_at', today_start.isoformat()).lt('starts_at', today_end.isoformat()).neq('status', 'cancelled').order('starts_at').execute()

        total_patients = sdb.table('patients').select('id', count='exact').eq('clinic_id', clinic_id).execute()
        total_apts_month = sdb.table('appointments').select('id', count='exact').eq('clinic_id', clinic_id).gte('starts_at', today_start.replace(day=1).isoformat()).execute()

        apts = today_apts.data or []
        # Enrich
        for apt in apts:
            p = sdb.table('patients').select('first_name,last_name').eq('id', apt["patient_id"]).maybe_single().execute()
            d = sdb.table('clinic_members').select('first_name,last_name').eq('id', apt["doctor_id"]).maybe_single().execute()
            apt["patient_name"] = f"{p.data['first_name']} {p.data['last_name']}" if p.data else ""
            apt["doctor_name"] = f"{d.data['first_name']} {d.data['last_name']}" if d.data else ""

        return {
            "today_appointments": apts,
            "today_count": len(apts),
            "total_patients": total_patients.count or 0,
            "month_appointments": total_apts_month.count or 0,
            "current_member": ctx["member"],
        }
    except Exception as e:
        logger.error(f"Clinic dashboard error: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener dashboard")

# ============== UTILITY ROUTES ==============

@api_router.get("/")
async def root():
    return {"message": "Clinic CRM Super Admin API"}

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
