# Plan: Inicio rápido (onboarding guiado) para administradores

## Objetivo
Agregar un panel de "Inicio rápido" en la pantalla de Inicio (dashboard) que guíe a los
administradores de clínica a recorrer y poner en orden las áreas del sistema. Cada punto
del inicio rápido enlaza a su área correspondiente, se puede ir marcando como completado,
y muestra el avance. Al terminar de recorrer todo el flujo, aparece la opción de retirar
(ocultar) el panel desde el propio inicio.

## Quién lo ve
- Solo administradores de clínica.
- No aparece para médicos, recepción ni otros roles.

## Dónde aparece
- Como una tarjeta destacada en la parte superior de la pantalla de Inicio.
- Se muestra en cada visita al Inicio mientras no esté completado y retirado.

## Los pasos (propuesta, en orden)
Cada paso tiene: título, descripción corta, un botón "Ir al área" y una casilla
"Marcar como hecho" (se puede marcar y desmarcar).

Pasos base (siempre presentes):
1. Configura tu clínica — datos, logo y horario → Configuración
2. Agrega a tu equipo — invita médicos y personal → Configuración › Equipo
3. Define roles y permisos → Configuración › Roles
4. Registra tus pacientes → Pacientes
5. Agenda tu primera cita → Agenda
6. Emite una receta → Recetas
7. Crea una orden de laboratorio → Laboratorio

Pasos que aparecen solo si esa área está activa para la clínica (según su plan/módulos):
8. Configura tu inventario → Inventario
9. Abre caja y registra una venta → Ventas / POS
10. Revisa cuentas por cobrar → Cuentas por cobrar
11. Registra gastos → Gastos
12. Configura comisiones → Comisiones
13. Consulta reportes financieros → Reportes
14. Registra tus sucursales → Sucursales (si multi-sucursal está activo)

(Se puede agregar, quitar o reordenar pasos si lo prefieres.)

## Cómo funciona
- "Ir al área" abre la sección correspondiente de forma normal; no marca el paso solo.
- El administrador marca cada paso manualmente cuando lo considere hecho.
- Indicador de progreso visible: "X de N completados" con barra de avance.

## Al terminar de recorrer todo el flujo
- Cuando todos los pasos visibles están marcados, aparece un botón "Retirar inicio rápido".
- Al retirarlo, el panel deja de mostrarse en el Inicio.
- Queda una opción en Configuración para volver a mostrarlo (por si se retiró por error).

## Decisiones asumidas (avísame si prefieres otra cosa)
- El avance y el retiro son a nivel de clínica (compartidos entre todos los administradores),
  no por usuario. Así, si un administrador ya avanzó, se refleja para los demás.
- El marcado es manual (no se auto-detecta con datos reales). Más adelante se podría añadir
  auto-marcado (p. ej., marcar "Registra pacientes" cuando ya exista al menos uno).
- Los pasos de áreas cuyo módulo/plan está inactivo no se muestran, para no pedir pasos que
  la clínica todavía no puede usar.

## Pregunta abierta
- ¿El listado y el orden de pasos propuesto te sirven, o quieres ajustar cuáles incluir?
