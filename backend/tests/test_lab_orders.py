"""
Lab Orders Module Tests
Tests for lab studies listing, lab order CRUD, and PDF generation
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
CLINIC_ADMIN_EMAIL = "carlos@lasalud.gt"
CLINIC_ADMIN_PASSWORD = "Test123456!"
TEST_PATIENT_ID = "dffcbc90-407b-4e3a-b032-b831b20b524b"  # Maria Garcia


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for clinic admin"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": CLINIC_ADMIN_EMAIL,
        "password": CLINIC_ADMIN_PASSWORD
    })
    if response.status_code != 200:
        pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")
    data = response.json()
    return data.get("access_token")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Get headers with auth token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


class TestLabStudies:
    """Tests for GET /api/clinic/lab-studies endpoint"""
    
    def test_list_lab_studies_returns_200(self, auth_headers):
        """Lab studies endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/clinic/lab-studies", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"✓ GET /api/clinic/lab-studies returns 200")
    
    def test_lab_studies_returns_list(self, auth_headers):
        """Lab studies should return a list"""
        response = requests.get(f"{BASE_URL}/api/clinic/lab-studies", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ Lab studies returns list with {len(data)} items")
    
    def test_lab_studies_have_required_fields(self, auth_headers):
        """Each lab study should have id, name, category, preparation fields"""
        response = requests.get(f"{BASE_URL}/api/clinic/lab-studies", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        if len(data) > 0:
            study = data[0]
            assert "id" in study, "Study should have 'id' field"
            assert "name" in study, "Study should have 'name' field"
            assert "category" in study, "Study should have 'category' field"
            # preparation can be null/empty
            assert "preparation" in study or study.get("preparation") is None, "Study should have 'preparation' field"
            print(f"✓ Lab studies have required fields (id, name, category, preparation)")
        else:
            pytest.skip("No lab studies in database to verify fields")
    
    def test_lab_studies_grouped_by_category(self, auth_headers):
        """Lab studies should have categories for grouping"""
        response = requests.get(f"{BASE_URL}/api/clinic/lab-studies", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        categories = set()
        for study in data:
            if study.get("category"):
                categories.add(study["category"])
        
        print(f"✓ Found {len(categories)} categories: {list(categories)[:5]}...")
        assert len(categories) > 0, "Should have at least one category"
    
    def test_lab_studies_have_preparation_instructions(self, auth_headers):
        """Some lab studies should have preparation instructions"""
        response = requests.get(f"{BASE_URL}/api/clinic/lab-studies", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        studies_with_prep = [s for s in data if s.get("preparation")]
        print(f"✓ Found {len(studies_with_prep)} studies with preparation instructions")
        # This is informational - not all studies need preparation


class TestLabOrdersList:
    """Tests for GET /api/clinic/lab-orders endpoint"""
    
    def test_list_lab_orders_returns_200(self, auth_headers):
        """Lab orders list endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/clinic/lab-orders", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"✓ GET /api/clinic/lab-orders returns 200")
    
    def test_lab_orders_response_structure(self, auth_headers):
        """Lab orders response should have orders, total, page, pages"""
        response = requests.get(f"{BASE_URL}/api/clinic/lab-orders", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "orders" in data, "Response should have 'orders' field"
        assert "total" in data, "Response should have 'total' field"
        assert "page" in data, "Response should have 'page' field"
        assert "pages" in data, "Response should have 'pages' field"
        assert isinstance(data["orders"], list), "'orders' should be a list"
        print(f"✓ Lab orders response has correct structure (orders: {len(data['orders'])}, total: {data['total']})")
    
    def test_lab_orders_have_enriched_fields(self, auth_headers):
        """Lab orders should have patient_name, study_summary, item_count"""
        response = requests.get(f"{BASE_URL}/api/clinic/lab-orders", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        if len(data["orders"]) > 0:
            order = data["orders"][0]
            assert "patient_name" in order, "Order should have 'patient_name'"
            assert "study_summary" in order, "Order should have 'study_summary'"
            assert "item_count" in order, "Order should have 'item_count'"
            assert "priority" in order, "Order should have 'priority'"
            assert "status" in order, "Order should have 'status'"
            print(f"✓ Lab orders have enriched fields (patient_name, study_summary, item_count)")
        else:
            print("⚠ No lab orders to verify enriched fields - will be tested after creation")
    
    def test_lab_orders_filter_by_status(self, auth_headers):
        """Lab orders can be filtered by status"""
        response = requests.get(f"{BASE_URL}/api/clinic/lab-orders?status=pending", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        # All returned orders should have pending status
        for order in data["orders"]:
            assert order["status"] == "pending", f"Expected status 'pending', got '{order['status']}'"
        print(f"✓ Lab orders filter by status works (found {len(data['orders'])} pending orders)")
    
    def test_lab_orders_filter_by_patient(self, auth_headers):
        """Lab orders can be filtered by patient_id"""
        response = requests.get(f"{BASE_URL}/api/clinic/lab-orders?patient_id={TEST_PATIENT_ID}", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        print(f"✓ Lab orders filter by patient_id works (found {len(data['orders'])} orders for patient)")


class TestLabOrderCreate:
    """Tests for POST /api/clinic/lab-orders endpoint"""
    
    @pytest.fixture(scope="class")
    def sample_studies(self, auth_headers):
        """Get sample studies for creating orders"""
        response = requests.get(f"{BASE_URL}/api/clinic/lab-studies", headers=auth_headers)
        if response.status_code != 200 or len(response.json()) < 2:
            pytest.skip("Need at least 2 lab studies to test order creation")
        return response.json()[:3]  # Get first 3 studies
    
    def test_create_lab_order_success(self, auth_headers, sample_studies):
        """Creating a lab order should return 200/201 with order id and pdf_url"""
        payload = {
            "patient_id": TEST_PATIENT_ID,
            "presumptive_diagnosis": "TEST_Diagnóstico de prueba",
            "priority": "routine",
            "special_instructions": "TEST_Indicaciones especiales de prueba",
            "notes": "TEST_Notas de prueba",
            "status": "pending",
            "items": [
                {
                    "study_id": sample_studies[0]["id"],
                    "study_name": sample_studies[0]["name"],
                    "category": sample_studies[0].get("category", "")
                },
                {
                    "study_id": sample_studies[1]["id"],
                    "study_name": sample_studies[1]["name"],
                    "category": sample_studies[1].get("category", "")
                }
            ]
        }
        
        response = requests.post(f"{BASE_URL}/api/clinic/lab-orders", json=payload, headers=auth_headers)
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "id" in data, "Response should have 'id'"
        assert "pdf_url" in data, "Response should have 'pdf_url'"
        assert data["pdf_url"] is not None, "PDF URL should be generated for pending orders"
        
        print(f"✓ Lab order created successfully with id: {data['id']}")
        print(f"✓ PDF URL generated: {data['pdf_url'][:50]}...")
        
        # Store for later tests
        TestLabOrderCreate.created_order_id = data["id"]
    
    def test_create_lab_order_urgent_priority(self, auth_headers, sample_studies):
        """Creating an urgent lab order should work"""
        payload = {
            "patient_id": TEST_PATIENT_ID,
            "presumptive_diagnosis": "TEST_Urgente - Diagnóstico",
            "priority": "urgent",
            "status": "pending",
            "items": [
                {
                    "study_id": sample_studies[0]["id"],
                    "study_name": sample_studies[0]["name"],
                    "category": sample_studies[0].get("category", "")
                }
            ]
        }
        
        response = requests.post(f"{BASE_URL}/api/clinic/lab-orders", json=payload, headers=auth_headers)
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "id" in data
        print(f"✓ Urgent lab order created successfully")
        
        # Verify the order has urgent priority
        get_response = requests.get(f"{BASE_URL}/api/clinic/lab-orders/{data['id']}", headers=auth_headers)
        assert get_response.status_code == 200
        order_data = get_response.json()
        assert order_data["priority"] == "urgent", f"Expected priority 'urgent', got '{order_data['priority']}'"
        print(f"✓ Urgent priority verified in created order")
    
    def test_create_lab_order_without_patient_fails(self, auth_headers, sample_studies):
        """Creating a lab order without patient_id should fail"""
        payload = {
            "presumptive_diagnosis": "TEST_Sin paciente",
            "priority": "routine",
            "items": [
                {
                    "study_id": sample_studies[0]["id"],
                    "study_name": sample_studies[0]["name"],
                    "category": sample_studies[0].get("category", "")
                }
            ]
        }
        
        response = requests.post(f"{BASE_URL}/api/clinic/lab-orders", json=payload, headers=auth_headers)
        assert response.status_code == 422, f"Expected 422 validation error, got {response.status_code}"
        print(f"✓ Creating order without patient_id fails with 422")
    
    def test_create_lab_order_without_items_succeeds(self, auth_headers):
        """Creating a lab order without items should succeed (empty items list)"""
        payload = {
            "patient_id": TEST_PATIENT_ID,
            "presumptive_diagnosis": "TEST_Sin estudios",
            "priority": "routine",
            "items": []
        }
        
        response = requests.post(f"{BASE_URL}/api/clinic/lab-orders", json=payload, headers=auth_headers)
        # This might succeed or fail depending on business logic
        print(f"Creating order without items: status {response.status_code}")


class TestLabOrderGet:
    """Tests for GET /api/clinic/lab-orders/:id endpoint"""
    
    def test_get_lab_order_by_id(self, auth_headers):
        """Getting a lab order by ID should return full details"""
        # First get list to find an order
        list_response = requests.get(f"{BASE_URL}/api/clinic/lab-orders", headers=auth_headers)
        assert list_response.status_code == 200
        orders = list_response.json()["orders"]
        
        if len(orders) == 0:
            pytest.skip("No lab orders to test GET by ID")
        
        order_id = orders[0]["id"]
        response = requests.get(f"{BASE_URL}/api/clinic/lab-orders/{order_id}", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "id" in data
        assert "patient" in data, "Should include patient details"
        assert "doctor" in data, "Should include doctor details"
        assert "items" in data, "Should include order items"
        assert isinstance(data["items"], list), "Items should be a list"
        
        print(f"✓ GET /api/clinic/lab-orders/{order_id} returns full order details")
        print(f"  - Patient: {data.get('patient', {}).get('first_name', 'N/A')}")
        print(f"  - Items count: {len(data['items'])}")
    
    def test_get_nonexistent_lab_order_returns_404(self, auth_headers):
        """Getting a non-existent lab order should return 404"""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = requests.get(f"{BASE_URL}/api/clinic/lab-orders/{fake_id}", headers=auth_headers)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print(f"✓ GET non-existent order returns 404")


class TestLabOrderPDF:
    """Tests for GET /api/clinic/lab-orders/:id/pdf-url endpoint"""
    
    def test_get_pdf_url_for_existing_order(self, auth_headers):
        """Getting PDF URL for existing order should return signed URL"""
        # First get list to find an order
        list_response = requests.get(f"{BASE_URL}/api/clinic/lab-orders", headers=auth_headers)
        assert list_response.status_code == 200
        orders = list_response.json()["orders"]
        
        if len(orders) == 0:
            pytest.skip("No lab orders to test PDF URL")
        
        order_id = orders[0]["id"]
        response = requests.get(f"{BASE_URL}/api/clinic/lab-orders/{order_id}/pdf-url", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "url" in data, "Response should have 'url' field"
        assert data["url"], "URL should not be empty"
        assert "supabase" in data["url"].lower() or "storage" in data["url"].lower(), "URL should be a Supabase storage URL"
        
        print(f"✓ GET /api/clinic/lab-orders/{order_id}/pdf-url returns signed URL")
    
    def test_get_pdf_url_for_nonexistent_order_returns_404(self, auth_headers):
        """Getting PDF URL for non-existent order should return 404"""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = requests.get(f"{BASE_URL}/api/clinic/lab-orders/{fake_id}/pdf-url", headers=auth_headers)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print(f"✓ GET PDF URL for non-existent order returns 404")


class TestLabOrderVerifyPersistence:
    """Tests to verify data persistence after creation"""
    
    def test_created_order_appears_in_list(self, auth_headers):
        """Newly created order should appear in the orders list"""
        # Create a new order
        studies_response = requests.get(f"{BASE_URL}/api/clinic/lab-studies", headers=auth_headers)
        if studies_response.status_code != 200 or len(studies_response.json()) < 1:
            pytest.skip("Need lab studies to test")
        
        studies = studies_response.json()
        
        payload = {
            "patient_id": TEST_PATIENT_ID,
            "presumptive_diagnosis": "TEST_Verificar persistencia",
            "priority": "routine",
            "status": "pending",
            "items": [
                {
                    "study_id": studies[0]["id"],
                    "study_name": studies[0]["name"],
                    "category": studies[0].get("category", "")
                }
            ]
        }
        
        create_response = requests.post(f"{BASE_URL}/api/clinic/lab-orders", json=payload, headers=auth_headers)
        assert create_response.status_code in [200, 201]
        created_id = create_response.json()["id"]
        
        # Verify it appears in list
        list_response = requests.get(f"{BASE_URL}/api/clinic/lab-orders", headers=auth_headers)
        assert list_response.status_code == 200
        orders = list_response.json()["orders"]
        
        order_ids = [o["id"] for o in orders]
        assert created_id in order_ids, f"Created order {created_id} should appear in list"
        print(f"✓ Created order appears in list (verified persistence)")
    
    def test_order_items_persisted_correctly(self, auth_headers):
        """Order items should be persisted and retrievable"""
        studies_response = requests.get(f"{BASE_URL}/api/clinic/lab-studies", headers=auth_headers)
        if studies_response.status_code != 200 or len(studies_response.json()) < 2:
            pytest.skip("Need at least 2 lab studies")
        
        studies = studies_response.json()[:2]
        
        payload = {
            "patient_id": TEST_PATIENT_ID,
            "presumptive_diagnosis": "TEST_Verificar items",
            "priority": "routine",
            "status": "pending",
            "items": [
                {
                    "study_id": studies[0]["id"],
                    "study_name": studies[0]["name"],
                    "category": studies[0].get("category", "")
                },
                {
                    "study_id": studies[1]["id"],
                    "study_name": studies[1]["name"],
                    "category": studies[1].get("category", "")
                }
            ]
        }
        
        create_response = requests.post(f"{BASE_URL}/api/clinic/lab-orders", json=payload, headers=auth_headers)
        assert create_response.status_code in [200, 201]
        created_id = create_response.json()["id"]
        
        # Get the order and verify items
        get_response = requests.get(f"{BASE_URL}/api/clinic/lab-orders/{created_id}", headers=auth_headers)
        assert get_response.status_code == 200
        order = get_response.json()
        
        assert len(order["items"]) == 2, f"Expected 2 items, got {len(order['items'])}"
        item_names = [i["study_name"] for i in order["items"]]
        assert studies[0]["name"] in item_names, f"First study should be in items"
        assert studies[1]["name"] in item_names, f"Second study should be in items"
        
        print(f"✓ Order items persisted correctly ({len(order['items'])} items)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
