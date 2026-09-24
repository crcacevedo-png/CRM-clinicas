"""FastAPI app entrypoint. Mounts all route modules under /api.

Heavy lifting (Supabase clients, settings, models, helpers, auth deps) lives in core.py
to keep this module thin and avoid circular imports.
"""
import os
import uuid
from fastapi import FastAPI, APIRouter, Depends, Request
from starlette.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from core import (
    settings, sdb, supabase_admin, logger, now_iso,
    require_super_admin, generate_password,
)

# ============== APP ==============

app = FastAPI(title="Clinic CRM Super Admin API")
api_router = APIRouter(prefix="/api")

# ============== RATE LIMITING ==============
# slowapi limiter keyed by client IP. Use a trusted-proxy aware extractor so
# X-Forwarded-For from the ingress is honored. The limiter is attached to the
# app and exposed via app.state.limiter so route decorators can reference it.

def _trusted_remote_address(request: Request) -> str:
    """Return the real client IP, trusting XFF only from known proxy CIDRs."""
    from core import client_ip
    ip = client_ip(request)
    if ip and ip != "unknown":
        return ip
    return get_remote_address(request)

limiter = Limiter(key_func=_trusted_remote_address, default_limits=[])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ============== STARTUP ==============

@app.on_event("startup")
async def startup_event():
    """Initialize super admin on startup"""
    try:
        import os as _os
        import anyio.to_thread
        tokens = int(_os.environ.get("THREADPOOL_TOKENS", "128"))
        anyio.to_thread.current_default_thread_limiter().total_tokens = tokens
        logger.info(f"AnyIO threadpool capacity set to {tokens}")
    except Exception as e:
        logger.warning(f"Could not raise threadpool capacity: {e}")
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
    system_health as _r_health,
    whatsapp_share as _r_wa,
    agenda_blocks as _r_ab,
    roles as _r_roles,
    quick_start as _r_qs,
    user_guide as _r_guide,
)
from core import require_module

# Routers with no module-level gate: auth, super-admin, shared lookups/config,
# appointments (agenda gated per-endpoint), patients (gated per-endpoint), etc.
for _r in (
    _r_auth, _r_sa, _r_cat, _r_cs, _r_br, _r_ff,
    _r_pat, _r_apt, _r_gc,
    _r_exp_full, _r_ann, _r_metrics, _r_audit, _r_health, _r_wa, _r_roles, _r_qs, _r_guide,
):
    api_router.include_router(_r.router)

# Module-gated routers — menu-level RBAC enforced in the backend. A role must
# have the module enabled (clinic_admin always bypasses) or every route 403s.
api_router.include_router(_r_mr.router, dependencies=[Depends(require_module('patients'))])
api_router.include_router(_r_pr.router, dependencies=[Depends(require_module('prescriptions'))])
api_router.include_router(_r_lab.router, dependencies=[Depends(require_module('lab_orders'))])
api_router.include_router(_r_inv.router, dependencies=[Depends(require_module('inventory'))])
api_router.include_router(_r_exp.router, dependencies=[Depends(require_module('expenses'))])
api_router.include_router(_r_comm.router, dependencies=[Depends(require_module('commissions'))])
api_router.include_router(_r_sales.router, dependencies=[Depends(require_module('sales'))])
api_router.include_router(_r_ar.router, dependencies=[Depends(require_module('accounts_receivable'))])
api_router.include_router(_r_rep.router, dependencies=[Depends(require_module('reports'))])
api_router.include_router(_r_ab.router, dependencies=[Depends(require_module('agenda'))])

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
    # API returns JSON/redirects only — lock CSP down tightly. The SPA's own CSP
    # (which needs to allow scripts/styles) is declared as a meta tag in index.html.
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
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
