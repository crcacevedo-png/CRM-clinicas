# Rediseño del flujo de Pago con Seguro

Un cargo hecho a un seguro médico ya no se cuenta como dinero recibido en caja: se separa del monto que el paciente paga hoy (copago o deducible) y se registra como una cuenta por cobrar a la aseguradora, que se marcará como cobrada cuando la aseguradora efectivamente pague.

## Who it's for
Recepcionistas, cajeros y administradores de clínicas que atienden pacientes con cobertura de seguro médico, y que necesitan saber en todo momento cuánto entró realmente a caja hoy y cuánto está pendiente de cobro con cada aseguradora.

## Core features and experience
- **Separación clara entre pago del paciente y cargo al seguro.** El cobro en el punto de venta muestra ambos montos por separado y calcula por sí solo el saldo pendiente restante.
- **La aseguradora deja de ser un “método de pago”.** Se elimina del selector de métodos de pago, y en su lugar aparece un panel dedicado arriba de los pagos del paciente.
- **Autocompletado de aseguradoras existentes.** Se mantiene la lista de aseguradoras que la clínica ya ha usado, con opción de agregar una nueva sobre la marcha.
- **La cuenta por cobrar refleja al deudor real.** Cuando parte del total va al seguro, la cuenta por cobrar asociada guarda el nombre de la aseguradora y el monto que le corresponde; el resto (si el paciente además queda a deber algo) queda como saldo a nombre del paciente en la misma cuenta.
- **Reporte de aseguradoras coherente con la caja.** El “cobrado por aseguradoras” en el reporte solo suma pagos efectivamente recibidos de aseguradoras (pagos aplicados a cuentas por cobrar de seguro), no promesas de pago al momento de la venta. El “pendiente” refleja lo que aún debe cada aseguradora.
- **Cobro del seguro cuando llega el pago.** Cuando la aseguradora paga, el usuario abre esa cuenta por cobrar en el módulo de Cuentas por Cobrar y usa el botón existente “Registrar pago” con el método real (transferencia, cheque, etc.). Ese pago sí cuenta como cobrado en el reporte de aseguradoras.
- **Migración retroactiva de ventas anteriores.** Las ventas ya registradas con “seguro” como método de pago se corrigen automáticamente para que los importes queden como cargo al seguro (cuenta por cobrar) y no como dinero recibido en caja. El historial visible se preserva, pero los totales de caja, cierres previos y reportes quedan alineados con la nueva definición.
- **Manual de usuario actualizado.** La sección de Ventas / Punto de venta y la de Cuentas por cobrar se reescriben para describir el nuevo flujo, incluyendo cómo registrar el pago que llega después desde la aseguradora.

## User flow
1. En el punto de venta, el cajero arma el carrito y presiona “Cobrar”.
2. Se abre el diálogo de cobro con el total a pagar. Encima de los métodos de pago aparece un panel “¿Parte del total va a un seguro médico?”. El cajero, si aplica, elige la aseguradora del autocompletado (o escribe una nueva) y captura el monto que cubre esa aseguradora.
3. Debajo, el cajero registra lo que el paciente paga hoy (efectivo, tarjeta, transferencia, etc.). El diálogo muestra en tiempo real: total, cargo al seguro, pagado hoy, cambio si aplica, y saldo pendiente del paciente.
4. Al confirmar, el sistema crea la venta con los pagos del paciente como cobrado real y, si el cargo al seguro es mayor a cero, crea una cuenta por cobrar a nombre de la aseguradora con ese monto. Si además queda saldo del paciente, ese saldo se registra en la misma cuenta con desglose visible en el detalle.
5. Días después, cuando la aseguradora deposita, el usuario abre la cuenta por cobrar correspondiente en el módulo de Cuentas por Cobrar y presiona “Registrar pago” con el método real. Ese abono se refleja de inmediato en el reporte de aseguradoras como “cobrado” y reduce el pendiente.
6. En el reporte de aseguradoras, el usuario ve por cada aseguradora: pendiente actual, cobrado en el período, acumulado, participación y el desglose mensual — todo alineado con lo que realmente entró a caja.

## UI/UX feel
- El panel de seguro se ve claramente separado de los métodos de pago: fondo suave azul con ícono de escudo, para diferenciarlo del bloque verde/teal de pagos reales.
- El resumen del diálogo destaca tres números en la misma línea: “Pagado hoy”, “Cargo al seguro”, “Saldo pendiente”, con colores distintos, para que el cajero entienda de un vistazo qué está entrando a caja y qué está quedando por cobrar.
- Si no se usa seguro, el panel se muestra colapsado con un simple “¿Parte va a un seguro? Agregar” para no ensuciar la vista de cobros comunes.
- El diálogo bloquea confirmar si el total no cuadra (paciente + seguro + pendiente ≠ total), con un mensaje claro de qué falta.
- En el módulo de Cuentas por Cobrar, la etiqueta “Seguro” en la tabla se mantiene y sigue siendo el indicador de que ese saldo pertenece a una aseguradora.

## Implementation phases

### Phase 1 — MVP (se construye ahora)
- Rediseño del diálogo de cobro en el punto de venta con el panel dedicado de seguro fuera del selector de métodos.
- Backend deja de aceptar “seguro” como método de pago; el cargo al seguro entra por un campo separado en la venta.
- Creación de la cuenta por cobrar con nombre de aseguradora y monto asignado; el resto del saldo del paciente queda en la misma cuenta con etiqueta clara.
- Migración retroactiva única que corrige las ventas históricas con “seguro” como método de pago: elimina esos pagos de caja, crea/ajusta la cuenta por cobrar y deja el historial consistente. Se registra en auditoría con conteo de filas afectadas.
- Reporte de aseguradoras: el “cobrado” pasa a alimentarse de pagos aplicados a cuentas por cobrar de seguro. El “pendiente” sigue leyendo el balance actual de cuentas por cobrar con aseguradora.
- Manual de usuario actualizado con el nuevo flujo y con instrucciones específicas para cuando llega el pago de la aseguradora.

### Phase 2 — Cobro y conciliación mejorados
- Vista dedicada “Por cobrar a aseguradoras” dentro del módulo de Cuentas por cobrar, con filtros por aseguradora y por antigüedad, y acción rápida “Registrar pago del seguro”.
- Registrar pago de aseguradora en lote: un solo depósito puede cubrir varias cuentas por cobrar de la misma aseguradora.
- Referencia opcional del número de autorización del seguro por cada venta.

### Phase 3 — Contabilidad de aseguradoras
- Estados de cuenta descargables en PDF por aseguradora y por período, listos para enviar.
- Alertas automáticas de cuentas por cobrar de aseguradora con más de N días de antigüedad.
- Comisión por aseguradora (porcentaje que la aseguradora descuenta al pagar) reflejada como gasto o descuento.

## Assumptions
- El cargo al seguro es un solo monto por venta y una sola aseguradora por venta. No se soportan por ahora ventas partidas entre dos aseguradoras distintas.
- Si el paciente paga hoy más que la diferencia entre total y seguro, el excedente se toma como cambio (mismo comportamiento actual con efectivo).
- Si el paciente además queda a deber una parte propia (no cubierta por seguro y no pagada hoy), esa deuda se registra en la misma cuenta por cobrar del seguro, con el saldo del paciente diferenciado en las notas y visible en el detalle de la cuenta. No se crean dos cuentas por cobrar separadas para la misma venta.
- La aseguradora capturada al vuelo (sin autocompletado) se guarda automáticamente como aseguradora de la clínica para futuros cobros, tal como ya funciona hoy.
- En el reporte de aseguradoras, “cobrado” refleja desde este cambio en adelante solo pagos aplicados a cuentas por cobrar con nombre de aseguradora. La migración retroactiva ajusta el histórico para que el comportamiento sea uniforme antes y después.
- La migración retroactiva se ejecuta una única vez, es idempotente (se puede reintentar sin duplicar) y se puede correr manualmente desde un endpoint protegido para super admin en caso de que quede una clínica pendiente.
- Los cierres de caja anteriores que ya se generaron no se recalculan hacia atrás; solo el histórico de datos base queda corregido. Si un cierre de caja imprimió “Q X en seguro” como ingreso, ese PDF ya está entregado y no se regenera.
- El botón “Registrar pago” en Cuentas por Cobrar se mantiene tal cual está hoy; sirve tanto para pagos del paciente como para pagos del seguro. No se agrega un botón especial.
- La UI del panel de seguro solo se muestra si la clínica ya ha usado el seguro alguna vez o si el usuario despliega explícitamente el panel colapsado; no se muestra siempre para no distraer en clínicas que no manejan seguros.
