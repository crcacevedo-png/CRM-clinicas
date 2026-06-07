"""FastAPI app entrypoint. Mounts all route modules under /api.

Heavy lifting (Supabase clients, settings, models, helpers, auth deps) lives in core.py
to keep this module thin and avoid circular imports.
"""
import os
import uuid
from fastapi import FastAPI, APIRouter, Depends
from starlette.middleware.cors import CORSMiddleware

from core import (
    settings, sdb, supabase_admin, logger, now_iso,
    require_super_admin, generate_password,
)

# ============== APP ==============

app = FastAPI(title="Clinic CRM Super Admin API")
api_router = APIRouter(prefix="/api")

# ============== STARTUP ==============

@app.on_event("startup")
async def startup_event():
    """Initialize super admin on startup"""
    try:
        result = sdb.table('super_admins').select('id').eq('email', settings.super_admin_email).execute()
        if result.data:
            return
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

    # Apply pending DDL migrations (idempotent, defensive)
    try:
        from services.migrations import run_pending_migrations
        result = run_pending_migrations()
        if result.get('applied'):
            logger.info(f"Migrations applied: {result['applied']}")
    except Exception as e:
        logger.warning(f"Migrations runner failed (will retry next startup): {e}")

    # Start background scheduler for appointment reminders (non-blocking)
    try:
        from services.reminder_scheduler import start_scheduler
        start_scheduler()
    except Exception as e:
        logger.warning(f"Reminder scheduler failed to start: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    try:
        from services.reminder_scheduler import stop_scheduler
        stop_scheduler()
    except Exception:
        pass

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

# ============== INCLUDE ROUTERS ==============

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
    clinic_export as _r_exp_full,
    announcements as _r_ann,
    admin_metrics as _r_metrics,
    audit_log as _r_audit,
)
for _r in (
    _r_auth, _r_sa, _r_cat, _r_cs, _r_br, _r_ff,
    _r_pat, _r_apt, _r_mr, _r_pr, _r_lab, _r_gc,
    _r_inv, _r_exp, _r_comm, _r_sales, _r_ar, _r_rep,
    _r_exp_full, _r_ann, _r_metrics, _r_audit,
):
    api_router.include_router(_r.router)

app.include_router(api_router)

# ============== SECURITY HEADERS ==============

@app.middleware("http")
async def security_headers_middleware(request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return response

# ============== CORS ==============

# CORS_ORIGINS MUST be set in .env as comma-separated allowlist. We refuse to
# fall back to '*' because allow_credentials=True + '*' is insecure (and rejected
# by modern browsers anyway). Failing fast surfaces the misconfig immediately.
_cors_env = os.environ.get('CORS_ORIGINS', '').strip()
if not _cors_env:
    raise RuntimeError(
        "CORS_ORIGINS env var is required. Set it to a comma-separated list of "
        "allowed origins, e.g. 'https://app.cortexiamedical.com,https://app2.example.com'."
    )
_allowed_origins = [o.strip() for o in _cors_env.split(',') if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=_allowed_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin", "X-Requested-With"],
)
