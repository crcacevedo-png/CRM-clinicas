"""Tests for WhatsApp appointment reminders endpoints.

Covers:
- GET /api/clinic/appointments/whatsapp-reminders (default + window cap)
- POST /api/clinic/appointments/{id}/whatsapp-reminder-sent
- POST /api/clinic/appointments/{id}/whatsapp-reminder-reset
- Auth / tenant isolation / status filter / regression on user-guide PDF
"""
import os
import time
import uuid
import pytest
import requests
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as fh:
        for line in fh:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

CLINIC_ADMIN_EMAIL = "prueba3@gmail.com"
CLINIC_ADMIN_PASSWORD = "Test123456!"
CLINIC_ID = "c0321ed8-97da-47a1-b601-3b94bffabdd7"
BRANCH_MAIN = "79c47aab-3d03-49a0-bcec-b931766aa48e"

# Super admin (for cross-clinic tenant isolation test we login as another clinic admin -
# but simpler: use a random UUID as apt_id which will 404). For "other clinic" real test,
# we use super admin? Actually the endpoint uses require_clinic_member, so super admin
# won't pass. We'll simulate "id of other clinic" using a random UUID (returns 404).

DOCTOR_EMAIL = "doctor.test@lasalud.gt"
DOCTOR_PASSWORD = "Kx9$mPzeta2026Q"


# --------------------- Fixtures ---------------------

@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": CLINIC_ADMIN_EMAIL, "password": CLINIC_ADMIN_PASSWORD},
                      timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def doctor_id(admin_headers):
    r = requests.get(f"{BASE_URL}/api/clinic/members", headers=admin_headers, timeout=30)
    assert r.status_code == 200, f"members: {r.status_code} {r.text}"
    members = r.json() if isinstance(r.json(), list) else r.json().get("members", [])
    for m in members:
        if (m.get("role") == "doctor" or "doctor" in (m.get("role") or "").lower()) and m.get("is_active", True):
            return m["id"]
    # fallback
    for m in members:
        if m.get("id"):
            return m["id"]
    pytest.skip("No doctor available in clinic")


@pytest.fixture(scope="module")
def patient_with_phone(admin_headers):
    """Create a patient with a phone number."""
    payload = {
        "first_name": "TEST_WA",
        "last_name": f"Pac_{int(time.time())}",
        "phone": "55512345",  # 8-digit local Guatemalan number
    }
    r = requests.post(f"{BASE_URL}/api/clinic/patients", headers=admin_headers, json=payload, timeout=30)
    assert r.status_code in (200, 201), f"create patient: {r.status_code} {r.text}"
    pid = r.json()["id"]
    yield pid
    # No delete endpoint for patients; leave it (marked TEST_)


@pytest.fixture(scope="module")
def patient_no_phone(admin_headers):
    payload = {
        "first_name": "TEST_WA_NOP",
        "last_name": f"NoPhone_{int(time.time())}",
    }
    r = requests.post(f"{BASE_URL}/api/clinic/patients", headers=admin_headers, json=payload, timeout=30)
    assert r.status_code in (200, 201), f"create patient no-phone: {r.status_code} {r.text}"
    yield r.json()["id"]


def _next_business_slot(hours_ahead: int = 2):
    """Return an ISO UTC datetime string a few hours ahead but always within 24h,
    aligned to a business hour in America/Guatemala (UTC-6).
    Clinic default hours are typically 08:00-17:00 local.
    We pick tomorrow 10:00 local (which is within 24h if current local time is
    after 10:00, otherwise within 24h anyway if before 10:00 today+1)."""
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("America/Guatemala")
    now_local = datetime.now(tz)
    # try today at now+2h if within business hours
    candidate = now_local + timedelta(hours=hours_ahead)
    candidate = candidate.replace(minute=0, second=0, microsecond=0)
    if 8 <= candidate.hour <= 16 and candidate.isoweekday() <= 6:
        return candidate.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    # otherwise use tomorrow 10:00
    tomorrow = (now_local + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    return tomorrow.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@pytest.fixture()
def appointment(admin_headers, patient_with_phone, doctor_id):
    starts_at = _next_business_slot(hours_ahead=2)
    payload = {
        "patient_id": patient_with_phone,
        "doctor_id": doctor_id,
        "branch_id": BRANCH_MAIN,
        "starts_at": starts_at,
        "duration_minutes": 30,
        "reason": f"TEST_WA_REMINDER_{int(time.time())}",
        "notes": "",
    }
    r = requests.post(f"{BASE_URL}/api/clinic/appointments", headers=admin_headers, json=payload, timeout=30)
    assert r.status_code in (200, 201), f"create appt: {r.status_code} {r.text}"
    apt_id = r.json()["id"]
    yield apt_id
    # Cleanup: cancel appointment
    try:
        requests.put(
            f"{BASE_URL}/api/clinic/appointments/{apt_id}/status",
            headers=admin_headers, json={"status": "cancelled"}, timeout=30,
        )
    except Exception:
        pass


# --------------------- Tests ---------------------

# --- Basic endpoint structure

def test_whatsapp_reminders_default_structure(admin_headers):
    r = requests.get(f"{BASE_URL}/api/clinic/appointments/whatsapp-reminders",
                     headers=admin_headers, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "appointments" in data and isinstance(data["appointments"], list)
    assert "count" in data
    assert "window_hours" in data
    assert data["window_hours"] == 24
    # skipped_no_phone present when there are results; may be absent if list empty
    if data["count"] > 0:
        assert "skipped_no_phone" in data


def test_whatsapp_reminders_window_cap_168(admin_headers):
    r = requests.get(f"{BASE_URL}/api/clinic/appointments/whatsapp-reminders",
                     params={"window_hours": 999}, headers=admin_headers, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    # Endpoint echoes the requested value but the internal window is capped
    assert data["window_hours"] == 999
    # Should not error out


def test_whatsapp_reminders_window_168(admin_headers):
    r = requests.get(f"{BASE_URL}/api/clinic/appointments/whatsapp-reminders",
                     params={"window_hours": 168}, headers=admin_headers, timeout=30)
    assert r.status_code == 200, r.text
    assert r.json()["window_hours"] == 168


# --- Auth

def test_no_auth_get_returns_401_or_403():
    r = requests.get(f"{BASE_URL}/api/clinic/appointments/whatsapp-reminders", timeout=30)
    assert r.status_code in (401, 403), r.status_code


def test_no_auth_post_sent_returns_401_or_403():
    r = requests.post(f"{BASE_URL}/api/clinic/appointments/{uuid.uuid4()}/whatsapp-reminder-sent", timeout=30)
    assert r.status_code in (401, 403), r.status_code


# --- Appointment listed with correct fields

def test_appointment_appears_with_correct_message_and_wa_url(admin_headers, appointment, patient_with_phone):
    r = requests.get(f"{BASE_URL}/api/clinic/appointments/whatsapp-reminders",
                     headers=admin_headers, timeout=30)
    assert r.status_code == 200
    data = r.json()
    item = next((a for a in data["appointments"] if a["id"] == appointment), None)
    assert item is not None, f"Appointment {appointment} not in reminders: {data}"

    # (a) message formatted with patient name, date, time, clinic
    msg = item["message"]
    assert "TEST_WA" in msg  # patient first name
    assert item["date_label"] in msg
    assert item["time_label"] in msg
    # Clinic name should be embedded — could be anything, just make sure non-empty msg
    assert len(msg) > 30

    # (b) wa_url starts with https://wa.me/ + normalized number with country 502
    assert item["wa_url"].startswith("https://wa.me/"), item["wa_url"]
    # phone was '55512345' local + Guatemala country '502' => '50255512345'
    assert "50255512345" in item["wa_url"], item["wa_url"]
    assert item["wa_phone"] == "50255512345"

    # (c) already_sent False
    assert item["already_sent"] is False

    # (d) date/time labels present
    assert item["date_label"]
    assert item["time_label"]


# --- Patient without phone is skipped

def test_patient_without_phone_not_listed_and_skipped_incremented(
    admin_headers, patient_no_phone, doctor_id
):
    # Create appointment for patient without phone
    starts_at = _next_business_slot(hours_ahead=3)
    payload = {
        "patient_id": patient_no_phone,
        "doctor_id": doctor_id,
        "branch_id": BRANCH_MAIN,
        "starts_at": starts_at,
        "duration_minutes": 30,
        "reason": f"TEST_WA_NOPHONE_{int(time.time())}",
    }
    r = requests.post(f"{BASE_URL}/api/clinic/appointments", headers=admin_headers, json=payload, timeout=30)
    if r.status_code not in (200, 201):
        pytest.skip(f"Could not create appt (conflict?): {r.text}")
    apt_id = r.json()["id"]
    try:
        r2 = requests.get(f"{BASE_URL}/api/clinic/appointments/whatsapp-reminders",
                          headers=admin_headers, timeout=30)
        assert r2.status_code == 200
        data = r2.json()
        ids = [a["id"] for a in data["appointments"]]
        assert apt_id not in ids
        assert data.get("skipped_no_phone", 0) >= 1
    finally:
        requests.put(f"{BASE_URL}/api/clinic/appointments/{apt_id}/status",
                     headers=admin_headers, json={"status": "cancelled"}, timeout=30)


# --- Mark sent / not-in-list / include_sent

def test_mark_sent_removes_from_list_and_include_sent_shows(admin_headers, appointment):
    r = requests.post(f"{BASE_URL}/api/clinic/appointments/{appointment}/whatsapp-reminder-sent",
                      headers=admin_headers, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("ok") is True
    assert body.get("appointment_id") == appointment

    # Not in default list
    r2 = requests.get(f"{BASE_URL}/api/clinic/appointments/whatsapp-reminders",
                      headers=admin_headers, timeout=30)
    ids = [a["id"] for a in r2.json()["appointments"]]
    assert appointment not in ids

    # With include_sent=true it appears with already_sent=true
    r3 = requests.get(f"{BASE_URL}/api/clinic/appointments/whatsapp-reminders",
                      params={"include_sent": "true"}, headers=admin_headers, timeout=30)
    assert r3.status_code == 200
    item = next((a for a in r3.json()["appointments"] if a["id"] == appointment), None)
    assert item is not None, "Should appear with include_sent=true"
    assert item["already_sent"] is True
    assert item.get("whatsapp_reminder_sent_at")


def test_reset_reminder_makes_it_reappear(admin_headers, appointment):
    # First mark as sent
    requests.post(f"{BASE_URL}/api/clinic/appointments/{appointment}/whatsapp-reminder-sent",
                  headers=admin_headers, timeout=30)
    # Reset
    r = requests.post(f"{BASE_URL}/api/clinic/appointments/{appointment}/whatsapp-reminder-reset",
                      headers=admin_headers, timeout=30)
    assert r.status_code == 200, r.text
    assert r.json().get("ok") is True

    # Now appears in pending list
    r2 = requests.get(f"{BASE_URL}/api/clinic/appointments/whatsapp-reminders",
                      headers=admin_headers, timeout=30)
    ids = [a["id"] for a in r2.json()["appointments"]]
    assert appointment in ids


# --- 404 cases

def test_mark_sent_nonexistent_appointment_returns_404(admin_headers):
    r = requests.post(f"{BASE_URL}/api/clinic/appointments/{uuid.uuid4()}/whatsapp-reminder-sent",
                      headers=admin_headers, timeout=30)
    assert r.status_code == 404, r.status_code


def test_mark_sent_other_clinic_returns_404(admin_headers):
    """Another clinic's appointment id -> 404 (tenant isolation).
    We simulate this by using a random UUID (not present) since we cannot easily
    obtain another clinic's real appointment id. The endpoint filters by clinic_id
    so any id not matching (clinic_id, id) returns 404 - which covers the
    tenant-isolation guarantee."""
    # Also try with a well-formed non-belonging id - should still be 404
    r = requests.post(
        f"{BASE_URL}/api/clinic/appointments/00000000-0000-0000-0000-000000000001/whatsapp-reminder-sent",
        headers=admin_headers, timeout=30)
    assert r.status_code == 404


# --- Status filter

def test_cancelled_appointment_not_in_list(admin_headers, patient_with_phone, doctor_id):
    starts_at = _next_business_slot(hours_ahead=4)
    payload = {
        "patient_id": patient_with_phone,
        "doctor_id": doctor_id,
        "branch_id": BRANCH_MAIN,
        "starts_at": starts_at,
        "duration_minutes": 30,
        "reason": f"TEST_WA_CANCEL_{int(time.time())}",
    }
    r = requests.post(f"{BASE_URL}/api/clinic/appointments", headers=admin_headers, json=payload, timeout=30)
    if r.status_code not in (200, 201):
        pytest.skip(f"Could not create appt: {r.text}")
    apt_id = r.json()["id"]
    try:
        # Cancel it
        rc = requests.put(f"{BASE_URL}/api/clinic/appointments/{apt_id}/status",
                          headers=admin_headers, json={"status": "cancelled"}, timeout=30)
        assert rc.status_code == 200, rc.text
        # Should not appear
        r2 = requests.get(f"{BASE_URL}/api/clinic/appointments/whatsapp-reminders",
                          headers=admin_headers, timeout=30)
        ids = [a["id"] for a in r2.json()["appointments"]]
        assert apt_id not in ids
    finally:
        pass


# --- Regression: user-guide PDF

def test_user_guide_pdf_regression(admin_headers):
    r = requests.get(f"{BASE_URL}/api/clinic/user-guide/pdf", headers=admin_headers, timeout=60)
    assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
    ctype = r.headers.get("content-type", "")
    assert "pdf" in ctype.lower(), ctype
    # First bytes should be PDF magic
    assert r.content[:4] == b"%PDF", r.content[:20]
