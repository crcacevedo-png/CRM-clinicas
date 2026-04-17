# Panel de Super Administrador + CRM Clinicas

## Problem Statement Original
Panel de Super Administrador para plataforma de CRM de clinicas medicas. El super admin crea clinicas y asigna administradores iniciales. Incluye: Agenda completa, Pacientes, Historia Clinica con plantillas, y Recetas Medicas con PDF.

## Arquitectura

### Stack Tecnologico
- **Frontend**: React 19 + Tailwind CSS + Shadcn UI + React Hook Form + Zod
- **Backend**: FastAPI (Python 3.11) + reportlab (PDF)
- **Base de datos**: Supabase PostgreSQL
- **Almacenamiento**: Supabase Storage (bucket: patient-files)

### Estructura de Base de Datos
- `super_admins`, `clinics`, `clinic_members`, `patients`, `appointments`
- `medical_records`: Historia clinica con signos vitales, diagnosticos CIE-10, addenda
- `consultation_templates`: Plantillas predefinidas (10 globales + por clinica)
- `prescriptions`: id, clinic_id, patient_id, doctor_id, medical_record_id, diagnosis, general_instructions, status(draft/issued), pdf_url, sent_via, sent_at, issued_at
- `prescription_items`: id, prescription_id, medication_name, presentation, dosage, frequency, route, duration, instructions, sort_order
- `medications`: 63 medicamentos precargados + por clinica
- `lab_studies`, `icd10_codes`: 672 codigos CIE-10

## Implementados
- [x] Login unico con deteccion de tipo de usuario
- [x] Super Admin Panel (Dashboard, Clinicas CRUD, Usuarios, Catalogos)
- [x] **MIGRACION MongoDB -> Supabase PostgreSQL** (10 Abril 2026)
- [x] **MODULO DE AGENDA COMPLETO** (16 Abril 2026)
- [x] **MODULO DE PACIENTES COMPLETO** (17 Abril 2026)
- [x] **MODULO DE HISTORIA CLINICA** (17 Abril 2026)
- [x] **PLANTILLAS DE CONSULTA** (17 Abril 2026) - 10 plantillas globales
- [x] **MODULO DE RECETAS MEDICAS CON PDF** (17 Abril 2026):
  - [x] Lista paginada con filtro por estado (Borrador/Emitida)
  - [x] Formulario con autocomplete de pacientes y medicamentos
  - [x] Tabla dinamica de medicamentos (agregar/eliminar filas)
  - [x] Campos: medicamento, presentacion, dosis, frecuencia, via, duracion, instrucciones
  - [x] Dropdown de presentaciones desde tabla medications
  - [x] Registrar nuevo medicamento desde el formulario
  - [x] Guardar borrador / Emitir receta / Emitir y enviar (WhatsApp MOCKEADO)
  - [x] Generacion de PDF con reportlab: header clinica, datos medico, Rx, medicamentos, firma
  - [x] PDF almacenado en Supabase Storage
  - [x] Descarga de PDF desde lista de recetas
  - [x] Acceso desde perfil del paciente (tab Recetas)
  - [x] Item "Recetas" en sidebar de navegacion clinica

## Pendientes
- [ ] Importacion CSV para catalogos - P2
- [ ] Reportes y estadisticas avanzadas - P2
- [ ] Notificaciones/recordatorios de citas - P2
- [ ] Integracion real WhatsApp via n8n - P2
- [ ] Refactoring: dividir server.py en routers separados

## Credenciales
Ver `/app/memory/test_credentials.md`
