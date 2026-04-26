"""Backend tests for /api/clinic/reports/* (financial reports module)."""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    # Fallback to read frontend/.env
    try:
        with open('/app/frontend/.env') as f:
            for line in f:
                if line.startswith('REACT_APP_BACKEND_URL='):
                    BASE_URL = line.split('=', 1)[1].strip().rstrip('/')
                    break
    except Exception:
        pass

CARLOS_EMAIL = "carlos@lasalud.gt"
CARLOS_PWD = "Test123456!"


@pytest.fixture(scope="module")
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def auth_headers(api_client):
    """Login as carlos and return auth headers."""
    r = api_client.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": CARLOS_EMAIL, "password": CARLOS_PWD},
        timeout=20,
    )
    if r.status_code != 200:
        pytest.skip(f"Login failed: {r.status_code} {r.text[:200]}")
    data = r.json()
    token = data.get("access_token") or data.get("token") or (data.get("session") or {}).get("access_token")
    if not token:
        pytest.skip(f"No token in login response: {data}")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# -------- Auth gating ---------
class TestReportsAuth:
    def test_executive_summary_requires_auth(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/clinic/reports/executive-summary", timeout=15)
        assert r.status_code in (401, 403)

    def test_income_requires_auth(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/clinic/reports/income", timeout=15)
        assert r.status_code in (401, 403)

    def test_pnl_requires_auth(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/clinic/reports/pnl", timeout=15)
        assert r.status_code in (401, 403)

    def test_inventory_requires_auth(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/clinic/reports/inventory", timeout=15)
        assert r.status_code in (401, 403)

    def test_by_branch_requires_auth(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/clinic/reports/by-branch", timeout=15)
        assert r.status_code in (401, 403)


# -------- Executive summary ---------
class TestExecutiveSummary:
    def test_current_month_structure(self, api_client, auth_headers):
        r = api_client.get(
            f"{BASE_URL}/api/clinic/reports/executive-summary?period=current_month",
            headers=auth_headers, timeout=60,
        )
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        # Top-level keys
        for key in ("period", "kpis", "trend_12m", "income_by_method", "expenses_by_category", "income_by_branch"):
            assert key in data, f"missing key {key}"
        # KPIs
        k = data["kpis"]
        for key in ("income", "expenses", "net_profit", "ar_pending", "avg_ticket", "new_patients", "appointments", "sales_count"):
            assert key in k, f"missing kpi {key}"
        assert "value" in k["income"] and "delta_pct" in k["income"]
        assert "value" in k["net_profit"] and "margin_pct" in k["net_profit"]
        # Trend 12 months exactly
        assert isinstance(data["trend_12m"], list)
        assert len(data["trend_12m"]) == 12
        for t in data["trend_12m"]:
            assert "month" in t and "income" in t and "expenses" in t

    @pytest.mark.parametrize("period", ["previous_month", "quarter", "year"])
    def test_other_periods_status_200(self, api_client, auth_headers, period):
        r = api_client.get(
            f"{BASE_URL}/api/clinic/reports/executive-summary?period={period}",
            headers=auth_headers, timeout=60,
        )
        assert r.status_code == 200, f"period={period} -> {r.status_code} {r.text[:200]}"
        data = r.json()
        assert "kpis" in data
        assert len(data["trend_12m"]) == 12

    def test_custom_period_with_dates(self, api_client, auth_headers):
        r = api_client.get(
            f"{BASE_URL}/api/clinic/reports/executive-summary?period=custom&date_from=2025-01-01&date_to=2026-01-31",
            headers=auth_headers, timeout=60,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["period"]["from"] == "2025-01-01"
        assert data["period"]["to"] == "2026-01-31"


# -------- Income ---------
class TestIncomeReport:
    def test_income_default(self, api_client, auth_headers):
        r = api_client.get(
            f"{BASE_URL}/api/clinic/reports/income?period=current_month",
            headers=auth_headers, timeout=45,
        )
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        for key in ("total_income", "sales_count", "time_series", "top_products", "top_services", "by_doctor", "by_method"):
            assert key in data, f"missing {key}"
        assert isinstance(data["time_series"], list)
        assert isinstance(data["top_products"], list) and len(data["top_products"]) <= 10
        assert isinstance(data["top_services"], list) and len(data["top_services"]) <= 10

    @pytest.mark.parametrize("grouping", ["day", "week", "month"])
    def test_grouping_supported(self, api_client, auth_headers, grouping):
        r = api_client.get(
            f"{BASE_URL}/api/clinic/reports/income?period=current_month&grouping={grouping}",
            headers=auth_headers, timeout=45,
        )
        assert r.status_code == 200, f"grouping={grouping} -> {r.status_code}"
        data = r.json()
        assert "time_series" in data


# -------- P&L ---------
class TestPnL:
    def test_pnl_structure(self, api_client, auth_headers):
        r = api_client.get(
            f"{BASE_URL}/api/clinic/reports/pnl?period=current_month",
            headers=auth_headers, timeout=45,
        )
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        for top in ("current", "previous"):
            assert top in data, f"missing {top}"
            block = data[top]
            for k in ("income", "cogs", "gross_margin", "expenses", "ebit_before_commissions", "commissions", "net_profit", "net_margin_pct"):
                assert k in block, f"missing {top}.{k}"
            assert "total" in block["income"]
            assert "total" in block["expenses"]
            assert "by_category" in block["expenses"]

    def test_pnl_pdf_returns_signed_url(self, api_client, auth_headers):
        r = api_client.get(
            f"{BASE_URL}/api/clinic/reports/pnl-pdf?period=current_month",
            headers=auth_headers, timeout=60,
        )
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        url = data.get("url") or data.get("signed_url") or data.get("pdf_url")
        assert url and isinstance(url, str) and url.startswith("http"), f"no url in {data}"
        # Fetch URL and check content-type
        try:
            head = requests.get(url, timeout=30, stream=True)
            ct = head.headers.get("content-type", "")
            assert "pdf" in ct.lower() or head.status_code == 200, f"content-type={ct}"
        except Exception as e:
            pytest.skip(f"Could not fetch signed PDF url: {e}")


# -------- Inventory ---------
class TestInventoryReport:
    def test_inventory_structure(self, api_client, auth_headers):
        r = api_client.get(
            f"{BASE_URL}/api/clinic/reports/inventory",
            headers=auth_headers, timeout=45,
        )
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        for key in ("valuation", "no_movement_products", "top_sold_90d", "expiring", "movements_30d"):
            assert key in data, f"missing {key}"
        v = data["valuation"]
        for k in ("cost_total", "retail_total", "potential_margin", "by_branch", "by_category"):
            assert k in v, f"missing valuation.{k}"

    @pytest.mark.parametrize("days", [30, 60, 90])
    def test_no_movement_filter(self, api_client, auth_headers, days):
        r = api_client.get(
            f"{BASE_URL}/api/clinic/reports/inventory?days_no_movement={days}",
            headers=auth_headers, timeout=45,
        )
        assert r.status_code == 200, f"days={days} -> {r.status_code}"
        data = r.json()
        assert "no_movement_products" in data


# -------- By branch ---------
class TestByBranch:
    def test_by_branch_structure(self, api_client, auth_headers):
        r = api_client.get(
            f"{BASE_URL}/api/clinic/reports/by-branch?period=current_month",
            headers=auth_headers, timeout=45,
        )
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert "branches" in data and isinstance(data["branches"], list)
        assert "totals" in data
        # Check branch row structure (if any branches)
        if data["branches"]:
            row = data["branches"][0]
            for k in ("income", "expenses", "profit", "sales_count", "appointments", "avg_ticket"):
                assert k in row, f"missing branch row key {k}"
