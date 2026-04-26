"""Auto-extracted from server.py."""
import uuid
import logging
from datetime import datetime, timezone, timedelta, date
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Body, Request
from pydantic import BaseModel

router = APIRouter()

# Shared deps from server module (imported at file-load time, after server.py finishes init)
from server import (
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

# ============== APPOINTMENT ROUTES ==============

@router.get("/clinic/appointments")
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

@router.post("/clinic/appointments")
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

        # Sync to Google Calendar (non-blocking)
        try:
            await sync_appointment_to_gcal(doc, "create")
        except Exception as gcal_err:
            logger.warning(f"Google Calendar sync failed (create): {gcal_err}")

        return doc
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create appointment error: {e}")
        raise HTTPException(status_code=500, detail="Error al crear cita")

@router.put("/clinic/appointments/{apt_id}")
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

        # Sync to Google Calendar (non-blocking)
        try:
            await sync_appointment_to_gcal(apt, "update")
        except Exception as gcal_err:
            logger.warning(f"Google Calendar sync failed (update): {gcal_err}")

        return apt
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update appointment error: {e}")
        raise HTTPException(status_code=500, detail="Error al actualizar cita")

@router.put("/clinic/appointments/{apt_id}/status")
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

        # If cancelled, delete from Google Calendar
        if data.status == "cancelled":
            try:
                apt_full = sdb.table('appointments').select('id,doctor_id,google_event_id').eq('id', apt_id).maybe_single().execute()
                if apt_full.data and apt_full.data.get('google_event_id'):
                    await sync_appointment_to_gcal(apt_full.data, "delete")
            except Exception as gcal_err:
                logger.warning(f"Google Calendar sync failed (cancel): {gcal_err}")

        return {"message": "Estado actualizado", "status": data.status}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Change status error: {e}")
        raise HTTPException(status_code=500, detail="Error al cambiar estado")



@router.get("/clinic/dashboard")
async def clinic_dashboard_stats(ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        from datetime import datetime as dt, timedelta
        now = dt.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        month_start = today_start.replace(day=1)

        # Today's appointments
        today_apts = sdb.table('appointments').select('*').eq('clinic_id', clinic_id).gte('starts_at', today_start.isoformat()).lt('starts_at', today_end.isoformat()).neq('status', 'cancelled').order('starts_at').execute()
        apts = today_apts.data or []

        pending_today = len([a for a in apts if a.get('status') in ('scheduled', 'confirmed')])

        # Next upcoming appointment
        next_apt = None
        upcoming = sdb.table('appointments').select('*').eq('clinic_id', clinic_id).gte('starts_at', now.isoformat()).neq('status', 'cancelled').order('starts_at').limit(1).execute()
        if upcoming.data:
            next_apt = upcoming.data[0]

        # New patients this month
        new_patients_month = sdb.table('patients').select('id', count='exact').eq('clinic_id', clinic_id).gte('created_at', month_start.isoformat()).execute()

        # Prescriptions issued this month
        rx_month = sdb.table('prescriptions').select('id', count='exact').eq('clinic_id', clinic_id).eq('status', 'issued').gte('issued_at', month_start.isoformat()).execute()

        # Recent patients (last 5 with completed visits)
        recent_apts = sdb.table('appointments').select('patient_id').eq('clinic_id', clinic_id).eq('status', 'completed').order('updated_at', desc=True).limit(10).execute()
        seen_ids = []
        recent_patients = []
        for ra in (recent_apts.data or []):
            pid = ra['patient_id']
            if pid not in seen_ids and len(recent_patients) < 5:
                seen_ids.append(pid)
                p = sdb.table('patients').select('id,first_name,last_name,phone').eq('id', pid).maybe_single().execute()
                if p.data:
                    recent_patients.append(p.data)

        # If not enough from completed, fill with recently created patients
        if len(recent_patients) < 5:
            extra = sdb.table('patients').select('id,first_name,last_name,phone').eq('clinic_id', clinic_id).order('created_at', desc=True).limit(5).execute()
            for p in (extra.data or []):
                if p['id'] not in seen_ids and len(recent_patients) < 5:
                    seen_ids.append(p['id'])
                    recent_patients.append(p)

        # Activity log (recent actions)
        activity = []

        # Recent appointments (created)
        recent_created_apts = sdb.table('appointments').select('id,patient_id,created_at,starts_at').eq('clinic_id', clinic_id).order('created_at', desc=True).limit(5).execute()
        for a in (recent_created_apts.data or []):
            p = sdb.table('patients').select('first_name,last_name').eq('id', a['patient_id']).maybe_single().execute()
            pname = f"{p.data['first_name']} {p.data['last_name']}" if p.data else "Paciente"
            activity.append({
                "type": "appointment",
                "message": f"Cita agendada para {pname}",
                "timestamp": a['created_at'],
            })

        # Recent prescriptions
        recent_rx = sdb.table('prescriptions').select('id,patient_id,created_at,status').eq('clinic_id', clinic_id).eq('status', 'issued').order('created_at', desc=True).limit(5).execute()
        for r in (recent_rx.data or []):
            p = sdb.table('patients').select('first_name,last_name').eq('id', r['patient_id']).maybe_single().execute()
            pname = f"{p.data['first_name']} {p.data['last_name']}" if p.data else "Paciente"
            activity.append({
                "type": "prescription",
                "message": f"Receta emitida para {pname}",
                "timestamp": r['created_at'],
            })

        # Recent patients registered
        recent_pats = sdb.table('patients').select('id,first_name,last_name,created_at').eq('clinic_id', clinic_id).order('created_at', desc=True).limit(5).execute()
        for p in (recent_pats.data or []):
            activity.append({
                "type": "patient",
                "message": f"Paciente registrado: {p['first_name']} {p['last_name']}",
                "timestamp": p['created_at'],
            })

        # Sort activity by timestamp desc, take top 10
        activity.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        activity = activity[:10]

        # Enrich today's appointments
        for apt in apts:
            p = sdb.table('patients').select('first_name,last_name').eq('id', apt["patient_id"]).maybe_single().execute()
            d = sdb.table('clinic_members').select('first_name,last_name').eq('id', apt["doctor_id"]).maybe_single().execute()
            apt["patient_name"] = f"{p.data['first_name']} {p.data['last_name']}" if p.data else ""
            apt["doctor_name"] = f"{d.data['first_name']} {d.data['last_name']}" if d.data else ""

        # Enrich next appointment
        if next_apt:
            p = sdb.table('patients').select('first_name,last_name').eq('id', next_apt["patient_id"]).maybe_single().execute()
            next_apt["patient_name"] = f"{p.data['first_name']} {p.data['last_name']}" if p.data else ""

        return {
            "today_appointments": apts,
            "today_count": len(apts),
            "pending_today": pending_today,
            "new_patients_month": new_patients_month.count or 0,
            "rx_issued_month": rx_month.count or 0,
            "next_appointment": next_apt,
            "recent_patients": recent_patients,
            "activity": activity,
            "current_member": ctx["member"],
        }
    except Exception as e:
        logger.error(f"Clinic dashboard error: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener dashboard")
