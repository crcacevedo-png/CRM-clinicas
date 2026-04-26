"""Iteration 24: Bulk patient import via CSV / XLSX.

Endpoints under test:
  - POST /api/clinic/patients-bulk/import (commit=false dry-run, commit=true)
  - GET  /api/clinic/patients-bulk/template?format=csv|xlsx

Coverage:
  - CSV dry-run with 5 rows (3 valid + 1 missing required + 1 dup)
  - CSV commit=true (imported>0)
  - Re-upload after commit -> all duplicates
  - XLSX with native Excel date cells -> ISO yyyy-mm-dd in DB
  - Gender M/F + masculino/femenino normalization
  - Dedup national_id case-insensitive + composite fallback
  - Template CSV (JSON) and XLSX (binary StreamingResponse)
  - Receptionist + Doctor can use endpoint
  - Empty file 400, .pdf 400, missing required column 400
"""
import io
import os
import time
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

CLINIC_ADMIN = ("carlos@lasalud.gt", "Test123456!")
DOCTOR = ("doctor.test@lasalud.gt", "Test123456!")
RECEPTIONIST = ("recepcion.test@lasalud.gt", "Test123456!")

# Unique prefixes so cleanup is easy and tests don't collide with other runs.
RUN_ID = f"{int(time.time())}{uuid.uuid4().hex[:4]}"
P = f"TestImport_{RUN_ID}_"            # generic prefix
NID = f"NID{RUN_ID}"                  # national_id base


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"Login failed for {email}: {r.status_code} {r.text}"
    return r.json()["access_token"]


def _h(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def admin_token():
    return _login(*CLINIC_ADMIN)


@pytest.fixture(scope="module")
def doctor_token():
    return _login(*DOCTOR)


@pytest.fixture(scope="module")
def recep_token():
    return _login(*RECEPTIONIST)


# ==================== TEMPLATE ====================

class TestTemplate:
    def test_template_csv(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/clinic/patients-bulk/template?format=csv",
                         headers=_h(admin_token), timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "headers" in data and "content" in data
        assert "first_name" in data["headers"]
        assert "last_name" in data["headers"]
        assert "first_name" in data["content"]

    def test_template_xlsx(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/clinic/patients-bulk/template?format=xlsx",
                         headers=_h(admin_token), timeout=20)
        assert r.status_code == 200, r.text
        ct = r.headers.get("content-type", "")
        assert "spreadsheetml" in ct or "officedocument" in ct, ct
        cd = r.headers.get("content-disposition", "")
        assert "plantilla_pacientes.xlsx" in cd
        # XLSX magic bytes (PK zip)
        assert r.content[:2] == b"PK"


# ==================== CSV DRY-RUN ====================

def _make_csv(rows_dicts, headers):
    """Build a CSV bytes payload."""
    out = io.StringIO()
    out.write(",".join(headers) + "\n")
    for r in rows_dicts:
        line = []
        for h in headers:
            v = str(r.get(h, ""))
            if "," in v or '"' in v:
                v = '"' + v.replace('"', '""') + '"'
            line.append(v)
        out.write(",".join(line) + "\n")
    return out.getvalue().encode("utf-8")


@pytest.fixture(scope="module")
def existing_patient(admin_token):
    """Create one patient via the bulk endpoint so we can test dedup against it."""
    headers = ["first_name", "last_name", "national_id", "phone", "gender"]
    rows = [{
        "first_name": f"{P}Existing",
        "last_name": "Dup",
        "national_id": f"{NID}_EXIST",
        "phone": "55550100",
        "gender": "M",
    }]
    csv_bytes = _make_csv(rows, headers)
    files = {"file": ("seed.csv", csv_bytes, "text/csv")}
    r = requests.post(
        f"{BASE_URL}/api/clinic/patients-bulk/import?commit=true",
        headers=_h(admin_token), files=files, timeout=30,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["imported"] == 1, body
    assert body["committed"] is True
    return rows[0]


class TestCsvDryRunAndCommit:
    def test_dry_run_5_rows(self, admin_token, existing_patient):
        """3 valid + 1 missing-required + 1 duplicate-of-existing = 5."""
        headers = ["first_name", "last_name", "national_id", "phone", "gender", "date_of_birth"]
        rows = [
            {"first_name": f"{P}A", "last_name": "Valid1", "national_id": f"{NID}_A", "phone": "55550101", "gender": "F", "date_of_birth": "1990-05-12"},
            {"first_name": f"{P}B", "last_name": "Valid2", "national_id": f"{NID}_B", "phone": "55550102", "gender": "masculino", "date_of_birth": "1985-11-30"},
            {"first_name": f"{P}C", "last_name": "Valid3", "national_id": f"{NID}_C", "phone": "55550103", "gender": "femenino", "date_of_birth": "12/04/1992"},
            {"first_name": "",       "last_name": "MissReq", "national_id": f"{NID}_X", "phone": "55550104", "gender": "M", "date_of_birth": ""},
            {"first_name": existing_patient["first_name"], "last_name": existing_patient["last_name"],
             "national_id": existing_patient["national_id"], "phone": existing_patient["phone"], "gender": "M", "date_of_birth": ""},
        ]
        csv_bytes = _make_csv(rows, headers)
        files = {"file": ("test5.csv", csv_bytes, "text/csv")}
        r = requests.post(
            f"{BASE_URL}/api/clinic/patients-bulk/import?commit=false",
            headers=_h(admin_token), files=files, timeout=30,
        )
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["total"] == 5, b
        assert b["valid_rows"] == 3, b
        assert b["error_rows"] == 1, b
        assert b["duplicates_skipped"] == 1, b
        assert b["committed"] is False
        assert b["imported"] == 0
        assert len(b["errors"]) >= 1
        e0 = b["errors"][0]
        assert "row" in e0 and "field" in e0 and "message" in e0
        assert e0["field"] == "first_name"
        assert isinstance(b["preview"], list) and len(b["preview"]) == 3

    def test_commit_true_inserts(self, admin_token):
        """Commit a fresh batch of 2 rows."""
        headers = ["first_name", "last_name", "national_id", "phone", "gender", "date_of_birth"]
        rows = [
            {"first_name": f"{P}Com1", "last_name": "Persist", "national_id": f"{NID}_COM1", "phone": "55550201", "gender": "M", "date_of_birth": "1975-01-15"},
            {"first_name": f"{P}Com2", "last_name": "Persist", "national_id": f"{NID}_COM2", "phone": "55550202", "gender": "F", "date_of_birth": "1980-07-22"},
        ]
        csv_bytes = _make_csv(rows, headers)
        files = {"file": ("commit.csv", csv_bytes, "text/csv")}
        r = requests.post(
            f"{BASE_URL}/api/clinic/patients-bulk/import?commit=true",
            headers=_h(admin_token), files=files, timeout=30,
        )
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["committed"] is True, b
        assert b["imported"] == 2, b
        assert b["valid_rows"] == 2
        assert b["commit_errors"] == []

    def test_recommit_same_returns_all_duplicates(self, admin_token):
        """Re-upload same data already committed -> all duplicates."""
        headers = ["first_name", "last_name", "national_id", "phone", "gender"]
        rows = [
            {"first_name": f"{P}Com1", "last_name": "Persist", "national_id": f"{NID}_COM1", "phone": "55550201", "gender": "M"},
            {"first_name": f"{P}Com2", "last_name": "Persist", "national_id": f"{NID}_COM2", "phone": "55550202", "gender": "F"},
        ]
        csv_bytes = _make_csv(rows, headers)
        files = {"file": ("recommit.csv", csv_bytes, "text/csv")}
        r = requests.post(
            f"{BASE_URL}/api/clinic/patients-bulk/import?commit=true",
            headers=_h(admin_token), files=files, timeout=30,
        )
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["imported"] == 0, b
        assert b["duplicates_skipped"] >= 2, b


# ==================== XLSX + native Excel dates ====================

class TestXlsx:
    def test_xlsx_native_date_cells(self, admin_token):
        from openpyxl import Workbook
        from datetime import date
        wb = Workbook()
        ws = wb.active
        ws.append(["first_name", "last_name", "national_id", "phone", "gender", "date_of_birth"])
        # native Excel date objects
        ws.append([f"{P}Xls1", "DateTest", f"{NID}_XLS1", "55550301", "M", date(1991, 3, 14)])
        ws.append([f"{P}Xls2", "DateTest", f"{NID}_XLS2", "55550302", "F", date(2000, 12, 1)])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)

        # dry-run first to verify ISO conversion in preview
        files = {"file": ("dates.xlsx", buf.getvalue(),
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        r = requests.post(
            f"{BASE_URL}/api/clinic/patients-bulk/import?commit=false",
            headers=_h(admin_token), files=files, timeout=30,
        )
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["valid_rows"] == 2, b
        assert b["error_rows"] == 0, b

        # commit
        files = {"file": ("dates.xlsx", buf.getvalue(),
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        r = requests.post(
            f"{BASE_URL}/api/clinic/patients-bulk/import?commit=true",
            headers=_h(admin_token), files=files, timeout=30,
        )
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["imported"] == 2, b
        assert b["committed"] is True

        # Verify date_of_birth via GET /api/clinic/patients (search by national_id or name)
        r = requests.get(
            f"{BASE_URL}/api/clinic/patients?search={P}Xls1",
            headers=_h(admin_token), timeout=20,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        items = data.get("items") or data.get("patients") or data if isinstance(data, list) else (data.get("items") or data.get("data") or [])
        if isinstance(data, dict) and not items:
            # fall back to common key shapes
            for k in ("items", "data", "results", "patients"):
                if k in data and isinstance(data[k], list):
                    items = data[k]
                    break
        assert items, f"No patient returned for search: {data}"
        target = [p for p in items if p.get("national_id") == f"{NID}_XLS1"]
        assert target, f"Patient with national_id {NID}_XLS1 not found in {items}"
        dob = target[0].get("date_of_birth")
        assert dob and dob.startswith("1991-03-14"), f"DOB ISO mismatch: {dob}"


# ==================== Dedup variants ====================

class TestDedup:
    def test_national_id_case_insensitive(self, admin_token):
        """Insert a patient with mixed-case national_id, then re-import lower case -> dedup."""
        headers = ["first_name", "last_name", "national_id", "phone"]
        nid = f"{NID}_CASE_AbCd"
        rows = [{"first_name": f"{P}Case", "last_name": "Test", "national_id": nid, "phone": "55550401"}]
        files = {"file": ("c1.csv", _make_csv(rows, headers), "text/csv")}
        r = requests.post(f"{BASE_URL}/api/clinic/patients-bulk/import?commit=true",
                          headers=_h(admin_token), files=files, timeout=30)
        assert r.status_code == 200 and r.json()["imported"] == 1, r.text

        # Now re-import same row with national_id lower-cased
        rows2 = [{"first_name": f"{P}Case", "last_name": "Test", "national_id": nid.lower(), "phone": "55550401"}]
        files2 = {"file": ("c2.csv", _make_csv(rows2, headers), "text/csv")}
        r2 = requests.post(f"{BASE_URL}/api/clinic/patients-bulk/import?commit=true",
                           headers=_h(admin_token), files=files2, timeout=30)
        assert r2.status_code == 200, r2.text
        b = r2.json()
        assert b["imported"] == 0, b
        assert b["duplicates_skipped"] == 1, b

    def test_composite_fallback_when_no_national_id(self, admin_token):
        """No national_id -> dedup on first_name+last_name+phone."""
        headers = ["first_name", "last_name", "phone"]
        rows = [{"first_name": f"{P}NoNid", "last_name": "Composite", "phone": "55550501"}]
        files = {"file": ("d1.csv", _make_csv(rows, headers), "text/csv")}
        r = requests.post(f"{BASE_URL}/api/clinic/patients-bulk/import?commit=true",
                          headers=_h(admin_token), files=files, timeout=30)
        assert r.status_code == 200 and r.json()["imported"] == 1, r.text

        files2 = {"file": ("d2.csv", _make_csv(rows, headers), "text/csv")}
        r2 = requests.post(f"{BASE_URL}/api/clinic/patients-bulk/import?commit=true",
                           headers=_h(admin_token), files=files2, timeout=30)
        assert r2.status_code == 200, r2.text
        b = r2.json()
        assert b["imported"] == 0, b
        assert b["duplicates_skipped"] >= 1, b


# ==================== Role access ====================

class TestRoles:
    def test_doctor_can_dryrun(self, doctor_token):
        headers = ["first_name", "last_name"]
        rows = [{"first_name": f"{P}Doc", "last_name": "AccessTest"}]
        files = {"file": ("doc.csv", _make_csv(rows, headers), "text/csv")}
        r = requests.post(f"{BASE_URL}/api/clinic/patients-bulk/import?commit=false",
                          headers=_h(doctor_token), files=files, timeout=30)
        assert r.status_code == 200, f"Doctor should be allowed: {r.status_code} {r.text}"

    def test_receptionist_can_dryrun(self, recep_token):
        headers = ["first_name", "last_name"]
        rows = [{"first_name": f"{P}Rec", "last_name": "AccessTest"}]
        files = {"file": ("rec.csv", _make_csv(rows, headers), "text/csv")}
        r = requests.post(f"{BASE_URL}/api/clinic/patients-bulk/import?commit=false",
                          headers=_h(recep_token), files=files, timeout=30)
        assert r.status_code == 200, f"Receptionist should be allowed: {r.status_code} {r.text}"


# ==================== Error cases ====================

class TestErrors:
    def test_empty_file_400(self, admin_token):
        files = {"file": ("empty.csv", b"", "text/csv")}
        r = requests.post(f"{BASE_URL}/api/clinic/patients-bulk/import",
                          headers=_h(admin_token), files=files, timeout=20)
        assert r.status_code == 400, r.text
        assert "vacío" in r.text.lower() or "empty" in r.text.lower()

    def test_pdf_unsupported_400(self, admin_token):
        files = {"file": ("file.pdf", b"%PDF-1.4 fake", "application/pdf")}
        r = requests.post(f"{BASE_URL}/api/clinic/patients-bulk/import",
                          headers=_h(admin_token), files=files, timeout=20)
        assert r.status_code == 400, r.text
        assert "Formato no soportado" in r.text

    def test_missing_required_column_400(self, admin_token):
        # CSV without first_name column
        csv_bytes = b"last_name,phone\nNoFirst,5551234\n"
        files = {"file": ("bad.csv", csv_bytes, "text/csv")}
        r = requests.post(f"{BASE_URL}/api/clinic/patients-bulk/import",
                          headers=_h(admin_token), files=files, timeout=20)
        assert r.status_code == 400, r.text
        assert "first_name" in r.text


# ==================== Cleanup ====================

class TestZZCleanup:
    def test_cleanup_test_patients(self, admin_token):
        """Best-effort cleanup of patients created by this run.

        Uses the public DELETE endpoint per patient. We list patients by search prefix.
        """
        # Search for our prefix
        r = requests.get(f"{BASE_URL}/api/clinic/patients?search={P}&limit=100",
                         headers=_h(admin_token), timeout=20)
        if r.status_code != 200:
            pytest.skip(f"Cannot list patients for cleanup: {r.status_code}")
        data = r.json()
        items = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            for k in ("items", "data", "results", "patients"):
                if k in data and isinstance(data[k], list):
                    items = data[k]
                    break
        deleted = 0
        for p in items:
            pid = p.get("id")
            if not pid:
                continue
            if not (p.get("first_name") or "").startswith(P):
                continue
            dr = requests.delete(f"{BASE_URL}/api/clinic/patients/{pid}",
                                 headers=_h(admin_token), timeout=20)
            if dr.status_code in (200, 204):
                deleted += 1
        # Don't fail if cleanup is partial — just report.
        print(f"Cleanup: deleted {deleted}/{len(items)} test patients")
