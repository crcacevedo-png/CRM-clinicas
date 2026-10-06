# Cobros SaaS: Fuente única de precios, Cortesía, Falta de pago y CRUD completo

Alineación del cobro mensual con el precio real de cada plan, modo cortesía para clínicas regaladas, bloqueo automático por falta de pago con pantalla "Pago vencido", y gestión completa (crear / editar / eliminar / restaurar) de clínicas y usuarios desde el Super Admin.

## Who it's for

- **Super Admin** (dueño de la plataforma): necesita cuadrar reportes de ingresos con los precios reales de los planes, regalar acceso a clínicas aliadas, forzar el pago cuando una tarjeta falla, y mantener limpios los catálogos de clínicas y usuarios sin editar la base de datos a mano.
- **Administradores de clínica**: cuando su cobro falla, deben saber qué pasó, cuántos días les quedan de gracia y cómo pagar; si no actualizan la tarjeta, el sistema los pone en pausa hasta regularizar.

## Core features and experience

- **Precio y límites del plan como fuente única de verdad.** Toda vista de cobros (Super Admin → Cobros, Clínica → Configuración → Plan, reportes y KPIs) muestra el precio tomado del plan en el momento de ver, no una copia guardada por clínica. Los límites (máximo de usuarios, pacientes y almacenamiento) también se leen del plan en el momento, nunca se guardan por clínica. Si un plan sube de $39 a $49 o cambia su límite de usuarios de 10 a 15, el cambio se refleja de inmediato en todas las clínicas suscritas a ese plan. El reporte "Ingresos por plan" deja de mostrar sumatorias confusas (ej. "$78 Professional" cuando dos clínicas pagan $39 cada una) y pasa a mostrar el precio unitario del plan, el conteo de clínicas, y el MRR total aparte en una línea diferente.
- **Cortesía.** El Super Admin puede marcar cualquier clínica como "Cortesía" desde su panel. Una clínica en cortesía:
  - No necesita suscripción Stripe para operar.
  - Se queda indefinidamente activa hasta que el Super Admin la desactive.
  - No participa en el MRR / ARR del reporte (se cuenta aparte como "Cortesía: N clínicas").
  - Nunca entra al flujo de bloqueo por falta de pago, aunque Stripe la haya marcado como `past_due`.
  - Mantiene su etiqueta de plan (Basic, Professional, Enterprise) para fines de permisos y límites.
- **Flujo de falta de pago.** Cuando Stripe reporta un pago fallido (`invoice.payment_failed` o `subscription.status = past_due`):
  - La clínica entra en periodo de gracia de **3 días**. Durante ese tiempo:
    - Un banner rojo aparece en todas las pantallas de la clínica indicando "Pago vencido — Actualiza tu método de pago antes del <fecha> o perderás acceso", con un botón "Pagar ahora" que abre el Stripe Customer Portal.
    - Se envía correo a **todos los administradores activos de la clínica** el día 0 (al detectar la falla) con instrucciones.
    - Se reintenta el cobro automáticamente por reglas de Stripe.
  - Al **día 4**, si el pago sigue sin aplicarse:
    - La clínica se bloquea. Todas las rutas devuelven una pantalla única "Pago vencido" con el logo, un mensaje claro, y un solo botón "Pagar ahora" que lleva al Customer Portal de Stripe. Nada más se puede ver ni hacer.
    - El API bloquea toda llamada que no sea de pago/portal con código HTTP 402.
    - Se envía un segundo correo a todos los administradores activos de la clínica indicando el bloqueo.
  - Cuando el pago se aplica (webhook `invoice.payment_succeeded` o `subscription.status = active`), el bloqueo se levanta automáticamente, el banner desaparece y la clínica vuelve a operar sin intervención manual.
  - Un cron diario revisa clínicas con suscripciones en estado `past_due`/`unpaid` cuyo periodo de gracia venció y activa el bloqueo si Stripe no lo resolvió solo.
  - Plan `basic` (precio = $0) nunca entra al flujo de bloqueo: no tiene suscripción Stripe que pueda fallar.
- **CRUD completo de clínicas.** El Super Admin puede desde la vista Clínicas:
  - Crear una clínica (ya existe).
  - **Editar todos los campos**: nombre, slug, país, ciudad, dirección, teléfono, email, zona horaria, plan, estado activo/inactivo, flag de cortesía. Los límites de usuarios / pacientes / almacenamiento no son editables por clínica: se heredan del plan en todo momento. Al cambiar el plan, si la clínica tiene suscripción Stripe activa, se cambia la suscripción en Stripe automáticamente con prorrateo; si la clínica está en cortesía o no tiene suscripción, solo se cambia el plan local sin tocar Stripe.
  - Enviar a Papelera (ya existe).
  - Restaurar desde Papelera (ya existe).
  - Purgar permanentemente (ya existe).
- **CRUD completo de usuarios.** El Super Admin puede desde la vista Usuarios:
  - Crear un usuario (ya existe).
  - **Editar todos los campos**: nombre, apellido, email (actualizando también en Supabase Auth), teléfono, rol, sucursales asignadas, estado activo/inactivo.
  - Reiniciar contraseña (ya existe).
  - Mover a otra clínica (ya existe).
  - Enviar a Papelera (ya existe).
  - Restaurar / Purgar (ya existe).

## User flow

**Super Admin regala una clínica.**
1. Entra a Clínicas, ubica la clínica, abre el menú de acciones → "Marcar como cortesía". Confirma el plan que quiere regalar.
2. La clínica aparece etiquetada con un badge amarillo "Cortesía". El Super Admin puede en cualquier momento revertir con "Quitar cortesía".

**Clínica entra en falta de pago.**
1. Stripe reintenta cobrar la tarjeta → falla. El webhook llega al backend. Se guarda `payment_grace_until = ahora + 3 días`, se envía email a todos los administradores de la clínica.
2. Un admin entra al sistema al día siguiente → ve un banner rojo con cuenta regresiva y un botón "Pagar ahora".
3. Si paga antes del día 4 → Stripe envía `invoice.payment_succeeded`, el banner desaparece, todo sigue normal.
4. Si no paga → al día 4 el cron bloquea la clínica. Al próximo login, en vez de ver el panel, se ve la pantalla "Pago vencido" con un solo botón que abre el Customer Portal.
5. El admin actualiza la tarjeta en el portal, Stripe cobra, webhook llega, bloqueo se levanta.

**Super Admin edita una clínica o un usuario.**
1. Entra a Clínicas → clic en una fila → se abre un panel con todos los campos editables agrupados por sección (Datos generales, Plan, Cortesía). Los límites se muestran como solo-lectura con el valor del plan actual.
2. Modifica lo que necesita. Si cambia el plan y la clínica tiene suscripción Stripe activa, aparece una confirmación: "Esto cambiará también la suscripción en Stripe con prorrateo. ¿Continuar?".
3. Guarda. Toda la acción queda en la bitácora de auditoría.
4. Para usuarios es el mismo patrón, con un botón "Editar" en cada fila que abre un modal con todos los campos.

## UI/UX feel

- **Banner de pago vencido**: rojo sobre fondo claro, fijo arriba de todas las pantallas de la clínica, con icono de alerta, cuenta regresiva ("Faltan 2 días para el bloqueo"), y un botón primario grande "Pagar ahora". No se puede cerrar.
- **Pantalla de bloqueo**: pantalla completa centrada, logo de la clínica arriba, icono grande de tarjeta rechazada, título "Pago vencido", párrafo breve, un solo botón grande "Pagar ahora" que lleva al portal, y un enlace secundario a soporte. Mismos colores que el resto del sistema, nada agresivo.
- **Badge Cortesía**: pequeño badge amarillo con icono de regalo, visible en la fila de clínicas (Super Admin) y en el banner superior del dashboard de la clínica para que su admin sepa que su acceso es cortesía.
- **Reporte "Ingresos por plan"**: cada tarjeta muestra el precio unitario del plan (del campo `plans.price_monthly`), un conteo de clínicas pagantes, y un MRR del plan debajo. Las cortesías aparecen en una tarjeta aparte, sin precio, con el solo conteo.
- **Modal de editar clínica/usuario**: dialog ancho con secciones colapsables, campos agrupados, botón primario "Guardar cambios" abajo a la derecha. Los límites se muestran como texto gris no editable (ej. "Usuarios: hasta 10 — definido por el plan Professional"). Si al cambiar plan se va a tocar Stripe, un cuadro informativo aparece dentro del modal antes de guardar.

## Implementation phases

### Phase 1 — MVP (se construye ahora)

- Reporte y vistas de cobros leen `plans.price_monthly` y los límites del plan en el momento, en vez de copias guardadas en la clínica. KPIs (MRR, ARR, Ingresos por plan) se recalculan desde los planes vigentes. Las columnas de límites por clínica se retiran del CRUD (solo se muestran como herencia del plan).
- Nueva columna `is_courtesy` en clínicas. Toggle para marcar/desmarcar desde el panel de Super Admin, con confirmación. Las clínicas en cortesía quedan excluidas del cálculo de MRR y del flujo de bloqueo, y se muestran aparte en el reporte.
- Flujo completo de falta de pago: campos `payment_grace_until`, `is_payment_blocked`; webhooks de Stripe actualizan estos campos; cron diario que aplica el bloqueo al día 4; dos correos (día 0 y día 4) a todos los administradores activos de la clínica; banner rojo en todas las pantallas durante gracia; pantalla única de bloqueo que reemplaza el dashboard; middleware/dependencia en el backend que devuelve 402 excepto para rutas de pago y portal; levantamiento automático al cobrarse.
- CRUD completo de clínicas: endpoint para editar todos los campos editables (incluido cambio de plan con reemplazo de suscripción Stripe prorrateado); modal en el panel Super Admin con todos los campos agrupados y límites del plan en modo solo-lectura.
- CRUD completo de usuarios: endpoint para editar todos los campos (incluido actualización de email en Supabase Auth); modal en el panel Super Admin con todos los campos.
- Toda acción destructiva o de cambio relevante queda registrada en `audit_log` con actor, entidad y snapshot.

### Phase 2 — Automatizaciones y visibilidad

- Reintento de pago inteligente: botón "Reintentar cobro ahora" desde el banner, sin esperar al próximo intento de Stripe.
- Historial de intentos de cobro por clínica (listado con fecha, resultado y motivo) accesible desde la vista de la clínica.
- Alerta a Slack / email para el Super Admin cuando una clínica entra en estado bloqueado (día 4).
- Reporte de churn: clínicas que entraron en bloqueo y no se recuperaron en N días → candidatas a cancelación.
- Vista "Mis cortesías" filtrable en Super Admin con el responsable comercial de cada cortesía.

### Phase 3 — Políticas avanzadas

- Políticas configurables de falta de pago por plan (ej. Enterprise con 7 días de gracia en vez de 3).
- Descuentos y cupones aplicables desde el panel Super Admin (crea cupones Stripe y los asigna).
- Downgrades programados (ej. "cancelar al final del periodo") y upgrades con fecha futura.
- Reporte financiero mensual descargable en PDF con MRR, ARR, churn, nuevos clientes y cortesías regaladas.

## Assumptions

- "Cortesía nunca expira" — una clínica en cortesía queda así hasta que un super admin cambie manualmente el flag; no hay fecha de vencimiento automática en esta fase.
- "Bloqueo total al día 4" — cuando el bloqueo se activa, el único botón disponible es "Pagar ahora" que lleva al Stripe Customer Portal; no hay modo solo-lectura intermedio, el admin tampoco puede ver sus datos. Los usuarios no-admin de la clínica ven la misma pantalla si intentan entrar.
- "Cambio de plan en Stripe automático" — al editar el plan de una clínica con suscripción activa desde el panel super admin, se llama a Stripe para cambiar el item de suscripción, con prorrateo (`proration_behavior = create_prorations`). Si la clínica no tiene suscripción activa o está en cortesía, solo se cambia el plan localmente.
- Correos de falta de pago (día 0 y día 4) se envían a todos los usuarios con rol `clinic_admin` activo en la clínica. Si no hay ningún admin activo, se registra el evento pero no se envía nada.
- El periodo de gracia de 3 días se cuenta en UTC desde el momento del webhook de pago fallido; una vez bloqueada, la clínica se desbloquea al recibir cualquier webhook de pago exitoso (`invoice.payment_succeeded` o `subscription.status = active`).
- Los límites (max_users, max_patients, max_storage_mb) viven en `plans` y nunca se guardan por clínica. Cualquier override previo en una fila de clínica se ignora y queda obsoleto; el super admin ya no puede ajustar límites por clínica desde el panel.
- Cambio de email de usuario desde CRUD también actualiza el email en Supabase Auth. Si la clave de Supabase falla, la operación entera se revierte y se muestra error, no se deja al usuario con emails distintos en Auth y en la base.
- Plan `basic` con `price_monthly = 0` nunca entra al flujo de bloqueo (no hay suscripción Stripe para fallar); solo los planes de pago participan.
- Toda vista de precios ("Precio/mes" en Cobros, "Ingresos por plan", KPIs de MRR/ARR) se recalcula leyendo `plans.price_monthly` en el momento, excluyendo cortesías. Si un plan sube de precio y hay clínicas con suscripciones Stripe antiguas al precio anterior, la vista local reflejará el precio nuevo mientras que Stripe seguirá cobrando el precio al que se suscribieron; esto es consistente con cómo funciona Stripe y el super admin puede sincronizar manualmente desde Cobros → Sincronizar planes para alinear.
