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
)
for _r in (
    _r_auth, _r_sa, _r_cat, _r_cs, _r_br, _r_ff,
    _r_pat, _r_apt, _r_mr, _r_pr, _r_lab, _r_gc,
    _r_inv, _r_exp, _r_comm, _r_sales, _r_ar, _r_rep,
    _r_exp_full, _r_ann,
):
    api_router.include_router(_r.router)

app.include_router(api_router)

# ============== CORS ==============

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)
