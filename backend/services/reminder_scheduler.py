"""Background scheduler for automatic appointment reminders.

Runs every 10 minutes (configurable) and emails any patient whose
appointment starts between (now + REMINDER_HOURS - WINDOW) and
(now + REMINDER_HOURS), as long as:

  - appointment.status == 'scheduled'
  - appointment.reminder_email_sent_at IS NULL
  - patient.email is non-empty
  - clinic.timezone is respected for display

After sending, `appointments.reminder_email_sent_at` is stamped so each
appointment is reminded exactly once.

Designed to be defensive: if Supabase is down or any single row fails,
the loop logs and continues — never crashes the FastAPI process.
"""
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

# Default: send reminder 24h before. Window = 30 min around target to catch
# rows even if the job is delayed a few minutes between ticks.
REMINDER_HOURS_BEFORE = int(os.environ.get("REMINDER_HOURS_BEFORE", "24"))
REMINDER_WINDOW_MIN = int(os.environ.get("REMINDER_WINDOW_MIN", "30"))
REMINDER_TICK_MIN = int(os.environ.get("REMINDER_TICK_MIN", "10"))

_scheduler: Optional[AsyncIOScheduler] = None


async def _send_due_reminders() -> dict:
    """Find and send all due reminders. Returns counters for observability."""
    from core import sdb, now_iso
    from services.email_service import send_email
    from services.email_templates import appointment_reminder

    counters = {"checked": 0, "sent": 0, "failed": 0, "skipped_no_email": 0}

    try:
        now_utc = datetime.now(timezone.utc)
        window_lo = (now_utc + timedelta(hours=REMINDER_HOURS_BEFORE) - timedelta(minutes=REMINDER_WINDOW_MIN)).isoformat()
        window_hi = (now_utc + timedelta(hours=REMINDER_HOURS_BEFORE) + timedelta(minutes=REMINDER_WINDOW_MIN)).isoformat()

        result = (
            sdb.table('appointments')
            .select('id,clinic_id,patient_id,doctor_id,branch_id,starts_at,reason,status,reminder_email_sent_at')
            .eq('status', 'scheduled')
            .is_('reminder_email_sent_at', 'null')
            .gte('starts_at', window_lo)
            .lte('starts_at', window_hi)
            .limit(200)
            .execute()
        )
        rows = result.data or []
        counters["checked"] = len(rows)
        if not rows:
            return counters

        # Batch-fetch related data
        patient_ids = list({r['patient_id'] for r in rows if r.get('patient_id')})
        doctor_ids = list({r['doctor_id'] for r in rows if r.get('doctor_id')})
        clinic_ids = list({r['clinic_id'] for r in rows if r.get('clinic_id')})
        branch_ids = list({r['branch_id'] for r in rows if r.get('branch_id')})

        patients_map = {}
        if patient_ids:
            p = sdb.table('patients').select('id,first_name,last_name,email').in_('id', patient_ids).execute()
            patients_map = {x['id']: x for x in (p.data or [])}
        doctors_map = {}
        if doctor_ids:
            d = sdb.table('clinic_members').select('id,first_name,last_name').in_('id', doctor_ids).execute()
            doctors_map = {x['id']: x for x in (d.data or [])}
        clinics_map = {}
        if clinic_ids:
            c = sdb.table('clinics').select('id,name,timezone').in_('id', clinic_ids).execute()
            clinics_map = {x['id']: x for x in (c.data or [])}
        branches_map = {}
        if branch_ids:
            b = sdb.table('branches').select('id,name').in_('id', branch_ids).execute()
            branches_map = {x['id']: x for x in (b.data or [])}

        for apt in rows:
            try:
                patient = patients_map.get(apt.get('patient_id')) or {}
                patient_email = (patient.get('email') or '').strip()
                if not patient_email or '@' not in patient_email:
                    counters["skipped_no_email"] += 1
                    # Stamp anyway so we don't reprocess (no email → won't get one ever)
                    sdb.table('appointments').update({
                        "reminder_email_sent_at": now_iso(),
                        "updated_at": now_iso(),
                    }).eq('id', apt['id']).execute()
                    continue

                clinic = clinics_map.get(apt.get('clinic_id')) or {}
                doctor = doctors_map.get(apt.get('doctor_id')) or {}
                branch = branches_map.get(apt.get('branch_id')) if apt.get('branch_id') else None

                # Format date in clinic's TZ
                from zoneinfo import ZoneInfo
                tz = ZoneInfo(clinic.get('timezone') or 'America/Guatemala')
                starts_iso = apt['starts_at']
                try:
                    starts_dt = datetime.fromisoformat(starts_iso.replace('Z', '+00:00'))
                except Exception:
                    starts_dt = now_utc
                local = starts_dt.astimezone(tz)
                when_str = local.strftime('%d/%m/%Y %H:%M')

                tmpl = appointment_reminder(
                    patient_name=f"{patient.get('first_name','')} {patient.get('last_name','')}".strip() or "Paciente",
                    clinic_name=clinic.get('name') or "Cortexia Medical",
                    doctor_name=f"Dr. {doctor.get('first_name','')} {doctor.get('last_name','')}".strip(),
                    when_str=when_str,
                    branch=(branch or {}).get('name') if branch else None,
                    reason=apt.get('reason') or None,
                )

                send_result = await send_email(
                    to=patient_email,
                    subject=tmpl['subject'],
                    html=tmpl['html'],
                    text=tmpl['text'],
                )
                if send_result.get('ok'):
                    sdb.table('appointments').update({
                        "reminder_email_sent_at": now_iso(),
                        "updated_at": now_iso(),
                    }).eq('id', apt['id']).execute()
                    counters["sent"] += 1
                else:
                    counters["failed"] += 1
                    logger.warning(f"Reminder failed apt={apt['id']}: {send_result.get('error')}")
            except Exception as e:
                counters["failed"] += 1
                logger.warning(f"Reminder error apt={apt.get('id')}: {e}")

        if counters["sent"] or counters["failed"]:
            logger.info(f"Reminder tick: {counters}")
        return counters
    except Exception as e:
        logger.warning(f"Reminder scheduler tick failed: {e}")
        return counters


def start_scheduler():
    """Start the global APScheduler. Safe to call multiple times — no-ops if already running."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    _scheduler = AsyncIOScheduler(timezone=timezone.utc)
    _scheduler.add_job(
        _send_due_reminders,
        trigger='interval',
        minutes=REMINDER_TICK_MIN,
        id='appointment_reminders',
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(timezone.utc) + timedelta(seconds=30),
    )
    _scheduler.start()
    logger.info(f"Reminder scheduler started — tick every {REMINDER_TICK_MIN}min, sends {REMINDER_HOURS_BEFORE}h before")
    return _scheduler


def stop_scheduler():
    global _scheduler
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:
            pass
        _scheduler = None
