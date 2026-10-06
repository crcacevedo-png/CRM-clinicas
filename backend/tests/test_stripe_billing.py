"""
Stripe Billing Integration Tests (Flow B / BYOK).

STRIPE_API_KEY=sk_test_emergent is a placeholder; Stripe will reject it.
These tests validate response STRUCTURE and graceful error handling rather than
end-to-end checkout success.

Covers:
- GET  /api/billing/subscription           (clinic admin)
- GET  /api/plans                          (clinic admin)
- POST /api/billing/checkout               (clinic admin — error paths)
- POST /api/billing/portal                 (clinic admin — no sub -> 400)
- POST /api/admin/billing/sync-stripe-catalog (super admin — invalid key path)
- GET  /api/admin/billing/overview         (super admin)
- GET  /api/admin/billing/transactions     (super admin)
- POST /api/webhook/stripe                 (bad signature -> 400)
- GET  /api/billing/status/{session_id}    (bogus id -> 404)
- RBAC guards: clinic admin cannot hit super-admin billing endpoints; unauth -> 401/403
"""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

SUPER_ADMIN_EMAIL = "info@cortexiagt.com"
SUPER_ADMIN_PASSWORD = "Armagedon1980$"

CLINIC_ADMIN_EMAIL = "prueba3@gmail.com"
CLINIC_ADMIN_PASSWORD = "Test123456!"


def _login(email: str, password: str) -> str:
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"Login failed for {email}: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def super_token():
    return _login(SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def clinic_token():
    return _login(CLINIC_ADMIN_EMAIL, CLINIC_ADMIN_PASSWORD)


@pytest.fixture
def super_headers(super_token):
    return {"Authorization": f"Bearer {super_token}", "Content-Type": "application/json"}


@pytest.fixture
def clinic_headers(clinic_token):
    return {"Authorization": f"Bearer {clinic_token}", "Content-Type": "application/json"}


# =============== /api/billing/subscription ===============

class TestSubscription:
    def test_get_subscription_structure(self, clinic_headers):
        r = requests.get(f"{BASE_URL}/api/billing/subscription", headers=clinic_headers, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        # Required keys
        for k in ["clinic_id", "plan_code", "plan_name", "price_monthly", "price_yearly",
                  "currency", "status", "stripe_configured", "stripe_subscription_status",
                  "stripe_subscription", "billing_cycle", "has_customer", "limits"]:
            assert k in d, f"Missing key {k} in subscription response: {d}"
        assert d["stripe_configured"] is True, "stripe_configured should be True (STRIPE_API_KEY set)"
        # Without a real sub we expect these to be null-ish
        assert d["stripe_subscription"] is None
        assert d["has_customer"] is False
        assert d["currency"] == "USD"
        assert isinstance(d["limits"], dict)


# =============== /api/plans ===============

class TestPlans:
    def test_list_plans_sorted_asc(self, clinic_headers):
        r = requests.get(f"{BASE_URL}/api/plans", headers=clinic_headers, timeout=30)
        assert r.status_code == 200, r.text
        plans = r.json()
        assert isinstance(plans, list) and len(plans) > 0
        prices = [float(p.get("price_monthly") or 0) for p in plans]
        assert prices == sorted(prices), f"Plans not sorted by price_monthly ASC: {prices}"
        required_fields = {"code", "name", "price_monthly", "price_yearly",
                           "stripe_price_monthly", "stripe_price_yearly"}
        for p in plans:
            assert required_fields.issubset(p.keys()), f"Plan missing fields: {p}"


# =============== /api/billing/checkout ===============

class TestCheckout:
    def test_checkout_plan_not_synced_returns_400(self, clinic_headers):
        payload = {"plan_code": "professional", "billing_cycle": "monthly", "origin_url": "https://x.com"}
        r = requests.post(f"{BASE_URL}/api/billing/checkout", json=payload, headers=clinic_headers, timeout=30)
        assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
        detail = r.json().get("detail", "")
        assert "sincronizado" in detail.lower() or "stripe" in detail.lower(), f"Unexpected detail: {detail}"

    def test_checkout_invalid_billing_cycle(self, clinic_headers):
        payload = {"plan_code": "professional", "billing_cycle": "weekly", "origin_url": "https://x.com"}
        r = requests.post(f"{BASE_URL}/api/billing/checkout", json=payload, headers=clinic_headers, timeout=30)
        assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
        assert "monthly" in r.json().get("detail", "").lower()

    def test_checkout_requires_auth(self):
        payload = {"plan_code": "professional", "billing_cycle": "monthly", "origin_url": "https://x.com"}
        r = requests.post(f"{BASE_URL}/api/billing/checkout", json=payload, timeout=30)
        assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}"


# =============== /api/billing/portal ===============

class TestPortal:
    def test_portal_without_subscription_returns_400(self, clinic_headers):
        r = requests.post(f"{BASE_URL}/api/billing/portal",
                          json={"origin_url": "https://x.com"},
                          headers=clinic_headers, timeout=30)
        assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
        assert "portal" in r.json().get("detail", "").lower() or "plan" in r.json().get("detail", "").lower()


# =============== /api/billing/status/{session_id} ===============

class TestBillingStatus:
    def test_bogus_session_returns_404(self):
        r = requests.get(f"{BASE_URL}/api/billing/status/cs_fake_123", timeout=30)
        assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"


# =============== /api/webhook/stripe ===============

class TestWebhook:
    def test_webhook_invalid_signature_returns_400(self):
        r = requests.post(f"{BASE_URL}/api/webhook/stripe",
                          data=b'{"type":"x"}',
                          headers={"stripe-signature": "bogus", "Content-Type": "application/json"},
                          timeout=30)
        # When STRIPE_WEBHOOK_SECRET is set -> 400 Firma inválida
        # When secret not set, code path trusts body (dev-only) -> 200. Accept 400 primarily.
        assert r.status_code in (400, 503), f"Expected 400/503, got {r.status_code}: {r.text}"


# =============== /api/admin/billing/sync-stripe-catalog ===============

class TestSyncCatalog:
    def test_sync_returns_200_with_errors_from_invalid_key(self, super_headers):
        r = requests.post(f"{BASE_URL}/api/admin/billing/sync-stripe-catalog",
                          headers=super_headers, timeout=60)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        d = r.json()
        assert d.get("ok") is True
        assert d.get("configured") is True
        assert "counters" in d
        counters = d["counters"]
        assert "errors" in counters and isinstance(counters["errors"], list)
        # With a placeholder key we expect errors on paid plans
        joined = " | ".join(counters["errors"]).lower()
        assert "invalid" in joined or "api key" in joined or len(counters["errors"]) > 0, \
            f"Expected Stripe invalid-key errors, got: {counters}"


# =============== /api/admin/billing/overview ===============

class TestAdminOverview:
    def test_overview_structure(self, super_headers):
        r = requests.get(f"{BASE_URL}/api/admin/billing/overview", headers=super_headers, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("stripe_configured") is True
        summary = d.get("summary") or {}
        for k in ("total_clinics", "active_clinics", "with_subscription", "mrr", "arr"):
            assert k in summary, f"Missing summary.{k}"
        assert summary["with_subscription"] == 0
        assert summary["mrr"] == 0
        assert summary["arr"] == 0
        assert isinstance(d.get("by_plan"), list)
        for bp in d["by_plan"]:
            assert "synced" in bp
            assert bp["synced"] is False  # placeholder key -> not synced
        assert isinstance(d.get("clinics"), list)
        if d["clinics"]:
            c0 = d["clinics"][0]
            for k in ("stripe_subscription_status", "stripe_subscription_id", "billing_cycle"):
                assert k in c0, f"Missing clinic row key {k}"

    def test_overview_blocks_clinic_admin(self, clinic_headers):
        r = requests.get(f"{BASE_URL}/api/admin/billing/overview", headers=clinic_headers, timeout=30)
        assert r.status_code == 403, f"Expected 403 for clinic admin, got {r.status_code}: {r.text}"


# =============== /api/admin/billing/transactions ===============

class TestAdminTransactions:
    def test_transactions_structure(self, super_headers):
        r = requests.get(f"{BASE_URL}/api/admin/billing/transactions", headers=super_headers, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "transactions" in d and isinstance(d["transactions"], list)
