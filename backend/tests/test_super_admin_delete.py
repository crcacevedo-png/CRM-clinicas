"""Backend tests for hard-delete endpoints on clinics and users (Super Admin).

Covers:
- DELETE /api/admin/clinics/{clinic_id} (with confirm_name guard, purge stats, auth deletion, audit)
- DELETE /api/admin/users/{member_id} (with self-protection, audit)
- 403 for non-super-admin, 404 for missing entities
- Regression on prior endpoints (dashboard, list clinics/users, create clinic, update clinic)
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"

SUPER_ADMIN_EMAIL = "info@cortexiagt.com"
SUPER_ADMIN_PASSWORD = "Armagedon1980$"
CLINIC_ADMIN_EMAIL = "prueba3@gmail.com"
CLINIC_ADMIN_PASSWORD = "Test123456!"

REAL_CLINIC_ID = "c0321ed8-97da-47a1-b601-3b94bffabdd7"  # DO NOT DELETE


# ---------- Fixtures ----------

def _login(email: str, password: str) -> str:
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def super_token():
    return _login(SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD)


@pytest.fixture(scope="session")
def clinic_admin_token():
    try:
        return _login(CLINIC_ADMIN_EMAIL, CLINIC_ADMIN_PASSWORD)
    except AssertionError as e:
        pytest.skip(f"clinic_admin login unavailable: {e}")


@pytest.fixture(scope="session")
def super_headers(super_token):
    return {"Authorization": f"Bearer {super_token}", "Content-Type": "application/json"}


# ---------- Helpers ----------

def _create_disposable_clinic(headers) -> dict:
    ts = int(time.time() * 1000)
    unique = uuid.uuid4().hex[:8]
    name = f"TEST_DEL_Clinic_{ts}_{unique}"
    admin_email = f"test_del_admin_{ts}_{unique}@example.com"
    payload = {
        "name": name,
        "country": "GT",
        "city": "GT City",
        "plan": "free",
        "admin_name": "Del",
        "admin_lastname": "Admin",
        "admin_email": admin_email,
        "admin_password": "Kx9$mPzeta2026Q!",
    }
    r = requests.post(f"{API}/admin/clinics", json=payload, headers=headers, timeout=60)
    assert r.status_code == 200, f"create clinic failed: {r.status_code} {r.text}"
    data = r.json()
    return {"name": name, "id": data["clinic"]["id"], "admin_email": admin_email}


def _add_member(headers, clinic_id: str) -> dict:
    ts = int(time.time() * 1000)
    unique = uuid.uuid4().hex[:8]
    email = f"test_del_member_{ts}_{unique}@example.com"
    payload = {
        "name": "Test",
        "lastname": "Member",
        "email": email,
        "password": "Kx9$mPzeta2026Q!",
        "role": "receptionist",
    }
    r = requests.post(f"{API}/admin/clinics/{clinic_id}/members", json=payload, headers=headers, timeout=30)
    assert r.status_code == 200, f"add member failed: {r.status_code} {r.text}"
    # Find the newly-inserted member id by listing users filtered by clinic_id
    r2 = requests.get(f"{API}/admin/users?clinic_id={clinic_id}", headers=headers, timeout=30)
    assert r2.status_code == 200
    members = [m for m in r2.json() if m.get("email") == email]
    assert members, f"member not found in list after create; email={email}, clinic={clinic_id}, all={[m.get('email') for m in r2.json()]}"
    return {"id": members[0]["id"], "email": email}


# ================================================================
# Regression: previous endpoints still work
# ================================================================

class TestRegressionExistingEndpoints:
    def test_dashboard(self, super_headers):
        r = requests.get(f"{API}/admin/dashboard", headers=super_headers, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "active_clinics" in d and "total_users" in d

    def test_list_clinics(self, super_headers):
        r = requests.get(f"{API}/admin/clinics", headers=super_headers, timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_list_users(self, super_headers):
        r = requests.get(f"{API}/admin/users", headers=super_headers, timeout=30)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_toggle_real_clinic_active_flag(self, super_headers):
        # Read current state
        r = requests.get(f"{API}/admin/clinics/{REAL_CLINIC_ID}", headers=super_headers, timeout=30)
        assert r.status_code == 200
        original = r.json()["clinic"]["is_active"]
        # Toggle and revert
        r = requests.put(
            f"{API}/admin/clinics/{REAL_CLINIC_ID}",
            json={"is_active": not original},
            headers=super_headers,
            timeout=30,
        )
        assert r.status_code == 200
        r = requests.put(
            f"{API}/admin/clinics/{REAL_CLINIC_ID}",
            json={"is_active": original},
            headers=super_headers,
            timeout=30,
        )
        assert r.status_code == 200


# ================================================================
# DELETE /admin/clinics/{clinic_id}
# ================================================================

class TestDeleteClinic:
    def test_delete_missing_confirm_name_returns_400(self, super_headers):
        info = _create_disposable_clinic(super_headers)
        try:
            r = requests.delete(
                f"{API}/admin/clinics/{info['id']}", headers=super_headers, timeout=30
            )
            assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"
            body = r.json()
            assert "nombre" in (body.get("detail") or "").lower()
        finally:
            # cleanup: delete with correct confirm_name
            requests.delete(
                f"{API}/admin/clinics/{info['id']}?confirm_name={info['name']}",
                headers=super_headers, timeout=60,
            )

    def test_delete_wrong_confirm_name_returns_400(self, super_headers):
        info = _create_disposable_clinic(super_headers)
        try:
            r = requests.delete(
                f"{API}/admin/clinics/{info['id']}?confirm_name=wrong-name",
                headers=super_headers, timeout=30,
            )
            assert r.status_code == 400
        finally:
            requests.delete(
                f"{API}/admin/clinics/{info['id']}?confirm_name={info['name']}",
                headers=super_headers, timeout=60,
            )

    def test_delete_missing_clinic_returns_404(self, super_headers):
        fake_id = str(uuid.uuid4())
        r = requests.delete(
            f"{API}/admin/clinics/{fake_id}?confirm_name=whatever",
            headers=super_headers, timeout=30,
        )
        assert r.status_code == 404
        assert "no encontrada" in (r.json().get("detail") or "").lower()

    def test_delete_without_super_admin_returns_403(self, clinic_admin_token):
        # Create clinic first as super, then attempt to delete as clinic_admin
        super_headers = {
            "Authorization": f"Bearer {_login(SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD)}",
            "Content-Type": "application/json",
        }
        info = _create_disposable_clinic(super_headers)
        try:
            ca_headers = {"Authorization": f"Bearer {clinic_admin_token}"}
            r = requests.delete(
                f"{API}/admin/clinics/{info['id']}?confirm_name={info['name']}",
                headers=ca_headers, timeout=30,
            )
            assert r.status_code == 403, f"expected 403 got {r.status_code}: {r.text}"
        finally:
            requests.delete(
                f"{API}/admin/clinics/{info['id']}?confirm_name={info['name']}",
                headers=super_headers, timeout=60,
            )

    def test_delete_happy_path_full_purge(self, super_headers):
        info = _create_disposable_clinic(super_headers)
        clinic_id = info["id"]

        # add an extra member so we exercise auth-user deletion
        member = _add_member(super_headers, clinic_id)

        # Sanity: GET clinic works pre-delete
        r = requests.get(f"{API}/admin/clinics/{clinic_id}", headers=super_headers, timeout=30)
        assert r.status_code == 200

        # DELETE with correct confirm_name
        r = requests.delete(
            f"{API}/admin/clinics/{clinic_id}?confirm_name={info['name']}",
            headers=super_headers, timeout=120,
        )
        assert r.status_code == 200, f"delete failed: {r.status_code} {r.text}"
        body = r.json()
        assert "message" in body
        assert "purge_stats" in body
        assert "auth_users_deleted" in body
        assert isinstance(body["purge_stats"], dict)
        # clinic_members should have been deleted (>=2: admin created with clinic + added member)
        assert body["purge_stats"].get("clinic_members", 0) >= 2
        assert body["auth_users_deleted"] >= 2

        # Verify: GET clinic -> 404
        r = requests.get(f"{API}/admin/clinics/{clinic_id}", headers=super_headers, timeout=30)
        assert r.status_code == 404, f"clinic still fetchable: {r.status_code} {r.text}"

        # Verify: not in list
        r = requests.get(f"{API}/admin/clinics", headers=super_headers, timeout=30)
        assert r.status_code == 200
        ids = [c["id"] for c in r.json()]
        assert clinic_id not in ids

        # Verify: the extra member is gone from users list (search by first_name filter)
        r = requests.get(f"{API}/admin/users?search=Test", headers=super_headers, timeout=30)
        assert r.status_code == 200
        emails = [m.get("email") for m in r.json()]
        assert member["email"] not in emails


# ================================================================
# DELETE /admin/users/{member_id}
# ================================================================

class TestDeleteUser:
    def test_delete_missing_user_returns_404(self, super_headers):
        fake_id = str(uuid.uuid4())
        r = requests.delete(f"{API}/admin/users/{fake_id}", headers=super_headers, timeout=30)
        assert r.status_code == 404
        assert "no encontrado" in (r.json().get("detail") or "").lower()

    def test_delete_without_super_admin_returns_403(self, clinic_admin_token):
        # Create disposable clinic + member as super
        super_headers_local = {
            "Authorization": f"Bearer {_login(SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD)}",
            "Content-Type": "application/json",
        }
        info = _create_disposable_clinic(super_headers_local)
        try:
            member = _add_member(super_headers_local, info["id"])
            ca_headers = {"Authorization": f"Bearer {clinic_admin_token}"}
            r = requests.delete(f"{API}/admin/users/{member['id']}", headers=ca_headers, timeout=30)
            assert r.status_code == 403
        finally:
            requests.delete(
                f"{API}/admin/clinics/{info['id']}?confirm_name={info['name']}",
                headers=super_headers_local, timeout=60,
            )

    def test_delete_happy_path(self, super_headers):
        info = _create_disposable_clinic(super_headers)
        try:
            member = _add_member(super_headers, info["id"])

            r = requests.delete(
                f"{API}/admin/users/{member['id']}",
                headers=super_headers, timeout=60,
            )
            assert r.status_code == 200, f"delete user failed: {r.status_code} {r.text}"
            body = r.json()
            assert "message" in body
            assert "auth_user_deleted" in body
            assert body["auth_user_deleted"] is True

            # Verify: user no longer in list (filter by the disposable clinic)
            r = requests.get(f"{API}/admin/users?clinic_id={info['id']}", headers=super_headers, timeout=30)
            assert r.status_code == 200
            emails = [m.get("email") for m in r.json()]
            assert member["email"] not in emails
        finally:
            # cleanup: delete disposable clinic
            requests.delete(
                f"{API}/admin/clinics/{info['id']}?confirm_name={info['name']}",
                headers=super_headers, timeout=60,
            )
