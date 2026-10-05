"""Backend regression tests for the Insurance-as-AR redesign (iter 38).

Covers:
  - Validation: payment_method='insurance' now rejected (400)
  - Validation: insurance_amount without insurance_name rejected (400)
  - Validation: insurance_amount > total rejected (400)
  - Validation: insurance_amount < 0 rejected (400)
  - New flow: sale with mixed cash + insurance creates ONE cash payment + ONE AR
  - Mixed: cash + insurance leaving patient_due produces combined AR balance
  - Regression: full cash sale still works
  - Regression: partial sale without insurance still creates AR without insurance_name
  - Insurance report: pending→collected after AR payment is applied
  - Migration endpoint: super_admin can run; second call is idempotent
  - Migration does not touch non-insurance payments (verified by payment table shape)
  - Sale detail: no payment has method='insurance'; AR shows insurance_name/amount
  - Insurance providers listing returns the upserted provider
  - User guide PDF still generates for clinic_admin
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")

# --- Credentials from /app/memory/test_credentials.md ---
SUPER_ADMIN = {"email": "info@cortexiagt.com", "password": "Armagedon1980$"}
CLINIC_ADMIN = {"email": "prueba3@gmail.com", "password": "Test123456!"}
CLINIC_ID = "c0321ed8-97da-47a1-b601-3b94bffabdd7"
MAIN_BRANCH = "79c47aab-3d03-49a0-bcec-b931766aa48e"

TS = int(time.time())


# ============== Fixtures ==============
@pytest.fixture(scope="session")
def admin_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json=CLINIC_ADMIN, timeout=30)
    assert r.status_code == 200, f"Clinic admin login failed: {r.status_code} {r.text}"
    token = r.json().get("access_token") or r.json().get("token")
    assert token, f"No token in response: {r.json()}"
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="session")
def super_admin_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json=SUPER_ADMIN, timeout=30)
    assert r.status_code == 200, f"Super admin login failed: {r.status_code} {r.text}"
    token = r.json().get("access_token") or r.json().get("token")
    assert token
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="session")
def patient_id(admin_session):
    """Pick first existing patient (search for 'a' which should hit many)."""
    r = admin_session.get(f"{BASE_URL}/api/clinic/patients/search?q=a", timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    patients = data if isinstance(data, list) else data.get("patients", [])
    if not patients:
        # Create one
        p = admin_session.post(f"{BASE_URL}/api/clinic/patients", json={
            "first_name": "TEST_INS",
            "last_name": f"Patient_{TS}",
        }, timeout=20)
        assert p.status_code == 200, p.text
        return p.json()["id"]
    return patients[0]["id"]


@pytest.fixture(scope="session")
def cash_session_id(admin_session):
    """Ensure there's an open cash session in MAIN branch; open one if needed."""
    r = admin_session.get(f"{BASE_URL}/api/clinic/sales/cash-session/current", timeout=20)
    assert r.status_code == 200, r.text
    sess = r.json().get("session")
    if sess and sess.get("status") == "open":
        # Verify branch matches MAIN; otherwise open a new one
        if sess.get("branch_id") == MAIN_BRANCH:
            return sess["id"]
    # Open: need a register in MAIN
    regs = admin_session.get(f"{BASE_URL}/api/clinic/sales/cash-registers?branch_id={MAIN_BRANCH}", timeout=20).json()
    if not regs:
        pytest.skip("No cash register in MAIN branch to open session")
    reg_id = regs[0]["id"]
    o = admin_session.post(f"{BASE_URL}/api/clinic/sales/cash-session/open", json={
        "cash_register_id": reg_id, "opening_amount": 0,
    }, timeout=20)
    if o.status_code != 200:
        # Maybe already open with different branch -> skip
        pytest.skip(f"Could not open cash session: {o.text}")
    return o.json()["id"]


def _base_sale_payload(patient_id, cash_session_id, total_item_price=600.0, items=None):
    return {
        "branch_id": MAIN_BRANCH,
        "cash_session_id": cash_session_id,
        "patient_id": patient_id,
        "customer_name": "TEST_INS Customer",
        "items": items or [{
            "description": "TEST_INS Servicio",
            "quantity": 1,
            "unit_price": total_item_price,
            "discount_pct": 0,
            "tax_rate": 0,
        }],
        "payments": [],
    }


# ============== Validation tests ==============
class TestValidation:
    """Validation rules for the new insurance contract."""

    def test_insurance_as_payment_method_rejected(self, admin_session, patient_id, cash_session_id):
        """payment_method='insurance' must return 400."""
        payload = _base_sale_payload(patient_id, cash_session_id)
        payload["payments"] = [{"payment_method": "insurance", "amount": 200}]
        r = admin_session.post(f"{BASE_URL}/api/clinic/sales", json=payload, timeout=20)
        assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
        detail = (r.json().get("detail") or "").lower()
        assert "seguro" in detail and ("método" in detail or "metodo" in detail or "method" in detail), \
            f"Error should mention seguro/método: {detail}"

    def test_insurance_amount_without_name_rejected(self, admin_session, patient_id, cash_session_id):
        payload = _base_sale_payload(patient_id, cash_session_id)
        payload["insurance_amount"] = 100
        # no insurance_name
        r = admin_session.post(f"{BASE_URL}/api/clinic/sales", json=payload, timeout=20)
        assert r.status_code == 400, f"Got {r.status_code}: {r.text}"
        detail = r.json().get("detail") or ""
        assert "aseguradora" in detail.lower(), detail

    def test_insurance_amount_greater_than_total_rejected(self, admin_session, patient_id, cash_session_id):
        # total = 600; insurance_amount = 1000
        payload = _base_sale_payload(patient_id, cash_session_id, total_item_price=600)
        payload["insurance_name"] = f"TEST_INS_VAL_{TS}"
        payload["insurance_amount"] = 1000
        r = admin_session.post(f"{BASE_URL}/api/clinic/sales", json=payload, timeout=20)
        assert r.status_code == 400, f"Got {r.status_code}: {r.text}"
        assert "mayor al total" in (r.json().get("detail") or "").lower()

    def test_insurance_amount_negative_rejected(self, admin_session, patient_id, cash_session_id):
        payload = _base_sale_payload(patient_id, cash_session_id)
        payload["insurance_name"] = f"TEST_INS_NEG_{TS}"
        payload["insurance_amount"] = -50
        r = admin_session.post(f"{BASE_URL}/api/clinic/sales", json=payload, timeout=20)
        assert r.status_code == 400
        assert "negativo" in (r.json().get("detail") or "").lower()


# ============== New flow tests ==============
class TestNewInsuranceFlow:
    """End-to-end: new insurance-as-AR flow."""

    insurance_name = f"TEST_INS_NEW_{TS}"
    sale_id = None
    ar_id = None

    def test_create_sale_with_cash_and_insurance(self, admin_session, patient_id, cash_session_id):
        """Q600 item + Q200 cash + Q400 insurance → amount_paid=200, amount_due=400, status=partial."""
        payload = _base_sale_payload(patient_id, cash_session_id, total_item_price=600)
        payload["insurance_name"] = TestNewInsuranceFlow.insurance_name
        payload["insurance_amount"] = 400
        payload["payments"] = [{"payment_method": "cash", "amount": 200}]
        r = admin_session.post(f"{BASE_URL}/api/clinic/sales", json=payload, timeout=30)
        assert r.status_code == 200, f"Create failed: {r.status_code} {r.text}"
        body = r.json()
        TestNewInsuranceFlow.sale_id = body["id"]
        assert body["total"] == 600.0
        assert body["amount_due"] == 400.0
        assert body["payment_status"] == "partial"

    def test_sale_detail_shows_only_cash_payment(self, admin_session):
        assert TestNewInsuranceFlow.sale_id, "Prior test must pass"
        r = admin_session.get(f"{BASE_URL}/api/clinic/sales/{TestNewInsuranceFlow.sale_id}", timeout=20)
        assert r.status_code == 200, r.text
        sale = r.json()
        assert sale["amount_paid"] == 200.0
        assert sale["amount_due"] == 400.0
        pays = sale.get("payments") or []
        assert len(pays) == 1, f"Expected 1 payment, got {len(pays)}: {pays}"
        assert pays[0]["payment_method"] == "cash"
        assert pays[0]["amount"] == 200.0
        # No payment with insurance method
        assert all(p.get("payment_method") != "insurance" for p in pays)

    def test_ar_was_created_for_insurance(self, admin_session, patient_id):
        """Verify an AR was created with the right insurance_name/amount and notes."""
        assert TestNewInsuranceFlow.sale_id
        r = admin_session.get(
            f"{BASE_URL}/api/clinic/accounts-receivable?patient_id={patient_id}&page=1&limit=100",
            timeout=20,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        ars = data.get("accounts") or data.get("accounts_receivable") or data.get("items") or (data if isinstance(data, list) else [])
        matching = [a for a in ars if a.get("sale_id") == TestNewInsuranceFlow.sale_id]
        assert len(matching) == 1, f"Expected 1 AR for sale, found {len(matching)}: {matching}"
        ar = matching[0]
        TestNewInsuranceFlow.ar_id = ar["id"]
        assert ar.get("insurance_name") == TestNewInsuranceFlow.insurance_name
        assert float(ar.get("insurance_amount") or 0) == 400.0
        assert float(ar.get("balance") or 0) == 400.0
        notes = (ar.get("notes") or "").lower()
        assert "cargo" in notes or TestNewInsuranceFlow.insurance_name.lower() in notes, f"Notes: {ar.get('notes')}"

    def test_insurance_provider_was_upserted(self, admin_session):
        r = admin_session.get(
            f"{BASE_URL}/api/clinic/insurance-providers?q={TestNewInsuranceFlow.insurance_name}",
            timeout=20,
        )
        assert r.status_code == 200
        providers = r.json()
        names = [p["name"] for p in providers]
        assert TestNewInsuranceFlow.insurance_name in names, f"Provider not upserted. Got: {names}"


class TestMixedPatientInsurance:
    """Total 600; cash 100; insurance 400; patient_due=100; AR balance=500."""

    insurance_name = f"TEST_INS_MIX_{TS}"

    def test_mixed_sale_builds_combined_ar(self, admin_session, patient_id, cash_session_id):
        payload = _base_sale_payload(patient_id, cash_session_id, total_item_price=600)
        payload["insurance_name"] = TestMixedPatientInsurance.insurance_name
        payload["insurance_amount"] = 400
        payload["payments"] = [{"payment_method": "cash", "amount": 100}]
        r = admin_session.post(f"{BASE_URL}/api/clinic/sales", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["amount_due"] == 500.0  # 100 patient + 400 insurance
        assert body["payment_status"] == "partial"
        sale_id = body["id"]
        # Verify AR
        ars = admin_session.get(
            f"{BASE_URL}/api/clinic/accounts-receivable?patient_id={patient_id}&page=1&limit=100",
            timeout=20,
        ).json()
        ars = ars.get("accounts") or ars.get("items") or (ars if isinstance(ars, list) else [])
        matching = [a for a in ars if a.get("sale_id") == sale_id]
        assert len(matching) == 1
        ar = matching[0]
        assert float(ar["balance"]) == 500.0
        assert float(ar["insurance_amount"]) == 400.0
        notes = ar.get("notes") or ""
        assert "400" in notes and "100" in notes, f"Notes should mention both amounts: {notes}"
        assert "paciente" in notes.lower()


# ============== Regression tests ==============
class TestPOSRegression:

    def test_full_cash_sale_no_insurance(self, admin_session, patient_id, cash_session_id):
        payload = _base_sale_payload(patient_id, cash_session_id, total_item_price=500)
        payload["payments"] = [{"payment_method": "cash", "amount": 500}]
        r = admin_session.post(f"{BASE_URL}/api/clinic/sales", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total"] == 500.0
        assert body["amount_due"] == 0.0
        assert body["payment_status"] == "paid"

    def test_partial_sale_without_insurance_creates_ar(self, admin_session, patient_id, cash_session_id):
        payload = _base_sale_payload(patient_id, cash_session_id, total_item_price=500)
        payload["payments"] = [{"payment_method": "cash", "amount": 300}]
        r = admin_session.post(f"{BASE_URL}/api/clinic/sales", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["amount_due"] == 200.0
        assert body["payment_status"] == "partial"
        sale_id = body["id"]
        # AR check
        ars = admin_session.get(
            f"{BASE_URL}/api/clinic/accounts-receivable?patient_id={patient_id}&page=1&limit=100",
            timeout=20,
        ).json()
        ars = ars.get("accounts") or ars.get("items") or (ars if isinstance(ars, list) else [])
        matching = [a for a in ars if a.get("sale_id") == sale_id]
        assert len(matching) == 1
        ar = matching[0]
        assert float(ar["balance"]) == 200.0
        assert ar.get("insurance_name") in (None, "")

    def test_user_guide_pdf(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/clinic/user-guide/pdf", timeout=30)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf") or r.content[:4] == b"%PDF"


# ============== Insurance report ==============
class TestInsuranceReport:
    """Report should count collected only from AR payments; pending from AR balance."""

    insurance_name = f"TEST_INS_RPT_{TS}"
    sale_id = None
    ar_id = None

    def test_setup_create_sale(self, admin_session, patient_id, cash_session_id):
        payload = _base_sale_payload(patient_id, cash_session_id, total_item_price=600)
        payload["insurance_name"] = TestInsuranceReport.insurance_name
        payload["insurance_amount"] = 400
        payload["payments"] = [{"payment_method": "cash", "amount": 200}]
        r = admin_session.post(f"{BASE_URL}/api/clinic/sales", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        TestInsuranceReport.sale_id = r.json()["id"]
        # Fetch AR
        ars = admin_session.get(
            f"{BASE_URL}/api/clinic/accounts-receivable?patient_id={patient_id}&page=1&limit=100",
            timeout=20,
        ).json()
        ars = ars.get("accounts") or ars.get("items") or (ars if isinstance(ars, list) else [])
        matching = [a for a in ars if a.get("sale_id") == TestInsuranceReport.sale_id]
        assert matching
        TestInsuranceReport.ar_id = matching[0]["id"]

    def test_report_shows_pending_before_payment(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/clinic/reports/insurance?period=year", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        summary = data.get("summary") or []
        prov = next((p for p in summary if p["name"] == TestInsuranceReport.insurance_name), None)
        assert prov is not None, f"Provider {TestInsuranceReport.insurance_name} not in summary"
        assert prov["pending"] == 400.0
        assert prov["collected"] == 0.0

    def test_register_insurer_payment_and_report_updates(self, admin_session):
        assert TestInsuranceReport.ar_id
        r = admin_session.post(
            f"{BASE_URL}/api/clinic/accounts-receivable/{TestInsuranceReport.ar_id}/payment",
            json={"amount": 400, "payment_method": "transfer", "notes": "TEST_INS insurer deposit"},
            timeout=20,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "paid"
        # Now report should show collected=400 pending=0
        rpt = admin_session.get(f"{BASE_URL}/api/clinic/reports/insurance?period=year", timeout=30).json()
        prov = next((p for p in rpt.get("summary", []) if p["name"] == TestInsuranceReport.insurance_name), None)
        assert prov is not None
        assert prov["collected"] == 400.0, f"Collected should be 400 after insurer payment: {prov}"
        assert prov["pending"] == 0.0, f"Pending should be 0 after full insurer payment: {prov}"


# ============== Migration tests ==============
class TestMigration:
    """Idempotent insurance payments migration."""

    first_counters = None

    def test_run_migration_first_time(self, super_admin_session):
        r = super_admin_session.post(
            f"{BASE_URL}/api/admin/migrations/insurance-payments-migration",
            timeout=120,
        )
        assert r.status_code == 200, f"Migration failed: {r.status_code} {r.text}"
        body = r.json()
        assert body.get("ok") is True
        counters = body.get("counters") or {}
        TestMigration.first_counters = counters
        # All expected keys present
        for key in ("sales_touched", "insurance_payments_deleted", "ars_created", "ars_updated"):
            assert key in counters, f"Missing counter {key}: {counters}"

    def test_run_migration_idempotent(self, super_admin_session):
        """Second call should find no legacy rows → sales_touched=0."""
        r = super_admin_session.post(
            f"{BASE_URL}/api/admin/migrations/insurance-payments-migration",
            timeout=120,
        )
        assert r.status_code == 200, r.text
        counters = r.json().get("counters") or {}
        assert counters.get("sales_touched", -1) == 0, f"Second run should be a no-op: {counters}"
        assert counters.get("insurance_payments_deleted", -1) == 0

    def test_non_insurance_payments_untouched(self, admin_session, patient_id, cash_session_id, super_admin_session):
        """Create a cash-only sale, run migration, verify payment still exists untouched."""
        payload = _base_sale_payload(patient_id, cash_session_id, total_item_price=250)
        payload["payments"] = [{"payment_method": "cash", "amount": 250}]
        r = admin_session.post(f"{BASE_URL}/api/clinic/sales", json=payload, timeout=20)
        assert r.status_code == 200
        sid = r.json()["id"]
        # Run migration
        super_admin_session.post(f"{BASE_URL}/api/admin/migrations/insurance-payments-migration", timeout=120)
        # Verify payment still cash
        sale = admin_session.get(f"{BASE_URL}/api/clinic/sales/{sid}", timeout=20).json()
        pays = sale.get("payments") or []
        assert len(pays) == 1
        assert pays[0]["payment_method"] == "cash"
        assert pays[0]["amount"] == 250.0
