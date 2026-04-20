# Panel de Super Administrador + CRM Clinicas

## Problem Statement Original
CRM de clinicas medicas completo con Super Admin, Agenda, Pacientes, Historia Clinica, Recetas, Ordenes Lab, Google Calendar, Configuracion, y Dashboard principal.

## Arquitectura
- **Frontend**: React 19 + Tailwind CSS + Shadcn UI + React Hook Form + Zod
- **Backend**: FastAPI (Python 3.11) + reportlab (PDF) + google-api-python-client
- **Base de datos**: Supabase PostgreSQL
- **Almacenamiento**: Supabase Storage (bucket: patient-files)
- **Integraciones**: Google Calendar OAuth2

## Implementados
- [x] Login unico + Super Admin Panel completo
- [x] Migracion MongoDB -> Supabase PostgreSQL
- [x] **MODULO DE AGENDA** - Day/Week/Month, DnD, colores medico
- [x] **MODULO DE PACIENTES** - CRUD completo, archivos, edicion in-profile
- [x] **MODULO HISTORIA CLINICA** - Secciones colapsables, CIE-10, timeline, addendum
- [x] **PLANTILLAS DE CONSULTA** - 10 globales + CRUD por clinica
- [x] **MODULO RECETAS** - Formulario, PDF, recetas recurrentes (duplicar)
- [x] **MODULO ORDENES LAB** - Formulario, estudios por categoria, PDF
- [x] **GOOGLE CALENDAR SYNC** - OAuth2, sync bidireccional
- [x] **PANEL DE CONFIGURACION** - Clinica, Equipo, Recetas, Plan, Integraciones
- [x] **DASHBOARD PRINCIPAL** (20 Abril 2026):
  - [x] Saludo personalizado con nombre del medico y fecha
  - [x] 4 cards de resumen: Citas hoy (pendientes), Pacientes nuevos mes, Recetas emitidas mes, Proxima cita
  - [x] Agenda del dia: timeline compacta con estado visual, motivo, doctor, boton consulta rapida
  - [x] Actividad reciente: log de ultimas acciones con filtro (Todo/Citas/Recetas/Pacientes)
  - [x] Pacientes recientes: ultimos 5 con avatar y link al perfil
  - [x] Acciones rapidas: 4 botones (Nueva cita, Nuevo paciente, Nueva receta, Orden lab)
  - [x] Auto-refresh cada 60 segundos

## Pendientes
- [ ] Importacion CSV para catalogos - P2
- [ ] Reportes y estadisticas avanzadas - P2
- [ ] Notificaciones/recordatorios de citas - P2
- [ ] Integracion real WhatsApp via n8n - P2
- [ ] Integracion Stripe/dLocal para facturacion - P2
- [ ] Refactoring: dividir server.py en routers

## Credenciales
Ver `/app/memory/test_credentials.md`
