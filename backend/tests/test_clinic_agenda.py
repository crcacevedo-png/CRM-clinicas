"""
Test suite for Clinic Agenda Module
Tests: Login, Dashboard, Appointments CRUD, Patients, Filters, Status changes
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
CLINIC_ADMIN_EMAIL = "carlos@lasalud.gt"
CLINIC_ADMIN_PASSWORD = "Test123456!"
CLINIC_ID = "c0321ed8-97da-47a1-b601-3b94bffabdd7"
DOCTOR_ID = "199d2ea1-e2ff-4595-be1a-de07cc2f807d"  # Carlos Lopez
EXISTING_PATIENT_ID = "dffcbc90-407b-4e3a-b032-b831b20b524b"  # Maria Garcia


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for clinic member"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": CLINIC_ADMIN_EMAIL,
        "password": CLINIC_ADMIN_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    assert data["user_type"] == "clinic_member", "Expected clinic_member user type"
    assert data.get("clinic_id") == CLINIC_ID, f"Expected clinic_id {CLINIC_ID}"
    return data["access_token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Auth headers for authenticated requests"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestClinicLogin:
    """Test clinic member login and redirect"""
    
    def test_clinic_member_login_success(self):
        """Login as clinic member returns correct user_type and clinic_id"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLINIC_ADMIN_EMAIL,
            "password": CLINIC_ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert data["user_type"] == "clinic_member"
        assert data["clinic_id"] == CLINIC_ID
        assert "access_token" in data
        print(f"✓ Clinic member login successful, clinic_id: {data['clinic_id']}")
    
    def test_invalid_credentials(self):
        """Invalid credentials return 401"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "wrong@email.com",
            "password": "wrongpassword"
        })
        assert response.status_code == 401


class TestClinicConfig:
    """Test clinic configuration endpoint"""
    
    def test_get_clinic_config(self, auth_headers):
        """Get clinic config returns schedule and doctors"""
        response = requests.get(f"{BASE_URL}/api/clinic/config", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Verify clinic data
        assert "clinic" in data
        clinic = data["clinic"]
        assert clinic["schedule_start"] == "08:00:00"
        assert clinic["schedule_end"] == "17:00:00"
        assert clinic["slot_duration"] == 30
        assert clinic["working_days"] == [1, 2, 3, 4, 5]
        
        # Verify doctors list
        assert "doctors" in data
        assert len(data["doctors"]) > 0
        print(f"✓ Clinic config: schedule {clinic['schedule_start']}-{clinic['schedule_end']}, {len(data['doctors'])} doctors")
    
    def test_config_returns_current_member(self, auth_headers):
        """Config includes current member info"""
        response = requests.get(f"{BASE_URL}/api/clinic/config", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "current_member" in data
        assert data["current_member"]["clinic_id"] == CLINIC_ID


class TestClinicDashboard:
    """Test clinic dashboard KPIs"""
    
    def test_dashboard_returns_kpis(self, auth_headers):
        """Dashboard returns today_count, total_patients, month_appointments"""
        response = requests.get(f"{BASE_URL}/api/clinic/dashboard", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "today_count" in data
        assert "total_patients" in data
        assert "month_appointments" in data
        assert "today_appointments" in data
        assert isinstance(data["today_appointments"], list)
        print(f"✓ Dashboard KPIs: today={data['today_count']}, patients={data['total_patients']}, month={data['month_appointments']}")
    
    def test_dashboard_appointments_enriched(self, auth_headers):
        """Today's appointments include patient_name and doctor_name"""
        response = requests.get(f"{BASE_URL}/api/clinic/dashboard", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        if data["today_appointments"]:
            apt = data["today_appointments"][0]
            assert "patient_name" in apt
            assert "doctor_name" in apt
            assert "status" in apt
            print(f"✓ Today's appointment: {apt['patient_name']} at {apt.get('starts_at', 'N/A')}")


class TestPatients:
    """Test patient search and creation"""
    
    def test_search_patients(self, auth_headers):
        """Search patients returns results"""
        response = requests.get(f"{BASE_URL}/api/clinic/patients/search?q=Maria", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should find Maria Garcia
        maria = next((p for p in data if "Maria" in p.get("first_name", "")), None)
        if maria:
            assert maria["id"] == EXISTING_PATIENT_ID
            print(f"✓ Found patient: {maria['first_name']} {maria['last_name']}")
    
    def test_list_patients(self, auth_headers):
        """List all patients for clinic"""
        response = requests.get(f"{BASE_URL}/api/clinic/patients", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} patients")
    
    def test_create_patient(self, auth_headers):
        """Create new patient"""
        patient_data = {
            "first_name": "TEST_Juan",
            "last_name": "TEST_Perez",
            "phone": "55551234",
            "email": "test_juan@test.com"
        }
        response = requests.post(f"{BASE_URL}/api/clinic/patients", json=patient_data, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["first_name"] == "TEST_Juan"
        print(f"✓ Created patient: {data['first_name']} {data['last_name']} (id: {data['id']})")
        return data["id"]


class TestAppointments:
    """Test appointments CRUD and status changes"""
    
    def test_list_appointments(self, auth_headers):
        """List appointments for current week"""
        today = datetime.now()
        start = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%dT00:00:00")
        end = (today + timedelta(days=6-today.weekday())).strftime("%Y-%m-%dT23:59:59")
        
        response = requests.get(
            f"{BASE_URL}/api/clinic/appointments?start_date={start}&end_date={end}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Listed {len(data)} appointments for current week")
        
        # Check if Maria Garcia's appointment exists
        maria_apt = next((a for a in data if "Maria" in a.get("patient_name", "")), None)
        if maria_apt:
            print(f"  Found Maria Garcia's appointment: {maria_apt['starts_at']} - status: {maria_apt['status']}")
    
    def test_filter_by_doctor(self, auth_headers):
        """Filter appointments by doctor"""
        response = requests.get(
            f"{BASE_URL}/api/clinic/appointments?doctor_id={DOCTOR_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        # All appointments should be for the specified doctor
        for apt in data:
            assert apt["doctor_id"] == DOCTOR_ID
        print(f"✓ Filtered {len(data)} appointments for doctor {DOCTOR_ID}")
    
    def test_filter_by_status(self, auth_headers):
        """Filter appointments by status"""
        response = requests.get(
            f"{BASE_URL}/api/clinic/appointments?status=scheduled",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        for apt in data:
            assert apt["status"] == "scheduled"
        print(f"✓ Filtered {len(data)} scheduled appointments")
    
    def test_create_appointment_success(self, auth_headers):
        """Create new appointment within clinic hours"""
        # Tomorrow at 10:00 AM
        tomorrow = datetime.now() + timedelta(days=1)
        # Make sure it's a weekday (Mon-Fri)
        while tomorrow.weekday() >= 5:  # Saturday or Sunday
            tomorrow += timedelta(days=1)
        
        starts_at = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0).isoformat()
        
        apt_data = {
            "patient_id": EXISTING_PATIENT_ID,
            "doctor_id": DOCTOR_ID,
            "starts_at": starts_at,
            "duration_minutes": 30,
            "reason": "TEST_Consulta general",
            "notes": "Test appointment"
        }
        
        response = requests.post(f"{BASE_URL}/api/clinic/appointments", json=apt_data, headers=auth_headers)
        assert response.status_code == 200, f"Create appointment failed: {response.text}"
        data = response.json()
        
        assert "id" in data
        assert data["patient_id"] == EXISTING_PATIENT_ID
        assert data["doctor_id"] == DOCTOR_ID
        assert data["status"] == "scheduled"
        assert "patient_name" in data
        assert "doctor_name" in data
        print(f"✓ Created appointment: {data['patient_name']} with {data['doctor_name']} at {starts_at}")
        return data["id"]
    
    def test_create_appointment_outside_hours_fails(self, auth_headers):
        """Creating appointment outside clinic hours (8:00-17:00) should fail"""
        tomorrow = datetime.now() + timedelta(days=1)
        while tomorrow.weekday() >= 5:
            tomorrow += timedelta(days=1)
        
        # 7:00 AM - before clinic opens
        starts_at = tomorrow.replace(hour=7, minute=0, second=0, microsecond=0).isoformat()
        
        apt_data = {
            "patient_id": EXISTING_PATIENT_ID,
            "doctor_id": DOCTOR_ID,
            "starts_at": starts_at,
            "duration_minutes": 30,
            "reason": "TEST_Early appointment"
        }
        
        response = requests.post(f"{BASE_URL}/api/clinic/appointments", json=apt_data, headers=auth_headers)
        assert response.status_code == 400, f"Expected 400 for outside hours, got {response.status_code}"
        print(f"✓ Correctly rejected appointment at 7:00 AM (outside clinic hours)")
    
    def test_create_appointment_conflict_fails(self, auth_headers):
        """Creating overlapping appointment should fail (double booking)"""
        # First create an appointment
        tomorrow = datetime.now() + timedelta(days=2)
        while tomorrow.weekday() >= 5:
            tomorrow += timedelta(days=1)
        
        starts_at = tomorrow.replace(hour=11, minute=0, second=0, microsecond=0).isoformat()
        
        apt_data = {
            "patient_id": EXISTING_PATIENT_ID,
            "doctor_id": DOCTOR_ID,
            "starts_at": starts_at,
            "duration_minutes": 30,
            "reason": "TEST_First appointment"
        }
        
        # Create first appointment
        response1 = requests.post(f"{BASE_URL}/api/clinic/appointments", json=apt_data, headers=auth_headers)
        assert response1.status_code == 200, f"First appointment failed: {response1.text}"
        
        # Try to create overlapping appointment
        apt_data["reason"] = "TEST_Conflicting appointment"
        response2 = requests.post(f"{BASE_URL}/api/clinic/appointments", json=apt_data, headers=auth_headers)
        assert response2.status_code == 409, f"Expected 409 for conflict, got {response2.status_code}"
        print(f"✓ Correctly rejected double booking at {starts_at}")


class TestAppointmentStatus:
    """Test appointment status changes"""
    
    @pytest.fixture
    def test_appointment(self, auth_headers):
        """Create a test appointment for status tests"""
        tomorrow = datetime.now() + timedelta(days=3)
        while tomorrow.weekday() >= 5:
            tomorrow += timedelta(days=1)
        
        starts_at = tomorrow.replace(hour=14, minute=0, second=0, microsecond=0).isoformat()
        
        apt_data = {
            "patient_id": EXISTING_PATIENT_ID,
            "doctor_id": DOCTOR_ID,
            "starts_at": starts_at,
            "duration_minutes": 30,
            "reason": "TEST_Status test"
        }
        
        response = requests.post(f"{BASE_URL}/api/clinic/appointments", json=apt_data, headers=auth_headers)
        assert response.status_code == 200
        return response.json()["id"]
    
    def test_confirm_appointment(self, auth_headers, test_appointment):
        """Confirm a scheduled appointment"""
        response = requests.put(
            f"{BASE_URL}/api/clinic/appointments/{test_appointment}/status",
            json={"status": "confirmed"},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "confirmed"
        print(f"✓ Confirmed appointment {test_appointment}")
    
    def test_start_appointment(self, auth_headers, test_appointment):
        """Start an appointment (in_progress)"""
        # First confirm
        requests.put(
            f"{BASE_URL}/api/clinic/appointments/{test_appointment}/status",
            json={"status": "confirmed"},
            headers=auth_headers
        )
        
        # Then start
        response = requests.put(
            f"{BASE_URL}/api/clinic/appointments/{test_appointment}/status",
            json={"status": "in_progress"},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "in_progress"
        print(f"✓ Started appointment {test_appointment}")
    
    def test_complete_appointment(self, auth_headers, test_appointment):
        """Complete an appointment"""
        # First start
        requests.put(
            f"{BASE_URL}/api/clinic/appointments/{test_appointment}/status",
            json={"status": "in_progress"},
            headers=auth_headers
        )
        
        # Then complete
        response = requests.put(
            f"{BASE_URL}/api/clinic/appointments/{test_appointment}/status",
            json={"status": "completed"},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        print(f"✓ Completed appointment {test_appointment}")
    
    def test_cancel_appointment_with_reason(self, auth_headers):
        """Cancel appointment with reason"""
        # Create new appointment for cancellation
        tomorrow = datetime.now() + timedelta(days=4)
        while tomorrow.weekday() >= 5:
            tomorrow += timedelta(days=1)
        
        starts_at = tomorrow.replace(hour=15, minute=0, second=0, microsecond=0).isoformat()
        
        apt_data = {
            "patient_id": EXISTING_PATIENT_ID,
            "doctor_id": DOCTOR_ID,
            "starts_at": starts_at,
            "duration_minutes": 30,
            "reason": "TEST_Cancel test"
        }
        
        response = requests.post(f"{BASE_URL}/api/clinic/appointments", json=apt_data, headers=auth_headers)
        apt_id = response.json()["id"]
        
        # Cancel with reason
        response = requests.put(
            f"{BASE_URL}/api/clinic/appointments/{apt_id}/status",
            json={"status": "cancelled", "cancellation_reason": "Patient requested cancellation"},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"
        print(f"✓ Cancelled appointment {apt_id} with reason")
    
    def test_invalid_status_fails(self, auth_headers, test_appointment):
        """Invalid status value should fail"""
        response = requests.put(
            f"{BASE_URL}/api/clinic/appointments/{test_appointment}/status",
            json={"status": "invalid_status"},
            headers=auth_headers
        )
        assert response.status_code == 400
        print(f"✓ Correctly rejected invalid status")


class TestAppointmentUpdate:
    """Test appointment update"""
    
    def test_update_appointment(self, auth_headers):
        """Update appointment details"""
        # Create appointment
        tomorrow = datetime.now() + timedelta(days=5)
        while tomorrow.weekday() >= 5:
            tomorrow += timedelta(days=1)
        
        starts_at = tomorrow.replace(hour=9, minute=0, second=0, microsecond=0).isoformat()
        
        apt_data = {
            "patient_id": EXISTING_PATIENT_ID,
            "doctor_id": DOCTOR_ID,
            "starts_at": starts_at,
            "duration_minutes": 30,
            "reason": "TEST_Original reason"
        }
        
        response = requests.post(f"{BASE_URL}/api/clinic/appointments", json=apt_data, headers=auth_headers)
        apt_id = response.json()["id"]
        
        # Update
        update_data = {
            "reason": "TEST_Updated reason",
            "notes": "Updated notes",
            "duration_minutes": 45
        }
        
        response = requests.put(f"{BASE_URL}/api/clinic/appointments/{apt_id}", json=update_data, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["reason"] == "TEST_Updated reason"
        assert data["notes"] == "Updated notes"
        assert data["duration_minutes"] == 45
        print(f"✓ Updated appointment {apt_id}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
