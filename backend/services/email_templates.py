"""HTML email templates for Cortexia Medical.

All templates are inline-CSS only (best email client compatibility) and use
table-based layouts. Each function returns a dict {subject, html, text}.

Branding: teal accent (#0D9488), Cortexia Medical sender, support footer.
"""
from datetime import datetime


_BRAND_TEAL = "#0D9488"
_BG = "#F8FAFC"
_BORDER = "#E2E8F0"
_TEXT = "#1E293B"
_MUTED = "#64748B"


def _wrapper(*, preheader: str, content_html: str, footer_extra: str = "") -> str:
    """Outer shell shared by all templates — header, content slot, footer."""
    year = datetime.utcnow().year
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cortexia Medical</title>
</head>
<body style="margin:0;padding:0;background:{_BG};font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:{_TEXT};">
<div style="display:none;max-height:0;overflow:hidden;mso-hide:all;">{preheader}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{_BG};padding:32px 12px;">
  <tr><td align="center">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#FFFFFF;border:1px solid {_BORDER};border-radius:12px;overflow:hidden;">
      <tr><td style="background:{_BRAND_TEAL};padding:18px 24px;">
        <h1 style="margin:0;color:#FFFFFF;font-size:18px;font-weight:700;letter-spacing:0.3px;">Cortexia Medical</h1>
      </td></tr>
      <tr><td style="padding:28px 24px;">{content_html}</td></tr>
      <tr><td style="background:{_BG};padding:18px 24px;border-top:1px solid {_BORDER};font-size:11px;color:{_MUTED};line-height:1.5;">
        {footer_extra}
        © {year} Cortexia Medical. Este correo fue enviado automáticamente, por favor no respondas a esta dirección.
      </td></tr>
    </table>
  </td></tr>
</table>
</body>
</html>"""


# ============== TEMPLATES ==============

def welcome_clinic(*, admin_name: str, clinic_name: str, login_url: str, temp_password: str | None = None) -> dict:
    content = f"""
<h2 style="margin:0 0 12px;font-size:20px;font-weight:700;color:{_TEXT};">¡Bienvenido/a, {admin_name}!</h2>
<p style="margin:0 0 14px;font-size:14px;line-height:1.6;color:{_TEXT};">
  Tu clínica <strong>{clinic_name}</strong> ya está activa en Cortexia Medical. Estamos felices de tenerte a bordo.
</p>
<p style="margin:0 0 18px;font-size:14px;line-height:1.6;color:{_TEXT};">
  Desde tu panel puedes gestionar pacientes, citas, recetas, ventas POS y reportes financieros — todo en un solo lugar.
</p>
{"<div style='margin:18px 0;padding:12px;background:#F1F5F9;border-radius:8px;font-size:13px;color:" + _TEXT + ";'><strong>Contraseña temporal:</strong> <code style='font-family:monospace;background:#FFFFFF;padding:2px 6px;border-radius:4px;'>" + temp_password + "</code><br><span style='font-size:11px;color:" + _MUTED + ";'>Cámbiala en tu primer ingreso.</span></div>" if temp_password else ""}
<table role="presentation" cellpadding="0" cellspacing="0" style="margin:22px 0;">
  <tr><td style="background:{_BRAND_TEAL};border-radius:8px;">
    <a href="{login_url}" style="display:inline-block;padding:12px 26px;color:#FFFFFF;text-decoration:none;font-weight:600;font-size:14px;">Ingresar al panel →</a>
  </td></tr>
</table>
<p style="margin:18px 0 0;font-size:12px;color:{_MUTED};">Si tienes dudas, responde directamente a este correo o escríbenos a soporte@cortexiamedical.com.</p>
"""
    text = f"¡Bienvenido/a, {admin_name}!\n\nTu clínica {clinic_name} ya está activa en Cortexia Medical.\nIngresa: {login_url}\n"
    if temp_password:
        text += f"Contraseña temporal: {temp_password}\n"
    return {
        "subject": f"Bienvenido/a a Cortexia Medical, {clinic_name}",
        "html": _wrapper(preheader=f"Tu clínica {clinic_name} ya está activa.", content_html=content),
        "text": text,
    }


def password_reset(*, user_name: str, new_password: str, login_url: str, set_by: str) -> dict:
    content = f"""
<h2 style="margin:0 0 12px;font-size:20px;font-weight:700;color:{_TEXT};">Tu contraseña fue actualizada</h2>
<p style="margin:0 0 14px;font-size:14px;line-height:1.6;color:{_TEXT};">
  Hola {user_name}, el administrador <strong>{set_by}</strong> acaba de definir una nueva contraseña para tu cuenta en Cortexia Medical.
</p>
<div style="margin:18px 0;padding:14px;background:#FEF3C7;border:1px solid #FCD34D;border-radius:8px;">
  <p style="margin:0 0 6px;font-size:12px;color:#92400E;font-weight:600;">Tu nueva contraseña temporal:</p>
  <code style="font-family:monospace;font-size:16px;background:#FFFFFF;padding:6px 10px;border-radius:4px;color:#7C2D12;">{new_password}</code>
</div>
<p style="margin:0 0 14px;font-size:13px;line-height:1.6;color:{_MUTED};">
  Por seguridad, te recomendamos cambiarla por una propia tan pronto inicies sesión.
</p>
<table role="presentation" cellpadding="0" cellspacing="0" style="margin:18px 0;">
  <tr><td style="background:{_BRAND_TEAL};border-radius:8px;">
    <a href="{login_url}" style="display:inline-block;padding:12px 26px;color:#FFFFFF;text-decoration:none;font-weight:600;font-size:14px;">Iniciar sesión →</a>
  </td></tr>
</table>
<p style="margin:18px 0 0;font-size:11px;color:{_MUTED};">Si no esperabas este cambio, contacta a tu administrador o a soporte@cortexiamedical.com inmediatamente.</p>
"""
    text = f"Hola {user_name},\n\nEl administrador {set_by} actualizó tu contraseña.\nNueva contraseña: {new_password}\nIngresa: {login_url}\n"
    return {
        "subject": "Tu contraseña fue actualizada — Cortexia Medical",
        "html": _wrapper(preheader="Nueva contraseña definida por tu administrador.", content_html=content),
        "text": text,
    }


def appointment_reminder(*, patient_name: str, clinic_name: str, doctor_name: str, when_str: str, branch: str | None = None, reason: str | None = None) -> dict:
    extra = ""
    if branch:
        extra += f'<tr><td style="padding:6px 0;font-size:13px;color:{_MUTED};">Sucursal</td><td style="padding:6px 0;font-size:13px;color:{_TEXT};font-weight:600;text-align:right;">{branch}</td></tr>'
    if reason:
        extra += f'<tr><td style="padding:6px 0;font-size:13px;color:{_MUTED};">Motivo</td><td style="padding:6px 0;font-size:13px;color:{_TEXT};font-weight:600;text-align:right;">{reason}</td></tr>'

    content = f"""
<h2 style="margin:0 0 8px;font-size:20px;font-weight:700;color:{_TEXT};">Recordatorio de cita</h2>
<p style="margin:0 0 18px;font-size:14px;line-height:1.6;color:{_TEXT};">Hola {patient_name}, te recordamos tu próxima cita en <strong>{clinic_name}</strong>.</p>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:18px 0;padding:14px;background:#F1F5F9;border-radius:8px;">
  <tr><td style="padding:6px 0;font-size:13px;color:{_MUTED};">Fecha y hora</td><td style="padding:6px 0;font-size:13px;color:{_TEXT};font-weight:600;text-align:right;">{when_str}</td></tr>
  <tr><td style="padding:6px 0;font-size:13px;color:{_MUTED};">Doctor/a</td><td style="padding:6px 0;font-size:13px;color:{_TEXT};font-weight:600;text-align:right;">{doctor_name}</td></tr>
  {extra}
</table>
<p style="margin:18px 0 0;font-size:12px;color:{_MUTED};line-height:1.5;">Si necesitas reprogramar o cancelar, contacta directamente con la clínica. Por favor llega 10 minutos antes de tu cita.</p>
"""
    text = f"Hola {patient_name},\n\nRecordatorio de cita en {clinic_name}:\nFecha: {when_str}\nDoctor: {doctor_name}\n"
    return {
        "subject": f"Recordatorio: cita el {when_str.split(' ')[0]} en {clinic_name}",
        "html": _wrapper(preheader=f"Tu cita es el {when_str}.", content_html=content),
        "text": text,
    }
