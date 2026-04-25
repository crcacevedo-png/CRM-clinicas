# Panel de Super Administrador + CRM Clinicas

## Problem Statement Original
CRM de clinicas medicas con Feature Flags, Planes, y Multi-branch.

## Arquitectura
- **Frontend**: React 19 + Tailwind CSS + Shadcn UI
- **Backend**: FastAPI (Python 3.11) + reportlab + google-api-python-client
- **Base de datos**: Supabase PostgreSQL
- **Almacenamiento**: Supabase Storage

## Implementados
- [x] Login + Super Admin Panel
- [x] Migracion MongoDB -> Supabase PostgreSQL
- [x] **MODULO DE AGENDA** - Day/Week/Month, DnD, colores medico
- [x] **MODULO DE PACIENTES** - CRUD, archivos, edicion in-profile
- [x] **MODULO HISTORIA CLINICA** - Secciones colapsables, CIE-10, timeline, addendum
- [x] **PLANTILLAS DE CONSULTA** - 10 globales + CRUD por clinica
- [x] **MODULO RECETAS** - Formulario, PDF, recetas recurrentes
- [x] **MODULO ORDENES LAB** - Formulario, estudios, PDF
- [x] **GOOGLE CALENDAR SYNC** - OAuth2, sync bidireccional
- [x] **PANEL CONFIGURACION** - Clinica, Equipo, Recetas, Plan, Integraciones
- [x] **DASHBOARD PRINCIPAL** - Cards, agenda dia, actividad, acciones rapidas
- [x] **SISTEMA FEATURE FLAGS** - FeatureProvider, useFeature, FeatureGate, sidebar dinamico, admin planes
- [x] **MULTI-BRANCH / SUCURSALES** (25 Abril 2026):
  - [x] BranchProvider + useBranch context global
  - [x] Pagina /dashboard/sucursales con grid de sucursales (nombre, direccion, estado, principal)
  - [x] Crear/Editar sucursal: nombre, codigo, direccion, telefono, horario, main toggle, activa
  - [x] Gestionar usuarios por sucursal con checkboxes y estrella para principal
  - [x] Branch selector en sidebar header con dropdown
  - [x] Verificacion limite plan (max_branches)
  - [x] FeatureGate: muestra "Enterprise" cuando multi_branch no esta activo
  - [x] Item "Sucursales" en sidebar (condicionado por feature)
  - [x] clinic_feature_overrides para activar multi_branch individualmente

## Pendientes
- [ ] Filtrar queries de Agenda/Inventario/Ventas por branch_id activa - P1
- [ ] Dropdown sucursal en formulario de nueva cita - P1
- [ ] Importacion CSV para catalogos - P2
- [ ] Reportes y estadisticas - P2
- [ ] Notificaciones/recordatorios - P2
- [ ] WhatsApp via n8n - P2
- [ ] Stripe/dLocal facturacion - P2
- [ ] Refactoring: dividir server.py en routers

## Credenciales
Ver `/app/memory/test_credentials.md`
