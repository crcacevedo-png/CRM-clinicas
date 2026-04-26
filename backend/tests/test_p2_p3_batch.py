"""P2/P3 batch regression tests.

Coverage:
  - GET /api/auth/me (clinic_admin + super_admin + 401)
  - Aliases: /clinic/expenses/categories vs /by-category, /clinic/sales/dashboard vs /daily-summary
  - UUID validation: 422 on malformed, 404 on valid-but-missing for sales/prescriptions/lab-orders/patients/medical-records
  - PDF-url endpoints uuid validation
  - Smoke regression on dashboard/appointments/sales endpoints
"""
import os
import requests
import pytest

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
CLINIC_ADMIN_EMAIL = "carlos@lasalud.gt"
CLINIC_ADMIN_PASSWORD = "Test123456!"
SUPER_ADMIN_EMAIL = "info@cortexiagt.com"
SUPER_ADMIN_PASSWORD = "Armagedon1980$"
CLINIC_ID_EXPECTED = "c0321ed8-97da-47a1-b601-3b94bffabdd7"
MEMBER_ID_EXPECTED = "199d2ea1-e2ff-4595-be1a-de07cc2f807d"
VALID_MISSING_UUID = "00000000-0000-0000-0000-000000000000"
MALFORMED_ID = "not-a-uuid"


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"Login failed for {email}: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def clinic_headers():
    token = _login(CLINIC_ADMIN_EMAIL, CLINIC_ADMIN_PASSWORD)
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def super_headers():
    token = _login(SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD)
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ======== /api/auth/me =========
class TestAuthMe:
    def test_me_clinic_admin(self, clinic_headers):
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=clinic_headers, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("user_type") == "clinic_member"
        assert d.get("clinic_id") == CLINIC_ID_EXPECTED
        assert d.get("member_id") == MEMBER_ID_EXPECTED
        assert d.get("role") in ("clinic_admin", "doctor", "receptionist")
        assert "name" in d
        assert "email" in d

    def test_me_super_admin(self, super_headers):
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=super_headers, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("user_type") == "super_admin"
        assert d.get("role") == "super_admin"
        assert d.get("clinic_id") is None

    def test_me_no_token(self):
        r = requests.get(f"{BASE_URL}/api/auth/me", timeout=20)
        assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}: {r.text}"

    def test_me_invalid_token(self):
        r = requests.get(f"{BASE_URL}/api/auth/me",
                         headers={"Authorization": "Bearer invalid.jwt.token"}, timeout=20)
        assert r.status_code in (401, 403), r.text


# ======== Aliases =========
class TestAliases:
    def test_expenses_categories_alias(self, clinic_headers):
        r1 = requests.get(f"{BASE_URL}/api/clinic/expenses/by-category", headers=clinic_headers, timeout=20)
        r2 = requests.get(f"{BASE_URL}/api/clinic/expenses/categories", headers=clinic_headers, timeout=20)
        assert r1.status_code == 200, r1.text
        assert r2.status_code == 200, r2.text
        # Both should have the same shape (list or dict)
        assert type(r1.json()) is type(r2.json())

    def test_sales_dashboard_alias(self, clinic_headers):
        r1 = requests.get(f"{BASE_URL}/api/clinic/sales/daily-summary", headers=clinic_headers, timeout=20)
        r2 = requests.get(f"{BASE_URL}/api/clinic/sales/dashboard", headers=clinic_headers, timeout=20)
        assert r1.status_code == 200, r1.text
        assert r2.status_code == 200, r2.text
        # Same top-level keys when both return dicts
        if isinstance(r1.json(), dict) and isinstance(r2.json(), dict):
            assert set(r1.json().keys()) == set(r2.json().keys())


# ======== UUID validation: 422 on malformed =========
class TestUuidValidation422:
    @pytest.mark.parametrize("path", [
        "/api/clinic/sales/not-a-uuid",
        "/api/clinic/prescriptions/not-a-uuid",
        "/api/clinic/lab-orders/not-a-uuid",
        "/api/clinic/patients/not-a-uuid",
        "/api/clinic/medical-records/not-a-uuid",
    ])
    def test_malformed_uuid_returns_422(self, clinic_headers, path):
        r = requests.get(f"{BASE_URL}{path}", headers=clinic_headers, timeout=20)
        assert r.status_code == 422, f"{path} expected 422, got {r.status_code}: {r.text[:200]}"

    @pytest.mark.parametrize("path", [
        "/api/clinic/lab-orders/not-a-uuid/pdf-url",
        "/api/clinic/prescriptions/not-a-uuid/pdf-url",
    ])
    def test_pdf_url_malformed_uuid_returns_422(self, clinic_headers, path):
        r = requests.get(f"{BASE_URL}{path}", headers=clinic_headers, timeout=20)
        assert r.status_code == 422, f"{path} expected 422, got {r.status_code}: {r.text[:200]}"


# ======== UUID validation: 404 on valid-but-missing =========
class TestUuidValidation404:
    @pytest.mark.parametrize("path", [
        f"/api/clinic/sales/{VALID_MISSING_UUID}",
        f"/api/clinic/prescriptions/{VALID_MISSING_UUID}",
        f"/api/clinic/lab-orders/{VALID_MISSING_UUID}",
        f"/api/clinic/patients/{VALID_MISSING_UUID}",
        f"/api/clinic/medical-records/{VALID_MISSING_UUID}",
    ])
    def test_valid_missing_uuid_returns_404(self, clinic_headers, path):
        r = requests.get(f"{BASE_URL}{path}", headers=clinic_headers, timeout=20)
        assert r.status_code == 404, f"{path} expected 404, got {r.status_code}: {r.text[:200]}"


# ======== Regression smoke =========
class TestRegression:
    def test_dashboard_200(self, clinic_headers):
        r = requests.get(f"{BASE_URL}/api/clinic/dashboard", headers=clinic_headers, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert isinstance(d, dict)

    def test_appointments_list_200(self, clinic_headers):
        r = requests.get(f"{BASE_URL}/api/clinic/appointments", headers=clinic_headers, timeout=30)
        assert r.status_code == 200, r.text

    def test_sales_list_200(self, clinic_headers):
        r = requests.get(f"{BASE_URL}/api/clinic/sales", headers=clinic_headers, timeout=30)
        assert r.status_code == 200, r.text
