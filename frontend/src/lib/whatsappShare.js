import axios from 'axios';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Prepare and open a WhatsApp Web share for a clinic document.
 * @param {'prescription'|'lab_order'|'sale'} docType
 * @param {string} docId
 * @param {object} headers - auth headers from useAuth().getAuthHeaders()
 */
export async function shareViaWhatsApp(docType, docId, headers) {
  const t = toast.loading('Preparando envío por WhatsApp…');
  try {
    const res = await axios.post(
      `${API}/clinic/whatsapp/share`,
      { doc_type: docType, doc_id: docId },
      { headers }
    );
    const data = res.data || {};
    toast.dismiss(t);
    if (!data.has_phone) {
      toast.info('El paciente no tiene teléfono registrado. Elige el contacto en WhatsApp.');
    } else {
      toast.success('Abriendo WhatsApp…');
    }
    if (data.wa_url) {
      window.open(data.wa_url, '_blank', 'noopener,noreferrer');
    }
    return data;
  } catch (err) {
    toast.dismiss(t);
    toast.error(err.response?.data?.detail || 'No se pudo preparar el envío por WhatsApp');
    return null;
  }
}
