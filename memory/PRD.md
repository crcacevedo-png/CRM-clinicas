# Panel de Super Administrador + CRM Clinicas

## Problem Statement Original
CRM de clinicas medicas con sistema de Feature Flags basado en planes.

## Arquitectura
- **Frontend**: React 19 + Tailwind CSS + Shadcn UI + React Hook Form + Zod
- **Backend**: FastAPI (Python 3.11) + reportlab (PDF) + google-api-python-client
- **Base de datos**: Supabase PostgreSQL
- **Almacenamiento**: Supabase Storage (bucket: patient-files)
- **Integraciones**: Google Calendar OAuth2

## Implementados
- [x] Login unico + Super Admin Panel
- [x] Migracion MongoDB -> Supabase PostgreSQL
- [x] **MODULO DE AGENDA** - Day/Week/Month, DnD, colores medico
- [x] **MODULO DE PACIENTES** - CRUD completo, archivos, edicion in-profile
- [x] **MODULO HISTORIA CLINICA** - Secciones colapsables, CIE-10, timeline, addendum
- [x] **PLANTILLAS DE CONSULTA** - 10 globales + CRUD por clinica
- [x] **MODULO RECETAS** - Formulario, PDF, recetas recurrentes
- [x] **MODULO ORDENES LAB** - Formulario, estudios por categoria, PDF
- [x] **GOOGLE CALENDAR SYNC** - OAuth2, sync bidireccional
- [x] **PANEL DE CONFIGURACION** - Clinica, Equipo, Recetas, Plan, Integraciones
- [x] **DASHBOARD PRINCIPAL** - Cards resumen, agenda dia, actividad, acciones rapidas
- [x] **SISTEMA FEATURE FLAGS Y PLANES** (25 Abril 2026):
  - [x] FeatureProvider global con hook useFeature(code) retorna true/false
  - [x] FeatureGate component que muestra lock + upgrade prompt
  - [x] Sidebar dinamico: muestra/oculta items segun features activos
  - [x] 16 features definidos en tabla: agenda, patients, prescriptions, lab_orders, medical_records, inventory, sales, accounts_receivable, expenses, financial_reports, google_calendar, whatsapp, multi_branch, commissions, clinical_reports, fiscal_invoicing
  - [x] 3 planes: Basic ($29), Professional ($79), Enterprise ($199)
  - [x] Admin /admin/planes: cards con precios y limites, editar plan con checkboxes de features
  - [x] Admin detalle clinica: seccion Plan y Modulos con selector plan + toggles override
  - [x] clinic_feature_overrides para activaciones individuales por clinica

## Pendientes
- [ ] Importacion CSV para catalogos - P2
- [ ] Reportes y estadisticas avanzadas - P2
- [ ] Notificaciones/recordatorios de citas - P2
- [ ] Integracion real WhatsApp via n8n - P2
- [ ] Integracion Stripe/dLocal para facturacion - P2
- [ ] Refactoring: dividir server.py en routers

## Credenciales
Ver `/app/memory/test_credentials.md`
