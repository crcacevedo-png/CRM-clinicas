# Panel de Super Administrador + CRM Clinicas

## Problem Statement Original
Panel de Super Administrador para plataforma de CRM de clinicas medicas. El super admin crea clinicas y asigna administradores iniciales. Modulo de Agenda completo para gestion de citas.

## Arquitectura

### Stack Tecnologico
- **Frontend**: React 19 + Tailwind CSS + Shadcn UI
- **Backend**: FastAPI (Python 3.11)
- **Base de datos**: Supabase PostgreSQL (datos + autenticacion + realtime)

### Estructura de Base de Datos (Supabase PostgreSQL)
- `super_admins`: id(uuid), user_id, first_name, last_name, email, is_active
- `clinics`: id(uuid), name, slug, country, city, address, phone, email, timezone, schedule_start, schedule_end, slot_duration, working_days, plan(enum), max_users, max_patients, max_storage_mb, is_active
- `clinic_members`: id(uuid), clinic_id(fk), user_id(fk->auth.users), role(enum), first_name, last_name, specialty, is_active
- `patients`: id(uuid), clinic_id(fk), first_name, last_name, phone, email, date_of_birth, gender, national_id, is_active
- `appointments`: id(uuid), clinic_id(fk), patient_id(fk), doctor_id(fk), starts_at, ends_at, duration_minutes, reason, notes, status(enum: scheduled/confirmed/in_progress/completed/cancelled/no_show), cancellation_reason
- `medications`: id(uuid), clinic_id, generic_name, brand_name, presentations(text[]), category, is_active
- `lab_studies`: id(uuid), clinic_id, name, category, preparation, is_active
- `icd10_codes`: id(int), code, description_en, description_es, category, is_common

### Flujo de Autenticacion
1. Login unico -> verifica tipo usuario (super_admin o clinic_member)
2. Super admin -> /admin
3. Clinic member -> /dashboard (agenda, pacientes)

## Implementados
- [x] Login unico con deteccion de tipo de usuario
- [x] Super Admin Panel (Dashboard, Clinicas CRUD, Usuarios, Catalogos)
- [x] Catalogos con importacion masiva (Medicamentos, Lab, CIE-10)
- [x] Precarga 672 codigos CIE-10
- [x] Login UI con branding Cortexia Medical
- [x] **MIGRACION MongoDB -> Supabase PostgreSQL** (10 Abril 2026)
- [x] **MODULO DE AGENDA COMPLETO** (16 Abril 2026):
  - [x] Dashboard clinica con KPIs y citas del dia
  - [x] Vista semanal Lun-Sab configurable por clinica
  - [x] Bloques de citas con colores por estado
  - [x] Formulario de nueva cita con buscador autocomplete de pacientes
  - [x] Creacion rapida de pacientes desde el formulario
  - [x] Detalle de cita con cambio de estados
  - [x] Filtros por medico, estado y nombre de paciente
  - [x] Navegacion entre semanas + boton Hoy
  - [x] Validacion de conflictos de horario
  - [x] Validacion de horario de clinica
  - [x] Supabase Realtime para actualizaciones en vivo
  - [x] Pagina de Pacientes (CRUD basico)
  - [x] **DRAG & DROP para reprogramar citas** (16 Abril 2026)

## Pendientes
- [ ] Importacion CSV para catalogos
- [ ] Recetas medicas
- [ ] Reportes y estadisticas avanzadas

## Credenciales
Ver `/app/memory/test_credentials.md`
