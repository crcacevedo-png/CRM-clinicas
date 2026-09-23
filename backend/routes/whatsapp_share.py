"""WhatsApp Web sharing for prescriptions, lab orders and sale receipts.

Builds a wa.me deep-link (no WhatsApp Business API required) with a pre-filled
message + a 7-day signed link to the document PDF. The frontend opens the
returned wa_url in a new tab. Tenant-scoped: every document is validated to
belong to the caller's clinic before a link is produced.
"""
import re
from urllib.parse import quote
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

router = APIRouter()

from core import sdb, supabase_admin, require_clinic_member, now_iso, logger, validate_uuid

SHARE_TTL = 7 * 24 * 3600  # 7 days

# Country name (as stored in clinics.country) -> WhatsApp calling code.
_COUNTRY_CODES = {
    'guatemala': '502', 'gt': '502',
    'mexico': '52', 'méxico': '52', 'mx': '52',
    'el salvador': '503', 'sv': '503',
    'honduras': '504', 'hn': '504',
    'nicaragua': '505', 'ni': '505',
    'costa rica': '506', 'cr': '506',
    'panama': '507', 'panamá': '507', 'pa': '507',
    'republica dominicana': '1', 'república dominicana': '1', 'do': '1',
    'colombia': '57', 'co': '57',
    'peru': '51', 'perú': '51', 'pe': '51',
    'ecuador': '593', 'ec': '593',
    'chile': '56', 'cl': '56',
    'argentina': '54', 'ar': '54',
    'bolivia': '591', 'bo': '591',
    'venezuela': '58', 've': '58',
    'estados unidos': '1', 'usa': '1', 'us': '1', 'united states': '1',
    'españa': '34', 'espana': '34', 'spain': '34', 'es': '34',
}
_DEFAULT_CC = '502'

_DOC_LABELS = {
    'prescription': 'receta médica',
    'lab_order': 'orden de laboratorio',
    'sale': 'recibo de compra',
}


def _normalize_wa_phone(phone: Optional[str], country: Optional[str]) -> Optional[str]:
    """Return digits-only phone with a country calling code, or None."""
    if not phone:
        return None
    digits = re.sub(r'\D', '', phone)
    if digits.startswith('00'):
        digits = digits[2:]
    if not digits:
        return None
    cc = _COUNTRY_CODES.get((country or '').strip().lower(), _DEFAULT_CC)
    # Already includes the country code (longer than a typical 8-digit local number)
    if digits.startswith(cc) and len(digits) > 8:
        return digits
    if len(digits) <= 8:
        return cc + digits
    return digits


def _signed_pdf_url(path: str) -> Optional[str]:
    try:
        signed = supabase_admin.storage.from_('patient-files').create_signed_url(path, SHARE_TTL)
        return signed.get('signedURL') or signed.get('signedUrl') or ''
    except Exception:
        return None


class WhatsAppShareRequest(BaseModel):
    doc_type: str  # 'prescription' | 'lab_order' | 'sale'
    doc_id: str


@router.post("/clinic/whatsapp/share")
async def whatsapp_share(data: WhatsAppShareRequest, ctx=Depends(require_clinic_member)):
    """Produce a WhatsApp Web deep-link + 7-day PDF link for a clinic document."""
    clinic_id = ctx["member"]["clinic_id"]
    doc_type = data.doc_type
    doc_id = data.doc_id
    validate_uuid(doc_id, "doc_id")
    if doc_type not in _DOC_LABELS:
        raise HTTPException(status_code=400, detail="Tipo de documento inválido")

    clinic = sdb.table('clinics').select('name,country').eq('id', clinic_id).maybe_single().execute()
    clinic_data = getattr(clinic, 'data', None) or {}
    clinic_name = clinic_data.get('name') or 'la clínica'
    country = clinic_data.get('country')

    if doc_type == 'prescription':
        row = sdb.table('prescriptions').select('id,patient_id,status').eq('id', doc_id).eq('clinic_id', clinic_id).maybe_single().execute()
        rd = getattr(row, 'data', None)
        if not rd:
            raise HTTPException(status_code=404, detail="Receta no encontrada")
        if rd.get('status') != 'issued':
            raise HTTPException(status_code=400, detail="Debes emitir la receta antes de enviarla")
        patient_id = rd.get('patient_id')
        path = f"{clinic_id}/prescriptions/{doc_id}.pdf"
        table = 'prescriptions'
        from routes.prescriptions import generate_prescription_pdf as gen
    elif doc_type == 'lab_order':
        row = sdb.table('lab_orders').select('id,patient_id').eq('id', doc_id).eq('clinic_id', clinic_id).maybe_single().execute()
        rd = getattr(row, 'data', None)
        if not rd:
            raise HTTPException(status_code=404, detail="Orden no encontrada")
        patient_id = rd.get('patient_id')
        path = f"{clinic_id}/lab-orders/{doc_id}.pdf"
        table = 'lab_orders'
        from routes.lab_orders import generate_lab_order_pdf as gen
    else:  # sale
        row = sdb.table('sales').select('id,patient_id,customer_name').eq('id', doc_id).eq('clinic_id', clinic_id).maybe_single().execute()
        rd = getattr(row, 'data', None)
        if not rd:
            raise HTTPException(status_code=404, detail="Venta no encontrada")
        patient_id = rd.get('patient_id')
        path = f"{clinic_id}/sales/{doc_id}.pdf"
        table = 'sales'
        from routes.sales import generate_sale_pdf as gen

    # Resolve recipient name + phone (tenant-scoped)
    patient_first = ''
    phone_raw = None
    if patient_id:
        pat = sdb.table('patients').select('first_name,last_name,phone,phone_secondary').eq('id', patient_id).eq('clinic_id', clinic_id).maybe_single().execute()
        pd = getattr(pat, 'data', None) or {}
        patient_first = (pd.get('first_name') or '').strip()
        phone_raw = pd.get('phone') or pd.get('phone_secondary')
    elif doc_type == 'sale':
        patient_first = (rd.get('customer_name') or '').strip()

    # Ensure the PDF exists → 7-day signed URL (regenerate once if missing)
    pdf_url = _signed_pdf_url(path)
    if not pdf_url:
        try:
            await gen(doc_id, clinic_id)
        except Exception as e:
            logger.error(f"whatsapp_share PDF gen failed ({doc_type} {doc_id}): {e}")
        pdf_url = _signed_pdf_url(path)
    if not pdf_url:
        raise HTTPException(status_code=500, detail="No se pudo generar el PDF del documento")

    phone = _normalize_wa_phone(phone_raw, country)
    doc_label = _DOC_LABELS[doc_type]
    greeting = f"Hola {patient_first}," if patient_first else "Hola,"
    message = (
        f"{greeting}\n\n"
        f"Le compartimos su {doc_label} de {clinic_name}.\n\n"
        f"Puede ver o descargar el documento (PDF) aquí:\n{pdf_url}\n\n"
        f"Gracias por su preferencia."
    )
    wa_url = f"https://wa.me/{phone}?text={quote(message)}" if phone else f"https://wa.me/?text={quote(message)}"

    # Mark the document as shared via WhatsApp (best-effort)
    try:
        sdb.table(table).update({
            "sent_via": "whatsapp", "sent_at": now_iso(), "updated_at": now_iso(),
        }).eq('id', doc_id).eq('clinic_id', clinic_id).execute()
    except Exception as e:
        logger.warning(f"whatsapp_share mark-sent failed ({table} {doc_id}): {e}")

    return {
        "wa_url": wa_url,
        "pdf_url": pdf_url,
        "phone": phone,
        "has_phone": bool(phone),
        "message": message,
        "doc_type": doc_type,
    }
