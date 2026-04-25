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
- [x] **MODULO INVENTARIO** (25 Abril 2026):
  - [x] Ruta /dashboard/inventario + sidebar item con feature flag 'inventory'
  - [x] Tab Productos: CRUD + categorias + busqueda + filtros + paginacion + margenes
  - [x] Tab Stock: por sucursal, alertas (bajo/vencimiento), ajustes con motivos
  - [x] Tab Compras: ordenes con multiples items, recepcion automatica de stock + lotes
  - [x] Tab Movimientos: paginado, filtros por tipo y sucursal
  - [x] Tab Proveedores: CRUD completo
  - [x] Backend hardened: defensive maybe_single() guards en todo el modulo
  - [x] Bug fix CRITICO: PO recibida ya NO duplica stock (trigger DB hace el upsert)
  - [x] Bug fix HIGH: adjust_stock funciona sin row inventory_stock previa
  - [x] Tested via testing_agent_v3_fork iteration_11 + curl post-fix verification

- [x] **MODULO VENTAS / POS** (25 Abril 2026):
  - [x] Ruta /dashboard/ventas + feature flag 'sales' + 4 tabs (POS, Ventas del día, Servicios, Sesiones de caja)
  - [x] Apertura/cierre de caja con resumen, multiples metodos de pago, cambio, saldo pendiente, anulacion con movimiento reverso, PDF recibo/factura via reportlab
  - [x] Bug fixes iter12: payment_method enum + clinics.nit + rollback transaccional
  - [x] Tested iter12+13 (100% backend 31/31, 100% frontend)

- [x] **MODULO CUENTAS POR COBRAR** (25 Abril 2026):
  - [x] Ruta /dashboard/cuentas + feature flag 'accounts_receivable'
  - [x] AR auto-creada cuando venta queda con saldo
  - [x] Tab Cuentas: 4 cards (total, pacientes, vencidas, vencen 30d), tabla con traffic light, filtros
  - [x] Modal detalle: paciente, venta, items, pagos, plan de cuotas
  - [x] Registrar abono: sincroniza venta + AR
  - [x] Plan de pagos: N cuotas (max 60), frequency weekly/biweekly/monthly (true calendar months)
  - [x] Tab Cuotas: lista pendientes con days_to_due
  - [x] Tab Antiguedad: 5 buckets (current/1-30/31-60/61-90/90+)
  - [x] Tested iteration_14 (100% backend 16/16, 100% frontend)

- [x] **MODULO GASTOS** (25 Abril 2026):
  - [x] Ruta /dashboard/gastos + feature flag 'expenses'
  - [x] Tab Gastos: 4 cards (mes actual, mes anterior con delta%, top categoría, pendientes), tabla con filtros (fechas, categoría, sucursal, estado, busqueda), form CRUD completo
  - [x] 10 categorías enum: rent, utilities, salaries, supplies, equipment, marketing, professional_services, taxes, maintenance, other (con labels en español)
  - [x] Total auto-calculado (amount + tax_amount), validación enum (categoría, payment_method, payment_status)
  - [x] Adjuntos PDF/PNG/JPG/WEBP (max 10MB) a Supabase Storage {clinic_id}/expenses/{expense_id}/
  - [x] Autocomplete de proveedor desde catalogo de inventory/suppliers
  - [x] Tab Por categoría: barras de progreso con %, total del periodo, filtros sucursal+rango
  - [x] Tab Por proveedor: tabla con totales por supplier_id resueltos a nombre
  - [x] Eliminar restringido a clinic_admin
  - [x] Tested iteration_15 (100% backend 15/15, 100% frontend E2E)

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
