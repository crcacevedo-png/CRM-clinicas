"""Backend tests for iteration 36:
- Papelera (soft delete + trash + restore + purge) for clinics and users
- Insurance payments in POS (validation, providers autocomplete, AR persistence)
- Accounts Receivable filters (insurance, date_from, date_to)
- User guide PDF regression
"""
import os
import time
import uuid
from datetime import datetime, timezone, timedelta
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"

SUPER_ADMIN_EMAIL = "info@cortexiagt.com"
SUPER_ADMIN_PASSWORD = "Armagedon1980$"
CLINIC_ADMIN_EMAIL = "prueba3@gmail.com"
CLINIC_ADMIN_PASSWORD = "Test123456!"
REAL_CLINIC_ID = "c0321ed8-97da-47a1-b601-3b94bffabdd7"
BRANCH_ID = "79c47aab-3d03-49a0-bcec-b931766aa48e"


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed {email}: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def super_headers():
    return {"Authorization": f"Bearer {_login(SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD)}",
            "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def clinic_headers():
    try:
        tok = _login(CLINIC_ADMIN_EMAIL, CLINIC_ADMIN_PASSWORD)
    except AssertionError as e:
        pytest.skip(f"clinic_admin login unavailable: {e}")
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def _create_disposable_clinic(headers):
    ts = int(time.time() * 1000)
    unique = uuid.uuid4().hex[:8]
    name = f"TEST_TRASH_{ts}_{unique}"
    payload = {
        "name": name, "country": "GT", "city": "GT", "plan": "free",
        "admin_name": "Trash", "admin_lastname": "Admin",
        "admin_email": f"test_trash_{ts}_{unique}@example.com",
        "admin_password": "Kx9$mPzeta2026Q!",
    }
    r = requests.post(f"{API}/admin/clinics", json=payload, headers=headers, timeout=60)
    assert r.status_code == 200, f"create clinic failed: {r.text}"
    return {"name": name, "id": r.json()["clinic"]["id"]}


def _add_member(headers, clinic_id):
    ts = int(time.time() * 1000)
    unique = uuid.uuid4().hex[:8]
    email = f"test_trash_m_{ts}_{unique}@example.com"
    r = requests.post(f"{API}/admin/clinics/{clinic_id}/members", headers=headers, timeout=30, json={
        "name": "Trash", "lastname": "Member", "email": email,
        "password": "Kx9$mPzeta2026Q!", "role": "receptionist",
    })
    assert r.status_code == 200, r.text
    r2 = requests.get(f"{API}/admin/trash", headers=headers, timeout=30)
    # find in users listing (not trash)
    r3 = requests.get(f"{API}/admin/users?clinic_id={clinic_id}", headers=headers, timeout=30)
    mem = [m for m in r3.json() if m.get("email") == email]
    assert mem, f"member not found: {email}"
    return {"id": mem[0]["id"], "email": email}


def _purge_disposable(headers, clinic_id):
    """Best effort: soft-delete then purge."""
    try:
        c = requests.get(f"{API}/admin/clinics/{clinic_id}", headers=headers, timeout=30)
        if c.status_code == 200:
            name = c.json()["clinic"]["name"]
            requests.delete(f"{API}/admin/clinics/{clinic_id}?confirm_name={name}", headers=headers, timeout=60)
    except Exception:
        pass
    try:
        requests.delete(f"{API}/admin/trash/clinics/{clinic_id}", headers=headers, timeout=90)
    except Exception:
        pass


# ================================================================
# PAPELERA — clinics
# ================================================================
class TestTrashClinic:
    def test_soft_delete_moves_to_trash(self, super_headers):
        info = _create_disposable_clinic(super_headers)
        try:
            # Delete with correct name → soft delete
            r = requests.delete(f"{API}/admin/clinics/{info['id']}?confirm_name={info['name']}",
                                headers=super_headers, timeout=60)
            assert r.status_code == 200, r.text
            body = r.json()
            assert "deleted_at" in body
            assert body.get("clinic_id") == info["id"]

            # GET /admin/clinics should NOT show it
            r = requests.get(f"{API}/admin/clinics", headers=super_headers, timeout=30)
            ids = [c["id"] for c in r.json()]
            assert info["id"] not in ids, "clinic still visible in list after soft delete"

            # GET /admin/trash should show it
            r = requests.get(f"{API}/admin/trash", headers=super_headers, timeout=30)
            assert r.status_code == 200
            tr = r.json()
            clinics = tr.get("clinics", [])
            found = [c for c in clinics if c["id"] == info["id"]]
            assert found, "clinic not in trash listing"
            assert found[0].get("deleted_at")
            assert 28 <= found[0].get("days_left", 0) <= 30

            # Members should also be soft-deleted (not in users list)
            r = requests.get(f"{API}/admin/users?clinic_id={info['id']}", headers=super_headers, timeout=30)
            assert r.status_code == 200
            assert r.json() == [] or all(u.get("clinic_id") != info["id"] for u in r.json())
            # And appear in trash.users
            users_in_trash = [u for u in tr.get("users", []) if u.get("clinic_id") == info["id"]]
            assert users_in_trash, "clinic members not soft-deleted with clinic"
        finally:
            _purge_disposable(super_headers, info["id"])

    def test_restore_clinic_and_members(self, super_headers):
        info = _create_disposable_clinic(super_headers)
        try:
            requests.delete(f"{API}/admin/clinics/{info['id']}?confirm_name={info['name']}",
                            headers=super_headers, timeout=60)
            r = requests.post(f"{API}/admin/trash/clinics/{info['id']}/restore",
                              headers=super_headers, timeout=60)
            assert r.status_code == 200, r.text
            # Should reappear in list
            r = requests.get(f"{API}/admin/clinics", headers=super_headers, timeout=30)
            ids = [c["id"] for c in r.json()]
            assert info["id"] in ids
            # Members restored
            r = requests.get(f"{API}/admin/users?clinic_id={info['id']}", headers=super_headers, timeout=30)
            assert r.status_code == 200
            assert len(r.json()) >= 1, "admin member not restored"
        finally:
            _purge_disposable(super_headers, info["id"])

    def test_purge_requires_in_trash(self, super_headers):
        info = _create_disposable_clinic(super_headers)
        try:
            # Try to purge a clinic that is NOT in trash → 400
            r = requests.delete(f"{API}/admin/trash/clinics/{info['id']}",
                                headers=super_headers, timeout=60)
            assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"
        finally:
            _purge_disposable(super_headers, info["id"])

    def test_purge_removes_row(self, super_headers):
        info = _create_disposable_clinic(super_headers)
        # Soft delete
        r = requests.delete(f"{API}/admin/clinics/{info['id']}?confirm_name={info['name']}",
                            headers=super_headers, timeout=60)
        assert r.status_code == 200
        # Now purge
        r = requests.delete(f"{API}/admin/trash/clinics/{info['id']}",
                            headers=super_headers, timeout=90)
        assert r.status_code == 200, r.text
        assert "purge_stats" in r.json()
        # Verify gone from trash
        r = requests.get(f"{API}/admin/trash", headers=super_headers, timeout=30)
        ids = [c["id"] for c in r.json().get("clinics", [])]
        assert info["id"] not in ids


# ================================================================
# PAPELERA — users
# ================================================================
class TestTrashUser:
    def test_user_soft_delete_and_restore(self, super_headers):
        info = _create_disposable_clinic(super_headers)
        try:
            member = _add_member(super_headers, info["id"])
            # Soft-delete
            r = requests.delete(f"{API}/admin/users/{member['id']}",
                                headers=super_headers, timeout=60)
            assert r.status_code == 200, r.text
            body = r.json()
            assert body.get("deleted_at")
            # Should be in trash
            r = requests.get(f"{API}/admin/trash", headers=super_headers, timeout=30)
            u_ids = [u["id"] for u in r.json().get("users", [])]
            assert member["id"] in u_ids
            # Restore
            r = requests.post(f"{API}/admin/trash/users/{member['id']}/restore",
                              headers=super_headers, timeout=30)
            assert r.status_code == 200, r.text
            # Should appear again in normal list
            r = requests.get(f"{API}/admin/users?clinic_id={info['id']}",
                             headers=super_headers, timeout=30)
            emails = [u.get("email") for u in r.json()]
            assert member["email"] in emails
        finally:
            _purge_disposable(super_headers, info["id"])

    def test_restore_user_blocked_if_clinic_in_trash(self, super_headers):
        info = _create_disposable_clinic(super_headers)
        try:
            member = _add_member(super_headers, info["id"])
            # Soft-delete the clinic (also soft-deletes members)
            requests.delete(f"{API}/admin/clinics/{info['id']}?confirm_name={info['name']}",
                            headers=super_headers, timeout=60)
            # Attempt to restore user while clinic is trashed → 400
            r = requests.post(f"{API}/admin/trash/users/{member['id']}/restore",
                              headers=super_headers, timeout=30)
            assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"
            detail = (r.json().get("detail") or "").lower()
            assert "clinica" in detail or "clínica" in detail
        finally:
            _purge_disposable(super_headers, info["id"])

    def test_purge_user_now(self, super_headers):
        info = _create_disposable_clinic(super_headers)
        try:
            member = _add_member(super_headers, info["id"])
            requests.delete(f"{API}/admin/users/{member['id']}", headers=super_headers, timeout=30)
            r = requests.delete(f"{API}/admin/trash/users/{member['id']}",
                                headers=super_headers, timeout=60)
            assert r.status_code == 200, r.text
            # Verify gone from trash
            r = requests.get(f"{API}/admin/trash", headers=super_headers, timeout=30)
            u_ids = [u["id"] for u in r.json().get("users", [])]
            assert member["id"] not in u_ids
        finally:
            _purge_disposable(super_headers, info["id"])


# ================================================================
# REGRESSION — pre-existing admin endpoints still work
# ================================================================
class TestAdminRegression:
    def test_dashboard(self, super_headers):
        r = requests.get(f"{API}/admin/dashboard", headers=super_headers, timeout=30)
        assert r.status_code == 200
        assert "active_clinics" in r.json()

    def test_list_clinics(self, super_headers):
        r = requests.get(f"{API}/admin/clinics", headers=super_headers, timeout=30)
        assert r.status_code == 200 and isinstance(r.json(), list)

    def test_list_users(self, super_headers):
        r = requests.get(f"{API}/admin/users", headers=super_headers, timeout=30)
        assert r.status_code == 200 and isinstance(r.json(), list)


# ================================================================
# INSURANCE — POS + AR + providers
# ================================================================
def _first_patient(clinic_headers):
    r = requests.get(f"{API}/clinic/patients?limit=1", headers=clinic_headers, timeout=30)
    if r.status_code == 200:
        js = r.json()
        # possible shapes
        items = js.get("patients") or js.get("items") or (js if isinstance(js, list) else [])
        if items:
            return items[0]["id"]
    # fallback shapes
    return None


class TestInsurancePayments:
    def test_insurance_missing_name_400(self, clinic_headers):
        payload = {
            "branch_id": BRANCH_ID,
            "items": [{"description": "Consulta", "quantity": 1, "unit_price": 100, "tax_rate": 0}],
            "payments": [{"payment_method": "insurance", "amount": 100}],
        }
        r = requests.post(f"{API}/clinic/sales", json=payload, headers=clinic_headers, timeout=30)
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"
        assert "seguro" in (r.json().get("detail") or "").lower()

    def test_full_insurance_sale_creates_provider(self, clinic_headers):
        ts = int(time.time())
        ins_name = f"TEST_INS_{ts}"
        payload = {
            "branch_id": BRANCH_ID,
            "items": [{"description": "Consulta insurance", "quantity": 1, "unit_price": 100, "tax_rate": 0}],
            "payments": [{"payment_method": "insurance", "amount": 100, "insurance_name": ins_name}],
        }
        r = requests.post(f"{API}/clinic/sales", json=payload, headers=clinic_headers, timeout=30)
        assert r.status_code == 200, f"sale failed: {r.text}"
        sale_id = r.json()["id"]
        # payment persisted with insurance_name
        r = requests.get(f"{API}/clinic/sales/{sale_id}", headers=clinic_headers, timeout=30)
        assert r.status_code == 200
        pays = r.json()["payments"]
        assert any(p.get("payment_method") == "insurance" and p.get("insurance_name") == ins_name for p in pays)
        # provider now listed
        r = requests.get(f"{API}/clinic/insurance-providers?q={ins_name}",
                         headers=clinic_headers, timeout=30)
        assert r.status_code == 200
        names = [p["name"] for p in r.json()]
        assert ins_name in names, f"provider not auto-created; got {names}"

    def test_partial_insurance_creates_ar(self, clinic_headers):
        pid = _first_patient(clinic_headers)
        if not pid:
            pytest.skip("No patient available in clinic")
        ts = int(time.time())
        ins_name = f"TEST_INS_AR_{ts}"
        payload = {
            "branch_id": BRANCH_ID,
            "patient_id": pid,
            "items": [{"description": "Servicio mixto", "quantity": 1, "unit_price": 600, "tax_rate": 0}],
            "payments": [
                {"payment_method": "cash", "amount": 200},
                {"payment_method": "insurance", "amount": 300, "insurance_name": ins_name},
            ],
        }
        r = requests.post(f"{API}/clinic/sales", json=payload, headers=clinic_headers, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["amount_due"] == 100
        sale_id = r.json()["id"]
        # AR should exist with insurance_name + insurance_amount=300
        r = requests.get(f"{API}/clinic/accounts-receivable?insurance={ins_name}",
                         headers=clinic_headers, timeout=30)
        assert r.status_code == 200, r.text
        items = r.json() if isinstance(r.json(), list) else (r.json().get("items") or r.json().get("accounts") or [])
        # locate our sale's AR
        ar = [x for x in items if x.get("sale_id") == sale_id]
        assert ar, f"AR not found for sale {sale_id}, results={items}"
        assert ar[0].get("insurance_name") == ins_name
        assert float(ar[0].get("insurance_amount") or 0) == 300.0

    def test_provider_manual_create_idempotent(self, clinic_headers):
        ts = int(time.time())
        name = f"TEST_INS_MAN_{ts}"
        r = requests.post(f"{API}/clinic/insurance-providers", json={"name": name},
                          headers=clinic_headers, timeout=30)
        assert r.status_code == 200, r.text
        first_id = r.json()["id"]
        # duplicate — case-insensitive
        r2 = requests.post(f"{API}/clinic/insurance-providers", json={"name": name.lower()},
                           headers=clinic_headers, timeout=30)
        assert r2.status_code == 200
        assert r2.json()["id"] == first_id, "provider not idempotent on duplicate"

    def test_provider_empty_name_400(self, clinic_headers):
        r = requests.post(f"{API}/clinic/insurance-providers", json={"name": "  "},
                          headers=clinic_headers, timeout=30)
        assert r.status_code == 400


# ================================================================
# AR FILTERS
# ================================================================
class TestArFilters:
    def test_ar_filter_by_insurance(self, clinic_headers):
        pid = _first_patient(clinic_headers)
        if not pid:
            pytest.skip("No patient available")
        ts = int(time.time())
        ins_name = f"TEST_ARF_{ts}"
        payload = {
            "branch_id": BRANCH_ID, "patient_id": pid,
            "items": [{"description": "arf", "quantity": 1, "unit_price": 500, "tax_rate": 0}],
            "payments": [{"payment_method": "insurance", "amount": 200, "insurance_name": ins_name}],
        }
        r = requests.post(f"{API}/clinic/sales", json=payload, headers=clinic_headers, timeout=30)
        assert r.status_code == 200, r.text
        # filter by insurance (case-insensitive)
        r = requests.get(f"{API}/clinic/accounts-receivable?insurance={ins_name.lower()}",
                         headers=clinic_headers, timeout=30)
        assert r.status_code == 200, r.text
        items = r.json() if isinstance(r.json(), list) else (r.json().get("items") or r.json().get("accounts") or [])
        assert items, "no AR returned when filtering by insurance"
        for it in items:
            assert (it.get("insurance_name") or "").lower() == ins_name.lower()

    def test_ar_filter_by_date_range(self, clinic_headers):
        today = datetime.now(timezone.utc).date().isoformat()
        tomorrow = (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()
        r = requests.get(
            f"{API}/clinic/accounts-receivable?date_from={today}&date_to={tomorrow}",
            headers=clinic_headers, timeout=30)
        assert r.status_code == 200, r.text
        # narrow date in far past should return empty
        r = requests.get(
            f"{API}/clinic/accounts-receivable?date_from=2000-01-01&date_to=2000-01-02",
            headers=clinic_headers, timeout=30)
        assert r.status_code == 200
        items = r.json() if isinstance(r.json(), list) else (r.json().get("items") or r.json().get("accounts") or [])
        assert items == [] or all(
            (it.get("created_at") or "")[:10] <= "2000-01-02" for it in items
        )


# ================================================================
# REGRESSION — POS non-insurance payments still work
# ================================================================
class TestPosRegression:
    def test_cash_sale(self, clinic_headers):
        payload = {
            "branch_id": BRANCH_ID,
            "items": [{"description": "cash test", "quantity": 1, "unit_price": 50, "tax_rate": 0}],
            "payments": [{"payment_method": "cash", "amount": 50}],
        }
        r = requests.post(f"{API}/clinic/sales", json=payload, headers=clinic_headers, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["payment_status"] == "paid"

    def test_card_sale(self, clinic_headers):
        payload = {
            "branch_id": BRANCH_ID,
            "items": [{"description": "card test", "quantity": 1, "unit_price": 30, "tax_rate": 0}],
            "payments": [{"payment_method": "credit_card", "amount": 30}],
        }
        r = requests.post(f"{API}/clinic/sales", json=payload, headers=clinic_headers, timeout=30)
        assert r.status_code == 200, r.text

    def test_transfer_sale(self, clinic_headers):
        payload = {
            "branch_id": BRANCH_ID,
            "items": [{"description": "xfer test", "quantity": 1, "unit_price": 20, "tax_rate": 0}],
            "payments": [{"payment_method": "transfer", "amount": 20}],
        }
        r = requests.post(f"{API}/clinic/sales", json=payload, headers=clinic_headers, timeout=30)
        assert r.status_code == 200, r.text


# ================================================================
# USER GUIDE PDF regression
# ================================================================
class TestUserGuidePDF:
    def test_pdf_generates(self, clinic_headers):
        r = requests.get(f"{API}/clinic/user-guide/pdf", headers=clinic_headers, timeout=60)
        assert r.status_code == 200, r.text
        ct = r.headers.get("content-type", "")
        assert "pdf" in ct.lower() or r.content[:4] == b"%PDF", f"not a pdf: ct={ct}"
        assert len(r.content) > 1000
