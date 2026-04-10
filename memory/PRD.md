# Panel de Super Administrador - CRM Clínicas

## Problem Statement Original
Panel de Super Administrador para plataforma de CRM de clínicas médicas. El super admin crea clínicas y asigna administradores iniciales. Las clínicas NO se registran solas.

## Arquitectura

### Stack Tecnológico
- **Frontend**: React 19 + Tailwind CSS + Shadcn UI
- **Backend**: FastAPI (Python 3.11)
- **Base de datos**: MongoDB (datos) + Supabase Auth (autenticación)
- **Diseño**: Aspecto tecnológico con sidebar morado oscuro (#120B29)

### Estructura de Base de Datos (MongoDB)
- `super_admins`: Usuarios con acceso de super admin
- `clinics`: Clínicas registradas en la plataforma
- `clinic_members`: Miembros de cada clínica con roles
- `patients`: Pacientes registrados
- `medications`: Catálogo global de medicamentos
- `lab_studies`: Catálogo global de estudios de laboratorio
- `icd10_codes`: Códigos CIE-10

### Flujo de Autenticación
1. Login único en `/login` para todos los usuarios
2. Backend verifica en Supabase Auth
3. Después del login, verifica tipo de usuario:
   - Si está en `super_admins` → Redirige a `/admin`
   - Si está en `clinic_members` → Redirige a `/dashboard`
   - Si no está en ninguna → Muestra error "Sin acceso"

## User Personas

### Super Admin (Dueño de la plataforma)
- Crea y gestiona clínicas
- Asigna administradores iniciales a cada clínica
- Gestiona catálogos globales (medicamentos, estudios, CIE-10)
- Ve estadísticas generales de toda la plataforma

### Clinic Admin (Administrador de clínica)
- Gestiona su clínica específica
- Gestiona miembros de su clínica
- Accede al dashboard de clínica (próximamente)

## Core Requirements

### Implementados ✅
- [x] Login único con detección de tipo de usuario
- [x] Panel de Super Admin con sidebar morado oscuro
- [x] Dashboard con KPIs (clínicas activas/inactivas, usuarios, pacientes)
- [x] Tabla de clínicas recientes en dashboard
- [x] Gestión de Clínicas (CRUD completo)
  - [x] Lista con filtros (país, plan, estado)
  - [x] Crear clínica + admin inicial en un modal
  - [x] Mostrar credenciales al crear
  - [x] Detalle de clínica con edición
  - [x] Activar/desactivar clínica
  - [x] Agregar usuarios a clínica
- [x] Gestión de Usuarios
  - [x] Lista con filtros (clínica, rol, estado)
  - [x] Cambiar rol
  - [x] Activar/desactivar
  - [x] Resetear contraseña
  - [x] Mover a otra clínica
- [x] Gestión de Catálogos
  - [x] Tab Medicamentos (CRUD + importación masiva por texto)
  - [x] Tab Estudios de Laboratorio (CRUD + importación masiva por texto)
  - [x] Tab Códigos CIE-10 (CRUD + toggle común + importación masiva)
  - [x] Precarga de 660 códigos CIE-10 comunes (endpoint /api/admin/catalogs/icd10/seed)
- [x] Login UI personalizado (branding Cortexia Medical, fondo navy, grid teal animado)
- [x] Logout funcional
- [x] Super admin se crea automáticamente al iniciar backend

### Pendientes (Próxima fase)
- [ ] Dashboard de Clínica (para clinic_members)
- [ ] Gestión de pacientes dentro de clínica
- [ ] Gestión de citas
- [ ] Recetas médicas
- [ ] Log de actividad detallado
- [ ] Configuración del sistema (página placeholder)
- [ ] Estadísticas avanzadas con gráficos

## What's Been Implemented

### Fecha: 10 de Abril 2026
- Implementación completa del Panel de Super Admin
- Integración con Supabase Auth para autenticación
- Backend FastAPI con endpoints para todas las funcionalidades
- Frontend React con diseño tecnológico
- Testing completo (100% backend, 100% frontend)

## Prioritized Backlog

### P0 (Crítico) - Completado ✅
- Login y autenticación
- Dashboard de super admin
- CRUD de clínicas
- CRUD de usuarios
- CRUD de catálogos

### P1 (Alta prioridad)
- Dashboard de clínica para clinic_members
- Gestión de pacientes
- Mejoras en la UI/UX

### P2 (Media prioridad)
- Citas y agenda
- Recetas médicas
- Reportes y estadísticas

## Next Tasks
1. Implementar dashboard de clínica para clinic_members
2. Añadir gestión de pacientes dentro de cada clínica
3. Implementar sistema de citas/agenda
4. Agregar gráficos y estadísticas avanzadas
5. Mejorar la página de configuración

## Credenciales de Prueba
Ver `/app/memory/test_credentials.md` para credenciales actualizadas.
