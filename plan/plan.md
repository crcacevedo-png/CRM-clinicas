# Plan: correo de bienvenida, ver contraseña, recuperación de contraseña y soporte

Cuatro funcionalidades nuevas. Decisiones ya confirmadas por el usuario (ver "Decisiones confirmadas").

---

## 1. Correo de bienvenida al crear una clínica

Cuando el Super Admin crea una clínica, se envía automáticamente un correo al administrador de esa clínica con:
- Bienvenida y nombre de la clínica.
- Su correo de acceso (usuario para iniciar sesión).
- Un enlace seguro para **crear/establecer su contraseña** (válido por tiempo limitado y de un solo uso).
- Recomendaciones para empezar: seguir el panel de "Inicio rápido" y descargar la Guía de usuario.

**Contraseña:** el correo **no** incluye la contraseña en texto plano (regla de seguridad). Lleva un enlace seguro para que el administrador la defina. La contraseña generada sigue mostrándose en pantalla al crear la clínica, por si el Super Admin desea entregarla por otro medio.

**Supuestos:**
- El enlace de "establecer contraseña" reutiliza el mecanismo del punto 3 (recuperación).
- El correo se envía al correo del administrador capturado al crear la clínica.
- Si el envío del correo falla, la clínica igual queda creada (el fallo de correo no bloquea la operación) y se informa el resultado.

---

## 2. Ver la contraseña en el login

Ícono de "ojo" en el campo de contraseña del login para mostrar u ocultar lo que se escribe.

---

## 3. Recuperación de contraseña ("Olvidé mi contraseña")

Enlace "¿Olvidaste tu contraseña?" en el login. El flujo:
1. La persona escribe su correo.
2. El sistema verifica que ese correo exista como Super Admin o como usuario de clínica **activo**.
3. Si existe: se envía un correo con un enlace seguro (un solo uso, vence en 60 min) para definir una nueva contraseña.
4. Si **no existe**: no se envía correo y se muestra el mensaje: **"Este correo no está registrado. Hable con su administrador."**

**Supuestos:**
- El enlace de recuperación vence a los 60 minutos y solo puede usarse una vez.
- La nueva contraseña debe cumplir las reglas de seguridad ya existentes.
- Hay un límite de intentos por correo/IP para evitar abuso.

---

## 4. Soporte: enviar mensajes y módulo del Super Admin

**Para cualquier usuario (con sesión iniciada):**
- Opción "Soporte" para enviar un mensaje (asunto + descripción).
- Puede ver sus propios mensajes y las respuestas recibidas dentro de la plataforma.

**Para el Super Admin:**
- Nuevo módulo "Soporte" en su panel para ver todos los mensajes entrantes, con quién y de qué clínica provienen.
- Puede responder cada mensaje y marcar su estado (abierto / respondido / cerrado).

**Entrega de la respuesta:** la respuesta queda visible **dentro de la plataforma** y además se envía una **notificación por correo** al usuario avisándole que tiene una respuesta (el correo lo invita a entrar a la plataforma a leerla).

**Supuestos:**
- Conversación simple con respuestas de ida y vuelta entre usuario y Super Admin.
- Solo usuarios con sesión pueden enviar soporte (sin formulario público anónimo).
- Estados: abierto, respondido, cerrado.

---

## Decisiones confirmadas
1. Correo de bienvenida: **sin** contraseña en texto plano; enlace seguro para definirla. ✅
2. Recuperación con correo no registrado: mostrar **"Este correo no está registrado. Hable con su administrador."** ✅
3. Respuesta de soporte: **en la plataforma + notificación por correo.** ✅
