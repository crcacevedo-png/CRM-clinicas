# Rebrand a Cortexia Medical, Cortesía más visible y Limpieza de precios

Rebranding completo del producto SaaS: todos los textos, nombres de producto y claves internas pasan de "ClinicWise" a "Cortexia Medical". Además se agrega el toggle de cortesía en la página de detalle de clínica y se archivan los precios huérfanos que quedaron en Stripe tras el sync.

## Para quién
Super admin que opera la plataforma (gestiona cobros, planes y clínicas) y clinic admins que ven etiquetas de marca en banners, emails, portal de pago y pantalla de bloqueo.

## Funcionalidades principales y experiencia

**Rebrand "ClinicWise" → "Cortexia Medical"** (frontend, backend, Stripe, emails, claves internas)
- Textos visibles al usuario: títulos, logos, placeholders, correos, pantalla de bloqueo y banner "Pago vencido"
- Productos en Stripe renombrados: `ClinicWise · Professional` → `Cortexia Medical Professional`, `ClinicWise · Enterprise` → `Cortexia Medical Enterprise`
- Metadata interna en Stripe: `managed_by: clinicwise` → `managed_by: cortexia_medical`
- `lookup_key` de precios: `clinicwise_professional_monthly` → `cortexia_professional_monthly` (idem yearly y enterprise), transferidos sobre los IDs existentes, sin cortar subscripciones vigentes
- Las subscripciones Stripe en curso siguen funcionando porque apuntan a `price_id`, no a `lookup_key`

**Toggle de cortesía en dos lugares**
- Donde ya existe hoy: menú de 3 puntos en la lista de clínicas (`/admin/clinicas`) con "Marcar como cortesía" / "Remover cortesía" + badge amarillo "CORTESÍA" al lado del nombre
- Nuevo: Switch "Clínica de cortesía" dentro de la página de detalle de la clínica (`/admin/clinicas/:id`), junto a los switches ya existentes, con texto explicativo ("exenta de cobros Stripe, no entra al flujo de pago vencido")
- Al activar cortesía desde cualquiera de los dos lugares se limpia automáticamente el bloqueo por pago vencido y el período de gracia

**Limpieza de precios huérfanos en Stripe (one-shot)**
- Script administrativo que corre una sola vez contra producción
- Alcance: solo los dos productos ya sincronizados (`Cortexia Medical Professional` y `Cortexia Medical Enterprise`), nunca productos externos
- Lista los precios activos de esos dos productos que **no están referenciados** por ningún plan en la tabla `plans` (es decir, los $39/$79 originales que se duplicaron durante el primer sync)
- Imprime la lista antes de archivar y pide confirmación en consola
- Archiva vía `stripe.Price.modify(active=False)` (archivar, no eliminar — Stripe no permite borrar precios usados)

## Flujo de usuario

**Super admin que marca una clínica como cortesía desde el detalle**
1. Entra a `/admin/clinicas/:id`
2. Ve un bloque "Facturación" con el Switch "Clínica de cortesía" apagado
3. Lo activa → confirmación nativa ("exime a esta clínica del cobro mensual") → toast de éxito
4. El badge amarillo "CORTESÍA" aparece junto al nombre tanto en el detalle como en la lista
5. Si la clínica estaba bloqueada por pago, se destraba y se muestra "activa" automáticamente

**Super admin que ve el rebrand en producción tras el deploy**
1. Entra al panel y ve "Cortexia Medical" en todos los títulos, breadcrumbs y footer
2. Entra a Cobros → los nombres de plan se leen de la BD como "Professional / Enterprise" sin prefijo de marca (la marca se renderiza aparte en el header de página)
3. Entra a Stripe Dashboard → los productos aparecen como "Cortexia Medical Professional" y "Cortexia Medical Enterprise"
4. Un clinic admin recibe un email de pago vencido con asunto "⚠ Pago vencido en {nombre clínica}" y firma "Cortexia Medical"

## UI/UX feel

- El rebrand mantiene el minimalismo actual: cambio de palabra, mismos componentes, misma paleta y espaciado
- El Switch de cortesía usa el mismo estilo de los switches existentes en la página de detalle (slate con acento amarillo cuando activo, consistente con el badge "CORTESÍA")
- Las confirmaciones nativas (`window.confirm`) se mantienen por simplicidad; sin modales adicionales
- Textos del Switch en el detalle:
  - Label: "Clínica de cortesía"
  - Help text: "Exenta de cobro Stripe. No entra al flujo de pago vencido ni se le crea subscripción."
- El badge amarillo "CORTESÍA" (ya existente en la lista) también aparece en el header de la página de detalle junto al nombre de la clínica para feedback inmediato

## Fases

**Fase 1 (MVP, se construye ahora)**
1. Rebrand completo: frontend (texto, logos, placeholders, pantallas de bloqueo y banner), backend (nombres de productos, metadata, lookup_keys, emails, código que arma strings "ClinicWise · ..."), test credentials file si contiene referencias
2. Script de migración Stripe (`services/rebrand_migration.py`) que:
   - Renombra los dos productos
   - Actualiza metadata.managed_by
   - Para cada `lookup_key`: desactiva el viejo `clinicwise_*`, transfiere el nuevo `cortexia_*` sobre el mismo `price_id`
   - Actualiza la tabla `plans` si cambia algún ID (no debería, los `price_id` se mantienen)
   - Idempotente: puede re-correrse sin romper nada
3. Toggle de cortesía en la página de detalle de clínica (`ClinicDetailPage.js`): bloque "Facturación" con Switch, badge en el header, confirmación + toast + refetch
4. Script `services/cleanup_orphan_prices.py` (ejecución manual) que lista y archiva precios huérfanos en los 2 productos sincronizados
5. Smoke tests: screenshot del detalle de clínica con el switch, screenshot de la lista con el badge, verificación manual de los productos en Stripe tras la migración

**Fase 2 (siguiente)**
- Modal de edición completa de clínica desde la lista (plan, email, país, admin principal) sin tener que entrar al detalle
- Historial de cambios de estado de cortesía en la pestaña de Auditoría

**Fase 3 (backlog)**
- Alertas Slack/email al super admin cuando una clínica entra en gracia o se bloquea
- Reporte mensual de clínicas en cortesía (quiénes, cuándo se activaron, descuento acumulado estimado)

## Supuestos

- "Cortexia Medical" se usa en singular y con mayúsculas iniciales en todos los lugares (sin logo con ícono adicional por ahora, el logo existente de Cortexia Medical en el sidebar se mantiene)
- El prefijo `clinicwise_` en lookup_keys se reemplaza por `cortexia_` (no `cortexia_medical_` para mantener keys cortas)
- La metadata `plan_code` queda igual (`professional`, `enterprise`) — no es parte del rebrand
- Las subscripciones activas no se tocan: siguen cobrando contra el mismo `price_id` que ya tienen. El rebrand es puramente de etiquetas y claves
- El script de precios huérfanos imprime en consola y espera `yes` por stdin antes de archivar; no se le expone endpoint HTTP ni se agrega UI
- Si al correr el script de rebrand se encuentra un `lookup_key` nuevo ya existente (por ejemplo si alguien lo creó manualmente), el script falla visiblemente en vez de sobrescribir, para que un humano decida
- No se migran correos ya enviados ni facturas pasadas; el rebrand aplica desde el momento del deploy en adelante
- El rebrand incluye el nombre del Checkout de Stripe (`line_items[0].price.product.name`), pero no toca `success_url` ni rutas internas
- El archivado de precios se hace vía `active=False`; los precios archivados siguen apareciendo en Stripe Dashboard pero no son seleccionables en nuevos checkouts
- No se corre contra Stripe sandbox/test (preview) porque la llave actual es un placeholder; todas las operaciones Stripe se verifican directamente contra la cuenta live en producción tras el deploy
