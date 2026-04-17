# Panel de Super Administrador + CRM Clinicas

## Problem Statement Original
Panel de Super Administrador para plataforma de CRM de clinicas medicas. Super admin, Agenda, Pacientes, Historia Clinica, Recetas con PDF, Ordenes de Laboratorio con PDF.

## Arquitectura
- **Frontend**: React 19 + Tailwind CSS + Shadcn UI + React Hook Form + Zod
- **Backend**: FastAPI (Python 3.11) + reportlab (PDF)
- **Base de datos**: Supabase PostgreSQL
- **Almacenamiento**: Supabase Storage (bucket: patient-files)

### Tablas
- `super_admins`, `clinics`, `clinic_members`, `patients`, `appointments`
- `medical_records`, `consultation_templates`
- `prescriptions`, `prescription_items`, `medications` (63)
- `lab_orders`, `lab_order_items`, `lab_studies` (82 en 12 categorias)
- `icd10_codes` (672)

## Implementados
- [x] Login unico + Super Admin Panel completo
- [x] Migracion MongoDB -> Supabase PostgreSQL
- [x] **MODULO DE AGENDA** - Day/Week/Month, DnD, colores medico
- [x] **MODULO DE PACIENTES** - CRUD completo, archivos Supabase Storage
- [x] **MODULO HISTORIA CLINICA** - Formulario con secciones colapsables, signos vitales, CIE-10, timeline, addendum
- [x] **PLANTILLAS DE CONSULTA** - 10 globales + CRUD por clinica
- [x] **MODULO RECETAS MEDICAS** - Formulario, PDF con reportlab, recetas recurrentes (duplicar)
- [x] **MODULO ORDENES LABORATORIO** (17 Abril 2026):
  - [x] Lista paginada con filtro estado (Pendiente/Completada/Cancelada)
  - [x] Formulario con autocomplete pacientes
  - [x] Radio buttons prioridad (Rutina/Urgente con estilo rojo)
  - [x] 82 estudios en 12 categorias con checkboxes agrupados
  - [x] Instrucciones de preparacion visibles bajo cada estudio
  - [x] Filtro de busqueda de estudios (client-side)
  - [x] Diagnostico presuntivo e indicaciones especiales
  - [x] PDF con header clinica, medico, paciente, estudios por categoria, preparaciones, firma
  - [x] PDF almacenado en Supabase Storage
  - [x] Acceso desde perfil paciente (tab Ordenes Lab)
  - [x] Item "Laboratorio" en sidebar

## Pendientes
- [ ] Importacion CSV para catalogos - P2
- [ ] Reportes y estadisticas avanzadas - P2
- [ ] Notificaciones/recordatorios de citas - P2
- [ ] Integracion real WhatsApp via n8n - P2
- [ ] Refactoring: dividir server.py en routers

## Credenciales
Ver `/app/memory/test_credentials.md`
