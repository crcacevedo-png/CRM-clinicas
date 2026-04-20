# Panel de Super Administrador + CRM Clinicas

## Problem Statement Original
CRM de clinicas medicas con Super Admin, Agenda, Pacientes, Historia Clinica, Recetas con PDF, Ordenes Lab con PDF, y Google Calendar sync.

## Arquitectura
- **Frontend**: React 19 + Tailwind CSS + Shadcn UI + React Hook Form + Zod
- **Backend**: FastAPI (Python 3.11) + reportlab (PDF) + google-api-python-client
- **Base de datos**: Supabase PostgreSQL
- **Almacenamiento**: Supabase Storage (bucket: patient-files)
- **Integraciones**: Google Calendar OAuth2

### Tablas
- `super_admins`, `clinics`, `clinic_members`, `patients`, `appointments` (con google_event_id)
- `medical_records`, `consultation_templates`
- `prescriptions`, `prescription_items`, `medications`
- `lab_orders`, `lab_order_items`, `lab_studies`
- `user_integrations`: id, user_id, provider, access_token(encrypted), refresh_token(encrypted), token_expires_at, is_active, calendar_id, metadata
- `icd10_codes`

## Implementados
- [x] Login + Super Admin Panel completo
- [x] Migracion MongoDB -> Supabase PostgreSQL
- [x] **MODULO DE AGENDA** - Day/Week/Month, DnD, colores medico
- [x] **MODULO DE PACIENTES** - CRUD completo, archivos, edicion in-profile
- [x] **MODULO HISTORIA CLINICA** - Secciones colapsables, CIE-10, timeline, addendum
- [x] **PLANTILLAS DE CONSULTA** - 10 globales + CRUD por clinica
- [x] **MODULO RECETAS** - Formulario, PDF, recetas recurrentes (duplicar)
- [x] **MODULO ORDENES LAB** - Formulario, estudios por categoria, PDF
- [x] Tabs de Recetas y Ordenes Lab en perfil del paciente con datos reales
- [x] **GOOGLE CALENDAR SYNC** (20 Abril 2026):
  - [x] OAuth2 con Google (flujo completo auth URL → callback → tokens)
  - [x] Tokens encriptados con Fernet en user_integrations
  - [x] Refresh automatico de tokens expirados
  - [x] Pagina Configuracion > Mi cuenta con boton "Conectar Google Calendar"
  - [x] Estado conectado: toggle sync, seleccion de calendario, desconectar
  - [x] Al crear cita → crea evento en Google Calendar (titulo: "Cita: {paciente}")
  - [x] Al modificar cita → actualiza evento en Google Calendar
  - [x] Al cancelar cita → elimina evento de Google Calendar
  - [x] NO sincroniza datos medicos sensibles (solo nombre y hora)
  - [x] Configuracion por medico (cada uno conecta su propio GCal)
  - [x] Item "Configuracion" en sidebar

## Pendientes
- [ ] Importacion CSV para catalogos - P2
- [ ] Reportes y estadisticas avanzadas - P2
- [ ] Notificaciones/recordatorios de citas - P2
- [ ] Integracion real WhatsApp via n8n - P2
- [ ] Refactoring: dividir server.py en routers

## Credenciales
Ver `/app/memory/test_credentials.md`
