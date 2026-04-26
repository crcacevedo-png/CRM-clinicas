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

- [x] **MODULO COMISIONES** (25 Abril 2026):
  - [x] Ruta /dashboard/comisiones + feature flag 'commissions' (habilitada via clinic_feature_overrides)
  - [x] Tab Liquidación: 3 cards (total generado, pagadas, pendientes) + tabla por médico con base/ganadas/pagadas/pendientes + drill-down por médico con checkboxes para bulk-pay + reporte PDF exportable agrupado por médico
  - [x] Tab Reglas: CRUD completo de commission_settings (médico, applies_to: all_consultations/all_products/service/product, calculation_type: percentage/fixed, valor, vigencia, toggle activa, eliminar admin-only)
  - [x] Auto-cálculo en create_sale: hook tras commit que evalúa todas las reglas activas del doctor_id de la venta y crea filas en commissions_earned por cada item que matchee (con prioridad: específico > general)
  - [x] Bulk pay: marca status=paid + paid_at + payment_reference; rechaza double-pay
  - [x] Validación enum: applies_to, calculation_type, percentage ≤ 100, requeridos según contexto
  - [x] Reglas ordenadas por created_at desc en evaluación → priority determinístico
  - [x] Tested iteration_16 (100% backend 17/17, 100% frontend E2E)

- [x] **MODULO REPORTES FINANCIEROS** (25 Abril 2026):
  - [x] Ruta /dashboard/reportes + feature 'financial_reports' (ya activo)
  - [x] Tab Resumen ejecutivo: 8 KPI cards (ingresos, gastos, utilidad neta+margen, CxC pendiente, ticket promedio, pacientes nuevos, citas, ventas) con delta% vs período anterior + 4 gráficas recharts (LineChart 12m income vs expenses, BarChart método pago, PieChart categorías gasto, BarChart horizontal sucursal)
  - [x] Tab Ingresos: total + tendencia (day/week/month) + Top 10 productos + Top 10 servicios + por médico + por método de pago + export CSV
  - [x] Tab Estado de resultados (P&L): tabla completa con comparación período actual vs anterior y Δ%, COGS auto-calculado de products.cost_price, comisiones, utilidad neta destacada, exportable a PDF profesional via reportlab
  - [x] Tab Inventario: valoración cost+retail+margen potencial por sucursal y categoría, productos sin movimiento (30/60/90 días), top vendidos (90 días), próximos a vencer, movimientos del periodo
  - [x] Tab Por sucursal: matriz comparativa (ingresos, gastos, utilidad, ventas, citas, ticket promedio) + 2 gráficas BarChart
  - [x] Selector de período (mes actual/anterior/trimestre/año/custom) compartido en todos los tabs
  - [x] 6 endpoints backend (/executive-summary, /income, /pnl, /pnl-pdf, /inventory, /by-branch) con auth gating
  - [x] Quick wins: KpiCard formato counts sin decimales, branch dict pre-fetch (N+1 fix), data-testid pnl-pdf-btn
  - [x] Tested iteration_17 (100% backend 21/21, 100% frontend E2E completo)

- [x] **REFACTOR: server.py modularizado** (26 Abril 2026):
  - [x] **Fase 1**: server.py reducido de 6060 → 3472 líneas (-43%); 6 routers extraídos
  - [x] **Fase 2** (26 Abril 2026): server.py reducido de 3472 → **126 líneas** (-98% del original)
  - [x] Creado `/app/backend/core.py` (280 líneas): Supabase clients (`supabase_user`, `supabase_admin`, `supabase_anon`, `sdb`), Settings, logger, helpers (`generate_password`, `now_iso`, `get_plan_limits`, `parse_presentations`, `get_auth_users_map`, `enrich_member`), auth deps (`get_current_user`, `require_super_admin`, `require_clinic_member`, `require_clinical_role`, `CLINICAL_ROLES`) y todos los modelos Pydantic compartidos
  - [x] 18 routers totales en `/app/backend/routes/`: auth, super_admin, catalogs, clinic_settings, branches, feature_flags, patients, appointments, medical_records, prescriptions, lab_orders, google_calendar, inventory, expenses, commissions, sales, accounts_receivable, reports
  - [x] `server.py` ahora solo contiene FastAPI app, startup_event, /health, /generate-password y mount de routers
  - [x] Eliminado patrón `from server import ...` que causaba circular imports
  - [x] Bug fix testing agent: `require_clinical_role` faltante en prescriptions/lab_orders → resuelto promoviendo helper a `core.py`
  - [x] Tested iteration_19: **44/44 PASS** suite de regresión + endpoints E2E verificados con curl

## Pendientes
- [ ] Filtrar queries de Agenda/Inventario/Ventas por branch_id activa - P1
- [ ] Dropdown sucursal en formulario de nueva cita - P1
- [ ] Endpoints faltantes detectados por testing agent (P2): /api/auth/me, /api/clinic/expenses/categories (alias de /by-category), /api/clinic/sales/dashboard (alias de /daily-summary)
- [ ] Mejora 422-vs-500 en path params no-UUID (sales/{id}, prescriptions/{id}, lab-orders/{id}, patients/{id}) - P2
- [ ] Importacion CSV para catalogos - P2
- [ ] Notificaciones/recordatorios - P2
- [ ] WhatsApp via n8n - P2
- [ ] Stripe/dLocal facturacion - P2

## Credenciales
Ver `/app/memory/test_credentials.md`
