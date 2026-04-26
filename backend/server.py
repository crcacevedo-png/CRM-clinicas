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

# === Routes moved to routes/auth.py ===
# === Routes moved to routes/super_admin.py ===
# === Routes moved to routes/catalogs.py ===
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

# === Routes moved to routes/clinic_settings.py ===
# === Routes moved to routes/appointments.py ===
# === Routes moved to routes/patients.py ===
# === Routes moved to routes/medical_records.py ===
# === Routes moved to routes/prescriptions.py ===
# === Routes moved to routes/lab_orders.py ===
# === Routes moved to routes/patients.py ===

# === Routes moved to routes/appointments.py ===

# === Routes moved to routes/google_calendar.py ===
# === Routes moved to routes/branches.py ===
# === Routes moved to routes/feature_flags.py ===
# ============== UTILITY ROUTES ==============

@api_router.get("/")
async def root():
    return {"message": "Clinic CRM Super Admin API"}

# === Routes moved to routes/sales.py ===
# === Routes moved to routes/accounts_receivable.py ===
# === Routes moved to routes/expenses.py ===
# === Routes moved to routes/commissions.py ===
# === Routes moved to routes/reports.py ===
@api_router.get("/health")
async def health():
    return {"status": "healthy"}

@api_router.post("/generate-password")
async def api_generate_password(user=Depends(require_super_admin)):
    return {"password": generate_password()}

# Include the router

# === Refactored route modules (Phase 1 + 2) ===
# Imported here (after all shared symbols are defined) to avoid circular imports.
from routes import (
    auth as _r_auth,
    super_admin as _r_sa,
    catalogs as _r_cat,
    clinic_settings as _r_cs,
    branches as _r_br,
    feature_flags as _r_ff,
    patients as _r_pat,
    appointments as _r_apt,
    medical_records as _r_mr,
    prescriptions as _r_pr,
    lab_orders as _r_lab,
    google_calendar as _r_gc,
    inventory as _r_inv,
    expenses as _r_exp,
    commissions as _r_comm,
    sales as _r_sales,
    accounts_receivable as _r_ar,
    reports as _r_rep,
)
for _r in (
    _r_auth, _r_sa, _r_cat, _r_cs, _r_br, _r_ff,
    _r_pat, _r_apt, _r_mr, _r_pr, _r_lab, _r_gc,
    _r_inv, _r_exp, _r_comm, _r_sales, _r_ar, _r_rep,
):
    api_router.include_router(_r.router)

app.include_router(api_router)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)
