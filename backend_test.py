#!/usr/bin/env python3

import requests
import sys
import json
from datetime import datetime

class CRMAPITester:
    def __init__(self, base_url="https://super-admin-panel-12.preview.emergentagent.com/api"):
        self.base_url = base_url
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        test_headers = {'Content-Type': 'application/json'}
        
        if self.token:
            test_headers['Authorization'] = f'Bearer {self.token}'
        
        if headers:
            test_headers.update(headers)

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=test_headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=test_headers, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=test_headers, timeout=10)
            elif method == 'DELETE':
                response = requests.delete(url, headers=test_headers, timeout=10)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return success, response.json() if response.text else {}
                except:
                    return success, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                print(f"   Response: {response.text[:200]}...")
                self.failed_tests.append({
                    "test": name,
                    "expected": expected_status,
                    "actual": response.status_code,
                    "response": response.text[:200]
                })
                try:
                    return False, response.json() if response.text else {}
                except:
                    return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            self.failed_tests.append({
                "test": name,
                "error": str(e)
            })
            return False, {}

    def test_health_check(self):
        """Test basic health endpoint"""
        return self.run_test("Health Check", "GET", "health", 200)

    def test_login(self, email, password):
        """Test login and get token"""
        success, response = self.run_test(
            "Super Admin Login",
            "POST",
            "auth/login",
            200,
            data={"email": email, "password": password}
        )
        if success and 'access_token' in response:
            self.token = response['access_token']
            print(f"   User Type: {response.get('user_type')}")
            print(f"   Email: {response.get('email')}")
            return True, response
        return False, response

    def test_dashboard_stats(self):
        """Test dashboard statistics"""
        return self.run_test("Dashboard Stats", "GET", "admin/dashboard", 200)

    def test_list_clinics(self):
        """Test listing clinics"""
        return self.run_test("List Clinics", "GET", "admin/clinics", 200)

    def test_create_clinic(self):
        """Test creating a clinic"""
        clinic_data = {
            "name": f"Test Clinic {datetime.now().strftime('%H%M%S')}",
            "country": "México",
            "city": "Ciudad de México",
            "address": "Calle Test 123",
            "phone": "+52 55 1234 5678",
            "email": "test@clinic.com",
            "timezone": "America/Mexico_City",
            "plan": "premium",
            "admin_name": "Admin",
            "admin_lastname": "Test",
            "admin_email": f"admin{datetime.now().strftime('%H%M%S')}@test.com",
            "admin_phone": "+52 55 8765 4321",
            "admin_password": "TestPassword123!"
        }
        return self.run_test("Create Clinic", "POST", "admin/clinics", 200, data=clinic_data)

    def test_list_users(self):
        """Test listing users"""
        return self.run_test("List Users", "GET", "admin/users", 200)

    def test_catalog_medications(self):
        """Test medications catalog"""
        return self.run_test("List Medications", "GET", "admin/catalogs/medications", 200)

    def test_catalog_lab_studies(self):
        """Test lab studies catalog"""
        return self.run_test("List Lab Studies", "GET", "admin/catalogs/lab-studies", 200)

    def test_catalog_icd10(self):
        """Test ICD-10 codes catalog"""
        return self.run_test("List ICD-10 Codes", "GET", "admin/catalogs/icd10", 200)

    def test_create_medication(self):
        """Test creating a medication"""
        med_data = {
            "generic_name": f"Test Medicine {datetime.now().strftime('%H%M%S')}",
            "brand_name": "Test Brand",
            "presentations": ["Tableta 500mg", "Jarabe 250mg/5ml"],
            "category": "Analgésico"
        }
        return self.run_test("Create Medication", "POST", "admin/catalogs/medications", 200, data=med_data)

    def test_logout(self):
        """Test logout"""
        return self.run_test("Logout", "POST", "auth/logout", 200)

def main():
    print("🚀 Starting CRM Super Admin API Tests")
    print("=" * 50)
    
    # Setup
    tester = CRMAPITester()
    
    # Test credentials from environment
    super_admin_email = "info@cortexiagt.com"
    super_admin_password = "Armagedon1980$"

    # Run tests in sequence
    print("\n📋 BASIC CONNECTIVITY TESTS")
    print("-" * 30)
    
    # Health check
    tester.test_health_check()

    print("\n🔐 AUTHENTICATION TESTS")
    print("-" * 30)
    
    # Login test
    login_success, login_response = tester.test_login(super_admin_email, super_admin_password)
    if not login_success:
        print("❌ Login failed, stopping tests")
        print(f"📊 Final Results: {tester.tests_passed}/{tester.tests_run} tests passed")
        return 1

    print("\n📊 DASHBOARD TESTS")
    print("-" * 30)
    
    # Dashboard stats
    tester.test_dashboard_stats()

    print("\n🏥 CLINIC MANAGEMENT TESTS")
    print("-" * 30)
    
    # Clinic operations
    tester.test_list_clinics()
    clinic_success, clinic_response = tester.test_create_clinic()

    print("\n👥 USER MANAGEMENT TESTS")
    print("-" * 30)
    
    # User operations
    tester.test_list_users()

    print("\n📚 CATALOG TESTS")
    print("-" * 30)
    
    # Catalog operations
    tester.test_catalog_medications()
    tester.test_catalog_lab_studies()
    tester.test_catalog_icd10()
    tester.test_create_medication()

    print("\n🚪 LOGOUT TESTS")
    print("-" * 30)
    
    # Logout
    tester.test_logout()

    # Print final results
    print("\n" + "=" * 50)
    print(f"📊 FINAL RESULTS: {tester.tests_passed}/{tester.tests_run} tests passed")
    
    if tester.failed_tests:
        print(f"\n❌ FAILED TESTS ({len(tester.failed_tests)}):")
        for i, failure in enumerate(tester.failed_tests, 1):
            print(f"{i}. {failure.get('test', 'Unknown')}")
            if 'error' in failure:
                print(f"   Error: {failure['error']}")
            else:
                print(f"   Expected: {failure.get('expected')}, Got: {failure.get('actual')}")
    
    success_rate = (tester.tests_passed / tester.tests_run) * 100 if tester.tests_run > 0 else 0
    print(f"\n✨ Success Rate: {success_rate:.1f}%")
    
    return 0 if tester.tests_passed == tester.tests_run else 1

if __name__ == "__main__":
    sys.exit(main())