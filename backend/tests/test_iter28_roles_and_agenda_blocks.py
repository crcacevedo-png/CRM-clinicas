"""Iteration 28: Agenda blocks (doctor-scope vs branch-scope) + Roles module CRUD
+ Enforcement (dynamic role reassignment). Cleans up all created data (blocks,
custom roles, and REVERTS doctor.test back to 'doctor' role) even on failure.
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/') + '/api'

ADMIN_EMAIL = "prueba3@gmail.com"
DOCTOR_EMAIL = "carlos@lasalud.gt"
DOCTOR_TEST_EMAIL = "doctor.test@lasalud.gt"
PASSWORD = "Test123456!"

CLINIC_ID = "c0321ed8-97da-47a1-b601-3b94bffabdd7"
DOCTOR_MEMBER_ID = "199d2ea1-e2ff-4595-be1a-de07cc2f807d"  # carlos
DOCTOR_TEST_MEMBER_ID = "dee8138c-0239-4610-b579-ed9dc5df8ee2"  # doctor.test
PATIENT_ID = "dffcbc90-407b-4e3a-b032-b831b20b524b"
BRANCH_MAIN = "79c47aab-3d03-49a0-bcec-b931766aa48e"
BRANCH_Z15 = "2ba2e8c4-3dde-4662-b232-11c3eff82bc9"


def _login(email, password):
    r = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_headers():
    tok = _login(ADMIN_EMAIL, PASSWORD)
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def doctor_headers():
    tok = _login(DOCTOR_EMAIL, PASSWORD)
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module", autouse=True)
def cleanup(admin_headers):
    """Track created blocks/roles and always clean up + revert doctor.test."""
    state = {"blocks": [], "roles": []}
    yield state
    # cleanup blocks
    for bid in state["blocks"]:
        try:
            requests.delete(f"{BASE_URL}/clinic/agenda-blocks/{bid}", headers=admin_headers, timeout=10)
        except Exception:
            pass
    # revert doctor.test role
    try:
        requests.put(f"{BASE_URL}/clinic/members/{DOCTOR_TEST_MEMBER_ID}/role",
                     headers=admin_headers, json={"role": "doctor"}, timeout=10)
    except Exception:
        pass
    # delete custom roles
    for rid in state["roles"]:
        try:
            requests.delete(f"{BASE_URL}/clinic/roles/{rid}", headers=admin_headers, timeout=10)
        except Exception:
            pass


# ============================================================
# AGENDA BLOCKS
# ============================================================
def _next_weekday_utc(hour_utc=15):
    """Return an aware UTC datetime for the next weekday (Mon-Fri) at hour_utc."""
    d = datetime.now(timezone.utc) + timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d.replace(hour=hour_utc, minute=0, second=0, microsecond=0)


class TestAgendaBlocks:
    def test_doctor_scope_blocks_all_branches(self, admin_headers, cleanup):
        start = _next_weekday_utc(15)
        end = start + timedelta(hours=1)
        payload = {
            "scope": "doctor",
            "doctor_id": DOCTOR_MEMBER_ID,
            "starts_at": start.isoformat().replace("+00:00", "Z"),
            "ends_at": end.isoformat().replace("+00:00", "Z"),
            "label": "TEST_doctor_scope_block",
        }
        r = requests.post(f"{BASE_URL}/clinic/agenda-blocks", headers=admin_headers, json=payload, timeout=15)
        assert r.status_code == 200, f"create doctor block: {r.status_code} {r.text}"
        block = r.json()
        assert block["scope"] == "doctor"
        assert block["doctor_id"] == DOCTOR_MEMBER_ID
        cleanup["blocks"].append(block["id"])

        # appointment in MAIN branch should 409
        for br in (BRANCH_MAIN, BRANCH_Z15):
            appt = {
                "patient_id": PATIENT_ID,
                "doctor_id": DOCTOR_MEMBER_ID,
                "branch_id": br,
                "starts_at": (start + timedelta(minutes=15)).isoformat().replace("+00:00", "Z"),
                "ends_at": (start + timedelta(minutes=45)).isoformat().replace("+00:00", "Z"),
                "reason": "TEST",
            }
            r2 = requests.post(f"{BASE_URL}/clinic/appointments", headers=admin_headers, json=appt, timeout=15)
            assert r2.status_code == 409, f"branch {br} expected 409 got {r2.status_code} {r2.text}"

    def test_branch_scope_only_blocks_that_branch(self, admin_headers, cleanup):
        start = _next_weekday_utc(17)
        end = start + timedelta(hours=1)
        payload = {
            "scope": "branch",
            "branch_id": BRANCH_MAIN,
            "starts_at": start.isoformat().replace("+00:00", "Z"),
            "ends_at": end.isoformat().replace("+00:00", "Z"),
            "label": "TEST_branch_scope_block",
        }
        r = requests.post(f"{BASE_URL}/clinic/agenda-blocks", headers=admin_headers, json=payload, timeout=15)
        assert r.status_code == 200, r.text
        cleanup["blocks"].append(r.json()["id"])

        appt_main = {
            "patient_id": PATIENT_ID, "doctor_id": DOCTOR_MEMBER_ID, "branch_id": BRANCH_MAIN,
            "starts_at": (start + timedelta(minutes=10)).isoformat().replace("+00:00", "Z"),
            "ends_at": (start + timedelta(minutes=40)).isoformat().replace("+00:00", "Z"),
            "reason": "TEST",
        }
        r_main = requests.post(f"{BASE_URL}/clinic/appointments", headers=admin_headers, json=appt_main, timeout=15)
        assert r_main.status_code == 409, f"MAIN expected 409 got {r_main.status_code} {r_main.text}"

        appt_z15 = {**appt_main, "branch_id": BRANCH_Z15}
        r_z15 = requests.post(f"{BASE_URL}/clinic/appointments", headers=admin_headers, json=appt_z15, timeout=15)
        assert r_z15.status_code in (200, 201), f"Z15 expected success got {r_z15.status_code} {r_z15.text}"
        # cleanup the created appointment
        appt_id = r_z15.json().get("id")
        if appt_id:
            requests.delete(f"{BASE_URL}/clinic/appointments/{appt_id}", headers=admin_headers, timeout=10)

    def test_invalid_block_payloads(self, admin_headers):
        # end before start
        s = _next_weekday_utc(16)
        r = requests.post(f"{BASE_URL}/clinic/agenda-blocks", headers=admin_headers, json={
            "scope": "doctor", "doctor_id": DOCTOR_MEMBER_ID,
            "starts_at": s.isoformat().replace("+00:00", "Z"),
            "ends_at": (s - timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
        }, timeout=15)
        assert r.status_code == 400
        # bad scope
        r = requests.post(f"{BASE_URL}/clinic/agenda-blocks", headers=admin_headers, json={
            "scope": "xyz", "starts_at": s.isoformat().replace("+00:00", "Z"),
            "ends_at": (s + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
        }, timeout=15)
        assert r.status_code == 400


# ============================================================
# ROLES CRUD
# ============================================================
class TestRolesCRUD:
    def test_list_roles_has_five_system_roles(self, admin_headers):
        r = requests.get(f"{BASE_URL}/clinic/roles", headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "roles" in data and "modules" in data
        assert len(data["modules"]) == 11
        system_keys = {r["key"] for r in data["roles"] if r.get("is_system")}
        assert {"clinic_admin", "doctor", "receptionist", "cashier", "assistant"}.issubset(system_keys)
        admin_row = next(r for r in data["roles"] if r["key"] == "clinic_admin")
        assert admin_row["locked"] is True

    def test_create_update_delete_custom_role(self, admin_headers, cleanup):
        name = f"TEST_role_{uuid.uuid4().hex[:6]}"
        r = requests.post(f"{BASE_URL}/clinic/roles", headers=admin_headers,
                          json={"name": name, "description": "test", "modules": ["agenda"]}, timeout=15)
        assert r.status_code == 200, r.text
        role = r.json()
        cleanup["roles"].append(role["id"])
        assert role["modules"] == ["agenda"]
        assert role["is_system"] is False

        # update
        r = requests.put(f"{BASE_URL}/clinic/roles/{role['id']}", headers=admin_headers,
                        json={"modules": ["agenda", "patients"], "description": "updated"}, timeout=15)
        assert r.status_code == 200, r.text

        # verify persistence
        r = requests.get(f"{BASE_URL}/clinic/roles", headers=admin_headers, timeout=15)
        row = next(x for x in r.json()["roles"] if x["id"] == role["id"])
        assert set(row["modules"]) == {"agenda", "patients"}

        # delete
        r = requests.delete(f"{BASE_URL}/clinic/roles/{role['id']}", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        cleanup["roles"].remove(role["id"])

    def test_cannot_edit_clinic_admin(self, admin_headers):
        r = requests.get(f"{BASE_URL}/clinic/roles", headers=admin_headers, timeout=15)
        admin_row = next(x for x in r.json()["roles"] if x["key"] == "clinic_admin")
        r = requests.put(f"{BASE_URL}/clinic/roles/{admin_row['id']}", headers=admin_headers,
                        json={"modules": ["agenda"]}, timeout=15)
        assert r.status_code == 400

    def test_cannot_delete_system_role(self, admin_headers):
        r = requests.get(f"{BASE_URL}/clinic/roles", headers=admin_headers, timeout=15)
        doctor_row = next(x for x in r.json()["roles"] if x["key"] == "doctor")
        r = requests.delete(f"{BASE_URL}/clinic/roles/{doctor_row['id']}", headers=admin_headers, timeout=15)
        assert r.status_code == 400

    def test_cannot_delete_role_with_members(self, admin_headers, cleanup):
        # Create a role, assign doctor.test to it, then try to delete → 400
        name = f"TEST_inuse_{uuid.uuid4().hex[:6]}"
        r = requests.post(f"{BASE_URL}/clinic/roles", headers=admin_headers,
                          json={"name": name, "modules": ["agenda"]}, timeout=15)
        assert r.status_code == 200
        role = r.json()
        cleanup["roles"].append(role["id"])

        r = requests.put(f"{BASE_URL}/clinic/members/{DOCTOR_TEST_MEMBER_ID}/role",
                         headers=admin_headers, json={"role": role["key"]}, timeout=15)
        assert r.status_code == 200, r.text

        r = requests.delete(f"{BASE_URL}/clinic/roles/{role['id']}", headers=admin_headers, timeout=15)
        assert r.status_code == 400

        # revert doctor.test
        r = requests.put(f"{BASE_URL}/clinic/members/{DOCTOR_TEST_MEMBER_ID}/role",
                         headers=admin_headers, json={"role": "doctor"}, timeout=15)
        assert r.status_code == 200


# ============================================================
# DYNAMIC ENFORCEMENT (assignment)
# ============================================================
class TestDynamicRoleEnforcement:
    def test_assign_agenda_only_role_and_enforce(self, admin_headers, cleanup):
        # Create custom role with ONLY agenda
        name = f"TEST_agonly_{uuid.uuid4().hex[:6]}"
        r = requests.post(f"{BASE_URL}/clinic/roles", headers=admin_headers,
                          json={"name": name, "modules": ["agenda"]}, timeout=15)
        assert r.status_code == 200
        role = r.json()
        cleanup["roles"].append(role["id"])

        # Assign to doctor.test
        r = requests.put(f"{BASE_URL}/clinic/members/{DOCTOR_TEST_MEMBER_ID}/role",
                         headers=admin_headers, json={"role": role["key"]}, timeout=15)
        assert r.status_code == 200, r.text

        # login as doctor.test
        tok = _login(DOCTOR_TEST_EMAIL, PASSWORD)
        h = {"Authorization": f"Bearer {tok}"}

        # 403 on modules NOT in role
        for path in ["/clinic/patients", "/clinic/sales", "/clinic/inventory/products",
                     "/clinic/expenses", "/clinic/accounts-receivable"]:
            r = requests.get(f"{BASE_URL}{path}", headers=h, timeout=15)
            assert r.status_code == 403, f"{path} expected 403 got {r.status_code}"

        # 200 on agenda
        r = requests.get(f"{BASE_URL}/clinic/appointments", headers=h, timeout=15)
        assert r.status_code == 200, f"appointments expected 200 got {r.status_code} {r.text}"

        # /clinic/features should reflect modules
        r = requests.get(f"{BASE_URL}/clinic/features", headers=h, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "modules" in data
        assert set(data["modules"]) == {"agenda"}

        # revert
        r = requests.put(f"{BASE_URL}/clinic/members/{DOCTOR_TEST_MEMBER_ID}/role",
                         headers=admin_headers, json={"role": "doctor"}, timeout=15)
        assert r.status_code == 200


# ============================================================
# STATIC ENFORCEMENT (doctor carlos - read only)
# ============================================================
class TestStaticEnforcement:
    def test_doctor_carlos_module_gating(self, doctor_headers):
        forbidden = [
            "/clinic/sales", "/clinic/inventory/products", "/clinic/expenses",
            "/clinic/commissions/settings", "/clinic/accounts-receivable",
            "/clinic/reports/executive-summary",
        ]
        for p in forbidden:
            r = requests.get(f"{BASE_URL}{p}", headers=doctor_headers, timeout=15)
            assert r.status_code == 403, f"doctor {p} expected 403 got {r.status_code}"

        allowed = ["/clinic/appointments", "/clinic/patients", "/clinic/prescriptions", "/clinic/lab-orders"]
        for p in allowed:
            r = requests.get(f"{BASE_URL}{p}", headers=doctor_headers, timeout=15)
            assert r.status_code == 200, f"doctor {p} expected 200 got {r.status_code} {r.text}"

    def test_admin_full_access(self, admin_headers):
        for p in ["/clinic/appointments", "/clinic/patients", "/clinic/sales",
                  "/clinic/inventory/products", "/clinic/expenses",
                  "/clinic/commissions/settings", "/clinic/accounts-receivable",
                  "/clinic/reports/executive-summary", "/clinic/prescriptions",
                  "/clinic/lab-orders"]:
            r = requests.get(f"{BASE_URL}{p}", headers=admin_headers, timeout=15)
            assert r.status_code == 200, f"admin {p} expected 200 got {r.status_code} {r.text}"

    def test_doctor_cannot_access_roles_admin(self, doctor_headers):
        r = requests.get(f"{BASE_URL}/clinic/roles", headers=doctor_headers, timeout=15)
        assert r.status_code == 403
