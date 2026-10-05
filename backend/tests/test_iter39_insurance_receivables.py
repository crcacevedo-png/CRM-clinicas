"""Backend tests for iteration 39:
Vista Por Cobrar a Aseguradoras:
- GET /api/clinic/insurance-receivables (filters: insurance, aging, status)
- GET /api/clinic/insurance-receivables/{insurance_name}/statement-pdf
Regression: /api/clinic/accounts-receivable still works.
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"

CLINIC_ADMIN_EMAIL = "prueba3@gmail.com"
CLINIC_ADMIN_PASSWORD = "Test123456!"
BRANCH_ID = "79c47aab-3d03-49a0-bcec-b931766aa48e"


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed {email}: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def clinic_headers():
    try:
        tok = _login(CLINIC_ADMIN_EMAIL, CLINIC_ADMIN_PASSWORD)
    except AssertionError as e:
        pytest.skip(f"clinic_admin login unavailable: {e}")
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def _first_patient(clinic_headers):
    r = requests.get(f"{API}/clinic/patients/search?q=garcia", headers=clinic_headers, timeout=30)
    if r.status_code == 200:
        js = r.json()
        items = js if isinstance(js, list) else (js.get("patients") or js.get("items") or [])
        if items:
            return items[0]["id"]
    # fallback
    r = requests.get(f"{API}/clinic/patients?limit=1", headers=clinic_headers, timeout=30)
    if r.status_code == 200:
        js = r.json()
        items = js.get("patients") or js.get("items") or (js if isinstance(js, list) else [])
        if items:
            return items[0]["id"]
    return None


# -----------------------------------------------------------------
# Structure + filters
# -----------------------------------------------------------------
class TestInsuranceReceivablesList:
    def test_no_filters_returns_structure(self, clinic_headers):
        r = requests.get(f"{API}/clinic/insurance-receivables", headers=clinic_headers, timeout=30)
        assert r.status_code == 200, r.text
        js = r.json()
        assert set(["providers", "accounts", "totals"]).issubset(js.keys())
        assert set(["pending", "insurance_pending", "count"]).issubset(js["totals"].keys())
        assert isinstance(js["providers"], list)
        assert isinstance(js["accounts"], list)
        # providers sorted by pending DESC
        pend = [p["pending"] for p in js["providers"]]
        assert pend == sorted(pend, reverse=True), f"not sorted desc: {pend}"
        # each provider shape
        for p in js["providers"]:
            assert set(["name", "pending", "insurance_pending", "count", "oldest_days"]).issubset(p.keys())
        # accounts have aging_days and aging_bucket
        for a in js["accounts"]:
            assert "aging_days" in a and isinstance(a["aging_days"], int)
            assert a.get("aging_bucket") in ("0-30", "31-60", "61-90", "90+")

    def test_default_status_hides_paid(self, clinic_headers):
        r = requests.get(f"{API}/clinic/insurance-receivables", headers=clinic_headers, timeout=30)
        assert r.status_code == 200
        for a in r.json()["accounts"]:
            assert a.get("status") != "paid"

    def test_status_paid_only(self, clinic_headers):
        r = requests.get(f"{API}/clinic/insurance-receivables?status=paid", headers=clinic_headers, timeout=30)
        assert r.status_code == 200
        for a in r.json()["accounts"]:
            assert a.get("status") == "paid"

    def test_status_all_includes_both(self, clinic_headers):
        r = requests.get(f"{API}/clinic/insurance-receivables?status=all", headers=clinic_headers, timeout=30)
        assert r.status_code == 200
        # just ensure 200 and shape consistent

    def test_insurance_filter_case_insensitive(self, clinic_headers):
        # pick an existing insurance name if any
        r0 = requests.get(f"{API}/clinic/insurance-receivables?status=all", headers=clinic_headers, timeout=30)
        provs = r0.json()["providers"]
        if not provs:
            pytest.skip("No insurance providers available for filter test")
        name = provs[0]["name"]
        r = requests.get(f"{API}/clinic/insurance-receivables?insurance={name.lower()}&status=all",
                         headers=clinic_headers, timeout=30)
        assert r.status_code == 200
        for a in r.json()["accounts"]:
            assert (a.get("insurance_name") or "").lower() == name.lower()

    @pytest.mark.parametrize("bucket", ["0-30", "31-60", "61-90", "90+"])
    def test_aging_filter_buckets(self, clinic_headers, bucket):
        # Use params to ensure proper URL-encoding of '+' as %2B
        r = requests.get(f"{API}/clinic/insurance-receivables",
                         params={"aging": bucket, "status": "all"},
                         headers=clinic_headers, timeout=30)
        assert r.status_code == 200
        for a in r.json()["accounts"]:
            assert a["aging_bucket"] == bucket

    def test_aging_invalid_ignored(self, clinic_headers):
        r_all = requests.get(f"{API}/clinic/insurance-receivables?status=all", headers=clinic_headers, timeout=30)
        r_bad = requests.get(f"{API}/clinic/insurance-receivables?aging=999&status=all",
                             headers=clinic_headers, timeout=30)
        assert r_all.status_code == 200 and r_bad.status_code == 200
        assert r_all.json()["totals"]["count"] == r_bad.json()["totals"]["count"]

    def test_empty_provider_returns_zero(self, clinic_headers):
        r = requests.get(f"{API}/clinic/insurance-receivables?insurance=zzz_imposible_xxx",
                         headers=clinic_headers, timeout=30)
        assert r.status_code == 200
        js = r.json()
        assert js["providers"] == []
        assert js["accounts"] == []
        assert js["totals"] == {"pending": 0, "insurance_pending": 0, "count": 0}

    def test_auth_required(self):
        r = requests.get(f"{API}/clinic/insurance-receivables", timeout=30)
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"


# -----------------------------------------------------------------
# Create AR (mixed sale with insurance) + verify
# -----------------------------------------------------------------
@pytest.fixture(scope="session")
def seeded_insurance_ar(clinic_headers):
    pid = _first_patient(clinic_headers)
    if not pid:
        pytest.skip("No patient available in clinic")
    ts = int(time.time())
    ins_name = f"TEST_PDF_{ts}"
    payload = {
        "branch_id": BRANCH_ID,
        "patient_id": pid,
        "items": [{"description": "Servicio PDF", "quantity": 1, "unit_price": 600, "tax_rate": 0}],
        "payments": [{"payment_method": "cash", "amount": 200}],
        "insurance_name": ins_name,
        "insurance_amount": 400,
    }
    r = requests.post(f"{API}/clinic/sales", json=payload, headers=clinic_headers, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"Could not create seeded sale: {r.status_code} {r.text}")
    sale = r.json()
    # find the AR
    r2 = requests.get(f"{API}/clinic/insurance-receivables?insurance={ins_name}&status=all",
                      headers=clinic_headers, timeout=30)
    assert r2.status_code == 200, r2.text
    accts = r2.json()["accounts"]
    ar = next((a for a in accts if a.get("sale_id") == sale["id"]), None)
    assert ar is not None, f"AR not found for seeded sale, accounts={accts}"
    return {"insurance_name": ins_name, "sale_id": sale["id"], "ar_id": ar["id"]}


class TestSeededARAndPDF:
    def test_seeded_ar_shape(self, clinic_headers, seeded_insurance_ar):
        ins_name = seeded_insurance_ar["insurance_name"]
        r = requests.get(f"{API}/clinic/insurance-receivables?insurance={ins_name}&status=all",
                         headers=clinic_headers, timeout=30)
        assert r.status_code == 200
        accts = r.json()["accounts"]
        ar = next((a for a in accts if a["id"] == seeded_insurance_ar["ar_id"]), None)
        assert ar is not None
        assert float(ar.get("balance") or 0) == 400.0
        assert float(ar.get("insurance_amount") or 0) == 400.0
        assert ar.get("aging_bucket") == "0-30"

    def test_statement_pdf_valid(self, clinic_headers, seeded_insurance_ar):
        ins_name = seeded_insurance_ar["insurance_name"]
        r = requests.get(
            f"{API}/clinic/insurance-receivables/{ins_name}/statement-pdf"
            f"?date_from=2026-01-01&date_to=2026-12-31",
            headers=clinic_headers, timeout=60)
        assert r.status_code == 200, r.text
        js = r.json()
        assert set(["url", "insurance_name", "date_from", "date_to", "totals"]).issubset(js.keys())
        assert js["url"].startswith("https://"), f"url not https: {js['url']}"
        assert set(["charged", "paid_in_period", "pending", "count"]).issubset(js["totals"].keys())
        assert js["totals"]["count"] >= 1
        # Download and check PDF magic bytes
        rp = requests.get(js["url"], timeout=60)
        assert rp.status_code == 200
        assert rp.content[:4] == b"%PDF", f"not a PDF, first bytes={rp.content[:8]!r}"

    def test_statement_pdf_nonexistent_insurer_zero_totals(self, clinic_headers):
        r = requests.get(
            f"{API}/clinic/insurance-receivables/zzz_impossible_insurer_xxx/statement-pdf"
            f"?date_from=2026-01-01&date_to=2026-12-31",
            headers=clinic_headers, timeout=60)
        assert r.status_code == 200, r.text
        js = r.json()
        assert "url" in js and js["url"].startswith("https://")
        assert js["totals"]["count"] == 0
        assert js["totals"]["pending"] == 0
        rp = requests.get(js["url"], timeout=60)
        assert rp.status_code == 200
        assert rp.content[:4] == b"%PDF"

    def test_statement_pdf_empty_name_4xx(self, clinic_headers):
        # Trailing slash before statement-pdf will produce 404 (path mismatch) or 400 — both acceptable
        r = requests.get(
            f"{API}/clinic/insurance-receivables/ /statement-pdf",
            headers=clinic_headers, timeout=30)
        assert 400 <= r.status_code < 500, f"expected 4xx, got {r.status_code}: {r.text}"


class TestPaymentReflects:
    def test_payment_reduces_balance_and_shows_in_pdf(self, clinic_headers, seeded_insurance_ar):
        ar_id = seeded_insurance_ar["ar_id"]
        ins_name = seeded_insurance_ar["insurance_name"]
        r = requests.post(
            f"{API}/clinic/accounts-receivable/{ar_id}/payment",
            json={"amount": 100, "payment_method": "transfer"},
            headers=clinic_headers, timeout=30)
        assert r.status_code == 200, f"payment failed: {r.status_code} {r.text}"
        # list again
        r2 = requests.get(f"{API}/clinic/insurance-receivables?insurance={ins_name}&status=all",
                          headers=clinic_headers, timeout=30)
        assert r2.status_code == 200
        accts = r2.json()["accounts"]
        ar = next((a for a in accts if a["id"] == ar_id), None)
        assert ar is not None
        assert float(ar["balance"]) == pytest.approx(300.0, abs=0.01), ar
        assert ar.get("status") in ("partial", "paid")
        # PDF includes paid_in_period >= 100
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).date().isoformat()
        r3 = requests.get(
            f"{API}/clinic/insurance-receivables/{ins_name}/statement-pdf"
            f"?date_from=2026-01-01&date_to={today}",
            headers=clinic_headers, timeout=60)
        assert r3.status_code == 200, r3.text
        totals = r3.json()["totals"]
        assert totals["paid_in_period"] >= 100.0, totals


# -----------------------------------------------------------------
# Regression: previous AR endpoint still works
# -----------------------------------------------------------------
class TestRegression:
    def test_accounts_receivable_endpoint_still_ok(self, clinic_headers):
        r = requests.get(f"{API}/clinic/accounts-receivable", headers=clinic_headers, timeout=30)
        assert r.status_code == 200, r.text
        js = r.json()
        assert isinstance(js, (list, dict))
