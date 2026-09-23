"""Auto-extracted from server.py."""
import os
import uuid
import logging
from datetime import datetime, timezone, timedelta, date
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Body, Request
from pydantic import BaseModel

router = APIRouter()

from core import (
    sdb, supabase_admin, supabase_user, logger, now_iso,
    generate_password, generate_slug, enrich_member, get_auth_users_map,
    get_plan_limits, parse_presentations,
    require_clinic_member, require_super_admin, get_current_user,
    LoginRequest, LoginResponse, ClinicCreate, ClinicUpdate, ClinicMemberCreate, UserUpdate,
    MedicationCreate, MedicationBulkImport, LabStudyCreate, LabStudyBulkImport,
    ICD10CodeCreate, ICD10BulkImport,
    AppointmentCreate, AppointmentUpdate, AppointmentStatusUpdate,
    PatientQuickCreate, PatientFullCreate,
)

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

# --- OAuth state signing (CSRF protection) ---
# The `state` param is signed with an HMAC bound to the initiating user and a
# short TTL. The callback rejects any state it did not sign, so an attacker
# cannot inject a victim's user_id and hijack their calendar sync.
import hmac as _hmac
import json as _json
import time as _time
import secrets as _secrets


def _oauth_state_secret() -> bytes:
    raw = os.environ.get('ENCRYPTION_KEY', 'default-key-change-me')
    return hashlib.sha256(('oauth-state:' + raw).encode()).digest()


def _sign_oauth_state(user_id: str, ttl: int = 600) -> str:
    payload = {"uid": user_id, "exp": int(_time.time()) + ttl, "n": _secrets.token_urlsafe(6)}
    body = base64.urlsafe_b64encode(_json.dumps(payload).encode()).decode().rstrip('=')
    sig = _hmac.new(_oauth_state_secret(), body.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{body}.{sig}"


def _verify_oauth_state(state: str):
    """Return the user_id embedded in a valid, unexpired state, else None."""
    try:
        body, sig = (state or "").split('.', 1)
    except (ValueError, AttributeError):
        return None
    expected = _hmac.new(_oauth_state_secret(), body.encode(), hashlib.sha256).hexdigest()[:32]
    if not _hmac.compare_digest(sig, expected):
        return None
    try:
        pad = '=' * (-len(body) % 4)
        payload = _json.loads(base64.urlsafe_b64decode(body + pad))
    except Exception:
        return None
    if int(payload.get('exp', 0)) < int(_time.time()):
        return None
    return payload.get('uid')


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
    # Disable PKCE: we're a confidential client (server-side with client_secret),
    # and PKCE requires preserving the code_verifier between the auth-url and
    # callback requests, which fails because they are separate Flow instances.
    flow.autogenerate_code_verifier = False
    flow.code_verifier = None
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

@router.get("/google-calendar/auth-url")
async def google_calendar_auth_url(ctx=Depends(require_clinic_member)):
    """Generate Google OAuth2 authorization URL"""
    user_id = ctx["auth_user"].id
    try:
        flow = get_google_flow()
        auth_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent',
            state=_sign_oauth_state(user_id),
        )
        return {"auth_url": auth_url}
    except Exception as e:
        logger.error(f"Google auth URL error: {e}")
        raise HTTPException(status_code=500, detail="Error al generar URL de autenticación")

@router.get("/google-calendar/callback")
async def google_calendar_callback(code: str = "", state: str = "", error: str = ""):
    """Handle Google OAuth2 callback"""
    if error:
        logger.error(f"Google callback error: {error}")
        frontend_url = os.environ.get('GOOGLE_REDIRECT_URI', '').replace('/api/google-calendar/callback', '')
        return RedirectResponse(url=f"{frontend_url}/dashboard?gcal_error=denied")

    if not code or not state:
        return RedirectResponse(url="/dashboard?gcal_error=missing_params")

    # Verify the signed state — rejects forged/expired states (CSRF protection)
    user_id = _verify_oauth_state(state)
    if not user_id:
        frontend_url = os.environ.get('GOOGLE_REDIRECT_URI', '').replace('/api/google-calendar/callback', '')
        return RedirectResponse(url=f"{frontend_url}/dashboard?gcal_error=invalid_state")
    try:
        flow = get_google_flow()
        flow.fetch_token(code=code)
        credentials = flow.credentials

        enc_access = encrypt_token(credentials.token)
        enc_refresh = encrypt_token(credentials.refresh_token or "")
        expires_at = credentials.expiry.isoformat() if credentials.expiry else None

        # Check if integration exists
        existing = sdb.table('user_integrations').select('id').eq('user_id', user_id).eq('provider', 'google_calendar').maybe_single().execute()
        existing_data = getattr(existing, 'data', None) if existing else None

        now = now_iso()
        if existing_data:
            sdb.table('user_integrations').update({
                "access_token": enc_access,
                "refresh_token": enc_refresh,
                "token_expires_at": expires_at,
                "is_active": True,
                "calendar_id": "primary",
                "updated_at": now,
            }).eq('id', existing_data['id']).execute()
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

@router.get("/google-calendar/status")
async def google_calendar_status(ctx=Depends(require_clinic_member)):
    """Check if current user has Google Calendar connected"""
    user_id = ctx["auth_user"].id
    try:
        result = sdb.table('user_integrations').select('id,is_active,calendar_id,created_at').eq('user_id', user_id).eq('provider', 'google_calendar').maybe_single().execute()
        data = getattr(result, 'data', None) if result else None
        if data and data.get('is_active'):
            return {"connected": True, "calendar_id": data.get('calendar_id', 'primary'), "since": data.get('created_at')}
        return {"connected": False}
    except Exception as e:
        logger.error(f"Google calendar status error: {e}")
        return {"connected": False}

@router.get("/google-calendar/calendars")
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

@router.put("/google-calendar/settings")
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

@router.delete("/google-calendar/disconnect")
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

async def _push_to_gcal_for_user(user_id: str, appointment_data: dict, action: str, target_label: str = ""):
    """Sync a single appointment to a single user's Google Calendar.

    Returns the google_event_id created/updated, or None on no-op.
    Logs (info) success and (error) failures, never raises.
    """
    try:
        integration = sdb.table('user_integrations').select('*').eq('user_id', user_id).eq('provider', 'google_calendar').eq('is_active', True).maybe_single().execute()
        integ_data = getattr(integration, 'data', None) if integration else None
        if not integ_data:
            return None

        access_token = decrypt_token(integ_data.get('access_token', ''))
        refresh_token = decrypt_token(integ_data.get('refresh_token', ''))
        if not access_token:
            return None

        calendar_id = integ_data.get('calendar_id') or 'primary'
        service, creds = get_google_service(access_token, refresh_token)

        # Persist refreshed access token if changed
        if creds.token and creds.token != access_token:
            sdb.table('user_integrations').update({
                "access_token": encrypt_token(creds.token),
                "token_expires_at": creds.expiry.isoformat() if creds.expiry else None,
                "updated_at": now_iso(),
            }).eq('id', integ_data['id']).execute()

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
            logger.info(f"GCal event created [{target_label}]: {event_id}")
            return event_id

        if action == "update":
            google_event_id = appointment_data.get('google_event_id')
            if google_event_id:
                try:
                    service.events().update(calendarId=calendar_id, eventId=google_event_id, body=event_body).execute()
                    logger.info(f"GCal event updated [{target_label}]: {google_event_id}")
                    return google_event_id
                except Exception as e:
                    # Event missing on this calendar — try to insert as new
                    if 'Not Found' in str(e) or '404' in str(e):
                        event = service.events().insert(calendarId=calendar_id, body=event_body).execute()
                        new_id = event.get('id')
                        logger.info(f"GCal event recreated [{target_label}]: {new_id}")
                        return new_id
                    raise

        if action == "delete":
            google_event_id = appointment_data.get('google_event_id')
            if google_event_id:
                try:
                    service.events().delete(calendarId=calendar_id, eventId=google_event_id).execute()
                    logger.info(f"GCal event deleted [{target_label}]: {google_event_id}")
                except Exception as e:
                    logger.warning(f"GCal delete skipped [{target_label}]: {e}")
            return None

    except Exception as e:
        logger.error(f"GCal push failed [{target_label}] user={user_id}: {e}")
        return None


async def sync_appointment_to_gcal(appointment_data: dict, action: str = "create"):
    """Sync an appointment to Google Calendar.

    Strategy: try the doctor's calendar first (so the doctor sees their
    schedule on their phone). If the doctor has not connected, fall back to
    the appointment's creator (e.g., a receptionist or clinic_admin who set
    up the appointment) so the user who connected GCal actually sees it.
    Stores the resulting `google_event_id` in `appointments`.
    """
    try:
        targets = []  # list of (user_id, label)
        seen_users = set()

        # Target 1: doctor's user
        doctor_id = appointment_data.get('doctor_id')
        if doctor_id:
            member = sdb.table('clinic_members').select('user_id').eq('id', doctor_id).maybe_single().execute()
            mdata = getattr(member, 'data', None) if member else None
            doc_uid = (mdata or {}).get('user_id')
            if doc_uid:
                targets.append((doc_uid, "doctor"))
                seen_users.add(doc_uid)

        # Target 2: creator's user (only if different from doctor, and present)
        created_by = appointment_data.get('created_by')
        if created_by:
            creator_member = sdb.table('clinic_members').select('user_id').eq('id', created_by).maybe_single().execute()
            cdata = getattr(creator_member, 'data', None) if creator_member else None
            creator_uid = (cdata or {}).get('user_id')
            if creator_uid and creator_uid not in seen_users:
                targets.append((creator_uid, "creator"))
                seen_users.add(creator_uid)

        if not targets:
            return

        primary_event_id = None
        for uid, label in targets:
            evt_id = await _push_to_gcal_for_user(uid, appointment_data, action, target_label=label)
            # Persist the first non-null event_id (used to update/delete later)
            if evt_id and not primary_event_id and action == "create":
                primary_event_id = evt_id

        if primary_event_id and appointment_data.get('id'):
            sdb.table('appointments').update({"google_event_id": primary_event_id}).eq('id', appointment_data['id']).execute()

    except Exception as e:
        logger.error(f"Google Calendar sync error: {e}")

# === Routes moved to routes/inventory.py ===
