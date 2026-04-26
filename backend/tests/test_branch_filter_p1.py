"""P1: Branch filter regression — Agenda/Inventory/Sales branch_id filtering.

Verifies:
  - GET /api/clinic/appointments accepts branch_id param and filters
  - POST /api/clinic/appointments persists branch_id
  - POST without branch_id still works (None persisted)
  - Inventory/Sales endpoints accept branch_id query param without error
"""
import os
import uuid
import requests
import pytest
from datetime import datetime, timedelta, timezone

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
ADMIN_EMAIL = "carlos@lasalud.gt"
ADMIN_PASSWORD = "Test123456!"
CLINIC_ID = "c0321ed8-97da-47a1-b601-3b94bffabdd7"
BRANCH_MAIN = "79c47aab-3d03-49a0-bcec-b931766aa48e"  # Sede Central
BRANCH_Z15 = "2ba2e8c4-3dde-4662-b232-11c3eff82bc9"  # Sucursal Zona 15


@pytest.fixture(scope="module")
def auth_headers():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def patient_and_doctor(auth_headers):
    """Get one valid patient_id and one valid doctor_id from the clinic."""
    pr = requests.get(f"{BASE_URL}/api/clinic/patients", headers=auth_headers, timeout=20)
    assert pr.status_code == 200
    pdata = pr.json()
    patients = pdata.get("patients") if isinstance(pdata, dict) else pdata
    assert patients and len(patients) > 0, f"Need at least 1 patient. Got: {pdata}"
    patient_id = patients[0]["id"]

    mr = requests.get(f"{BASE_URL}/api/clinic/members", headers=auth_headers, timeout=20)
    assert mr.status_code == 200
    members = mr.json()
    doctor = next((m for m in members if m.get("role") in ("doctor", "clinic_admin")), None)
    assert doctor, "Need a doctor or clinic_admin member"
    return patient_id, doctor["id"]


def _next_business_slot():
    """Return ISO start at next Mon-Fri 10:00 UTC well within clinic hours (08-17 GT)."""
    # Clinic TZ is America/Guatemala (UTC-6). 10:00 GT == 16:00 UTC.
    now = datetime.now(timezone.utc)
    candidate = now + timedelta(days=1)
    while candidate.isoweekday() > 5:
        candidate += timedelta(days=1)
    candidate = candidate.replace(hour=16, minute=0, second=0, microsecond=0)
    # Add a random minute offset to avoid conflict
    candidate += timedelta(minutes=(uuid.uuid4().int % 50) + 1)
    return candidate.isoformat()


# ===== Backend: appointments branch_id =====

class TestAppointmentsBranchFilter:

    def test_list_appointments_no_branch_filter(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/clinic/appointments", headers=auth_headers, timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_list_appointments_with_branch_id(self, auth_headers):
        r = requests.get(
            f"{BASE_URL}/api/clinic/appointments",
            headers=auth_headers,
            params={"branch_id": BRANCH_MAIN},
            timeout=30,
        )
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list)
        # All returned rows must have branch_id == BRANCH_MAIN (or be empty)
        for row in rows:
            assert row.get("branch_id") == BRANCH_MAIN, f"Row leaked: {row.get('branch_id')}"

    def test_list_appointments_other_branch(self, auth_headers):
        r = requests.get(
            f"{BASE_URL}/api/clinic/appointments",
            headers=auth_headers,
            params={"branch_id": BRANCH_Z15},
            timeout=30,
        )
        assert r.status_code == 200
        rows = r.json()
        for row in rows:
            assert row.get("branch_id") == BRANCH_Z15

    def test_create_appointment_with_branch_id_persists(self, auth_headers, patient_and_doctor):
        patient_id, doctor_id = patient_and_doctor
        starts_at = _next_business_slot()
        payload = {
            "patient_id": patient_id,
            "doctor_id": doctor_id,
            "starts_at": starts_at,
            "duration_minutes": 30,
            "reason": "TEST_branch_filter_p1",
            "branch_id": BRANCH_Z15,
        }
        r = requests.post(f"{BASE_URL}/api/clinic/appointments", json=payload, headers=auth_headers, timeout=30)
        assert r.status_code == 200, f"Create failed: {r.status_code} {r.text}"
        doc = r.json()
        assert doc.get("branch_id") == BRANCH_Z15
        apt_id = doc["id"]

        # Verify persistence: filtered list must include this apt
        r2 = requests.get(
            f"{BASE_URL}/api/clinic/appointments",
            headers=auth_headers,
            params={"branch_id": BRANCH_Z15},
            timeout=30,
        )
        assert r2.status_code == 200
        ids = [a["id"] for a in r2.json()]
        assert apt_id in ids, "Created apt not in branch-filtered list"

        # And NOT in main branch list
        r3 = requests.get(
            f"{BASE_URL}/api/clinic/appointments",
            headers=auth_headers,
            params={"branch_id": BRANCH_MAIN},
            timeout=30,
        )
        assert r3.status_code == 200
        ids_main = [a["id"] for a in r3.json()]
        assert apt_id not in ids_main, "Created apt leaked into main branch list"

        # Cleanup: cancel
        requests.put(
            f"{BASE_URL}/api/clinic/appointments/{apt_id}/status",
            json={"status": "cancelled", "cancellation_reason": "TEST cleanup"},
            headers=auth_headers, timeout=20,
        )

    def test_create_appointment_without_branch_id_backwards_compat(self, auth_headers, patient_and_doctor):
        patient_id, doctor_id = patient_and_doctor
        starts_at = _next_business_slot()
        payload = {
            "patient_id": patient_id,
            "doctor_id": doctor_id,
            "starts_at": starts_at,
            "duration_minutes": 30,
            "reason": "TEST_no_branch_p1",
        }
        r = requests.post(f"{BASE_URL}/api/clinic/appointments", json=payload, headers=auth_headers, timeout=30)
        assert r.status_code == 200, f"Create without branch failed: {r.status_code} {r.text}"
        doc = r.json()
        assert doc.get("branch_id") is None
        apt_id = doc["id"]

        # Cleanup
        requests.put(
            f"{BASE_URL}/api/clinic/appointments/{apt_id}/status",
            json={"status": "cancelled", "cancellation_reason": "TEST cleanup"},
            headers=auth_headers, timeout=20,
        )


# ===== Backend: regression — Inventory/Sales accept branch_id =====

class TestInventorySalesBranchFilter:

    def test_inventory_stock_with_branch_id(self, auth_headers):
        r = requests.get(
            f"{BASE_URL}/api/clinic/inventory/stock",
            headers=auth_headers,
            params={"branch_id": BRANCH_MAIN},
            timeout=30,
        )
        assert r.status_code == 200, f"Got {r.status_code}: {r.text[:200]}"

    def test_inventory_movements_with_branch_id(self, auth_headers):
        r = requests.get(
            f"{BASE_URL}/api/clinic/inventory/movements",
            headers=auth_headers,
            params={"branch_id": BRANCH_MAIN},
            timeout=30,
        )
        assert r.status_code == 200, f"Got {r.status_code}: {r.text[:200]}"

    def test_sales_daily_summary_with_branch_id(self, auth_headers):
        r = requests.get(
            f"{BASE_URL}/api/clinic/sales/daily-summary",
            headers=auth_headers,
            params={"branch_id": BRANCH_MAIN},
            timeout=30,
        )
        assert r.status_code == 200

    def test_sales_list_with_branch_id(self, auth_headers):
        r = requests.get(
            f"{BASE_URL}/api/clinic/sales",
            headers=auth_headers,
            params={"branch_id": BRANCH_MAIN},
            timeout=30,
        )
        assert r.status_code == 200

    def test_cash_sessions_with_branch_id(self, auth_headers):
        r = requests.get(
            f"{BASE_URL}/api/clinic/sales/cash-sessions",
            headers=auth_headers,
            params={"branch_id": BRANCH_MAIN},
            timeout=30,
        )
        assert r.status_code == 200

    def test_cash_registers_with_branch_id(self, auth_headers):
        r = requests.get(
            f"{BASE_URL}/api/clinic/sales/cash-registers",
            headers=auth_headers,
            params={"branch_id": BRANCH_MAIN},
            timeout=30,
        )
        assert r.status_code == 200
