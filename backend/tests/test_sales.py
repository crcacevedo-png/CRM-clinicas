"""
Sales / POS Module Tests - Backend
Endpoints covered:
- /api/clinic/sales/services (GET, POST, PUT)
- /api/clinic/sales/cash-registers (GET, POST)
- /api/clinic/sales/cash-session/open, /current, /{id}/close, /{id}/summary
- /api/clinic/sales (POST, GET)
- /api/clinic/sales/{id} (GET)
- /api/clinic/sales/{id}/cancel (POST)
- /api/clinic/sales/{id}/pdf-url (GET)
- /api/clinic/sales/daily-summary
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
EMAIL = "carlos@lasalud.gt"
PASS = "Test123456!"
CLINIC_ID = "c0321ed8-97da-47a1-b601-3b94bffabdd7"

# Module-level state (shared across tests in declared order)
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
    branches = r.json()
    assert len(branches) > 0
    return branches[0]["id"]


# ---------- Feature flag ----------
class TestFeature:
    def test_sales_feature_enabled(self, H):
        r = requests.get(f"{BASE_URL}/api/clinic/features", headers=H)
        assert r.status_code == 200
        feats = r.json().get("features", [])
        assert "sales" in feats, f"'sales' not in features: {feats}"


# ---------- Services CRUD ----------
class TestServices:
    def test_create_service(self, H):
        payload = {"name": "TEST_Consulta", "price": 200, "tax_rate": 12, "duration_minutes": 30, "category": "Consultas"}
        r = requests.post(f"{BASE_URL}/api/clinic/sales/services", headers=H, json=payload)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "id" in d
        state["service_id"] = d["id"]

    def test_create_service_2(self, H):
        payload = {"name": "TEST_Limpieza", "price": 350.50, "tax_rate": 12, "duration_minutes": 45}
        r = requests.post(f"{BASE_URL}/api/clinic/sales/services", headers=H, json=payload)
        assert r.status_code == 200
        state["service_id_2"] = r.json()["id"]

    def test_list_services(self, H):
        r = requests.get(f"{BASE_URL}/api/clinic/sales/services", headers=H)
        assert r.status_code == 200
        items = r.json()
        names = [s["name"] for s in items]
        assert "TEST_Consulta" in names
        assert "TEST_Limpieza" in names
        # Check fields
        s1 = next(s for s in items if s["name"] == "TEST_Consulta")
        assert float(s1["price"]) == 200
        assert int(s1.get("tax_rate") or 0) == 12

    def test_update_service(self, H):
        sid = state["service_id"]
        r = requests.put(f"{BASE_URL}/api/clinic/sales/services/{sid}", headers=H,
                         json={"price": 250, "name": "TEST_Consulta_Upd"})
        assert r.status_code == 200
        # Verify persistence
        r2 = requests.get(f"{BASE_URL}/api/clinic/sales/services?q=TEST_Consulta_Upd", headers=H)
        items = r2.json()
        s = next((x for x in items if x["id"] == sid), None)
        assert s is not None
        assert float(s["price"]) == 250
        assert s["name"] == "TEST_Consulta_Upd"


# ---------- Cash Registers ----------
class TestCashRegisters:
    def test_create_register_requires_branch(self, H):
        r = requests.post(f"{BASE_URL}/api/clinic/sales/cash-registers", headers=H,
                          json={"name": "TEST_NoBranch"})
        assert r.status_code == 400

    def test_create_register(self, H, branch_id):
        r = requests.post(f"{BASE_URL}/api/clinic/sales/cash-registers", headers=H,
                          json={"name": "TEST_Caja_Principal", "branch_id": branch_id})
        assert r.status_code == 200, r.text
        state["register_id"] = r.json()["id"]

    def test_list_registers(self, H):
        r = requests.get(f"{BASE_URL}/api/clinic/sales/cash-registers", headers=H)
        assert r.status_code == 200
        items = r.json()
        ids = [x["id"] for x in items]
        assert state["register_id"] in ids
        # Has branch_name enrichment
        reg = next(x for x in items if x["id"] == state["register_id"])
        assert "branch_name" in reg


# ---------- Cash Session lifecycle ----------
class TestCashSession:
    def test_no_current_session_initially(self, H):
        r = requests.get(f"{BASE_URL}/api/clinic/sales/cash-session/current", headers=H)
        assert r.status_code == 200
        # If a session is already open from prior test, close it first (defensive)
        sess = r.json().get("session")
        if sess and sess.get("status") == "open":
            requests.post(f"{BASE_URL}/api/clinic/sales/cash-session/{sess['id']}/close",
                          headers=H, json={"actual_amount": 0})

    def test_open_session_requires_register(self, H):
        r = requests.post(f"{BASE_URL}/api/clinic/sales/cash-session/open", headers=H, json={})
        assert r.status_code == 400

    def test_open_session(self, H):
        r = requests.post(f"{BASE_URL}/api/clinic/sales/cash-session/open", headers=H,
                          json={"cash_register_id": state["register_id"], "opening_amount": 500})
        assert r.status_code == 200, r.text
        state["session_id"] = r.json()["id"]

    def test_double_open_blocked(self, H):
        r = requests.post(f"{BASE_URL}/api/clinic/sales/cash-session/open", headers=H,
                          json={"cash_register_id": state["register_id"], "opening_amount": 100})
        assert r.status_code == 400

    def test_get_current_session(self, H):
        r = requests.get(f"{BASE_URL}/api/clinic/sales/cash-session/current", headers=H)
        assert r.status_code == 200
        sess = r.json().get("session")
        assert sess is not None
        assert sess["id"] == state["session_id"]
        assert sess["status"] == "open"
        assert float(sess["opening_amount"]) == 500
        assert "cash_register_name" in sess
        assert "branch_id" in sess


# ---------- Sales (POS) ----------
class TestSales:
    def test_create_sale_cash_exact(self, H, branch_id):
        # 1 service @250 incl tax 12% -> total = 250 + 30 = 280
        payload = {
            "branch_id": branch_id,
            "cash_session_id": state["session_id"],
            "items": [{
                "service_id": state["service_id"],
                "name": "TEST_Consulta_Upd",
                "description": "TEST_Consulta_Upd",
                "quantity": 1,
                "unit_price": 250,
                "tax_rate": 12,
                "discount_pct": 0,
            }],
            "payments": [{"payment_method": "cash", "amount": 280}],
            "customer_name": "Cliente Cash",
        }
        r = requests.post(f"{BASE_URL}/api/clinic/sales", headers=H, json=payload)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["payment_status"] == "paid"
        assert abs(float(d["total"]) - 280.0) < 0.01
        assert float(d["amount_due"]) == 0
        assert d["sale_number"].startswith("V-")
        state["sale_id_cash"] = d["id"]
        state["sale_number_cash"] = d["sale_number"]

    def test_create_sale_partial_pending(self, H, branch_id):
        # Service 350.50 + IVA 12% = 392.56; pay 200 cash → partial
        payload = {
            "branch_id": branch_id,
            "cash_session_id": state["session_id"],
            "items": [{
                "service_id": state["service_id_2"],
                "name": "TEST_Limpieza",
                "description": "TEST_Limpieza",
                "quantity": 1,
                "unit_price": 350.50,
                "tax_rate": 12,
            }],
            "payments": [{"payment_method": "cash", "amount": 200}],
            "customer_name": "Cliente Parcial",
        }
        r = requests.post(f"{BASE_URL}/api/clinic/sales", headers=H, json=payload)
        assert r.status_code == 200, r.text
        d = r.json()
        assert abs(float(d["total"]) - 392.56) < 0.05
        assert d["payment_status"] == "partial"
        assert float(d["amount_due"]) > 0
        state["sale_id_partial"] = d["id"]

    def test_create_sale_mixed_card_cash(self, H, branch_id):
        # 2 x service @ 250 = 500 + IVA 60 = 560; pay 300 card + 260 cash
        payload = {
            "branch_id": branch_id,
            "cash_session_id": state["session_id"],
            "items": [{
                "service_id": state["service_id"],
                "description": "TEST_Consulta_Upd",
                "quantity": 2,
                "unit_price": 250,
                "tax_rate": 12,
            }],
            "payments": [
                {"payment_method": "card", "amount": 300},
                {"payment_method": "cash", "amount": 260},
            ],
        }
        r = requests.post(f"{BASE_URL}/api/clinic/sales", headers=H, json=payload)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["payment_status"] == "paid"
        assert abs(float(d["total"]) - 560.0) < 0.01
        state["sale_id_mixed"] = d["id"]

    def test_create_sale_requires_items(self, H, branch_id):
        r = requests.post(f"{BASE_URL}/api/clinic/sales", headers=H,
                          json={"branch_id": branch_id, "items": [], "payments": []})
        assert r.status_code == 400

    def test_get_sale_detail(self, H):
        sid = state["sale_id_cash"]
        r = requests.get(f"{BASE_URL}/api/clinic/sales/{sid}", headers=H)
        assert r.status_code == 200
        d = r.json()
        assert d["id"] == sid
        assert "items" in d and len(d["items"]) == 1
        assert "payments" in d and len(d["payments"]) == 1
        assert d["payments"][0]["payment_method"] == "cash"
        assert "cashier_name" in d

    def test_list_sales_today(self, H):
        from datetime import date
        today = date.today().isoformat()
        r = requests.get(f"{BASE_URL}/api/clinic/sales", headers=H,
                         params={"date_from": today})
        assert r.status_code == 200
        d = r.json()
        ids = [s["id"] for s in d["sales"]]
        assert state["sale_id_cash"] in ids
        assert state["sale_id_partial"] in ids
        assert state["sale_id_mixed"] in ids

    def test_daily_summary(self, H):
        r = requests.get(f"{BASE_URL}/api/clinic/sales/daily-summary", headers=H)
        assert r.status_code == 200
        d = r.json()
        # 3 sales created: 280 + 392.56 + 560 = 1232.56
        assert d["count"] >= 3
        assert d["total"] >= 1232
        assert d["cash"] >= 280 + 200 + 260  # 740
        assert d["card"] >= 300
        assert d["pending_due"] > 0  # from partial sale

    def test_cancel_sale(self, H):
        sid = state["sale_id_partial"]
        r = requests.post(f"{BASE_URL}/api/clinic/sales/{sid}/cancel", headers=H,
                          json={"reason": "Test cancellation"})
        assert r.status_code == 200
        # Verify
        r2 = requests.get(f"{BASE_URL}/api/clinic/sales/{sid}", headers=H)
        assert r2.json()["status"] == "cancelled"

    def test_cancel_already_cancelled(self, H):
        sid = state["sale_id_partial"]
        r = requests.post(f"{BASE_URL}/api/clinic/sales/{sid}/cancel", headers=H,
                          json={"reason": "again"})
        assert r.status_code == 400

    def test_pdf_url(self, H):
        sid = state["sale_id_cash"]
        # Allow time for background PDF generation
        time.sleep(2)
        r = requests.get(f"{BASE_URL}/api/clinic/sales/{sid}/pdf-url", headers=H)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "url" in d
        assert d["url"], "PDF url should not be empty"


# ---------- Cash session summary & close ----------
class TestCloseSession:
    def test_summary(self, H):
        sid = state["session_id"]
        r = requests.get(f"{BASE_URL}/api/clinic/sales/cash-session/{sid}/summary", headers=H)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["opening"] == 500
        # cash_total = sale1 (280) + sale3 (260) = 540 (sale2 cancelled, excluded)
        assert d["totals"]["cash"] >= 540
        assert d["totals"]["card"] >= 300
        # expected = opening + cash
        assert d["expected"] >= 500 + 540

    def test_close_session(self, H):
        sid = state["session_id"]
        # Get expected
        s = requests.get(f"{BASE_URL}/api/clinic/sales/cash-session/{sid}/summary", headers=H).json()
        expected = s["expected"]
        # Close with actual = expected + 5 → difference = 5
        actual = expected + 5
        r = requests.post(f"{BASE_URL}/api/clinic/sales/cash-session/{sid}/close", headers=H,
                          json={"actual_amount": actual})
        assert r.status_code == 200, r.text
        d = r.json()
        assert abs(float(d["expected"]) - expected) < 0.01
        assert abs(float(d["actual"]) - actual) < 0.01
        assert abs(float(d["difference"]) - 5) < 0.01

    def test_close_session_already_closed(self, H):
        sid = state["session_id"]
        r = requests.post(f"{BASE_URL}/api/clinic/sales/cash-session/{sid}/close", headers=H,
                          json={"actual_amount": 0})
        assert r.status_code == 400

    def test_current_after_close(self, H):
        r = requests.get(f"{BASE_URL}/api/clinic/sales/cash-session/current", headers=H)
        assert r.status_code == 200
        assert r.json().get("session") is None


# ---------- Auth ----------
class TestAuth:
    def test_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/clinic/sales/services")
        assert r.status_code in (401, 403)
