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

# ============== PATIENT FILE ROUTES ==============

from fastapi import UploadFile, File

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
