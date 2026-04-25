"""
Feature Flags and Plans System Tests
Tests for:
- GET /api/clinic/features - Get active features for clinic user
- GET /api/admin/plans - List all plans
- GET /api/admin/features - List all features
- GET /api/admin/plans/{plan_id}/features - Get features for a plan
- PUT /api/admin/plans/{plan_id}/features - Set features for a plan
- GET /api/admin/clinics/{clinic_id}/features - Get clinic features with overrides
- PUT /api/admin/clinics/{clinic_id}/features/{feature_id} - Toggle feature override
- PUT /api/admin/clinics/{clinic_id}/plan - Change clinic plan
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
SUPER_ADMIN_EMAIL = "info@cortexiagt.com"
SUPER_ADMIN_PASSWORD = "Armagedon1980$"
CLINIC_ADMIN_EMAIL = "carlos@lasalud.gt"
CLINIC_ADMIN_PASSWORD = "Test123456!"
CLINIC_ID = "c0321ed8-97da-47a1-b601-3b94bffabdd7"


@pytest.fixture(scope="module")
def super_admin_token():
    """Get super admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": SUPER_ADMIN_EMAIL,
        "password": SUPER_ADMIN_PASSWORD
    })
    assert response.status_code == 200, f"Super admin login failed: {response.text}"
    data = response.json()
    assert "access_token" in data
    return data["access_token"]


@pytest.fixture(scope="module")
def clinic_admin_token():
    """Get clinic admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": CLINIC_ADMIN_EMAIL,
        "password": CLINIC_ADMIN_PASSWORD
    })
    assert response.status_code == 200, f"Clinic admin login failed: {response.text}"
    data = response.json()
    assert "access_token" in data
    return data["access_token"]


@pytest.fixture
def super_admin_headers(super_admin_token):
    return {"Authorization": f"Bearer {super_admin_token}", "Content-Type": "application/json"}


@pytest.fixture
def clinic_admin_headers(clinic_admin_token):
    return {"Authorization": f"Bearer {clinic_admin_token}", "Content-Type": "application/json"}


class TestClinicFeatures:
    """Tests for clinic user feature access"""

    def test_get_clinic_features_returns_200(self, clinic_admin_headers):
        """GET /api/clinic/features should return 200 for clinic user"""
        response = requests.get(f"{BASE_URL}/api/clinic/features", headers=clinic_admin_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    def test_get_clinic_features_returns_features_array(self, clinic_admin_headers):
        """Response should contain features array"""
        response = requests.get(f"{BASE_URL}/api/clinic/features", headers=clinic_admin_headers)
        data = response.json()
        assert "features" in data, "Response should have 'features' key"
        assert isinstance(data["features"], list), "Features should be a list"

    def test_get_clinic_features_returns_plan_code(self, clinic_admin_headers):
        """Response should contain plan code"""
        response = requests.get(f"{BASE_URL}/api/clinic/features", headers=clinic_admin_headers)
        data = response.json()
        assert "plan" in data, "Response should have 'plan' key"
        assert data["plan"] in ["basic", "professional", "enterprise", "free", "premium"], f"Unexpected plan: {data['plan']}"

    def test_clinic_has_professional_plan(self, clinic_admin_headers):
        """Clinica la salud should have professional plan"""
        response = requests.get(f"{BASE_URL}/api/clinic/features", headers=clinic_admin_headers)
        data = response.json()
        assert data["plan"] == "professional", f"Expected 'professional', got '{data['plan']}'"

    def test_clinic_has_expected_features(self, clinic_admin_headers):
        """Professional plan should include expected features"""
        response = requests.get(f"{BASE_URL}/api/clinic/features", headers=clinic_admin_headers)
        data = response.json()
        features = data["features"]
        # Professional plan should have these core features
        expected_features = ["agenda", "patients", "prescriptions", "lab_orders"]
        for feat in expected_features:
            assert feat in features, f"Expected feature '{feat}' not found in {features}"


class TestAdminPlans:
    """Tests for admin plans management"""

    def test_list_plans_returns_200(self, super_admin_headers):
        """GET /api/admin/plans should return 200"""
        response = requests.get(f"{BASE_URL}/api/admin/plans", headers=super_admin_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    def test_list_plans_returns_array(self, super_admin_headers):
        """Response should be an array of plans"""
        response = requests.get(f"{BASE_URL}/api/admin/plans", headers=super_admin_headers)
        data = response.json()
        assert isinstance(data, list), "Response should be a list"

    def test_list_plans_has_three_plans(self, super_admin_headers):
        """Should have at least 3 plans (Basic, Professional, Enterprise)"""
        response = requests.get(f"{BASE_URL}/api/admin/plans", headers=super_admin_headers)
        data = response.json()
        assert len(data) >= 3, f"Expected at least 3 plans, got {len(data)}"

    def test_plans_have_required_fields(self, super_admin_headers):
        """Each plan should have required fields"""
        response = requests.get(f"{BASE_URL}/api/admin/plans", headers=super_admin_headers)
        data = response.json()
        required_fields = ["id", "code", "name", "price_monthly", "price_yearly", "max_users", "max_patients", "max_storage_mb"]
        for plan in data:
            for field in required_fields:
                assert field in plan, f"Plan missing field '{field}': {plan}"

    def test_basic_plan_exists(self, super_admin_headers):
        """Basic plan should exist with correct price"""
        response = requests.get(f"{BASE_URL}/api/admin/plans", headers=super_admin_headers)
        data = response.json()
        basic = next((p for p in data if p["code"] == "basic"), None)
        assert basic is not None, "Basic plan not found"
        assert basic["price_monthly"] == 29, f"Basic price should be 29, got {basic['price_monthly']}"

    def test_professional_plan_exists(self, super_admin_headers):
        """Professional plan should exist with correct price"""
        response = requests.get(f"{BASE_URL}/api/admin/plans", headers=super_admin_headers)
        data = response.json()
        professional = next((p for p in data if p["code"] == "professional"), None)
        assert professional is not None, "Professional plan not found"
        assert professional["price_monthly"] == 79, f"Professional price should be 79, got {professional['price_monthly']}"

    def test_enterprise_plan_exists(self, super_admin_headers):
        """Enterprise plan should exist with correct price"""
        response = requests.get(f"{BASE_URL}/api/admin/plans", headers=super_admin_headers)
        data = response.json()
        enterprise = next((p for p in data if p["code"] == "enterprise"), None)
        assert enterprise is not None, "Enterprise plan not found"
        assert enterprise["price_monthly"] == 199, f"Enterprise price should be 199, got {enterprise['price_monthly']}"


class TestAdminFeatures:
    """Tests for admin features management"""

    def test_list_features_returns_200(self, super_admin_headers):
        """GET /api/admin/features should return 200"""
        response = requests.get(f"{BASE_URL}/api/admin/features", headers=super_admin_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    def test_list_features_returns_array(self, super_admin_headers):
        """Response should be an array of features"""
        response = requests.get(f"{BASE_URL}/api/admin/features", headers=super_admin_headers)
        data = response.json()
        assert isinstance(data, list), "Response should be a list"

    def test_features_have_required_fields(self, super_admin_headers):
        """Each feature should have required fields"""
        response = requests.get(f"{BASE_URL}/api/admin/features", headers=super_admin_headers)
        data = response.json()
        required_fields = ["id", "code", "name", "category"]
        for feature in data:
            for field in required_fields:
                assert field in feature, f"Feature missing field '{field}': {feature}"

    def test_expected_features_exist(self, super_admin_headers):
        """Expected feature codes should exist"""
        response = requests.get(f"{BASE_URL}/api/admin/features", headers=super_admin_headers)
        data = response.json()
        codes = [f["code"] for f in data]
        expected_codes = ["agenda", "patients", "prescriptions", "lab_orders", "inventory", "sales", "expenses", "financial_reports"]
        for code in expected_codes:
            assert code in codes, f"Expected feature code '{code}' not found"


class TestPlanFeatures:
    """Tests for plan-feature associations"""

    def test_get_plan_features_returns_200(self, super_admin_headers):
        """GET /api/admin/plans/{plan_id}/features should return 200"""
        # First get a plan ID
        plans_response = requests.get(f"{BASE_URL}/api/admin/plans", headers=super_admin_headers)
        plans = plans_response.json()
        if plans:
            plan_id = plans[0]["id"]
            response = requests.get(f"{BASE_URL}/api/admin/plans/{plan_id}/features", headers=super_admin_headers)
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    def test_get_plan_features_returns_array(self, super_admin_headers):
        """Response should be an array of feature IDs"""
        plans_response = requests.get(f"{BASE_URL}/api/admin/plans", headers=super_admin_headers)
        plans = plans_response.json()
        if plans:
            plan_id = plans[0]["id"]
            response = requests.get(f"{BASE_URL}/api/admin/plans/{plan_id}/features", headers=super_admin_headers)
            data = response.json()
            assert isinstance(data, list), "Response should be a list"


class TestClinicFeaturesAdmin:
    """Tests for admin clinic feature management"""

    def test_get_clinic_features_admin_returns_200(self, super_admin_headers):
        """GET /api/admin/clinics/{clinic_id}/features should return 200"""
        response = requests.get(f"{BASE_URL}/api/admin/clinics/{CLINIC_ID}/features", headers=super_admin_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    def test_get_clinic_features_admin_has_features(self, super_admin_headers):
        """Response should have features array"""
        response = requests.get(f"{BASE_URL}/api/admin/clinics/{CLINIC_ID}/features", headers=super_admin_headers)
        data = response.json()
        assert "features" in data, "Response should have 'features' key"
        assert isinstance(data["features"], list), "Features should be a list"

    def test_get_clinic_features_admin_has_plan(self, super_admin_headers):
        """Response should have plan code"""
        response = requests.get(f"{BASE_URL}/api/admin/clinics/{CLINIC_ID}/features", headers=super_admin_headers)
        data = response.json()
        assert "plan" in data, "Response should have 'plan' key"

    def test_clinic_features_have_in_plan_flag(self, super_admin_headers):
        """Each feature should have in_plan flag"""
        response = requests.get(f"{BASE_URL}/api/admin/clinics/{CLINIC_ID}/features", headers=super_admin_headers)
        data = response.json()
        for feature in data["features"]:
            assert "in_plan" in feature, f"Feature missing 'in_plan' flag: {feature}"

    def test_clinic_features_have_override_field(self, super_admin_headers):
        """Each feature should have override field"""
        response = requests.get(f"{BASE_URL}/api/admin/clinics/{CLINIC_ID}/features", headers=super_admin_headers)
        data = response.json()
        for feature in data["features"]:
            assert "override" in feature, f"Feature missing 'override' field: {feature}"


class TestChangePlan:
    """Tests for changing clinic plan"""

    def test_change_plan_returns_200(self, super_admin_headers):
        """PUT /api/admin/clinics/{clinic_id}/plan should return 200"""
        # Change to professional (same as current to avoid side effects)
        response = requests.put(
            f"{BASE_URL}/api/admin/clinics/{CLINIC_ID}/plan",
            json={"plan": "professional"},
            headers=super_admin_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    def test_change_plan_requires_plan_field(self, super_admin_headers):
        """Should return 400 if plan field is missing"""
        response = requests.put(
            f"{BASE_URL}/api/admin/clinics/{CLINIC_ID}/plan",
            json={},
            headers=super_admin_headers
        )
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"

    def test_change_plan_validates_plan_code(self, super_admin_headers):
        """Should return 404 for invalid plan code"""
        response = requests.put(
            f"{BASE_URL}/api/admin/clinics/{CLINIC_ID}/plan",
            json={"plan": "invalid_plan_code"},
            headers=super_admin_headers
        )
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"


class TestAuthRequired:
    """Tests for authentication requirements"""

    def test_clinic_features_requires_auth(self):
        """GET /api/clinic/features should require auth"""
        response = requests.get(f"{BASE_URL}/api/clinic/features")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"

    def test_admin_plans_requires_super_admin(self, clinic_admin_headers):
        """GET /api/admin/plans should require super admin"""
        response = requests.get(f"{BASE_URL}/api/admin/plans", headers=clinic_admin_headers)
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"

    def test_admin_features_requires_super_admin(self, clinic_admin_headers):
        """GET /api/admin/features should require super admin"""
        response = requests.get(f"{BASE_URL}/api/admin/features", headers=clinic_admin_headers)
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
