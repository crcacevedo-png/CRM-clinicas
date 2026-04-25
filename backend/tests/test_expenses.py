"""Test the Expenses module endpoints."""
import os
import io
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    # Read frontend env
    try:
        with open('/app/frontend/.env') as f:
            for line in f:
                if line.startswith('REACT_APP_BACKEND_URL='):
                    BASE_URL = line.split('=', 1)[1].strip().rstrip('/')
                    break
    except Exception:
        pass

CLINIC_EMAIL = "carlos@lasalud.gt"
CLINIC_PWD = "Test123456!"


@pytest.fixture(scope="module")
def auth_headers():
    """Login via Supabase via the backend session-bridge endpoint."""
    s = requests.Session()
    # Login via /api/auth/login or via Supabase. The server uses Supabase JWT.
    # We use /api/auth/login if exists, otherwise direct Supabase auth.
    try:
        r = s.post(f"{BASE_URL}/api/auth/login", json={"email": CLINIC_EMAIL, "password": CLINIC_PWD}, timeout=15)
        if r.status_code == 200:
            tok = r.json().get("access_token") or r.json().get("token")
            if tok:
                return {"Authorization": f"Bearer {tok}"}
    except Exception:
        pass
    # Fallback: Supabase direct
    sb_url = os.environ.get('SUPABASE_URL') or _read_backend_env('SUPABASE_URL')
    sb_key = os.environ.get('SUPABASE_ANON_KEY') or _read_backend_env('SUPABASE_ANON_KEY')
    if sb_url and sb_key:
        r = requests.post(f"{sb_url}/auth/v1/token?grant_type=password",
                          json={"email": CLINIC_EMAIL, "password": CLINIC_PWD},
                          headers={"apikey": sb_key, "Content-Type": "application/json"}, timeout=15)
        if r.status_code == 200:
            return {"Authorization": f"Bearer {r.json()['access_token']}"}
    pytest.skip("Could not authenticate")


def _read_backend_env(key):
    try:
        with open('/app/backend/.env') as f:
            for line in f:
                if line.startswith(f"{key}="):
                    return line.split('=', 1)[1].strip().strip('"').strip("'")
    except Exception:
        return None


# ---------- Dashboard ----------
class TestExpensesDashboard:
    def test_dashboard_keys(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/clinic/expenses/dashboard", headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ["this_month", "prev_month", "delta_pct", "top_category", "pending"]:
            assert k in d
        assert "count" in d["pending"] and "amount" in d["pending"]
        assert "key" in d["top_category"] and "label" in d["top_category"] and "amount" in d["top_category"]


# ---------- List ----------
class TestExpensesList:
    def test_list_basic(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/clinic/expenses?limit=5", headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "expenses" in d and "total" in d and "page" in d and "pages" in d
        assert isinstance(d["expenses"], list)

    def test_list_filter_category(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/clinic/expenses?category=rent", headers=auth_headers, timeout=15)
        assert r.status_code == 200
        for e in r.json()["expenses"]:
            assert e["category"] == "rent"


# ---------- Create / validation ----------
class TestExpensesCreateValidation:
    def test_create_invalid_category(self, auth_headers):
        r = requests.post(f"{BASE_URL}/api/clinic/expenses",
                          json={"category": "BOGUS", "description": "x", "amount": 10},
                          headers=auth_headers, timeout=15)
        assert r.status_code == 400

    def test_create_invalid_payment_method(self, auth_headers):
        r = requests.post(f"{BASE_URL}/api/clinic/expenses",
                          json={"category": "rent", "description": "x", "amount": 10,
                                "payment_method": "BOGUS"},
                          headers=auth_headers, timeout=15)
        assert r.status_code == 400

    def test_create_invalid_payment_status(self, auth_headers):
        r = requests.post(f"{BASE_URL}/api/clinic/expenses",
                          json={"category": "rent", "description": "x", "amount": 10,
                                "payment_status": "BOGUS"},
                          headers=auth_headers, timeout=15)
        assert r.status_code == 400

    def test_create_missing_description(self, auth_headers):
        r = requests.post(f"{BASE_URL}/api/clinic/expenses",
                          json={"category": "rent", "amount": 10},
                          headers=auth_headers, timeout=15)
        assert r.status_code == 400


# ---------- Full flow (create, total math, get, update, attachment, delete) ----------
class TestExpensesFullFlow:
    expense_id = None

    def test_create_with_total_calc(self, auth_headers):
        payload = {
            "category": "supplies",
            "description": "TEST_supplies for tests",
            "amount": 1000,
            "tax_amount": 120,
            "payment_method": "cash",
            "payment_status": "paid",
            "document_type": "Recibo",
            "document_number": "TST-001",
            "expense_date": "2026-01-10",
        }
        r = requests.post(f"{BASE_URL}/api/clinic/expenses", json=payload,
                          headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["total"] == 1120
        assert "id" in d
        TestExpensesFullFlow.expense_id = d["id"]

    def test_appears_in_list(self, auth_headers):
        eid = TestExpensesFullFlow.expense_id
        assert eid
        r = requests.get(f"{BASE_URL}/api/clinic/expenses?category=supplies&limit=50",
                         headers=auth_headers, timeout=15)
        assert r.status_code == 200
        ids = [e["id"] for e in r.json()["expenses"]]
        assert eid in ids
        match = next(e for e in r.json()["expenses"] if e["id"] == eid)
        assert match["amount"] == 1000
        assert match["tax_amount"] == 120
        assert match["total"] == 1120

    def test_update_recomputes_total(self, auth_headers):
        eid = TestExpensesFullFlow.expense_id
        assert eid
        r = requests.put(f"{BASE_URL}/api/clinic/expenses/{eid}",
                         json={"amount": 2000, "tax_amount": 240},
                         headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text
        # Verify
        rl = requests.get(f"{BASE_URL}/api/clinic/expenses?category=supplies&limit=50",
                          headers=auth_headers, timeout=15)
        match = next(e for e in rl.json()["expenses"] if e["id"] == eid)
        assert match["amount"] == 2000
        assert match["tax_amount"] == 240
        assert match["total"] == 2240

    def test_upload_attachment(self, auth_headers):
        eid = TestExpensesFullFlow.expense_id
        assert eid
        # Tiny PNG
        png = bytes.fromhex(
            "89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C4"
            "890000000D49444154789C636060606000000005000148AFA4F70000000049454E44AE426082"
        )
        files = {"file": ("receipt.png", io.BytesIO(png), "image/png")}
        h = {k: v for k, v in auth_headers.items() if k != "Content-Type"}
        r = requests.post(f"{BASE_URL}/api/clinic/expenses/{eid}/attachment",
                          files=files, headers=h, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "url" in d and d["url"]
        assert "path" in d

    def test_get_attachment_signed_url(self, auth_headers):
        eid = TestExpensesFullFlow.expense_id
        assert eid
        r = requests.get(f"{BASE_URL}/api/clinic/expenses/{eid}/attachment-url",
                         headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text
        assert "url" in r.json()
        assert r.json()["url"]

    def test_delete_cleanup(self, auth_headers):
        eid = TestExpensesFullFlow.expense_id
        assert eid
        r = requests.delete(f"{BASE_URL}/api/clinic/expenses/{eid}",
                            headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text


# ---------- Reports ----------
class TestExpensesReports:
    def test_by_category_format(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/clinic/expenses/by-category",
                         headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "categories" in d and "total" in d
        # Sorted desc
        amounts = [c["amount"] for c in d["categories"]]
        assert amounts == sorted(amounts, reverse=True)
        # Each entry has label
        for c in d["categories"]:
            assert "category" in c and "label" in c and "amount" in c and "count" in c

    def test_by_supplier_format(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/clinic/expenses/by-supplier",
                         headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "suppliers" in d and "total" in d
        for s in d["suppliers"]:
            assert "supplier_id" in s and "supplier_name" in s and "amount" in s and "count" in s
