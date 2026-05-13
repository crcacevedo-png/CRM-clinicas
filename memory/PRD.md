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
  - [x] Creado `/app/backend/core.py` (280 líneas): Supabase clients (`supabase_user`, `supabase_admin`, `supabase_anon`, `sdb`), Settings, logger, helpers (`generate_password`, `now_iso`, `get_plan_limits`, `parse_presentations`, `get_auth_users_map`, `enrich_member`, `get_clinic_features`), auth deps (`get_current_user`, `require_super_admin`, `require_clinic_member`, `require_clinical_role`, `CLINICAL_ROLES`) y todos los modelos Pydantic compartidos
  - [x] 18 routers totales en `/app/backend/routes/`: auth, super_admin, catalogs, clinic_settings, branches, feature_flags, patients, appointments, medical_records, prescriptions, lab_orders, google_calendar, inventory, expenses, commissions, sales, accounts_receivable, reports
  - [x] `server.py` ahora solo contiene FastAPI app, startup_event, /health, /generate-password y mount de routers
  - [x] Eliminado patrón `from server import ...` que causaba circular imports
  - [x] Bug fix testing agent: `require_clinical_role` faltante en prescriptions/lab_orders → resuelto promoviendo helper a `core.py`
  - [x] Tested iteration_19: **44/44 PASS** suite de regresión + endpoints E2E verificados con curl

- [x] **DASHBOARD ROL-AWARE (PROMPT A9)** (26 Abril 2026):
  - [x] Backend `/api/clinic/dashboard` extendido: nuevos campos `role`, `features`, `admin_stats`, `alerts`, `income_chart`, `my_commissions_month` (todos backwards-compatible)
  - [x] Helper `core.get_clinic_features(clinic_id)` reutilizable (plan + overrides) extraído del router de feature_flags
  - [x] Cards condicionales por feature: sales→ventas hoy + pendiente cobro; inventory→stock bajo + próximos a vencer; expenses→gastos del mes; commissions→comisiones del mes
  - [x] Sección "Alertas y notificaciones" (5 tipos): low_stock, expiring (60d), ar_overdue, installment_overdue, cash_session abierta >18h, cada una con link directo a la página correspondiente
  - [x] Gráfica `recharts` LineChart de ingresos diarios del mes (solo si feature `financial_reports` activo)
  - [x] **Vista por rol**:
    - doctor: dashboard simplificado — sus citas del día, sus pacientes recientes, sus comisiones del mes (si aplica)
    - clinic_admin / cashier: dashboard completo con admin stats + alertas + gráfica + acciones rápidas (incluyendo "Nueva venta")
    - assistant / receptionist: intermedio — agenda + tarjeta de caja + alertas
  - [x] Frontend reescrito con sub-componentes: AdminStatsRow, AlertsCard, IncomeChartCard, MyCommissionsCard, CashSessionCard, badge de rol visible
  - [x] Tested iteration_20: 100% backend (19/19), 100% frontend Playwright (16/16 asserts), zero console errors

- [x] **MULTI-BRANCH FILTER P1** (26 Abril 2026):
  - [x] Backend: `AppointmentCreate` y `AppointmentUpdate` aceptan `branch_id` opcional
  - [x] Backend: `GET /api/clinic/appointments` filtra por `branch_id` query param
  - [x] Backend: `POST /api/clinic/appointments` y `PUT /api/clinic/appointments/{id}` persisten `branch_id` y validan que pertenezca al `clinic_id` del miembro (400 si inválido)
  - [x] Backend: chequeo de **conflictos del médico ahora es scoped por sucursal** — un mismo doctor puede tener citas simultáneas en sucursales distintas; mensaje 409 actualizado a "...en esta sucursal"
  - [x] Frontend: `AgendaPage` envía automáticamente `branch_id=<activeBranch.id>` cuando `multi_branch` está activo y hay sucursal seleccionada
  - [x] Frontend: `NewAppointmentModal` muestra dropdown de sucursal cuando `multi_branch` está activo (default = activeBranch o sucursal principal)
  - [x] Frontend: `InventoryPage.StockTab + MovementsTab` y `SalesPage.DailySalesTab + SessionsTab` defaultean su `branchFilter` a `activeBranch.id` con `useEffect` de sincronización
  - [x] Tested iteration_21: **74/74 PASS** (11 P1 + 44 phase2_refactor + 19 dashboard A9), Playwright E2E 6/6 integration assertions; cross-branch verificado con curl (MAIN+Z15 OK simultáneos, mismo MAIN+MAIN → 409)

- [x] **OPTIMIZACIÓN N+1** (26 Abril 2026):
  - [x] `GET /api/clinic/appointments`: dos batched fetches (`patients.in_(...)`, `clinic_members.in_(...)`) en lugar de 2N queries individuales
  - [x] `GET /api/clinic/dashboard`: batch único de patients/doctors al final del cómputo (citas hoy + next_apt + recent + activity), reduciendo ~50 queries a ~6 para una agenda típica
  - [x] `GET /api/clinic/dashboard` (low_stock): un solo `inventory_stock.in_('product_id', [...])` en lugar de 1 query/producto
  - [x] `GET /api/clinic/sales`: cuatro batched fetches (cashiers, branches, sale_items, payments) en lugar de 4N queries
  - [x] **Resultados latencia**: dashboard 1.65s, appointments 0.37s, sales 0.48s; suite de tests bajó de 43s → 32s (-25%)
  - [x] Suite regresión completa: **74/74 PASS** sin regresiones

- [x] **P2 + P3 BATCH** (26 Abril 2026):
  - [x] `GET /api/auth/me` añadido — devuelve identidad completa (user_type, role, name, clinic_id, member_id, specialty)
  - [x] Alias `GET /api/clinic/expenses/categories` (= `/by-category`) y `GET /api/clinic/sales/dashboard` (= `/daily-summary`) vía decoradores apilados
  - [x] Helper reusable `core.validate_uuid()` aplicado en path params de: `/sales/{id}`, `/sales/{id}/pdf-url` (heredado), `/prescriptions/{id}`, `/prescriptions/{id}/pdf-url`, `/lab-orders/{id}`, `/lab-orders/{id}/pdf-url`, `/patients/{id}`, `/medical-records/{id}` — UUIDs malformados ahora devuelven **422** (antes 500); UUIDs válidos pero no encontrados devuelven **404**
  - [x] `BranchContext.activeBranch` persiste en `localStorage.cliniccrm.activeBranchId` con prioridad: persisted > is_main > primer item
  - [x] React `unique key` warning en `AgendaPage` resuelto: `<>` Fragment dentro de `slots.map` reemplazado por `<Fragment key={...}>`
  - [x] **Bug fix descubierto por linter**: `routes/appointments.py` llamaba `sync_appointment_to_gcal` sin importarlo (F821); ahora importado localmente en los 3 callsites — Google Calendar sync vuelve a funcionar
  - [x] Tested iteration_22: **95/95 PASS** (21 nuevos P2/P3 + 74 baseline) en 50s; 0 console warnings/errors en frontend Playwright

- [x] **P2 BATCH OPTIÓN B** (26 Abril 2026):
  - [x] **Seeds doctor + receptionist** en `clinic_id=c0321ed8`:
    - `doctor.test@lasalud.gt / Test123456!` (member_id=dee8138c…) — Diana Ramírez, Medicina General
    - `recepcion.test@lasalud.gt / Test123456!` (member_id=7988bbdc…) — Rosa Hernández
    - Ambos valid login + `/auth/me` devuelve role correcto; `/clinic/dashboard` rol-aware verificado
  - [x] **Default branch_id en Reports/Expenses**: `ReportsPage` (4 tabs: summary, income, pnl, inventory) y `ExpensesPage` (ListTab, CategoryReportTab) ahora defaultean su `branchFilter` a `activeBranch.id` con `useEffect` de sincronización
  - [x] **CSV Import para catálogos** (super admin):
    - Backend: `POST /api/admin/catalogs/{medications|lab-studies|icd10}/import-csv?commit={true|false}` — auto-detect delimiter (,;), encoding fallback (utf-8/latin-1), header normalización, validación required-fields, dedup case-insensitive contra DB y dentro del archivo, batch insert 500 rows
    - Backend: `GET /api/admin/catalogs/{catalog}/csv-template` — devuelve plantilla CSV con headers + ejemplo
    - Backend: schema-aware — `icd10_codes` (sin clinic_id/created_at/is_active, id auto-int) recibe tratamiento separado; auto-fill de `description_en` desde `description_es` si no se proporciona
    - Frontend: `<CsvImportDialog>` reusable (drag-drop, dry-run preview con stats Total/Válidas/Duplicadas/Errores, tabla de errores fila-por-fila, vista previa de filas, botón download plantilla, surface de `commit_errors` separado del array de validation errors)
    - Botones "CSV" añadidos junto a "Importar (JSON)" en cada tab de `/admin/catalogos`
  - [x] **Bug fix descubierto por testing agent (iter 23)**: ICD10 commit fallaba 100% por columnas inexistentes (`created_at`, `is_active`) y tipo de id (int auto-increment, no UUID); solucionado con guard schema-aware + auto-fill `description_en` (NOT NULL constraint)
  - [x] Tested iteration_23: 99.1% (116/117) detectó el bug ICD10; iteration post-fix: **96/96 PASS** (44 phase2 + 19 dashboard + 11 branch_filter + 22 P2 CSV)

- [x] **IMPORTACIÓN MASIVA DE PACIENTES (CSV/XLSX)** (26 Abril 2026):
  - [x] Backend: `POST /api/clinic/patients-bulk/import?commit={true|false}` — acepta `.csv` (sniffer de delimitador, encoding fallback) y `.xlsx` (openpyxl con `data_only=True`); cap de tamaño 5 MB enforced server-side
  - [x] Backend: `GET /api/clinic/patients-bulk/template?format={csv|xlsx}` — plantilla descargable con headers + ejemplo (XLSX vía StreamingResponse)
  - [x] Backend: helpers `_parse_csv`, `_parse_xlsx`, `_parse_patient_row` — normalización de fechas (DD/MM/YYYY o ISO o objetos `date`), género (M/F/masculino/femenino → male/female), valores vacíos → null
  - [x] Backend: dedup por `national_id` case-insensitive con fallback composite (`first_name+last_name+phone`) cuando national_id está vacío; batch insert 500 rows; rutas en prefix `/clinic/patients-bulk/` para no chocar con `/clinic/patients/{id}` (validate_uuid)
  - [x] Backend: doctor + receptionist + clinic_admin pueden invocar (member-level access)
  - [x] Frontend: `<CsvImportDialog>` extendido con prop `acceptXlsx` y `ENDPOINT_MAP` para 4 catálogos; segundo botón "Excel" en sección de plantillas
  - [x] Frontend: botón "Importar" en `PatientsPage` (junto a "Nuevo paciente"), abre el dialog con `catalog="patients" acceptXlsx={true}`
  - [x] Tested iteration_24: **131/131 PASS** (14 nuevos patients_bulk + 117 regression total); cero bugs encontrados; testing agent confirmó parsing nativo de fechas Excel, normalización de género, dedup national_id + composite, plantillas CSV/XLSX, rechazo 400 en empty/.pdf/missing-required + 5MB cap; frontend Playwright 100% E2E flows OK

## Pendientes
- [ ] Recordatorios WhatsApp via n8n (24h/2h antes) - P1
- [ ] Stripe/dLocal facturacion (requiere keys del usuario) - P2

## Cambios recientes
- **2026-05-13 — Métricas de anuncios (Comunicación)**: tracking completo de vistas/cobertura.
  - **DB**: nueva tabla `announcement_views` (PK announcement+user, columnas `first_viewed_at`, `last_viewed_at`, `view_count`, `clinic_id`). RLS habilitado con políticas para que cada usuario gestione su propia fila.
  - **Backend**:
    - `POST /api/clinic/announcements/{id}/view` — idempotente, incrementa `view_count` y actualiza `last_viewed_at`.
    - `GET /api/admin/announcements` ampliado: cada fila trae `clinics_reached`, `users_viewed`, `total_views`, `users_dismissed`, `clinics_dismissed`.
    - `GET /api/admin/announcements/{id}/metrics` — endpoint detallado con totales (cobertura %, tasa de descarte %), breakdown por plan y por país, top-10 clínicas más recientes.
  - **Frontend**:
    - Banner clínico envía `POST .../view` automáticamente al renderizar (fire-and-forget, no bloquea UI).
    - Lista de anuncios super admin muestra métricas inline: `1 clínicas · 2 usuarios · 4 vistas · 0 descartado(s)`.
    - Nuevo botón **📊 Métricas** abre diálogo con KPIs (4 tarjetas), tabla por plan, tabla por país, top-10 clínicas recientes.
  - Verificado: 3 POST view → `view_count=3`, métricas detalladas correctas (1/7 elegibles = 14.3%, Professional 100%, Free 0%).

- **2026-05-13 — Submódulo Comunicación (Super Admin → Clínicas)**: anuncios globales con banner en dashboard de clínica.
  - **DB**: nuevas tablas `super_announcements` (con `segment_plans[]`, `segment_countries[]`, `segment_clinic_ids[]`, `severity`, `cta_label/url`, ventana `starts_at`/`ends_at`) y `announcement_dismissals` (PK: announcement_id+user_id). RLS habilitado + policies de lectura para `authenticated`.
  - **Backend** (`routes/announcements.py`):
    - Super admin: `GET/POST/PUT/DELETE /api/admin/announcements` (con contador de dismissals).
    - Clínica: `GET /api/clinic/announcements` (filtra por segmentación + ventana de tiempo + no dismissed por usuario). `POST /api/clinic/announcements/{id}/dismiss`.
    - Lógica de matching: plan-restricted, country-restricted, clinic-id-allowlist; null/empty = sin filtro.
  - **Frontend**:
    - Super admin: nueva página `/admin/comunicacion` con listado, creación/edición con segmentación (planes/países togglables), CTA, severidad (info/success/warning/critical), ventana de tiempo, activar/desactivar, contador de dismissals.
    - Clínicas: componente `AnnouncementsBanner` montado al inicio del dashboard. Estilos por severidad (azul/verde/ámbar/rojo), icono megaphone, botón CTA, botón X de descartar (optimistic UI + persistencia).
  - Verificado E2E (6/6 backend tests + smoke UI): global visible para todos, free-only oculto en clínica professional, premium-only visible para professional, dismiss persiste, doctor → 403, super admin → CRUD completo.

- **2026-05-10 — Firma anclada al pie de la receta**: la firma del doctor + nº colegiado + footer de la clínica ahora se dibujan vía `canvas` callback (`onFirstPage`/`onLaterPages`) en posición fija ~22mm del borde inferior, en lugar de fluir como `Spacer(20mm)` después de los medicamentos. Ventaja: el espacio entre los medicamentos y la firma se expande automáticamente al fondo del A5 — la firma siempre queda anclada al pie, dando aire visual y aspecto profesional independientemente de cuántos medicamentos tenga la receta.

- **2026-05-10 — Receta médica rediseñada (A5 landscape)**: 
  - Cambio de tamaño: `letter` → `landscape(A5)` (210×148mm) para imprimir más rápido y ahorrar papel.
  - Logo de la clínica reposicionado: ahora a la **derecha del header** (alineado con clinic name+contacto a la izquierda en una tabla 2 columnas).
  - Eliminado campo **DPI** del bloque de paciente.
  - Bloque doctor/paciente/fecha colapsado a **1 sola fila** (3 columnas) en lugar de 2 filas con etiquetas separadas, ocupando ~50% menos altura.
  - Reducidos paddings/spacers en todas las secciones (header, Rx, items, firma) — el contenido ahora cabe holgadamente en A5 horizontal.
  - Verificado: PDF de 595×419 pts con logo arriba-derecha, sin DPI, layout horizontal limpio.

- **2026-05-10 — Horarios partidos (split schedules)**: cada día puede tener múltiples bloques de horario (ej. 08:00-12:00 + 14:00-18:00 para clínicas con almuerzo).
  - **DB**: `working_hours[iso]` ahora acepta un array de bloques `[{start,end},...]` o un dict simple `{start,end}` (compatible con el formato anterior).
  - **Backend**: `core.get_clinic_day_hours()` retorna lista de bloques. Validación de citas verifica que `[start_time, end_time]` caiga dentro de **algún** bloque del día. Mensaje de error muestra todos los bloques disponibles.
  - **Frontend**: cada fila de día tiene botón "+ bloque" y "x" para eliminar; renderiza N inputs hora-inicio/fin por día.
  - **Verificado E2E (8/8)**: dentro de bloque mañana ✓, en lunch break entre bloques ✗400, dentro de bloque tarde ✓, supera fin del último bloque ✗400, día cerrado ✗400, bloque único 09-17 ✓, etc.

- **2026-05-10 — Horarios específicos por día de la semana**: Cada clínica puede ahora definir horario distinto para cada día (Lun-Dom) o cerrar días específicos.
  - **DB**: nueva columna `clinics.working_hours JSONB` (estructura `{"1":{"start":"08:00","end":"17:00"}, ...}` con keys 1-7 isoweekday). Día sin key = cerrado.
  - **Backend**: helper `core.get_clinic_day_hours(clinic, iso_dow)` con fallback a campos legacy (`schedule_start/end` + `working_days`). Validación de citas en `appointments.py` (create + update) ahora respeta el horario de cada día específico.
  - **Frontend**: toggle "Mismo horario / Por día" en `ClinicSettingsPage.js` Tab Clínica → card "Horario de atención". En modo per-day: 7 filas (Lun-Dom) con botón abrir/cerrar + inputs hora-inicio/fin. Al activar, semilla automática desde valores legacy.
  - **Backward compatible**: si `working_hours` es null, sigue usando el comportamiento clásico (válido para clínicas existentes que no migran).
  - Verificado E2E (5/5 escenarios): cita en hora válida ✓, antes del horario del día ✗400, día cerrado ✗400, después del horario ✗400, hora válida en día con horario corto ✓.

- **2026-05-10 — Gestión de contraseñas para miembros (clinic_admin)**: El admin de clínica ahora puede:
  - **Invitar miembro** con contraseña personalizada (campo opcional, mín. 8 chars). Si se deja vacío, se mantiene el comportamiento actual de generar contraseña temporal.
  - **Editar miembro** → sección "Cambiar contraseña" con input + botón "Aplicar" para resetearla. No disponible para sí mismo (debe usar su propio perfil).
  - Backend: `MemberInvite.password` opcional + nuevo endpoint `PUT /api/clinic/members/{id}/password` (clinic_admin only) que invoca `supabase_admin.auth.admin.update_user_by_id`. Validaciones: rol, no-self, longitud mínima 8.
  - Verificado E2E (9/9 tests): invite con custom pwd → login OK; reset pwd → nuevo login OK + viejo 401; doctor → 403; admin self → 400; pwd corta → 400.

- **2026-05-10 — Bug fix Google Calendar sync**: el sync de citas solo intentaba al calendario del doctor; cuando el creador era el único con GCal conectado, no pasaba nada. Refactor a helper `_push_to_gcal_for_user` con fallback al creator. También: auto-recreate cuando el evento fue borrado manualmente desde Google (404 → insert).

- **2026-05-10 — Bug fix Google Calendar OAuth**: `Missing code verifier` (PKCE) — deshabilitado en `get_google_flow()` ya que somos un cliente confidencial con `client_secret`. Más defensive null checks en `maybe_single().execute()`.

- **2026-05-10 — Logo de clínica en PDFs de recetas y comprobantes de venta**: helper compartido `core.fetch_clinic_logo_image(logo_url, max_h_mm)` descarga el logo (cache en memoria), lo escala con aspect ratio preservado y devuelve un `Image` flowable de reportlab. Insertado al inicio del header en `routes/prescriptions.py::generate_prescription_pdf` (20mm) y `routes/sales.py::generate_sale_pdf` (18mm), antes del nombre de la clínica. Si el logo no existe o falla la descarga, el PDF se genera normalmente sin él (no se rompe). Verificado: ambos PDFs ahora muestran el logo embebido en el header.

- **2026-05-10 — Logo de la clínica en sidebar**: el header del sidebar (`ClinicLayout.js`) ahora muestra el logo de la clínica cuando `logo_url` está presente; si no, hace fallback al nombre de la clínica (no más "ClinicCRM" hardcoded). Fetch en mount via `/api/clinic/settings`. Verificado E2E con/sin logo.

- **2026-05-02 — Export completo de clínica (clinic_admin)**: Nueva función para que el administrador descargue todos los datos de su clínica.
  - Backend: `routes/clinic_export.py` — endpoint `GET /api/clinic/export/full` (require_clinic_admin) genera un ZIP en memoria con:
    - 28 tablas con `clinic_id` directo (clinics, branches, members, patients, appointments, medical_records, prescriptions, lab_orders, products, services, inventory_*, suppliers, purchase_orders, sales, payments, accounts_receivable, cash_*, expenses, commissions_*, attachments, activity_logs, notification_logs, etc.)
    - 6 tablas hijas vía join con padres (sale_items, prescription_items, lab_order_items, purchase_order_items, member_branches, payment_plan_installments)
    - Archivos del bucket Storage `patient-files` bajo `files/<storage_path>`
    - `manifest.json` (versión, clinic_id, conteos por tabla, errores) y `README.md`
  - Frontend: tab "Datos" agregado a `ClinicSettingsPage.js` (visible solo para clinic_admin); botón descarga ZIP con `responseType: 'blob'`, toast con conteos, advertencia HIPAA-friendly de info sensible.
  - Verificado: clinic_admin → 200 ZIP (36 archivos, 34 tablas, 1.9s); doctor/recepcionista → 403; sin auth → 403; tab "Datos" no aparece para roles no-admin.

- **2026-05-01 — Hardening DB**: REVOKE TRUNCATE de roles `anon` y `authenticated` sobre 46 tablas + ALTER DEFAULT PRIVILEGES (cierra vector de DoS por TRUNCATE que ignora RLS).

- **2026-05-01 — Eliminación módulo Plantillas de Consulta**: Removido por solicitud del usuario.
  - Backend: borrados endpoints `GET/POST/PUT/DELETE /api/clinic/templates` y modelo `TemplateCreate` de `routes/medical_records.py`.
  - Frontend: removida sección "Usar plantilla" de `MedicalRecordForm.js` (estados `templates`, `selectedTemplate`, función `applyTemplate`, fetch `/clinic/templates`, import `FileStack`).
  - DB: tabla `consultation_templates` eliminada vía `DROP TABLE CASCADE` (28 filas + estructura). Sin FKs externas, drop seguro.
  - Tests: eliminado `tests/test_consultation_templates.py`.
  - Verificado: `GET /api/clinic/templates` → 404; `information_schema` confirma tabla inexistente; lint pass FE+BE.

- **2026-05-01 — Conexión Postgres directa (DDL automático)**:
  - Añadida `SUPABASE_DB_URL` a `backend/.env` (Session Pooler, IPv4 compatible).
  - Helper `core.run_sql(sql, params, fetch)` para ejecutar DDL desde el código (DROP/CREATE/ALTER TABLE, RLS policies, índices, migraciones).
  - `psycopg2-binary` ya estaba instalado.
  - Cualquier futura modificación de schema puede ejecutarse sin pasar por el SQL Editor.

## Credenciales
Ver `/app/memory/test_credentials.md`
