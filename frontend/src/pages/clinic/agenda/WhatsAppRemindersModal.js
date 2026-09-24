import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../../components/ui/dialog';
import { Button } from '../../../components/ui/button';
import { Badge } from '../../../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../../components/ui/select';
import { toast } from 'sonner';
import { MessageCircle, Phone, Clock, User, CheckCircle2, RotateCcw, AlertCircle } from 'lucide-react';
import { API } from './constants';

/**
 * Lists upcoming appointments (default: next 24h) with a click-to-send
 * WhatsApp Web button per row. Clicking opens wa.me in a new tab AND marks
 * the appointment as reminded so it stops showing up.
 */
export default function WhatsAppRemindersModal({ open, onClose, headers }) {
  const [window_hours, setWindow] = useState(24);
  const [includeSent, setIncludeSent] = useState(false);
  const [items, setItems] = useState([]);
  const [skippedNoPhone, setSkippedNoPhone] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ window_hours: String(window_hours) });
      if (includeSent) params.set('include_sent', 'true');
      const r = await axios.get(`${API}/clinic/appointments/whatsapp-reminders?${params}`, { headers });
      setItems(r.data.appointments || []);
      setSkippedNoPhone(r.data.skipped_no_phone || 0);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Error al cargar recordatorios');
    } finally { setLoading(false); }
  }, [window_hours, includeSent, headers]);

  useEffect(() => { if (open) load(); }, [open, load]);

  const sendReminder = async (item) => {
    // Open WhatsApp Web in a new tab FIRST — browsers block window.open outside a user gesture
    // if it happens after an async await. So we synchronously open, then await the API call.
    const opened = window.open(item.wa_url, '_blank', 'noopener');
    if (!opened) {
      toast.error('Tu navegador bloqueó la ventana emergente. Habilita popups para este sitio.');
      return;
    }
    setBusyId(item.id);
    try {
      await axios.post(`${API}/clinic/appointments/${item.id}/whatsapp-reminder-sent`, {}, { headers });
      toast.success(`Recordatorio enviado a ${item.patient_name}. Haz clic en Enviar en WhatsApp.`);
      // Optimistic remove from the pending list
      setItems(prev => prev.filter(x => x.id !== item.id));
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Error al marcar recordatorio');
    } finally { setBusyId(null); }
  };

  const resetReminder = async (item) => {
    setBusyId(item.id);
    try {
      await axios.post(`${API}/clinic/appointments/${item.id}/whatsapp-reminder-reset`, {}, { headers });
      toast.success('Recordatorio reactivado');
      load();
    } catch (e) {
      toast.error('Error al reactivar');
    } finally { setBusyId(null); }
  };

  const sendAll = async () => {
    const pending = items.filter(i => !i.already_sent);
    if (pending.length === 0) return;
    toast.info(`Abriendo ${pending.length} pestañas de WhatsApp — envía cada mensaje manualmente.`);
    for (const item of pending) {
      window.open(item.wa_url, '_blank', 'noopener');
      // Mark as sent (fire and forget)
      axios.post(`${API}/clinic/appointments/${item.id}/whatsapp-reminder-sent`, {}, { headers }).catch(() => {});
      // Small pause so browsers don't collapse the tabs
      await new Promise(r => setTimeout(r, 250));
    }
    setItems(prev => prev.map(i => ({ ...i, already_sent: true })));
  };

  const pendingCount = items.filter(i => !i.already_sent).length;

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto" data-testid="wa-reminders-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-emerald-700">
            <MessageCircle className="w-5 h-5" />
            Recordatorios de cita — WhatsApp Web
          </DialogTitle>
        </DialogHeader>

        <div className="bg-emerald-50 border border-emerald-200 rounded p-3 text-xs text-emerald-900 mb-3">
          Al hacer clic en <strong>Enviar por WhatsApp</strong> se abrirá WhatsApp Web con el mensaje ya redactado. Solo debes presionar el botón verde de enviar en WhatsApp. La cita quedará marcada como recordada automáticamente.
        </div>

        <div className="flex flex-wrap gap-3 mb-4 items-center">
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-slate-400" />
            <span className="text-xs text-slate-600">Próximas</span>
            <Select value={String(window_hours)} onValueChange={v => setWindow(parseInt(v))}>
              <SelectTrigger className="w-32 h-8 text-xs" data-testid="wa-window-select"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="24">24 horas</SelectItem>
                <SelectItem value="48">48 horas</SelectItem>
                <SelectItem value="72">72 horas</SelectItem>
                <SelectItem value="168">7 días</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <label className="flex items-center gap-1.5 text-xs text-slate-700 cursor-pointer">
            <input type="checkbox" className="rounded" checked={includeSent} onChange={e => setIncludeSent(e.target.checked)} data-testid="wa-include-sent" />
            Ver ya enviados
          </label>
          <div className="flex-1" />
          {pendingCount > 1 && (
            <Button
              size="sm"
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
              onClick={sendAll}
              data-testid="wa-send-all-btn"
            >
              <MessageCircle className="w-4 h-4 mr-1" />
              Enviar todos ({pendingCount})
            </Button>
          )}
        </div>

        {skippedNoPhone > 0 && (
          <div className="flex items-start gap-2 bg-amber-50 border border-amber-200 rounded p-2 text-xs text-amber-800 mb-3">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>Hay <strong>{skippedNoPhone}</strong> {skippedNoPhone === 1 ? 'cita' : 'citas'} sin número de teléfono del paciente. Actualiza sus datos para poder enviarles recordatorio.</span>
          </div>
        )}

        {loading ? (
          <div className="flex justify-center py-12"><div className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" /></div>
        ) : items.length === 0 ? (
          <div className="text-center py-12 text-slate-400">
            <CheckCircle2 className="w-12 h-12 mx-auto mb-2 text-emerald-300" strokeWidth={1.5} />
            <p className="text-sm font-medium text-slate-600">No hay citas pendientes de recordatorio</p>
            <p className="text-xs mt-1">
              {includeSent
                ? 'No hay citas en la próxima ventana seleccionada.'
                : 'Todas las citas próximas ya han sido recordadas o no aplican.'}
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {items.map(item => (
              <div
                key={item.id}
                className={`border rounded-lg p-3 ${item.already_sent ? 'bg-slate-50 border-slate-200 opacity-70' : 'bg-white border-slate-200 hover:border-emerald-300 hover:shadow-sm'} transition-all`}
                data-testid={`wa-reminder-row-${item.id}`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <User className="w-4 h-4 text-slate-400 shrink-0" />
                      <p className="font-semibold text-sm text-slate-900 truncate">{item.patient_name}</p>
                      {item.already_sent && <Badge variant="outline" className="text-[10px] bg-emerald-50 text-emerald-700 border-emerald-200"><CheckCircle2 className="w-3 h-3 mr-0.5" />Enviado</Badge>}
                    </div>
                    <div className="flex flex-wrap gap-3 text-xs text-slate-600">
                      <span className="inline-flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {item.date_label} · {item.time_label}
                      </span>
                      <span className="inline-flex items-center gap-1">
                        <Phone className="w-3 h-3" />
                        {item.patient_phone || '—'}
                      </span>
                      {item.doctor_name && <span className="text-slate-500">Dr. {item.doctor_name}</span>}
                    </div>
                    {item.reason && (
                      <p className="text-xs text-slate-500 mt-1 italic truncate">{item.reason}</p>
                    )}
                  </div>
                  <div className="shrink-0 flex gap-2">
                    {item.already_sent ? (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => resetReminder(item)}
                        disabled={busyId === item.id}
                        data-testid={`wa-reset-${item.id}`}
                      >
                        <RotateCcw className="w-3.5 h-3.5 mr-1" />
                        Reenviar
                      </Button>
                    ) : (
                      <Button
                        size="sm"
                        className="bg-emerald-600 hover:bg-emerald-700 text-white"
                        onClick={() => sendReminder(item)}
                        disabled={busyId === item.id}
                        data-testid={`wa-send-${item.id}`}
                      >
                        <MessageCircle className="w-3.5 h-3.5 mr-1" />
                        {busyId === item.id ? '...' : 'Enviar por WhatsApp'}
                      </Button>
                    )}
                  </div>
                </div>
                <details className="mt-2">
                  <summary className="text-[11px] text-slate-400 cursor-pointer hover:text-slate-600">Vista previa del mensaje</summary>
                  <pre className="mt-1 p-2 bg-slate-50 border border-slate-100 rounded text-[11px] whitespace-pre-wrap text-slate-700">{item.message}</pre>
                </details>
              </div>
            ))}
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cerrar</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
