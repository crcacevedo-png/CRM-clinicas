"""Downloadable, comprehensive user guide (PDF) for the clinic CRM.

Generated on the fly with ReportLab. Includes the clinic logo (if available)
on the cover. Available to any clinic member — it is documentation.
"""
import io
import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from core import sdb, require_clinic_member, fetch_clinic_logo_image

logger = logging.getLogger(__name__)
router = APIRouter()

TEAL = "#0d9488"
SLATE = "#334155"

# (title, intro, [bullets]) — the full guide content, in Spanish.
GUIDE_SECTIONS = [
    (
        "Acceso al sistema",
        "Cómo iniciar sesión y entender tu rol dentro de la clínica.",
        [
            "Ingresa con tu correo y contraseña en la pantalla de inicio de sesión.",
            "Si es tu primer acceso, el sistema puede pedirte cambiar la contraseña por seguridad.",
            "Tu rol (Administrador, Doctor, Asistente, Recepcionista o un rol personalizado) determina qué áreas puedes ver y usar.",
            "Para cerrar sesión usa el menú de tu usuario en la barra lateral.",
        ],
    ),
    (
        "Inicio (Panel principal)",
        "El Inicio muestra un resumen del día y accesos rápidos según tu rol.",
        [
            "Verás indicadores clave: citas del día, alertas y actividad reciente.",
            "Inicio rápido (solo Administradores): un panel guiado que te ayuda a poner en orden tu clínica paso a paso. Marca cada paso como hecho y sigue el avance.",
            "Cuando completes todos los pasos, puedes retirar el panel; podrás volver a mostrarlo desde Configuración › Datos.",
        ],
    ),
    (
        "Pacientes",
        "Registro y administración del expediente de tus pacientes.",
        [
            "Crea un paciente con sus datos personales, contacto y antecedentes.",
            "Busca pacientes por nombre, teléfono o identificación.",
            "Abre el perfil del paciente para ver su historial de consultas, recetas, laboratorio y citas.",
            "Desde el perfil puedes iniciar una nueva consulta médica.",
        ],
    ),
    (
        "Consulta médica y expediente",
        "El formulario de consulta reúne todo lo necesario para atender al paciente.",
        [
            "Registra el motivo de consulta, signos vitales, exploración y evolución.",
            "Agrega diagnósticos usando el buscador de códigos CIE-10.",
            "Dentro de la misma consulta puedes crear la Receta de medicamentos y la Orden de estudios/laboratorio, imprimirlas (PDF) y enviarlas por WhatsApp.",
            "El diagnóstico principal se copia automáticamente a la receta y a la orden de laboratorio (puedes editarlo).",
            "Guarda como borrador para continuar después, o finaliza la consulta cuando termines.",
        ],
    ),
    (
        "Recetas médicas",
        "Emisión de recetas profesionales con datos de la clínica y del médico.",
        [
            "Agrega uno o varios medicamentos con dosis, frecuencia, vía y duración.",
            "Al emitir la receta se genera un PDF con el encabezado y logo de la clínica.",
            "Puedes imprimir la receta o enviarla directamente al paciente por WhatsApp.",
            "El módulo de Recetas guarda el historial de todas las recetas emitidas.",
        ],
    ),
    (
        "Laboratorio (órdenes de estudios)",
        "Solicitud de estudios y análisis clínicos.",
        [
            "Selecciona los estudios por categoría e indica el diagnóstico presuntivo y la prioridad.",
            "Al crear la orden se genera un PDF listo para imprimir o enviar por WhatsApp.",
            "Consulta el estado de las órdenes desde el módulo de Laboratorio.",
        ],
    ),
    (
        "Agenda",
        "Programación de citas y control de disponibilidad.",
        [
            "Crea, reprograma o cancela citas por médico y sucursal.",
            "Usa los Bloqueos de agenda para marcar horarios no disponibles por médico o sucursal (vacaciones, ausencias, mantenimiento). El sistema evita solapamientos.",
            "Si activaste Google Calendar, las citas pueden sincronizarse hacia tu calendario.",
        ],
    ),
    (
        "Inventario (según tu plan)",
        "Control de productos, insumos y existencias.",
        [
            "Registra productos con su presentación, costo y precio.",
            "Ajusta y controla las existencias disponibles.",
            "El inventario se enlaza con el módulo de Ventas/POS.",
        ],
    ),
    (
        "Ventas / Punto de venta (según tu plan)",
        "Cobro de servicios y productos en caja.",
        [
            "Abre caja al iniciar el turno y ciérrala al finalizar.",
            "Registra ventas de productos y servicios; el sistema calcula subtotales, impuestos y total.",
            "Las ventas alimentan los reportes financieros y las cuentas por cobrar.",
        ],
    ),
    (
        "Cuentas por cobrar (según tu plan)",
        "Seguimiento de saldos pendientes de pacientes.",
        [
            "Consulta los saldos por paciente y su antigüedad.",
            "Registra pagos parciales o totales.",
        ],
    ),
    (
        "Gastos (según tu plan)",
        "Control de egresos de la clínica.",
        [
            "Registra gastos por categoría con su comprobante.",
            "Los gastos se reflejan en los reportes financieros.",
        ],
    ),
    (
        "Comisiones (según tu plan)",
        "Reglas de comisión por médico o servicio.",
        [
            "Define porcentajes o montos de comisión por médico.",
            "El sistema calcula las comisiones a partir de las ventas y servicios prestados.",
        ],
    ),
    (
        "Reportes financieros (según tu plan)",
        "Visión del desempeño económico de la clínica.",
        [
            "Consulta ingresos, gastos y utilidad por periodo.",
            "Filtra por sucursal y rango de fechas.",
        ],
    ),
    (
        "Configuración",
        "Ajustes generales de la clínica (según tus permisos).",
        [
            "Clínica: datos generales, logo y horario de atención. El logo aparece en recetas, órdenes y en esta guía.",
            "Equipo: invita y administra a médicos y personal.",
            "Roles y permisos: crea roles personalizados y define a qué módulos accede cada uno.",
            "Plan: consulta tu plan y las funciones activas.",
            "Integraciones: conecta Google Calendar, WhatsApp y correo (Resend).",
            "Sucursales: administra tus sedes si tienes multi-sucursal.",
            "Datos: exporta toda tu base a Excel (con filtros de fecha y hojas) o a un respaldo ZIP; aquí también puedes volver a mostrar el Inicio rápido.",
            "Bitácora: registro de auditoría de acciones sensibles (cambios de roles, exportaciones, etc.).",
        ],
    ),
    (
        "Recomendaciones y soporte",
        "Buenas prácticas para aprovechar el sistema.",
        [
            "Mantén actualizados los datos de la clínica y el logo para que tus documentos se vean profesionales.",
            "Asigna a cada miembro el rol con los permisos mínimos necesarios.",
            "Realiza respaldos periódicos desde Configuración › Datos.",
            "Ante cualquier duda, contacta al administrador de tu clínica.",
        ],
    ),
]


def _build_guide_pdf(clinic: dict) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, PageBreak, HRFlowable, ListFlowable, ListItem,
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

    story = []

    # ---- Cover ----
    story.append(Spacer(1, 40 * mm))
    logo = fetch_clinic_logo_image((clinic or {}).get("logo_url"), max_h_mm=26)
    if logo is not None:
        logo.hAlign = "CENTER"
        story.append(logo)
        story.append(Spacer(1, 10 * mm))
    story.append(Paragraph(clinic_name, st_title))
    story.append(Paragraph("Guía de Usuario del Sistema", st_sub))
    story.append(Spacer(1, 4 * mm))
    story.append(HRFlowable(width="40%", thickness=1, color=teal, hAlign="CENTER"))
    story.append(Spacer(1, 6 * mm))
    fecha = datetime.now(timezone.utc).strftime("%d/%m/%Y")
    story.append(Paragraph(f"Generado el {fecha}", st_meta))
    story.append(PageBreak())

    # ---- Table of contents ----
    story.append(Paragraph("Contenido", st_h2))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0")))
    story.append(Spacer(1, 3 * mm))
    for i, (title, _intro, _bullets) in enumerate(GUIDE_SECTIONS, start=1):
        story.append(Paragraph(f"{i}. {title}", st_toc))
    story.append(PageBreak())

    # ---- Sections ----
    for i, (title, intro, bullets) in enumerate(GUIDE_SECTIONS, start=1):
        story.append(Paragraph(f"{i}. {title}", st_h2))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0")))
        story.append(Spacer(1, 2 * mm))
        if intro:
            story.append(Paragraph(intro, st_intro))
        items = [ListItem(Paragraph(b, st_bullet), leftIndent=6) for b in bullets]
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
async def download_user_guide(ctx=Depends(require_clinic_member)):
    clinic_id = ctx["member"]["clinic_id"]
    try:
        clinic = (sdb.table("clinics").select("name,logo_url").eq("id", clinic_id).single().execute().data) or {}
    except Exception:
        clinic = {}

    loop = asyncio.get_event_loop()
    try:
        data = await loop.run_in_executor(None, _build_guide_pdf, clinic)
    except Exception as e:
        logger.error(f"user guide pdf failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error al generar la guía")

    safe = (clinic.get("name") or "clinica").lower().replace(" ", "_")[:40]
    fname = f"guia_usuario_{safe}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.pdf"
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
