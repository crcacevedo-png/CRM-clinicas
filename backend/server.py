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

@api_router.post("/admin/catalogs/icd10/seed")
async def seed_icd10_codes(user = Depends(require_super_admin)):
    """Precarga códigos CIE-10 comunes"""
    now = datetime.now(timezone.utc).isoformat()
    
    # Lista completa de códigos CIE-10 comunes en medicina general
    icd10_codes = [
        # ENFERMEDADES INFECCIOSAS Y PARASITARIAS (A00-B99)
        {"code": "A09", "description_es": "Diarrea y gastroenteritis de presunto origen infeccioso", "category": "Infecciosas", "is_common": True},
        {"code": "A09.0", "description_es": "Gastroenteritis y colitis de origen infeccioso", "category": "Infecciosas", "is_common": True},
        {"code": "A15", "description_es": "Tuberculosis respiratoria", "category": "Infecciosas", "is_common": False},
        {"code": "A37", "description_es": "Tos ferina", "category": "Infecciosas", "is_common": False},
        {"code": "A38", "description_es": "Escarlatina", "category": "Infecciosas", "is_common": False},
        {"code": "A49.9", "description_es": "Infección bacteriana no especificada", "category": "Infecciosas", "is_common": True},
        {"code": "A60", "description_es": "Infección anogenital por virus del herpes", "category": "Infecciosas", "is_common": False},
        {"code": "A63.0", "description_es": "Verrugas anogenitales (venéreas)", "category": "Infecciosas", "is_common": False},
        {"code": "A64", "description_es": "Enfermedad de transmisión sexual no especificada", "category": "Infecciosas", "is_common": False},
        {"code": "B00", "description_es": "Infecciones herpéticas (herpes simple)", "category": "Infecciosas", "is_common": True},
        {"code": "B01", "description_es": "Varicela", "category": "Infecciosas", "is_common": True},
        {"code": "B02", "description_es": "Herpes zóster", "category": "Infecciosas", "is_common": True},
        {"code": "B05", "description_es": "Sarampión", "category": "Infecciosas", "is_common": False},
        {"code": "B06", "description_es": "Rubéola", "category": "Infecciosas", "is_common": False},
        {"code": "B07", "description_es": "Verrugas víricas", "category": "Infecciosas", "is_common": True},
        {"code": "B08.1", "description_es": "Molusco contagioso", "category": "Infecciosas", "is_common": True},
        {"code": "B15", "description_es": "Hepatitis aguda tipo A", "category": "Infecciosas", "is_common": False},
        {"code": "B16", "description_es": "Hepatitis aguda tipo B", "category": "Infecciosas", "is_common": False},
        {"code": "B17.1", "description_es": "Hepatitis aguda tipo C", "category": "Infecciosas", "is_common": False},
        {"code": "B18.1", "description_es": "Hepatitis viral tipo B crónica", "category": "Infecciosas", "is_common": False},
        {"code": "B18.2", "description_es": "Hepatitis viral tipo C crónica", "category": "Infecciosas", "is_common": False},
        {"code": "B26", "description_es": "Parotiditis infecciosa (paperas)", "category": "Infecciosas", "is_common": False},
        {"code": "B27", "description_es": "Mononucleosis infecciosa", "category": "Infecciosas", "is_common": True},
        {"code": "B34.9", "description_es": "Infección viral no especificada", "category": "Infecciosas", "is_common": True},
        {"code": "B35", "description_es": "Dermatofitosis (tiña)", "category": "Infecciosas", "is_common": True},
        {"code": "B35.0", "description_es": "Tiña de la cabeza y de la barba", "category": "Infecciosas", "is_common": True},
        {"code": "B35.1", "description_es": "Tiña de las uñas", "category": "Infecciosas", "is_common": True},
        {"code": "B35.3", "description_es": "Tiña del pie (pie de atleta)", "category": "Infecciosas", "is_common": True},
        {"code": "B35.4", "description_es": "Tiña del cuerpo", "category": "Infecciosas", "is_common": True},
        {"code": "B36.0", "description_es": "Pitiriasis versicolor", "category": "Infecciosas", "is_common": True},
        {"code": "B37", "description_es": "Candidiasis", "category": "Infecciosas", "is_common": True},
        {"code": "B37.0", "description_es": "Estomatitis candidiásica (muguet oral)", "category": "Infecciosas", "is_common": True},
        {"code": "B37.3", "description_es": "Candidiasis de la vulva y vagina", "category": "Infecciosas", "is_common": True},
        {"code": "B76", "description_es": "Anquilostomiasis y necatoriasis", "category": "Infecciosas", "is_common": False},
        {"code": "B77", "description_es": "Ascariasis", "category": "Infecciosas", "is_common": True},
        {"code": "B80", "description_es": "Enterobiasis (oxiuriasis)", "category": "Infecciosas", "is_common": True},
        {"code": "B82.9", "description_es": "Parasitosis intestinal no especificada", "category": "Infecciosas", "is_common": True},
        {"code": "B85", "description_es": "Pediculosis y phthiriasis (piojos)", "category": "Infecciosas", "is_common": True},
        {"code": "B86", "description_es": "Escabiosis (sarna)", "category": "Infecciosas", "is_common": True},
        
        # NEOPLASIAS (C00-D48)
        {"code": "C18", "description_es": "Tumor maligno del colon", "category": "Neoplasias", "is_common": False},
        {"code": "C34", "description_es": "Tumor maligno del pulmón", "category": "Neoplasias", "is_common": False},
        {"code": "C50", "description_es": "Tumor maligno de la mama", "category": "Neoplasias", "is_common": False},
        {"code": "C53", "description_es": "Tumor maligno del cuello del útero", "category": "Neoplasias", "is_common": False},
        {"code": "C61", "description_es": "Tumor maligno de la próstata", "category": "Neoplasias", "is_common": False},
        {"code": "D17", "description_es": "Lipoma", "category": "Neoplasias", "is_common": True},
        {"code": "D22", "description_es": "Nevo melanocítico (lunar)", "category": "Neoplasias", "is_common": True},
        {"code": "D25", "description_es": "Leiomioma del útero (mioma)", "category": "Neoplasias", "is_common": True},
        
        # ENFERMEDADES DE LA SANGRE (D50-D89)
        {"code": "D50", "description_es": "Anemia por deficiencia de hierro", "category": "Sangre", "is_common": True},
        {"code": "D50.9", "description_es": "Anemia ferropénica no especificada", "category": "Sangre", "is_common": True},
        {"code": "D51", "description_es": "Anemia por deficiencia de vitamina B12", "category": "Sangre", "is_common": True},
        {"code": "D52", "description_es": "Anemia por deficiencia de folatos", "category": "Sangre", "is_common": True},
        {"code": "D64.9", "description_es": "Anemia no especificada", "category": "Sangre", "is_common": True},
        {"code": "D69.6", "description_es": "Trombocitopenia no especificada", "category": "Sangre", "is_common": False},
        
        # ENFERMEDADES ENDOCRINAS, NUTRICIONALES Y METABÓLICAS (E00-E90)
        {"code": "E03", "description_es": "Hipotiroidismo", "category": "Endocrinas", "is_common": True},
        {"code": "E03.9", "description_es": "Hipotiroidismo no especificado", "category": "Endocrinas", "is_common": True},
        {"code": "E04", "description_es": "Bocio no tóxico", "category": "Endocrinas", "is_common": True},
        {"code": "E04.1", "description_es": "Nódulo tiroideo solitario no tóxico", "category": "Endocrinas", "is_common": True},
        {"code": "E04.2", "description_es": "Bocio multinodular no tóxico", "category": "Endocrinas", "is_common": True},
        {"code": "E05", "description_es": "Tirotoxicosis (hipertiroidismo)", "category": "Endocrinas", "is_common": True},
        {"code": "E06", "description_es": "Tiroiditis", "category": "Endocrinas", "is_common": True},
        {"code": "E10", "description_es": "Diabetes mellitus tipo 1", "category": "Endocrinas", "is_common": True},
        {"code": "E11", "description_es": "Diabetes mellitus tipo 2", "category": "Endocrinas", "is_common": True},
        {"code": "E11.9", "description_es": "Diabetes mellitus tipo 2 sin complicaciones", "category": "Endocrinas", "is_common": True},
        {"code": "E13", "description_es": "Otros tipos especificados de diabetes mellitus", "category": "Endocrinas", "is_common": False},
        {"code": "E14", "description_es": "Diabetes mellitus no especificada", "category": "Endocrinas", "is_common": True},
        {"code": "E16.2", "description_es": "Hipoglucemia no especificada", "category": "Endocrinas", "is_common": True},
        {"code": "E34.9", "description_es": "Trastorno endocrino no especificado", "category": "Endocrinas", "is_common": False},
        {"code": "E44", "description_es": "Desnutrición proteico-calórica", "category": "Endocrinas", "is_common": True},
        {"code": "E46", "description_es": "Desnutrición proteico-calórica no especificada", "category": "Endocrinas", "is_common": True},
        {"code": "E53.8", "description_es": "Deficiencia de otras vitaminas del grupo B", "category": "Endocrinas", "is_common": True},
        {"code": "E55", "description_es": "Deficiencia de vitamina D", "category": "Endocrinas", "is_common": True},
        {"code": "E55.9", "description_es": "Deficiencia de vitamina D no especificada", "category": "Endocrinas", "is_common": True},
        {"code": "E56.1", "description_es": "Deficiencia de vitamina K", "category": "Endocrinas", "is_common": False},
        {"code": "E61.1", "description_es": "Deficiencia de hierro", "category": "Endocrinas", "is_common": True},
        {"code": "E63.9", "description_es": "Deficiencia nutricional no especificada", "category": "Endocrinas", "is_common": True},
        {"code": "E66", "description_es": "Obesidad", "category": "Endocrinas", "is_common": True},
        {"code": "E66.0", "description_es": "Obesidad debida a exceso de calorías", "category": "Endocrinas", "is_common": True},
        {"code": "E66.9", "description_es": "Obesidad no especificada", "category": "Endocrinas", "is_common": True},
        {"code": "E78", "description_es": "Trastornos del metabolismo de lipoproteínas", "category": "Endocrinas", "is_common": True},
        {"code": "E78.0", "description_es": "Hipercolesterolemia pura", "category": "Endocrinas", "is_common": True},
        {"code": "E78.1", "description_es": "Hipertrigliceridemia pura", "category": "Endocrinas", "is_common": True},
        {"code": "E78.2", "description_es": "Hiperlipidemia mixta", "category": "Endocrinas", "is_common": True},
        {"code": "E78.5", "description_es": "Hiperlipidemia no especificada", "category": "Endocrinas", "is_common": True},
        {"code": "E79.0", "description_es": "Hiperuricemia", "category": "Endocrinas", "is_common": True},
        {"code": "E83.5", "description_es": "Trastornos del metabolismo del calcio", "category": "Endocrinas", "is_common": False},
        {"code": "E86", "description_es": "Deshidratación", "category": "Endocrinas", "is_common": True},
        {"code": "E87.6", "description_es": "Hipopotasemia", "category": "Endocrinas", "is_common": True},
        
        # TRASTORNOS MENTALES Y DEL COMPORTAMIENTO (F00-F99)
        {"code": "F10", "description_es": "Trastornos mentales por uso de alcohol", "category": "Salud Mental", "is_common": True},
        {"code": "F10.1", "description_es": "Uso nocivo de alcohol", "category": "Salud Mental", "is_common": True},
        {"code": "F10.2", "description_es": "Síndrome de dependencia del alcohol", "category": "Salud Mental", "is_common": True},
        {"code": "F17", "description_es": "Trastornos mentales por uso de tabaco", "category": "Salud Mental", "is_common": True},
        {"code": "F17.1", "description_es": "Uso nocivo de tabaco", "category": "Salud Mental", "is_common": True},
        {"code": "F17.2", "description_es": "Dependencia del tabaco", "category": "Salud Mental", "is_common": True},
        {"code": "F19", "description_es": "Trastornos por uso de múltiples drogas", "category": "Salud Mental", "is_common": False},
        {"code": "F20", "description_es": "Esquizofrenia", "category": "Salud Mental", "is_common": False},
        {"code": "F31", "description_es": "Trastorno afectivo bipolar", "category": "Salud Mental", "is_common": True},
        {"code": "F32", "description_es": "Episodio depresivo", "category": "Salud Mental", "is_common": True},
        {"code": "F32.0", "description_es": "Episodio depresivo leve", "category": "Salud Mental", "is_common": True},
        {"code": "F32.1", "description_es": "Episodio depresivo moderado", "category": "Salud Mental", "is_common": True},
        {"code": "F32.2", "description_es": "Episodio depresivo grave sin síntomas psicóticos", "category": "Salud Mental", "is_common": True},
        {"code": "F32.9", "description_es": "Episodio depresivo no especificado", "category": "Salud Mental", "is_common": True},
        {"code": "F33", "description_es": "Trastorno depresivo recurrente", "category": "Salud Mental", "is_common": True},
        {"code": "F34.1", "description_es": "Distimia", "category": "Salud Mental", "is_common": True},
        {"code": "F40", "description_es": "Trastornos de ansiedad fóbica", "category": "Salud Mental", "is_common": True},
        {"code": "F40.0", "description_es": "Agorafobia", "category": "Salud Mental", "is_common": True},
        {"code": "F40.1", "description_es": "Fobias sociales", "category": "Salud Mental", "is_common": True},
        {"code": "F40.2", "description_es": "Fobias específicas", "category": "Salud Mental", "is_common": True},
        {"code": "F41", "description_es": "Otros trastornos de ansiedad", "category": "Salud Mental", "is_common": True},
        {"code": "F41.0", "description_es": "Trastorno de pánico", "category": "Salud Mental", "is_common": True},
        {"code": "F41.1", "description_es": "Trastorno de ansiedad generalizada", "category": "Salud Mental", "is_common": True},
        {"code": "F41.2", "description_es": "Trastorno mixto ansioso-depresivo", "category": "Salud Mental", "is_common": True},
        {"code": "F41.9", "description_es": "Trastorno de ansiedad no especificado", "category": "Salud Mental", "is_common": True},
        {"code": "F42", "description_es": "Trastorno obsesivo-compulsivo", "category": "Salud Mental", "is_common": True},
        {"code": "F43", "description_es": "Reacciones al estrés grave y trastornos de adaptación", "category": "Salud Mental", "is_common": True},
        {"code": "F43.0", "description_es": "Reacción al estrés agudo", "category": "Salud Mental", "is_common": True},
        {"code": "F43.1", "description_es": "Trastorno de estrés postraumático", "category": "Salud Mental", "is_common": True},
        {"code": "F43.2", "description_es": "Trastornos de adaptación", "category": "Salud Mental", "is_common": True},
        {"code": "F45", "description_es": "Trastornos somatomorfos", "category": "Salud Mental", "is_common": True},
        {"code": "F45.0", "description_es": "Trastorno de somatización", "category": "Salud Mental", "is_common": True},
        {"code": "F48.0", "description_es": "Neurastenia", "category": "Salud Mental", "is_common": True},
        {"code": "F50.0", "description_es": "Anorexia nerviosa", "category": "Salud Mental", "is_common": True},
        {"code": "F50.2", "description_es": "Bulimia nerviosa", "category": "Salud Mental", "is_common": True},
        {"code": "F51", "description_es": "Trastornos no orgánicos del sueño", "category": "Salud Mental", "is_common": True},
        {"code": "F51.0", "description_es": "Insomnio no orgánico", "category": "Salud Mental", "is_common": True},
        {"code": "F52", "description_es": "Disfunción sexual no orgánica", "category": "Salud Mental", "is_common": True},
        {"code": "F52.0", "description_es": "Ausencia o pérdida del deseo sexual", "category": "Salud Mental", "is_common": True},
        {"code": "F90", "description_es": "Trastornos hipercinéticos (TDAH)", "category": "Salud Mental", "is_common": True},
        {"code": "F90.0", "description_es": "Trastorno de la actividad y de la atención", "category": "Salud Mental", "is_common": True},
        
        # ENFERMEDADES DEL SISTEMA NERVIOSO (G00-G99)
        {"code": "G20", "description_es": "Enfermedad de Parkinson", "category": "Neurológicas", "is_common": True},
        {"code": "G25.0", "description_es": "Temblor esencial", "category": "Neurológicas", "is_common": True},
        {"code": "G30", "description_es": "Enfermedad de Alzheimer", "category": "Neurológicas", "is_common": True},
        {"code": "G35", "description_es": "Esclerosis múltiple", "category": "Neurológicas", "is_common": False},
        {"code": "G40", "description_es": "Epilepsia", "category": "Neurológicas", "is_common": True},
        {"code": "G40.9", "description_es": "Epilepsia no especificada", "category": "Neurológicas", "is_common": True},
        {"code": "G43", "description_es": "Migraña", "category": "Neurológicas", "is_common": True},
        {"code": "G43.0", "description_es": "Migraña sin aura", "category": "Neurológicas", "is_common": True},
        {"code": "G43.1", "description_es": "Migraña con aura", "category": "Neurológicas", "is_common": True},
        {"code": "G43.9", "description_es": "Migraña no especificada", "category": "Neurológicas", "is_common": True},
        {"code": "G44", "description_es": "Otros síndromes de cefalea", "category": "Neurológicas", "is_common": True},
        {"code": "G44.2", "description_es": "Cefalea tensional", "category": "Neurológicas", "is_common": True},
        {"code": "G45", "description_es": "Ataques de isquemia cerebral transitoria", "category": "Neurológicas", "is_common": True},
        {"code": "G47", "description_es": "Trastornos del sueño", "category": "Neurológicas", "is_common": True},
        {"code": "G47.0", "description_es": "Trastornos del inicio y mantenimiento del sueño (insomnio)", "category": "Neurológicas", "is_common": True},
        {"code": "G47.3", "description_es": "Apnea del sueño", "category": "Neurológicas", "is_common": True},
        {"code": "G50.0", "description_es": "Neuralgia del trigémino", "category": "Neurológicas", "is_common": True},
        {"code": "G51.0", "description_es": "Parálisis de Bell (parálisis facial)", "category": "Neurológicas", "is_common": True},
        {"code": "G54.0", "description_es": "Trastornos del plexo braquial", "category": "Neurológicas", "is_common": True},
        {"code": "G56.0", "description_es": "Síndrome del túnel carpiano", "category": "Neurológicas", "is_common": True},
        {"code": "G57.1", "description_es": "Meralgia parestésica", "category": "Neurológicas", "is_common": True},
        {"code": "G62.9", "description_es": "Polineuropatía no especificada", "category": "Neurológicas", "is_common": True},
        {"code": "G81", "description_es": "Hemiplejía", "category": "Neurológicas", "is_common": False},
        
        # ENFERMEDADES DEL OJO Y SUS ANEXOS (H00-H59)
        {"code": "H00.0", "description_es": "Orzuelo y chalazión", "category": "Oftalmológicas", "is_common": True},
        {"code": "H01.0", "description_es": "Blefaritis", "category": "Oftalmológicas", "is_common": True},
        {"code": "H04.0", "description_es": "Dacrioadenitis", "category": "Oftalmológicas", "is_common": False},
        {"code": "H10", "description_es": "Conjuntivitis", "category": "Oftalmológicas", "is_common": True},
        {"code": "H10.0", "description_es": "Conjuntivitis mucopurulenta", "category": "Oftalmológicas", "is_common": True},
        {"code": "H10.1", "description_es": "Conjuntivitis atópica aguda", "category": "Oftalmológicas", "is_common": True},
        {"code": "H10.3", "description_es": "Conjuntivitis aguda no especificada", "category": "Oftalmológicas", "is_common": True},
        {"code": "H10.4", "description_es": "Conjuntivitis crónica", "category": "Oftalmológicas", "is_common": True},
        {"code": "H11.0", "description_es": "Pterigión", "category": "Oftalmológicas", "is_common": True},
        {"code": "H16", "description_es": "Queratitis", "category": "Oftalmológicas", "is_common": True},
        {"code": "H25", "description_es": "Catarata senil", "category": "Oftalmológicas", "is_common": True},
        {"code": "H26", "description_es": "Otras cataratas", "category": "Oftalmológicas", "is_common": True},
        {"code": "H35.3", "description_es": "Degeneración macular", "category": "Oftalmológicas", "is_common": True},
        {"code": "H40", "description_es": "Glaucoma", "category": "Oftalmológicas", "is_common": True},
        {"code": "H40.1", "description_es": "Glaucoma primario de ángulo abierto", "category": "Oftalmológicas", "is_common": True},
        {"code": "H52", "description_es": "Trastornos de la refracción y de la acomodación", "category": "Oftalmológicas", "is_common": True},
        {"code": "H52.0", "description_es": "Hipermetropía", "category": "Oftalmológicas", "is_common": True},
        {"code": "H52.1", "description_es": "Miopía", "category": "Oftalmológicas", "is_common": True},
        {"code": "H52.2", "description_es": "Astigmatismo", "category": "Oftalmológicas", "is_common": True},
        {"code": "H52.4", "description_es": "Presbicia", "category": "Oftalmológicas", "is_common": True},
        {"code": "H53.9", "description_es": "Alteración visual no especificada", "category": "Oftalmológicas", "is_common": True},
        {"code": "H57.1", "description_es": "Dolor ocular", "category": "Oftalmológicas", "is_common": True},
        
        # ENFERMEDADES DEL OÍDO (H60-H95)
        {"code": "H60", "description_es": "Otitis externa", "category": "Otológicas", "is_common": True},
        {"code": "H60.3", "description_es": "Otitis externa infecciosa", "category": "Otológicas", "is_common": True},
        {"code": "H61.2", "description_es": "Cerumen impactado", "category": "Otológicas", "is_common": True},
        {"code": "H65", "description_es": "Otitis media no supurativa", "category": "Otológicas", "is_common": True},
        {"code": "H65.0", "description_es": "Otitis media aguda serosa", "category": "Otológicas", "is_common": True},
        {"code": "H66", "description_es": "Otitis media supurativa", "category": "Otológicas", "is_common": True},
        {"code": "H66.0", "description_es": "Otitis media aguda supurativa", "category": "Otológicas", "is_common": True},
        {"code": "H66.9", "description_es": "Otitis media no especificada", "category": "Otológicas", "is_common": True},
        {"code": "H81.0", "description_es": "Enfermedad de Ménière", "category": "Otológicas", "is_common": True},
        {"code": "H81.1", "description_es": "Vértigo paroxístico benigno", "category": "Otológicas", "is_common": True},
        {"code": "H81.3", "description_es": "Otros vértigos periféricos", "category": "Otológicas", "is_common": True},
        {"code": "H81.9", "description_es": "Trastorno de la función vestibular no especificado", "category": "Otológicas", "is_common": True},
        {"code": "H83.0", "description_es": "Laberintitis", "category": "Otológicas", "is_common": True},
        {"code": "H90", "description_es": "Hipoacusia conductiva y neurosensorial", "category": "Otológicas", "is_common": True},
        {"code": "H91.9", "description_es": "Hipoacusia no especificada", "category": "Otológicas", "is_common": True},
        {"code": "H93.1", "description_es": "Tinnitus (acúfenos)", "category": "Otológicas", "is_common": True},
        
        # ENFERMEDADES DEL SISTEMA CIRCULATORIO (I00-I99)
        {"code": "I10", "description_es": "Hipertensión esencial (primaria)", "category": "Cardiovasculares", "is_common": True},
        {"code": "I11", "description_es": "Enfermedad cardíaca hipertensiva", "category": "Cardiovasculares", "is_common": True},
        {"code": "I20", "description_es": "Angina de pecho", "category": "Cardiovasculares", "is_common": True},
        {"code": "I20.0", "description_es": "Angina inestable", "category": "Cardiovasculares", "is_common": True},
        {"code": "I20.9", "description_es": "Angina de pecho no especificada", "category": "Cardiovasculares", "is_common": True},
        {"code": "I21", "description_es": "Infarto agudo del miocardio", "category": "Cardiovasculares", "is_common": True},
        {"code": "I25", "description_es": "Enfermedad isquémica crónica del corazón", "category": "Cardiovasculares", "is_common": True},
        {"code": "I25.9", "description_es": "Enfermedad isquémica crónica del corazón no especificada", "category": "Cardiovasculares", "is_common": True},
        {"code": "I34.0", "description_es": "Insuficiencia mitral", "category": "Cardiovasculares", "is_common": True},
        {"code": "I35.0", "description_es": "Estenosis aórtica", "category": "Cardiovasculares", "is_common": True},
        {"code": "I42", "description_es": "Miocardiopatía", "category": "Cardiovasculares", "is_common": False},
        {"code": "I44", "description_es": "Bloqueo auriculoventricular y de rama izquierda", "category": "Cardiovasculares", "is_common": True},
        {"code": "I47", "description_es": "Taquicardia paroxística", "category": "Cardiovasculares", "is_common": True},
        {"code": "I48", "description_es": "Fibrilación y aleteo auricular", "category": "Cardiovasculares", "is_common": True},
        {"code": "I49", "description_es": "Otras arritmias cardíacas", "category": "Cardiovasculares", "is_common": True},
        {"code": "I49.9", "description_es": "Arritmia cardíaca no especificada", "category": "Cardiovasculares", "is_common": True},
        {"code": "I50", "description_es": "Insuficiencia cardíaca", "category": "Cardiovasculares", "is_common": True},
        {"code": "I50.0", "description_es": "Insuficiencia cardíaca congestiva", "category": "Cardiovasculares", "is_common": True},
        {"code": "I50.9", "description_es": "Insuficiencia cardíaca no especificada", "category": "Cardiovasculares", "is_common": True},
        {"code": "I63", "description_es": "Infarto cerebral", "category": "Cardiovasculares", "is_common": True},
        {"code": "I64", "description_es": "Accidente vascular encefálico no especificado", "category": "Cardiovasculares", "is_common": True},
        {"code": "I67.9", "description_es": "Enfermedad cerebrovascular no especificada", "category": "Cardiovasculares", "is_common": True},
        {"code": "I70", "description_es": "Aterosclerosis", "category": "Cardiovasculares", "is_common": True},
        {"code": "I73.9", "description_es": "Enfermedad vascular periférica no especificada", "category": "Cardiovasculares", "is_common": True},
        {"code": "I80", "description_es": "Flebitis y tromboflebitis", "category": "Cardiovasculares", "is_common": True},
        {"code": "I83", "description_es": "Venas varicosas de miembros inferiores", "category": "Cardiovasculares", "is_common": True},
        {"code": "I84", "description_es": "Hemorroides", "category": "Cardiovasculares", "is_common": True},
        {"code": "I84.0", "description_es": "Hemorroides internas trombosadas", "category": "Cardiovasculares", "is_common": True},
        {"code": "I84.1", "description_es": "Hemorroides internas con otras complicaciones", "category": "Cardiovasculares", "is_common": True},
        {"code": "I84.2", "description_es": "Hemorroides internas sin complicaciones", "category": "Cardiovasculares", "is_common": True},
        {"code": "I84.5", "description_es": "Hemorroides externas sin complicaciones", "category": "Cardiovasculares", "is_common": True},
        {"code": "I87.2", "description_es": "Insuficiencia venosa (crónica) (periférica)", "category": "Cardiovasculares", "is_common": True},
        {"code": "I89.0", "description_es": "Linfedema no clasificado en otra parte", "category": "Cardiovasculares", "is_common": True},
        {"code": "I95.1", "description_es": "Hipotensión ortostática", "category": "Cardiovasculares", "is_common": True},
        {"code": "I95.9", "description_es": "Hipotensión no especificada", "category": "Cardiovasculares", "is_common": True},
        
        # ENFERMEDADES DEL SISTEMA RESPIRATORIO (J00-J99)
        {"code": "J00", "description_es": "Rinofaringitis aguda (resfriado común)", "category": "Respiratorias", "is_common": True},
        {"code": "J01", "description_es": "Sinusitis aguda", "category": "Respiratorias", "is_common": True},
        {"code": "J01.9", "description_es": "Sinusitis aguda no especificada", "category": "Respiratorias", "is_common": True},
        {"code": "J02", "description_es": "Faringitis aguda", "category": "Respiratorias", "is_common": True},
        {"code": "J02.0", "description_es": "Faringitis estreptocócica", "category": "Respiratorias", "is_common": True},
        {"code": "J02.9", "description_es": "Faringitis aguda no especificada", "category": "Respiratorias", "is_common": True},
        {"code": "J03", "description_es": "Amigdalitis aguda", "category": "Respiratorias", "is_common": True},
        {"code": "J03.9", "description_es": "Amigdalitis aguda no especificada", "category": "Respiratorias", "is_common": True},
        {"code": "J04", "description_es": "Laringitis y traqueítis agudas", "category": "Respiratorias", "is_common": True},
        {"code": "J04.0", "description_es": "Laringitis aguda", "category": "Respiratorias", "is_common": True},
        {"code": "J05.0", "description_es": "Laringitis obstructiva aguda (crup)", "category": "Respiratorias", "is_common": True},
        {"code": "J06", "description_es": "Infecciones agudas de las vías respiratorias superiores", "category": "Respiratorias", "is_common": True},
        {"code": "J06.9", "description_es": "Infección aguda de las vías respiratorias superiores no especificada", "category": "Respiratorias", "is_common": True},
        {"code": "J10", "description_es": "Gripe debida a virus de la gripe identificado", "category": "Respiratorias", "is_common": True},
        {"code": "J11", "description_es": "Gripe con virus no identificado", "category": "Respiratorias", "is_common": True},
        {"code": "J12", "description_es": "Neumonía viral no clasificada en otra parte", "category": "Respiratorias", "is_common": True},
        {"code": "J15", "description_es": "Neumonía bacteriana no clasificada en otra parte", "category": "Respiratorias", "is_common": True},
        {"code": "J18", "description_es": "Neumonía, organismo no especificado", "category": "Respiratorias", "is_common": True},
        {"code": "J18.9", "description_es": "Neumonía no especificada", "category": "Respiratorias", "is_common": True},
        {"code": "J20", "description_es": "Bronquitis aguda", "category": "Respiratorias", "is_common": True},
        {"code": "J20.9", "description_es": "Bronquitis aguda no especificada", "category": "Respiratorias", "is_common": True},
        {"code": "J21", "description_es": "Bronquiolitis aguda", "category": "Respiratorias", "is_common": True},
        {"code": "J30", "description_es": "Rinitis alérgica y vasomotora", "category": "Respiratorias", "is_common": True},
        {"code": "J30.1", "description_es": "Rinitis alérgica debida al polen", "category": "Respiratorias", "is_common": True},
        {"code": "J30.4", "description_es": "Rinitis alérgica no especificada", "category": "Respiratorias", "is_common": True},
        {"code": "J31", "description_es": "Rinitis, rinofaringitis y faringitis crónicas", "category": "Respiratorias", "is_common": True},
        {"code": "J32", "description_es": "Sinusitis crónica", "category": "Respiratorias", "is_common": True},
        {"code": "J32.9", "description_es": "Sinusitis crónica no especificada", "category": "Respiratorias", "is_common": True},
        {"code": "J33", "description_es": "Pólipo nasal", "category": "Respiratorias", "is_common": True},
        {"code": "J34.2", "description_es": "Desviación del tabique nasal", "category": "Respiratorias", "is_common": True},
        {"code": "J35.0", "description_es": "Amigdalitis crónica", "category": "Respiratorias", "is_common": True},
        {"code": "J35.2", "description_es": "Hipertrofia de adenoides", "category": "Respiratorias", "is_common": True},
        {"code": "J37.0", "description_es": "Laringitis crónica", "category": "Respiratorias", "is_common": True},
        {"code": "J40", "description_es": "Bronquitis no especificada como aguda o crónica", "category": "Respiratorias", "is_common": True},
        {"code": "J41", "description_es": "Bronquitis crónica simple y mucopurulenta", "category": "Respiratorias", "is_common": True},
        {"code": "J42", "description_es": "Bronquitis crónica no especificada", "category": "Respiratorias", "is_common": True},
        {"code": "J43", "description_es": "Enfisema", "category": "Respiratorias", "is_common": True},
        {"code": "J44", "description_es": "Otras enfermedades pulmonares obstructivas crónicas (EPOC)", "category": "Respiratorias", "is_common": True},
        {"code": "J44.9", "description_es": "EPOC no especificada", "category": "Respiratorias", "is_common": True},
        {"code": "J45", "description_es": "Asma", "category": "Respiratorias", "is_common": True},
        {"code": "J45.0", "description_es": "Asma predominantemente alérgica", "category": "Respiratorias", "is_common": True},
        {"code": "J45.9", "description_es": "Asma no especificada", "category": "Respiratorias", "is_common": True},
        {"code": "J98.0", "description_es": "Enfermedades de la tráquea y de los bronquios", "category": "Respiratorias", "is_common": True},
        
        # ENFERMEDADES DEL SISTEMA DIGESTIVO (K00-K93)
        {"code": "K00.6", "description_es": "Alteraciones en la erupción dentaria", "category": "Digestivas", "is_common": True},
        {"code": "K01", "description_es": "Dientes incluidos e impactados", "category": "Digestivas", "is_common": True},
        {"code": "K02", "description_es": "Caries dental", "category": "Digestivas", "is_common": True},
        {"code": "K04", "description_es": "Enfermedades de la pulpa y de los tejidos periapicales", "category": "Digestivas", "is_common": True},
        {"code": "K04.7", "description_es": "Absceso periapical sin fístula", "category": "Digestivas", "is_common": True},
        {"code": "K05", "description_es": "Gingivitis y enfermedades periodontales", "category": "Digestivas", "is_common": True},
        {"code": "K05.0", "description_es": "Gingivitis aguda", "category": "Digestivas", "is_common": True},
        {"code": "K05.1", "description_es": "Gingivitis crónica", "category": "Digestivas", "is_common": True},
        {"code": "K08.1", "description_es": "Pérdida de dientes debida a accidente, extracción o enfermedad periodontal", "category": "Digestivas", "is_common": True},
        {"code": "K12", "description_es": "Estomatitis y lesiones afines", "category": "Digestivas", "is_common": True},
        {"code": "K12.0", "description_es": "Estomatitis aftosa recurrente", "category": "Digestivas", "is_common": True},
        {"code": "K13.0", "description_es": "Enfermedades de los labios (queilitis)", "category": "Digestivas", "is_common": True},
        {"code": "K14.0", "description_es": "Glositis", "category": "Digestivas", "is_common": True},
        {"code": "K20", "description_es": "Esofagitis", "category": "Digestivas", "is_common": True},
        {"code": "K21", "description_es": "Enfermedad por reflujo gastroesofágico", "category": "Digestivas", "is_common": True},
        {"code": "K21.0", "description_es": "Enfermedad por reflujo gastroesofágico con esofagitis", "category": "Digestivas", "is_common": True},
        {"code": "K25", "description_es": "Úlcera gástrica", "category": "Digestivas", "is_common": True},
        {"code": "K26", "description_es": "Úlcera duodenal", "category": "Digestivas", "is_common": True},
        {"code": "K27", "description_es": "Úlcera péptica de sitio no especificado", "category": "Digestivas", "is_common": True},
        {"code": "K29", "description_es": "Gastritis y duodenitis", "category": "Digestivas", "is_common": True},
        {"code": "K29.7", "description_es": "Gastritis no especificada", "category": "Digestivas", "is_common": True},
        {"code": "K30", "description_es": "Dispepsia funcional", "category": "Digestivas", "is_common": True},
        {"code": "K35", "description_es": "Apendicitis aguda", "category": "Digestivas", "is_common": True},
        {"code": "K40", "description_es": "Hernia inguinal", "category": "Digestivas", "is_common": True},
        {"code": "K41", "description_es": "Hernia femoral", "category": "Digestivas", "is_common": True},
        {"code": "K42", "description_es": "Hernia umbilical", "category": "Digestivas", "is_common": True},
        {"code": "K44", "description_es": "Hernia diafragmática (hernia hiatal)", "category": "Digestivas", "is_common": True},
        {"code": "K50", "description_es": "Enfermedad de Crohn", "category": "Digestivas", "is_common": True},
        {"code": "K51", "description_es": "Colitis ulcerosa", "category": "Digestivas", "is_common": True},
        {"code": "K52.9", "description_es": "Colitis y gastroenteritis no infecciosas no especificadas", "category": "Digestivas", "is_common": True},
        {"code": "K57", "description_es": "Enfermedad diverticular del intestino", "category": "Digestivas", "is_common": True},
        {"code": "K58", "description_es": "Síndrome del intestino irritable", "category": "Digestivas", "is_common": True},
        {"code": "K58.9", "description_es": "Síndrome del intestino irritable sin diarrea", "category": "Digestivas", "is_common": True},
        {"code": "K59.0", "description_es": "Constipación", "category": "Digestivas", "is_common": True},
        {"code": "K60.0", "description_es": "Fisura anal aguda", "category": "Digestivas", "is_common": True},
        {"code": "K60.2", "description_es": "Fisura anal no especificada", "category": "Digestivas", "is_common": True},
        {"code": "K61", "description_es": "Absceso de las regiones anal y rectal", "category": "Digestivas", "is_common": True},
        {"code": "K62.5", "description_es": "Hemorragia del ano y del recto", "category": "Digestivas", "is_common": True},
        {"code": "K70", "description_es": "Enfermedad hepática alcohólica", "category": "Digestivas", "is_common": True},
        {"code": "K73", "description_es": "Hepatitis crónica no clasificada en otra parte", "category": "Digestivas", "is_common": True},
        {"code": "K74", "description_es": "Fibrosis y cirrosis del hígado", "category": "Digestivas", "is_common": True},
        {"code": "K76.0", "description_es": "Hígado graso no clasificado en otra parte (esteatosis hepática)", "category": "Digestivas", "is_common": True},
        {"code": "K80", "description_es": "Colelitiasis (cálculos biliares)", "category": "Digestivas", "is_common": True},
        {"code": "K81", "description_es": "Colecistitis", "category": "Digestivas", "is_common": True},
        {"code": "K85", "description_es": "Pancreatitis aguda", "category": "Digestivas", "is_common": True},
        {"code": "K86.1", "description_es": "Otras pancreatitis crónicas", "category": "Digestivas", "is_common": True},
        
        # ENFERMEDADES DE LA PIEL (L00-L99)
        {"code": "L00", "description_es": "Síndrome estafilocócico de la piel escaldada", "category": "Dermatológicas", "is_common": False},
        {"code": "L01", "description_es": "Impétigo", "category": "Dermatológicas", "is_common": True},
        {"code": "L02", "description_es": "Absceso cutáneo, furúnculo y carbunco", "category": "Dermatológicas", "is_common": True},
        {"code": "L02.9", "description_es": "Absceso cutáneo, furúnculo y carbunco no especificado", "category": "Dermatológicas", "is_common": True},
        {"code": "L03", "description_es": "Celulitis", "category": "Dermatológicas", "is_common": True},
        {"code": "L03.1", "description_es": "Celulitis de otras partes de los miembros", "category": "Dermatológicas", "is_common": True},
        {"code": "L04", "description_es": "Linfadenitis aguda", "category": "Dermatológicas", "is_common": True},
        {"code": "L08.0", "description_es": "Piodermia", "category": "Dermatológicas", "is_common": True},
        {"code": "L20", "description_es": "Dermatitis atópica", "category": "Dermatológicas", "is_common": True},
        {"code": "L20.9", "description_es": "Dermatitis atópica no especificada", "category": "Dermatológicas", "is_common": True},
        {"code": "L21", "description_es": "Dermatitis seborreica", "category": "Dermatológicas", "is_common": True},
        {"code": "L22", "description_es": "Dermatitis del pañal", "category": "Dermatológicas", "is_common": True},
        {"code": "L23", "description_es": "Dermatitis alérgica de contacto", "category": "Dermatológicas", "is_common": True},
        {"code": "L24", "description_es": "Dermatitis de contacto por irritantes", "category": "Dermatológicas", "is_common": True},
        {"code": "L25", "description_es": "Dermatitis de contacto no especificada", "category": "Dermatológicas", "is_common": True},
        {"code": "L27.0", "description_es": "Erupción cutánea generalizada debida a drogas y medicamentos", "category": "Dermatológicas", "is_common": True},
        {"code": "L29", "description_es": "Prurito", "category": "Dermatológicas", "is_common": True},
        {"code": "L29.9", "description_es": "Prurito no especificado", "category": "Dermatológicas", "is_common": True},
        {"code": "L30", "description_es": "Otras dermatitis", "category": "Dermatológicas", "is_common": True},
        {"code": "L30.9", "description_es": "Dermatitis no especificada", "category": "Dermatológicas", "is_common": True},
        {"code": "L40", "description_es": "Psoriasis", "category": "Dermatológicas", "is_common": True},
        {"code": "L40.0", "description_es": "Psoriasis vulgar", "category": "Dermatológicas", "is_common": True},
        {"code": "L42", "description_es": "Pitiriasis rosada", "category": "Dermatológicas", "is_common": True},
        {"code": "L43", "description_es": "Liquen plano", "category": "Dermatológicas", "is_common": True},
        {"code": "L50", "description_es": "Urticaria", "category": "Dermatológicas", "is_common": True},
        {"code": "L50.0", "description_es": "Urticaria alérgica", "category": "Dermatológicas", "is_common": True},
        {"code": "L50.9", "description_es": "Urticaria no especificada", "category": "Dermatológicas", "is_common": True},
        {"code": "L53.9", "description_es": "Afección eritematosa no especificada", "category": "Dermatológicas", "is_common": True},
        {"code": "L55", "description_es": "Quemadura solar", "category": "Dermatológicas", "is_common": True},
        {"code": "L56", "description_es": "Otros cambios agudos de la piel debidos a radiación ultravioleta", "category": "Dermatológicas", "is_common": True},
        {"code": "L60", "description_es": "Trastornos de las uñas", "category": "Dermatológicas", "is_common": True},
        {"code": "L60.0", "description_es": "Uña encarnada", "category": "Dermatológicas", "is_common": True},
        {"code": "L63", "description_es": "Alopecia areata", "category": "Dermatológicas", "is_common": True},
        {"code": "L64", "description_es": "Alopecia androgenética", "category": "Dermatológicas", "is_common": True},
        {"code": "L65.9", "description_es": "Pérdida del cabello no cicatrizal no especificada", "category": "Dermatológicas", "is_common": True},
        {"code": "L70", "description_es": "Acné", "category": "Dermatológicas", "is_common": True},
        {"code": "L70.0", "description_es": "Acné vulgar", "category": "Dermatológicas", "is_common": True},
        {"code": "L71", "description_es": "Rosácea", "category": "Dermatológicas", "is_common": True},
        {"code": "L72.0", "description_es": "Quiste epidérmico", "category": "Dermatológicas", "is_common": True},
        {"code": "L72.1", "description_es": "Quiste tricodérmico (quiste sebáceo)", "category": "Dermatológicas", "is_common": True},
        {"code": "L73.2", "description_es": "Hidradenitis supurativa", "category": "Dermatológicas", "is_common": True},
        {"code": "L74.0", "description_es": "Miliaria rubra", "category": "Dermatológicas", "is_common": True},
        {"code": "L80", "description_es": "Vitíligo", "category": "Dermatológicas", "is_common": True},
        {"code": "L81.0", "description_es": "Hiperpigmentación postinflamatoria", "category": "Dermatológicas", "is_common": True},
        {"code": "L81.1", "description_es": "Cloasma (melasma)", "category": "Dermatológicas", "is_common": True},
        {"code": "L82", "description_es": "Queratosis seborreica", "category": "Dermatológicas", "is_common": True},
        {"code": "L84", "description_es": "Callos y callosidades", "category": "Dermatológicas", "is_common": True},
        {"code": "L85.3", "description_es": "Xerosis cutánea (piel seca)", "category": "Dermatológicas", "is_common": True},
        {"code": "L90.5", "description_es": "Estrías atróficas", "category": "Dermatológicas", "is_common": True},
        {"code": "L91.0", "description_es": "Cicatriz queloidea", "category": "Dermatológicas", "is_common": True},
        {"code": "L98.9", "description_es": "Trastorno de la piel y del tejido subcutáneo no especificado", "category": "Dermatológicas", "is_common": True},
        
        # ENFERMEDADES DEL SISTEMA MUSCULOESQUELÉTICO (M00-M99)
        {"code": "M06.9", "description_es": "Artritis reumatoide no especificada", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M10", "description_es": "Gota", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M10.9", "description_es": "Gota no especificada", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M13.9", "description_es": "Artritis no especificada", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M15", "description_es": "Poliartrosis", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M16", "description_es": "Coxartrosis (artrosis de cadera)", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M17", "description_es": "Gonartrosis (artrosis de rodilla)", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M19", "description_es": "Otras artrosis", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M19.9", "description_es": "Artrosis no especificada", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M23", "description_es": "Trastornos internos de la rodilla", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M25.5", "description_es": "Dolor articular", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M32", "description_es": "Lupus eritematoso sistémico", "category": "Musculoesqueléticas", "is_common": False},
        {"code": "M35.3", "description_es": "Polimialgia reumática", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M41", "description_es": "Escoliosis", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M42", "description_es": "Osteocondrosis de la columna vertebral", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M43.1", "description_es": "Espondilolistesis", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M47", "description_es": "Espondilosis", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M47.9", "description_es": "Espondilosis no especificada", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M50", "description_es": "Trastornos de disco cervical", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M51", "description_es": "Otros trastornos de los discos intervertebrales", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M51.1", "description_es": "Hernia discal lumbar con radiculopatía", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M53.1", "description_es": "Síndrome cervicobraquial", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M54", "description_es": "Dorsalgia", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M54.2", "description_es": "Cervicalgia", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M54.3", "description_es": "Ciática", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M54.4", "description_es": "Lumbago con ciática", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M54.5", "description_es": "Lumbago no especificado (dolor lumbar)", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M54.6", "description_es": "Dolor en la columna torácica", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M54.9", "description_es": "Dorsalgia no especificada", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M60.9", "description_es": "Miositis no especificada", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M62.8", "description_es": "Otros trastornos especificados de los músculos", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M65", "description_es": "Sinovitis y tenosinovitis", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M65.4", "description_es": "Tenosinovitis de estiloides radial (de Quervain)", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M67.4", "description_es": "Ganglión", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M70.2", "description_es": "Bursitis del olécranon", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M70.4", "description_es": "Bursitis prerrotuliana", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M71.1", "description_es": "Otras bursitis infecciosas", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M72.0", "description_es": "Fibromatosis de la fascia palmar (Dupuytren)", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M72.2", "description_es": "Fibromatosis de la fascia plantar", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M75", "description_es": "Lesiones del hombro", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M75.0", "description_es": "Capsulitis adhesiva del hombro (hombro congelado)", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M75.1", "description_es": "Síndrome del manguito rotatorio", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M75.3", "description_es": "Tendinitis calcificante del hombro", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M76.6", "description_es": "Tendinitis aquílica", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M77.0", "description_es": "Epicondilitis medial", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M77.1", "description_es": "Epicondilitis lateral (codo de tenista)", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M77.3", "description_es": "Espolón calcáneo", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M79.1", "description_es": "Mialgia", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M79.2", "description_es": "Neuralgia y neuritis no especificadas", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M79.3", "description_es": "Paniculitis no especificada", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M79.6", "description_es": "Dolor en miembro", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M79.7", "description_es": "Fibromialgia", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M80", "description_es": "Osteoporosis con fractura patológica", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M81", "description_es": "Osteoporosis sin fractura patológica", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M81.0", "description_es": "Osteoporosis postmenopáusica", "category": "Musculoesqueléticas", "is_common": True},
        {"code": "M81.9", "description_es": "Osteoporosis no especificada", "category": "Musculoesqueléticas", "is_common": True},
        
        # ENFERMEDADES DEL SISTEMA GENITOURINARIO (N00-N99)
        {"code": "N10", "description_es": "Nefritis tubulointersticial aguda (pielonefritis aguda)", "category": "Genitourinarias", "is_common": True},
        {"code": "N11", "description_es": "Nefritis tubulointersticial crónica", "category": "Genitourinarias", "is_common": False},
        {"code": "N12", "description_es": "Nefritis tubulointersticial no especificada", "category": "Genitourinarias", "is_common": True},
        {"code": "N13.3", "description_es": "Otras hidronefrosis", "category": "Genitourinarias", "is_common": False},
        {"code": "N17", "description_es": "Insuficiencia renal aguda", "category": "Genitourinarias", "is_common": True},
        {"code": "N18", "description_es": "Enfermedad renal crónica", "category": "Genitourinarias", "is_common": True},
        {"code": "N18.9", "description_es": "Enfermedad renal crónica no especificada", "category": "Genitourinarias", "is_common": True},
        {"code": "N19", "description_es": "Insuficiencia renal no especificada", "category": "Genitourinarias", "is_common": True},
        {"code": "N20", "description_es": "Cálculos del riñón y del uréter", "category": "Genitourinarias", "is_common": True},
        {"code": "N20.0", "description_es": "Cálculo del riñón", "category": "Genitourinarias", "is_common": True},
        {"code": "N21", "description_es": "Cálculos de las vías urinarias inferiores", "category": "Genitourinarias", "is_common": True},
        {"code": "N23", "description_es": "Cólico renal no especificado", "category": "Genitourinarias", "is_common": True},
        {"code": "N28.1", "description_es": "Quiste de riñón adquirido", "category": "Genitourinarias", "is_common": True},
        {"code": "N30", "description_es": "Cistitis", "category": "Genitourinarias", "is_common": True},
        {"code": "N30.0", "description_es": "Cistitis aguda", "category": "Genitourinarias", "is_common": True},
        {"code": "N30.9", "description_es": "Cistitis no especificada", "category": "Genitourinarias", "is_common": True},
        {"code": "N34", "description_es": "Uretritis y síndrome uretral", "category": "Genitourinarias", "is_common": True},
        {"code": "N39.0", "description_es": "Infección de vías urinarias, sitio no especificado", "category": "Genitourinarias", "is_common": True},
        {"code": "N39.3", "description_es": "Incontinencia urinaria de esfuerzo", "category": "Genitourinarias", "is_common": True},
        {"code": "N39.4", "description_es": "Otras incontinencias urinarias especificadas", "category": "Genitourinarias", "is_common": True},
        {"code": "N40", "description_es": "Hiperplasia de la próstata", "category": "Genitourinarias", "is_common": True},
        {"code": "N41", "description_es": "Enfermedades inflamatorias de la próstata", "category": "Genitourinarias", "is_common": True},
        {"code": "N41.0", "description_es": "Prostatitis aguda", "category": "Genitourinarias", "is_common": True},
        {"code": "N41.1", "description_es": "Prostatitis crónica", "category": "Genitourinarias", "is_common": True},
        {"code": "N43", "description_es": "Hidrocele y espermatocele", "category": "Genitourinarias", "is_common": True},
        {"code": "N44", "description_es": "Torsión del testículo", "category": "Genitourinarias", "is_common": True},
        {"code": "N45", "description_es": "Orquitis y epididimitis", "category": "Genitourinarias", "is_common": True},
        {"code": "N46", "description_es": "Infertilidad masculina", "category": "Genitourinarias", "is_common": True},
        {"code": "N47", "description_es": "Trastornos del prepucio (fimosis)", "category": "Genitourinarias", "is_common": True},
        {"code": "N48.1", "description_es": "Balanopostitis", "category": "Genitourinarias", "is_common": True},
        {"code": "N48.4", "description_es": "Impotencia de origen orgánico", "category": "Genitourinarias", "is_common": True},
        {"code": "N52", "description_es": "Disfunción eréctil masculina", "category": "Genitourinarias", "is_common": True},
        {"code": "N60", "description_es": "Displasia mamaria benigna", "category": "Genitourinarias", "is_common": True},
        {"code": "N61", "description_es": "Trastornos inflamatorios de la mama", "category": "Genitourinarias", "is_common": True},
        {"code": "N63", "description_es": "Masa no especificada en la mama", "category": "Genitourinarias", "is_common": True},
        {"code": "N64.4", "description_es": "Mastodinia", "category": "Genitourinarias", "is_common": True},
        {"code": "N70", "description_es": "Salpingitis y ooforitis", "category": "Genitourinarias", "is_common": True},
        {"code": "N71", "description_es": "Enfermedad inflamatoria del útero (excepto el cuello)", "category": "Genitourinarias", "is_common": True},
        {"code": "N72", "description_es": "Enfermedad inflamatoria del cuello uterino", "category": "Genitourinarias", "is_common": True},
        {"code": "N73", "description_es": "Otras enfermedades pélvicas inflamatorias femeninas", "category": "Genitourinarias", "is_common": True},
        {"code": "N75.1", "description_es": "Absceso de la glándula de Bartholin", "category": "Genitourinarias", "is_common": True},
        {"code": "N76", "description_es": "Otras afecciones inflamatorias de la vagina y vulva", "category": "Genitourinarias", "is_common": True},
        {"code": "N76.0", "description_es": "Vaginitis aguda", "category": "Genitourinarias", "is_common": True},
        {"code": "N76.1", "description_es": "Vaginitis subaguda y crónica", "category": "Genitourinarias", "is_common": True},
        {"code": "N76.2", "description_es": "Vulvitis aguda", "category": "Genitourinarias", "is_common": True},
        {"code": "N77.1", "description_es": "Vaginitis, vulvitis y vulvovaginitis en enfermedades infecciosas y parasitarias", "category": "Genitourinarias", "is_common": True},
        {"code": "N80", "description_es": "Endometriosis", "category": "Genitourinarias", "is_common": True},
        {"code": "N81", "description_es": "Prolapso genital femenino", "category": "Genitourinarias", "is_common": True},
        {"code": "N83.0", "description_es": "Quiste folicular del ovario", "category": "Genitourinarias", "is_common": True},
        {"code": "N83.2", "description_es": "Otros quistes ováricos", "category": "Genitourinarias", "is_common": True},
        {"code": "N84", "description_es": "Pólipo del tracto genital femenino", "category": "Genitourinarias", "is_common": True},
        {"code": "N85.0", "description_es": "Hiperplasia endometrial", "category": "Genitourinarias", "is_common": True},
        {"code": "N87", "description_es": "Displasia del cuello uterino", "category": "Genitourinarias", "is_common": True},
        {"code": "N89.8", "description_es": "Otros trastornos no inflamatorios especificados de la vagina", "category": "Genitourinarias", "is_common": True},
        {"code": "N91", "description_es": "Menstruación ausente, escasa o rara", "category": "Genitourinarias", "is_common": True},
        {"code": "N91.0", "description_es": "Amenorrea primaria", "category": "Genitourinarias", "is_common": True},
        {"code": "N91.1", "description_es": "Amenorrea secundaria", "category": "Genitourinarias", "is_common": True},
        {"code": "N91.2", "description_es": "Amenorrea no especificada", "category": "Genitourinarias", "is_common": True},
        {"code": "N92", "description_es": "Menstruación excesiva, frecuente e irregular", "category": "Genitourinarias", "is_common": True},
        {"code": "N92.0", "description_es": "Menstruación excesiva y frecuente con ciclo regular", "category": "Genitourinarias", "is_common": True},
        {"code": "N92.1", "description_es": "Menstruación excesiva y frecuente con ciclo irregular", "category": "Genitourinarias", "is_common": True},
        {"code": "N93.9", "description_es": "Hemorragia uterina o vaginal anormal no especificada", "category": "Genitourinarias", "is_common": True},
        {"code": "N94.3", "description_es": "Síndrome de tensión premenstrual", "category": "Genitourinarias", "is_common": True},
        {"code": "N94.4", "description_es": "Dismenorrea primaria", "category": "Genitourinarias", "is_common": True},
        {"code": "N94.6", "description_es": "Dismenorrea no especificada", "category": "Genitourinarias", "is_common": True},
        {"code": "N95.1", "description_es": "Estados menopáusicos y climatéricos femeninos", "category": "Genitourinarias", "is_common": True},
        {"code": "N97", "description_es": "Infertilidad femenina", "category": "Genitourinarias", "is_common": True},
        
        # EMBARAZO, PARTO Y PUERPERIO (O00-O99)
        {"code": "O00", "description_es": "Embarazo ectópico", "category": "Obstetricia", "is_common": True},
        {"code": "O03", "description_es": "Aborto espontáneo", "category": "Obstetricia", "is_common": True},
        {"code": "O20.0", "description_es": "Amenaza de aborto", "category": "Obstetricia", "is_common": True},
        {"code": "O21", "description_es": "Vómitos excesivos en el embarazo", "category": "Obstetricia", "is_common": True},
        {"code": "O23.4", "description_es": "Infección no especificada de las vías urinarias en el embarazo", "category": "Obstetricia", "is_common": True},
        {"code": "O24", "description_es": "Diabetes mellitus en el embarazo", "category": "Obstetricia", "is_common": True},
        {"code": "O26.8", "description_es": "Otras afecciones especificadas relacionadas con el embarazo", "category": "Obstetricia", "is_common": True},
        {"code": "O47", "description_es": "Falso trabajo de parto", "category": "Obstetricia", "is_common": True},
        {"code": "O80", "description_es": "Parto único espontáneo", "category": "Obstetricia", "is_common": True},
        {"code": "Z32.1", "description_es": "Embarazo confirmado", "category": "Obstetricia", "is_common": True},
        {"code": "Z34", "description_es": "Supervisión de embarazo normal", "category": "Obstetricia", "is_common": True},
        {"code": "Z35", "description_es": "Supervisión de embarazo de alto riesgo", "category": "Obstetricia", "is_common": True},
        
        # AFECCIONES PERINATALES (P00-P96)
        {"code": "P07.3", "description_es": "Otros recién nacidos pretérmino", "category": "Perinatales", "is_common": True},
        {"code": "P22", "description_es": "Dificultad respiratoria del recién nacido", "category": "Perinatales", "is_common": True},
        {"code": "P36", "description_es": "Sepsis bacteriana del recién nacido", "category": "Perinatales", "is_common": True},
        {"code": "P59", "description_es": "Ictericia neonatal por otras causas y por las no especificadas", "category": "Perinatales", "is_common": True},
        {"code": "P61.0", "description_es": "Trombocitopenia neonatal transitoria", "category": "Perinatales", "is_common": False},
        {"code": "P70.4", "description_es": "Otras hipoglucemias neonatales", "category": "Perinatales", "is_common": True},
        {"code": "P96.9", "description_es": "Afección originada en el período perinatal no especificada", "category": "Perinatales", "is_common": True},
        
        # MALFORMACIONES CONGÉNITAS (Q00-Q99)
        {"code": "Q21.0", "description_es": "Defecto del tabique ventricular", "category": "Congénitas", "is_common": False},
        {"code": "Q21.1", "description_es": "Defecto del tabique auricular", "category": "Congénitas", "is_common": False},
        {"code": "Q65", "description_es": "Deformidades congénitas de la cadera", "category": "Congénitas", "is_common": True},
        {"code": "Q66.0", "description_es": "Pie equinovaro (pie zambo)", "category": "Congénitas", "is_common": True},
        {"code": "Q66.5", "description_es": "Pie plano congénito", "category": "Congénitas", "is_common": True},
        
        # SÍNTOMAS, SIGNOS Y HALLAZGOS ANORMALES (R00-R99)
        {"code": "R00.0", "description_es": "Taquicardia no especificada", "category": "Síntomas", "is_common": True},
        {"code": "R00.1", "description_es": "Bradicardia no especificada", "category": "Síntomas", "is_common": True},
        {"code": "R00.2", "description_es": "Palpitaciones", "category": "Síntomas", "is_common": True},
        {"code": "R01", "description_es": "Soplos y otros sonidos cardíacos", "category": "Síntomas", "is_common": True},
        {"code": "R03.0", "description_es": "Lectura elevada de la presión sanguínea sin diagnóstico de hipertensión", "category": "Síntomas", "is_common": True},
        {"code": "R04.0", "description_es": "Epistaxis (sangrado nasal)", "category": "Síntomas", "is_common": True},
        {"code": "R05", "description_es": "Tos", "category": "Síntomas", "is_common": True},
        {"code": "R06.0", "description_es": "Disnea", "category": "Síntomas", "is_common": True},
        {"code": "R06.2", "description_es": "Sibilancias", "category": "Síntomas", "is_common": True},
        {"code": "R07.4", "description_es": "Dolor torácico no especificado", "category": "Síntomas", "is_common": True},
        {"code": "R10", "description_es": "Dolor abdominal y pélvico", "category": "Síntomas", "is_common": True},
        {"code": "R10.1", "description_es": "Dolor localizado en abdomen superior", "category": "Síntomas", "is_common": True},
        {"code": "R10.3", "description_es": "Dolor localizado en otras partes del abdomen inferior", "category": "Síntomas", "is_common": True},
        {"code": "R10.4", "description_es": "Otros dolores abdominales y los no especificados", "category": "Síntomas", "is_common": True},
        {"code": "R11", "description_es": "Náusea y vómito", "category": "Síntomas", "is_common": True},
        {"code": "R12", "description_es": "Pirosis (acidez)", "category": "Síntomas", "is_common": True},
        {"code": "R13", "description_es": "Disfagia", "category": "Síntomas", "is_common": True},
        {"code": "R14", "description_es": "Flatulencia y afecciones afines", "category": "Síntomas", "is_common": True},
        {"code": "R17", "description_es": "Ictericia no especificada", "category": "Síntomas", "is_common": True},
        {"code": "R19.4", "description_es": "Cambio en los hábitos intestinales", "category": "Síntomas", "is_common": True},
        {"code": "R19.5", "description_es": "Otras anormalidades fecales", "category": "Síntomas", "is_common": True},
        {"code": "R20.2", "description_es": "Parestesia de la piel", "category": "Síntomas", "is_common": True},
        {"code": "R21", "description_es": "Sarpullido y otras erupciones cutáneas no especificadas", "category": "Síntomas", "is_common": True},
        {"code": "R22", "description_es": "Tumefacción, masa o prominencia de la piel localizada", "category": "Síntomas", "is_common": True},
        {"code": "R23.0", "description_es": "Cianosis", "category": "Síntomas", "is_common": True},
        {"code": "R23.3", "description_es": "Equimosis espontánea", "category": "Síntomas", "is_common": True},
        {"code": "R25.1", "description_es": "Temblor no especificado", "category": "Síntomas", "is_common": True},
        {"code": "R25.2", "description_es": "Calambres y espasmos", "category": "Síntomas", "is_common": True},
        {"code": "R26.2", "description_es": "Dificultad para caminar no clasificada en otra parte", "category": "Síntomas", "is_common": True},
        {"code": "R27.0", "description_es": "Ataxia no especificada", "category": "Síntomas", "is_common": False},
        {"code": "R30.0", "description_es": "Disuria", "category": "Síntomas", "is_common": True},
        {"code": "R31", "description_es": "Hematuria", "category": "Síntomas", "is_common": True},
        {"code": "R32", "description_es": "Incontinencia urinaria no especificada", "category": "Síntomas", "is_common": True},
        {"code": "R33", "description_es": "Retención de orina", "category": "Síntomas", "is_common": True},
        {"code": "R35", "description_es": "Poliuria", "category": "Síntomas", "is_common": True},
        {"code": "R40.0", "description_es": "Somnolencia", "category": "Síntomas", "is_common": True},
        {"code": "R41.3", "description_es": "Otras amnesias", "category": "Síntomas", "is_common": True},
        {"code": "R42", "description_es": "Mareo y desvanecimiento", "category": "Síntomas", "is_common": True},
        {"code": "R45.0", "description_es": "Nerviosismo", "category": "Síntomas", "is_common": True},
        {"code": "R45.1", "description_es": "Inquietud y agitación", "category": "Síntomas", "is_common": True},
        {"code": "R50", "description_es": "Fiebre de otro origen y de origen desconocido", "category": "Síntomas", "is_common": True},
        {"code": "R50.9", "description_es": "Fiebre no especificada", "category": "Síntomas", "is_common": True},
        {"code": "R51", "description_es": "Cefalea", "category": "Síntomas", "is_common": True},
        {"code": "R52", "description_es": "Dolor no clasificado en otra parte", "category": "Síntomas", "is_common": True},
        {"code": "R53", "description_es": "Malestar y fatiga", "category": "Síntomas", "is_common": True},
        {"code": "R55", "description_es": "Síncope y colapso", "category": "Síntomas", "is_common": True},
        {"code": "R56.0", "description_es": "Convulsiones febriles", "category": "Síntomas", "is_common": True},
        {"code": "R56.8", "description_es": "Otras convulsiones y las no especificadas", "category": "Síntomas", "is_common": True},
        {"code": "R58", "description_es": "Hemorragia no clasificada en otra parte", "category": "Síntomas", "is_common": True},
        {"code": "R59", "description_es": "Adenomegalia (ganglios linfáticos inflamados)", "category": "Síntomas", "is_common": True},
        {"code": "R59.0", "description_es": "Adenomegalia localizada", "category": "Síntomas", "is_common": True},
        {"code": "R59.1", "description_es": "Adenomegalia generalizada", "category": "Síntomas", "is_common": True},
        {"code": "R60.0", "description_es": "Edema localizado", "category": "Síntomas", "is_common": True},
        {"code": "R60.1", "description_es": "Edema generalizado", "category": "Síntomas", "is_common": True},
        {"code": "R63.0", "description_es": "Anorexia (pérdida del apetito)", "category": "Síntomas", "is_common": True},
        {"code": "R63.4", "description_es": "Pérdida anormal de peso", "category": "Síntomas", "is_common": True},
        {"code": "R63.5", "description_es": "Aumento anormal de peso", "category": "Síntomas", "is_common": True},
        {"code": "R68.8", "description_es": "Otros síntomas y signos generales especificados", "category": "Síntomas", "is_common": True},
        {"code": "R73.0", "description_es": "Anormalidad en prueba de tolerancia a la glucosa", "category": "Síntomas", "is_common": True},
        
        # TRAUMATISMOS, ENVENENAMIENTOS (S00-T98)
        {"code": "S00", "description_es": "Traumatismo superficial de la cabeza", "category": "Traumatismos", "is_common": True},
        {"code": "S00.0", "description_es": "Traumatismo superficial del cuero cabelludo", "category": "Traumatismos", "is_common": True},
        {"code": "S01", "description_es": "Herida de la cabeza", "category": "Traumatismos", "is_common": True},
        {"code": "S02", "description_es": "Fractura del cráneo y de los huesos de la cara", "category": "Traumatismos", "is_common": True},
        {"code": "S02.0", "description_es": "Fractura de la bóveda del cráneo", "category": "Traumatismos", "is_common": False},
        {"code": "S06", "description_es": "Traumatismo intracraneal", "category": "Traumatismos", "is_common": True},
        {"code": "S06.0", "description_es": "Conmoción cerebral", "category": "Traumatismos", "is_common": True},
        {"code": "S09.9", "description_es": "Traumatismo de la cabeza no especificado", "category": "Traumatismos", "is_common": True},
        {"code": "S13.4", "description_es": "Esguince y torcedura de columna cervical", "category": "Traumatismos", "is_common": True},
        {"code": "S20", "description_es": "Traumatismo superficial del tórax", "category": "Traumatismos", "is_common": True},
        {"code": "S22", "description_es": "Fractura de costillas, esternón y columna torácica", "category": "Traumatismos", "is_common": True},
        {"code": "S30", "description_es": "Traumatismo superficial del abdomen, de la región lumbosacra y de la pelvis", "category": "Traumatismos", "is_common": True},
        {"code": "S33.5", "description_es": "Esguince y torcedura de columna lumbar", "category": "Traumatismos", "is_common": True},
        {"code": "S40", "description_es": "Traumatismo superficial del hombro y del brazo", "category": "Traumatismos", "is_common": True},
        {"code": "S42", "description_es": "Fractura del hombro y del brazo", "category": "Traumatismos", "is_common": True},
        {"code": "S43.0", "description_es": "Luxación de la articulación del hombro", "category": "Traumatismos", "is_common": True},
        {"code": "S50", "description_es": "Traumatismo superficial del antebrazo", "category": "Traumatismos", "is_common": True},
        {"code": "S52", "description_es": "Fractura del antebrazo", "category": "Traumatismos", "is_common": True},
        {"code": "S60", "description_es": "Traumatismo superficial de la muñeca y de la mano", "category": "Traumatismos", "is_common": True},
        {"code": "S61", "description_es": "Herida de la muñeca y de la mano", "category": "Traumatismos", "is_common": True},
        {"code": "S62", "description_es": "Fractura de la muñeca y de la mano", "category": "Traumatismos", "is_common": True},
        {"code": "S63", "description_es": "Luxación, esguince y torcedura de articulaciones y ligamentos de la muñeca y de la mano", "category": "Traumatismos", "is_common": True},
        {"code": "S70", "description_es": "Traumatismo superficial de la cadera y del muslo", "category": "Traumatismos", "is_common": True},
        {"code": "S72", "description_es": "Fractura del fémur", "category": "Traumatismos", "is_common": True},
        {"code": "S80", "description_es": "Traumatismo superficial de la pierna", "category": "Traumatismos", "is_common": True},
        {"code": "S82", "description_es": "Fractura de la pierna, incluso del tobillo", "category": "Traumatismos", "is_common": True},
        {"code": "S83", "description_es": "Luxación, esguince y torcedura de articulaciones y ligamentos de la rodilla", "category": "Traumatismos", "is_common": True},
        {"code": "S83.0", "description_es": "Luxación de la rótula", "category": "Traumatismos", "is_common": True},
        {"code": "S83.4", "description_es": "Esguince y torcedura de ligamentos laterales de la rodilla", "category": "Traumatismos", "is_common": True},
        {"code": "S83.6", "description_es": "Esguince y torcedura de otras partes y las no especificadas de la rodilla", "category": "Traumatismos", "is_common": True},
        {"code": "S90", "description_es": "Traumatismo superficial del tobillo y del pie", "category": "Traumatismos", "is_common": True},
        {"code": "S91", "description_es": "Herida del tobillo y del pie", "category": "Traumatismos", "is_common": True},
        {"code": "S92", "description_es": "Fractura del pie (excepto del tobillo)", "category": "Traumatismos", "is_common": True},
        {"code": "S93", "description_es": "Luxación, esguince y torcedura de articulaciones y ligamentos del tobillo y del pie", "category": "Traumatismos", "is_common": True},
        {"code": "S93.4", "description_es": "Esguince y torcedura del tobillo", "category": "Traumatismos", "is_common": True},
        {"code": "T00", "description_es": "Traumatismos superficiales que afectan múltiples regiones del cuerpo", "category": "Traumatismos", "is_common": True},
        {"code": "T07", "description_es": "Traumatismos múltiples no especificados", "category": "Traumatismos", "is_common": True},
        {"code": "T14.0", "description_es": "Traumatismo superficial de región del cuerpo no especificada", "category": "Traumatismos", "is_common": True},
        {"code": "T14.1", "description_es": "Herida de región del cuerpo no especificada", "category": "Traumatismos", "is_common": True},
        {"code": "T15", "description_es": "Cuerpo extraño en parte externa del ojo", "category": "Traumatismos", "is_common": True},
        {"code": "T16", "description_es": "Cuerpo extraño en el oído", "category": "Traumatismos", "is_common": True},
        {"code": "T17", "description_es": "Cuerpo extraño en las vías respiratorias", "category": "Traumatismos", "is_common": True},
        {"code": "T18", "description_es": "Cuerpo extraño en el conducto alimentario", "category": "Traumatismos", "is_common": True},
        {"code": "T20", "description_es": "Quemadura y corrosión de la cabeza y del cuello", "category": "Traumatismos", "is_common": True},
        {"code": "T30", "description_es": "Quemadura y corrosión, región del cuerpo no especificada", "category": "Traumatismos", "is_common": True},
        {"code": "T63.4", "description_es": "Efecto tóxico del veneno de otros artrópodos", "category": "Traumatismos", "is_common": True},
        {"code": "T78.2", "description_es": "Choque anafiláctico no especificado", "category": "Traumatismos", "is_common": True},
        {"code": "T78.3", "description_es": "Edema angioneurótico", "category": "Traumatismos", "is_common": True},
        {"code": "T78.4", "description_es": "Alergia no especificada", "category": "Traumatismos", "is_common": True},
        {"code": "T88.7", "description_es": "Efecto adverso de drogas y medicamentos no especificado", "category": "Traumatismos", "is_common": True},
        
        # FACTORES QUE INFLUYEN EN EL ESTADO DE SALUD (Z00-Z99)
        {"code": "Z00.0", "description_es": "Examen médico general", "category": "Factores de Salud", "is_common": True},
        {"code": "Z00.1", "description_es": "Examen de rutina de salud del niño", "category": "Factores de Salud", "is_common": True},
        {"code": "Z01.0", "description_es": "Examen de ojos y de la visión", "category": "Factores de Salud", "is_common": True},
        {"code": "Z01.1", "description_es": "Examen de oídos y de la audición", "category": "Factores de Salud", "is_common": True},
        {"code": "Z01.2", "description_es": "Examen odontológico", "category": "Factores de Salud", "is_common": True},
        {"code": "Z01.4", "description_es": "Examen ginecológico (de rutina) (general)", "category": "Factores de Salud", "is_common": True},
        {"code": "Z02.0", "description_es": "Examen para admisión a instituciones educativas", "category": "Factores de Salud", "is_common": True},
        {"code": "Z02.1", "description_es": "Examen preempleo", "category": "Factores de Salud", "is_common": True},
        {"code": "Z02.8", "description_es": "Otros exámenes con fines administrativos", "category": "Factores de Salud", "is_common": True},
        {"code": "Z03.9", "description_es": "Observación por sospecha de enfermedad o afección no especificada", "category": "Factores de Salud", "is_common": True},
        {"code": "Z12.1", "description_es": "Examen de pesquisa especial para tumor de intestino", "category": "Factores de Salud", "is_common": True},
        {"code": "Z12.3", "description_es": "Examen de pesquisa especial para tumor de mama", "category": "Factores de Salud", "is_common": True},
        {"code": "Z12.4", "description_es": "Examen de pesquisa especial para tumor del cuello uterino", "category": "Factores de Salud", "is_common": True},
        {"code": "Z13.0", "description_es": "Examen de pesquisa especial para enfermedades de la sangre", "category": "Factores de Salud", "is_common": True},
        {"code": "Z13.1", "description_es": "Examen de pesquisa especial para diabetes mellitus", "category": "Factores de Salud", "is_common": True},
        {"code": "Z13.6", "description_es": "Examen de pesquisa especial para trastornos cardiovasculares", "category": "Factores de Salud", "is_common": True},
        {"code": "Z20.8", "description_es": "Contacto con y exposición a otras enfermedades transmisibles", "category": "Factores de Salud", "is_common": True},
        {"code": "Z23", "description_es": "Necesidad de inmunización contra una sola enfermedad bacteriana", "category": "Factores de Salud", "is_common": True},
        {"code": "Z24", "description_es": "Necesidad de inmunización contra ciertas enfermedades virales", "category": "Factores de Salud", "is_common": True},
        {"code": "Z25", "description_es": "Necesidad de inmunización contra otras enfermedades virales únicas", "category": "Factores de Salud", "is_common": True},
        {"code": "Z26", "description_es": "Necesidad de inmunización contra otras enfermedades infecciosas únicas", "category": "Factores de Salud", "is_common": True},
        {"code": "Z27", "description_es": "Necesidad de inmunización contra combinaciones de enfermedades infecciosas", "category": "Factores de Salud", "is_common": True},
        {"code": "Z29.1", "description_es": "Inmunoterapia profiláctica", "category": "Factores de Salud", "is_common": True},
        {"code": "Z30", "description_es": "Atención para la anticoncepción", "category": "Factores de Salud", "is_common": True},
        {"code": "Z30.0", "description_es": "Consejo y asesoramiento general sobre la anticoncepción", "category": "Factores de Salud", "is_common": True},
        {"code": "Z30.4", "description_es": "Supervisión del uso de drogas anticonceptivas", "category": "Factores de Salud", "is_common": True},
        {"code": "Z30.5", "description_es": "Supervisión del uso de dispositivo anticonceptivo intrauterino", "category": "Factores de Salud", "is_common": True},
        {"code": "Z31.1", "description_es": "Inseminación artificial", "category": "Factores de Salud", "is_common": False},
        {"code": "Z34.0", "description_es": "Supervisión de primer embarazo normal", "category": "Factores de Salud", "is_common": True},
        {"code": "Z34.8", "description_es": "Supervisión de otros embarazos normales", "category": "Factores de Salud", "is_common": True},
        {"code": "Z36", "description_es": "Examen prenatal", "category": "Factores de Salud", "is_common": True},
        {"code": "Z39.0", "description_es": "Atención y examen inmediatamente después del parto", "category": "Factores de Salud", "is_common": True},
        {"code": "Z39.2", "description_es": "Seguimiento posparto de rutina", "category": "Factores de Salud", "is_common": True},
        {"code": "Z71.3", "description_es": "Consejo sobre régimen dietético y vigilancia", "category": "Factores de Salud", "is_common": True},
        {"code": "Z71.6", "description_es": "Consejo sobre abuso de tabaco", "category": "Factores de Salud", "is_common": True},
        {"code": "Z72.0", "description_es": "Problemas relacionados con el uso de tabaco", "category": "Factores de Salud", "is_common": True},
        {"code": "Z73.0", "description_es": "Agotamiento (burnout)", "category": "Factores de Salud", "is_common": True},
        {"code": "Z76.0", "description_es": "Emisión de receta de repetición", "category": "Factores de Salud", "is_common": True},
        {"code": "Z87.3", "description_es": "Historia personal de enfermedades del sistema digestivo", "category": "Factores de Salud", "is_common": True},
        {"code": "Z96.6", "description_es": "Presencia de implantes ortopédicos articulares", "category": "Factores de Salud", "is_common": True},
    ]
    
    imported = 0
    skipped = 0
    
    for code_data in icd10_codes:
        # Check if code already exists
        existing = await db.icd10_codes.find_one({"code": code_data["code"]})
        if existing:
            skipped += 1
            continue
        
        doc = {
            "id": str(uuid.uuid4()),
            "code": code_data["code"],
            "description_es": code_data["description_es"],
            "category": code_data["category"],
            "is_common": code_data["is_common"],
            "created_at": now,
            "updated_at": now
        }
        await db.icd10_codes.insert_one(doc)
        imported += 1
    
    return {
        "message": f"Base de datos CIE-10 precargada",
        "imported": imported,
        "skipped": skipped,
        "total_in_database": await db.icd10_codes.count_documents({})
    }

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
