"""Auto-extracted from server.py."""
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
    get_plan_limits, parse_presentations, get_clinic_day_hours,
    require_clinic_member, require_super_admin, get_current_user,
    LoginRequest, LoginResponse, ClinicCreate, ClinicUpdate, ClinicMemberCreate, UserUpdate,
    MedicationCreate, MedicationBulkImport, LabStudyCreate, LabStudyBulkImport,
    ICD10CodeCreate, ICD10BulkImport,
    AppointmentCreate, AppointmentUpdate, AppointmentStatusUpdate,
    PatientQuickCreate, PatientFullCreate,
    get_clinic_features,
    assert_patient_in_clinic, assert_doctor_in_clinic,
    require_module,
)

# ============== APPOINTMENT ROUTES ==============

@router.get("/clinic/appointments")
async def list_appointments(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    doctor_id: Optional[str] = None,
    status: Optional[str] = None,
    patient_search: Optional[str] = None,
    branch_id: Optional[str] = None,
    ctx=Depends(require_module('agenda'))
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
        if branch_id:
            query = query.eq('branch_id', branch_id)

        result = query.order('starts_at').execute()
        appointments = result.data or []

        # Enrich with patient and doctor names — batch fetched via .in_() to avoid N+1
        patient_ids = list({a["patient_id"] for a in appointments if a.get("patient_id")})
        doctor_ids = list({a["doctor_id"] for a in appointments if a.get("doctor_id")})

        patient_map = {}
        if patient_ids:
            ps = sdb.table('patients').select('id,first_name,last_name').in_('id', patient_ids).execute()
            for p in (ps.data or []):
                patient_map[p['id']] = f"{p['first_name']} {p['last_name']}"

        doctor_map = {}
        if doctor_ids:
            ds = sdb.table('clinic_members').select('id,first_name,last_name').in_('id', doctor_ids).execute()
            for d in (ds.data or []):
                doctor_map[d['id']] = f"{d['first_name']} {d['last_name']}"

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
async def create_appointment(data: AppointmentCreate, ctx=Depends(require_module('agenda'))):
    clinic_id = ctx["member"]["clinic_id"]
    member = ctx["member"]
    try:
        from datetime import datetime as dt, timedelta
        import re

        # Validate branch belongs to this clinic
        if data.branch_id:
            br = sdb.table('branches').select('id').eq('id', data.branch_id).eq('clinic_id', clinic_id).maybe_single().execute()
            if not getattr(br, 'data', None):
                raise HTTPException(status_code=400, detail="Sucursal inválida")

        # Validate patient + doctor belong to this clinic (tenant isolation / IDOR)
        assert_patient_in_clinic(data.patient_id, clinic_id)
        assert_doctor_in_clinic(data.doctor_id, clinic_id)

        starts = dt.fromisoformat(data.starts_at.replace('Z', '+00:00'))
        if starts.tzinfo is None:
            from zoneinfo import ZoneInfo
            starts = starts.replace(tzinfo=ZoneInfo('UTC'))
        ends = starts + timedelta(minutes=data.duration_minutes)

        # Validate clinic hours
        clinic = sdb.table('clinics').select('schedule_start,schedule_end,working_days,working_hours,timezone').eq('id', clinic_id).single().execute()
        c = clinic.data

        # Convert to clinic local time for validation
        from zoneinfo import ZoneInfo
        clinic_tz = ZoneInfo(c.get('timezone') or 'America/Guatemala')
        local_start = starts.astimezone(clinic_tz)
        local_end = ends.astimezone(clinic_tz)

        start_time = local_start.strftime("%H:%M:%S")
        end_time = local_end.strftime("%H:%M:%S")
        day_of_week = local_start.isoweekday()

        day_blocks = get_clinic_day_hours(c, day_of_week)
        if day_blocks is None:
            raise HTTPException(status_code=400, detail="La clinica no opera este dia")
        if not any(start_time >= b[0] and end_time <= b[1] for b in day_blocks):
            ranges = ", ".join(f"{b[0][:5]}-{b[1][:5]}" for b in day_blocks)
            raise HTTPException(status_code=400, detail=f"Fuera del horario de la clinica ({ranges})")

        # Check conflicts for this doctor across ALL branches — a doctor cannot be
        # booked in two places at the same time (their schedule can't overlap).
        conflicts = sdb.table('appointments').select('id,branch_id').eq('clinic_id', clinic_id).eq('doctor_id', data.doctor_id).neq('status', 'cancelled').lt('starts_at', ends.isoformat()).gt('ends_at', starts.isoformat()).execute()
        if conflicts.data:
            raise HTTPException(status_code=409, detail="El médico ya tiene una cita en ese horario (no puede agendarse en dos lugares a la vez)")

        # Reject if the slot falls inside an agenda block (doctor or branch)
        from routes.agenda_blocks import check_agenda_block_conflict
        _blk = check_agenda_block_conflict(clinic_id, data.doctor_id, data.branch_id, starts.isoformat(), ends.isoformat())
        if _blk:
            _lbl = _blk.get('label') or ('Sucursal bloqueada' if _blk.get('scope') == 'branch' else 'Médico no disponible')
            raise HTTPException(status_code=409, detail=f"Horario bloqueado: {_lbl}")

        now = now_iso()
        apt_id = str(uuid.uuid4())
        doc = {
            "id": apt_id,
            "clinic_id": clinic_id,
            "patient_id": data.patient_id,
            "doctor_id": data.doctor_id,
            "branch_id": data.branch_id,
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
            from routes.google_calendar import sync_appointment_to_gcal
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
async def update_appointment(apt_id: str, data: AppointmentUpdate, ctx=Depends(require_module('agenda'))):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        existing = sdb.table('appointments').select('*').eq('id', apt_id).eq('clinic_id', clinic_id).maybe_single().execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Cita no encontrada")

        update_data = {k: v for k, v in data.model_dump().items() if v is not None}

        # Validate branch_id (if provided) belongs to this clinic
        if update_data.get('branch_id'):
            br = sdb.table('branches').select('id').eq('id', update_data['branch_id']).eq('clinic_id', clinic_id).maybe_single().execute()
            if not getattr(br, 'data', None):
                raise HTTPException(status_code=400, detail="Sucursal inválida")

        # Validate doctor (if reassigned) belongs to this clinic
        if update_data.get('doctor_id'):
            assert_doctor_in_clinic(update_data['doctor_id'], clinic_id)

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
            clinic = sdb.table('clinics').select('schedule_start,schedule_end,working_days,working_hours,timezone').eq('id', clinic_id).single().execute()
            c = clinic.data
            clinic_tz = ZoneInfo(c.get('timezone') or 'America/Guatemala')
            local_start = starts.astimezone(clinic_tz)
            local_end = ends.astimezone(clinic_tz)
            start_time = local_start.strftime("%H:%M:%S")
            end_time = local_end.strftime("%H:%M:%S")
            day_of_week = local_start.isoweekday()
            day_blocks = get_clinic_day_hours(c, day_of_week)
            if day_blocks is None:
                raise HTTPException(status_code=400, detail="La clinica no opera este dia")
            if not any(start_time >= b[0] and end_time <= b[1] for b in day_blocks):
                ranges = ", ".join(f"{b[0][:5]}-{b[1][:5]}" for b in day_blocks)
                raise HTTPException(status_code=400, detail=f"Fuera del horario de la clinica ({ranges})")

            doctor_id = update_data.get("doctor_id", existing.data["doctor_id"])
            target_branch = update_data.get("branch_id", existing.data.get("branch_id"))
            # A doctor cannot overlap with their own appointments in ANY branch
            conflicts = sdb.table('appointments').select('id,branch_id').eq('clinic_id', clinic_id).eq('doctor_id', doctor_id).neq('status', 'cancelled').neq('id', apt_id).lt('starts_at', ends.isoformat()).gt('ends_at', starts.isoformat()).execute()
            if conflicts.data:
                raise HTTPException(status_code=409, detail="Conflicto de horario: el médico ya tiene otra cita a esa hora")

            # Reject if the new slot falls inside an agenda block
            from routes.agenda_blocks import check_agenda_block_conflict
            _blk = check_agenda_block_conflict(clinic_id, doctor_id, target_branch, starts.isoformat(), ends.isoformat())
            if _blk:
                _lbl = _blk.get('label') or ('Sucursal bloqueada' if _blk.get('scope') == 'branch' else 'Médico no disponible')
                raise HTTPException(status_code=409, detail=f"Horario bloqueado: {_lbl}")

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
            from routes.google_calendar import sync_appointment_to_gcal
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
async def change_appointment_status(apt_id: str, data: AppointmentStatusUpdate, ctx=Depends(require_module('agenda'))):
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
                    from routes.google_calendar import sync_appointment_to_gcal
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
    member_id = ctx["member"]["id"]
    role = ctx["member"].get("role") or "staff"
    try:
        from datetime import datetime as dt, timedelta, date as dt_date
        now = dt.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        month_start = today_start.replace(day=1)
        today_date = today_start.date()
        month_start_date = today_date.replace(day=1)

        features = get_clinic_features(clinic_id)

        # ===== Common: today's appointments =====
        # Doctors only see their own appointments; admin/cashier/receptionist/assistant see all
        apt_q = sdb.table('appointments').select('*').eq('clinic_id', clinic_id).gte('starts_at', today_start.isoformat()).lt('starts_at', today_end.isoformat()).neq('status', 'cancelled')
        if role == 'doctor':
            apt_q = apt_q.eq('doctor_id', member_id)
        today_apts = apt_q.order('starts_at').execute()
        apts = today_apts.data or []
        pending_today = len([a for a in apts if a.get('status') in ('scheduled', 'confirmed')])

        # Next upcoming appointment
        next_apt = None
        upc_q = sdb.table('appointments').select('*').eq('clinic_id', clinic_id).gte('starts_at', now.isoformat()).neq('status', 'cancelled')
        if role == 'doctor':
            upc_q = upc_q.eq('doctor_id', member_id)
        upcoming = upc_q.order('starts_at').limit(1).execute()
        if upcoming.data:
            next_apt = upcoming.data[0]

        # New patients this month (clinic-wide)
        new_patients_month = sdb.table('patients').select('id', count='exact').eq('clinic_id', clinic_id).gte('created_at', month_start.isoformat()).execute()

        # Prescriptions issued this month: doctor sees own, others see clinic-wide
        rx_q = sdb.table('prescriptions').select('id', count='exact').eq('clinic_id', clinic_id).eq('status', 'issued').gte('issued_at', month_start.isoformat())
        if role == 'doctor':
            rx_q = rx_q.eq('doctor_id', member_id)
        rx_month = rx_q.execute()

        # Recent patients (collect ids first, then one batched fetch below)
        recent_apts_q = sdb.table('appointments').select('patient_id').eq('clinic_id', clinic_id).eq('status', 'completed')
        if role == 'doctor':
            recent_apts_q = recent_apts_q.eq('doctor_id', member_id)
        recent_apts = recent_apts_q.order('updated_at', desc=True).limit(10).execute()
        seen_ids = []
        for ra in (recent_apts.data or []):
            pid = ra.get('patient_id')
            if pid and pid not in seen_ids and len(seen_ids) < 5:
                seen_ids.append(pid)
        # Pre-fetch up to 5 fallback patients (only if non-doctor and we don't have 5 yet)
        fallback_patients = []
        if len(seen_ids) < 5 and role != 'doctor':
            extra = sdb.table('patients').select('id,first_name,last_name,phone').eq('clinic_id', clinic_id).order('created_at', desc=True).limit(5).execute()
            for p in (extra.data or []):
                if p['id'] not in seen_ids and len(seen_ids) + len(fallback_patients) < 5:
                    fallback_patients.append(p)

        # Activity log (skipped for doctor) — fetch the source rows now; enrich names in the batch step
        activity_rows = []
        if role != 'doctor':
            recent_created_apts = sdb.table('appointments').select('id,patient_id,created_at,starts_at').eq('clinic_id', clinic_id).order('created_at', desc=True).limit(5).execute()
            for a in (recent_created_apts.data or []):
                activity_rows.append({"type": "appointment", "patient_id": a.get('patient_id'), "timestamp": a['created_at']})
            recent_rx = sdb.table('prescriptions').select('id,patient_id,created_at,status').eq('clinic_id', clinic_id).eq('status', 'issued').order('created_at', desc=True).limit(5).execute()
            for r in (recent_rx.data or []):
                activity_rows.append({"type": "prescription", "patient_id": r.get('patient_id'), "timestamp": r['created_at']})
            recent_pats_for_activity = sdb.table('patients').select('id,first_name,last_name,created_at').eq('clinic_id', clinic_id).order('created_at', desc=True).limit(5).execute()
            for p in (recent_pats_for_activity.data or []):
                activity_rows.append({"type": "patient", "_inline_name": f"{p['first_name']} {p['last_name']}", "timestamp": p['created_at']})

        # ===== Single batched lookup: patients + doctors =====
        all_patient_ids = set()
        all_doctor_ids = set()
        for a in apts:
            if a.get('patient_id'): all_patient_ids.add(a['patient_id'])
            if a.get('doctor_id'): all_doctor_ids.add(a['doctor_id'])
        if next_apt and next_apt.get('patient_id'):
            all_patient_ids.add(next_apt['patient_id'])
        for pid in seen_ids:
            all_patient_ids.add(pid)
        for ar in activity_rows:
            if ar.get('patient_id'):
                all_patient_ids.add(ar['patient_id'])

        patient_map = {}
        if all_patient_ids:
            ps = sdb.table('patients').select('id,first_name,last_name,phone').in_('id', list(all_patient_ids)).execute()
            for p in (ps.data or []):
                patient_map[p['id']] = p

        doctor_map = {}
        if all_doctor_ids:
            ds = sdb.table('clinic_members').select('id,first_name,last_name').in_('id', list(all_doctor_ids)).execute()
            for d in (ds.data or []):
                doctor_map[d['id']] = d

        # Build recent_patients from seen_ids preserving order, fall back to fallback_patients
        recent_patients = []
        for pid in seen_ids:
            p = patient_map.get(pid)
            if p:
                recent_patients.append({"id": p['id'], "first_name": p['first_name'], "last_name": p['last_name'], "phone": p.get('phone')})
        for fb in fallback_patients:
            if len(recent_patients) >= 5:
                break
            recent_patients.append(fb)

        # Build activity messages with patient names from the batched map
        activity = []
        for ar in activity_rows:
            if ar['type'] == 'patient':
                msg = f"Paciente registrado: {ar['_inline_name']}"
            else:
                pdata = patient_map.get(ar.get('patient_id'))
                pname = f"{pdata['first_name']} {pdata['last_name']}" if pdata else "Paciente"
                msg = (f"Cita agendada para {pname}" if ar['type'] == 'appointment' else f"Receta emitida para {pname}")
            activity.append({"type": ar['type'], "message": msg, "timestamp": ar['timestamp']})
        activity.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        activity = activity[:10]

        # Enrich today's appointments
        for apt in apts:
            p = patient_map.get(apt.get('patient_id'))
            d = doctor_map.get(apt.get('doctor_id'))
            apt["patient_name"] = f"{p['first_name']} {p['last_name']}" if p else ""
            apt["doctor_name"] = f"{d['first_name']} {d['last_name']}" if d else ""
        if next_apt:
            p = patient_map.get(next_apt.get('patient_id'))
            next_apt["patient_name"] = f"{p['first_name']} {p['last_name']}" if p else ""

        # ===== Admin stats + alerts (skip for doctor) =====
        admin_stats = {}
        alerts = []
        income_chart = []
        my_commissions_month = None

        is_admin_view = role in ('clinic_admin', 'cashier', 'assistant', 'receptionist')

        # Cash session status — useful for cashier/receptionist/assistant/admin
        if is_admin_view and 'sales' in features:
            cs = sdb.table('cash_sessions').select('id,opened_at,opening_amount').eq('clinic_id', clinic_id).eq('status', 'open').limit(5).execute()
            open_sessions = cs.data or []
            admin_stats['open_cash_sessions'] = len(open_sessions)
            # Alert: cash session opened more than 18h ago
            for s in open_sessions:
                try:
                    opened = dt.fromisoformat(s['opened_at'].replace('Z', '+00:00'))
                    hours = (now - opened).total_seconds() / 3600
                    if hours >= 18:
                        alerts.append({
                            "type": "cash_session",
                            "severity": "warning",
                            "message": f"Caja abierta hace {int(hours)}h sin cerrar",
                            "link": "/dashboard/ventas",
                            "count": 1,
                        })
                        break
                except Exception:
                    pass

        # Sales today + AR pending (clinic_admin / cashier full view; assistant/receptionist intermediate)
        if role in ('clinic_admin', 'cashier'):
            if 'sales' in features:
                sales_q = sdb.table('sales').select('total,status').eq('clinic_id', clinic_id).gte('created_at', today_start.isoformat()).lt('created_at', today_end.isoformat()).execute()
                sales_today_rows = [s for s in (sales_q.data or []) if s.get('status') != 'cancelled']
                admin_stats['sales_today_amount'] = round(sum(float(s.get('total') or 0) for s in sales_today_rows), 2)
                admin_stats['sales_today_count'] = len(sales_today_rows)

                ar_q = sdb.table('accounts_receivable').select('balance,due_date,status').eq('clinic_id', clinic_id).neq('status', 'paid').execute()
                ar_rows = ar_q.data or []
                admin_stats['ar_pending_amount'] = round(sum(float(a.get('balance') or 0) for a in ar_rows), 2)
                # Overdue alert
                overdue = 0
                for a in ar_rows:
                    if not a.get('due_date'):
                        continue
                    try:
                        if dt_date.fromisoformat(a['due_date']) < today_date:
                            overdue += 1
                    except Exception:
                        pass
                if overdue > 0:
                    alerts.append({
                        "type": "ar_overdue",
                        "severity": "danger",
                        "message": f"{overdue} cuenta(s) por cobrar vencida(s)",
                        "link": "/dashboard/cuentas-por-cobrar",
                        "count": overdue,
                    })
                # Overdue installments (filter via clinic's AR ids since installments table has no clinic_id)
                ar_ids_resp = sdb.table('accounts_receivable').select('id').eq('clinic_id', clinic_id).execute()
                ar_id_list = [a['id'] for a in (ar_ids_resp.data or [])]
                inst_overdue = 0
                if ar_id_list:
                    installments = sdb.table('payment_plan_installments').select('id,due_date,status').in_('account_receivable_id', ar_id_list).neq('status', 'paid').execute()
                    for i in (installments.data or []):
                        if not i.get('due_date'):
                            continue
                        try:
                            if dt_date.fromisoformat(i['due_date']) < today_date:
                                inst_overdue += 1
                        except Exception:
                            pass
                if inst_overdue > 0:
                    alerts.append({
                        "type": "installment_overdue",
                        "severity": "danger",
                        "message": f"{inst_overdue} cuota(s) de plan de pago vencida(s)",
                        "link": "/dashboard/cuentas-por-cobrar",
                        "count": inst_overdue,
                    })

            if 'inventory' in features:
                # Low stock count — single batched query for all stocks
                products = sdb.table('products').select('id,min_stock').eq('clinic_id', clinic_id).eq('is_active', True).execute()
                product_min = {p['id']: (p.get('min_stock') or 0) for p in (products.data or []) if (p.get('min_stock') or 0) > 0}
                low_count = 0
                if product_min:
                    pids = list(product_min.keys())
                    stocks = sdb.table('inventory_stock').select('product_id,quantity').in_('product_id', pids).execute()
                    # Track which products have at least one branch under min_stock
                    flagged = set()
                    for s in (stocks.data or []):
                        pid = s.get('product_id')
                        if pid in flagged:
                            continue
                        if (s.get('quantity') or 0) <= product_min[pid]:
                            flagged.add(pid)
                    low_count = len(flagged)
                admin_stats['low_stock_count'] = low_count
                if low_count > 0:
                    alerts.append({
                        "type": "low_stock",
                        "severity": "warning",
                        "message": f"{low_count} producto(s) con stock crítico",
                        "link": "/dashboard/inventario",
                        "count": low_count,
                    })

                # Expiring batches (next 60 days)
                cutoff = (now + timedelta(days=60)).isoformat()
                exp_batches = sdb.table('inventory_batches').select('id', count='exact').eq('clinic_id', clinic_id).eq('is_active', True).lt('expiration_date', cutoff).gt('quantity', 0).execute()
                exp_count = exp_batches.count or 0
                admin_stats['expiring_count'] = exp_count
                if exp_count > 0:
                    alerts.append({
                        "type": "expiring",
                        "severity": "warning",
                        "message": f"{exp_count} producto(s) próximo(s) a vencer (60 días)",
                        "link": "/dashboard/inventario",
                        "count": exp_count,
                    })

            if 'expenses' in features:
                exp_q = sdb.table('expenses').select('total,expense_date').eq('clinic_id', clinic_id).gte('expense_date', month_start_date.isoformat()).execute()
                admin_stats['expenses_month'] = round(sum(float(e.get('total') or 0) for e in (exp_q.data or [])), 2)

            if 'commissions' in features:
                comm_q = sdb.table('commissions_earned').select('commission_amount,status').eq('clinic_id', clinic_id).gte('earned_at', month_start.isoformat()).execute()
                admin_stats['commissions_month'] = round(sum(float(c.get('commission_amount') or 0) for c in (comm_q.data or [])), 2)
                admin_stats['commissions_pending'] = round(sum(float(c.get('commission_amount') or 0) for c in (comm_q.data or []) if c.get('status') == 'earned'), 2)

            # Income chart for current month (daily)
            if 'financial_reports' in features and 'sales' in features:
                month_sales = sdb.table('sales').select('created_at,total,status').eq('clinic_id', clinic_id).gte('created_at', month_start.isoformat()).lt('created_at', today_end.isoformat()).execute()
                daily = {}
                for s in (month_sales.data or []):
                    if s.get('status') == 'cancelled':
                        continue
                    try:
                        d_iso = (s.get('created_at') or '')[:10]
                        if d_iso:
                            daily[d_iso] = daily.get(d_iso, 0) + float(s.get('total') or 0)
                    except Exception:
                        pass
                cur = month_start_date
                while cur <= today_date:
                    iso = cur.isoformat()
                    income_chart.append({"date": iso, "income": round(daily.get(iso, 0), 2)})
                    cur = cur + timedelta(days=1)

        # Doctor: own commissions this month
        if role == 'doctor' and 'commissions' in features:
            comm_q = sdb.table('commissions_earned').select('commission_amount,status').eq('clinic_id', clinic_id).eq('doctor_id', member_id).gte('earned_at', month_start.isoformat()).execute()
            rows = comm_q.data or []
            my_commissions_month = {
                "earned": round(sum(float(c.get('commission_amount') or 0) for c in rows), 2),
                "pending": round(sum(float(c.get('commission_amount') or 0) for c in rows if c.get('status') == 'earned'), 2),
                "paid": round(sum(float(c.get('commission_amount') or 0) for c in rows if c.get('status') == 'paid'), 2),
            }

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
            "role": role,
            "features": sorted(features),
            "admin_stats": admin_stats,
            "alerts": alerts,
            "income_chart": income_chart,
            "my_commissions_month": my_commissions_month,
        }
    except Exception as e:
        logger.error(f"Clinic dashboard error: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener dashboard")


from server import limiter


@router.post("/clinic/appointments/{apt_id}/send-reminder")
@limiter.limit("30/minute")
async def send_appointment_reminder_now(apt_id: str, request: Request, ctx=Depends(require_module('agenda'))):
    """Manually send the email reminder for a single appointment.

    Useful for the receptionist UI when they want to send the reminder ad-hoc
    (e.g. patient just called, doctor changed schedule, etc.). The automatic
    scheduler also runs every 10 minutes and sends 24h-before reminders.
    Rate-limited to 30 reminders / minute / IP.
    """
    clinic_id = ctx["member"]["clinic_id"]
    try:
        apt_res = sdb.table('appointments').select('*').eq('id', apt_id).eq('clinic_id', clinic_id).maybe_single().execute()
        apt = getattr(apt_res, 'data', None) if apt_res else None
        if not apt:
            raise HTTPException(status_code=404, detail="Cita no encontrada")

        # Resolve patient, doctor, clinic, branch
        patient = sdb.table('patients').select('id,first_name,last_name,email').eq('id', apt['patient_id']).maybe_single().execute().data or {}
        patient_email = (patient.get('email') or '').strip()
        if not patient_email or '@' not in patient_email:
            raise HTTPException(status_code=400, detail="El paciente no tiene email registrado")

        doctor = sdb.table('clinic_members').select('first_name,last_name').eq('id', apt['doctor_id']).maybe_single().execute().data or {}
        clinic = sdb.table('clinics').select('name,timezone').eq('id', clinic_id).maybe_single().execute().data or {}
        branch = None
        if apt.get('branch_id'):
            br = sdb.table('branches').select('name').eq('id', apt['branch_id']).maybe_single().execute().data
            branch = (br or {}).get('name')

        from zoneinfo import ZoneInfo
        from datetime import datetime as _dt
        tz = ZoneInfo(clinic.get('timezone') or 'America/Guatemala')
        starts_dt = _dt.fromisoformat(apt['starts_at'].replace('Z', '+00:00'))
        when_str = starts_dt.astimezone(tz).strftime('%d/%m/%Y %H:%M')

        from services.email_service import send_email
        from services.email_templates import appointment_reminder
        tmpl = appointment_reminder(
            patient_name=f"{patient.get('first_name','')} {patient.get('last_name','')}".strip() or "Paciente",
            clinic_name=clinic.get('name') or "Cortexia Medical",
            doctor_name=f"Dr. {doctor.get('first_name','')} {doctor.get('last_name','')}".strip(),
            when_str=when_str,
            branch=branch,
            reason=apt.get('reason') or None,
        )
        send_result = await send_email(
            to=patient_email,
            subject=tmpl['subject'],
            html=tmpl['html'],
            text=tmpl['text'],
        )
        if not send_result.get('ok'):
            raise HTTPException(status_code=502, detail=f"Error de envío: {send_result.get('error')}")

        sdb.table('appointments').update({
            "reminder_email_sent_at": now_iso(),
            "updated_at": now_iso(),
        }).eq('id', apt_id).execute()
        return {"ok": True, "message": "Recordatorio enviado", "sent_to": patient_email, "message_id": send_result.get('id')}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Send reminder error: {e}")
        raise HTTPException(status_code=500, detail="Error al enviar recordatorio")


@router.post("/admin/reminders/run-now")
async def admin_run_reminders_now(user=Depends(require_super_admin)):
    """Super-admin helper to manually trigger a scheduler tick (for testing)."""
    from services.reminder_scheduler import _send_due_reminders
    counters = await _send_due_reminders()
    return {"ok": True, "counters": counters}
