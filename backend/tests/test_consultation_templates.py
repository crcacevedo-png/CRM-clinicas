"""
Test suite for Consultation Templates feature
Tests: GET /api/clinic/templates, POST /api/clinic/templates, DELETE /api/clinic/templates/:id
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://super-admin-panel-12.preview.emergentagent.com').rstrip('/')

# Test credentials
CLINIC_ADMIN_EMAIL = "carlos@lasalud.gt"
CLINIC_ADMIN_PASSWORD = "Test123456!"
PATIENT_ID = "dffcbc90-407b-4e3a-b032-b831b20b524b"


class TestConsultationTemplates:
    """Test consultation templates CRUD operations"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": CLINIC_ADMIN_EMAIL,
            "password": CLINIC_ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        self.token = data["access_token"]
        self.clinic_id = data["clinic_id"]
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        self.created_template_id = None
        yield
        # Cleanup: delete test template if created
        if self.created_template_id:
            try:
                requests.delete(
                    f"{BASE_URL}/api/clinic/templates/{self.created_template_id}",
                    headers=self.headers
                )
            except:
                pass
    
    def test_01_get_templates_returns_10_global_templates(self):
        """GET /api/clinic/templates returns 10 global templates"""
        response = requests.get(f"{BASE_URL}/api/clinic/templates", headers=self.headers)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        templates = response.json()
        
        # Should have at least 10 global templates
        global_templates = [t for t in templates if t.get('clinic_id') is None]
        assert len(global_templates) >= 10, f"Expected at least 10 global templates, got {len(global_templates)}"
        
        # Verify template structure
        for t in templates:
            assert 'id' in t, "Template missing 'id'"
            assert 'name' in t, "Template missing 'name'"
            assert 'category' in t, "Template missing 'category'"
            assert 'template_data' in t, "Template missing 'template_data'"
            assert 'is_active' in t, "Template missing 'is_active'"
        
        print(f"PASSED: GET /api/clinic/templates returns {len(global_templates)} global templates")
    
    def test_02_templates_have_correct_categories(self):
        """Templates are organized by correct categories"""
        response = requests.get(f"{BASE_URL}/api/clinic/templates", headers=self.headers)
        assert response.status_code == 200
        templates = response.json()
        
        expected_categories = {'general', 'especialidad', 'urgencia', 'cronica', 'procedimiento'}
        found_categories = {t['category'] for t in templates}
        
        assert expected_categories.issubset(found_categories), \
            f"Missing categories. Expected: {expected_categories}, Found: {found_categories}"
        
        # Count templates per category
        category_counts = {}
        for t in templates:
            cat = t['category']
            category_counts[cat] = category_counts.get(cat, 0) + 1
        
        print(f"PASSED: Templates organized by categories: {category_counts}")
    
    def test_03_consulta_general_adulto_template_structure(self):
        """'Consulta general adulto' template has correct structure (no chief_complaint, has physical_exam)"""
        response = requests.get(f"{BASE_URL}/api/clinic/templates", headers=self.headers)
        assert response.status_code == 200
        templates = response.json()
        
        general_template = next((t for t in templates if t['name'] == 'Consulta general adulto'), None)
        assert general_template is not None, "Template 'Consulta general adulto' not found"
        
        td = general_template.get('template_data', {})
        
        # Should NOT have chief_complaint pre-filled
        assert 'chief_complaint' not in td or td.get('chief_complaint') is None or td.get('chief_complaint') == '', \
            f"'Consulta general adulto' should NOT have chief_complaint pre-filled, got: {td.get('chief_complaint')}"
        
        # Should have physical_exam sections
        assert 'physical_exam' in td, "'Consulta general adulto' should have physical_exam"
        pe = td['physical_exam']
        assert 'head' in pe, "physical_exam should have 'head'"
        assert 'neck' in pe, "physical_exam should have 'neck'"
        assert 'chest' in pe, "physical_exam should have 'chest'"
        assert 'abdomen' in pe, "physical_exam should have 'abdomen'"
        
        print(f"PASSED: 'Consulta general adulto' has correct structure - no chief_complaint, has physical_exam sections")
    
    def test_04_control_diabetes_template_has_diagnosis_e11(self):
        """'Control de diabetes' template has E11 diagnosis as primary"""
        response = requests.get(f"{BASE_URL}/api/clinic/templates", headers=self.headers)
        assert response.status_code == 200
        templates = response.json()
        
        diabetes_template = next((t for t in templates if t['name'] == 'Control de diabetes'), None)
        assert diabetes_template is not None, "Template 'Control de diabetes' not found"
        
        td = diabetes_template.get('template_data', {})
        
        # Should have chief_complaint = "Control de diabetes"
        assert td.get('chief_complaint') == 'Control de diabetes', \
            f"Expected chief_complaint='Control de diabetes', got: {td.get('chief_complaint')}"
        
        # Should have diagnoses with E11 as primary
        diagnoses = td.get('diagnoses', [])
        assert len(diagnoses) > 0, "Control de diabetes should have diagnoses"
        
        e11_diagnosis = next((d for d in diagnoses if d.get('code') == 'E11'), None)
        assert e11_diagnosis is not None, "E11 diagnosis not found in Control de diabetes template"
        assert e11_diagnosis.get('type') == 'primary', f"E11 should be primary, got: {e11_diagnosis.get('type')}"
        
        # Should have HbA1c in notes
        notes = td.get('notes', '')
        assert 'HbA1c' in notes, f"Notes should mention HbA1c, got: {notes}"
        
        print(f"PASSED: 'Control de diabetes' has E11 as primary diagnosis and HbA1c in notes")
    
    def test_05_control_hipertension_template_has_diagnosis_i10(self):
        """'Control de hipertensión' template has I10 diagnosis as primary"""
        response = requests.get(f"{BASE_URL}/api/clinic/templates", headers=self.headers)
        assert response.status_code == 200
        templates = response.json()
        
        hta_template = next((t for t in templates if t['name'] == 'Control de hipertensión'), None)
        assert hta_template is not None, "Template 'Control de hipertensión' not found"
        
        td = hta_template.get('template_data', {})
        
        # Should have chief_complaint = "Control de hipertensión arterial"
        assert td.get('chief_complaint') == 'Control de hipertensión arterial', \
            f"Expected chief_complaint='Control de hipertensión arterial', got: {td.get('chief_complaint')}"
        
        # Should have diagnoses with I10 as primary
        diagnoses = td.get('diagnoses', [])
        assert len(diagnoses) > 0, "Control de hipertensión should have diagnoses"
        
        i10_diagnosis = next((d for d in diagnoses if d.get('code') == 'I10'), None)
        assert i10_diagnosis is not None, "I10 diagnosis not found in Control de hipertensión template"
        assert i10_diagnosis.get('type') == 'primary', f"I10 should be primary, got: {i10_diagnosis.get('type')}"
        
        print(f"PASSED: 'Control de hipertensión' has I10 as primary diagnosis")
    
    def test_06_create_clinic_specific_template(self):
        """POST /api/clinic/templates creates a clinic-specific template"""
        template_data = {
            "name": "TEST_Plantilla de prueba",
            "category": "general",
            "description": "Plantilla de prueba para testing",
            "template_data": {
                "chief_complaint": "Consulta de prueba",
                "physical_exam": {
                    "head": "Normal",
                    "chest": "Normal"
                }
            },
            "sort_order": 100
        }
        
        response = requests.post(
            f"{BASE_URL}/api/clinic/templates",
            headers=self.headers,
            json=template_data
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        result = response.json()
        
        assert 'id' in result, "Response should contain template id"
        self.created_template_id = result['id']
        
        print(f"PASSED: Created clinic-specific template with id: {self.created_template_id}")
    
    def test_07_clinic_template_appears_in_list(self):
        """Created clinic template appears in the templates list"""
        # First create a template
        template_data = {
            "name": "TEST_Plantilla verificación",
            "category": "general",
            "description": "Para verificar que aparece en lista",
            "template_data": {"chief_complaint": "Test"},
            "sort_order": 101
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/clinic/templates",
            headers=self.headers,
            json=template_data
        )
        assert create_response.status_code == 200
        created_id = create_response.json()['id']
        self.created_template_id = created_id
        
        # Now get templates and verify it appears
        list_response = requests.get(f"{BASE_URL}/api/clinic/templates", headers=self.headers)
        assert list_response.status_code == 200
        templates = list_response.json()
        
        clinic_template = next((t for t in templates if t['id'] == created_id), None)
        assert clinic_template is not None, f"Created template {created_id} not found in list"
        assert clinic_template['clinic_id'] == self.clinic_id, "Template should have clinic_id set"
        
        print(f"PASSED: Clinic template appears in list with clinic_id={self.clinic_id}")
    
    def test_08_delete_clinic_template(self):
        """DELETE /api/clinic/templates/:id deactivates a clinic template"""
        # First create a template to delete
        template_data = {
            "name": "TEST_Plantilla para eliminar",
            "category": "general",
            "description": "Esta plantilla será eliminada",
            "template_data": {},
            "sort_order": 102
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/clinic/templates",
            headers=self.headers,
            json=template_data
        )
        assert create_response.status_code == 200
        template_id = create_response.json()['id']
        
        # Delete the template
        delete_response = requests.delete(
            f"{BASE_URL}/api/clinic/templates/{template_id}",
            headers=self.headers
        )
        assert delete_response.status_code == 200, f"Expected 200, got {delete_response.status_code}: {delete_response.text}"
        
        # Verify it no longer appears in active templates
        list_response = requests.get(f"{BASE_URL}/api/clinic/templates", headers=self.headers)
        assert list_response.status_code == 200
        templates = list_response.json()
        
        deleted_template = next((t for t in templates if t['id'] == template_id), None)
        assert deleted_template is None, "Deleted template should not appear in active templates list"
        
        print(f"PASSED: DELETE /api/clinic/templates/{template_id} deactivated the template")
    
    def test_09_cannot_delete_global_template(self):
        """Cannot delete global templates (clinic_id=null)"""
        # Get a global template id
        response = requests.get(f"{BASE_URL}/api/clinic/templates", headers=self.headers)
        assert response.status_code == 200
        templates = response.json()
        
        global_template = next((t for t in templates if t.get('clinic_id') is None), None)
        assert global_template is not None, "No global template found"
        
        # Try to delete it
        delete_response = requests.delete(
            f"{BASE_URL}/api/clinic/templates/{global_template['id']}",
            headers=self.headers
        )
        
        # Should return 403 Forbidden
        assert delete_response.status_code == 403, \
            f"Expected 403 when deleting global template, got {delete_response.status_code}: {delete_response.text}"
        
        print(f"PASSED: Cannot delete global template - returns 403")
    
    def test_10_all_10_expected_templates_exist(self):
        """Verify all 10 expected global templates exist"""
        response = requests.get(f"{BASE_URL}/api/clinic/templates", headers=self.headers)
        assert response.status_code == 200
        templates = response.json()
        
        expected_templates = [
            "Consulta general adulto",
            "Control de seguimiento",
            "Control prenatal",
            "Consulta pediátrica",
            "Consulta ginecológica",
            "Urgencia médica",
            "Consulta por dolor",
            "Control de diabetes",
            "Control de hipertensión",
            "Procedimiento menor / curación"
        ]
        
        template_names = [t['name'] for t in templates if t.get('clinic_id') is None]
        
        for expected in expected_templates:
            assert expected in template_names, f"Expected template '{expected}' not found"
        
        print(f"PASSED: All 10 expected global templates exist: {expected_templates}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
