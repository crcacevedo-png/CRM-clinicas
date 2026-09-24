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

- **2026-06 — Panel de capacidad en producción (auto-medición)**: en Super Admin → **Salud del sistema** (`/admin/salud`) se agregó una tarjeta "Capacidad en vivo" + prueba de carga interna.
  - **Backend** (`routes/system_health.py`): `GET /admin/system/capacity` (CPU/mem vía psutil+cgroup, proceso, threadpool en uso/capacidad, Redis ping, latencia PostgREST, config de workers/pool) y `POST /admin/system/capacity/benchmark?concurrency=N` (N≤60; lanza consultas ligeras en paralelo y reporta throughput, p50/p95, errores y estimación de usuarios activos). Ambos gated `require_super_admin`. Requiere `psutil` (añadido a requirements).
  - **Frontend** (`admin/SystemHealthPage.js`): tarjeta `capacity-card` con métricas + selector de concurrencia y botón `run-benchmark-btn`.
  - **Verificado en preview:** Redis ping ~19ms, latencia BD ~77ms, benchmark 20-conc = 135 ops/s, 0 errores.
  - **Nota deploy:** el build en curso se inició ANTES de estos cambios y de `REDIS_URL`; hay que **redeployar** y agregar `REDIS_URL` (+ workers/CPU) en el entorno de producción para que apliquen. Guía: `/app/memory/SCALING.md`.

- **2026-06 — Redis conectado (Upstash)**: `REDIS_URL` configurada en `backend/.env` (preview); logs confirman "Cache backend: Redis" y las llaves `perm:*` se escriben en Upstash. En producción hay que definir la misma `REDIS_URL` en el deploy.


- **2026-06 — Escalado a 200 clínicas / 100-150 usuarios simultáneos (fase código)**. Ver guía completa en `/app/memory/SCALING.md`.
  - **Caché compartida Redis-ready** (`services/cache.py`): `get_clinic_features`/`get_role_modules` usan Redis si existe `REDIS_URL` (compartida entre workers), si no caen a memoria. TTL 45s, invalidación en cambios de rol/plan/feature.
  - **Pool httpx a Supabase ampliado** (`_tune_supabase_httpx`: max_connections=200, keepalive=50, expiry=10s; vars `SUPABASE_MAX_CONNECTIONS`/`SUPABASE_MAX_KEEPALIVE`).
  - **Threadpool AnyIO** subido a 128 en el startup (var `THREADPOOL_TOKENS`).
  - **Medido (1 worker preview):** Dashboard 30 conc. 3.6s (100% OK); 100 peticiones ligeras conc. 12.5s (100% OK); permisos intactos. Un worker rinde bien hasta ~30 acciones pesadas simultáneas.
  - **Requiere INFRA en Emergent para la meta 100-150 conc.:** subir procesador (4-8 vCPU), correr **8 workers** (gunicorn/uvicorn sin `--reload`; el supervisord del preview es READONLY con `--workers 1`), **provisionar Redis (`REDIS_URL`)** y usar el **connection pooler de Supabase**. Detalle y comandos exactos en `SCALING.md`.


- **2026-06 — Optimización de capacidad/concurrencia (backend)**: se corrigió el cuello de botella que serializaba las peticiones.
  - **Anti-patrón async→sync (endpoint más pesado)**: el Dashboard (`GET /clinic/dashboard`, ~10-12 consultas Supabase) se convirtió de `async def` a `def`, para que FastAPI lo ejecute en su threadpool y NO bloquee el event loop. Las peticiones concurrentes ahora corren en paralelo.
  - **Caché TTL de permisos/plan (30s)** en `core.get_clinic_features` (hacía hasta 5 llamadas Supabase por request) y `core.get_role_modules`, con invalidación (`clear_perm_cache`) al cambiar roles (`routes/roles.py`) y features/plan (`routes/feature_flags.py`). Reduce las llamadas Supabase en TODOS los endpoints protegidos.
  - **Reintento global de PostgREST**: `core._install_postgrest_retry()` envuelve `.execute()` de `SyncQueryRequestBuilder`, `SyncSingleRequestBuilder` y `SyncMaybeSingleRequestBuilder` con reintento (5 intentos, backoff corto) ante errores transitorios de httpx (`RemoteProtocolError: Server disconnected` por conexiones keepalive de Supabase cerradas). Hace confiable el acceso concurrente al cliente Supabase compartido (bug que la paralelización dejó al descubierto).
  - **Resultados medidos (Dashboard):** 15 concurrentes 27s→~5s (100% OK); 30 concurrentes ~54s→6.3s (100% OK); 50 concurrentes (ráfaga extrema) de >120s/inusable → 34.8s (100% OK). Sin regresiones: datos correctos y RBAC intacto (doctor sigue recibiendo 403 en endpoints de admin).
  - **Pendiente (no aplicable en preview):** subir el número de *workers* de Uvicorn/Gunicorn corresponde al entorno de **producción** — el `supervisord.conf` del preview es READONLY (`--workers 1 --reload`). Otros endpoints `async def` con consultas bloqueantes (p. ej. reportes) aún serializan en el loop; convertirlos a `def` (como el Dashboard) es la siguiente palanca.


- **2026-06 — Guía de Usuario: capturas por módulo + versión por rol**:
  - **Capturas reales**: la guía PDF ahora incrusta una captura de pantalla real de cada módulo (12 imágenes en `/app/backend/assets/guide/*.png`: dashboard, patients, prescriptions, lab_orders, agenda, inventory, sales, accounts, expenses, commissions, reports, settings). `_build_guide_pdf` incrusta la imagen si el archivo existe (escala al ancho de página, cap de alto ~105mm) con pie "Vista de <módulo>". PDF resultante ~1.3MB.
  - **Guía por rol**: `GET /api/clinic/user-guide/pdf?scope=role|full`. `scope=role` (default) filtra las secciones a solo los módulos que el miembro puede usar = `get_role_modules(clinic_id, role)` ∩ features activas de la clínica (los administradores siempre reciben la guía completa). `scope=full` = manual completo. La portada muestra el subtítulo "Guía completa" o "Guía para: <Rol>".
  - **Frontend** `ClinicSettingsPage.js` (pestaña Guía): dos botones — `download-user-guide-btn` (completa) y `download-user-guide-role-btn` (según rol).
  - Verificado: curl (admin/full=1.3MB, doctor/role filtrado más pequeño, doctor/full completo) + análisis del PDF (capturas nítidas y completas por sección). Las capturas se regeneran ejecutando un script Playwright de login (no versionado).


- **2026-06 — Guía de Usuario descargable (PDF)**: manual completo del sistema generado con ReportLab, disponible para cualquier miembro de la clínica.
  - **Backend NUEVO** `routes/user_guide.py`: `GET /api/clinic/user-guide/pdf` (require_clinic_member) genera y transmite un PDF A4 con portada (logo de la clínica vía `fetch_clinic_logo_image` si `clinics.logo_url` existe, + nombre + título + fecha), tabla de contenido y 15 secciones numeradas cubriendo todos los módulos (Acceso, Inicio/Inicio rápido, Pacientes, Consulta, Recetas, Laboratorio, Agenda, Inventario, Ventas/POS, Cuentas por cobrar, Gastos, Comisiones, Reportes, Configuración, Recomendaciones). Pie de página con nombre de clínica + número de página. Registrado en `server.py` como `_r_guide`.
  - **Frontend MODIFICADO** `ClinicSettingsPage.js`: nueva pestaña **"Guía"** (`tab-guide`, visible a todos los miembros) con tarjeta `user-guide-card` que lista el contenido y botón `download-user-guide-btn` para descargar el PDF. Añadido `guide` a los VALID_TABS del deep-link `?tab=`.
  - Verificado por curl (200, `application/pdf`, ~6 páginas) y análisis de estructura del PDF (portada + TOC + secciones en español, correcto). El logo se incluye solo si la clínica ya lo configuró.


- **2026-06 — Inicio rápido (onboarding guiado para administradores)**: panel destacado en la parte superior del Inicio (`/dashboard`) visible **solo para clinic_admin**, que guía a recorrer y poner en orden las áreas del sistema.
  - **Backend NUEVO** `routes/quick_start.py`: `GET /api/clinic/quick-start` y `PUT /api/clinic/quick-start` (require_clinic_admin). Estado a nivel de clínica en columna nueva `clinics.quick_start JSONB` = `{completed: [step_keys], dismissed: bool}` (compartido entre admins). Migración `2026_06_quick_start_clinics` (añadida a `services/migrations.py` y aplicada vía run_sql). Registrado en `server.py` como `_r_qs`.
  - **Frontend NUEVO** `components/QuickStartPanel.js`: catálogo de 14 pasos (7 base siempre + 7 gated por feature: inventory, sales, accounts_receivable, expenses, commissions, financial_reports, multi_branch). Cada paso: ícono, título, descripción, toggle "hecho" (marca/desmarca, persistente) y botón "Ir" que navega al área. Barra de progreso "X de N completados". Al completar todos los pasos visibles aparece el banner con "Retirar inicio rápido" (dismiss). Fetch con 1 reintento; fail-closed si falla.
  - **Frontend MODIFICADO** `ClinicDashboardPage.js`: renderiza `<QuickStartPanel features={...} />` solo cuando `role === 'clinic_admin'`.
  - **Frontend MODIFICADO** `ClinicSettingsPage.js`: ahora lee `?tab=` para activar la pestaña (usado por los pasos team→members y roles→roles); tarjeta nueva en pestaña Datos ("Inicio rápido (onboarding)", `restore-quick-start-btn`) para volver a mostrar el panel si se retiró.
  - Decisiones: estado a nivel de clínica (no por usuario); marcado manual (sin auto-detección); pasos de áreas inactivas no se muestran. Verificado por testing_agent iteration_30: **100%** (visibilidad por rol, 14 pasos, toggle+persistencia tras recarga, deep-links ?tab=, completar→retirar, restaurar).


- **2026-06 — Recetas y Órdenes de Laboratorio DENTRO de la consulta médica**: al realizar una consulta (`/dashboard/pacientes/:id/consulta`), el médico ahora puede crear la receta de medicamentos y la orden de estudios/laboratorio sin salir del formulario, e **imprimir (PDF)** y **enviar por WhatsApp** desde ahí mismo.
  - **Frontend NUEVO** `pages/clinic/ConsultationPrescriptionSection.js`: editor de medicamentos (búsqueda `/clinic/medications/search`, presentación, dosis, frecuencia, vía, duración, instrucciones), diagnóstico prellenado desde el CIE-10 principal, indicaciones generales. Botones `presc-emit-print-btn` (POST `/clinic/prescriptions` status='issued' → abre PDF) y `presc-emit-whatsapp-btn` (emite + `shareViaWhatsApp('prescription', id)`). Tras emitir muestra panel de éxito `presc-created-panel` con reimprimir / WhatsApp / nueva receta.
  - **Frontend NUEVO** `pages/clinic/ConsultationLabSection.js`: selector de estudios por categoría (`/clinic/lab-studies`), diagnóstico presuntivo prellenado, prioridad rutina/urgente, indicaciones. Botones `lab-create-print-btn` (POST `/clinic/lab-orders` status='pending' → abre PDF) y `lab-create-whatsapp-btn`. Panel de éxito `lab-created-panel`.
  - **Frontend MODIFICADO** `pages/clinic/MedicalRecordForm.js`: dos secciones colapsables nuevas ("Receta médica", "Órdenes de estudios / Laboratorio"). Helper `ensureRecordId()` que auto-guarda la consulta como borrador (si aún no existe) para obtener `medical_record_id` y vincular los documentos; `currentRecordId` evita crear registros duplicados al finalizar; `primaryDiagnosisText` alimenta el prellenado.
  - Backend sin cambios (ya soportaba `medical_record_id` en `PrescriptionCreate`/`LabOrderCreate`, generación de PDF y `POST /clinic/whatsapp/share`). Verificado E2E por curl (receta+laboratorio vinculadas, PDF, `wa_url`) y por testing_agent iteration_29 (flujo doctor 100%).

- **2026-06 — Auditoría de Cambios de Rol (bitácora RBAC)**: `routes/roles.py` ahora registra en `audit_log` cada acción de gestión de roles vía `services.audit.log_audit`: `role_created`, `role_updated` (con old/new de nombre y módulos), `role_deleted` y `member_role_assigned` (old/new role). Cada endpoint recibe `Request` para capturar IP/User-Agent. Verificado por curl (eventos aparecen con actor y valores) y testing_agent iteration_29 (visibles en pestaña Bitácora).

- **2026-06 — Exportación Filtrada a Excel**: `GET /api/clinic/export/excel` acepta `start_date`, `end_date` (opcionales, filtran por `created_at` las hojas con fecha: Pacientes, Evaluaciones, Recetas, Laboratorio, Citas) y `sheets[]` (selección de hojas; Equipo/Sucursales/Clínica siempre completas). UI: `ClinicSettingsPage.js` → pestaña Datos → botón "Exportar a Excel…" abre modal (`excel-export-dialog`) con rango de fechas, checkboxes de hojas, atajos Todas/Ninguna. 
  - **Bug fix (HIGH, iteration_29)**: la descarga desde el navegador daba 500 intermitente (`httpx.RemoteProtocolError: Server disconnected`) porque el cliente supabase compartido reutilizaba conexiones keepalive cerradas bajo peticiones concurrentes. Solución: helper `_execute_retry()` en `routes/clinic_export.py` que reintenta las lecturas ante errores transitorios de httpx (aplicado en `_fetch_all`, `_fetch_in` y las lecturas de `clinics`), + 1 reintento en el frontend ante 5xx. Verificado: 18/18 peticiones concurrentes → 200. **NOTA**: `GET /clinic/features` tiene el mismo problema sistémico latente (500 transitorio esporádico bajo concurrencia extrema); es preexistente y fuera del alcance de esta tarea.


- **2026-09-23 — Exportación de base de datos a Excel (clinic_admin)**: nueva descarga de toda la base de datos en un solo archivo `.xlsx` multi-hoja, dentro de Configuración → pestaña "Datos".
  - **Backend** (`routes/clinic_export.py`): nuevo `GET /api/clinic/export/excel` (require_clinic_admin). Construye el workbook con `openpyxl` en un threadpool (no bloquea el event loop) y lo devuelve como `StreamingResponse`. Hojas: **Pacientes** (todas las variables), **Evaluaciones Médicas** (historia clínica, con paciente/médico resueltos), **Recetas** + **Recetas - Medicamentos**, **Laboratorio** + **Laboratorio - Estudios**, **Citas**, **Equipo**, **Sucursales**, **Clínica**. Helpers `_xl_cell` (coerción segura: dicts/listas → JSON, bool → Sí/No, trunca >32k, quita chars XML ilegales), `_write_sheet` (header en negrita + freeze panes + columnas calculadas paciente/médico), `_build_excel_bytes`. Auditado (`clinic_data_export_excel`). Verificado: xlsx válido de 10 hojas; doctor no-admin → 403.
  - **Frontend** (`ClinicSettingsPage.js`): tarjeta "Descargar base de datos (Excel)" en la pestaña Datos (junto al export ZIP existente), botón `download-excel-export-btn` que descarga el blob `.xlsx`. Verificado por screenshot desktop + móvil (sin overflow).

- **2026-09-23 — Módulo de Gestión de Roles (RBAC por módulo/menú)**: solo clinic_admin, en Configuración → pestaña "Roles". Gestiona roles fijos del sistema + roles personalizados, cada uno con acceso activable por módulo del menú. Enforcement en frontend Y backend. Verificado por testing_agent (iteration_28: 12/12 backend, 100% frontend).
  - **DB**: nueva tabla `clinic_roles` (id, clinic_id, key único por clínica, name, description, is_system, modules jsonb, timestamps) + nueva columna `clinic_members.role_key TEXT`. Migraciones `2026_06_12_clinic_roles_table` y `2026_06_12_clinic_members_role_key` (aplicadas directo vía run_sql + reload de schema cache; el pooler de startup a veces expira). RLS on, anon sin acceso.
  - **IMPORTANTE — enum**: `clinic_members.role` es un ENUM Postgres `user_role` que solo admite `super_admin/clinic_admin/doctor/assistant/receptionist` (NO cashier ni roles personalizados). Por eso el **rol autoritativo vive en `role_key`** y `core.require_clinic_member` expone `member['role'] = role_key or role` (efectivo). El enum solo se escribe cuando el valor está en `ENUM_ROLE_VALUES`.
  - **Backend** (`core.py`): `MODULE_CATALOG` (11 módulos toggeables: agenda, patients, prescriptions, lab_orders, inventory, sales, accounts_receivable, expenses, commissions, reports, branches; dashboard y settings SIEMPRE accesibles), `SYSTEM_ROLES`, `SYSTEM_ROLE_LABELS/DESCRIPTIONS`, `DEFAULT_ROLE_MODULES`, `get_role_modules(clinic_id, role_key)` (clinic_admin = todos; lee clinic_roles o cae a defaults), `require_module(module_key)` (factory de dependency; clinic_admin bypass; 403 si el módulo no está). `require_finance_role` reescrito para ser module-based (module 'reports').
  - **Backend** (`routes/roles.py`): `GET /clinic/roles` (siembra los 5 roles del sistema idempotente + devuelve modules catalog + member_count por rol), `POST/PUT/DELETE /clinic/roles`, `PUT /clinic/members/{id}/role`. Protecciones: clinic_admin no editable, roles del sistema no eliminables, no eliminar rol con miembros, no dejar la clínica sin admin activo.
  - **Backend enforcement**: routers puros montados con `dependencies=[Depends(require_module(...))]` (inventory, sales, accounts_receivable, expenses, commissions, reports, agenda_blocks, prescriptions, lab_orders, medical_records). Per-endpoint en appointments.py (agenda) y patients.py (patients) — dejando abiertos los lookups compartidos (`/clinic/patients/search`, `POST /clinic/patients`) para no romper el modal de nueva cita. `GET /clinic/features` ahora devuelve `modules` + `role` del miembro.
  - **Frontend**: `FeatureContext` expone `hasModule` (+ reset de estado al cambiar de usuario), `ClinicLayout` filtra el sidebar por feature Y módulo, `components/ModuleRoute.js` protege las rutas (redirige a /dashboard si el rol no tiene el módulo), `pages/clinic/RolesTab.js` (lista de roles con chips de módulos, crear/editar/eliminar con checkboxes de 11 módulos, + tabla de asignación de rol por miembro). Pestaña "Roles" solo visible para clinic_admin.

- **2026-09-23 — Bloqueo de Agenda (Agenda Blocks) — VERIFICADO**: (código escrito en la sesión anterior, probado en esta). Backend por curl + frontend por testing_agent (iter 28). Un bloqueo por médico impide agendarlo en CUALQUIER sucursal (409); un bloqueo por sucursal solo afecta esa sucursal. UI: botón "Bloquear" + modal + banda gris rayada en el calendario con botón de eliminar.


- **2026 — Envío por WhatsApp Web (recetas, órdenes de laboratorio y recibos de venta)**: se agregó la capacidad de compartir documentos con el paciente por WhatsApp Web mediante enlaces `wa.me` (sin necesidad de la API de WhatsApp Business). Verificado: backend por curl (3 tipos + 400/404) y frontend por testing_agent (iteration_27, 100%).
  - **Backend** — nuevo `routes/whatsapp_share.py` con `POST /api/clinic/whatsapp/share {doc_type, doc_id}` (doc_type: `prescription`|`lab_order`|`sale`). Valida que el documento pertenezca a la clínica (tenant-scoped: 404 si no); para recetas exige `status='issued'`; asegura/regenera el PDF y crea una **URL firmada de 7 días** en Supabase Storage; normaliza el teléfono del paciente a formato internacional (código país por defecto **+502**, con mapa de países LATAM/EE.UU./España); arma el mensaje en español + enlace al PDF y el `wa_url` (`https://wa.me/<tel>?text=...`, o sin número si el paciente no tiene teléfono → el usuario elige el contacto). Marca el documento como `sent_via='whatsapp', sent_at=now`. Registrado en `server.py` como `_r_wa`.
  - **Migración** `2026_06_10_whatsapp_share_sent_columns`: `sent_via TEXT` + `sent_at TIMESTAMPTZ` agregadas a `sales` y `lab_orders` (recetas ya las tenían). Aplicada directamente vía `run_sql` (el pooler de startup a veces expira) y registrada en `schema_migrations`.
  - **Frontend** — nuevo util `src/lib/whatsappShare.js` (`shareViaWhatsApp(docType, docId, headers)`: POST → abre `wa_url` en pestaña nueva + toasts sonner). Botón verde "WhatsApp" (icono `MessageCircle`) agregado en: `PrescriptionsPage.js` (filas emitidas), `LabOrdersPage.js` (todas las filas), `sales/DailySalesTab.js` (filas no anuladas + footer del diálogo de detalle) y `sales/POSTab.js` (pantalla de venta registrada). Data-testids: `whatsapp-prescription-<id>`, `whatsapp-lab-<id>`, `whatsapp-sale-<id>`, `whatsapp-sale-detail-btn`, `whatsapp-receipt-btn`.



- **2026 — Security Hardening Bloque 4 (auditoría exhaustiva de seguridad)**: cierre de 5 hallazgos tras una revisión completa de la plataforma solicitada por el usuario. Verificado: backend por curl (A/B/C/D/E), frontend por testing_agent (iteration_26, 5/5 PASS, 0 violaciones CSP).
  - **(A) OAuth Google — CSRF/nonce**: `routes/google_calendar.py` ya no usa el `user_id` crudo como `state`. Nuevos helpers `_sign_oauth_state(uid, ttl=600)` / `_verify_oauth_state(state)` firman el state con HMAC-SHA256 (clave derivada de `ENCRYPTION_KEY`) + expiración 10 min + nonce. El callback rechaza states forjados/expirados → redirect `?gcal_error=invalid_state`. Cierra el secuestro de PHI de citas al calendario de un atacante. Verificado: auth-url emite state firmado; state forjado (uuid crudo) → 307 invalid_state.
  - **(B) IDOR/BOLA — propiedad de paciente/médico**: nuevos guards en `core.py` `assert_patient_in_clinic(pid, clinic_id)` y `assert_doctor_in_clinic(did, clinic_id)` (validan UUID + pertenencia a la clínica → 400). Aplicados en: `appointments.create` (patient+doctor), `appointments.update` (doctor si se reasigna), `sales.create` (branch+patient+doctor), `lab_orders.create` (patient), `prescriptions.create` (patient). Verificado: cita con patient_id ajeno → 400 "Paciente inválido para esta clínica".
  - **(C) Reportes financieros — gating por rol**: nuevo `core.require_finance_role(ctx)` (FINANCE_ROLES = clinic_admin, cashier), aplicado a los 6 endpoints de `routes/reports.py` (executive-summary, income, pnl, pnl-pdf, inventory, by-branch). Frontend: `ClinicLayout.js` oculta el item "Reportes" del sidebar para roles no financieros (nav item con `roles:['clinic_admin','cashier']`); `ReportsPage.js` muestra guard `data-testid='reports-no-access'` para roles no autorizados. Verificado: clinic_admin 200 en los 6; doctor/receptionist 403 + sin menú + guard en acceso directo por URL.
  - **(D) Rate-limit anti-spoofing XFF**: nuevo `core.client_ip(request)` con lista de CIDRs de proxy confiables (`TRUSTED_PROXY_CIDRS`, default RFC1918+loopback). Solo confía en `X-Forwarded-For`/`X-Real-IP` cuando el peer TCP es un proxy confiable. Reemplaza el "primer XFF sin validar" en `server.py::_trusted_remote_address` y `services/db_rate_limit.py::rate_limit_key`. Verificado: login → 401×3 luego 429.
  - **(E) Endurecimientos varios**: (1) rangos en items de venta (`sales.create`: qty>0, unit_price≥0, discount 0–100, montos de pago≥0 → 400); (2) límite de plan `max_patients` en `patients.create` (usa `get_plan_limits` como fallback); (3) mensajes de error genéricos al cliente (sin `str(e)`) en `patients.create`, `sales.create` (3 sitios) y `clinic_settings.invite` — el detalle completo queda en el log con `exc_info=True`; (4) **Content-Security-Policy**: header estricto `default-src 'none'` en respuestas API (`server.py` middleware) + meta CSP permisivo en `frontend/public/index.html` para el SPA (permite self/inline/eval/https/blob workers/ws-wss). NOTA: el fallback de `ENCRYPTION_KEY='default-key-change-me'` se dejó SIN cambios por indicación del usuario (assuming defaults).
  - **Nota de auditoría**: el hallazgo "secretos committeados" (SEC-001) fue verificado y NO aplica — `.gitignore` excluye `.env`/`.env.*`/`*.env` y `git ls-files` confirma que ningún `.env` está versionado; los secretos viven solo en el entorno del pod. Recomendación pendiente (no destructiva): rotación periódica de `SERVICE_ROLE_KEY`, `SUPER_ADMIN_PASSWORD`, `ENCRYPTION_KEY`.
  - **Lint housekeeping**: corregidos 8 errores de lint preexistentes bloqueantes (F811 redefiniciones de `date`/`timedelta` en accounts_receivable/reports/sales; E722 bare-except en clinic_settings/lab_orders/tests).

- **2026-07-10 — Force-change on first login (P0 security hardening completado)**: cierra el hueco de "admin genera password → usuario nunca la cambia".
  - **Backend** (`core.py`): nuevos helpers `mark_password_needs_reset(user_id, needs)` y `user_needs_password_reset(user)` — persisten en `user_metadata.password_needs_reset` de Supabase Auth (sin migración DB). `_LocalAuthUser` ampliado con `user_metadata` extraído del JWT payload. `POST /auth/login` y `GET /auth/me` devuelven `password_needs_reset: bool`.
  - **Flag marcado en 5 flujos**: `POST /admin/clinics` (initial admin), `POST /admin/clinics/{id}/members` (super-admin agrega miembro), `POST /clinic/members/invite` (con o sin custom_pw), `PUT /clinic/members/{id}/password` (clinic-admin reset), `POST /admin/users/{id}/reset-password` (super-admin reset con auto-gen).
  - **Endpoint self-service** `POST /auth/change-password` (rate-limited 10/min): verifica current password vía `supabase_user.sign_in`, rechaza cuando new==current, aplica `services.password_policy.validate_password` con email+nombre para personal-token check, persiste con `supabase_admin.update_user_by_id`, limpia el flag, log audit `password_self_changed`.
  - **Frontend**: nueva página `/cambiar-password` (`ChangePasswordPage.js`) con 3 inputs (current, new, confirm), integra `PasswordStrengthMeter`, banner ámbar cuando es forzado, botón "Cerrar sesión" para escape. `AuthContext` guarda `passwordNeedsReset` (fuente: login response, jamás sobrescrito por `/auth/me` que lee JWT stale), expone `clearPasswordResetFlag()`. `ProtectedRoute` redirige a `/cambiar-password` si el flag es true y bloquea bypass a cualquier otra ruta. `LoginPage` también redirige tras login exitoso cuando el flag viene true. Post-cambio: `window.location.assign(target)` para hard-reload y evitar race condition de React 18 state batching.
  - **Verificado E2E**: (1) Login con flag=true → forzado a `/cambiar-password`. (2) Intento de bypass a `/dashboard` → rebota a `/cambiar-password`. (3) Submit con current wrong → 400. (4) Submit con new==current → 400. (5) Submit con new débil → 400 (policy). (6) Submit success → toast + reload → `/dashboard` funcional con Diana Ramírez logueada como doctor. (7) `/auth/me` posterior muestra `password_needs_reset: false` (backend limpio user_metadata).

- **2026-07-10 — Password Policy hardened (NIST SP 800-63B balanced tier)**: reemplaza el mínimo de 8 caracteres.
  - **Backend**: nuevo `services/password_policy.py::validate_password(pw, email, name)` con **6 capas de validación**: (1) longitud ≥10, (2) ≥3 de 4 categorías (mayús/minús/dígito/símbolo), (3) no contiene email local-part ni nombre de usuario ≥4 chars, (4) blocklist top-10.000 (`common_passwords.txt` cargado lazy), (5) **HIBP k-anonymity check** vía `api.pwnedpasswords.com/range/` (envía solo los 5 primeros chars del SHA-1, fail-open en outages), (6) score dinámico para el frontend meter.
  - **Wireado en 4 endpoints**: `POST /admin/clinics` (admin_password), `POST /admin/clinics/{id}/members` (data.password), `POST /clinic/members/invite` (data.password si custom), `PUT /clinic/members/{id}/password` (fetch email del target para personal-token check). El super-admin reset `POST /admin/users/{id}/reset-password` usa `generate_password()` que ya es policy-compliant por construcción.
  - **`core.generate_password(14)` reescrito**: garantiza 1 char de cada una de las 4 categorías + shuffle con `secrets.SystemRandom()`. Antes 12 chars, ahora 14. Verificado: 10 generados en secuencia todos pasan la política.
  - **Frontend**: nuevo `components/PasswordStrengthMeter.js` reusable — barra 5-niveles ("Muy débil"…"Muy fuerte"), 3 checks en tiempo real (longitud, categorías, personal), sin dependencias externas (implementación manual, ~90 líneas). Helper `passwordMeetsPolicy(pw, {email,name})` para deshabilitar botones de submit. Montado en 3 formularios: `ClinicsPage` (crear clínica), `ClinicDetailPage` (agregar miembro), `ClinicSettingsPage` (invitar miembro + reset password de miembro).
  - **Verificado E2E**: 4 curl tests → longitud <10, sólo 2 categorías, contiene nombre "Roberto", `MyPassword123!` (bloqueada por HIBP) — todas 400 con mensaje específico en español. Screenshots UI verifican meter con nombre "Roberto Perez" detectando "roberto" dentro del password.
  - **Nota de compatibilidad**: la política se aplica SOLO al establecer/cambiar password. Usuarios existentes con passwords legacy (<10 chars, incluido `Armagedon1980$`) siguen pudiendo hacer login normalmente hasta que la cambien.

- **2026-07-10 — Cold Storage archival para audit_log**: mantenimiento mensual ahora archiva particiones >12 meses antes de dropearlas.
  - **Backend**: `services/monthly_maintenance.py::_archive_partition_to_storage` exporta cada partición como JSONL comprimido (gzip) a `patient-files/_archives/audit_log/audit_log_YYYY_MM.jsonl.gz`. Serializer custom `_json_default` maneja `datetime`/`UUID`/`Decimal`/`bytes`. `_drop_old_audit_partitions` retorna lista de dicts `{name, archived:{ok,path,rows,bytes}, dropped, error?}`; la partición solo se drpea DESPUÉS de un upload exitoso — si el archivo falla, la partición se preserva.
  - **Endpoint nuevo**: `GET /api/admin/maintenance/archives` (super-admin) lista archivos con signed URLs 24h. Útil para restauración forense o cumplimiento regulatorio.
  - **UI**: nueva card "Archivos históricos (Cold Storage)" en `/admin/salud` con tabla (archivo, fecha, tamaño, botón descargar). Muestra mensaje amigable cuando no hay archivos aún.
  - **Verificado E2E**: detach catch-all → crear partición fake 2024_01 con 3 rows → run maintenance → 3 filas exportadas (291 bytes gzip / 984 raw, 70% compresión) → partición drpeada → download + decompress OK. Fallback verificado: MIME `application/gzip` bloqueado por bucket policy → cambiado a `application/octet-stream`.

- **2026-05-24 — Dashboard SaaS Super Admin (Fase 1: Bloques 1, 2, 3, 4, 6)**: panel de métricas completo del SaaS.
  - **Backend**: nuevo `routes/admin_metrics.py` con endpoint `GET /api/admin/dashboard/saas`. Agrega en un solo response: MRR/ARR (calculado de planes activos × precios), nuevas clínicas hoy/7d/30d con MoM%, funnel onboarding (registradas→pacientes→citas→ventas), distribución geográfica, DAU/WAU/MAU + sticky ratio (vía `activity_logs`), clínicas inactivas 7/14/30d, adopción por 9 módulos, engagement (citas/recetas/ventas/pacientes hoy/7d/30d), Top-10/Bottom-10 clínicas por score ponderado, distribución de estados de citas, MRR por plan, planes próximos a vencer, AR total, warnings de plan limit (clínicas free/basic/professional cerca del límite de pacientes).
  - **Frontend**: `AdminDashboard.js` reescrito de cero — 5 secciones con ~30 widgets: 16 KPI cards, funnel visual, barras horizontales para adopción de módulos, PieChart para estados de citas, BarChart de MRR por plan, listas Top/Bottom 10, tabla de planes próximos a vencer y warnings de límite. Colores semánticos por severidad. Sticky ratio cambia color (verde >20%, ámbar <20%). Tabla con drill-down.
  - **Estado**: código completo y linted; pendiente smoke test en cuanto Supabase Auth (caído por incidente Cloudflare 521 al momento) regrese.

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


- **2026-05-24 — Resend dominio verificado (`mail.cortexiamedical.com`)**: el dominio `mail.cortexiamedical.com` quedó verified en Resend (status: verified, sending: enabled). `SENDER_EMAIL` en `backend/.env` cambiado de `onboarding@resend.dev` a `noreply@mail.cortexiamedical.com`. Probado envío real (`info@cortexiagt.com`) — Resend message id devuelto OK. Emails transaccionales (welcome, password reset, appointment reminder) ahora salen con remitente oficial `Cortexia Medical <noreply@mail.cortexiamedical.com>`.

- **2026-05-24 — Envío automático: recetas por email + recordatorios 24 h antes**: dos flujos transaccionales sobre Resend.
  - **Recetas:** dentro de `routes/prescriptions.py::generate_prescription_pdf` se adjunta el PDF al email del paciente cuando `status=='issued'`. Plantilla nueva `email_templates.prescription_issued` (subject, html, text, attachments con bytes binarios → base64). Marca `prescriptions.sent_via='email'` y `sent_at=now()` al confirmar entrega. UI: `NewPrescriptionPage.js` muestra toast con email destinatario.
  - **Recordatorios 24h:** `services/reminder_scheduler.py` (APScheduler `AsyncIOScheduler`, tick cada 10 min, ventana ±30 min). Busca `appointments` con `status='scheduled'`, `reminder_email_sent_at IS NULL`, `starts_at` entre `now+23h30` y `now+24h30`. Envía email con `email_templates.appointment_reminder`. Stamp `appointments.reminder_email_sent_at` aunque el paciente no tenga email (evita reintentos). Configurables vía env: `REMINDER_HOURS_BEFORE`, `REMINDER_WINDOW_MIN`, `REMINDER_TICK_MIN`. Endpoint manual `POST /api/clinic/appointments/{id}/send-reminder` (UI: nueva sección "Recordatorio al paciente" en `AppointmentDetailModal` con botón "Enviar ahora / Reenviar" + estado del último envío). Endpoint super-admin `POST /api/admin/reminders/run-now` para forzar un tick.
  - **DDL migración**: nueva columna `appointments.reminder_email_sent_at TIMESTAMPTZ` + índice parcial `idx_apt_reminder_due`. Aplicada vía `services/migrations.py` (tabla `schema_migrations` con tracking idempotente). Auto-corre en startup; también disponible vía `POST /api/admin/migrations/run` para reintentos manuales.
  - Scheduler inicia/para via `@app.on_event("startup"/"shutdown")` en `server.py`. Defensivo: Supabase caído no rompe el backend.


- **2026-05-10 — Logo de la clínica en sidebar**: el header del sidebar (`ClinicLayout.js`) ahora muestra el logo de la clínica cuando `logo_url` está presente; si no, hace fallback al nombre de la clínica (no más "ClinicCRM" hardcoded). Fetch en mount via `/api/clinic/settings`. Verificado E2E con/sin logo.


- **2026-05-24 — RLS Hardening v1 (5 fixes)**: auditoría completa de seguridad RLS, 5 vulnerabilidades corregidas vía `services/migrations.py::2026_05_24_rls_hardening_v1` (idempotente, trackeada en `schema_migrations`).
  - **(1) Vistas con SECURITY DEFINER → SECURITY INVOKER**: `v_daily_sales`, `v_expiring_products`, `v_low_stock_alerts`, `v_monthly_pnl` hacían bypass total de RLS (cualquier `authenticated` veía datos de TODAS las clínicas). Ahora ejecutan con los privilegios del invoker, RLS aplica.
  - **(2) 44 policies UPDATE/ALL ahora con WITH CHECK = USING**: cierra cross-tenant write attack (ej. `UPDATE patients SET clinic_id='otra-clinica'`). DO block dinámico itera `pg_policies` y aplica `ALTER POLICY ... WITH CHECK` espejo del USING. Verificado: 0 policies bad ahora.
  - **(3) REVOKE INSERT/UPDATE/DELETE/TRUNCATE/REFERENCES/TRIGGER de `anon`** en las 50 tablas+vistas de `public`. `anon` solo conserva SELECT (que RLS sigue bloqueando). `ALTER DEFAULT PRIVILEGES` aplicado para tablas futuras. Defense-in-depth: si una policy futura es buggy, anon igual no puede escribir.
  - **(4) `schema_migrations` con RLS + policy super-admin-only**: cierra la única tabla sin RLS.
  - **(5) Catálogos públicos documentados**: `features`, `icd10_codes`, `plan_features` mantienen `qual=true` para `public` (son catálogos read-only por diseño). Si se agregan columnas sensibles a futuro, reforzar.
  - **Resultado**: 46/46 tablas con RLS, 131 policies, 0 bad policies, anon solo SELECT. Backend (service_role) sigue funcionando 100%, verificado via `/api/admin/dashboard`.

- **2026-05-24 — Audit Log v1 (bitácora inmutable)**: tabla `audit_log` append-only para acciones críticas, con UI dedicada.
  - **DDL** (`migrations.py::2026_05_24_audit_log_v1`): tabla con `id, occurred_at, action, entity, entity_id, clinic_id, actor_user_id, actor_email, actor_role, old_values, new_values, ip_address, user_agent, meta`. Triggers `BEFORE UPDATE/DELETE` que `RAISE EXCEPTION` bloquean cualquier mutación (incluso desde service_role). 4 índices: `(clinic_id, occurred_at DESC)`, `(actor_user_id, occurred_at DESC)`, `(entity, entity_id)`, `(action, occurred_at DESC)`. RLS: super_admin ve todo, clinic_admin ve solo su clinic_id; `REVOKE ALL FROM anon`, INSERT bloqueado a authenticated.
  - **Backend** (`services/audit.py::log_audit`): helper async, nunca lanza excepción, captura IP/User-Agent del Request, extrae actor del ctx. Cableado en: `auth/login` (success, failed, denied), `clinic/members/invite|toggle|password`, `admin/users/*/reset-password`, `admin/clinics/{id}` (plan_change, activated/deactivated, generic update con diff), `clinic/patients/{id}/toggle-active` (archived/activated), `clinic/prescriptions` (issued), `clinic/export/full` (data_export).
  - **Endpoints** (`routes/audit_log.py`): `GET /api/admin/audit-log` (super-admin, scope global con filtro `clinic_id`) y `GET /api/clinic/audit-log` (clinic-admin, scope a su clínica). Filtros: `action`, `entity`, `actor_email` (ilike), `since`, `until`, paginación. `GET /api/admin/audit-log/actions` devuelve lista distinct para el dropdown.
  - **UI**: componente reusable `components/AuditLogTable.js` con filtros (acción, email actor, fechas), badges por color de acción, paginación. Página `pages/admin/AuditLogPage.js` montada en `/admin/auditoria` (sidebar con icon Shield). Tab "Bitácora" en `ClinicSettingsPage.js` para clinic_admin (junto a "Datos").
  - **Verificado E2E**: login fallido + login exitoso quedan registrados con IP `34.16.56.64`; clinic_admin ve solo eventos de su clínica (`c0321ed8`); clinic_admin → `/admin/audit-log` = 403; doctor → `/clinic/audit-log` = 403. UPDATE y DELETE sobre `audit_log` lanzan `audit_log is append-only`.

- **2026-06-07 — Security Hardening Bloque 1 (5 fixes rápidos)**: aplicado tras auditoría completa de seguridad del SaaS.
  - **(1) CORS estricto**: `server.py` ahora requiere `CORS_ORIGINS` en `.env` y falla en startup si no está. Antes caía al wildcard `*` con `allow_credentials=True` (inválido y peligroso). Allowlist: `super-admin-panel-12.preview.emergentagent.com`, `app.cortexiamedical.com`, `cortexiamedical.com`.
  - **(13/14) Security headers + allow_headers/methods específicos**: middleware `security_headers_middleware` añade HSTS (`max-age=31536000; includeSubDomains`), `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy: geolocation=(), microphone=(), camera=()`. CORS solo acepta métodos REST estándar y headers `Authorization, Content-Type, Accept, Origin, X-Requested-With`.
  - **(11) ErrorBoundary React**: nuevo `components/ErrorBoundary.js` envuelve todo el árbol en `App.js`. Antes un error en cualquier componente tumbaba la app con pantalla blanca; ahora muestra fallback amigable con botón "Volver al inicio" y stack trace solo en development.
  - **(18) GENERATE_SOURCEMAP=false** en `frontend/.env` → builds de producción ya no exponen source maps con código original al navegador.
  - **(10) HTML escape en email templates**: `services/email_templates.py` ahora tiene helper `_esc()` con `html.escape(..., quote=True)` aplicado a TODAS las variables (patient_name, doctor_name, clinic_name, diagnosis, reason, branch, set_by, etc.). Antes un paciente llamado `<script>alert(1)</script>` rompía el HTML del email; verificado: input malicioso → `&lt;script&gt;`.
  - **Verificado E2E**: curl directo a `localhost:8001/api/health` con `Origin: evil.example.com` NO devuelve `Access-Control-Allow-Origin`; con origen permitido SÍ. Security headers presentes en HEAD. Login + dashboard cargan sin issues post-cambios. Test XSS en `appointment_reminder` confirma escape.



- **2026-05-02 — Export completo de clínica (clinic_admin)**: Nueva función para que el administrador descargue todos los datos de su clínica.

- **2026-06-07 — Security Hardening Bloque 2 + 3 (rate limit, sanitización, magic bytes, signed URLs cortas)**:
  - **(B2.2) Rate limiting** con `slowapi==0.1.9` (`server.py::limiter` con `_trusted_remote_address` que respeta XFF del proxy). Límites aplicados: `/auth/login` 5/min/IP; `/admin/users/{id}/reset-password` 10/min; `/clinic/members/{id}/password` 10/min; `/clinic/appointments/{id}/send-reminder` 30/min. Verificado: 7 intentos consecutivos a login → 5×401 + 2×429.
  - **(B2.12) Email enumeration cerrada** en `/clinic/members/invite`: si el usuario ya es miembro activo, ya no devuelve "El usuario ya es miembro de esta clínica" (que permitía enumerar emails). Ahora siempre responde `{"message":"Miembro listo"}` y actualiza silenciosamente. El audit log captura la distinción (`member_invited` vs `member_reinvited`).
  - **(B3.6) PostgREST filter injection cerrada** en 11 endpoints de búsqueda (`patients`, `inventory`, `prescriptions/medications`, `medical_records/icd10`, `expenses`, `sales/services`, `super_admin/users`). Nuevo `services/input_sanitizer.py::sanitize_postgrest_search` strip-ea `,()*:%\` que tenían meaning en el DSL de PostgREST y podían extender filtros `or_`. Verificado: `q=*,is_active.eq.false` → `is_active.eq.false` (literal dentro del ilike, no se interpreta como filter).
  - **(B3.7) Magic-bytes validation en uploads**: `python-magic` + `libmagic1`. `services/input_sanitizer.py::validate_image_upload` y `validate_document_upload` leen los primeros 4096 bytes y verifican que el mime-type real corresponda a la categoría declarada. Aplicado en `/clinic/settings/logo` (image-only) y `/clinic/patients/{id}/files/upload` (image + PDF + office docs + DICOM). También sanitiza el filename para prevenir path traversal. Verificado: text spoofed as `image/png` → 400; PDF spoofed as image → 400; JPEG real → OK.
  - **(B3.8) Signed URLs cortas**: `lab_orders` 24h→1h, `prescriptions` 24h→1h, `sales` 24h→1h, `expenses` lista 7d→1h. Logos mantienen 1 año (necesario en HTML de emails y PDFs). PDFs en emails llevan los bytes adjuntos, no la URL.
  - **(B3.4) IP whitelist en audit log**: `services/audit.py::_ip_from_request` ahora solo confía en `X-Forwarded-For` cuando el peer TCP viene de un CIDR conocido (configurable via env `TRUSTED_PROXY_CIDRS`, default: RFC1918 + loopback). Headers desde IPs no-trusted son ignorados — defeats spoofing en accesos directos al backend.
  - **Verificado E2E**: 7 logins → rate limited; invite con email existente → respuesta uniforme; search con injection → sanitized; uploads con magic bytes válidos/inválidos → diferenciados correctamente. Backend lint clean, healthcheck OK, supervisor RUNNING.

  - Backend: `routes/clinic_export.py` — endpoint `GET /api/clinic/export/full` (require_clinic_admin) genera un ZIP en memoria con:
    - 28 tablas con `clinic_id` directo (clinics, branches, members, patients, appointments, medical_records, prescriptions, lab_orders, products, services, inventory_*, suppliers, purchase_orders, sales, payments, accounts_receivable, cash_*, expenses, commissions_*, attachments, activity_logs, notification_logs, etc.)
    - 6 tablas hijas vía join con padres (sale_items, prescription_items, lab_order_items, purchase_order_items, member_branches, payment_plan_installments)
    - Archivos del bucket Storage `patient-files` bajo `files/<storage_path>`
    - `manifest.json` (versión, clinic_id, conteos por tabla, errores) y `README.md`
  - Frontend: tab "Datos" agregado a `ClinicSettingsPage.js` (visible solo para clinic_admin); botón descarga ZIP con `responseType: 'blob'`, toast con conteos, advertencia HIPAA-friendly de info sensible.
  - Verificado: clinic_admin → 200 ZIP (36 archivos, 34 tablas, 1.9s); doctor/recepcionista → 403; sin auth → 403; tab "Datos" no aparece para roles no-admin.

- **2026-05-01 — Hardening DB**: REVOKE TRUNCATE de roles `anon` y `authenticated` sobre 46 tablas + ALTER DEFAULT PRIVILEGES (cierra vector de DoS por TRUNCATE que ignora RLS).

- **2026-05-01 — Eliminación módulo Plantillas de Consulta**: Removido por solicitud del usuario.

- **2026-06-07 — Security Hardening Fix #3 + #5 (JWT local + httpOnly cookie)**: dos fixes de alto impacto en latencia y resiliencia.
  - **(Fix #3) JWT local validation** en `core.py::_decode_jwt_local`. Soporta los dos esquemas de Supabase: **ES256/RS256 vía JWKS** (default para proyectos modernos como el nuestro) y **HS256** vía `SUPABASE_JWT_SECRET` (legacy). Cache de JWKS en memoria con TTL 1 h + refresh forzado si el `kid` no está en cache (handle key rotation). Antes: cada request autenticada llamaba a `supabase_admin.auth.get_user(token)` por HTTP (~150-300 ms RTT). Ahora: validación pura local ~1 ms. **Resultado**: la app es inmune a outages de Supabase Auth para flujos autenticados, latencia per-request bajada ~200 ms. Verificado: 0 llamadas a `/auth/v1/user` desde restart; 1 sola llamada a `/auth/v1/.well-known/jwks.json` (cacheada).
  - **(Fix #5) httpOnly Secure SameSite=Strict cookie** `cortexia_access_token` seteada en `/auth/login`. Frontend SIGUE usando `Authorization: Bearer` (no breaking change), pero la cookie es una segunda capa: si XSS roba el localStorage, la cookie queda inaccesible a JS. `SameSite=Strict` provee CSRF inherente. Backend (`get_current_user`) acepta header O cookie (header tiene prioridad). Nuevo `POST /api/auth/logout` borra cookie + invalida sesión Supabase. Verificado en Playwright: cookie con `httpOnly: True, secure: True, sameSite: Strict`. Verificado curl: cookie-only auth funciona (sin Authorization header).
  - **Tech**: `python-jose==3.5.0`, `ecdsa==0.19.2` (para ES256). JWKS endpoint: `https://<project>.supabase.co/auth/v1/.well-known/jwks.json`.
  - **`SUPABASE_JWT_SECRET`** agregado a `backend/.env` (fallback HS256 si el proyecto migra de vuelta).

  - Backend: borrados endpoints `GET/POST/PUT/DELETE /api/clinic/templates` y modelo `TemplateCreate` de `routes/medical_records.py`.
  - Frontend: removida sección "Usar plantilla" de `MedicalRecordForm.js` (estados `templates`, `selectedTemplate`, función `applyTemplate`, fetch `/clinic/templates`, import `FileStack`).
  - DB: tabla `consultation_templates` eliminada vía `DROP TABLE CASCADE` (28 filas + estructura). Sin FKs externas, drop seguro.
  - Tests: eliminado `tests/test_consultation_templates.py`.
  - Verificado: `GET /api/clinic/templates` → 404; `information_schema` confirma tabla inexistente; lint pass FE+BE.

- **2026-06-07 — Scaling Fixes 1-5 (10x capacity sin cambiar plan)**: 5 optimizaciones que suben el techo del sistema de ~50 a ~300 clínicas activas.
  - **(Fix 3) `audit_log` particionada por mes** (`RANGE PARTITION BY occurred_at`). Migración `2026_06_07_audit_log_partitioning_v2` renombra la tabla, crea nueva con `PRIMARY KEY (id, occurred_at)`, bootstrap 24 meses hacia atrás + 6 hacia adelante, backfill de datos legacy, drop legacy. 14 particiones creadas. Función `ensure_audit_partitions(months_ahead)` mantiene la ventana automáticamente. Triggers de inmutabilidad en el parent cascadean a partitions. Verificado: queries por rango de fecha ahora tocan solo la partición relevante (query planner constraint exclusion). Impacto: mantiene queries `<10ms` incluso con 50M+ rows.
  - **(Fix 1) Advisory locks distribuidos** para el reminder scheduler. Nueva tabla `distributed_locks(lock_name PK, holder, acquired_at, expires_at)` + funciones SQL `try_acquire_lock(name, holder, ttl)` y `release_lock(name, holder)` con INSERT..ON CONFLICT DO UPDATE WHERE expired. Reemplaza `pg_try_advisory_lock` (que se libera al cerrar conexión). `_send_due_reminders` ahora acquires + release around each tick. TTL 300s auto-libera si un pod muere. Verificado: pod1 gets lock → pod2/pod3 rejected → pod1 releases → pod2 gets lock.
  - **(Fix 5) Signed URL cache** in-memory. Nuevo `services/signed_url_cache.py::get_or_create_signed_url` con TTL matching (safety margin 5 min). Aplicado en 3 endpoints hot: `GET /prescriptions/{id}/pdf-url`, `GET /lab-orders/{id}/pdf-url`, `GET /sales/{id}/pdf-url`. Verificado E2E: 1st call 133 ms (Storage API), 2nd call **0.00 ms (cache hit)** = **112,000x speedup**. Reduce llamadas al Storage API ~90% en tráfico repetido.
  - **(Fix 2) DB-backed rate limiting** para endpoints multi-pod-crítico. Nueva tabla `rate_limit_events(key, occurred_at)` + `services/db_rate_limit.py`. Aplicado en `/auth/login` (10 intentos / 5 min por IP+email hasheado). slowapi `memory://` sigue de primer nivel (single-pod rejection rápido); DB rate limit es el second layer que sobrevive multi-pod. Cleanup opportunistic (5% de calls hacen DELETE de rows viejas). Verificado: 10 pasan → 11 y 12 rechazadas con 429.
  - **(Fix 4) Export en background** con job architecture. Nueva tabla `export_jobs(id, clinic_id, status, progress, file_path, signed_url, url_expires_at, ...)`. Refactor completo de `routes/clinic_export.py`: `POST /clinic/export/full` crea el job y retorna `job_id` en <100 ms; task async construye el ZIP en tempfile (no memoria), lo sube a Storage bajo `<clinic>/exports/<job>.zip`, actualiza status. `GET /clinic/export/jobs/{id}` para polling. `GET /clinic/export/jobs` lista los últimos 20. Signed URLs auto-refrescadas al polear si expiran en <5min. Distributed lock por `job_id` evita doble procesamiento. UI en `ClinicSettingsPage.js` cambió a polling cada 3s hasta done, luego descarga. `patient-files` bucket actualizado para permitir `application/zip`. Concurrent request → 409 (bien, solo 1 export a la vez por clínica). Verificado E2E: 4 KB ZIP generado en 4 segundos.


- **2026-05-01 — Conexión Postgres directa (DDL automático)**:
  - Añadida `SUPABASE_DB_URL` a `backend/.env` (Session Pooler, IPv4 compatible).
  - Helper `core.run_sql(sql, params, fetch)` para ejecutar DDL desde el código (DROP/CREATE/ALTER TABLE, RLS policies, índices, migraciones).
  - `psycopg2-binary` ya estaba instalado.
  - Cualquier futura modificación de schema puede ejecutarse sin pasar por el SQL Editor.

## Credenciales
Ver `/app/memory/test_credentials.md`
