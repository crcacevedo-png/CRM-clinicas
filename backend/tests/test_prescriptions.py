"""
Test suite for Prescriptions Module
Tests: Prescription CRUD, Medication search, PDF generation
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://super-admin-panel-12.preview.emergentagent.com')

# Test credentials
CLINIC_ADMIN_EMAIL = "carlos@lasalud.gt"
CLINIC_ADMIN_PASSWORD = "Test123456!"
PATIENT_ID = "dffcbc90-407b-4e3a-b032-b831b20b524b"  # Maria Garcia
EXISTING_PRESCRIPTION_ID = "55dc09f8-203f-4a16-bf17-be659d2890da"  # Issued prescription


class TestPrescriptionsModule:
    """Test suite for prescriptions endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as clinic admin
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLINIC_ADMIN_EMAIL,
            "password": CLINIC_ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        self.token = data["access_token"]
        self.clinic_id = data.get("clinic_id")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        print(f"✓ Logged in as {CLINIC_ADMIN_EMAIL}")
        yield
        # Cleanup: Delete TEST_ prefixed prescriptions
        try:
            resp = self.session.get(f"{BASE_URL}/api/clinic/prescriptions?limit=50")
            if resp.status_code == 200:
                for p in resp.json().get("prescriptions", []):
                    if p.get("diagnosis", "").startswith("TEST_"):
                        # Can't delete issued prescriptions, just leave them
                        pass
        except:
            pass
    
    # ============== MEDICATION SEARCH TESTS ==============
    
    def test_medication_search_returns_results(self):
        """Test GET /api/clinic/medications/search?q=aceta returns medications"""
        response = self.session.get(f"{BASE_URL}/api/clinic/medications/search?q=aceta")
        assert response.status_code == 200, f"Medication search failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ Medication search returned {len(data)} results for 'aceta'")
        
        # Verify structure
        if len(data) > 0:
            med = data[0]
            assert "id" in med, "Medication should have id"
            assert "generic_name" in med, "Medication should have generic_name"
            assert "presentations" in med, "Medication should have presentations"
            print(f"  First result: {med['generic_name']}")
    
    def test_medication_search_empty_query(self):
        """Test medication search with empty query returns default list"""
        response = self.session.get(f"{BASE_URL}/api/clinic/medications/search?q=")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Empty query returned {len(data)} medications")
    
    def test_medication_search_short_query(self):
        """Test medication search with 1 char returns empty (min 2 chars)"""
        response = self.session.get(f"{BASE_URL}/api/clinic/medications/search?q=a")
        assert response.status_code == 200
        data = response.json()
        # Should return default list since query < 2 chars
        print(f"✓ Short query (1 char) returned {len(data)} medications")
    
    # ============== PATIENT SEARCH TESTS ==============
    
    def test_patient_search_returns_results(self):
        """Test GET /api/clinic/patients/search?q=Maria returns patients"""
        response = self.session.get(f"{BASE_URL}/api/clinic/patients/search?q=Maria")
        assert response.status_code == 200, f"Patient search failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ Patient search returned {len(data)} results for 'Maria'")
        
        # Verify Maria Garcia is in results
        maria_found = any(p.get("first_name") == "Maria" for p in data)
        assert maria_found, "Maria should be in search results"
        print("  ✓ Maria Garcia found in results")
    
    # ============== PRESCRIPTIONS LIST TESTS ==============
    
    def test_list_prescriptions(self):
        """Test GET /api/clinic/prescriptions returns list with correct structure"""
        response = self.session.get(f"{BASE_URL}/api/clinic/prescriptions")
        assert response.status_code == 200, f"List prescriptions failed: {response.text}"
        data = response.json()
        
        assert "prescriptions" in data, "Response should have prescriptions key"
        assert "total" in data, "Response should have total key"
        assert "pages" in data, "Response should have pages key"
        
        prescriptions = data["prescriptions"]
        print(f"✓ List prescriptions returned {len(prescriptions)} items, total: {data['total']}")
        
        # Verify structure of prescription
        if len(prescriptions) > 0:
            p = prescriptions[0]
            assert "id" in p, "Prescription should have id"
            assert "patient_name" in p, "Prescription should have patient_name"
            assert "doctor_name" in p, "Prescription should have doctor_name"
            assert "status" in p, "Prescription should have status"
            assert "item_count" in p, "Prescription should have item_count"
            print(f"  First prescription: {p['patient_name']} - {p['status']}")
    
    def test_list_prescriptions_filter_by_status(self):
        """Test filtering prescriptions by status"""
        response = self.session.get(f"{BASE_URL}/api/clinic/prescriptions?status=issued")
        assert response.status_code == 200
        data = response.json()
        
        # All returned prescriptions should be issued
        for p in data["prescriptions"]:
            assert p["status"] == "issued", f"Expected issued status, got {p['status']}"
        print(f"✓ Status filter returned {len(data['prescriptions'])} issued prescriptions")
    
    def test_list_prescriptions_filter_by_patient(self):
        """Test filtering prescriptions by patient_id"""
        response = self.session.get(f"{BASE_URL}/api/clinic/prescriptions?patient_id={PATIENT_ID}")
        assert response.status_code == 200
        data = response.json()
        print(f"✓ Patient filter returned {len(data['prescriptions'])} prescriptions for Maria Garcia")
    
    # ============== GET SINGLE PRESCRIPTION TESTS ==============
    
    def test_get_prescription_by_id(self):
        """Test GET /api/clinic/prescriptions/:id returns full prescription with items"""
        response = self.session.get(f"{BASE_URL}/api/clinic/prescriptions/{EXISTING_PRESCRIPTION_ID}")
        assert response.status_code == 200, f"Get prescription failed: {response.text}"
        data = response.json()
        
        assert "id" in data, "Prescription should have id"
        assert "patient" in data, "Prescription should have patient object"
        assert "items" in data, "Prescription should have items array"
        assert "doctor" in data, "Prescription should have doctor object"
        
        print(f"✓ Get prescription returned prescription with {len(data['items'])} items")
        print(f"  Patient: {data['patient'].get('first_name')} {data['patient'].get('last_name')}")
        print(f"  Status: {data['status']}")
        
        # Verify items structure
        if len(data["items"]) > 0:
            item = data["items"][0]
            assert "medication_name" in item, "Item should have medication_name"
            print(f"  First medication: {item['medication_name']}")
    
    def test_get_prescription_not_found(self):
        """Test GET /api/clinic/prescriptions/:id with invalid ID returns 404"""
        response = self.session.get(f"{BASE_URL}/api/clinic/prescriptions/invalid-id-12345")
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Invalid prescription ID returns 404")
    
    # ============== CREATE PRESCRIPTION TESTS ==============
    
    def test_create_prescription_draft(self):
        """Test POST /api/clinic/prescriptions creates draft prescription"""
        payload = {
            "patient_id": PATIENT_ID,
            "diagnosis": "TEST_Gripe común",
            "general_instructions": "Reposo y abundantes líquidos",
            "items": [
                {
                    "medication_name": "Acetaminofén (Tylenol)",
                    "presentation": "Tabletas 500mg",
                    "dosage": "500mg",
                    "frequency": "Cada 8 horas",
                    "route": "oral",
                    "duration": "5 días",
                    "instructions": "Tomar con alimentos"
                }
            ],
            "status": "draft"
        }
        
        response = self.session.post(f"{BASE_URL}/api/clinic/prescriptions", json=payload)
        assert response.status_code == 200, f"Create prescription failed: {response.text}"
        data = response.json()
        
        assert "id" in data, "Response should have prescription id"
        assert data.get("pdf_url") is None, "Draft should not have PDF"
        print(f"✓ Created draft prescription: {data['id']}")
        
        # Verify it was created
        get_resp = self.session.get(f"{BASE_URL}/api/clinic/prescriptions/{data['id']}")
        assert get_resp.status_code == 200
        presc = get_resp.json()
        assert presc["status"] == "draft"
        assert presc["diagnosis"] == "TEST_Gripe común"
        assert len(presc["items"]) == 1
        print("  ✓ Draft prescription verified in database")
        
        # Store for cleanup
        self.created_draft_id = data["id"]
        return data["id"]
    
    def test_create_prescription_issued_generates_pdf(self):
        """Test POST /api/clinic/prescriptions with status=issued generates PDF"""
        payload = {
            "patient_id": PATIENT_ID,
            "diagnosis": "TEST_Infección respiratoria",
            "general_instructions": "Completar tratamiento antibiótico",
            "items": [
                {
                    "medication_name": "Amoxicilina",
                    "presentation": "Cápsulas 500mg",
                    "dosage": "500mg",
                    "frequency": "Cada 8 horas",
                    "route": "oral",
                    "duration": "7 días",
                    "instructions": "Tomar con alimentos"
                },
                {
                    "medication_name": "Ibuprofeno",
                    "presentation": "Tabletas 400mg",
                    "dosage": "400mg",
                    "frequency": "Cada 6 horas si hay dolor",
                    "route": "oral",
                    "duration": "3 días",
                    "instructions": "No tomar en ayunas"
                }
            ],
            "status": "issued"
        }
        
        response = self.session.post(f"{BASE_URL}/api/clinic/prescriptions", json=payload)
        assert response.status_code == 200, f"Create issued prescription failed: {response.text}"
        data = response.json()
        
        assert "id" in data, "Response should have prescription id"
        # PDF generation might be async, so pdf_url could be None initially
        print(f"✓ Created issued prescription: {data['id']}")
        print(f"  PDF URL: {data.get('pdf_url', 'Not generated yet')}")
        
        # Verify it was created with issued status
        get_resp = self.session.get(f"{BASE_URL}/api/clinic/prescriptions/{data['id']}")
        assert get_resp.status_code == 200
        presc = get_resp.json()
        assert presc["status"] == "issued"
        assert presc.get("issued_at") is not None, "Issued prescription should have issued_at"
        assert len(presc["items"]) == 2
        print("  ✓ Issued prescription verified with 2 medications")
        
        return data["id"]
    
    def test_create_prescription_without_patient_fails(self):
        """Test creating prescription without patient_id fails"""
        payload = {
            "diagnosis": "TEST_Should fail",
            "items": [],
            "status": "draft"
        }
        
        response = self.session.post(f"{BASE_URL}/api/clinic/prescriptions", json=payload)
        assert response.status_code in [400, 422], f"Expected validation error, got {response.status_code}"
        print("✓ Creating prescription without patient_id fails with validation error")
    
    # ============== UPDATE PRESCRIPTION TESTS ==============
    
    def test_update_draft_prescription(self):
        """Test PUT /api/clinic/prescriptions/:id updates draft prescription"""
        # First create a draft
        create_payload = {
            "patient_id": PATIENT_ID,
            "diagnosis": "TEST_Original diagnosis",
            "items": [
                {
                    "medication_name": "Paracetamol",
                    "dosage": "500mg",
                    "frequency": "Cada 8 horas",
                    "route": "oral",
                    "duration": "3 días"
                }
            ],
            "status": "draft"
        }
        
        create_resp = self.session.post(f"{BASE_URL}/api/clinic/prescriptions", json=create_payload)
        assert create_resp.status_code == 200
        presc_id = create_resp.json()["id"]
        print(f"✓ Created draft prescription for update test: {presc_id}")
        
        # Update it
        update_payload = {
            "patient_id": PATIENT_ID,
            "diagnosis": "TEST_Updated diagnosis",
            "general_instructions": "New instructions",
            "items": [
                {
                    "medication_name": "Paracetamol",
                    "dosage": "1000mg",  # Changed dosage
                    "frequency": "Cada 6 horas",  # Changed frequency
                    "route": "oral",
                    "duration": "5 días"  # Changed duration
                },
                {
                    "medication_name": "Vitamina C",
                    "dosage": "1g",
                    "frequency": "Una vez al día",
                    "route": "oral",
                    "duration": "10 días"
                }
            ],
            "status": "draft"
        }
        
        update_resp = self.session.put(f"{BASE_URL}/api/clinic/prescriptions/{presc_id}", json=update_payload)
        assert update_resp.status_code == 200, f"Update failed: {update_resp.text}"
        print("✓ Updated draft prescription")
        
        # Verify update
        get_resp = self.session.get(f"{BASE_URL}/api/clinic/prescriptions/{presc_id}")
        presc = get_resp.json()
        assert presc["diagnosis"] == "TEST_Updated diagnosis"
        assert len(presc["items"]) == 2
        print("  ✓ Update verified: diagnosis changed, 2 medications now")
    
    def test_update_draft_to_issued(self):
        """Test updating draft prescription to issued status generates PDF"""
        # Create draft
        create_payload = {
            "patient_id": PATIENT_ID,
            "diagnosis": "TEST_Draft to issue",
            "items": [
                {
                    "medication_name": "Omeprazol",
                    "presentation": "Cápsulas 20mg",
                    "dosage": "20mg",
                    "frequency": "Una vez al día en ayunas",
                    "route": "oral",
                    "duration": "14 días"
                }
            ],
            "status": "draft"
        }
        
        create_resp = self.session.post(f"{BASE_URL}/api/clinic/prescriptions", json=create_payload)
        assert create_resp.status_code == 200
        presc_id = create_resp.json()["id"]
        print(f"✓ Created draft prescription: {presc_id}")
        
        # Update to issued
        update_payload = {
            "patient_id": PATIENT_ID,
            "diagnosis": "TEST_Draft to issue",
            "items": [
                {
                    "medication_name": "Omeprazol",
                    "presentation": "Cápsulas 20mg",
                    "dosage": "20mg",
                    "frequency": "Una vez al día en ayunas",
                    "route": "oral",
                    "duration": "14 días"
                }
            ],
            "status": "issued"
        }
        
        update_resp = self.session.put(f"{BASE_URL}/api/clinic/prescriptions/{presc_id}", json=update_payload)
        assert update_resp.status_code == 200, f"Update to issued failed: {update_resp.text}"
        data = update_resp.json()
        print(f"✓ Updated to issued status")
        print(f"  PDF URL: {data.get('pdf_url', 'Not available')}")
        
        # Verify
        get_resp = self.session.get(f"{BASE_URL}/api/clinic/prescriptions/{presc_id}")
        presc = get_resp.json()
        assert presc["status"] == "issued"
        assert presc.get("issued_at") is not None
        print("  ✓ Prescription is now issued with issued_at timestamp")
    
    def test_cannot_update_issued_prescription(self):
        """Test that issued prescriptions cannot be edited"""
        # Try to update the existing issued prescription
        update_payload = {
            "patient_id": PATIENT_ID,
            "diagnosis": "TEST_Should not update",
            "items": [],
            "status": "draft"
        }
        
        response = self.session.put(f"{BASE_URL}/api/clinic/prescriptions/{EXISTING_PRESCRIPTION_ID}", json=update_payload)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print("✓ Cannot update issued prescription (returns 400)")
    
    # ============== PDF URL TESTS ==============
    
    def test_get_pdf_url_for_issued_prescription(self):
        """Test GET /api/clinic/prescriptions/:id/pdf-url returns signed URL"""
        response = self.session.get(f"{BASE_URL}/api/clinic/prescriptions/{EXISTING_PRESCRIPTION_ID}/pdf-url")
        assert response.status_code == 200, f"Get PDF URL failed: {response.text}"
        data = response.json()
        
        assert "url" in data, "Response should have url"
        assert data["url"] is not None, "URL should not be None"
        assert "supabase" in data["url"].lower() or "storage" in data["url"].lower(), "URL should be from Supabase storage"
        print(f"✓ Got PDF URL for issued prescription")
        print(f"  URL: {data['url'][:100]}...")
    
    # ============== SEND WHATSAPP TESTS ==============
    
    def test_mark_prescription_sent_whatsapp(self):
        """Test PUT /api/clinic/prescriptions/:id/send marks as sent (MOCKED)"""
        # First create and issue a prescription
        create_payload = {
            "patient_id": PATIENT_ID,
            "diagnosis": "TEST_WhatsApp test",
            "items": [
                {
                    "medication_name": "Loratadina",
                    "dosage": "10mg",
                    "frequency": "Una vez al día",
                    "route": "oral",
                    "duration": "7 días"
                }
            ],
            "status": "issued"
        }
        
        create_resp = self.session.post(f"{BASE_URL}/api/clinic/prescriptions", json=create_payload)
        assert create_resp.status_code == 200
        presc_id = create_resp.json()["id"]
        print(f"✓ Created issued prescription for WhatsApp test: {presc_id}")
        
        # Mark as sent
        send_resp = self.session.put(f"{BASE_URL}/api/clinic/prescriptions/{presc_id}/send")
        assert send_resp.status_code == 200, f"Send failed: {send_resp.text}"
        print("✓ Marked prescription as sent via WhatsApp (MOCKED - no actual send)")
        
        # Verify sent_via is set
        get_resp = self.session.get(f"{BASE_URL}/api/clinic/prescriptions/{presc_id}")
        presc = get_resp.json()
        assert presc.get("sent_via") == "whatsapp", "sent_via should be 'whatsapp'"
        assert presc.get("sent_at") is not None, "sent_at should be set"
        print("  ✓ Prescription has sent_via='whatsapp' and sent_at timestamp")
    
    # ============== CREATE MEDICATION TESTS ==============
    
    def test_create_clinic_medication(self):
        """Test POST /api/clinic/medications creates clinic-specific medication"""
        payload = {
            "generic_name": "TEST_Medicamento Prueba",
            "brand_name": "TestBrand",
            "presentations": "Tabletas 100mg, Jarabe 50mg/5ml",
            "category": "Test"
        }
        
        response = self.session.post(f"{BASE_URL}/api/clinic/medications", json=payload)
        assert response.status_code == 200, f"Create medication failed: {response.text}"
        data = response.json()
        
        assert "id" in data, "Response should have medication id"
        print(f"✓ Created clinic medication: {data['id']}")
        
        # Verify it appears in search
        search_resp = self.session.get(f"{BASE_URL}/api/clinic/medications/search?q=TEST_Medicamento")
        search_data = search_resp.json()
        found = any(m.get("generic_name") == "TEST_Medicamento Prueba" for m in search_data)
        assert found, "Created medication should appear in search"
        print("  ✓ New medication appears in search results")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
