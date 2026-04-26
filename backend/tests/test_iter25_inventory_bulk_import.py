"""Iteration 25: Bulk inventory/products import via CSV / XLSX.

Endpoints under test:
  - POST /api/clinic/inventory-bulk/import  (commit=false dry-run, commit=true)
  - GET  /api/clinic/inventory-bulk/template?format=csv|xlsx

Coverage:
  - CSV dry-run with 4 rows (2 valid + 1 missing required + 1 dup)
  - CSV commit=true (insert + auto-create categories + seed inventory_stock)
  - Re-upload after commit -> all duplicates_skipped
  - XLSX with native Excel numbers / booleans + integer min/max stock persistence
  - branch_id query override
  - Template CSV (JSON) and XLSX (binary StreamingResponse)
  - Empty file 400, .pdf 400, missing required column 400, >5MB 400
  - Auto-create categories case-insensitive match (no dup)
  - initial_stock=0 -> no stock row; initial_stock>0 -> stock row + counter
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

BRANCH_MAIN = "79c47aab-3d03-49a0-bcec-b931766aa48e"
BRANCH_Z15 = "2ba2e8c4-3dde-4662-b232-11c3eff82bc9"

RUN_ID = f"{int(time.time())}{uuid.uuid4().hex[:4]}"
P = f"TestInv_{RUN_ID}_"           # product name prefix
SKU = f"SKU{RUN_ID}"               # sku base
CAT = f"TestInv_Cat_{RUN_ID}_"     # category prefix


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"Login failed for {email}: {r.status_code} {r.text}"
    return r.json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


@pytest.fixture(scope="module")
def admin_token():
    return _login(*CLINIC_ADMIN)


def _make_csv(rows, headers):
    out = io.StringIO()
    out.write(",".join(headers) + "\n")
    for r in rows:
        line = []
        for h in headers:
            v = "" if r.get(h) is None else str(r.get(h))
            if "," in v or '"' in v:
                v = '"' + v.replace('"', '""') + '"'
            line.append(v)
        out.write(",".join(line) + "\n")
    return out.getvalue().encode("utf-8")


# ==================== TEMPLATE ====================

class TestTemplate:
    def test_template_csv(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/clinic/inventory-bulk/template?format=csv",
                         headers=_h(admin_token), timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "headers" in data and "content" in data
        assert "name" in data["headers"]
        assert "initial_stock" in data["headers"]
        assert "category" in data["headers"]
        assert "name" in data["content"]

    def test_template_xlsx(self, admin_token):
        r = requests.get(f"{BASE_URL}/api/clinic/inventory-bulk/template?format=xlsx",
                         headers=_h(admin_token), timeout=20)
        assert r.status_code == 200, r.text
        ct = r.headers.get("content-type", "")
        assert "spreadsheetml" in ct or "officedocument" in ct, ct
        cd = r.headers.get("content-disposition", "")
        assert "plantilla_productos.xlsx" in cd
        assert r.content[:2] == b"PK"


# ==================== Dry-run + commit + dedup ====================

class TestDryRunCommit:
    seeded_product_ids = []

    def test_dry_run_mixed(self, admin_token):
        """Insert one product first to test dedup-on-existing."""
        # Seed one existing product via commit path
        headers = ["name", "sku", "brand", "category", "sale_price", "min_stock", "max_stock", "initial_stock"]
        seed_rows = [{
            "name": f"{P}Seed",
            "sku": f"{SKU}_SEED",
            "brand": "TestBrand",
            "category": f"{CAT}Existing",
            "sale_price": "10.50",
            "min_stock": "5",
            "max_stock": "50",
            "initial_stock": "0",
        }]
        files = {"file": ("seed.csv", _make_csv(seed_rows, headers), "text/csv")}
        rs = requests.post(f"{BASE_URL}/api/clinic/inventory-bulk/import?commit=true",
                           headers=_h(admin_token), files=files, timeout=30)
        assert rs.status_code == 200, rs.text
        bs = rs.json()
        assert bs["imported"] == 1, bs
        assert bs["categories_created"] >= 0
        # 0 stock_seeded for initial_stock=0
        assert bs["stock_seeded"] == 0, bs

        # Now dry-run with mixed
        rows = [
            {"name": f"{P}A", "sku": f"{SKU}_A", "brand": "BrandA", "category": f"{CAT}New1", "sale_price": "5.00", "min_stock": "2", "max_stock": "20", "initial_stock": "10"},
            {"name": f"{P}B", "sku": f"{SKU}_B", "brand": "BrandB", "category": f"{CAT}New1", "sale_price": "7.00", "min_stock": "0", "max_stock": "", "initial_stock": "0"},
            {"name": "",       "sku": f"{SKU}_X", "brand": "MissReq", "category": "", "sale_price": "1", "initial_stock": "0"},
            # dup of seed by SKU (case-insensitive)
            {"name": f"{P}DupBySku", "sku": f"{SKU}_seed", "brand": "X", "category": "", "sale_price": "1", "initial_stock": "0"},
        ]
        files = {"file": ("mix.csv", _make_csv(rows, headers), "text/csv")}
        r = requests.post(f"{BASE_URL}/api/clinic/inventory-bulk/import?commit=false",
                          headers=_h(admin_token), files=files, timeout=30)
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["total"] == 4, b
        assert b["valid_rows"] == 2, b
        assert b["error_rows"] == 1, b
        assert b["duplicates_skipped"] == 1, b
        assert b["committed"] is False
        assert b["imported"] == 0
        e0 = b["errors"][0]
        assert e0["field"] == "name"
        assert isinstance(b["preview"], list) and len(b["preview"]) == 2

    def test_commit_inserts_with_categories_and_stock(self, admin_token):
        """Commit fresh batch -> verify products + categories + stock seeding."""
        headers = ["name", "sku", "brand", "category", "sale_price", "min_stock", "max_stock", "initial_stock"]
        rows = [
            {"name": f"{P}Com1", "sku": f"{SKU}_COM1", "brand": "BrandC", "category": f"{CAT}AutoNew", "sale_price": "12.00", "min_stock": "3", "max_stock": "30", "initial_stock": "25"},
            {"name": f"{P}Com2", "sku": f"{SKU}_COM2", "brand": "BrandC", "category": f"{CAT}AutoNew", "sale_price": "18.50", "min_stock": "1", "max_stock": "10", "initial_stock": "5"},
            {"name": f"{P}Com3", "sku": f"{SKU}_COM3", "brand": "BrandD", "category": f"{CAT}AutoNew2", "sale_price": "3.25", "min_stock": "0", "max_stock": "", "initial_stock": "0"},
        ]
        files = {"file": ("commit.csv", _make_csv(rows, headers), "text/csv")}
        r = requests.post(f"{BASE_URL}/api/clinic/inventory-bulk/import?commit=true",
                          headers=_h(admin_token), files=files, timeout=30)
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["committed"] is True, b
        assert b["imported"] == 3, b
        # 2 distinct new categories
        assert b["categories_created"] >= 2, b
        # only Com1 + Com2 had initial_stock>0
        assert b["stock_seeded"] == 2, b
        assert b["target_branch_id"] == BRANCH_MAIN, b

        # Verify via GET /api/clinic/inventory/products (uses q= param, returns {"products":[]})
        rg = requests.get(f"{BASE_URL}/api/clinic/inventory/products?q={P}Com1",
                          headers=_h(admin_token), timeout=20)
        assert rg.status_code == 200, rg.text
        items = rg.json().get("products", []) if isinstance(rg.json(), dict) else rg.json()
        assert any(p.get("name") == f"{P}Com1" for p in items), f"{P}Com1 not found: {items}"
        target = next(p for p in items if p.get("name") == f"{P}Com1")
        # min_stock/max_stock stored as integer types
        assert isinstance(target.get("min_stock"), int), f"min_stock not int: {type(target.get('min_stock'))}"
        if target.get("max_stock") is not None:
            assert isinstance(target.get("max_stock"), int), f"max_stock not int: {type(target.get('max_stock'))}"

        # Verify stock at main branch via GET /api/clinic/inventory/stock
        rs = requests.get(f"{BASE_URL}/api/clinic/inventory/stock?branch_id={BRANCH_MAIN}",
                          headers=_h(admin_token), timeout=20)
        assert rs.status_code == 200, rs.text
        stocks = rs.json() if isinstance(rs.json(), list) else (rs.json().get("items") or [])
        com1 = next((s for s in stocks if s.get("product_id") == target.get("id")), None)
        assert com1, f"No stock row for {P}Com1 / id {target.get('id')}"
        # Quantity should be 25
        assert int(com1.get("quantity") or 0) == 25, com1

    def test_recommit_same_returns_all_duplicates(self, admin_token):
        headers = ["name", "sku", "brand", "category", "sale_price", "initial_stock"]
        rows = [
            {"name": f"{P}Com1", "sku": f"{SKU}_COM1", "brand": "BrandC", "category": f"{CAT}AutoNew", "sale_price": "12.00", "initial_stock": "0"},
            {"name": f"{P}Com2", "sku": f"{SKU}_COM2", "brand": "BrandC", "category": f"{CAT}AutoNew", "sale_price": "18.50", "initial_stock": "0"},
        ]
        files = {"file": ("rec.csv", _make_csv(rows, headers), "text/csv")}
        r = requests.post(f"{BASE_URL}/api/clinic/inventory-bulk/import?commit=true",
                          headers=_h(admin_token), files=files, timeout=30)
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["imported"] == 0, b
        assert b["duplicates_skipped"] >= 2, b


# ==================== XLSX with native types ====================

class TestXlsx:
    def test_xlsx_native_numbers_booleans(self, admin_token):
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.append(["name", "sku", "brand", "category", "sale_price", "cost_price",
                   "min_stock", "max_stock", "requires_prescription", "has_expiration", "initial_stock"])
        ws.append([f"{P}Xls1", f"{SKU}_XLS1", "BrandX", f"{CAT}XlsCat",
                   12.75, 6.50, 5, 60, False, True, 8])
        ws.append([f"{P}Xls2", f"{SKU}_XLS2", "BrandX", f"{CAT}XlsCat",
                   3.0, 1.25, 0, 20, True, False, 0])
        buf = io.BytesIO()
        wb.save(buf); buf.seek(0)

        files = {"file": ("inv.xlsx", buf.getvalue(),
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        r = requests.post(f"{BASE_URL}/api/clinic/inventory-bulk/import?commit=false",
                          headers=_h(admin_token), files=files, timeout=30)
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["valid_rows"] == 2, b
        assert b["error_rows"] == 0, b

        # commit
        files = {"file": ("inv.xlsx", buf.getvalue(),
                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        r = requests.post(f"{BASE_URL}/api/clinic/inventory-bulk/import?commit=true",
                          headers=_h(admin_token), files=files, timeout=30)
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["imported"] == 2, b
        assert b["committed"] is True
        # Only Xls1 had initial_stock=8>0 -> stock_seeded=1
        assert b["stock_seeded"] == 1, b

        # Verify min/max stored as integer
        rg = requests.get(f"{BASE_URL}/api/clinic/inventory/products?q={P}Xls1",
                          headers=_h(admin_token), timeout=20)
        items = rg.json().get("products", []) if isinstance(rg.json(), dict) else rg.json()
        prod = next((p for p in items if p.get("name") == f"{P}Xls1"), None)
        assert prod, f"{P}Xls1 not found"
        assert prod.get("min_stock") == 5, prod
        assert prod.get("max_stock") == 60, prod
        assert prod.get("has_expiration") is True, prod
        assert prod.get("requires_prescription") is False, prod


# ==================== branch_id override ====================

class TestBranchOverride:
    def test_branch_id_query_overrides_main(self, admin_token):
        headers = ["name", "sku", "category", "sale_price", "initial_stock"]
        rows = [{"name": f"{P}BrZ15", "sku": f"{SKU}_BRZ15", "category": f"{CAT}Z15",
                 "sale_price": "9.99", "initial_stock": "7"}]
        files = {"file": ("br.csv", _make_csv(rows, headers), "text/csv")}
        r = requests.post(f"{BASE_URL}/api/clinic/inventory-bulk/import?commit=true&branch_id={BRANCH_Z15}",
                          headers=_h(admin_token), files=files, timeout=30)
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["imported"] == 1, b
        assert b["target_branch_id"] == BRANCH_Z15, b
        assert b["stock_seeded"] == 1, b

        # Verify the stock row is at Z15 not main
        rg = requests.get(f"{BASE_URL}/api/clinic/inventory/products?q={P}BrZ15",
                          headers=_h(admin_token), timeout=20)
        items = rg.json().get("products", []) if isinstance(rg.json(), dict) else rg.json()
        prod = next((p for p in items if p.get("name") == f"{P}BrZ15"), None)
        assert prod, "BrZ15 product not found"

        rs = requests.get(f"{BASE_URL}/api/clinic/inventory/stock?branch_id={BRANCH_Z15}",
                          headers=_h(admin_token), timeout=20)
        stocks = rs.json() if isinstance(rs.json(), list) else (rs.json().get("items") or [])
        match = next((s for s in stocks if s.get("product_id") == prod.get("id")), None)
        assert match, f"No Z15 stock row for {prod.get('id')}"
        assert int(match.get("quantity") or 0) == 7, match


# ==================== Category dedup case-insensitive ====================

class TestCategoryDedup:
    def test_existing_category_case_insensitive(self, admin_token):
        """Re-using a category in different case should NOT create a duplicate category."""
        cat_label = f"{CAT}AutoNew"  # already created in TestDryRunCommit.test_commit_inserts
        # Use UPPERCASE variant - should match existing case-insensitively
        headers = ["name", "sku", "category", "sale_price", "initial_stock"]
        rows = [{"name": f"{P}CatCase", "sku": f"{SKU}_CATCASE",
                 "category": cat_label.upper(), "sale_price": "1", "initial_stock": "0"}]
        files = {"file": ("catcase.csv", _make_csv(rows, headers), "text/csv")}
        r = requests.post(f"{BASE_URL}/api/clinic/inventory-bulk/import?commit=true",
                          headers=_h(admin_token), files=files, timeout=30)
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["imported"] == 1, b
        # No new category should have been created
        assert b["categories_created"] == 0, b


# ==================== Error cases ====================

class TestErrors:
    def test_empty_file_400(self, admin_token):
        files = {"file": ("empty.csv", b"", "text/csv")}
        r = requests.post(f"{BASE_URL}/api/clinic/inventory-bulk/import",
                          headers=_h(admin_token), files=files, timeout=20)
        assert r.status_code == 400, r.text
        assert "vacío" in r.text.lower() or "empty" in r.text.lower()

    def test_pdf_unsupported_400(self, admin_token):
        files = {"file": ("file.pdf", b"%PDF-1.4 fake", "application/pdf")}
        r = requests.post(f"{BASE_URL}/api/clinic/inventory-bulk/import",
                          headers=_h(admin_token), files=files, timeout=20)
        assert r.status_code == 400, r.text
        assert "Formato no soportado" in r.text

    def test_missing_required_column_400(self, admin_token):
        # CSV without 'name' column
        csv_bytes = b"sku,brand\nNOR1,BrandX\n"
        files = {"file": ("bad.csv", csv_bytes, "text/csv")}
        r = requests.post(f"{BASE_URL}/api/clinic/inventory-bulk/import",
                          headers=_h(admin_token), files=files, timeout=20)
        assert r.status_code == 400, r.text
        assert "name" in r.text

    def test_oversize_5mb_400(self, admin_token):
        # 5.1 MB payload
        big = b"name,sku\n" + (b"x," * 100 + b"\n") * (5 * 1024 * 1024 // 200 + 50)
        files = {"file": ("big.csv", big, "text/csv")}
        r = requests.post(f"{BASE_URL}/api/clinic/inventory-bulk/import",
                          headers=_h(admin_token), files=files, timeout=30)
        assert r.status_code == 400, r.text
        assert "5 MB" in r.text or "5MB" in r.text or "límite" in r.text.lower()
