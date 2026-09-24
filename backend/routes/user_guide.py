"""Downloadable, comprehensive user guide (PDF) for the clinic CRM.

Generated on the fly with ReportLab. Two scopes:
  - scope="full": the complete manual (all modules).
  - scope="role" (default): only the sections the requesting member can use,
    based on their role's modules intersected with the clinic's active features.

Includes the clinic logo (if configured) on the cover, and — when available —
a screenshot per module (PNG files under assets/guide/).
"""
import io
import os
import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from core import (
    sdb, require_clinic_member, fetch_clinic_logo_image,
    get_role_modules, get_clinic_features, MODULE_CATALOG,
    SYSTEM_ROLE_LABELS,
)

logger = logging.getLogger(__name__)
router = APIRouter()

TEAL = "#0d9488"
SLATE = "#334155"

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "guide")

# Each section: dict(title, intro, bullets, module, image).
#   module: None = always included; otherwise the module key that must be
#           available to the member for the section to appear in a role guide.
#   image:  optional PNG filename under ASSETS_DIR embedded as a screenshot.
GUIDE_SECTIONS = [
    {
        "title": "Acceso al sistema", "module": None, "image": None,
        "intro": "Cómo iniciar sesión y entender tu rol dentro de la clínica.",
        "bullets": [
            "Ingresa con tu correo y contraseña en la pantalla de inicio de sesión.",
            "Si es tu primer acceso, el sistema puede pedirte cambiar la contraseña por seguridad.",
            "Tu rol (Administrador, Doctor, Asistente, Recepcionista o un rol personalizado) determina qué áreas puedes ver y usar.",
            "Para cerrar sesión usa el menú de tu usuario en la barra lateral.",
        ],
    },
    {
        "title": "Inicio (Panel principal)", "module": None, "image": "dashboard.png",
        "intro": "El Inicio muestra un resumen del día y accesos rápidos según tu rol.",
        "bullets": [
            "Verás indicadores clave: citas del día, alertas y actividad reciente.",
            "Inicio rápido (solo Administradores): un panel guiado que te ayuda a poner en orden tu clínica paso a paso. Marca cada paso como hecho y sigue el avance.",
            "Cuando completes todos los pasos, puedes retirar el panel; podrás volver a mostrarlo desde Configuración › Datos.",
        ],
    },
    {
        "title": "Pacientes", "module": "patients", "image": "patients.png",
        "intro": "Registro y administración del expediente de tus pacientes.",
        "bullets": [
            "Crea un paciente con sus datos personales, contacto y antecedentes.",
            "Busca pacientes por nombre, teléfono o identificación.",
            "Abre el perfil del paciente para ver su historial de consultas, recetas, laboratorio y citas.",
            "Desde el perfil puedes iniciar una nueva consulta médica.",
        ],
    },
    {
        "title": "Consulta médica y expediente", "module": "patients", "image": None,
        "intro": "El formulario de consulta reúne todo lo necesario para atender al paciente.",
        "bullets": [
            "Registra el motivo de consulta, signos vitales, exploración y evolución.",
            "Agrega diagnósticos usando el buscador de códigos CIE-10.",
            "Dentro de la misma consulta puedes crear la Receta de medicamentos y la Orden de estudios/laboratorio, imprimirlas (PDF) y enviarlas por WhatsApp.",
            "El diagnóstico principal se copia automáticamente a la receta y a la orden de laboratorio (puedes editarlo).",
            "Guarda como borrador para continuar después, o finaliza la consulta cuando termines.",
        ],
    },
    {
        "title": "Recetas médicas", "module": "prescriptions", "image": "prescriptions.png",
        "intro": "Emisión de recetas profesionales con datos de la clínica y del médico.",
        "bullets": [
            "Agrega uno o varios medicamentos con dosis, frecuencia, vía y duración.",
            "Al emitir la receta se genera un PDF con el encabezado y logo de la clínica.",
            "Puedes imprimir la receta o enviarla directamente al paciente por WhatsApp.",
            "El módulo de Recetas guarda el historial de todas las recetas emitidas.",
        ],
    },
    {
        "title": "Laboratorio (órdenes de estudios)", "module": "lab_orders", "image": "lab_orders.png",
        "intro": "Solicitud de estudios y análisis clínicos.",
        "bullets": [
            "Selecciona los estudios por categoría e indica el diagnóstico presuntivo y la prioridad.",
            "Al crear la orden se genera un PDF listo para imprimir o enviar por WhatsApp.",
            "Consulta el estado de las órdenes desde el módulo de Laboratorio.",
        ],
    },
    {
        "title": "Agenda", "module": "agenda", "image": "agenda.png",
        "intro": "Programación de citas y control de disponibilidad.",
        "bullets": [
            "Crea, reprograma o cancela citas por médico y sucursal.",
            "Usa los Bloqueos de agenda para marcar horarios no disponibles por médico o sucursal (vacaciones, ausencias, mantenimiento). El sistema evita solapamientos.",
            "Si activaste Google Calendar, las citas pueden sincronizarse hacia tu calendario.",
        ],
    },
    {
        "title": "Inventario", "module": "inventory", "image": "inventory.png",
        "intro": "Control de productos, insumos y existencias.",
        "bullets": [
            "Registra productos con su presentación, costo y precio.",
            "Ajusta y controla las existencias disponibles.",
            "El inventario se enlaza con el módulo de Ventas/POS.",
        ],
    },
    {
        "title": "Ventas / Punto de venta", "module": "sales", "image": "sales.png",
        "intro": "Cobro de servicios y productos en caja.",
        "bullets": [
            "Abre caja al iniciar el turno y ciérrala al finalizar.",
            "Registra ventas de productos y servicios; el sistema calcula subtotales, impuestos y total.",
            "Puedes combinar varios métodos de pago en una misma venta: Efectivo, Tarjeta crédito/débito, Transferencia, Cheque, Crédito, Seguro médico u Otro.",
            "Pago con Seguro: al elegir «Seguro» debes escribir el nombre del seguro médico (con autocompletado desde los seguros que ya has usado antes). Puedes indicar solo la porción que cubre el seguro y dejar el resto como saldo pendiente.",
            "Pagos parciales: si el paciente paga solo una parte (por ejemplo, el seguro cubre Q400 de una consulta de Q600), el sistema crea automáticamente una Cuenta por cobrar con el saldo restante, el nombre del seguro y su monto aplicado para futuras conciliaciones.",
            "Las ventas alimentan los reportes financieros y las cuentas por cobrar.",
        ],
    },
    {
        "title": "Cuentas por cobrar", "module": "accounts_receivable", "image": "accounts.png",
        "intro": "Seguimiento de saldos pendientes de pacientes.",
        "bullets": [
            "Consulta los saldos por paciente y su antigüedad.",
            "Registra pagos parciales o totales.",
            "Filtra cuentas por Seguro médico para conciliar rápidamente lo que cada aseguradora te adeuda.",
            "Filtra por rango de fechas de creación para cerrar cortes contables mensuales o quincenales.",
            "Cada cuenta por cobrar guarda el seguro asociado y el monto de la porción cubierta, lo que facilita el reporte de comisiones y cobros a aseguradoras.",
        ],
    },
    {
        "title": "Gastos", "module": "expenses", "image": "expenses.png",
        "intro": "Control de egresos de la clínica.",
        "bullets": [
            "Registra gastos por categoría con su comprobante.",
            "Los gastos se reflejan en los reportes financieros.",
        ],
    },
    {
        "title": "Comisiones", "module": "commissions", "image": "commissions.png",
        "intro": "Reglas de comisión por médico o servicio.",
        "bullets": [
            "Define porcentajes o montos de comisión por médico.",
            "El sistema calcula las comisiones a partir de las ventas y servicios prestados.",
        ],
    },
    {
        "title": "Reportes financieros", "module": "reports", "image": "reports.png",
        "intro": "Visión del desempeño económico de la clínica.",
        "bullets": [
            "Consulta ingresos, gastos y utilidad por periodo.",
            "Filtra por sucursal y rango de fechas.",
        ],
    },
    {
        "title": "Configuración", "module": None, "image": "settings.png",
        "intro": "Ajustes generales de la clínica (según tus permisos).",
        "bullets": [
            "Clínica: datos generales, logo y horario de atención. El logo aparece en recetas, órdenes y en esta guía.",
            "Equipo: invita y administra a médicos y personal.",
            "Roles y permisos: crea roles personalizados y define a qué módulos accede cada uno.",
            "Plan: consulta tu plan y las funciones activas.",
            "Integraciones: conecta Google Calendar, WhatsApp y correo (Resend).",
            "Sucursales: administra tus sedes si tienes multi-sucursal.",
            "Datos: exporta toda tu base a Excel (con filtros de fecha y hojas) o a un respaldo ZIP; aquí también puedes volver a mostrar el Inicio rápido.",
            "Guía: descarga este manual (completo o adaptado a tu rol).",
            "Bitácora: registro de auditoría de acciones sensibles (cambios de roles, exportaciones, etc.).",
        ],
    },
    {
        "title": "Recomendaciones y soporte", "module": None, "image": None,
        "intro": "Buenas prácticas para aprovechar el sistema.",
        "bullets": [
            "Mantén actualizados los datos de la clínica y el logo para que tus documentos se vean profesionales.",
            "Asigna a cada miembro el rol con los permisos mínimos necesarios.",
            "Realiza respaldos periódicos desde Configuración › Datos.",
            "Ante cualquier duda, contacta al administrador de tu clínica.",
        ],
    },
]


def _available_modules(clinic_id: str, role: str) -> set:
    """Modules the member can actually use = role modules ∩ active clinic features."""
    role_mods = get_role_modules(clinic_id, role)
    try:
        active = get_clinic_features(clinic_id)
    except Exception:
        active = set()
    feat_by_mod = {m["key"]: m["feature"] for m in MODULE_CATALOG}
    return {k for k in role_mods if feat_by_mod.get(k) in active}


def _role_label(clinic_id: str, role: str) -> str:
    if role in SYSTEM_ROLE_LABELS:
        return SYSTEM_ROLE_LABELS[role]
    try:
        row = sdb.table("clinic_roles").select("name").eq("clinic_id", clinic_id).eq("key", role).maybe_single().execute()
        data = getattr(row, "data", None)
        if data and data.get("name"):
            return data["name"]
    except Exception:
        pass
    return "Mi rol"


def _build_guide_pdf(clinic: dict, sections: list, subtitle: str) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, PageBreak, HRFlowable,
        ListFlowable, ListItem, Image as RLImage,
    )

    clinic_name = (clinic or {}).get("name") or "Clínica"
    teal = colors.HexColor(TEAL)
    slate = colors.HexColor(SLATE)

    styles = getSampleStyleSheet()
    st_title = ParagraphStyle("gTitle", parent=styles["Title"], fontSize=26, textColor=teal, alignment=TA_CENTER, spaceAfter=6)
    st_sub = ParagraphStyle("gSub", parent=styles["Normal"], fontSize=13, textColor=slate, alignment=TA_CENTER, spaceAfter=2)
    st_meta = ParagraphStyle("gMeta", parent=styles["Normal"], fontSize=9, textColor=colors.grey, alignment=TA_CENTER)
    st_h2 = ParagraphStyle("gH2", parent=styles["Heading2"], fontSize=14, textColor=teal, spaceBefore=10, spaceAfter=4, keepWithNext=True)
    st_intro = ParagraphStyle("gIntro", parent=styles["Normal"], fontSize=10.5, textColor=slate, spaceAfter=4, leading=15)
    st_bullet = ParagraphStyle("gBullet", parent=styles["Normal"], fontSize=10, textColor=colors.HexColor("#1e293b"), leading=14)
    st_toc = ParagraphStyle("gToc", parent=styles["Normal"], fontSize=10.5, textColor=slate, leading=18)
    st_cap = ParagraphStyle("gCap", parent=styles["Normal"], fontSize=8, textColor=colors.grey, alignment=TA_CENTER, spaceBefore=2, spaceAfter=6)

    avail_w = A4[0] - 36 * mm  # page width minus L/R margins
    max_img_h = 105 * mm

    def image_flowable(filename):
        if not filename:
            return None
        path = os.path.join(ASSETS_DIR, filename)
        if not os.path.exists(path):
            return None
        try:
            img = RLImage(path)
            scale = min(avail_w / img.imageWidth, max_img_h / img.imageHeight, 1.0)
            img.drawWidth = img.imageWidth * scale
            img.drawHeight = img.imageHeight * scale
            img.hAlign = "CENTER"
            return img
        except Exception as e:
            logger.warning(f"guide image {filename} failed: {e}")
            return None

    story = []

    # ---- Cover ----
    story.append(Spacer(1, 38 * mm))
    logo = fetch_clinic_logo_image((clinic or {}).get("logo_url"), max_h_mm=26)
    if logo is not None:
        logo.hAlign = "CENTER"
        story.append(logo)
        story.append(Spacer(1, 10 * mm))
    story.append(Paragraph(clinic_name, st_title))
    story.append(Paragraph("Guía de Usuario del Sistema", st_sub))
    if subtitle:
        story.append(Paragraph(subtitle, st_sub))
    story.append(Spacer(1, 4 * mm))
    story.append(HRFlowable(width="40%", thickness=1, color=teal, hAlign="CENTER"))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(f"Generado el {datetime.now(timezone.utc).strftime('%d/%m/%Y')}", st_meta))
    story.append(PageBreak())

    # ---- Table of contents ----
    story.append(Paragraph("Contenido", st_h2))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0")))
    story.append(Spacer(1, 3 * mm))
    for i, s in enumerate(sections, start=1):
        story.append(Paragraph(f"{i}. {s['title']}", st_toc))
    story.append(PageBreak())

    # ---- Sections ----
    for i, s in enumerate(sections, start=1):
        story.append(Paragraph(f"{i}. {s['title']}", st_h2))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0")))
        story.append(Spacer(1, 2 * mm))
        if s.get("intro"):
            story.append(Paragraph(s["intro"], st_intro))
        img = image_flowable(s.get("image"))
        if img is not None:
            story.append(Spacer(1, 2 * mm))
            story.append(img)
            story.append(Paragraph(f"Vista de {s['title']}", st_cap))
        items = [ListItem(Paragraph(b, st_bullet), leftIndent=6) for b in s["bullets"]]
        story.append(ListFlowable(items, bulletType="bullet", start="•", leftIndent=14, bulletColor=teal, spaceBefore=2, spaceAfter=8))

    def _on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(18 * mm, 12 * mm, clinic_name)
        canvas.drawRightString(A4[0] - 18 * mm, 12 * mm, f"Página {doc.page}")
        canvas.setStrokeColor(colors.HexColor("#e2e8f0"))
        canvas.setLineWidth(0.5)
        canvas.line(18 * mm, 15 * mm, A4[0] - 18 * mm, 15 * mm)
        canvas.restoreState()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm, bottomMargin=20 * mm,
        title=f"Guía de Usuario - {clinic_name}",
    )
    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    buf.seek(0)
    return buf.getvalue()


@router.get("/clinic/user-guide/pdf")
async def download_user_guide(
    scope: str = Query("role", pattern="^(role|full)$"),
    ctx=Depends(require_clinic_member),
):
    clinic_id = ctx["member"]["clinic_id"]
    role = ctx["member"].get("role") or ""

    try:
        clinic = (sdb.table("clinics").select("name,logo_url").eq("id", clinic_id).single().execute().data) or {}
    except Exception:
        clinic = {}

    if scope == "full" or role == "clinic_admin":
        sections = GUIDE_SECTIONS
        subtitle = "Guía completa"
        scope = "full"
    else:
        available = _available_modules(clinic_id, role)
        sections = [s for s in GUIDE_SECTIONS if s["module"] is None or s["module"] in available]
        subtitle = f"Guía para: {_role_label(clinic_id, role)}"

    loop = asyncio.get_event_loop()
    try:
        data = await loop.run_in_executor(None, _build_guide_pdf, clinic, sections, subtitle)
    except Exception as e:
        logger.error(f"user guide pdf failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al generar la guía")

    safe = (clinic.get("name") or "clinica").lower().replace(" ", "_")[:40]
    tag = "completa" if scope == "full" else "rol"
    fname = f"guia_usuario_{tag}_{safe}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.pdf"
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
