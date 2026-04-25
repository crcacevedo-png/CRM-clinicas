"""
Accounts Receivable Module Tests - Backend
Endpoints covered:
- GET  /api/clinic/accounts-receivable/dashboard
- GET  /api/clinic/accounts-receivable/aging
- GET  /api/clinic/accounts-receivable/installments
- GET  /api/clinic/accounts-receivable
- GET  /api/clinic/accounts-receivable/{id}
- POST /api/clinic/accounts-receivable/{id}/payment
- POST /api/clinic/accounts-receivable/{id}/payment-plan
- Sales: create_sale auto-creates AR row when amount_due>0
"""
import os
import time
import uuid
import pytest
import requests
from datetime import datetime, timedelta, date, timezone

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
EMAIL = "carlos@lasalud.gt"
PASS = "Test123456!"
CLINIC_ID = "c0321ed8-97da-47a1-b601-3b94bffabdd7"

state = {}


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASS})
    assert r.status_code == 200, f"Login failed: {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def H(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def branch_id(H):
    r = requests.get(f"{BASE_URL}/api/clinic/branches", headers=H)
    assert r.status_code == 200
    return r.json()[0]["id"]


@pytest.fixture(scope="module")
def patient_id(H):
    r = requests.get(f"{BASE_URL}/api/clinic/patients?limit=1", headers=H)
    assert r.status_code == 200
    body = r.json()
    items = body.get("items") or body.get("patients") or body
    if isinstance(items, dict):
        items = items.get("items") or items.get("patients") or []
    assert len(items) > 0, "Need at least 1 patient seeded"
    return items[0]["id"]


@pytest.fixture(scope="module")
def service_id(H):
    r = requests.get(f"{BASE_URL}/api/clinic/sales/services?q=TEST_", headers=H)
    if r.status_code == 200 and r.json():
        return r.json()[0]["id"]
    # Create a service
    payload = {"name": "TEST_AR_Service", "price": 500, "category": "consulta"}
    r = requests.post(f"{BASE_URL}/api/clinic/sales/services", headers=H, json=payload)
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


@pytest.fixture(scope="module")
def cash_session(H, branch_id):
    """Ensure a cash session is open (or open one) for sales."""
    r = requests.get(f"{BASE_URL}/api/clinic/sales/cash-session/current", headers=H)
    if r.status_code == 200:
        body = r.json() or {}
        sess = body.get("session") if isinstance(body, dict) else None
        if sess and sess.get("id"):
            return sess["id"]
    # Need a register
    rr = requests.get(f"{BASE_URL}/api/clinic/sales/cash-registers", headers=H)
    regs = rr.json() if rr.status_code == 200 else []
    if not regs:
        rc = requests.post(f"{BASE_URL}/api/clinic/sales/cash-registers", headers=H,
                           json={"name": "TEST_Caja_AR", "branch_id": branch_id})
        assert rc.status_code in (200, 201), rc.text
        reg_id = rc.json()["id"]
    else:
        reg_id = regs[0]["id"]
    ro = requests.post(f"{BASE_URL}/api/clinic/sales/cash-session/open", headers=H,
                      json={"cash_register_id": reg_id, "opening_amount": 0})
    assert ro.status_code in (200, 201), ro.text
    return ro.json()["id"]


# ---------- 1. Auto-create AR on sale with debt ----------
class TestSaleCreatesAR:
    def test_create_sale_with_balance_creates_ar(self, H, branch_id, patient_id, service_id, cash_session):
        # Sale Q500, pay Q200 cash, due Q300
        payload = {
            "patient_id": patient_id,
            "branch_id": branch_id,
            "items": [{"description": "TEST_AR_Service", "quantity": 1, "unit_price": 500, "service_id": service_id}],
            "payments": [{"payment_method": "cash", "amount": 200}],
        }
        r = requests.post(f"{BASE_URL}/api/clinic/sales", headers=H, json=payload)
        assert r.status_code in (200, 201), r.text
        sale = r.json()
        assert sale["amount_due"] == 300
        assert sale["payment_status"] in ("partial", "pending")
        state["sale_id"] = sale["id"]
        state["sale_number"] = sale["sale_number"]
        # Wait briefly for AR insert
        time.sleep(1)
        # Verify AR was created via list endpoint
        rl = requests.get(f"{BASE_URL}/api/clinic/accounts-receivable?status=pending&limit=50",
                          headers=H)
        assert rl.status_code == 200
        accounts = rl.json()["accounts"]
        ar = next((a for a in accounts if a.get("sale_id") == sale["id"]), None)
        assert ar is not None, f"AR not auto-created for sale {sale['id']}"
        assert ar["original_amount"] == 500
        assert ar["paid_amount"] == 200
        assert ar["balance"] == 300
        assert ar["status"] == "pending"
        assert ar.get("due_date"), "due_date should default to +30d"
        state["ar_id"] = ar["id"]


# ---------- 2. Dashboard ----------
class TestDashboard:
    def test_dashboard_keys(self, H):
        r = requests.get(f"{BASE_URL}/api/clinic/accounts-receivable/dashboard", headers=H)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("total_balance", "patients_with_debt", "overdue", "upcoming_30d"):
            assert k in d, f"missing {k}"
        assert "count" in d["overdue"] and "amount" in d["overdue"]
        assert "count" in d["upcoming_30d"] and "amount" in d["upcoming_30d"]
        assert isinstance(d["total_balance"], (int, float))
        # Total balance must include our new Q300
        assert d["total_balance"] >= 300


# ---------- 3. Aging ----------
class TestAging:
    def test_aging_buckets(self, H):
        r = requests.get(f"{BASE_URL}/api/clinic/accounts-receivable/aging", headers=H)
        assert r.status_code == 200, r.text
        b = r.json()
        for k in ("current", "d1_30", "d31_60", "d61_90", "d90_plus"):
            assert k in b, f"missing bucket {k}"
            assert "count" in b[k] and "amount" in b[k]


# ---------- 4. List with filters ----------
class TestList:
    def test_list_default(self, H):
        r = requests.get(f"{BASE_URL}/api/clinic/accounts-receivable", headers=H)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "accounts" in body and "total" in body and "page" in body
        assert isinstance(body["accounts"], list)

    def test_list_filter_status_pending(self, H):
        r = requests.get(f"{BASE_URL}/api/clinic/accounts-receivable?status=pending",
                         headers=H)
        assert r.status_code == 200
        for a in r.json()["accounts"]:
            assert a["status"] == "pending"

    def test_list_only_overdue_no_crash(self, H):
        r = requests.get(f"{BASE_URL}/api/clinic/accounts-receivable?only_overdue=true",
                         headers=H)
        assert r.status_code == 200

    def test_list_search(self, H):
        # Search a patient_name token unlikely to crash
        r = requests.get(f"{BASE_URL}/api/clinic/accounts-receivable?q=TEST", headers=H)
        assert r.status_code == 200


# ---------- 5. Detail ----------
class TestDetail:
    def test_detail_has_sale_and_payments(self, H):
        ar_id = state.get("ar_id")
        assert ar_id, "Need ar_id from earlier test"
        r = requests.get(f"{BASE_URL}/api/clinic/accounts-receivable/{ar_id}", headers=H)
        assert r.status_code == 200, r.text
        ar = r.json()
        assert ar["id"] == ar_id
        assert ar["balance"] == 300
        assert "sale" in ar and ar["sale"] is not None
        assert "items" in ar["sale"]
        assert "initial_payments" in ar
        assert len(ar["initial_payments"]) >= 1
        assert ar["initial_payments"][0]["payment_method"] == "cash"
        assert "ar_payments" in ar
        assert "installments_list" in ar


# ---------- 6. Register payment ----------
class TestRegisterPayment:
    def test_invalid_method_card(self, H):
        ar_id = state.get("ar_id")
        r = requests.post(f"{BASE_URL}/api/clinic/accounts-receivable/{ar_id}/payment",
                          headers=H, json={"amount": 50, "payment_method": "card"})
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"

    def test_invalid_method_bogus(self, H):
        ar_id = state.get("ar_id")
        r = requests.post(f"{BASE_URL}/api/clinic/accounts-receivable/{ar_id}/payment",
                          headers=H, json={"amount": 50, "payment_method": "BOGUS"})
        assert r.status_code == 400

    def test_invalid_amount_zero(self, H):
        ar_id = state.get("ar_id")
        r = requests.post(f"{BASE_URL}/api/clinic/accounts-receivable/{ar_id}/payment",
                          headers=H, json={"amount": 0, "payment_method": "cash"})
        assert r.status_code == 400

    def test_register_partial_payment_syncs_sale(self, H):
        ar_id = state.get("ar_id")
        sale_id = state.get("sale_id")
        # Pay Q100 cash → balance should drop to 200, sale.amount_due should drop to 200
        r = requests.post(f"{BASE_URL}/api/clinic/accounts-receivable/{ar_id}/payment",
                          headers=H, json={"amount": 100, "payment_method": "cash",
                                           "reference": "TEST_REF_1"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["new_balance"] == 200
        assert body["status"] == "partial"
        # Verify via GET detail
        rd = requests.get(f"{BASE_URL}/api/clinic/accounts-receivable/{ar_id}", headers=H)
        ar = rd.json()
        assert ar["balance"] == 200
        assert ar["paid_amount"] == 300
        assert ar["status"] == "partial"
        assert len(ar["ar_payments"]) >= 1
        # Verify sale was synced
        rs = requests.get(f"{BASE_URL}/api/clinic/sales/{sale_id}", headers=H)
        assert rs.status_code == 200
        sale = rs.json()
        assert sale["amount_paid"] == 300
        assert sale["amount_due"] == 200
        assert sale["payment_status"] == "partial"


# ---------- 7. Payment plan ----------
class TestPaymentPlan:
    def test_plan_min_installments(self, H):
        ar_id = state.get("ar_id")
        r = requests.post(f"{BASE_URL}/api/clinic/accounts-receivable/{ar_id}/payment-plan",
                          headers=H, json={"installments": 1,
                                           "first_due_date": (date.today() + timedelta(days=7)).isoformat()})
        assert r.status_code == 400

    def test_plan_missing_first_due(self, H):
        ar_id = state.get("ar_id")
        r = requests.post(f"{BASE_URL}/api/clinic/accounts-receivable/{ar_id}/payment-plan",
                          headers=H, json={"installments": 3})
        assert r.status_code == 400

    def test_plan_create_3_monthly(self, H):
        ar_id = state.get("ar_id")
        first = (date.today() + timedelta(days=7)).isoformat()
        r = requests.post(f"{BASE_URL}/api/clinic/accounts-receivable/{ar_id}/payment-plan",
                          headers=H, json={"installments": 3, "first_due_date": first,
                                           "frequency": "monthly"})
        assert r.status_code == 200, r.text
        # Verify detail shows installments_list with 3 rows
        rd = requests.get(f"{BASE_URL}/api/clinic/accounts-receivable/{ar_id}", headers=H)
        ar = rd.json()
        assert ar["has_payment_plan"] is True
        assert ar["installments"] == 3
        ins = ar["installments_list"]
        assert len(ins) == 3
        nums = sorted(i["installment_number"] for i in ins)
        assert nums == [1, 2, 3]
        # Sum of amounts == balance
        assert round(sum(float(i["amount"]) for i in ins), 2) == 200.00
        # All pending
        assert all(i["status"] == "pending" for i in ins)


# ---------- 8. Installments tab ----------
class TestInstallments:
    def test_list_pending_installments(self, H):
        r = requests.get(f"{BASE_URL}/api/clinic/accounts-receivable/installments?days_ahead=120",
                         headers=H)
        assert r.status_code == 200, r.text
        ins = r.json()
        assert isinstance(ins, list)
        # Should include the 3 we just created (within 90 days)
        ar_id = state.get("ar_id")
        ours = [i for i in ins if i["account_receivable_id"] == ar_id]
        assert len(ours) >= 3
        # Each has patient_name and days_to_due
        for i in ours:
            assert "patient_name" in i
            assert "days_to_due" in i
            assert isinstance(i["days_to_due"], int)
