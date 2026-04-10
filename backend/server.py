from fastapi import FastAPI, APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from supabase import create_client, Client
import os
import logging
import secrets
import string
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from pydantic_settings import BaseSettings
from typing import List, Optional
import uuid
from datetime import datetime, timezone
from jose import JWTError, jwt

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Settings
class Settings(BaseSettings):
    supabase_url: str = os.environ.get('SUPABASE_URL', '')
    supabase_anon_key: str = os.environ.get('SUPABASE_ANON_KEY', '')
    supabase_service_role_key: str = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
    mongo_url: str = os.environ.get('MONGO_URL', '')
    db_name: str = os.environ.get('DB_NAME', '')
    super_admin_email: str = os.environ.get('SUPER_ADMIN_EMAIL', '')
    super_admin_password: str = os.environ.get('SUPER_ADMIN_PASSWORD', '')

settings = Settings()

# MongoDB connection
client = AsyncIOMotorClient(settings.mongo_url)
db = client[settings.db_name]

# Supabase clients
supabase_user: Client = create_client(settings.supabase_url, settings.supabase_anon_key)
supabase_admin: Client = create_client(settings.supabase_url, settings.supabase_service_role_key)

# Create the main app
app = FastAPI(title="Clinic CRM Super Admin API")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Security
security = HTTPBearer()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
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

class Clinic(BaseModel):
    id: str
    name: str
    slug: str
    country: str
    city: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    timezone: Optional[str] = None
    plan: str
    is_active: bool
    created_at: str
    updated_at: str

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
    presentations: Optional[List[str]] = []
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

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        # Verify with Supabase
        response = supabase_admin.auth.get_user(token)
        if response and response.user:
            return response.user
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        logger.error(f"Token validation error: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")

async def require_super_admin(user = Depends(get_current_user)):
    super_admin = await db.super_admins.find_one({"user_id": user.id}, {"_id": 0})
    if not super_admin:
        raise HTTPException(status_code=403, detail="Super admin access required")
    return user

# ============== INITIALIZATION ==============

@app.on_event("startup")
async def startup_event():
    """Initialize super admin on startup"""
    try:
        # Check if super admin exists
        existing = await db.super_admins.find_one({"email": settings.super_admin_email})
        if not existing:
            # Create super admin in Supabase Auth
            try:
                response = supabase_admin.auth.admin.create_user({
                    "email": settings.super_admin_email,
                    "password": settings.super_admin_password,
                    "email_confirm": True
                })
                if response.user:
                    # Store in super_admins collection
                    await db.super_admins.insert_one({
                        "id": str(uuid.uuid4()),
                        "user_id": response.user.id,
                        "email": settings.super_admin_email,
                        "created_at": datetime.now(timezone.utc).isoformat()
                    })
                    logger.info(f"Super admin created: {settings.super_admin_email}")
            except Exception as e:
                # User might already exist in Supabase, try to get them
                logger.warning(f"Could not create super admin in Supabase: {e}")
                try:
                    users = supabase_admin.auth.admin.list_users()
                    for u in users:
                        if u.email == settings.super_admin_email:
                            await db.super_admins.insert_one({
                                "id": str(uuid.uuid4()),
                                "user_id": u.id,
                                "email": settings.super_admin_email,
                                "created_at": datetime.now(timezone.utc).isoformat()
                            })
                            logger.info(f"Super admin linked: {settings.super_admin_email}")
                            break
                except Exception as e2:
                    logger.error(f"Error linking super admin: {e2}")
    except Exception as e:
        logger.error(f"Startup error: {e}")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

# ============== AUTH ROUTES ==============

@api_router.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    try:
        # Authenticate with Supabase
        response = supabase_user.auth.sign_in_with_password({
            "email": request.email,
            "password": request.password
        })
        
        if not response.session:
            raise HTTPException(status_code=401, detail="Credenciales inválidas")
        
        user_id = response.user.id
        
        # Check user type
        super_admin = await db.super_admins.find_one({"user_id": user_id}, {"_id": 0})
        if super_admin:
            return LoginResponse(
                access_token=response.session.access_token,
                refresh_token=response.session.refresh_token,
                user_type="super_admin",
                user_id=user_id,
                email=request.email
            )
        
        clinic_member = await db.clinic_members.find_one({"user_id": user_id, "is_active": True}, {"_id": 0})
        if clinic_member:
            return LoginResponse(
                access_token=response.session.access_token,
                refresh_token=response.session.refresh_token,
                user_type="clinic_member",
                user_id=user_id,
                email=request.email,
                clinic_id=clinic_member.get("clinic_id")
            )
        
        # User not in any table
        raise HTTPException(status_code=403, detail="No tienes acceso al sistema")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=401, detail="Error de autenticación")

@api_router.post("/auth/logout")
async def logout(user = Depends(get_current_user)):
    try:
        supabase_user.auth.sign_out()
        return {"message": "Sesión cerrada correctamente"}
    except Exception as e:
        logger.error(f"Logout error: {e}")
        return {"message": "Sesión cerrada"}

# ============== DASHBOARD ROUTES ==============

@api_router.get("/admin/dashboard")
async def get_dashboard_stats(user = Depends(require_super_admin)):
    try:
        active_clinics = await db.clinics.count_documents({"is_active": True})
        inactive_clinics = await db.clinics.count_documents({"is_active": False})
        total_users = await db.clinic_members.count_documents({})
        total_patients = await db.patients.count_documents({})
        
        # Recent clinics
        recent_clinics = await db.clinics.find({}, {"_id": 0}).sort("created_at", -1).limit(10).to_list(10)
        
        # Add user and patient counts per clinic
        for clinic in recent_clinics:
            clinic["users_count"] = await db.clinic_members.count_documents({"clinic_id": clinic["id"]})
            clinic["patients_count"] = await db.patients.count_documents({"clinic_id": clinic["id"]})
        
        return {
            "active_clinics": active_clinics,
            "inactive_clinics": inactive_clinics,
            "total_users": total_users,
            "total_patients": total_patients,
            "recent_clinics": recent_clinics
        }
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener estadísticas")

# ============== CLINIC ROUTES ==============

@api_router.get("/admin/clinics")
async def list_clinics(
    search: Optional[str] = None,
    country: Optional[str] = None,
    plan: Optional[str] = None,
    status: Optional[str] = None,
    user = Depends(require_super_admin)
):
    try:
        query = {}
        if search:
            query["name"] = {"$regex": search, "$options": "i"}
        if country:
            query["country"] = country
        if plan:
            query["plan"] = plan
        if status:
            query["is_active"] = status == "active"
        
        clinics = await db.clinics.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
        
        # Add counts
        for clinic in clinics:
            clinic["users_count"] = await db.clinic_members.count_documents({"clinic_id": clinic["id"]})
            clinic["patients_count"] = await db.patients.count_documents({"clinic_id": clinic["id"]})
        
        return clinics
    except Exception as e:
        logger.error(f"List clinics error: {e}")
        raise HTTPException(status_code=500, detail="Error al listar clínicas")

@api_router.post("/admin/clinics")
async def create_clinic(data: ClinicCreate, user = Depends(require_super_admin)):
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
        now = datetime.now(timezone.utc).isoformat()
        
        clinic_doc = {
            "id": clinic_id,
            "name": data.name,
            "slug": generate_slug(data.name),
            "country": data.country,
            "city": data.city,
            "address": data.address,
            "phone": data.phone,
            "email": data.email,
            "timezone": data.timezone,
            "plan": data.plan,
            "is_active": True,
            "created_at": now,
            "updated_at": now
        }
        
        await db.clinics.insert_one(clinic_doc)
        
        # 3. Create clinic member
        member_doc = {
            "id": str(uuid.uuid4()),
            "user_id": admin_user_id,
            "clinic_id": clinic_id,
            "name": data.admin_name,
            "lastname": data.admin_lastname,
            "email": data.admin_email,
            "phone": data.admin_phone,
            "role": "clinic_admin",
            "is_active": True,
            "created_at": now,
            "updated_at": now,
            "last_login": None
        }
        
        await db.clinic_members.insert_one(member_doc)
        
        # Remove _id from response
        if "_id" in clinic_doc:
            del clinic_doc["_id"]
        
        return {
            "message": "Clínica creada exitosamente",
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
        raise HTTPException(status_code=500, detail="Error al crear clínica")

@api_router.get("/admin/clinics/{clinic_id}")
async def get_clinic(clinic_id: str, user = Depends(require_super_admin)):
    try:
        clinic = await db.clinics.find_one({"id": clinic_id}, {"_id": 0})
        if not clinic:
            raise HTTPException(status_code=404, detail="Clínica no encontrada")
        
        # Get members
        members = await db.clinic_members.find({"clinic_id": clinic_id}, {"_id": 0}).to_list(1000)
        
        # Get stats
        stats = {
            "total_patients": await db.patients.count_documents({"clinic_id": clinic_id}),
            "total_appointments": await db.appointments.count_documents({"clinic_id": clinic_id}),
            "total_prescriptions": await db.prescriptions.count_documents({"clinic_id": clinic_id}),
            "members_count": len(members)
        }
        
        # Get activity log
        activity = await db.activity_logs.find({"clinic_id": clinic_id}, {"_id": 0}).sort("created_at", -1).limit(20).to_list(20)
        
        return {
            "clinic": clinic,
            "members": members,
            "stats": stats,
            "activity": activity
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get clinic error: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener clínica")

@api_router.put("/admin/clinics/{clinic_id}")
async def update_clinic(clinic_id: str, data: ClinicUpdate, user = Depends(require_super_admin)):
    try:
        clinic = await db.clinics.find_one({"id": clinic_id})
        if not clinic:
            raise HTTPException(status_code=404, detail="Clínica no encontrada")
        
        update_data = {k: v for k, v in data.model_dump().items() if v is not None}
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        if "name" in update_data:
            update_data["slug"] = generate_slug(update_data["name"])
        
        await db.clinics.update_one({"id": clinic_id}, {"$set": update_data})
        
        updated = await db.clinics.find_one({"id": clinic_id}, {"_id": 0})
        return updated
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update clinic error: {e}")
        raise HTTPException(status_code=500, detail="Error al actualizar clínica")

@api_router.post("/admin/clinics/{clinic_id}/members")
async def add_clinic_member(clinic_id: str, data: ClinicMemberCreate, user = Depends(require_super_admin)):
    try:
        clinic = await db.clinics.find_one({"id": clinic_id})
        if not clinic:
            raise HTTPException(status_code=404, detail="Clínica no encontrada")
        
        # Create user in Supabase
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
        
        now = datetime.now(timezone.utc).isoformat()
        member_doc = {
            "id": str(uuid.uuid4()),
            "user_id": new_user_id,
            "clinic_id": clinic_id,
            "name": data.name,
            "lastname": data.lastname,
            "email": data.email,
            "phone": data.phone,
            "role": data.role,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
            "last_login": None
        }
        
        await db.clinic_members.insert_one(member_doc)
        
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
    user = Depends(require_super_admin)
):
    try:
        query = {}
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"lastname": {"$regex": search, "$options": "i"}},
                {"email": {"$regex": search, "$options": "i"}}
            ]
        if clinic_id:
            query["clinic_id"] = clinic_id
        if role:
            query["role"] = role
        if status:
            query["is_active"] = status == "active"
        
        users = await db.clinic_members.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
        
        # Add clinic name
        for u in users:
            clinic = await db.clinics.find_one({"id": u.get("clinic_id")}, {"_id": 0, "name": 1})
            u["clinic_name"] = clinic["name"] if clinic else "N/A"
        
        return users
    except Exception as e:
        logger.error(f"List users error: {e}")
        raise HTTPException(status_code=500, detail="Error al listar usuarios")

@api_router.put("/admin/users/{member_id}")
async def update_user(member_id: str, data: UserUpdate, user = Depends(require_super_admin)):
    try:
        member = await db.clinic_members.find_one({"id": member_id})
        if not member:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        update_data = {k: v for k, v in data.model_dump().items() if v is not None}
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        await db.clinic_members.update_one({"id": member_id}, {"$set": update_data})
        
        updated = await db.clinic_members.find_one({"id": member_id}, {"_id": 0})
        return updated
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update user error: {e}")
        raise HTTPException(status_code=500, detail="Error al actualizar usuario")

@api_router.post("/admin/users/{member_id}/reset-password")
async def reset_user_password(member_id: str, user = Depends(require_super_admin)):
    try:
        member = await db.clinic_members.find_one({"id": member_id}, {"_id": 0})
        if not member:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        new_password = generate_password()
        
        # Update in Supabase
        try:
            supabase_admin.auth.admin.update_user_by_id(
                member["user_id"],
                {"password": new_password}
            )
        except Exception as e:
            logger.error(f"Reset password error: {e}")
            raise HTTPException(status_code=400, detail="Error al resetear contraseña")
        
        return {
            "message": "Contraseña reseteada exitosamente",
            "new_password": new_password
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reset password error: {e}")
        raise HTTPException(status_code=500, detail="Error al resetear contraseña")

# ============== CATALOG ROUTES ==============

# Medications
@api_router.get("/admin/catalogs/medications")
async def list_medications(user = Depends(require_super_admin)):
    meds = await db.medications.find({"clinic_id": None}, {"_id": 0}).to_list(1000)
    return meds

@api_router.post("/admin/catalogs/medications")
async def create_medication(data: MedicationCreate, user = Depends(require_super_admin)):
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": str(uuid.uuid4()),
        "clinic_id": None,
        "generic_name": data.generic_name,
        "brand_name": data.brand_name,
        "presentations": data.presentations,
        "category": data.category,
        "is_active": True,
        "created_at": now,
        "updated_at": now
    }
    await db.medications.insert_one(doc)
    if "_id" in doc:
        del doc["_id"]
    return doc

@api_router.put("/admin/catalogs/medications/{med_id}")
async def update_medication(med_id: str, data: MedicationCreate, user = Depends(require_super_admin)):
    update_data = data.model_dump()
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.medications.update_one({"id": med_id}, {"$set": update_data})
    updated = await db.medications.find_one({"id": med_id}, {"_id": 0})
    return updated

@api_router.delete("/admin/catalogs/medications/{med_id}")
async def deactivate_medication(med_id: str, user = Depends(require_super_admin)):
    await db.medications.update_one({"id": med_id}, {"$set": {"is_active": False}})
    return {"message": "Medicamento desactivado"}

@api_router.post("/admin/catalogs/medications/bulk")
async def bulk_import_medications(data: MedicationBulkImport, user = Depends(require_super_admin)):
    now = datetime.now(timezone.utc).isoformat()
    imported = 0
    errors = []
    
    for med in data.medications:
        try:
            doc = {
                "id": str(uuid.uuid4()),
                "clinic_id": None,
                "generic_name": med.generic_name,
                "brand_name": med.brand_name,
                "presentations": med.presentations or [],
                "category": med.category,
                "is_active": True,
                "created_at": now,
                "updated_at": now
            }
            await db.medications.insert_one(doc)
            imported += 1
        except Exception as e:
            errors.append(f"{med.generic_name}: {str(e)}")
    
    return {"imported": imported, "errors": errors, "total": len(data.medications)}

# Lab Studies
@api_router.get("/admin/catalogs/lab-studies")
async def list_lab_studies(user = Depends(require_super_admin)):
    studies = await db.lab_studies.find({"clinic_id": None}, {"_id": 0}).to_list(1000)
    return studies

@api_router.post("/admin/catalogs/lab-studies")
async def create_lab_study(data: LabStudyCreate, user = Depends(require_super_admin)):
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": str(uuid.uuid4()),
        "clinic_id": None,
        "name": data.name,
        "category": data.category,
        "preparation": data.preparation,
        "is_active": True,
        "created_at": now,
        "updated_at": now
    }
    await db.lab_studies.insert_one(doc)
    if "_id" in doc:
        del doc["_id"]
    return doc

@api_router.put("/admin/catalogs/lab-studies/{study_id}")
async def update_lab_study(study_id: str, data: LabStudyCreate, user = Depends(require_super_admin)):
    update_data = data.model_dump()
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.lab_studies.update_one({"id": study_id}, {"$set": update_data})
    updated = await db.lab_studies.find_one({"id": study_id}, {"_id": 0})
    return updated

@api_router.delete("/admin/catalogs/lab-studies/{study_id}")
async def deactivate_lab_study(study_id: str, user = Depends(require_super_admin)):
    await db.lab_studies.update_one({"id": study_id}, {"$set": {"is_active": False}})
    return {"message": "Estudio desactivado"}

@api_router.post("/admin/catalogs/lab-studies/bulk")
async def bulk_import_lab_studies(data: LabStudyBulkImport, user = Depends(require_super_admin)):
    now = datetime.now(timezone.utc).isoformat()
    imported = 0
    errors = []
    
    for study in data.studies:
        try:
            doc = {
                "id": str(uuid.uuid4()),
                "clinic_id": None,
                "name": study.name,
                "category": study.category,
                "preparation": study.preparation,
                "is_active": True,
                "created_at": now,
                "updated_at": now
            }
            await db.lab_studies.insert_one(doc)
            imported += 1
        except Exception as e:
            errors.append(f"{study.name}: {str(e)}")
    
    return {"imported": imported, "errors": errors, "total": len(data.studies)}

# ICD-10 Codes
@api_router.get("/admin/catalogs/icd10")
async def list_icd10_codes(user = Depends(require_super_admin)):
    codes = await db.icd10_codes.find({}, {"_id": 0}).to_list(1000)
    return codes

@api_router.post("/admin/catalogs/icd10")
async def create_icd10_code(data: ICD10CodeCreate, user = Depends(require_super_admin)):
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": str(uuid.uuid4()),
        "code": data.code,
        "description_es": data.description_es,
        "category": data.category,
        "is_common": data.is_common,
        "created_at": now,
        "updated_at": now
    }
    await db.icd10_codes.insert_one(doc)
    if "_id" in doc:
        del doc["_id"]
    return doc

@api_router.put("/admin/catalogs/icd10/{code_id}")
async def update_icd10_code(code_id: str, data: ICD10CodeCreate, user = Depends(require_super_admin)):
    update_data = data.model_dump()
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.icd10_codes.update_one({"id": code_id}, {"$set": update_data})
    updated = await db.icd10_codes.find_one({"id": code_id}, {"_id": 0})
    return updated

@api_router.put("/admin/catalogs/icd10/{code_id}/toggle-common")
async def toggle_icd10_common(code_id: str, user = Depends(require_super_admin)):
    code = await db.icd10_codes.find_one({"id": code_id})
    if not code:
        raise HTTPException(status_code=404, detail="Código no encontrado")
    
    new_value = not code.get("is_common", False)
    await db.icd10_codes.update_one({"id": code_id}, {"$set": {"is_common": new_value}})
    return {"is_common": new_value}

@api_router.post("/admin/catalogs/icd10/bulk")
async def bulk_import_icd10(data: ICD10BulkImport, user = Depends(require_super_admin)):
    now = datetime.now(timezone.utc).isoformat()
    imported = 0
    errors = []
    
    for code in data.codes:
        try:
            # Check if code already exists
            existing = await db.icd10_codes.find_one({"code": code.code})
            if existing:
                errors.append(f"{code.code}: Ya existe")
                continue
                
            doc = {
                "id": str(uuid.uuid4()),
                "code": code.code,
                "description_es": code.description_es,
                "category": code.category,
                "is_common": code.is_common,
                "created_at": now,
                "updated_at": now
            }
            await db.icd10_codes.insert_one(doc)
            imported += 1
        except Exception as e:
            errors.append(f"{code.code}: {str(e)}")
    
    return {"imported": imported, "errors": errors, "total": len(data.codes)}

# ============== UTILITY ROUTES ==============

@api_router.get("/")
async def root():
    return {"message": "Clinic CRM Super Admin API"}

@api_router.get("/health")
async def health():
    return {"status": "healthy"}

@api_router.post("/generate-password")
async def api_generate_password(user = Depends(require_super_admin)):
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
