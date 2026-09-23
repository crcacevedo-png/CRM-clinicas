"""
Medical Records Module Backend Tests
Tests for: ICD10 search, medical record CRUD, addendum functionality
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://super-admin-panel-12.preview.emergentagent.com').rstrip('/')

# Test credentials
CLINIC_ADMIN_EMAIL = "carlos@lasalud.gt"
CLINIC_ADMIN_PASSWORD = "Test123456!"

# Test patient IDs
PATIENT_ID_MARIA = "dffcbc90-407b-4e3a-b032-b831b20b524b"
PATIENT_ID_PEDRO = "3af0efd4-8c74-4de0-bb62-f174fa2af673"


class TestMedicalRecordsAPI:
    """Medical Records API tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as clinic admin
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLINIC_ADMIN_EMAIL,
            "password": CLINIC_ADMIN_PASSWORD
        })
        
        if login_response.status_code != 200:
            pytest.skip(f"Login failed: {login_response.status_code} - {login_response.text}")
        
        data = login_response.json()
        self.token = data.get("access_token") or data.get("token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        self.created_record_id = None
        yield
        
        # Cleanup - delete test record if created
        if self.created_record_id:
            try:
                # Note: No delete endpoint exists, so we leave draft records
                pass
            except Exception:
                pass
    
    # ============== ICD10 SEARCH TESTS ==============
    
    def test_icd10_search_common_codes(self):
        """Test ICD10 search returns common codes when query is short"""
        response = self.session.get(f"{BASE_URL}/api/clinic/icd10/search?q=a")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list response"
        # Should return common codes when query < 2 chars
        print(f"ICD10 common codes returned: {len(data)} codes")
    
    def test_icd10_search_diabetes(self):
        """Test ICD10 search for 'diabetes' returns relevant results"""
        response = self.session.get(f"{BASE_URL}/api/clinic/icd10/search?q=diabetes&limit=15")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list response"
        
        if len(data) > 0:
            # Verify structure of ICD10 result
            first_result = data[0]
            assert "code" in first_result, "ICD10 result should have 'code'"
            assert "description_es" in first_result, "ICD10 result should have 'description_es'"
            print(f"ICD10 search 'diabetes' returned {len(data)} results")
            print(f"First result: {first_result.get('code')} - {first_result.get('description_es')}")
        else:
            print("Warning: No ICD10 results for 'diabetes' - may need to seed ICD10 codes")
    
    def test_icd10_search_by_code(self):
        """Test ICD10 search by code (e.g., E11)"""
        response = self.session.get(f"{BASE_URL}/api/clinic/icd10/search?q=E11")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list response"
        print(f"ICD10 search 'E11' returned {len(data)} results")
    
    # ============== MEDICAL RECORD CRUD TESTS ==============
    
    def test_create_medical_record_draft(self):
        """Test creating a draft medical record"""
        payload = {
            "patient_id": PATIENT_ID_MARIA,
            "chief_complaint": "TEST_Dolor de cabeza persistente",
            "present_illness": "Paciente refiere cefalea de 3 días de evolución",
            "blood_pressure_systolic": 120,
            "blood_pressure_diastolic": 80,
            "heart_rate": 72,
            "respiratory_rate": 16,
            "temperature": 36.5,
            "oxygen_saturation": 98,
            "weight_kg": 70,
            "height_cm": 170,
            "bmi": 24.2,
            "diagnoses": [
                {"code": "R51", "description": "Cefalea", "type": "primary"}
            ],
            "treatment_plan": "Paracetamol 500mg cada 8 horas",
            "notes": "Seguimiento en 1 semana",
            "status": "draft"
        }
        
        response = self.session.post(f"{BASE_URL}/api/clinic/medical-records", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "id" in data, "Response should contain record ID"
        self.created_record_id = data["id"]
        print(f"Created draft medical record: {self.created_record_id}")
    
    def test_create_medical_record_with_out_of_range_vitals(self):
        """Test creating a record with out-of-range vital signs"""
        payload = {
            "patient_id": PATIENT_ID_MARIA,
            "chief_complaint": "TEST_Fiebre alta",
            "temperature": 39.5,  # Out of range (> 38.0)
            "blood_pressure_systolic": 190,  # Out of range (> 180)
            "heart_rate": 130,  # Out of range (> 120)
            "oxygen_saturation": 88,  # Out of range (< 92)
            "status": "draft"
        }
        
        response = self.session.post(f"{BASE_URL}/api/clinic/medical-records", json=payload)
        # Should still create - validation is frontend-side for alerts
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "id" in data
        print(f"Created record with out-of-range vitals: {data['id']}")
    
    def test_list_patient_medical_records(self):
        """Test listing medical records for a patient"""
        response = self.session.get(f"{BASE_URL}/api/clinic/patients/{PATIENT_ID_MARIA}/medical-records")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Expected list response"
        print(f"Patient {PATIENT_ID_MARIA} has {len(data)} medical records")
        
        if len(data) > 0:
            record = data[0]
            assert "id" in record
            assert "status" in record
            assert "doctor_name" in record
            print(f"First record: {record.get('id')} - Status: {record.get('status')} - Doctor: {record.get('doctor_name')}")
    
    def test_list_medical_records_with_filters(self):
        """Test listing medical records with doctor and date filters"""
        # Test with date filter
        response = self.session.get(
            f"{BASE_URL}/api/clinic/patients/{PATIENT_ID_MARIA}/medical-records?date_from=2024-01-01&date_to=2026-12-31"
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list)
        print(f"Filtered records (date range): {len(data)} records")
    
    def test_get_single_medical_record(self):
        """Test getting a single medical record by ID"""
        # First create a record
        create_payload = {
            "patient_id": PATIENT_ID_MARIA,
            "chief_complaint": "TEST_Consulta de control",
            "status": "draft"
        }
        create_response = self.session.post(f"{BASE_URL}/api/clinic/medical-records", json=create_payload)
        assert create_response.status_code == 200
        record_id = create_response.json()["id"]
        
        # Now get it
        response = self.session.get(f"{BASE_URL}/api/clinic/medical-records/{record_id}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["id"] == record_id
        assert data["chief_complaint"] == "TEST_Consulta de control"
        assert "doctor_name" in data
        assert "patient_name" in data
        print(f"Retrieved record: {record_id} - Patient: {data.get('patient_name')}")
    
    def test_update_draft_medical_record(self):
        """Test updating a draft medical record"""
        # First create a draft
        create_payload = {
            "patient_id": PATIENT_ID_MARIA,
            "chief_complaint": "TEST_Original complaint",
            "status": "draft"
        }
        create_response = self.session.post(f"{BASE_URL}/api/clinic/medical-records", json=create_payload)
        assert create_response.status_code == 200
        record_id = create_response.json()["id"]
        
        # Update it
        update_payload = {
            "patient_id": PATIENT_ID_MARIA,
            "chief_complaint": "TEST_Updated complaint",
            "treatment_plan": "New treatment plan",
            "status": "draft"
        }
        response = self.session.put(f"{BASE_URL}/api/clinic/medical-records/{record_id}", json=update_payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify update
        get_response = self.session.get(f"{BASE_URL}/api/clinic/medical-records/{record_id}")
        assert get_response.status_code == 200
        data = get_response.json()
        assert data["chief_complaint"] == "TEST_Updated complaint"
        assert data["treatment_plan"] == "New treatment plan"
        print(f"Updated record {record_id} successfully")
    
    def test_finalize_medical_record(self):
        """Test finalizing a medical record"""
        # Create a draft with required fields for finalization
        create_payload = {
            "patient_id": PATIENT_ID_MARIA,
            "chief_complaint": "TEST_Consulta para finalizar",
            "diagnoses": [{"code": "J00", "description": "Resfriado común", "type": "primary"}],
            "status": "draft"
        }
        create_response = self.session.post(f"{BASE_URL}/api/clinic/medical-records", json=create_payload)
        assert create_response.status_code == 200
        record_id = create_response.json()["id"]
        
        # Finalize via update with status=finalized
        finalize_payload = {
            "patient_id": PATIENT_ID_MARIA,
            "chief_complaint": "TEST_Consulta para finalizar",
            "diagnoses": [{"code": "J00", "description": "Resfriado común", "type": "primary"}],
            "status": "finalized"
        }
        response = self.session.put(f"{BASE_URL}/api/clinic/medical-records/{record_id}", json=finalize_payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify finalized
        get_response = self.session.get(f"{BASE_URL}/api/clinic/medical-records/{record_id}")
        data = get_response.json()
        assert data["status"] == "finalized"
        assert "finalized_at" in data
        print(f"Finalized record {record_id} successfully")
        
        return record_id  # Return for addendum test
    
    def test_cannot_edit_finalized_record(self):
        """Test that finalized records cannot be edited"""
        # Create and finalize a record
        create_payload = {
            "patient_id": PATIENT_ID_MARIA,
            "chief_complaint": "TEST_No editar",
            "diagnoses": [{"code": "J00", "description": "Test", "type": "primary"}],
            "status": "finalized"
        }
        create_response = self.session.post(f"{BASE_URL}/api/clinic/medical-records", json=create_payload)
        assert create_response.status_code == 200
        record_id = create_response.json()["id"]
        
        # Try to update - should fail
        update_payload = {
            "patient_id": PATIENT_ID_MARIA,
            "chief_complaint": "TEST_Trying to edit",
            "status": "draft"
        }
        response = self.session.put(f"{BASE_URL}/api/clinic/medical-records/{record_id}", json=update_payload)
        assert response.status_code == 400, f"Expected 400 for editing finalized record, got {response.status_code}"
        print(f"Correctly prevented editing finalized record {record_id}")
    
    # ============== ADDENDUM TESTS ==============
    
    def test_add_addendum_to_finalized_record(self):
        """Test adding an addendum to a finalized record"""
        # Create and finalize a record
        create_payload = {
            "patient_id": PATIENT_ID_MARIA,
            "chief_complaint": "TEST_Record for addendum",
            "diagnoses": [{"code": "J00", "description": "Test", "type": "primary"}],
            "status": "finalized"
        }
        create_response = self.session.post(f"{BASE_URL}/api/clinic/medical-records", json=create_payload)
        assert create_response.status_code == 200
        record_id = create_response.json()["id"]
        
        # Add addendum
        addendum_payload = {"text": "TEST_Addendum: Paciente reporta mejoría"}
        response = self.session.post(f"{BASE_URL}/api/clinic/medical-records/{record_id}/addendum", json=addendum_payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Verify addendum was added
        get_response = self.session.get(f"{BASE_URL}/api/clinic/medical-records/{record_id}")
        data = get_response.json()
        assert "addenda" in data
        assert len(data["addenda"]) > 0
        assert data["addenda"][-1]["text"] == "TEST_Addendum: Paciente reporta mejoría"
        assert "doctor_name" in data["addenda"][-1]
        assert "created_at" in data["addenda"][-1]
        print(f"Added addendum to record {record_id} successfully")
    
    def test_add_multiple_addenda(self):
        """Test adding multiple addenda to a record"""
        # Create and finalize a record
        create_payload = {
            "patient_id": PATIENT_ID_MARIA,
            "chief_complaint": "TEST_Multiple addenda",
            "diagnoses": [{"code": "J00", "description": "Test", "type": "primary"}],
            "status": "finalized"
        }
        create_response = self.session.post(f"{BASE_URL}/api/clinic/medical-records", json=create_payload)
        record_id = create_response.json()["id"]
        
        # Add first addendum
        self.session.post(f"{BASE_URL}/api/clinic/medical-records/{record_id}/addendum", 
                         json={"text": "TEST_First addendum"})
        
        # Add second addendum
        self.session.post(f"{BASE_URL}/api/clinic/medical-records/{record_id}/addendum", 
                         json={"text": "TEST_Second addendum"})
        
        # Verify both addenda
        get_response = self.session.get(f"{BASE_URL}/api/clinic/medical-records/{record_id}")
        data = get_response.json()
        assert len(data["addenda"]) >= 2
        print(f"Record {record_id} has {len(data['addenda'])} addenda")
    
    # ============== ERROR HANDLING TESTS ==============
    
    def test_create_record_invalid_patient(self):
        """Test creating a record for non-existent patient"""
        payload = {
            "patient_id": "00000000-0000-0000-0000-000000000000",
            "chief_complaint": "TEST_Invalid patient",
            "status": "draft"
        }
        response = self.session.post(f"{BASE_URL}/api/clinic/medical-records", json=payload)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("Correctly returned 404 for invalid patient")
    
    def test_get_nonexistent_record(self):
        """Test getting a non-existent record"""
        response = self.session.get(f"{BASE_URL}/api/clinic/medical-records/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("Correctly returned 404 for non-existent record")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
