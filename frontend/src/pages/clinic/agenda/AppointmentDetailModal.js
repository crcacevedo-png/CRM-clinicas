import { useState } from 'react';
import axios from 'axios';
import { Button } from '../../../components/ui/button';
import { Badge } from '../../../components/ui/badge';
import { Input } from '../../../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../../components/ui/dialog';
import { Label } from '../../../components/ui/label';
import { Textarea } from '../../../components/ui/textarea';
import { toast } from 'sonner';
import { Edit, Ban, Mail } from 'lucide-react';
import { API, STATUS_CONFIG, DOCTOR_COLORS } from './constants';

export default function AppointmentDetailModal({ appointment, config, doctorMap, headers, onClose, onUpdated }) {
  const [cancellationReason, setCancellationReason] = useState('');
  const [showEdit, setShowEdit] = useState(false);
  const [editForm, setEditForm] = useState({
    doctor_id: appointment.doctor_id,
    starts_at: appointment.starts_at ? new Date(appointment.starts_at).toISOString().slice(0, 16) : '',
    duration_minutes: appointment.duration_minutes,
    reason: appointment.reason || '',
    notes: appointment.notes || '',
  });
  const [saving, setSaving] = useState(false);
  const [sendingReminder, setSendingReminder] = useState(false);

  const sendReminder = async () => {
    setSendingReminder(true);
    try {
      const r = await axios.post(`${API}/clinic/appointments/${appointment.id}/send-reminder`, {}, { headers });
      toast.success(`Recordatorio enviado a ${r.data.sent_to}`);
      onUpdated();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al enviar recordatorio');
    } finally {
      setSendingReminder(false);
    }
  };

  const cfg = STATUS_CONFIG[appointment.status] || STATUS_CONFIG.scheduled;
  const drColor = doctorMap[appointment.doctor_id] || DOCTOR_COLORS[0];

  const changeStatus = async (newStatus) => {
    if (newStatus === 'cancelled' && !cancellationReason) {
      toast.error('Ingresa el motivo de cancelación');
      return;
    }
    setSaving(true);
    try {
      await axios.put(`${API}/clinic/appointments/${appointment.id}/status`, {
        status: newStatus,
        cancellation_reason: newStatus === 'cancelled' ? cancellationReason : undefined,
      }, { headers });
      toast.success('Estado actualizado');
      onUpdated();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error');
    } finally {
      setSaving(false);
    }
  };

  const saveEdit = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/clinic/appointments/${appointment.id}`, {
        doctor_id: editForm.doctor_id,
        starts_at: editForm.starts_at ? new Date(editForm.starts_at).toISOString() : undefined,
        duration_minutes: editForm.duration_minutes,
        reason: editForm.reason,
        notes: editForm.notes,
      }, { headers });
      toast.success('Cita actualizada');
      onUpdated();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al actualizar');
    } finally {
      setSaving(false);
    }
  };

  const time = new Date(appointment.starts_at).toLocaleTimeString('es-GT', { hour: '2-digit', minute: '2-digit', hour12: true });
  const date = new Date(appointment.starts_at).toLocaleDateString('es-GT', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });

  return (
    <Dialog open={true} onOpenChange={onClose}>
      <DialogContent className="max-w-md" data-testid="apt-detail-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-base pr-6">
            <div className="w-3 h-3 rounded-sm shrink-0" style={{ backgroundColor: drColor.accent }} />
            Detalle de cita
            <Badge variant="outline" className="text-xs">
              <div className={`w-2 h-2 rounded-full mr-1 ${cfg.dot}`} />{cfg.label}
            </Badge>
          </DialogTitle>
        </DialogHeader>

        {!showEdit ? (
          <div className="space-y-4 py-2">
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <p className="text-xs text-slate-500">Paciente</p>
                <p className="font-semibold text-slate-900">{appointment.patient_name}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Médico</p>
                <p className="font-semibold text-slate-900">{appointment.doctor_name}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Fecha</p>
                <p className="font-medium text-slate-700 capitalize">{date}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Hora</p>
                <p className="font-medium text-slate-700">{time} ({appointment.duration_minutes} min)</p>
              </div>
            </div>
            {appointment.reason && (
              <div>
                <p className="text-xs text-slate-500">Motivo</p>
                <p className="text-sm text-slate-800">{appointment.reason}</p>
              </div>
            )}
            {appointment.notes && (
              <div>
                <p className="text-xs text-slate-500">Notas</p>
                <p className="text-sm text-slate-700">{appointment.notes}</p>
              </div>
            )}

            {appointment.status !== 'cancelled' && appointment.status !== 'completed' && (
              <div className="border-t border-slate-100 pt-3">
                <p className="text-xs font-medium text-slate-600 mb-2">Cambiar estado:</p>
                <div className="flex flex-wrap gap-2">
                  {appointment.status === 'scheduled' && (
                    <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700 text-xs h-7" onClick={() => changeStatus('confirmed')} disabled={saving} data-testid="confirm-apt-btn">
                      Confirmar
                    </Button>
                  )}
                  {(appointment.status === 'scheduled' || appointment.status === 'confirmed') && (
                    <Button size="sm" className="bg-amber-500 hover:bg-amber-600 text-xs h-7" onClick={() => changeStatus('in_progress')} disabled={saving} data-testid="start-apt-btn">
                      Iniciar consulta
                    </Button>
                  )}
                  {appointment.status === 'in_progress' && (
                    <Button size="sm" className="bg-slate-600 hover:bg-slate-700 text-xs h-7" onClick={() => changeStatus('completed')} disabled={saving} data-testid="complete-apt-btn">
                      Completar
                    </Button>
                  )}
                  <Button size="sm" variant="outline" className="text-xs h-7" onClick={() => changeStatus('no_show')} disabled={saving}>
                    No asistió
                  </Button>
                </div>

                <div className="mt-3">
                  <div className="flex items-center gap-2">
                    <Input
                      className="text-xs h-7 flex-1"
                      placeholder="Motivo de cancelación..."
                      value={cancellationReason}
                      onChange={e => setCancellationReason(e.target.value)}
                      data-testid="cancel-reason-input"
                    />
                    <Button size="sm" variant="destructive" className="text-xs h-7" onClick={() => changeStatus('cancelled')} disabled={saving} data-testid="cancel-apt-btn">
                      <Ban className="w-3 h-3 mr-1" /> Cancelar
                    </Button>
                  </div>
                </div>

                <div className="mt-3 pt-3 border-t border-slate-100">
                  <p className="text-xs font-medium text-slate-600 mb-2">Recordatorio al paciente</p>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs text-slate-500">
                      {appointment.reminder_email_sent_at
                        ? `Enviado ${new Date(appointment.reminder_email_sent_at).toLocaleString('es-GT', { dateStyle: 'short', timeStyle: 'short' })}`
                        : 'Aún no se ha enviado'}
                    </span>
                    <Button
                      size="sm"
                      variant="outline"
                      className="text-xs h-7"
                      onClick={sendReminder}
                      disabled={sendingReminder}
                      data-testid="send-reminder-btn"
                    >
                      <Mail className="w-3 h-3 mr-1" />
                      {sendingReminder ? 'Enviando…' : (appointment.reminder_email_sent_at ? 'Reenviar' : 'Enviar ahora')}
                    </Button>
                  </div>
                  <p className="text-[10px] text-slate-400 mt-1">El sistema envía automáticamente 24 h antes de la cita si el paciente tiene email.</p>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="space-y-3 py-2">
            <div>
              <Label className="text-xs">Médico</Label>
              <Select value={editForm.doctor_id} onValueChange={v => setEditForm(p => ({ ...p, doctor_id: v }))}>
                <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {(config.doctors || []).map(d => (
                    <SelectItem key={d.id} value={d.id}>{d.first_name} {d.last_name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <Label className="text-xs">Fecha y hora</Label>
                <Input type="datetime-local" className="mt-1 text-sm" value={editForm.starts_at} onChange={e => setEditForm(p => ({ ...p, starts_at: e.target.value }))} />
              </div>
              <div>
                <Label className="text-xs">Duración</Label>
                <Select value={String(editForm.duration_minutes)} onValueChange={v => setEditForm(p => ({ ...p, duration_minutes: parseInt(v) }))}>
                  <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="15">15 min</SelectItem>
                    <SelectItem value="20">20 min</SelectItem>
                    <SelectItem value="30">30 min</SelectItem>
                    <SelectItem value="45">45 min</SelectItem>
                    <SelectItem value="60">60 min</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div>
              <Label className="text-xs">Motivo</Label>
              <Input className="mt-1 text-sm" value={editForm.reason} onChange={e => setEditForm(p => ({ ...p, reason: e.target.value }))} />
            </div>
            <div>
              <Label className="text-xs">Notas</Label>
              <Textarea className="mt-1 text-sm" rows={2} value={editForm.notes} onChange={e => setEditForm(p => ({ ...p, notes: e.target.value }))} />
            </div>
          </div>
        )}

        <DialogFooter>
          {!showEdit ? (
            <>
              <Button variant="outline" onClick={onClose}>Cerrar</Button>
              {appointment.status !== 'cancelled' && appointment.status !== 'completed' && (
                <Button variant="outline" onClick={() => setShowEdit(true)} data-testid="edit-apt-btn">
                  <Edit className="w-3.5 h-3.5 mr-1" /> Editar
                </Button>
              )}
            </>
          ) : (
            <>
              <Button variant="outline" onClick={() => setShowEdit(false)}>Cancelar</Button>
              <Button className="bg-teal-600 hover:bg-teal-700" onClick={saveEdit} disabled={saving} data-testid="save-edit-apt-btn">
                {saving ? 'Guardando...' : 'Guardar cambios'}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
