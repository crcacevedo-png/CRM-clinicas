"""Backend regression tests for the 6 NEW audit fixes (Cortexia Medical CRM).

FIX1 (P0): cancel_sale reverts accounts_receivable AND commissions.
FIX2 (P1): sale with AR creates sale + items + AR consistently (happy path).
FIX3 (P1): post-insert stock verification (no negative stock, oversell blocked).
FIX4 (P2): PnL income matches /reports/income total when a global discount is applied.
FIX5 (P2): AR payment updates payment_plan_installments FIFO (full and partial).
FIX6 (P2): Inventory bulk import seeds stock via inventory_movements of type 'purchase'
           with reference_type='import' (never writes inventory_stock directly).
MINOR: cash_session_id from another clinic / nonexistent is rejected.

Scope: isolated audit clinics A/B only.
"""
import io
import os
import uuid
import time
import csv as _csv
import requests
import pytest

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE}/api"

AUDIT_A_EMAIL = "audita@test-cortexia.com"
AUDIT_A_PASS = "AuditTest2026!"
AUDIT_A_CLINIC = "4687b2ad-6530-43aa-948a-92dc0cdb5aae"

AUDIT_B_EMAIL = "auditb@test-cortexia.com"
AUDIT_B_PASS = "AuditTest2026!"
AUDIT_B_CLINIC = "09f2caf3-c3b8-43fb-b2bb-dad5dc9c497e"


# ---------- shared helpers ----------

def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed {email}: {r.status_code} {r.text}"
    tok = r.json().get("access_token")
    assert tok, f"no token: {r.json()}"
    return tok


@pytest.fixture(scope="session")
def H_a():
    return {"Authorization": f"Bearer {_login(AUDIT_A_EMAIL, AUDIT_A_PASS)}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def H_b():
    return {"Authorization": f"Bearer {_login(AUDIT_B_EMAIL, AUDIT_B_PASS)}", "Content-Type": "application/json"}


def _first_branch(H):
    r = requests.get(f"{API}/clinic/branches", headers=H, timeout=30)
    assert r.status_code == 200, r.text
    arr = r.json() if isinstance(r.json(), list) else r.json().get("branches", [])
    assert arr, "no branches found"
    return arr[0]


@pytest.fixture(scope="session")
def branch_a(H_a):
    return _first_branch(H_a)


@pytest.fixture(scope="session")
def branch_b(H_b):
    return _first_branch(H_b)


def _create_product(H, name=None, cost=10.0, price=100.0, tax=0):
    name = name or f"TEST_P_{uuid.uuid4().hex[:6]}"
    r = requests.post(f"{API}/clinic/inventory/products", headers=H, json={
        "name": name, "cost_price": cost, "sale_price": price,
        "tax_rate": tax, "sku": f"SKU-{uuid.uuid4().hex[:8]}",
        "unit": "unidad", "is_active": True,
    }, timeout=30)
    assert r.status_code in (200, 201), f"create_product: {r.status_code} {r.text}"
    return r.json()["id"]


def _adjust_stock(H, product_id, branch_id, new_qty):
    r = requests.post(f"{API}/clinic/inventory/adjust", headers=H, json={
        "product_id": product_id, "branch_id": branch_id,
        "new_quantity": new_qty, "reason": "TEST seed",
    }, timeout=30)
    assert r.status_code in (200, 201), f"adjust_stock: {r.status_code} {r.text}"


def _get_stock(H, product_id, branch_id):
    r = requests.get(f"{API}/clinic/inventory/stock", headers=H, params={"branch_id": branch_id}, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    rows = data if isinstance(data, list) else data.get("stock", [])
    for s in rows:
        if s.get("product_id") == product_id:
            return float(s.get("quantity") or 0)
    return 0.0


def _create_patient(H):
    r = requests.post(f"{API}/clinic/patients", headers=H, json={
        "first_name": f"TESTAR{uuid.uuid4().hex[:4]}", "last_name": "Patient",
        "date_of_birth": "1990-01-01", "gender": "male",
    }, timeout=30)
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def _get_ar_list(H, patient_id=None):
    params = {}
    if patient_id:
        params["patient_id"] = patient_id
    r = requests.get(f"{API}/clinic/accounts-receivable", headers=H, params=params, timeout=30)
    assert r.status_code == 200, r.text
    return r.json().get("accounts", [])


# =================================================================
# FIX1 (P0): cancel credit sale reverts AR and commissions + restores stock
# =================================================================

def test_fix1_cancel_credit_sale_reverts_ar_and_stock(H_a, branch_a):
    pid = _create_product(H_a, cost=10, price=100, tax=0)
    _adjust_stock(H_a, pid, branch_a["id"], 10)
    stock0 = _get_stock(H_a, pid, branch_a["id"])
    assert stock0 == 10.0, f"seed stock 10 expected got {stock0}"

    patient_id = _create_patient(H_a)

    # Credit sale: 2 x 100 = 200, no payment (fully on credit)
    sale_payload = {
        "branch_id": branch_a["id"],
        "patient_id": patient_id,
        "items": [{"product_id": pid, "quantity": 2, "unit_price": 100.0, "tax_rate": 0, "description": "TEST"}],
        "payments": [],
        "customer_name": "TEST Credit",
    }
    r = requests.post(f"{API}/clinic/sales", headers=H_a, json=sale_payload, timeout=30)
    assert r.status_code == 200, f"create credit sale: {r.status_code} {r.text}"
    sale_id = r.json()["id"]

    # Stock decremented by 2
    stock1 = _get_stock(H_a, pid, branch_a["id"])
    assert stock1 == stock0 - 2, f"stock after sale expected {stock0-2} got {stock1}"

    # An AR must exist with balance 200 and status != cancelled
    ars = [a for a in _get_ar_list(H_a, patient_id=patient_id) if a.get("sale_id") == sale_id]
    assert ars, "AR not created for credit sale (FIX2 regression)"
    ar = ars[0]
    assert float(ar.get("balance") or 0) == 200.0, f"AR balance expected 200 got {ar.get('balance')}"
    assert ar.get("status") != "cancelled"

    # Cancel the sale
    r = requests.post(f"{API}/clinic/sales/{sale_id}/cancel", headers=H_a,
                      json={"reason": "TEST cancel credit"}, timeout=30)
    assert r.status_code == 200, f"cancel: {r.status_code} {r.text}"

    # Sale is cancelled
    r = requests.get(f"{API}/clinic/sales/{sale_id}", headers=H_a, timeout=30)
    assert r.status_code == 200
    assert r.json().get("status") == "cancelled"

    # AR must no longer appear as pending: either removed, or balance=0 and status in {cancelled,paid}
    ars_after = [a for a in _get_ar_list(H_a, patient_id=patient_id) if a.get("sale_id") == sale_id]
    for a in ars_after:
        assert float(a.get("balance") or 0) == 0.0, f"AR after cancel still has balance: {a}"
        assert a.get("status") in ("cancelled", "paid"), f"AR not cancelled: {a}"

    # Stock restored
    stock2 = _get_stock(H_a, pid, branch_a["id"])
    assert stock2 == stock0, f"stock not restored: expected {stock0} got {stock2}"


# =================================================================
# FIX2 (P1): credit-sale happy path still creates sale + items + AR
#            And a normal cash sale still works OK.
# =================================================================

def test_fix2_credit_sale_happy_path(H_a, branch_a):
    pid = _create_product(H_a, cost=5, price=50, tax=0)
    _adjust_stock(H_a, pid, branch_a["id"], 5)
    patient_id = _create_patient(H_a)

    r = requests.post(f"{API}/clinic/sales", headers=H_a, json={
        "branch_id": branch_a["id"],
        "patient_id": patient_id,
        "items": [{"product_id": pid, "quantity": 2, "unit_price": 50.0, "tax_rate": 0, "description": "TEST item"}],
        "payments": [{"payment_method": "cash", "amount": 20.0}],  # partial
        "customer_name": "TEST Partial Credit",
    }, timeout=30)
    assert r.status_code == 200, f"happy credit sale: {r.status_code} {r.text}"
    sale_id = r.json()["id"]

    r2 = requests.get(f"{API}/clinic/sales/{sale_id}", headers=H_a, timeout=30)
    assert r2.status_code == 200
    sale = r2.json()
    assert sale.get("status") == "completed"
    assert sale.get("payment_status") in ("partial", "pending")
    items = sale.get("items") or []
    assert len(items) == 1, f"items missing: {items}"

    ars = [a for a in _get_ar_list(H_a, patient_id=patient_id) if a.get("sale_id") == sale_id]
    assert ars and float(ars[0].get("balance") or 0) == 80.0, f"AR expected balance=80, got {ars}"


def test_fix2_cash_sale_normal(H_a, branch_a):
    pid = _create_product(H_a, cost=5, price=20, tax=0)
    _adjust_stock(H_a, pid, branch_a["id"], 10)
    r = requests.post(f"{API}/clinic/sales", headers=H_a, json={
        "branch_id": branch_a["id"],
        "items": [{"product_id": pid, "quantity": 1, "unit_price": 20.0, "tax_rate": 0, "description": "TEST item"}],
        "payments": [{"payment_method": "cash", "amount": 20.0}],
        "customer_name": "TEST Cash",
    }, timeout=30)
    assert r.status_code == 200, f"cash sale: {r.status_code} {r.text}"
    sale = r.json()
    assert sale.get("payment_status") == "paid"


# =================================================================
# FIX3 (P1): post-insert stock verification (anti-sobreventa)
# =================================================================

def test_fix3_exact_sellout_then_oversell(H_a, branch_a):
    pid = _create_product(H_a, cost=1, price=10, tax=0)
    _adjust_stock(H_a, pid, branch_a["id"], 5)
    assert _get_stock(H_a, pid, branch_a["id"]) == 5.0

    # Sell exactly 5
    r = requests.post(f"{API}/clinic/sales", headers=H_a, json={
        "branch_id": branch_a["id"],
        "items": [{"product_id": pid, "quantity": 5, "unit_price": 10.0, "tax_rate": 0, "description": "TEST item"}],
        "payments": [{"payment_method": "cash", "amount": 50.0}],
        "customer_name": "TEST exact",
    }, timeout=30)
    assert r.status_code == 200, f"exact sellout: {r.status_code} {r.text}"
    assert _get_stock(H_a, pid, branch_a["id"]) == 0.0

    # Try to sell 6 — must 400 w/ 'Stock insuficiente'
    r2 = requests.post(f"{API}/clinic/sales", headers=H_a, json={
        "branch_id": branch_a["id"],
        "items": [{"product_id": pid, "quantity": 6, "unit_price": 10.0, "tax_rate": 0, "description": "TEST item"}],
        "payments": [{"payment_method": "cash", "amount": 60.0}],
        "customer_name": "TEST over",
    }, timeout=30)
    assert r2.status_code == 400, f"oversell: expected 400 got {r2.status_code} {r2.text}"
    assert "stock insuficiente" in r2.text.lower()

    # Stock still 0, never negative
    s = _get_stock(H_a, pid, branch_a["id"])
    assert s >= 0, f"stock went negative: {s}"
    assert s == 0.0


# =================================================================
# FIX4 (P2): PnL consistent with global discount
# =================================================================

def test_fix4_pnl_matches_income_with_global_discount(H_a, branch_a):
    """Create a product + sale with discount_amount>0 in a tiny custom window,
    then verify /reports/income total_income == /reports/pnl current.income.total."""
    pid = _create_product(H_a, cost=5, price=100, tax=12)
    _adjust_stock(H_a, pid, branch_a["id"], 5)

    # Narrow period: today only
    from datetime import date as _d
    today = _d.today().isoformat()

    # Measure baseline for the day
    r_i0 = requests.get(f"{API}/clinic/reports/income", headers=H_a,
                       params={"period": "custom", "date_from": today, "date_to": today}, timeout=30)
    assert r_i0.status_code == 200, r_i0.text
    baseline_income = float(r_i0.json().get("total_income") or 0)

    r_p0 = requests.get(f"{API}/clinic/reports/pnl", headers=H_a,
                       params={"period": "custom", "date_from": today, "date_to": today}, timeout=30)
    assert r_p0.status_code == 200, r_p0.text
    baseline_pnl = float((r_p0.json().get("current") or {}).get("income", {}).get("total") or 0)

    # Create a sale with 1 unit @ Q100 + IVA 12%, global discount Q10
    # subtotal(after global)=100-10=90, tax=100*0.12=12, total=102
    r = requests.post(f"{API}/clinic/sales", headers=H_a, json={
        "branch_id": branch_a["id"],
        "items": [{"product_id": pid, "quantity": 1, "unit_price": 100.0, "tax_rate": 12, "description": "TEST item"}],
        "discount_amount": 10.0,
        "payments": [{"payment_method": "cash", "amount": 102.0}],
        "customer_name": "TEST discount",
    }, timeout=30)
    assert r.status_code == 200, f"discount sale: {r.status_code} {r.text}"

    # Re-measure
    r_i = requests.get(f"{API}/clinic/reports/income", headers=H_a,
                      params={"period": "custom", "date_from": today, "date_to": today}, timeout=30)
    assert r_i.status_code == 200
    income_total = float(r_i.json().get("total_income") or 0)

    r_p = requests.get(f"{API}/clinic/reports/pnl", headers=H_a,
                      params={"period": "custom", "date_from": today, "date_to": today}, timeout=30)
    assert r_p.status_code == 200
    pnl_total = float((r_p.json().get("current") or {}).get("income", {}).get("total") or 0)

    delta_income = round(income_total - baseline_income, 2)
    delta_pnl = round(pnl_total - baseline_pnl, 2)

    # Expected delta = total(102) - tax(12) = 90 (net of IVA, net of global discount)
    assert abs(delta_income - 90.0) < 0.05, f"income delta expected 90, got {delta_income}"
    assert abs(delta_pnl - delta_income) < 0.05, (
        f"FIX4 FAILED: PnL income_total ({delta_pnl}) != income total_income ({delta_income})"
    )


# =================================================================
# FIX5 (P2): AR payment updates payment_plan_installments FIFO
# =================================================================

def _get_ar(H, ar_id):
    r = requests.get(f"{API}/clinic/accounts-receivable/{ar_id}", headers=H, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


def test_fix5_ar_payment_updates_installments_fifo(H_a, branch_a):
    pid = _create_product(H_a, cost=10, price=100, tax=0)
    _adjust_stock(H_a, pid, branch_a["id"], 5)
    patient_id = _create_patient(H_a)

    # Credit sale 300 (3 x 100), no payment
    r = requests.post(f"{API}/clinic/sales", headers=H_a, json={
        "branch_id": branch_a["id"],
        "patient_id": patient_id,
        "items": [{"product_id": pid, "quantity": 3, "unit_price": 100.0, "tax_rate": 0, "description": "TEST item"}],
        "payments": [],
        "customer_name": "TEST plan",
    }, timeout=30)
    assert r.status_code == 200, r.text
    sale_id = r.json()["id"]
    ars = [a for a in _get_ar_list(H_a, patient_id=patient_id) if a.get("sale_id") == sale_id]
    assert ars, "AR missing"
    ar_id = ars[0]["id"]

    # Create a 3-installments plan: 100 + 100 + 100
    r = requests.post(f"{API}/clinic/accounts-receivable/{ar_id}/payment-plan", headers=H_a,
                     json={"installments": 3, "first_due_date": "2026-02-01", "frequency": "monthly"}, timeout=30)
    assert r.status_code == 200, f"create plan: {r.status_code} {r.text}"

    # --- PARTIAL payment: Q150 should pay installment #1 fully and leave #2 pending (not partial-paid status)
    r = requests.post(f"{API}/clinic/accounts-receivable/{ar_id}/payment", headers=H_a,
                     json={"amount": 150.0, "payment_method": "cash"}, timeout=30)
    assert r.status_code == 200, f"partial pay: {r.status_code} {r.text}"

    ar = _get_ar(H_a, ar_id)
    insts = ar.get("installments_list") or []
    insts = sorted(insts, key=lambda x: x.get("installment_number"))
    assert len(insts) == 3, f"expected 3 installments got {len(insts)}"
    # #1 paid, #2 partial (50/100), #3 pending
    assert insts[0]["status"] == "paid", f"inst1 status: {insts[0]}"
    assert float(insts[0].get("paid_amount") or 0) == 100.0
    # #2 should not be 'paid' yet (only 50 of 100)
    assert insts[1]["status"] != "paid", f"inst2 should not be paid yet: {insts[1]}"
    assert float(insts[1].get("paid_amount") or 0) == 50.0
    assert insts[2]["status"] == "pending", f"inst3 not pending: {insts[2]}"
    assert float(insts[2].get("paid_amount") or 0) == 0.0

    # --- FULL remaining payment: Q150 -> all installments paid
    r = requests.post(f"{API}/clinic/accounts-receivable/{ar_id}/payment", headers=H_a,
                     json={"amount": 150.0, "payment_method": "cash"}, timeout=30)
    assert r.status_code == 200, f"full pay: {r.status_code} {r.text}"

    ar2 = _get_ar(H_a, ar_id)
    insts2 = sorted(ar2.get("installments_list") or [], key=lambda x: x.get("installment_number"))
    for i in insts2:
        assert i["status"] == "paid", f"installment not paid after full payment: {i}"
    assert ar2.get("status") == "paid"
    assert float(ar2.get("balance") or 0) == 0.0


# =================================================================
# FIX6 (P2): Bulk import products — initial_stock seeds via inventory_movements
# =================================================================

def test_fix6_bulk_import_creates_purchase_movement(H_a, branch_a):
    # Build a CSV in-memory with one TEST_ product, initial_stock=7
    sku = f"IMP-{uuid.uuid4().hex[:8]}"
    name = f"TEST_IMPORT_{uuid.uuid4().hex[:6]}"
    headers_cols = ["name", "sku", "cost_price", "sale_price", "tax_rate", "unit", "initial_stock"]
    buf = io.StringIO()
    w = _csv.writer(buf)
    w.writerow(headers_cols)
    w.writerow([name, sku, "4.00", "15.00", "0", "unidad", "7"])
    csv_bytes = buf.getvalue().encode("utf-8")

    tok = H_a["Authorization"]
    files = {"file": ("import.csv", csv_bytes, "text/csv")}
    r = requests.post(f"{API}/clinic/inventory-bulk/import",
                      headers={"Authorization": tok},
                      files=files,
                      params={"branch_id": branch_a["id"], "commit": "true"},
                      timeout=60)
    assert r.status_code == 200, f"bulk import: {r.status_code} {r.text}"
    body = r.json()
    assert body.get("committed") is True, f"import not committed: {body}"
    assert body.get("stock_seeded", 0) >= 1, f"stock not seeded: {body}"

    # Find the newly imported product
    r2 = requests.get(f"{API}/clinic/inventory/products", headers=H_a, params={"q": name}, timeout=30)
    assert r2.status_code == 200, r2.text
    prods = r2.json() if isinstance(r2.json(), list) else r2.json().get("products", [])
    match = [p for p in prods if p.get("sku") == sku or p.get("name") == name]
    assert match, f"imported product not found: {prods}"
    pid = match[0]["id"]

    # Stock = 7 at target branch
    s = _get_stock(H_a, pid, branch_a["id"])
    assert s == 7.0, f"imported stock expected 7 got {s}"

    # inventory_movements of type 'purchase' with reference_type='import' must exist
    rm = requests.get(f"{API}/clinic/inventory/movements", headers=H_a,
                      params={"product_id": pid}, timeout=30)
    assert rm.status_code == 200, rm.text
    mdata = rm.json()
    movs = mdata if isinstance(mdata, list) else mdata.get("movements", [])
    import_movs = [m for m in movs if m.get("movement_type") == "purchase" and m.get("reference_type") == "import"]
    assert import_movs, f"no purchase/import movement found: movs={movs}"
    assert int(import_movs[0].get("quantity") or 0) == 7


# =================================================================
# MINOR: cash_session_id from another clinic / nonexistent is rejected
# =================================================================

def test_minor_cross_clinic_cash_session_rejected(H_a, H_b, branch_a):
    """Pass a cash_session_id that does NOT exist in clinic A -> must 400."""
    pid = _create_product(H_a, cost=1, price=10, tax=0)
    _adjust_stock(H_a, pid, branch_a["id"], 2)

    fake_cs = str(uuid.uuid4())  # nonexistent
    r = requests.post(f"{API}/clinic/sales", headers=H_a, json={
        "branch_id": branch_a["id"],
        "cash_session_id": fake_cs,
        "items": [{"product_id": pid, "quantity": 1, "unit_price": 10.0, "tax_rate": 0, "description": "TEST item"}],
        "payments": [{"payment_method": "cash", "amount": 10.0}],
        "customer_name": "TEST xclinic cs",
    }, timeout=30)
    assert r.status_code == 400, f"expected 400 for cross-clinic cs, got {r.status_code} {r.text}"
    assert "sesión de caja" in r.text.lower() or "caja" in r.text.lower()


def test_minor_normal_cash_session_works(H_a, branch_a):
    """A sale WITHOUT cash_session_id (fallback) and WITH a legit open session (if any) must work."""
    pid = _create_product(H_a, cost=1, price=10, tax=0)
    _adjust_stock(H_a, pid, branch_a["id"], 2)

    r = requests.post(f"{API}/clinic/sales", headers=H_a, json={
        "branch_id": branch_a["id"],
        "items": [{"product_id": pid, "quantity": 1, "unit_price": 10.0, "tax_rate": 0, "description": "TEST item"}],
        "payments": [{"payment_method": "cash", "amount": 10.0}],
        "customer_name": "TEST normal",
    }, timeout=30)
    assert r.status_code == 200, f"normal cash sale: {r.status_code} {r.text}"
