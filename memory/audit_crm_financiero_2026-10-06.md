# Auditoría técnico-funcional (QA + contabilidad) — Cortexia Medical CRM
Fecha: 2026-10-06
Clínicas de prueba usadas: "Clinica Test A Auditoria" (id 4687b2ad-6530-43aa-948a-92dc0cdb5aae), "Clinica Test B Auditoria" (id 09f2caf3-c3b8-43fb-b2bb-dad5dc9c497e)
Credenciales: audita@test-cortexia.com / AuditTest2026! · auditb@test-cortexia.com / AuditTest2026!

## Hallazgos críticos confirmados con evidencia (ver chat para detalle completo)
1. `routes/patients.py::create_patient` — sin validación de duplicados (national_id/teléfono/nombre+dob). Solo el import masivo (CSV/XLSX) tiene dedupe.
2. `routes/sales.py::cancel_sale` línea ~729 — inserta `"quantity": float(it['quantity'])` en columna entera de `inventory_movements` → Postgres error 22P02 → la anulación SIEMPRE falla con productos. Stock nunca se repone, venta nunca cambia a 'cancelled'.
3. Atomicidad de ventas: no hay transacción/RPC real, solo rollback manual por `delete()`. El trigger de `inventory_movements` descuenta stock al INSERT pero no existe trigger inverso al DELETE → al hacer rollback de una venta fallida, el stock queda permanentemente desincronizado (perdimos 1 unidad fantasma en la prueba forzada).
4. Sin control de sobreventa: vendí 999 unidades con 14 en stock, la venta se procesó (200 OK) y `inventory_stock.quantity` quedó en -985.
5. `routes/sales.py::create_sale` línea ~478 — guarda `unit_cost = unit_price` (precio de venta) en vez del costo real del producto, en el movimiento de tipo 'sale'. Corrompe el kardex de costos.
6. `routes/accounts_receivable.py::register_ar_payment` — no valida `amount <= balance`; acepta sobre-pagos, los clampa a balance=0 silenciosamente, y `sales.amount_paid` queda por encima de `sales.total` (inconsistencia contable visible).
7. IVA: el POS suma 12% por defecto sobre el precio ingresado (`tax_rate ?? 12` en POSTab.js), pero los reportes (`income_report`, `pnl_report`, `executive_summary`) usan `sales.total`/`sale_items.total` (CON IVA) como "ingresos", inflando ventas/utilidad por el IVA cobrado a nombre del fisco.
8. No existe un reporte de "Flujo de caja" dedicado (cobros efectivo - gastos pagados), solo el resumen de sesión de caja (mezclado, no por rango de fechas).
9. Costeo de inventario: `products.cost_price` es un campo estático manual; nunca se recalcula con promedio ponderado ni último costo desde `purchase_order_items`/`inventory_batches`.

## Hallazgos que PASAN
- `clinic_id` siempre resuelto server-side desde el JWT (`require_clinic_member`), nunca del payload del cliente.
- Aislamiento multi-tenant vía API: 404/400/[] en todos los intentos cross-tenant (lectura directa, búsqueda, IDOR en venta).
- RLS habilitado en BD (patients, sales, accounts_receivable, products, expenses, payments, sale_items, inventory_stock) con policies correctas basadas en `get_user_clinic_ids()` — backstop a nivel BD, aunque el backend usa `service_role` (bypassa RLS) por lo que el aislamiento real depende 100% del filtrado `.eq('clinic_id', ...)` en cada endpoint.
- Venta de servicios no genera movimiento de inventario.
- Toda entrada/ajuste de stock pasa por `inventory_movements` (no hay edición directa de `inventory_stock.quantity`).
- Venta a crédito no ingresa a caja; AR creada correctamente con balance = total.
- P&L separa COGS de ingresos y resta gastos (estructura de utilidad real, no solo caja), trata ventas a crédito como ingreso devengado.
- Clínica B: reportes financieros en cero, sin fuga de datos de Clínica A.

## Estado de los datos de prueba al cierre
Dejé ambas clínicas de prueba intactas para inspección del usuario. Clínica A quedó con: 4 pacientes (incluye 1 duplicado intencional), 1 producto (stock=14, debería ser 15), 4 ventas (1 con anulación fallida que sigue 'completed'), 1 gasto Q400, 1 AR en estado corrupto (paid/0 por prueba de sobrepago intencional).
No se aplicó ningún fix de código — pendiente de aprobación del usuario.

## ✅ CORRECCIONES APLICADAS Y VERIFICADAS — 2026-10-06 (aprobación: "corrige todo")
Las 9 vulnerabilidades fueron corregidas y validadas 100% por el agente de pruebas (iteration_42.json, 7/7 tests).
1. ✅ `cancel_sale`: cantidad del movimiento convertida a entero `int(round(...))` → anulación devuelve 200 y repone stock.
2. ✅ `create_sale`: validación de sobreventa (stock disponible por producto/sucursal) → HTTP 400 "Stock insuficiente".
3. ✅ Rollback de venta fallida: inserta movimientos 'return' compensatorios (el trigger solo actúa en INSERT) → stock nunca queda desincronizado.
4. ✅ `create_sale`: el movimiento 'sale' guarda `unit_cost = products.cost_price` (costo real) en vez del precio de venta → kardex/COGS correcto.
5. ✅ `register_ar_payment`: bloquea sobre-pagos (`amount > balance + 0.01` → HTTP 400).
6. ✅ Reportes (income, pnl, executive-summary, by-branch): ingresos NETOS de IVA (`total - tax_amount`, `sale_items.subtotal`).
7. ✅ `create_patient`: dedupe por `national_id` y por `nombre + fecha de nacimiento`.
8. ✅ Nuevo endpoint `GET /clinic/reports/cash-flow` (cobros reales vs gastos pagados, excluye 'credit').
9. ✅ `process_po_receive`: recalcula `products.cost_price` con costo promedio ponderado al recibir órdenes de compra.
Archivo de pruebas de regresión: `/app/backend/tests/test_audit_9_fixes.py`.

