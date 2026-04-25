"""
Commissions Module Tests - Backend
Endpoints covered:
- GET/POST/PUT/DELETE /api/clinic/commissions/settings
- GET /api/clinic/commissions/earned
- GET /api/clinic/commissions/dashboard
- POST /api/clinic/commissions/pay
- GET /api/clinic/commissions/report-pdf
- Auto-calc hook on POST /api/clinic/sales (with doctor_id)
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
EMAIL = "carlos@lasalud.gt"
PASS = "Test123456!"
CLINIC_ID = "c0321ed8-97da-47a1-b601-3b94bffabdd7"

state = {}


@pytest.fixture(scope="module")
def H():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASS})
    assert r.status_code == 200, f"Login failed: {r.text}"
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def branch_id(H):
    r = requests.get(f"{BASE_URL}/api/clinic/branches", headers=H)
    assert r.status_code == 200
    return r.json()[0]["id"]


@pytest.fixture(scope="module")
def doctor_id(H):
    """Find a doctor in members list."""
    r = requests.get(f"{BASE_URL}/api/clinic/members", headers=H)
    assert r.status_code == 200, r.text
    members = r.json() if isinstance(r.json(), list) else r.json().get("members", [])
    docs = [m for m in members if m.get("role") == "doctor"]
    assert docs, f"No doctor in clinic members: {members}"
    return docs[0]["id"]


@pytest.fixture(scope="module")
def session_id(H, branch_id):
    """Open or reuse a cash session for sales."""
    r = requests.get(f"{BASE_URL}/api/clinic/sales/cash-session/current", headers=H)
    if r.status_code == 200 and r.json().get("session"):
        return r.json()["session"]["id"]
    # Need to open - find a register
    cr = requests.get(f"{BASE_URL}/api/clinic/sales/cash-registers", headers=H)
    regs = cr.json() if cr.status_code == 200 else []
    if not regs:
        # create one
        rc = requests.post(f"{BASE_URL}/api/clinic/sales/cash-registers", headers=H,
                           json={"name": "TEST_Register", "branch_id": branch_id})
        assert rc.status_code == 200
        reg_id = rc.json()["id"]
    else:
        reg_id = regs[0]["id"]
    op = requests.post(f"{BASE_URL}/api/clinic/sales/cash-session/open", headers=H,
                      json={"cash_register_id": reg_id, "opening_amount": 0, "branch_id": branch_id})
    assert op.status_code == 200, op.text
    return op.json()["id"]


@pytest.fixture(scope="module")
def service_id(H):
    """Create or reuse a TEST_ service."""
    r = requests.get(f"{BASE_URL}/api/clinic/sales/services", headers=H)
    if r.status_code == 200:
        for s in r.json():
            if s.get("name") == "TEST_CommServ":
                return s["id"]
    rc = requests.post(f"{BASE_URL}/api/clinic/sales/services", headers=H,
                       json={"name": "TEST_CommServ", "price": 500, "tax_rate": 0, "duration_minutes": 30})
    assert rc.status_code == 200, rc.text
    return rc.json()["id"]


# ---------- Feature flag ----------
class TestFeature:
    def test_commissions_feature_enabled(self, H):
        r = requests.get(f"{BASE_URL}/api/clinic/features", headers=H)
        assert r.status_code == 200
        feats = r.json().get("features", [])
        assert "commissions" in feats, f"'commissions' missing: {feats}"


# ---------- Settings (Rules) CRUD + validation ----------
class TestSettingsCRUD:
    def test_create_rule_invalid_applies_to(self, H, doctor_id):
        r = requests.post(f"{BASE_URL}/api/clinic/commissions/settings", headers=H,
                          json={"doctor_id": doctor_id, "applies_to": "BOGUS",
                                "calculation_type": "percentage", "percentage": 10})
        assert r.status_code == 400, r.text

    def test_create_rule_invalid_calc_type(self, H, doctor_id):
        r = requests.post(f"{BASE_URL}/api/clinic/commissions/settings", headers=H,
                          json={"doctor_id": doctor_id, "applies_to": "all_consultations",
                                "calculation_type": "BOGUS", "percentage": 10})
        assert r.status_code == 400

    def test_create_rule_service_without_service_id(self, H, doctor_id):
        r = requests.post(f"{BASE_URL}/api/clinic/commissions/settings", headers=H,
                          json={"doctor_id": doctor_id, "applies_to": "service",
                                "calculation_type": "percentage", "percentage": 20})
        assert r.status_code == 400

    def test_create_rule_product_without_product_id(self, H, doctor_id):
        r = requests.post(f"{BASE_URL}/api/clinic/commissions/settings", headers=H,
                          json={"doctor_id": doctor_id, "applies_to": "product",
                                "calculation_type": "fixed", "fixed_amount": 5})
        assert r.status_code == 400

    def test_create_rule_all_consultations_30pct(self, H, doctor_id):
        # First: clean any pre-existing rules for this doctor to keep test deterministic
        r0 = requests.get(f"{BASE_URL}/api/clinic/commissions/settings?doctor_id={doctor_id}", headers=H)
        if r0.status_code == 200:
            body = r0.json()
            existing = body.get("rules") if isinstance(body, dict) else body
            for rule in (existing or []):
                if isinstance(rule, dict) and rule.get("id"):
                    requests.delete(f"{BASE_URL}/api/clinic/commissions/settings/{rule['id']}", headers=H)
        r = requests.post(f"{BASE_URL}/api/clinic/commissions/settings", headers=H,
                          json={"doctor_id": doctor_id, "applies_to": "all_consultations",
                                "calculation_type": "percentage", "percentage": 30, "is_active": True})
        assert r.status_code == 200, r.text
        state["rule_id"] = r.json()["id"]

    def test_list_settings_has_doctor_name(self, H, doctor_id):
        r = requests.get(f"{BASE_URL}/api/clinic/commissions/settings?doctor_id={doctor_id}", headers=H)
        assert r.status_code == 200
        body = r.json()
        rules = body.get("rules") if isinstance(body, dict) else body
        assert isinstance(rules, list) and len(rules) > 0
        found = next((x for x in rules if x.get("id") == state.get("rule_id")), None)
        assert found is not None
        assert "doctor_name" in found and found["doctor_name"]
        assert found["applies_to"] == "all_consultations"
        assert float(found["percentage"]) == 30

    def test_toggle_active_via_put(self, H):
        rid = state["rule_id"]
        r = requests.put(f"{BASE_URL}/api/clinic/commissions/settings/{rid}", headers=H,
                         json={"is_active": False})
        assert r.status_code == 200
        # Verify
        r2 = requests.get(f"{BASE_URL}/api/clinic/commissions/settings", headers=H)
        rules = r2.json().get("rules") if isinstance(r2.json(), dict) else r2.json()
        f = next(x for x in rules if x["id"] == rid)
        assert f["is_active"] is False
        # Re-enable for auto-calc test
        requests.put(f"{BASE_URL}/api/clinic/commissions/settings/{rid}", headers=H,
                     json={"is_active": True})


# ---------- Auto-calc on sale creation ----------
class TestAutoCalc:
    def test_sale_with_doctor_creates_commission(self, H, branch_id, doctor_id, session_id, service_id):
        # Snapshot pre-count for this doctor
        pre = requests.get(
            f"{BASE_URL}/api/clinic/commissions/earned?doctor_id={doctor_id}",
            headers=H,
        )
        pre_total = pre.json().get("total") if pre.status_code == 200 else 0

        payload = {
            "branch_id": branch_id,
            "cash_session_id": session_id,
            "doctor_id": doctor_id,
            "items": [{
                "service_id": service_id,
                "name": "TEST_CommServ", "description": "TEST_CommServ",
                "quantity": 1, "unit_price": 500, "tax_rate": 0, "discount_pct": 0,
            }],
            "payments": [{"payment_method": "cash", "amount": 500}],
            "customer_name": "TEST_Customer_Comm",
        }
        r = requests.post(f"{BASE_URL}/api/clinic/sales", headers=H, json=payload)
        assert r.status_code == 200, r.text
        sale = r.json()
        state["sale_id"] = sale["id"]
        # Allow background helper to flush
        time.sleep(1.0)

        # Verify commission earned row exists for this sale
        post = requests.get(
            f"{BASE_URL}/api/clinic/commissions/earned?doctor_id={doctor_id}&status=earned",
            headers=H,
        )
        assert post.status_code == 200
        body = post.json()
        rows = body.get("commissions") or body.get("rows") or []
        # Find the one for our sale
        match = next((x for x in rows if x.get("sale_id") == sale["id"]), None)
        assert match is not None, f"No commission_earned for sale {sale['id']}; got rows: {rows[:3]}"
        # base = line subtotal pre-tax = 500
        assert abs(float(match["base_amount"]) - 500.0) < 0.01
        # commission = 500 * 0.30 = 150
        assert abs(float(match["commission_amount"]) - 150.0) < 0.01
        assert match["status"] == "earned"
        state["commission_id"] = match["id"]

    def test_sale_without_doctor_no_commission(self, H, branch_id, session_id, service_id):
        payload = {
            "branch_id": branch_id,
            "cash_session_id": session_id,
            # no doctor_id
            "items": [{
                "service_id": service_id,
                "name": "TEST_CommServ", "description": "TEST_CommServ",
                "quantity": 1, "unit_price": 500, "tax_rate": 0,
            }],
            "payments": [{"payment_method": "cash", "amount": 500}],
            "customer_name": "TEST_NoDoctor",
        }
        r = requests.post(f"{BASE_URL}/api/clinic/sales", headers=H, json=payload)
        assert r.status_code == 200
        sid = r.json()["id"]
        time.sleep(0.5)
        # No commission row should reference this sale_id
        post = requests.get(
            f"{BASE_URL}/api/clinic/commissions/earned?limit=200",
            headers=H,
        )
        rows = post.json().get("commissions") or []
        assert not any(x.get("sale_id") == sid for x in rows)


# ---------- Dashboard ----------
class TestDashboard:
    def test_dashboard_totals(self, H, doctor_id):
        r = requests.get(
            f"{BASE_URL}/api/clinic/commissions/dashboard?doctor_id={doctor_id}",
            headers=H,
        )
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("total_earned", "total_paid", "total_pending", "by_doctor", "date_from", "date_to"):
            assert k in d, f"Missing {k}: {d}"
        # by_doctor entry for our doctor
        bd = next((x for x in d["by_doctor"] if x["doctor_id"] == doctor_id), None)
        assert bd is not None
        for k in ("base_total", "earned_total", "paid_total", "pending_total", "count", "doctor_name"):
            assert k in bd
        assert bd["count"] >= 1
        assert bd["earned_total"] >= 150.0


# ---------- Bulk pay ----------
class TestPay:
    def test_pay_commission(self, H):
        cid = state["commission_id"]
        r = requests.post(f"{BASE_URL}/api/clinic/commissions/pay", headers=H,
                          json={"commission_ids": [cid], "payment_reference": "TEST_PAY_REF"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["count"] == 1
        assert abs(float(d["total"]) - 150.0) < 0.01

    def test_double_pay_rejected(self, H):
        cid = state["commission_id"]
        r = requests.post(f"{BASE_URL}/api/clinic/commissions/pay", headers=H,
                          json={"commission_ids": [cid]})
        assert r.status_code == 400
        assert "elegible" in r.text.lower() or "ningun" in r.text.lower()

    def test_pay_empty_ids(self, H):
        r = requests.post(f"{BASE_URL}/api/clinic/commissions/pay", headers=H,
                          json={"commission_ids": []})
        assert r.status_code == 400

    def test_paid_visible_after(self, H, doctor_id):
        post = requests.get(
            f"{BASE_URL}/api/clinic/commissions/earned?doctor_id={doctor_id}&status=paid",
            headers=H,
        )
        rows = post.json().get("commissions") or []
        match = next((x for x in rows if x["id"] == state["commission_id"]), None)
        assert match is not None
        assert match["status"] == "paid"
        assert match.get("payment_reference") == "TEST_PAY_REF"
        assert match.get("paid_at")


# ---------- PDF Report ----------
class TestReportPDF:
    def test_pdf_url_returned(self, H):
        r = requests.get(f"{BASE_URL}/api/clinic/commissions/report-pdf", headers=H)
        assert r.status_code == 200, r.text
        d = r.json()
        url = d.get("url") or d.get("pdf_url") or d.get("signed_url")
        assert url and url.startswith("http"), f"Bad url: {d}"
        # Try to fetch it
        rr = requests.get(url, timeout=15)
        assert rr.status_code == 200
        assert rr.headers.get("content-type", "").startswith("application/pdf") or rr.content[:4] == b"%PDF"


# ---------- Cleanup ----------
class TestZCleanup:
    def test_delete_rule_clinic_admin(self, H):
        rid = state.get("rule_id")
        if not rid:
            pytest.skip("No rule")
        r = requests.delete(f"{BASE_URL}/api/clinic/commissions/settings/{rid}", headers=H)
        assert r.status_code == 200
