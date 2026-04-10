# Panel de Super Administrador - CRM Clinicas

## Problem Statement Original
Panel de Super Administrador para plataforma de CRM de clinicas medicas. El super admin crea clinicas y asigna administradores iniciales. Las clinicas NO se registran solas.

## Arquitectura

### Stack Tecnologico
- **Frontend**: React 19 + Tailwind CSS + Shadcn UI
- **Backend**: FastAPI (Python 3.11)
- **Base de datos**: Supabase PostgreSQL (datos + autenticacion)
- **Diseno**: Aspecto tecnologico con sidebar morado oscuro (#120B29)

### Estructura de Base de Datos (Supabase PostgreSQL)
- `super_admins`: id(uuid), user_id(uuid), first_name, last_name, email, phone, is_active, created_at, updated_at
- `clinics`: id(uuid), name, slug, country, city, address, phone, email, timezone, schedule_start, schedule_end, slot_duration, working_days, plan(enum), max_users, max_patients, max_storage_mb, is_active, created_at, updated_at
- `clinic_members`: id(uuid), clinic_id(fk->clinics), user_id(fk->auth.users), role(enum), first_name, last_name, specialty, license_number, phone, is_active, created_at, updated_at
- `patients`: id(uuid), clinic_id(fk), first_name, last_name, date_of_birth, gender, etc.
- `medications`: id(uuid), clinic_id, generic_name, brand_name, presentations(text[]), category, is_active, search_vector, created_at
- `lab_studies`: id(uuid), clinic_id, name, category, preparation, is_active, sort_order, created_at
- `icd10_codes`: id(int auto-increment), code, description_en, description_es, category, is_common, search_vector

### Flujo de Autenticacion
1. Login unico en `/login` para todos los usuarios
2. Backend verifica en Supabase Auth
3. Despues del login, verifica tipo de usuario:
   - Si esta en `super_admins` -> Redirige a `/admin`
   - Si esta en `clinic_members` -> Redirige a `/dashboard`
   - Si no esta en ninguna -> Muestra error "Sin acceso"

## Core Requirements

### Implementados
- [x] Login unico con deteccion de tipo de usuario
- [x] Panel de Super Admin con sidebar morado oscuro
- [x] Dashboard con KPIs (clinicas activas/inactivas, usuarios, pacientes)
- [x] Tabla de clinicas recientes en dashboard
- [x] Gestion de Clinicas (CRUD completo)
- [x] Gestion de Usuarios (cambiar rol, activar/desactivar, resetear password, mover clinica)
- [x] Gestion de Catalogos (Medicamentos, Estudios Lab, CIE-10)
- [x] Importacion masiva por texto para todos los catalogos
- [x] Precarga de 672 codigos CIE-10 comunes
- [x] Login UI personalizado (branding Cortexia Medical, fondo navy, grid teal animado)
- [x] **MIGRACION DE MONGODB A SUPABASE POSTGRESQL** (completada 10 Abril 2026)

### Pendientes
- [ ] Dashboard de Clinica (para clinic_members)
- [ ] Gestion de pacientes dentro de clinica
- [ ] Gestion de citas
- [ ] Recetas medicas
- [ ] Importacion CSV para catalogos

## Credenciales de Prueba
Ver `/app/memory/test_credentials.md`
