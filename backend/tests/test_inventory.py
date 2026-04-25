"""
Inventory Module Tests - Backend
Tests for:
- /api/clinic/inventory/categories (GET, POST)
- /api/clinic/inventory/products (GET, POST, PUT)
- /api/clinic/inventory/stock (GET)
- /api/clinic/inventory/adjust (POST)
- /api/clinic/inventory/alerts (GET)
- /api/clinic/inventory/movements (GET)
- /api/clinic/inventory/suppliers (GET, POST, PUT)
- /api/clinic/inventory/purchase-orders (GET, POST)
- /api/clinic/features (verify 'inventory' feature)
"""

import os
import time
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

CLINIC_ADMIN_EMAIL = "carlos@lasalud.gt"
CLINIC_ADMIN_PASSWORD = "Test123456!"
CLINIC_ID = "c0321ed8-97da-47a1-b601-3b94bffabdd7"


@pytest.fixture(scope="module")
def clinic_admin_token():
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": CLINIC_ADMIN_EMAIL,
        "password": CLINIC_ADMIN_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def headers(clinic_admin_token):
    return {"Authorization": f"Bearer {clinic_admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def branch_id(headers):
    """Get a branch ID for testing"""
    r = requests.get(f"{BASE_URL}/api/clinic/branches", headers=headers)
    assert r.status_code == 200, f"Failed to list branches: {r.text}"
    branches = r.json()
    assert len(branches) > 0, "No branches found"
    return branches[0]["id"]


# --- Feature flag check ---
class TestFeatureFlag:
    def test_inventory_feature_enabled(self, headers):
        r = requests.get(f"{BASE_URL}/api/clinic/features", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert "features" in data
        assert "inventory" in data["features"], f"'inventory' not in features: {data['features']}"


# --- Categories ---
class TestCategories:
    created_id = None

    def test_list_categories(self, headers):
        r = requests.get(f"{BASE_URL}/api/clinic/inventory/categories", headers=headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_create_category(self, headers):
        payload = {"name": f"TEST_Cat_{int(time.time())}", "description": "test category"}
        r = requests.post(f"{BASE_URL}/api/clinic/inventory/categories",
                          json=payload, headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "id" in data
        TestCategories.created_id = data["id"]

        # Verify GET shows it
        r2 = requests.get(f"{BASE_URL}/api/clinic/inventory/categories", headers=headers)
        ids = [c["id"] for c in r2.json()]
        assert data["id"] in ids


# --- Products ---
class TestProducts:
    created_id = None
    sku = None

    def test_list_products(self, headers):
        r = requests.get(f"{BASE_URL}/api/clinic/inventory/products", headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert "products" in body and "total" in body and "page" in body

    def test_create_product(self, headers):
        ts = int(time.time())
        TestProducts.sku = f"TEST-SKU-{ts}"
        payload = {
            "name": f"TEST_Producto_{ts}",
            "sku": TestProducts.sku,
            "brand": "TestBrand",
            "presentation": "Caja x10",
            "cost_price": 50,
            "sale_price": 100,
            "tax_rate": 12,
            "unit": "unidad",
            "min_stock": 5,
            "has_expiration": True,
            "is_active": True,
        }
        r = requests.post(f"{BASE_URL}/api/clinic/inventory/products",
                          json=payload, headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "id" in data
        TestProducts.created_id = data["id"]

    def test_get_product_in_list(self, headers):
        assert TestProducts.created_id is not None
        r = requests.get(f"{BASE_URL}/api/clinic/inventory/products?q=TEST_Producto",
                         headers=headers)
        assert r.status_code == 200
        ids = [p["id"] for p in r.json()["products"]]
        assert TestProducts.created_id in ids

    def test_update_product(self, headers):
        assert TestProducts.created_id is not None
        payload = {"sale_price": 150, "min_stock": 10}
        r = requests.put(f"{BASE_URL}/api/clinic/inventory/products/{TestProducts.created_id}",
                         json=payload, headers=headers)
        assert r.status_code == 200, r.text

        # Verify
        r2 = requests.get(
            f"{BASE_URL}/api/clinic/inventory/products?q=TEST_Producto",
            headers=headers,
        )
        prod = next((p for p in r2.json()["products"] if p["id"] == TestProducts.created_id), None)
        assert prod is not None
        assert float(prod["sale_price"]) == 150
        assert prod["min_stock"] == 10

    def test_search_products(self, headers):
        r = requests.get(f"{BASE_URL}/api/clinic/inventory/products/search?q=TEST",
                         headers=headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# --- Stock & Adjust ---
class TestStock:
    def test_list_stock(self, headers):
        r = requests.get(f"{BASE_URL}/api/clinic/inventory/stock", headers=headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_list_stock_filter_branch(self, headers, branch_id):
        r = requests.get(f"{BASE_URL}/api/clinic/inventory/stock?branch_id={branch_id}",
                         headers=headers)
        assert r.status_code == 200
        for s in r.json():
            assert s["branch_id"] == branch_id

    def test_adjust_stock(self, headers, branch_id):
        assert TestProducts.created_id is not None
        payload = {
            "product_id": TestProducts.created_id,
            "branch_id": branch_id,
            "new_quantity": 25,
            "reason": "initial",
            "notes": "TEST adjust",
        }
        r = requests.post(f"{BASE_URL}/api/clinic/inventory/adjust",
                          json=payload, headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["new"] == 25

        # Verify in stock
        r2 = requests.get(f"{BASE_URL}/api/clinic/inventory/stock?branch_id={branch_id}",
                          headers=headers)
        stocks = r2.json()
        match = next((s for s in stocks if s["product_id"] == TestProducts.created_id), None)
        assert match is not None
        assert match["quantity"] == 25

    def test_alerts_structure(self, headers):
        r = requests.get(f"{BASE_URL}/api/clinic/inventory/alerts", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert "low_stock" in data
        assert "expiring" in data
        assert isinstance(data["low_stock"], list)
        assert isinstance(data["expiring"], list)


# --- Movements ---
class TestMovements:
    def test_list_movements(self, headers):
        r = requests.get(f"{BASE_URL}/api/clinic/inventory/movements", headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert "movements" in body and "total" in body and "page" in body

    def test_filter_by_type_adjustment(self, headers):
        r = requests.get(f"{BASE_URL}/api/clinic/inventory/movements?movement_type=adjustment",
                         headers=headers)
        assert r.status_code == 200
        for m in r.json()["movements"]:
            assert m["movement_type"] == "adjustment"

    def test_filter_by_branch(self, headers, branch_id):
        r = requests.get(f"{BASE_URL}/api/clinic/inventory/movements?branch_id={branch_id}",
                         headers=headers)
        assert r.status_code == 200
        for m in r.json()["movements"]:
            assert m["branch_id"] == branch_id


# --- Suppliers ---
class TestSuppliers:
    created_id = None

    def test_list_suppliers(self, headers):
        r = requests.get(f"{BASE_URL}/api/clinic/inventory/suppliers", headers=headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_create_supplier(self, headers):
        ts = int(time.time())
        payload = {
            "name": f"TEST_Supplier_{ts}",
            "tax_id": "12345678",
            "contact_person": "John Test",
            "phone": "5555-1234",
            "email": f"test{ts}@example.com",
            "address": "Test Address 123",
        }
        r = requests.post(f"{BASE_URL}/api/clinic/inventory/suppliers",
                          json=payload, headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "id" in data
        TestSuppliers.created_id = data["id"]

    def test_supplier_in_list(self, headers):
        assert TestSuppliers.created_id is not None
        r = requests.get(f"{BASE_URL}/api/clinic/inventory/suppliers", headers=headers)
        ids = [s["id"] for s in r.json()]
        assert TestSuppliers.created_id in ids

    def test_update_supplier(self, headers):
        assert TestSuppliers.created_id is not None
        payload = {"phone": "5555-9999", "contact_person": "Jane Updated"}
        r = requests.put(
            f"{BASE_URL}/api/clinic/inventory/suppliers/{TestSuppliers.created_id}",
            json=payload, headers=headers,
        )
        assert r.status_code == 200, r.text

        # Verify
        r2 = requests.get(f"{BASE_URL}/api/clinic/inventory/suppliers", headers=headers)
        sup = next((s for s in r2.json() if s["id"] == TestSuppliers.created_id), None)
        assert sup is not None
        assert sup["phone"] == "5555-9999"
        assert sup["contact_person"] == "Jane Updated"


# --- Purchase Orders ---
class TestPurchaseOrders:
    pending_id = None
    received_id = None

    def test_create_pending_po_no_stock_change(self, headers, branch_id):
        assert TestProducts.created_id is not None
        # Get current stock
        r0 = requests.get(f"{BASE_URL}/api/clinic/inventory/stock?branch_id={branch_id}",
                          headers=headers)
        before = next(
            (s["quantity"] for s in r0.json() if s["product_id"] == TestProducts.created_id), 0)

        payload = {
            "branch_id": branch_id,
            "order_number": f"TEST-PO-PEND-{int(time.time())}",
            "supplier_name": "TEST Supplier Pending",
            "tax_rate": 12,
            "status": "pending",
            "items": [{
                "product_id": TestProducts.created_id,
                "quantity": 10,
                "unit_cost": 50,
                "subtotal": 500,
            }],
        }
        r = requests.post(f"{BASE_URL}/api/clinic/inventory/purchase-orders",
                          json=payload, headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "id" in data
        TestPurchaseOrders.pending_id = data["id"]

        # Stock should NOT change
        r1 = requests.get(f"{BASE_URL}/api/clinic/inventory/stock?branch_id={branch_id}",
                          headers=headers)
        after = next(
            (s["quantity"] for s in r1.json() if s["product_id"] == TestProducts.created_id), 0)
        assert after == before, f"Stock changed for pending PO: {before} -> {after}"

    def test_create_received_po_increases_stock(self, headers, branch_id):
        assert TestProducts.created_id is not None
        # Get current stock
        r0 = requests.get(f"{BASE_URL}/api/clinic/inventory/stock?branch_id={branch_id}",
                          headers=headers)
        before = next(
            (s["quantity"] for s in r0.json() if s["product_id"] == TestProducts.created_id), 0)

        qty = 7
        payload = {
            "branch_id": branch_id,
            "order_number": f"TEST-PO-RECV-{int(time.time())}",
            "supplier_name": "TEST Supplier Received",
            "tax_rate": 12,
            "status": "received",
            "items": [{
                "product_id": TestProducts.created_id,
                "quantity": qty,
                "unit_cost": 60,
                "subtotal": 60 * qty,
                "batch_number": "BATCH-TEST-001",
                "expiration_date": "2027-12-31",
            }],
        }
        r = requests.post(f"{BASE_URL}/api/clinic/inventory/purchase-orders",
                          json=payload, headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "id" in data
        TestPurchaseOrders.received_id = data["id"]

        # Stock should increase by qty
        r1 = requests.get(f"{BASE_URL}/api/clinic/inventory/stock?branch_id={branch_id}",
                          headers=headers)
        after = next(
            (s["quantity"] for s in r1.json() if s["product_id"] == TestProducts.created_id), 0)
        assert after == before + qty, f"Stock not increased: {before} + {qty} != {after}"

        # Verify a 'purchase' movement was created
        r2 = requests.get(
            f"{BASE_URL}/api/clinic/inventory/movements?movement_type=purchase&branch_id={branch_id}",
            headers=headers,
        )
        movs = r2.json()["movements"]
        match = next(
            (m for m in movs if m.get("reference_id") == TestPurchaseOrders.received_id),
            None,
        )
        assert match is not None, "purchase movement not created"
        assert match["quantity"] == qty

    def test_list_purchase_orders(self, headers):
        r = requests.get(f"{BASE_URL}/api/clinic/inventory/purchase-orders", headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert "orders" in body
        ids = [o["id"] for o in body["orders"]]
        if TestPurchaseOrders.pending_id:
            assert TestPurchaseOrders.pending_id in ids
        if TestPurchaseOrders.received_id:
            assert TestPurchaseOrders.received_id in ids

    def test_filter_purchase_orders_by_status(self, headers):
        r = requests.get(f"{BASE_URL}/api/clinic/inventory/purchase-orders?status=received",
                         headers=headers)
        assert r.status_code == 200
        for o in r.json()["orders"]:
            assert o["status"] == "received"


# --- Auth checks ---
class TestAuth:
    def test_inventory_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/clinic/inventory/products")
        assert r.status_code in [401, 403]
