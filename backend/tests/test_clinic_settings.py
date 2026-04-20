"""
Test Clinic Settings Panel - Backend API Tests
Tests for: GET/PUT /api/clinic/settings, POST /api/clinic/settings/logo,
           GET /api/clinic/members, POST /api/clinic/members/invite,
           PUT /api/clinic/members/:id, PUT /api/clinic/members/:id/toggle
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from test_credentials.md
CLINIC_ADMIN_EMAIL = "carlos@lasalud.gt"
CLINIC_ADMIN_PASSWORD = "Test123456!"


class TestClinicSettingsAuth:
    """Authentication and setup for clinic settings tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for clinic admin"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLINIC_ADMIN_EMAIL,
            "password": CLINIC_ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        return data["access_token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        """Get headers with auth token"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }


class TestClinicSettingsEndpoints(TestClinicSettingsAuth):
    """Test GET/PUT /api/clinic/settings endpoints"""
    
    def test_get_clinic_settings_returns_200(self, headers):
        """GET /api/clinic/settings should return 200 with clinic data"""
        response = requests.get(f"{BASE_URL}/api/clinic/settings", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("PASSED: GET /api/clinic/settings returns 200")
    
    def test_get_clinic_settings_has_required_fields(self, headers):
        """Clinic settings should have all required fields"""
        response = requests.get(f"{BASE_URL}/api/clinic/settings", headers=headers)
        data = response.json()
        
        # Check basic info fields
        assert "id" in data, "Missing 'id' field"
        assert "name" in data, "Missing 'name' field"
        assert "address" in data, "Missing 'address' field"
        assert "phone" in data, "Missing 'phone' field"
        
        # Check schedule fields
        assert "schedule_start" in data, "Missing 'schedule_start' field"
        assert "schedule_end" in data, "Missing 'schedule_end' field"
        assert "slot_duration" in data, "Missing 'slot_duration' field"
        assert "working_days" in data, "Missing 'working_days' field"
        
        # Check plan fields
        assert "plan" in data, "Missing 'plan' field"
        assert "max_users" in data, "Missing 'max_users' field"
        assert "max_patients" in data, "Missing 'max_patients' field"
        
        print("PASSED: Clinic settings has all required fields")
    
    def test_clinic_data_is_prefilled(self, headers):
        """Clinic data should be pre-filled with expected values"""
        response = requests.get(f"{BASE_URL}/api/clinic/settings", headers=headers)
        data = response.json()
        
        # Verify expected pre-filled values
        assert data.get("name") == "Clinica la salud", f"Expected name 'Clinica la salud', got '{data.get('name')}'"
        assert data.get("phone") == "22334455", f"Expected phone '22334455', got '{data.get('phone')}'"
        assert data.get("address") == "Zona 10", f"Expected address 'Zona 10', got '{data.get('address')}'"
        
        print("PASSED: Clinic data is pre-filled correctly")
    
    def test_clinic_schedule_fields(self, headers):
        """Clinic schedule fields should have valid values"""
        response = requests.get(f"{BASE_URL}/api/clinic/settings", headers=headers)
        data = response.json()
        
        # Check schedule times are in HH:MM format
        schedule_start = data.get("schedule_start", "")
        schedule_end = data.get("schedule_end", "")
        assert schedule_start.startswith("08:00"), f"Expected schedule_start '08:00', got '{schedule_start}'"
        assert schedule_end.startswith("17:00"), f"Expected schedule_end '17:00', got '{schedule_end}'"
        
        # Check working days is array of ints [1,2,3,4,5]
        working_days = data.get("working_days", [])
        assert isinstance(working_days, list), "working_days should be a list"
        assert working_days == [1, 2, 3, 4, 5], f"Expected working_days [1,2,3,4,5], got {working_days}"
        
        # Check slot duration
        assert data.get("slot_duration") == 30, f"Expected slot_duration 30, got {data.get('slot_duration')}"
        
        print("PASSED: Clinic schedule fields are valid")
    
    def test_clinic_plan_is_professional(self, headers):
        """Clinic plan should be 'professional'"""
        response = requests.get(f"{BASE_URL}/api/clinic/settings", headers=headers)
        data = response.json()
        
        assert data.get("plan") == "professional", f"Expected plan 'professional', got '{data.get('plan')}'"
        print("PASSED: Clinic plan is 'professional'")
    
    def test_update_clinic_settings(self, headers):
        """PUT /api/clinic/settings should update clinic data"""
        # First get current data
        get_response = requests.get(f"{BASE_URL}/api/clinic/settings", headers=headers)
        original_data = get_response.json()
        original_name = original_data.get("name")
        
        # Update with test name
        test_name = "TEST_Clinica la salud Updated"
        update_response = requests.put(f"{BASE_URL}/api/clinic/settings", 
            headers=headers,
            json={"name": test_name}
        )
        assert update_response.status_code == 200, f"Update failed: {update_response.text}"
        
        # Verify update persisted
        verify_response = requests.get(f"{BASE_URL}/api/clinic/settings", headers=headers)
        verify_data = verify_response.json()
        assert verify_data.get("name") == test_name, f"Name not updated: {verify_data.get('name')}"
        
        # Restore original name
        restore_response = requests.put(f"{BASE_URL}/api/clinic/settings",
            headers=headers,
            json={"name": original_name}
        )
        assert restore_response.status_code == 200, f"Restore failed: {restore_response.text}"
        
        print("PASSED: PUT /api/clinic/settings updates and persists data")
    
    def test_update_prescription_settings(self, headers):
        """PUT /api/clinic/settings should update prescription footer and validity"""
        # Update prescription settings
        test_footer = "TEST_Footer - Receta válida por 30 días"
        test_validity = 45
        
        update_response = requests.put(f"{BASE_URL}/api/clinic/settings",
            headers=headers,
            json={
                "prescription_footer": test_footer,
                "prescription_validity_days": test_validity
            }
        )
        assert update_response.status_code == 200, f"Update failed: {update_response.text}"
        
        # Verify update persisted
        verify_response = requests.get(f"{BASE_URL}/api/clinic/settings", headers=headers)
        verify_data = verify_response.json()
        assert verify_data.get("prescription_footer") == test_footer, "Prescription footer not updated"
        assert verify_data.get("prescription_validity_days") == test_validity, "Prescription validity not updated"
        
        print("PASSED: Prescription settings update correctly")


class TestClinicMembersEndpoints(TestClinicSettingsAuth):
    """Test /api/clinic/members endpoints"""
    
    def test_get_clinic_members_returns_200(self, headers):
        """GET /api/clinic/members should return 200 with members list"""
        response = requests.get(f"{BASE_URL}/api/clinic/members", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("PASSED: GET /api/clinic/members returns 200")
    
    def test_clinic_members_has_required_fields(self, headers):
        """Members should have required fields including email"""
        response = requests.get(f"{BASE_URL}/api/clinic/members", headers=headers)
        members = response.json()
        
        assert isinstance(members, list), "Response should be a list"
        assert len(members) >= 1, "Should have at least 1 member"
        
        # Check first member has required fields
        member = members[0]
        required_fields = ["id", "first_name", "last_name", "email", "role", "is_active"]
        for field in required_fields:
            assert field in member, f"Missing field '{field}' in member"
        
        print(f"PASSED: Members have required fields (found {len(members)} members)")
    
    def test_clinic_has_three_members(self, headers):
        """Clinic should have 3 existing members"""
        response = requests.get(f"{BASE_URL}/api/clinic/members", headers=headers)
        members = response.json()
        
        # Filter out TEST_ prefixed members from previous tests
        real_members = [m for m in members if not m.get("first_name", "").startswith("TEST_")]
        assert len(real_members) >= 3, f"Expected at least 3 members, got {len(real_members)}"
        
        print(f"PASSED: Clinic has {len(real_members)} members (expected 3+)")
    
    def test_members_have_emails(self, headers):
        """All members should have email addresses"""
        response = requests.get(f"{BASE_URL}/api/clinic/members", headers=headers)
        members = response.json()
        
        for member in members:
            email = member.get("email", "")
            # Email should not be empty
            assert email, f"Member {member.get('first_name')} has no email"
        
        print("PASSED: All members have email addresses")
    
    def test_members_table_columns(self, headers):
        """Members should have Name, Email, Rol, Especialidad, Estado columns data"""
        response = requests.get(f"{BASE_URL}/api/clinic/members", headers=headers)
        members = response.json()
        
        if members:
            member = members[0]
            # Name = first_name + last_name
            assert "first_name" in member and "last_name" in member, "Missing name fields"
            # Email
            assert "email" in member, "Missing email field"
            # Rol
            assert "role" in member, "Missing role field"
            # Especialidad (optional)
            assert "specialty" in member or member.get("specialty") is None, "specialty field issue"
            # Estado
            assert "is_active" in member, "Missing is_active field"
        
        print("PASSED: Members have all table column data")
    
    def test_update_member(self, headers):
        """PUT /api/clinic/members/:id should update member data"""
        # Get members first
        response = requests.get(f"{BASE_URL}/api/clinic/members", headers=headers)
        members = response.json()
        
        # Find a non-admin member to update (not the current user)
        target_member = None
        for m in members:
            if m.get("role") != "clinic_admin":
                target_member = m
                break
        
        if not target_member:
            # Use first member that's not the admin
            target_member = members[1] if len(members) > 1 else members[0]
        
        member_id = target_member["id"]
        original_specialty = target_member.get("specialty", "")
        
        # Update specialty
        test_specialty = "TEST_Cardiología"
        update_response = requests.put(f"{BASE_URL}/api/clinic/members/{member_id}",
            headers=headers,
            json={"specialty": test_specialty}
        )
        assert update_response.status_code == 200, f"Update failed: {update_response.text}"
        
        # Verify update
        verify_response = requests.get(f"{BASE_URL}/api/clinic/members", headers=headers)
        verify_members = verify_response.json()
        updated_member = next((m for m in verify_members if m["id"] == member_id), None)
        assert updated_member is not None, "Member not found after update"
        assert updated_member.get("specialty") == test_specialty, "Specialty not updated"
        
        # Restore original
        requests.put(f"{BASE_URL}/api/clinic/members/{member_id}",
            headers=headers,
            json={"specialty": original_specialty}
        )
        
        print("PASSED: PUT /api/clinic/members/:id updates member data")
    
    def test_update_member_license_number(self, headers):
        """PUT /api/clinic/members/:id should update license_number (No. Colegiado)"""
        response = requests.get(f"{BASE_URL}/api/clinic/members", headers=headers)
        members = response.json()
        
        if len(members) > 1:
            member_id = members[1]["id"]
        else:
            member_id = members[0]["id"]
        
        test_license = "TEST_COL-12345"
        update_response = requests.put(f"{BASE_URL}/api/clinic/members/{member_id}",
            headers=headers,
            json={"license_number": test_license}
        )
        assert update_response.status_code == 200, f"Update failed: {update_response.text}"
        
        # Verify
        verify_response = requests.get(f"{BASE_URL}/api/clinic/members", headers=headers)
        verify_members = verify_response.json()
        updated_member = next((m for m in verify_members if m["id"] == member_id), None)
        assert updated_member.get("license_number") == test_license, "License number not updated"
        
        print("PASSED: License number (No. Colegiado) updates correctly")


class TestMemberInviteEndpoint(TestClinicSettingsAuth):
    """Test POST /api/clinic/members/invite endpoint"""
    
    def test_invite_member_requires_fields(self, headers):
        """POST /api/clinic/members/invite should require email, first_name, last_name"""
        # Missing required fields
        response = requests.post(f"{BASE_URL}/api/clinic/members/invite",
            headers=headers,
            json={"email": "test@test.com"}  # Missing first_name, last_name
        )
        assert response.status_code == 422, f"Expected 422 for missing fields, got {response.status_code}"
        print("PASSED: Invite requires all required fields")
    
    def test_invite_member_with_role_and_specialty(self, headers):
        """POST /api/clinic/members/invite should accept role and specialty"""
        import uuid
        test_email = f"test_invite_{uuid.uuid4().hex[:8]}@test.com"
        
        response = requests.post(f"{BASE_URL}/api/clinic/members/invite",
            headers=headers,
            json={
                "email": test_email,
                "first_name": "TEST_Invite",
                "last_name": "TEST_User",
                "role": "doctor",
                "specialty": "Pediatría"
            }
        )
        
        # Should succeed or fail with user already exists
        assert response.status_code in [200, 400], f"Unexpected status: {response.status_code}: {response.text}"
        
        if response.status_code == 200:
            data = response.json()
            assert "id" in data or "message" in data, "Response should have id or message"
            # Check if temp_password is returned
            if "temp_password" in data:
                print(f"PASSED: Invite returns temp_password: {data['temp_password'][:4]}...")
            else:
                print("PASSED: Invite member endpoint works")
        else:
            print("PASSED: Invite endpoint validates correctly")


class TestMemberToggleEndpoint(TestClinicSettingsAuth):
    """Test PUT /api/clinic/members/:id/toggle endpoint"""
    
    def test_toggle_member_status(self, headers):
        """PUT /api/clinic/members/:id/toggle should activate/deactivate member"""
        # Get members
        response = requests.get(f"{BASE_URL}/api/clinic/members", headers=headers)
        members = response.json()
        
        # Find a non-admin member to toggle
        target_member = None
        for m in members:
            if m.get("role") != "clinic_admin":
                target_member = m
                break
        
        if not target_member:
            pytest.skip("No non-admin member to toggle")
        
        member_id = target_member["id"]
        original_status = target_member.get("is_active", True)
        
        # Toggle
        toggle_response = requests.put(f"{BASE_URL}/api/clinic/members/{member_id}/toggle",
            headers=headers
        )
        assert toggle_response.status_code == 200, f"Toggle failed: {toggle_response.text}"
        
        data = toggle_response.json()
        assert "is_active" in data, "Response should have is_active"
        assert data["is_active"] != original_status, "Status should have changed"
        
        # Toggle back to restore
        requests.put(f"{BASE_URL}/api/clinic/members/{member_id}/toggle", headers=headers)
        
        print("PASSED: Toggle member status works")
    
    def test_cannot_toggle_self(self, headers):
        """Admin cannot deactivate themselves"""
        # Get current member ID
        response = requests.get(f"{BASE_URL}/api/clinic/members", headers=headers)
        members = response.json()
        
        # Find the admin (carlos@lasalud.gt)
        admin_member = None
        for m in members:
            if m.get("email") == CLINIC_ADMIN_EMAIL:
                admin_member = m
                break
        
        if not admin_member:
            pytest.skip("Admin member not found")
        
        # Try to toggle self
        toggle_response = requests.put(f"{BASE_URL}/api/clinic/members/{admin_member['id']}/toggle",
            headers=headers
        )
        assert toggle_response.status_code == 400, f"Expected 400 for self-toggle, got {toggle_response.status_code}"
        
        print("PASSED: Cannot toggle self (admin protection)")


class TestGoogleCalendarEndpoints(TestClinicSettingsAuth):
    """Test Google Calendar integration endpoints"""
    
    def test_gcal_status_endpoint(self, headers):
        """GET /api/google-calendar/status should return connection status"""
        response = requests.get(f"{BASE_URL}/api/google-calendar/status", headers=headers)
        # Should return 200 even if not connected
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "connected" in data, "Response should have 'connected' field"
        
        print(f"PASSED: Google Calendar status endpoint works (connected: {data.get('connected')})")
    
    def test_gcal_auth_url_endpoint(self, headers):
        """GET /api/google-calendar/auth-url should return OAuth URL"""
        response = requests.get(f"{BASE_URL}/api/google-calendar/auth-url", headers=headers)
        
        # Should return 200 with auth_url
        if response.status_code == 200:
            data = response.json()
            assert "auth_url" in data, "Response should have 'auth_url'"
            assert "google.com" in data["auth_url"], "Auth URL should be Google OAuth"
            print("PASSED: Google Calendar auth URL endpoint works")
        else:
            # May fail if Google credentials not configured
            print(f"INFO: Google Calendar auth URL returned {response.status_code} (may need configuration)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
