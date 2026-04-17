# Panel de Super Administrador + CRM Clinicas

## Problem Statement Original
Panel de Super Administrador para plataforma de CRM de clinicas medicas. El super admin crea clinicas y asigna administradores iniciales. Modulo de Agenda completo, Modulo de Pacientes completo, y Modulo de Historia Clinica completo.

## Arquitectura

### Stack Tecnologico
- **Frontend**: React 19 + Tailwind CSS + Shadcn UI + React Hook Form + Zod
- **Backend**: FastAPI (Python 3.11)
- **Base de datos**: Supabase PostgreSQL (datos + autenticacion + realtime)
- **Almacenamiento**: Supabase Storage (bucket: patient-files)

### Estructura de Base de Datos (Supabase PostgreSQL)
- `super_admins`: id(uuid), user_id, first_name, last_name, email, is_active
- `clinics`: id(uuid), name, slug, country, city, address, phone, email, timezone, schedule_start, schedule_end, slot_duration, working_days, plan(enum), max_users, max_patients, max_storage_mb, is_active
- `clinic_members`: id(uuid), clinic_id(fk), user_id(fk->auth.users), role(enum), first_name, last_name, specialty, is_active
- `patients`: id(uuid), clinic_id(fk), first_name, last_name, phone, email, date_of_birth, gender, national_id, nationality, phone_secondary, address, city, state, country, emergency_contact_name, emergency_contact_relation, emergency_contact_phone, blood_type, allergies(text[]), chronic_conditions(text[]), current_medications(text[]), insurance_provider, insurance_policy_number, insurance_expiry, notes, is_active
- `appointments`: id(uuid), clinic_id(fk), patient_id(fk), doctor_id(fk), starts_at, ends_at, duration_minutes, reason, notes, status(enum), cancellation_reason
- `medical_records`: id(uuid), clinic_id(fk), patient_id(fk), doctor_id(fk), appointment_id(fk, nullable), status(draft/finalized), chief_complaint, present_illness, review_of_systems(jsonb), blood_pressure_systolic, blood_pressure_diastolic, heart_rate, respiratory_rate, temperature, oxygen_saturation, weight_kg, height_cm, bmi, physical_exam(jsonb), diagnoses(jsonb[]), treatment_plan, procedures, notes, private_notes, addenda(jsonb[]), finalized_at, created_at, updated_at
- `medications`: id(uuid), clinic_id, generic_name, brand_name, presentations(text[]), category, is_active
- `lab_studies`: id(uuid), clinic_id, name, category, preparation, is_active
- `icd10_codes`: id(int), code, description_en, description_es, category, is_common (672 codigos precargados)

### Flujo de Autenticacion
1. Login unico -> verifica tipo usuario (super_admin o clinic_member)
2. Super admin -> /admin
3. Clinic member -> /dashboard (agenda, pacientes, historial clinico)

## Implementados
- [x] Login unico con deteccion de tipo de usuario
- [x] Super Admin Panel (Dashboard, Clinicas CRUD, Usuarios, Catalogos)
- [x] Catalogos con importacion masiva (Medicamentos, Lab, CIE-10)
- [x] Precarga 672 codigos CIE-10
- [x] Login UI con branding Cortexia Medical
- [x] **MIGRACION MongoDB -> Supabase PostgreSQL** (10 Abril 2026)
- [x] **MODULO DE AGENDA COMPLETO** (16 Abril 2026)
- [x] Eliminacion de marca de agua Emergent via CSS
- [x] Busqueda/filtro en catalogos de Super Admin
- [x] **MODULO DE PACIENTES COMPLETO** (17 Abril 2026)
- [x] **MODULO DE HISTORIA CLINICA COMPLETO** (17 Abril 2026):
  - [x] Formulario de nueva consulta con 7 secciones colapsables
  - [x] Motivo de consulta e historia de enfermedad actual
  - [x] Revision por sistemas con checkboxes organizados (9 sistemas)
  - [x] Signos vitales con validacion de rangos normales (PA, FC, FR, Temp, SpO2)
  - [x] IMC auto-calculado desde peso y talla con clasificacion
  - [x] Examen fisico por region (cabeza, cuello, torax, abdomen, extremidades, neurologico)
  - [x] Diagnostico con buscador CIE-10 autocomplete (672 codigos)
  - [x] Diagnostico principal/secundario con etiquetas visuales
  - [x] Plan de tratamiento y procedimientos realizados
  - [x] Notas generales y notas privadas del medico (solo visibles para doctores)
  - [x] Guardar borrador y Finalizar consulta
  - [x] Consulta finalizada no editable (solo addendum)
  - [x] Addendum para consultas finalizadas con historial
  - [x] Timeline cronologica en perfil del paciente (mas reciente primero)
  - [x] Filtro por medico y rango de fechas en timeline
  - [x] Cards expandibles con detalle completo del registro medico
  - [x] Indicador visual de signos vitales fuera de rango
  - [x] Permisos: doctor/clinic_admin crean/ven completo, assistant ve resumen sin notas privadas, receptionist sin acceso

## Pendientes
- [ ] Modulo de recetas medicas - P1
- [ ] Importacion CSV para catalogos - P2
- [ ] Reportes y estadisticas avanzadas - P2
- [ ] Notificaciones/recordatorios de citas - P2
- [ ] Refactoring: dividir server.py en routers separados

## Credenciales
Ver `/app/memory/test_credentials.md`
