"""PROMPT A9: Role-aware /api/clinic/dashboard with admin_stats, alerts, income_chart."""
import os
import pytest
import requests
from datetime import date

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')
CLINIC_EMAIL = "carlos@lasalud.gt"
CLINIC_PASS = "Test123456!"


@pytest.fixture(scope="module")
def clinic_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": CLINIC_EMAIL, "password": CLINIC_PASS}, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def ch(clinic_token):
    return {"Authorization": f"Bearer {clinic_token}"}


@pytest.fixture(scope="module")
def dash(ch):
    r = requests.get(f"{BASE_URL}/api/clinic/dashboard", headers=ch, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


# ----- Schema / new fields -----
class TestDashboardSchema:
    def test_status_200(self, dash):
        assert isinstance(dash, dict)

    def test_new_fields_present(self, dash):
        for key in ("role", "features", "admin_stats", "alerts", "income_chart", "my_commissions_month"):
            assert key in dash, f"missing field {key}"

    def test_legacy_fields_preserved(self, dash):
        for key in ("today_appointments", "today_count", "pending_today",
                    "new_patients_month", "rx_issued_month", "next_appointment",
                    "recent_patients", "activity", "current_member"):
            assert key in dash, f"legacy field {key} missing"

    def test_role_is_clinic_admin(self, dash):
        assert dash["role"] == "clinic_admin"

    def test_features_is_list(self, dash):
        assert isinstance(dash["features"], list)
        # carlos has all features active including financial_reports
        for f in ("sales", "inventory", "expenses", "commissions", "financial_reports"):
            assert f in dash["features"], f"feature {f} missing for test clinic"


# ----- admin_stats for clinic_admin -----
class TestAdminStats:
    def test_admin_stats_shape(self, dash):
        s = dash["admin_stats"]
        assert isinstance(s, dict)
        # All expected keys for clinic_admin with full features
        expected = [
            "sales_today_amount", "sales_today_count",
            "ar_pending_amount",
            "low_stock_count", "expiring_count",
            "expenses_month",
            "commissions_month", "commissions_pending",
            "open_cash_sessions",
        ]
        for k in expected:
            assert k in s, f"admin_stats missing {k}"

    def test_admin_stats_numeric(self, dash):
        s = dash["admin_stats"]
        for k in ("sales_today_amount", "ar_pending_amount", "expenses_month",
                  "commissions_month", "commissions_pending"):
            assert isinstance(s[k], (int, float)), f"{k} not numeric: {s[k]!r}"
        for k in ("sales_today_count", "low_stock_count", "expiring_count", "open_cash_sessions"):
            assert isinstance(s[k], int), f"{k} not int"

    def test_admin_stats_non_negative(self, dash):
        s = dash["admin_stats"]
        for k, v in s.items():
            assert v >= 0, f"{k} should be >=0, got {v}"


# ----- alerts -----
class TestAlerts:
    def test_alerts_is_list(self, dash):
        assert isinstance(dash["alerts"], list)

    def test_alert_item_shape(self, dash):
        for a in dash["alerts"]:
            for k in ("type", "severity", "message", "link", "count"):
                assert k in a, f"alert missing {k}: {a}"
            assert a["severity"] in ("info", "warning", "danger")
            assert isinstance(a["count"], int)


# ----- income chart -----
class TestIncomeChart:
    def test_income_chart_present(self, dash):
        assert isinstance(dash["income_chart"], list)
        # financial_reports + sales => populated
        assert len(dash["income_chart"]) > 0, "income_chart empty for clinic_admin with FR+sales"

    def test_income_chart_item_shape(self, dash):
        for p in dash["income_chart"]:
            assert "date" in p and "income" in p
            # ISO YYYY-MM-DD
            assert len(p["date"]) == 10 and p["date"][4] == '-'
            assert isinstance(p["income"], (int, float))
            assert p["income"] >= 0

    def test_income_chart_starts_at_month_start_and_includes_today(self, dash):
        today = date.today()
        first = date(today.year, today.month, 1).isoformat()
        last = today.isoformat()
        dates = [p["date"] for p in dash["income_chart"]]
        assert dates[0] == first, f"first day should be {first}, got {dates[0]}"
        assert dates[-1] == last, f"last day should be {last}, got {dates[-1]}"
        # dates strictly ascending and contiguous
        assert len(dates) == (today.day)


# ----- doctor commission field is None for admin -----
class TestMyCommissions:
    def test_my_commissions_none_for_admin(self, dash):
        # for clinic_admin, this field should be None (only doctor populates)
        assert dash["my_commissions_month"] is None


# ----- regression: legacy contract still valid -----
class TestRegression:
    def test_today_appointments_is_list(self, dash):
        assert isinstance(dash["today_appointments"], list)

    def test_today_count_matches_list(self, dash):
        assert dash["today_count"] == len(dash["today_appointments"])

    def test_recent_patients_list(self, dash):
        assert isinstance(dash["recent_patients"], list)

    def test_activity_list_for_admin(self, dash):
        # non-doctor must include activity
        assert isinstance(dash["activity"], list)

    def test_current_member_has_role(self, dash):
        m = dash["current_member"]
        assert m and m.get("role") == "clinic_admin"
