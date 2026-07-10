"""Shared core module: Supabase clients, settings, helpers, auth deps, and Pydantic models.

Routes import from this module (not from server.py) to avoid circular imports.
"""
import os
import logging
import secrets
import string
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from pydantic_settings import BaseSettings
from supabase import create_client, Client

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# ============== SETTINGS ==============

class Settings(BaseSettings):
    supabase_url: str = os.environ.get('SUPABASE_URL', '')
    supabase_anon_key: str = os.environ.get('SUPABASE_ANON_KEY', '')
    supabase_service_role_key: str = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
    supabase_jwt_secret: str = os.environ.get('SUPABASE_JWT_SECRET', '')
    super_admin_email: str = os.environ.get('SUPER_ADMIN_EMAIL', '')
    super_admin_password: str = os.environ.get('SUPER_ADMIN_PASSWORD', '')

settings = Settings()

# ============== SUPABASE CLIENTS ==============

supabase_user: Client = create_client(settings.supabase_url, settings.supabase_anon_key)
supabase_admin: Client = create_client(settings.supabase_url, settings.supabase_service_role_key)
# Backwards-compat alias used in some legacy modules
supabase_anon: Client = supabase_user
# Shorthand for DB operations (service role bypasses RLS)
sdb = supabase_admin

# ============== POSTGRES DDL CONNECTION (for migrations) ==============
# supabase-py only supports PostgREST (DML). For DDL (CREATE/DROP/ALTER TABLE,
# RLS policies, indices, etc.) use this direct pooler connection.

_db_url = os.environ.get('SUPABASE_DB_URL', '')

def run_sql(sql: str, params: tuple | None = None, fetch: bool = False):
    """Execute raw SQL against the Supabase Postgres pooler.

    Use ONLY for DDL or one-off admin queries — for regular CRUD use `sdb.table(...)`.
    Returns rows when fetch=True, else None. Auto-commits each call.
    """
    if not _db_url:
        raise RuntimeError("SUPABASE_DB_URL is not configured in backend/.env")
    import psycopg2
    conn = psycopg2.connect(_db_url, connect_timeout=10)
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(sql, params)
            if fetch and cur.description:
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]
            return None
    finally:
        conn.close()

# ============== LOGGING ==============

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("clinic_crm")

# ============== HTTP SECURITY ==============

security = HTTPBearer(auto_error=False)

# ============== HELPERS ==============

def generate_slug(name: str) -> str:
    slug = name.lower().replace(" ", "-").replace(".", "").replace(",", "")
    return ''.join(c for c in slug if c.isalnum() or c == '-')

def generate_password(length: int = 14) -> str:
    """Generate a random password that satisfies services.password_policy.

    - length >= 10 (default 14 for extra margin)
    - guaranteed one char from each of the 4 categories (satisfies >=3)
    - never touches the common-passwords list because it's fully random
    """
    if length < 10:
        length = 10
    upper = string.ascii_uppercase
    lower = string.ascii_lowercase
    digits = string.digits
    symbols = "!@#$%^&*_-+="
    # Guarantee at least one from each category
    required = [
        secrets.choice(upper),
        secrets.choice(lower),
        secrets.choice(digits),
        secrets.choice(symbols),
    ]
    pool = upper + lower + digits + symbols
    remaining = [secrets.choice(pool) for _ in range(length - len(required))]
    chars = required + remaining
    # Shuffle securely (secrets.SystemRandom())
    secrets.SystemRandom().shuffle(chars)
    return ''.join(chars)

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


def get_clinic_day_hours(clinic_row: dict, iso_dow: int) -> list | None:
    """Return list of (start_hhmmss, end_hhmmss) blocks for the given iso weekday
    (1=Mon..7=Sun). Each block represents an open period; multiple blocks support
    split schedules (e.g. 08:00-12:00 + 14:00-18:00).

    Resolution order:
      1) `working_hours` JSON. Each day value can be:
         - a list of blocks: `[{"start":"08:00","end":"12:00"}, {"start":"14:00","end":"18:00"}]`
         - a single block dict: `{"start":"08:00","end":"17:00"}` (backward compat)
         - presence of the key with valid block(s) = open; absence = closed.
      2) Fallback to legacy `working_days` + `schedule_start`/`schedule_end`.

    Returns None if the clinic is closed that day.
    """
    def _norm(v: str) -> str:
        v = (v or '').strip()
        if not v:
            return ''
        return v + ":00" if len(v) == 5 else v

    def _block(b: dict) -> tuple | None:
        if not isinstance(b, dict):
            return None
        s = _norm(b.get('start', ''))
        e = _norm(b.get('end', ''))
        if not s or not e:
            return None
        return (s, e)

    wh = clinic_row.get('working_hours') or None
    if isinstance(wh, dict) and wh:
        entry = wh.get(str(iso_dow)) or wh.get(iso_dow)
        if not entry:
            return None
        if isinstance(entry, list):
            blocks = [b for b in (_block(x) for x in entry) if b]
            return blocks or None
        if isinstance(entry, dict):
            b = _block(entry)
            return [b] if b else None
        return None
    # Fallback to legacy fields
    days = clinic_row.get('working_days') or [1, 2, 3, 4, 5]
    if iso_dow not in days:
        return None
    s = clinic_row.get('schedule_start') or '08:00:00'
    e = clinic_row.get('schedule_end') or '17:00:00'
    return [(s, e)]

# Cache for clinic logo bytes during a single process lifetime (per logo_url)
_logo_cache: dict = {}

def fetch_clinic_logo_image(logo_url: str | None, max_h_mm: float = 18.0):
    """Return a reportlab Image flowable (centered) for the clinic logo, or None.

    Downloads the logo bytes once per URL (cached in process memory) so repeated
    PDF generations don't re-fetch. Falls back to None on any failure so PDF
    generation never breaks because of a missing/broken logo.
    """
    if not logo_url:
        return None
    try:
        from reportlab.platypus import Image as RLImage
        from reportlab.lib.units import mm
        import io as _io
        import httpx
        if logo_url in _logo_cache:
            data = _logo_cache[logo_url]
        else:
            r = httpx.get(logo_url, timeout=8.0, follow_redirects=True)
            if r.status_code != 200 or not r.content:
                return None
            data = r.content
            _logo_cache[logo_url] = data
        img = RLImage(_io.BytesIO(data))
        # Constrain to max height keeping aspect ratio
        try:
            iw, ih = img.imageWidth, img.imageHeight
            target_h = max_h_mm * mm
            scale = target_h / float(ih) if ih else 1
            img.drawHeight = target_h
            img.drawWidth = float(iw) * scale
            # Cap width to avoid super-wide logos breaking layout
            max_w = 80 * mm
            if img.drawWidth > max_w:
                img.drawWidth = max_w
                img.drawHeight = max_w * (float(ih) / float(iw)) if iw else target_h
        except Exception:
            pass
        img.hAlign = 'CENTER'
        return img
    except Exception as e:
        logger.warning(f"fetch_clinic_logo_image failed for {logo_url[:60]}…: {e}")
        return None

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

# ============== AUTH DEPENDENCIES ==============

# Cookie name used by Fix #5 (httpOnly Secure cookie containing the access token).
# Kept in sync with the value the /auth/login endpoint sets.
ACCESS_TOKEN_COOKIE = "cortexia_access_token"


class _LocalAuthUser:
    """Minimal user object returned by local JWT validation.

    Exposes `.id` and `.email` so existing call sites (`user.id`, `user.email`)
    keep working without changes. The Supabase Python SDK returns a richer
    object, but downstream code only reads these two attributes.
    """
    __slots__ = ("id", "email", "role", "aud")

    def __init__(self, sub: str, email: str | None, role: str | None, aud: str | None):
        self.id = sub
        self.email = email
        self.role = role
        self.aud = aud


# JWKS cache: lazily fetched on first use, kept in memory for the process lifetime.
# Refreshed on demand if a token's `kid` is not in the current cache (handles
# Supabase key rotation transparently). For safety we also TTL-refresh hourly.
import time as _time
_JWKS_CACHE: dict = {"keys_by_kid": {}, "fetched_at": 0}
_JWKS_TTL = 3600  # 1h


def _fetch_jwks(force: bool = False) -> dict:
    """Fetch (or return cached) JWKS keys keyed by kid."""
    now = _time.time()
    if not force and _JWKS_CACHE["keys_by_kid"] and (now - _JWKS_CACHE["fetched_at"]) < _JWKS_TTL:
        return _JWKS_CACHE["keys_by_kid"]
    try:
        import httpx
        url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
        r = httpx.get(url, timeout=5.0)
        r.raise_for_status()
        payload = r.json()
        keys = {k["kid"]: k for k in payload.get("keys", []) if k.get("kid")}
        if keys:
            _JWKS_CACHE["keys_by_kid"] = keys
            _JWKS_CACHE["fetched_at"] = now
        return _JWKS_CACHE["keys_by_kid"]
    except Exception as e:
        logger.warning(f"JWKS fetch failed: {e}; using cached keys ({len(_JWKS_CACHE['keys_by_kid'])})")
        return _JWKS_CACHE["keys_by_kid"]


def _decode_jwt_local(token: str):
    """Decode a Supabase JWT locally.

    Supports two signature schemes:
      - ES256 / RS256 via JWKS (modern Supabase projects, default since 2025)
      - HS256 via SUPABASE_JWT_SECRET (legacy projects)

    For ES256/RS256: we pick the public key by the token's `kid` header from
    a cached JWKS (auto-refreshed on cache-miss). For HS256: we use the
    shared secret from env. Either way, validation is fully local — no HTTP
    call to Supabase Auth per request.
    """
    try:
        from jose import jwt as _jose_jwt, JWTError
        # Read the alg + kid from the unverified header to pick the verification path
        unverified_header = _jose_jwt.get_unverified_header(token)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token malformado: {str(e)[:80]}")

    alg = unverified_header.get("alg")
    kid = unverified_header.get("kid")

    try:
        if alg in ("ES256", "RS256", "ES384", "RS384"):
            # Asymmetric — fetch the matching public key from JWKS
            keys = _fetch_jwks()
            jwk = keys.get(kid)
            if not jwk:
                # kid not in cache → force refresh once
                keys = _fetch_jwks(force=True)
                jwk = keys.get(kid)
            if not jwk:
                raise HTTPException(status_code=401, detail="Clave de firma desconocida")
            payload = _jose_jwt.decode(
                token,
                jwk,
                algorithms=[alg],
                audience="authenticated",
                options={"verify_aud": True},
            )
        elif alg == "HS256":
            if not settings.supabase_jwt_secret:
                raise HTTPException(status_code=500, detail="SUPABASE_JWT_SECRET no configurado")
            payload = _jose_jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
                options={"verify_aud": True},
            )
        else:
            raise HTTPException(status_code=401, detail=f"Algoritmo no soportado: {alg}")
    except HTTPException:
        raise
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Token invalido: {str(e)[:80]}")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Error de validación de token: {str(e)[:80]}")

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Token sin sujeto")
    return _LocalAuthUser(
        sub=sub,
        email=payload.get("email"),
        role=payload.get("role"),
        aud=payload.get("aud"),
    )


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
):
    """Resolve the current auth user.

    Token source priority:
      1. `Authorization: Bearer <jwt>` header (current frontend usage)
      2. `cortexia_access_token` httpOnly cookie (Fix #5 — XSS-resistant)

    Validation is done **locally** with ES256/JWKS (or HS256/secret fallback).
    No HTTP call to Supabase Auth per request. Brings latency from ~150ms to
    ~1ms and makes the app immune to Supabase Auth outages for authenticated
    flows.
    """
    token = credentials.credentials if credentials else None
    if not token:
        token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="No autenticado")
    return _decode_jwt_local(token)

async def require_super_admin(user=Depends(get_current_user)):
    result = sdb.table('super_admins').select('id').eq('user_id', user.id).execute()
    if not result.data:
        raise HTTPException(status_code=403, detail="Super admin access required")
    return user

async def require_clinic_member(user=Depends(get_current_user)):
    result = sdb.table('clinic_members').select(
        'id,clinic_id,role,first_name,last_name'
    ).eq('user_id', user.id).eq('is_active', True).maybe_single().execute()
    if not result.data:
        raise HTTPException(status_code=403, detail="Acceso de miembro de clinica requerido")
    return {"auth_user": user, "member": result.data}

CLINICAL_ROLES = ["doctor", "clinic_admin"]

def require_clinical_role(ctx):
    """Restrict an endpoint to clinical roles (doctor / clinic_admin)."""
    role = ctx["member"].get("role", "")
    if role not in CLINICAL_ROLES:
        raise HTTPException(status_code=403, detail="Acceso restringido a médicos y administradores clínicos")
    return ctx

async def require_clinic_admin(ctx=Depends(require_clinic_member)):
    """Restrict an endpoint to clinic_admin only. Use for sensitive bulk/destructive ops."""
    role = ctx["member"].get("role", "")
    if role != "clinic_admin":
        raise HTTPException(status_code=403, detail="Acceso restringido a administradores de clínica")
    return ctx

def validate_uuid(value: str, label: str = "ID") -> str:
    """Validate a path-param UUID. Returns the value unchanged or raises HTTP 422."""
    try:
        uuid.UUID(str(value))
        return value
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(status_code=422, detail=f"{label} inválido (UUID requerido)")

def get_clinic_features(clinic_id: str) -> set:
    """Resolve the active feature codes for a clinic (plan + overrides)."""
    try:
        clinic = sdb.table('clinics').select('plan').eq('id', clinic_id).maybe_single().execute()
        clinic_data = getattr(clinic, 'data', None) if clinic else None
        plan_code = (clinic_data or {}).get('plan', 'basic')

        plan_features = set()
        plan = sdb.table('plans').select('id').eq('code', plan_code).maybe_single().execute()
        plan_data = getattr(plan, 'data', None) if plan else None
        if plan_data:
            pf = sdb.table('plan_features').select('feature_id').eq('plan_id', plan_data['id']).execute()
            ids = [r['feature_id'] for r in (pf.data or [])]
            if ids:
                feats = sdb.table('features').select('code').in_('id', ids).eq('is_active', True).execute()
                plan_features = {f['code'] for f in (feats.data or [])}

        overrides = sdb.table('clinic_feature_overrides').select('feature_id,is_enabled').eq('clinic_id', clinic_id).execute()
        if overrides.data:
            ids = [o['feature_id'] for o in overrides.data]
            if ids:
                feats = sdb.table('features').select('id,code').in_('id', ids).execute()
                id_to_code = {f['id']: f['code'] for f in (feats.data or [])}
                for o in overrides.data:
                    code = id_to_code.get(o['feature_id'])
                    if not code:
                        continue
                    if o['is_enabled']:
                        plan_features.add(code)
                    else:
                        plan_features.discard(code)
        return plan_features
    except Exception as e:
        logger.error(f"get_clinic_features error: {e}")
        return set()

# ============== PYDANTIC MODELS ==============

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

class AppointmentCreate(BaseModel):
    patient_id: str
    doctor_id: str
    starts_at: str
    duration_minutes: int = 30
    reason: Optional[str] = None
    notes: Optional[str] = None
    branch_id: Optional[str] = None

class AppointmentUpdate(BaseModel):
    starts_at: Optional[str] = None
    duration_minutes: Optional[int] = None
    reason: Optional[str] = None
    notes: Optional[str] = None
    doctor_id: Optional[str] = None
    branch_id: Optional[str] = None

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
