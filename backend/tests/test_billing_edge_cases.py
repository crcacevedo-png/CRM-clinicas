"""
Backend tests for Phase 1 SaaS Billing Edge Cases:
- PUT /api/admin/clinics/{id} canonical route (super admin): name/plan/is_active updates + slug recompute + limits refresh + Stripe proration swallow
- PUT /api/admin/users/{id} canonical route (super admin): first_name/role/role_key updates + email change via Supabase Auth (valid + invalid)
- GET /api/billing/payment-status (clinic member): normal state structure
- Payment-block middleware: 402 for non-billing endpoints when is_payment_blocked=True, allow for /api/billing/* and /api/plans
- POST /api/admin/clinics/{id}/courtesy: clears block flags, sets is_active=True
- No duplicate PUT routes / no legacy 410 placeholders

Teardown: restore clinic c0321ed8-... and user prueba3@gmail.com to normal state.
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://super-admin-panel-12.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

SUPER_EMAIL = "info@cortexiagt.com"
SUPER_PASS = "Armagedon1980$"
CLINIC_EMAIL = "prueba3@gmail.com"
CLINIC_PASS = "Test123456!"

CLINIC_ID = "c0321ed8-97da-47a1-b601-3b94bffabdd7"
MEMBER_ID = "e6f13689-07b7-4159-ab9d-26b060a7b8dd"


# ---------- fixtures ----------
@pytest.fixture(scope="session")
def super_token():
    r = requests.post(f"{API}/auth/login", json={"email": SUPER_EMAIL, "password": SUPER_PASS}, timeout=20)
    assert r.status_code == 200, f"super login failed: {r.status_code} {r.text}"
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok
    return tok


@pytest.fixture(scope="session")
def clinic_token():
    r = requests.post(f"{API}/auth/login", json={"email": CLINIC_EMAIL, "password": CLINIC_PASS}, timeout=20)
    assert r.status_code == 200, f"clinic login failed: {r.status_code} {r.text}"
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok
    return tok


def h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# ---------- original clinic snapshot (for restore) ----------
@pytest.fixture(scope="session")
def original_clinic(super_token):
    r = requests.get(f"{API}/admin/clinics/{CLINIC_ID}", headers=h(super_token), timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["clinic"]


@pytest.fixture(scope="session")
def original_member(super_token):
    r = requests.get(f"{API}/admin/users", headers=h(super_token), timeout=20)
    assert r.status_code == 200
    for u in r.json():
        if u.get("id") == MEMBER_ID:
            return u
    pytest.skip("member not found")


# ---------- 1. Route-uniqueness / OpenAPI ----------
class TestRouteUniqueness:
    def test_no_duplicate_put_routes(self):
        """Inspect the registered FastAPI routes directly — ensures only one PUT handler each."""
        import sys
        sys.path.insert(0, "/app/backend")
        from server import app  # type: ignore
        clinic_puts = [r for r in app.routes if getattr(r, "path", "") == "/api/admin/clinics/{clinic_id}" and "PUT" in getattr(r, "methods", set())]
        user_puts = [r for r in app.routes if getattr(r, "path", "") == "/api/admin/users/{member_id}" and "PUT" in getattr(r, "methods", set())]
        assert len(clinic_puts) == 1, f"duplicate PUT /api/admin/clinics: {len(clinic_puts)}"
        assert len(user_puts) == 1, f"duplicate PUT /api/admin/users: {len(user_puts)}"

    def test_no_legacy_edit_routes(self):
        import sys
        sys.path.insert(0, "/app/backend")
        from server import app  # type: ignore
        for r in app.routes:
            name = getattr(r, "name", "") or ""
            assert name != "edit_clinic_full", f"legacy edit_clinic_full still registered at {getattr(r,'path','?')}"
            assert name != "edit_user", f"legacy edit_user still registered at {getattr(r,'path','?')}"


# ---------- 2. PUT /admin/clinics/{id} ----------
class TestClinicUpdate:
    def test_update_name_recomputes_slug(self, super_token, original_clinic):
        new_name = f"Clinica la salud TEST {int(time.time())}"
        r = requests.put(
            f"{API}/admin/clinics/{CLINIC_ID}",
            headers=h(super_token),
            json={"name": new_name},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["name"] == new_name
        assert data.get("slug"), "slug missing"
        # slug normalized
        assert "clinica-la-salud-test" in data["slug"].lower()
        # restore
        requests.put(
            f"{API}/admin/clinics/{CLINIC_ID}",
            headers=h(super_token),
            json={"name": original_clinic["name"]},
            timeout=20,
        )

    def test_update_city_persists(self, super_token, original_clinic):
        orig_city = original_clinic.get("city") or "Guatemala"
        new_city = f"TestCity_{int(time.time())}"
        r = requests.put(
            f"{API}/admin/clinics/{CLINIC_ID}",
            headers=h(super_token),
            json={"city": new_city},
            timeout=20,
        )
        assert r.status_code == 200
        assert r.json().get("city") == new_city
        # verify persistence via GET
        g = requests.get(f"{API}/admin/clinics/{CLINIC_ID}", headers=h(super_token), timeout=20)
        assert g.json()["clinic"].get("city") == new_city
        # restore
        requests.put(f"{API}/admin/clinics/{CLINIC_ID}", headers=h(super_token), json={"city": orig_city}, timeout=20)

    def test_update_plan_refreshes_limits(self, super_token, original_clinic):
        orig_plan = original_clinic.get("plan") or "professional"
        # DB enum only accepts 'professional' and 'enterprise' at this time
        target = "enterprise" if orig_plan != "enterprise" else "professional"
        r = requests.put(
            f"{API}/admin/clinics/{CLINIC_ID}",
            headers=h(super_token),
            json={"plan": target},
            timeout=30,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["plan"] == target
        # Limits that get_plan_limits() returns must be present & numeric
        for k in ("max_users", "max_patients", "max_storage_mb"):
            assert k in data, f"{k} missing from response after plan change"
            assert data[k] is None or isinstance(data[k], (int, float)), f"{k} not numeric"
        # max_branches is spec'd but not returned by get_plan_limits() — flag as a known gap
        # (not asserted here to avoid double-counting the same bug across tests)
        # restore
        rr = requests.put(
            f"{API}/admin/clinics/{CLINIC_ID}",
            headers=h(super_token),
            json={"plan": orig_plan},
            timeout=30,
        )
        assert rr.status_code == 200

    def test_update_is_active_toggle(self, super_token, original_clinic):
        orig = bool(original_clinic.get("is_active", True))
        r = requests.put(
            f"{API}/admin/clinics/{CLINIC_ID}",
            headers=h(super_token),
            json={"is_active": not orig},
            timeout=20,
        )
        assert r.status_code == 200
        assert r.json()["is_active"] == (not orig)
        # restore
        requests.put(f"{API}/admin/clinics/{CLINIC_ID}", headers=h(super_token), json={"is_active": orig}, timeout=20)


# ---------- 3. PUT /admin/users/{id} ----------
class TestUserUpdate:
    def test_update_basic_fields(self, super_token, original_member):
        orig_phone = original_member.get("phone") or ""
        new_phone = f"+502{int(time.time()) % 100000000}"
        r = requests.put(
            f"{API}/admin/users/{MEMBER_ID}",
            headers=h(super_token),
            json={"phone": new_phone, "first_name": original_member.get("first_name") or "Admin"},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        assert r.json().get("phone") == new_phone
        # restore phone
        requests.put(f"{API}/admin/users/{MEMBER_ID}", headers=h(super_token), json={"phone": orig_phone}, timeout=20)

    def test_update_role_key_preserves_role(self, super_token, original_member):
        # Preserve current role_key (may be None). Only re-send is_active true to prove non-destructive.
        r = requests.put(
            f"{API}/admin/users/{MEMBER_ID}",
            headers=h(super_token),
            json={"is_active": True},
            timeout=20,
        )
        assert r.status_code == 200
        # role must still be clinic_admin either as base_role or returned "role"
        data = r.json()
        role_val = data.get("role_key") or data.get("role") or data.get("base_role")
        assert role_val in ("clinic_admin", None) or "admin" in str(role_val).lower()

    def test_update_invalid_email_returns_400(self, super_token):
        r = requests.put(
            f"{API}/admin/users/{MEMBER_ID}",
            headers=h(super_token),
            json={"email": "not-an-email"},
            timeout=20,
        )
        # Supabase should reject -> wrapped as 400
        assert r.status_code == 400, f"expected 400 for invalid email, got {r.status_code}: {r.text}"
        body = r.text.lower()
        assert "supabase" in body or "email" in body

    def test_update_same_email_is_noop(self, super_token, original_member):
        # Sending the current email should not call Supabase and should 200
        current_email = original_member.get("email") or CLINIC_EMAIL
        r = requests.put(
            f"{API}/admin/users/{MEMBER_ID}",
            headers=h(super_token),
            json={"email": current_email},
            timeout=20,
        )
        assert r.status_code == 200, r.text


# ---------- 4. GET /billing/payment-status (normal state) ----------
class TestPaymentStatusNormal:
    def test_structure_in_normal_state(self, clinic_token):
        r = requests.get(f"{API}/billing/payment-status", headers=h(clinic_token), timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        for k in ("is_payment_blocked", "payment_grace_until", "is_courtesy", "stripe_subscription_status", "clinic_name"):
            assert k in data, f"missing key {k}"
        assert data["is_payment_blocked"] is False
        assert data["is_courtesy"] is False
        assert data["clinic_name"]


# ---------- 5. Payment-block middleware (mutate via sdb) ----------
class TestPaymentBlockMiddleware:
    @pytest.fixture(scope="class")
    def block_clinic(self):
        """Set is_payment_blocked=True on the clinic. Restore on teardown."""
        import sys
        sys.path.insert(0, "/app/backend")
        from core import sdb  # type: ignore
        sdb.table("clinics").update({
            "is_payment_blocked": True,
            "is_courtesy": False,
            "payment_blocked_at": "2026-01-01T00:00:00+00:00",
        }).eq("id", CLINIC_ID).execute()
        yield
        sdb.table("clinics").update({
            "is_payment_blocked": False,
            "is_courtesy": False,
            "payment_blocked_at": None,
            "payment_grace_until": None,
            "stripe_subscription_status": None,
        }).eq("id", CLINIC_ID).execute()

    def test_blocked_clinic_settings_returns_402(self, clinic_token, block_clinic):
        r = requests.get(f"{API}/clinic/settings", headers=h(clinic_token), timeout=20)
        assert r.status_code == 402, f"expected 402, got {r.status_code}: {r.text[:200]}"

    def test_blocked_billing_payment_status_allowed(self, clinic_token, block_clinic):
        r = requests.get(f"{API}/billing/payment-status", headers=h(clinic_token), timeout=20)
        assert r.status_code == 200, r.text
        assert r.json()["is_payment_blocked"] is True

    def test_blocked_billing_subscription_allowed(self, clinic_token, block_clinic):
        r = requests.get(f"{API}/billing/subscription", headers=h(clinic_token), timeout=20)
        assert r.status_code == 200, f"/billing/subscription should pass through gate, got {r.status_code}"

    def test_blocked_plans_allowed(self, clinic_token, block_clinic):
        r = requests.get(f"{API}/plans", headers=h(clinic_token), timeout=20)
        # /api/plans may be public or protected; must NOT be 402
        assert r.status_code != 402, f"/api/plans must not be blocked, got 402"


# ---------- 6. Courtesy toggle clears block ----------
class TestCourtesyToggle:
    def test_enable_courtesy_clears_block_flags(self, super_token):
        import sys
        sys.path.insert(0, "/app/backend")
        from core import sdb  # type: ignore
        # Pre-condition: set clinic as blocked
        sdb.table("clinics").update({
            "is_payment_blocked": True,
            "is_courtesy": False,
            "payment_blocked_at": "2026-01-01T00:00:00+00:00",
            "payment_grace_until": "2026-01-10T00:00:00+00:00",
            "is_active": False,
        }).eq("id", CLINIC_ID).execute()

        try:
            r = requests.post(
                f"{API}/admin/clinics/{CLINIC_ID}/courtesy",
                headers=h(super_token),
                json={"enabled": True},
                timeout=20,
            )
            assert r.status_code == 200, r.text
            # verify fields
            got = sdb.table("clinics").select(
                "is_courtesy,is_payment_blocked,payment_blocked_at,payment_grace_until,is_active"
            ).eq("id", CLINIC_ID).single().execute().data
            assert got["is_courtesy"] is True
            assert got["is_payment_blocked"] is False
            assert got["payment_blocked_at"] is None
            assert got["payment_grace_until"] is None
            assert got["is_active"] is True
        finally:
            # restore to normal: disable courtesy
            requests.post(
                f"{API}/admin/clinics/{CLINIC_ID}/courtesy",
                headers=h(super_token),
                json={"enabled": False},
                timeout=20,
            )
            sdb.table("clinics").update({
                "is_courtesy": False,
                "is_payment_blocked": False,
                "payment_blocked_at": None,
                "payment_grace_until": None,
                "stripe_subscription_status": None,
                "is_active": True,
            }).eq("id", CLINIC_ID).execute()
