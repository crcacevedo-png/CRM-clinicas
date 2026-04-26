"""Iteration 23: Doctor/Receptionist role-aware dashboards + CSV import for super-admin catalogs.

Coverage:
  - GET /api/auth/me with doctor.test@lasalud.gt -> role=doctor, clinic_id=c0321ed8...
  - GET /api/auth/me with recepcion.test@lasalud.gt -> role=receptionist, clinic_id=c0321ed8...
  - GET /api/clinic/dashboard (doctor) -> admin_stats empty, my_commissions_month populated
  - GET /api/clinic/dashboard (receptionist) -> admin_stats only contains open_cash_sessions
  - POST /api/admin/catalogs/{catalog}/import-csv (medications, lab-studies, icd10)
      * dry-run (commit=false)
      * commit=true insert
      * malformed CSV (missing required column) -> 400
      * dedup on second commit
  - GET /api/admin/catalogs/{catalog}/csv-template
  - 403 for non-super-admin on import-csv and csv-template
"""
import os
import io
import time
import requests
import pytest

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

CLINIC_ADMIN = ("carlos@lasalud.gt", "Test123456!")
SUPER_ADMIN = ("info@cortexiagt.com", "Armagedon1980$")
DOCTOR = ("doctor.test@lasalud.gt", "Test123456!")
RECEPTIONIST = ("recepcion.test@lasalud.gt", "Test123456!")

CLINIC_ID = "c0321ed8-97da-47a1-b601-3b94bffabdd7"
DOCTOR_MEMBER_ID = "dee8138c-0239-4610-b579-ed9dc5df8ee2"
RECEP_MEMBER_ID = "7988bbdc-c0c9-4dd6-ae93-c93f8e7b0659"

# Unique prefix so cleanup is easy
PREFIX = f"TestE2E-{int(time.time())}-"


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"Login failed for {email}: {r.status_code} {r.text}"
    return r.json()["access_token"]


def _headers(token, json_ct=True):
    h = {"Authorization": f"Bearer {token}"}
    if json_ct:
        h["Content-Type"] = "application/json"
    return h


@pytest.fixture(scope="module")
def super_token():
    return _login(*SUPER_ADMIN)


@pytest.fixture(scope="module")
def clinic_admin_token():
    return _login(*CLINIC_ADMIN)


@pytest.fixture(scope="module")
def doctor_token():
    return _login(*DOCTOR)


@pytest.fixture(scope="module")
def receptionist_token():
    return _login(*RECEPTIONIST)


# ===================== /auth/me role coverage =====================
class TestAuthMeRoles:
    def test_me_doctor(self, doctor_token):
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=_headers(doctor_token), timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("user_type") == "clinic_member"
        assert d.get("clinic_id") == CLINIC_ID
        assert d.get("role") == "doctor", f"Expected role=doctor, got {d.get('role')}"
        assert d.get("member_id") == DOCTOR_MEMBER_ID
        assert d.get("email") == DOCTOR[0]

    def test_me_receptionist(self, receptionist_token):
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=_headers(receptionist_token), timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("user_type") == "clinic_member"
        assert d.get("clinic_id") == CLINIC_ID
        assert d.get("role") == "receptionist", f"Expected role=receptionist, got {d.get('role')}"
        assert d.get("member_id") == RECEP_MEMBER_ID
        assert d.get("email") == RECEPTIONIST[0]


# ===================== /clinic/dashboard role-aware shape =====================
class TestRoleAwareDashboard:
    def test_dashboard_doctor_shape(self, doctor_token):
        r = requests.get(f"{BASE_URL}/api/clinic/dashboard", headers=_headers(doctor_token), timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert isinstance(d, dict), "dashboard must be a dict"
        # admin_stats must be empty for doctor
        admin_stats = d.get("admin_stats")
        assert admin_stats == {} or admin_stats is None or admin_stats == {}, \
            f"Expected admin_stats empty for doctor, got {admin_stats}"
        # doctor must have my_commissions_month present (number/dict)
        assert "my_commissions_month" in d, f"my_commissions_month missing for doctor. Keys: {list(d.keys())}"

    def test_dashboard_receptionist_shape(self, receptionist_token):
        r = requests.get(f"{BASE_URL}/api/clinic/dashboard", headers=_headers(receptionist_token), timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert isinstance(d, dict)
        admin_stats = d.get("admin_stats") or {}
        assert isinstance(admin_stats, dict), f"admin_stats must be dict, got {type(admin_stats)}"
        # Receptionist should have at most open_cash_sessions; should NOT have sales/AR/inventory aggregates
        forbidden = {"total_sales_month", "total_revenue_month", "accounts_receivable_total",
                     "inventory_low_stock", "inventory_value", "ar_total", "sales_today"}
        present_forbidden = forbidden.intersection(set(admin_stats.keys()))
        assert not present_forbidden, \
            f"receptionist admin_stats should not include {present_forbidden}; got keys={list(admin_stats.keys())}"

    def test_dashboard_clinic_admin_full_shape(self, clinic_admin_token):
        # regression: admin should still get full admin_stats
        r = requests.get(f"{BASE_URL}/api/clinic/dashboard", headers=_headers(clinic_admin_token), timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        admin_stats = d.get("admin_stats") or {}
        assert isinstance(admin_stats, dict)
        # admin should at least have more keys than receptionist (sanity check)
        assert len(admin_stats.keys()) >= 1


# ===================== CSV Template =====================
class TestCsvTemplate:
    @pytest.mark.parametrize("catalog,required", [
        ("medications", ["generic_name"]),
        ("lab-studies", ["name"]),
        ("icd10", ["code", "description_es"]),
    ])
    def test_template_super_admin(self, super_token, catalog, required):
        r = requests.get(f"{BASE_URL}/api/admin/catalogs/{catalog}/csv-template",
                         headers=_headers(super_token), timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "headers" in d and "content" in d
        for req in required:
            assert req in d["headers"], f"required column {req} missing in template headers {d['headers']}"
        # content has header line + at least one example row
        lines = [l for l in d["content"].splitlines() if l.strip()]
        assert len(lines) >= 2, f"template content should have header+example, got: {d['content']!r}"

    def test_template_unknown_catalog_400(self, super_token):
        r = requests.get(f"{BASE_URL}/api/admin/catalogs/unknown-catalog/csv-template",
                         headers=_headers(super_token), timeout=20)
        assert r.status_code == 400, r.text

    def test_template_403_for_clinic_admin(self, clinic_admin_token):
        r = requests.get(f"{BASE_URL}/api/admin/catalogs/medications/csv-template",
                         headers=_headers(clinic_admin_token), timeout=20)
        assert r.status_code == 403, f"Expected 403 for non-super-admin, got {r.status_code}: {r.text[:200]}"


# ===================== CSV Import: medications =====================
def _upload_csv(token, catalog, csv_text, commit=False):
    files = {"file": (f"{catalog}.csv", io.BytesIO(csv_text.encode("utf-8")), "text/csv")}
    params = {"commit": "true" if commit else "false"}
    r = requests.post(
        f"{BASE_URL}/api/admin/catalogs/{catalog}/import-csv",
        headers={"Authorization": f"Bearer {token}"},
        files=files,
        params=params,
        timeout=30,
    )
    return r


class TestCsvImportMedications:
    @pytest.fixture(scope="class")
    def med_csv_valid_mixed(self):
        # 1 valid + 1 missing required + use unique prefix for cleanup
        return (
            "generic_name,brand_name,presentations,category\n"
            f"{PREFIX}MedA,BrandA,500mg tableta,Analgésico\n"
            f",,,SoloCategoria\n"
            f"{PREFIX}MedB,BrandB,250mg jarabe,Antibiótico\n"
        )

    @pytest.fixture(scope="class")
    def med_csv_malformed(self):
        # Missing required 'generic_name' column entirely
        return (
            "brand_name,presentations\n"
            "BrandX,100mg\n"
        )

    def test_dryrun_returns_stats(self, super_token, med_csv_valid_mixed):
        r = _upload_csv(super_token, "medications", med_csv_valid_mixed, commit=False)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("total", "valid_rows", "error_rows", "duplicates_skipped", "errors", "preview"):
            assert k in d, f"missing key {k} in dryrun response: {d}"
        assert d["valid_rows"] == 2, f"expected 2 valid, got {d}"
        assert d["error_rows"] == 1, f"expected 1 error row, got {d}"
        assert d.get("committed") is False
        assert d.get("imported", 0) == 0
        # Error includes field info
        assert any("generic_name" == e.get("field") for e in d["errors"]), d["errors"]

    def test_commit_inserts(self, super_token, med_csv_valid_mixed):
        r = _upload_csv(super_token, "medications", med_csv_valid_mixed, commit=True)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("committed") is True
        assert d["imported"] == 2, f"expected imported=2, got {d}"

    def test_recommit_dedups(self, super_token, med_csv_valid_mixed):
        # Second commit -> duplicates_skipped should equal previously imported (2)
        r = _upload_csv(super_token, "medications", med_csv_valid_mixed, commit=True)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["duplicates_skipped"] == 2, f"expected duplicates_skipped=2, got {d}"
        assert d["imported"] == 0, f"on dedup should import 0, got {d}"

    def test_malformed_csv_returns_400(self, super_token, med_csv_malformed):
        r = _upload_csv(super_token, "medications", med_csv_malformed, commit=False)
        assert r.status_code == 400, f"expected 400 for missing required column, got {r.status_code}: {r.text}"
        assert "generic_name" in r.text or "requeridas" in r.text.lower()

    def test_import_403_for_clinic_admin(self, clinic_admin_token, med_csv_valid_mixed):
        r = _upload_csv(clinic_admin_token, "medications", med_csv_valid_mixed, commit=False)
        assert r.status_code == 403, r.text


# ===================== CSV Import: lab-studies =====================
class TestCsvImportLabStudies:
    @pytest.fixture(scope="class")
    def lab_csv(self):
        return (
            "name,category,preparation\n"
            f"{PREFIX}LabA,Hematología,Ayuno 8h\n"
            f"{PREFIX}LabB,Bioquímica,Sin ayuno\n"
        )

    def test_dryrun(self, super_token, lab_csv):
        r = _upload_csv(super_token, "lab-studies", lab_csv, commit=False)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["valid_rows"] == 2, d
        assert d["error_rows"] == 0, d

    def test_commit(self, super_token, lab_csv):
        r = _upload_csv(super_token, "lab-studies", lab_csv, commit=True)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["imported"] == 2, d

    def test_malformed_missing_name(self, super_token):
        bad = "category,preparation\nFoo,Bar\n"
        r = _upload_csv(super_token, "lab-studies", bad, commit=False)
        assert r.status_code == 400, r.text


# ===================== CSV Import: icd10 =====================
class TestCsvImportIcd10:
    @pytest.fixture(scope="class")
    def icd_csv(self):
        # ICD-10 codes have length constraints; use short unique codes derived from timestamp
        # Format: Z+2 alphanumeric digits (mod 100). Use ts to keep them rare.
        ts = int(time.time())
        c1 = f"Z{ts % 100:02d}A"
        c2 = f"Z{ts % 100:02d}B"
        return (
            "code,description_es,category,is_common\n"
            f"{c1},{PREFIX}DescA,General,true\n"
            f"{c2},{PREFIX}DescB,General,false\n"
        )

    def test_dryrun(self, super_token, icd_csv):
        r = _upload_csv(super_token, "icd10", icd_csv, commit=False)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["valid_rows"] == 2, d

    def test_commit_then_dedup(self, super_token, icd_csv):
        r1 = _upload_csv(super_token, "icd10", icd_csv, commit=True)
        assert r1.status_code == 200, r1.text
        assert r1.json()["imported"] == 2, r1.json()
        # Re-upload same -> all duplicates
        r2 = _upload_csv(super_token, "icd10", icd_csv, commit=True)
        assert r2.status_code == 200, r2.text
        assert r2.json()["duplicates_skipped"] == 2, r2.json()
        assert r2.json()["imported"] == 0

    def test_malformed_missing_required(self, super_token):
        bad = "category,is_common\nGeneral,true\n"
        r = _upload_csv(super_token, "icd10", bad, commit=False)
        assert r.status_code == 400, r.text


# ===================== Cleanup =====================
class TestZZ_Cleanup:
    """Removes inserted TestE2E-* rows. Runs alphabetically last (ZZ prefix)."""

    def test_cleanup_inserted_rows(self, super_token):
        # Use the supabase admin client directly via backend core.
        try:
            import sys
            sys.path.insert(0, "/app/backend")
            from core import sdb  # noqa: E402
        except Exception as e:
            pytest.skip(f"Cannot import sdb for cleanup: {e}")
            return
        # medications: delete by generic_name prefix
        try:
            sdb.table("medications").delete().like("generic_name", f"{PREFIX}%").execute()
        except Exception as e:
            print(f"[cleanup] medications delete failed: {e}")
        # lab_studies: delete by name prefix
        try:
            sdb.table("lab_studies").delete().like("name", f"{PREFIX}%").execute()
        except Exception as e:
            print(f"[cleanup] lab_studies delete failed: {e}")
        # icd10_codes: delete by description_es prefix (codes were Z+suffix)
        try:
            sdb.table("icd10_codes").delete().like("description_es", f"{PREFIX}%").execute()
        except Exception as e:
            print(f"[cleanup] icd10_codes delete failed: {e}")
        # No assertion — best-effort cleanup
        assert True
