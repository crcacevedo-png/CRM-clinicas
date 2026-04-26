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
            state=user_id,
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

    user_id = state
    try:
        flow = get_google_flow()
        flow.fetch_token(code=code)
        credentials = flow.credentials

        enc_access = encrypt_token(credentials.token)
        enc_refresh = encrypt_token(credentials.refresh_token or "")
        expires_at = credentials.expiry.isoformat() if credentials.expiry else None

        # Check if integration exists
        existing = sdb.table('user_integrations').select('id').eq('user_id', user_id).eq('provider', 'google_calendar').maybe_single().execute()

        now = now_iso()
        if existing.data:
            sdb.table('user_integrations').update({
                "access_token": enc_access,
                "refresh_token": enc_refresh,
                "token_expires_at": expires_at,
                "is_active": True,
                "calendar_id": "primary",
                "updated_at": now,
            }).eq('id', existing.data['id']).execute()
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
        if result.data and result.data.get('is_active'):
            return {"connected": True, "calendar_id": result.data.get('calendar_id', 'primary'), "since": result.data.get('created_at')}
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

async def sync_appointment_to_gcal(appointment_data: dict, action: str = "create"):
    """Sync an appointment to Google Calendar for the doctor"""
    try:
        doctor_id = appointment_data.get('doctor_id')
        if not doctor_id:
            return

        # Get doctor's user_id
        member = sdb.table('clinic_members').select('user_id').eq('id', doctor_id).maybe_single().execute()
        if not member.data or not member.data.get('user_id'):
            return

        user_id = member.data['user_id']

        # Check if doctor has active Google Calendar integration
        integration = sdb.table('user_integrations').select('*').eq('user_id', user_id).eq('provider', 'google_calendar').eq('is_active', True).maybe_single().execute()
        if not integration.data:
            return

        access_token = decrypt_token(integration.data.get('access_token', ''))
        refresh_token = decrypt_token(integration.data.get('refresh_token', ''))
        if not access_token:
            return

        calendar_id = integration.data.get('calendar_id') or 'primary'

        service, creds = get_google_service(access_token, refresh_token)

        # Update tokens if refreshed
        if creds.token != access_token:
            sdb.table('user_integrations').update({
                "access_token": encrypt_token(creds.token),
                "token_expires_at": creds.expiry.isoformat() if creds.expiry else None,
                "updated_at": now_iso(),
            }).eq('id', integration.data['id']).execute()

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
            if event_id:
                sdb.table('appointments').update({"google_event_id": event_id}).eq('id', appointment_data['id']).execute()
            logger.info(f"Google Calendar event created: {event_id}")

        elif action == "update":
            google_event_id = appointment_data.get('google_event_id')
            if google_event_id:
                service.events().update(calendarId=calendar_id, eventId=google_event_id, body=event_body).execute()
                logger.info(f"Google Calendar event updated: {google_event_id}")

        elif action == "delete":
            google_event_id = appointment_data.get('google_event_id')
            if google_event_id:
                try:
                    service.events().delete(calendarId=calendar_id, eventId=google_event_id).execute()
                    logger.info(f"Google Calendar event deleted: {google_event_id}")
                except Exception:
                    pass

    except Exception as e:
        logger.error(f"Google Calendar sync error: {e}")

# === Routes moved to routes/inventory.py ===
