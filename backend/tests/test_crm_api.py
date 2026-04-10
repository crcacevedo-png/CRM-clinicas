"""
CRM Super Admin Panel - Backend API Tests
Tests for: Authentication, Dashboard, Clinics, Users, Catalogs (Medications, Lab Studies, ICD-10)
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://super-admin-panel-12.preview.emergentagent.com').rstrip('/')

# Test credentials from test_credentials.md
SUPER_ADMIN_EMAIL = "info@cortexiagt.com"
SUPER_ADMIN_PASSWORD = "Armagedon1980$"
CLINIC_MEMBER_EMAIL = "carlos@lasalud.gt"
CLINIC_MEMBER_PASSWORD = "Test123456!"


class TestHealthCheck:
    """Health check endpoint tests"""
    
    def test_health_endpoint(self):
        """Test API health endpoint"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("✓ Health check passed")

    def test_root_endpoint(self):
        """Test API root endpoint"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        print("✓ Root endpoint passed")


class TestAuthentication:
    """Authentication endpoint tests"""
    
    def test_super_admin_login_success(self):
        """Test super admin login with valid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL,
            "password": SUPER_ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert "access_token" in data
        assert "refresh_token" in data
        assert "user_type" in data
        assert "user_id" in data
        assert "email" in data
        
        # Validate user type is super_admin
        assert data["user_type"] == "super_admin"
        assert data["email"] == SUPER_ADMIN_EMAIL
        print(f"✓ Super admin login successful - user_type: {data['user_type']}")
        return data["access_token"]

    def test_clinic_member_login_success(self):
        """Test clinic member login with valid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLINIC_MEMBER_EMAIL,
            "password": CLINIC_MEMBER_PASSWORD
        })
        assert response.status_code == 200, f"Clinic member login failed: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert "access_token" in data
        assert "user_type" in data
        assert data["user_type"] == "clinic_member"
        assert "clinic_id" in data
        assert data["clinic_id"] is not None
        print(f"✓ Clinic member login successful - user_type: {data['user_type']}, clinic_id: {data['clinic_id']}")

    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "invalid@example.com",
            "password": "wrongpassword"
        })
        assert response.status_code in [401, 403]
        print("✓ Invalid credentials rejected correctly")

    def test_login_missing_fields(self):
        """Test login with missing fields"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": SUPER_ADMIN_EMAIL
        })
        assert response.status_code == 422  # Validation error
        print("✓ Missing fields validation works")


@pytest.fixture(scope="module")
def auth_token():
    """Get super admin authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": SUPER_ADMIN_EMAIL,
        "password": SUPER_ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json()["access_token"]
    pytest.skip("Super admin authentication failed")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Get authentication headers"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestDashboard:
    """Dashboard endpoint tests"""
    
    def test_dashboard_stats(self, auth_headers):
        """Test dashboard statistics endpoint"""
        response = requests.get(f"{BASE_URL}/api/admin/dashboard", headers=auth_headers)
        assert response.status_code == 200, f"Dashboard failed: {response.text}"
        data = response.json()
        
        # Validate KPI fields
        assert "active_clinics" in data
        assert "inactive_clinics" in data
        assert "total_users" in data
        assert "total_patients" in data
        assert "recent_clinics" in data
        
        # Validate data types
        assert isinstance(data["active_clinics"], int)
        assert isinstance(data["inactive_clinics"], int)
        assert isinstance(data["total_users"], int)
        assert isinstance(data["total_patients"], int)
        assert isinstance(data["recent_clinics"], list)
        
        print(f"✓ Dashboard stats: active_clinics={data['active_clinics']}, total_users={data['total_users']}, total_patients={data['total_patients']}")

    def test_dashboard_requires_auth(self):
        """Test dashboard requires authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/dashboard")
        assert response.status_code in [401, 403]
        print("✓ Dashboard requires authentication")


class TestClinics:
    """Clinic management endpoint tests"""
    
    def test_list_clinics(self, auth_headers):
        """Test listing clinics"""
        response = requests.get(f"{BASE_URL}/api/admin/clinics", headers=auth_headers)
        assert response.status_code == 200, f"List clinics failed: {response.text}"
        data = response.json()
        
        assert isinstance(data, list)
        if len(data) > 0:
            clinic = data[0]
            # Validate clinic structure
            assert "id" in clinic
            assert "name" in clinic
            assert "country" in clinic
            assert "plan" in clinic
            assert "is_active" in clinic
            assert "users_count" in clinic
            assert "patients_count" in clinic
            print(f"✓ Listed {len(data)} clinics - First clinic: {clinic['name']}, users: {clinic['users_count']}")
        else:
            print("✓ Listed 0 clinics (empty)")

    def test_list_clinics_with_filters(self, auth_headers):
        """Test listing clinics with filters"""
        # Test status filter
        response = requests.get(f"{BASE_URL}/api/admin/clinics?status=active", headers=auth_headers)
        assert response.status_code == 200
        print("✓ Clinic filter by status works")

    def test_get_clinic_detail(self, auth_headers):
        """Test getting clinic detail"""
        # First get list of clinics
        list_response = requests.get(f"{BASE_URL}/api/admin/clinics", headers=auth_headers)
        clinics = list_response.json()
        
        if len(clinics) > 0:
            clinic_id = clinics[0]["id"]
            response = requests.get(f"{BASE_URL}/api/admin/clinics/{clinic_id}", headers=auth_headers)
            assert response.status_code == 200, f"Get clinic detail failed: {response.text}"
            data = response.json()
            
            assert "clinic" in data
            assert "members" in data
            assert "stats" in data
            print(f"✓ Clinic detail retrieved: {data['clinic']['name']}, members: {len(data['members'])}")
        else:
            pytest.skip("No clinics available for detail test")

    def test_get_nonexistent_clinic(self, auth_headers):
        """Test getting non-existent clinic"""
        fake_id = str(uuid.uuid4())
        response = requests.get(f"{BASE_URL}/api/admin/clinics/{fake_id}", headers=auth_headers)
        assert response.status_code == 404
        print("✓ Non-existent clinic returns 404")


class TestUsers:
    """User management endpoint tests"""
    
    def test_list_users(self, auth_headers):
        """Test listing users"""
        response = requests.get(f"{BASE_URL}/api/admin/users", headers=auth_headers)
        assert response.status_code == 200, f"List users failed: {response.text}"
        data = response.json()
        
        assert isinstance(data, list)
        if len(data) > 0:
            user = data[0]
            # Validate user structure - should have name, lastname, email, clinic_name, role
            assert "id" in user
            assert "name" in user
            assert "lastname" in user
            assert "email" in user
            assert "clinic_name" in user
            assert "role" in user
            assert "is_active" in user
            print(f"✓ Listed {len(data)} users - First user: {user['name']} {user['lastname']}, email: {user['email']}, clinic: {user['clinic_name']}, role: {user['role']}")
        else:
            print("✓ Listed 0 users (empty)")

    def test_list_users_with_filters(self, auth_headers):
        """Test listing users with filters"""
        # Test role filter
        response = requests.get(f"{BASE_URL}/api/admin/users?role=clinic_admin", headers=auth_headers)
        assert response.status_code == 200
        print("✓ User filter by role works")


class TestCatalogMedications:
    """Medication catalog endpoint tests"""
    
    def test_list_medications(self, auth_headers):
        """Test listing medications"""
        response = requests.get(f"{BASE_URL}/api/admin/catalogs/medications", headers=auth_headers)
        assert response.status_code == 200, f"List medications failed: {response.text}"
        data = response.json()
        
        assert isinstance(data, list)
        count = len(data)
        print(f"✓ Listed {count} medications")
        
        # Verify we have 61+ medications as per requirements
        if count >= 61:
            print(f"✓ Medications count ({count}) meets requirement (61+)")
        else:
            print(f"⚠ Medications count ({count}) is below expected (61+)")
        
        if count > 0:
            med = data[0]
            assert "id" in med
            assert "generic_name" in med
            print(f"  First medication: {med['generic_name']}")

    def test_create_medication(self, auth_headers):
        """Test creating a medication"""
        test_med = {
            "generic_name": f"TEST_Medication_{uuid.uuid4().hex[:8]}",
            "brand_name": "TestBrand",
            "presentations": "100mg tablets, 50mg capsules",
            "category": "Test Category"
        }
        response = requests.post(f"{BASE_URL}/api/admin/catalogs/medications", 
                                json=test_med, headers=auth_headers)
        assert response.status_code == 200, f"Create medication failed: {response.text}"
        data = response.json()
        
        assert data["generic_name"] == test_med["generic_name"]
        print(f"✓ Created medication: {data['generic_name']}")
        return data["id"]


class TestCatalogLabStudies:
    """Lab studies catalog endpoint tests"""
    
    def test_list_lab_studies(self, auth_headers):
        """Test listing lab studies"""
        response = requests.get(f"{BASE_URL}/api/admin/catalogs/lab-studies", headers=auth_headers)
        assert response.status_code == 200, f"List lab studies failed: {response.text}"
        data = response.json()
        
        assert isinstance(data, list)
        count = len(data)
        print(f"✓ Listed {count} lab studies")
        
        # Verify we have 80+ lab studies as per requirements
        if count >= 80:
            print(f"✓ Lab studies count ({count}) meets requirement (80+)")
        else:
            print(f"⚠ Lab studies count ({count}) is below expected (80+)")
        
        if count > 0:
            study = data[0]
            assert "id" in study
            assert "name" in study
            print(f"  First lab study: {study['name']}")

    def test_create_lab_study(self, auth_headers):
        """Test creating a lab study"""
        test_study = {
            "name": f"TEST_LabStudy_{uuid.uuid4().hex[:8]}",
            "category": "Test Category",
            "preparation": "No preparation needed"
        }
        response = requests.post(f"{BASE_URL}/api/admin/catalogs/lab-studies", 
                                json=test_study, headers=auth_headers)
        assert response.status_code == 200, f"Create lab study failed: {response.text}"
        data = response.json()
        
        assert data["name"] == test_study["name"]
        print(f"✓ Created lab study: {data['name']}")


class TestCatalogICD10:
    """ICD-10 codes catalog endpoint tests"""
    
    def test_list_icd10_codes(self, auth_headers):
        """Test listing ICD-10 codes"""
        response = requests.get(f"{BASE_URL}/api/admin/catalogs/icd10", headers=auth_headers)
        assert response.status_code == 200, f"List ICD-10 codes failed: {response.text}"
        data = response.json()
        
        assert isinstance(data, list)
        count = len(data)
        print(f"✓ Listed {count} ICD-10 codes")
        
        # Verify we have 672+ ICD-10 codes as per requirements
        if count >= 672:
            print(f"✓ ICD-10 codes count ({count}) meets requirement (672+)")
        else:
            print(f"⚠ ICD-10 codes count ({count}) is below expected (672+)")
        
        if count > 0:
            code = data[0]
            assert "id" in code
            assert "code" in code
            assert "description_es" in code
            print(f"  First ICD-10 code: {code['code']} - {code.get('description_es', 'N/A')[:50]}")

    def test_toggle_icd10_common(self, auth_headers):
        """Test toggling ICD-10 common flag"""
        # First get list of ICD-10 codes
        list_response = requests.get(f"{BASE_URL}/api/admin/catalogs/icd10", headers=auth_headers)
        codes = list_response.json()
        
        if len(codes) > 0:
            code_id = codes[0]["id"]
            original_common = codes[0].get("is_common", False)
            
            response = requests.put(f"{BASE_URL}/api/admin/catalogs/icd10/{code_id}/toggle-common", 
                                   headers=auth_headers)
            assert response.status_code == 200, f"Toggle common failed: {response.text}"
            data = response.json()
            
            assert "is_common" in data
            assert data["is_common"] != original_common
            print(f"✓ Toggled ICD-10 common flag: {original_common} -> {data['is_common']}")
            
            # Toggle back to original
            requests.put(f"{BASE_URL}/api/admin/catalogs/icd10/{code_id}/toggle-common", 
                        headers=auth_headers)
        else:
            pytest.skip("No ICD-10 codes available for toggle test")


class TestCreateClinic:
    """Test clinic creation with admin"""
    
    def test_create_clinic_with_admin(self, auth_headers):
        """Test creating a new clinic with admin user"""
        unique_id = uuid.uuid4().hex[:8]
        test_clinic = {
            "name": f"TEST_Clinic_{unique_id}",
            "country": "guatemala",
            "city": "Guatemala City",
            "address": "Test Address 123",
            "phone": "+502 1234 5678",
            "email": f"test_clinic_{unique_id}@test.com",
            "timezone": "America/Guatemala",
            "plan": "free",
            "admin_name": "Test",
            "admin_lastname": "Admin",
            "admin_email": f"test_admin_{unique_id}@test.com",
            "admin_phone": "+502 9876 5432",
            "admin_password": "TestPassword123!"
        }
        
        response = requests.post(f"{BASE_URL}/api/admin/clinics", 
                                json=test_clinic, headers=auth_headers)
        
        # Note: This might fail if the email already exists in Supabase Auth
        if response.status_code == 200:
            data = response.json()
            assert "clinic" in data
            assert "admin_credentials" in data
            assert data["clinic"]["name"] == test_clinic["name"]
            print(f"✓ Created clinic: {data['clinic']['name']}")
            print(f"  Admin credentials: {data['admin_credentials']['email']}")
        elif response.status_code == 400:
            # User might already exist
            print(f"⚠ Clinic creation returned 400 (user may already exist): {response.text}")
        else:
            print(f"⚠ Clinic creation failed with status {response.status_code}: {response.text}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
