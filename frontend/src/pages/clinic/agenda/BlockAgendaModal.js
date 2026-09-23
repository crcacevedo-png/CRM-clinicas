import { useState } from 'react';
import axios from 'axios';
import { Button } from '../../../components/ui/button';
import { Input } from '../../../components/ui/input';
import { Label } from '../../../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../../components/ui/dialog';
import { toast } from 'sonner';
import { Lock } from 'lucide-react';
import { API } from './constants';

const TIME_OPTIONS = [];
for (let m = 0; m < 24 * 60; m += 30) {
  TIME_OPTIONS.push(`${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`);
}

export default function BlockAgendaModal({ config, headers, branches = [], activeBranch = null, onClose, onCreated }) {
  const today = new Date().toISOString().split('T')[0];
  const [scope, setScope] = useState('doctor');
  const [doctorId, setDoctorId] = useState(config.doctors?.[0]?.id || '');
  const [branchId, setBranchId] = useState(activeBranch?.id || branches[0]?.id || '');
  const [date, setDate] = useState(today);
  const [endDate, setEndDate] = useState(today);
  const [allDay, setAllDay] = useState(false);
  const [startTime, setStartTime] = useState(config.clinic?.schedule_start?.slice(0, 5) || '08:00');
  const [endTime, setEndTime] = useState(config.clinic?.schedule_end?.slice(0, 5) || '17:00');
  const [label, setLabel] = useState('');
  const [saving, setSaving] = useState(false);

  const submit = async () => {
    if (scope === 'doctor' && !doctorId) { toast.error('Selecciona un médico'); return; }
    if (scope === 'branch' && !branchId) { toast.error('Selecciona una sucursal'); return; }
    const ed = endDate && endDate >= date ? endDate : date;
    let startsAt, endsAt;
    if (allDay) {
      startsAt = new Date(`${date}T00:00:00`);
      endsAt = new Date(`${ed}T23:59:59`);
    } else {
      startsAt = new Date(`${date}T${startTime}:00`);
      endsAt = new Date(`${ed}T${endTime}:00`);
    }
    if (endsAt <= startsAt) { toast.error('El fin debe ser posterior al inicio'); return; }
    setSaving(true);
    try {
      await axios.post(`${API}/clinic/agenda-blocks`, {
        scope,
        doctor_id: scope === 'doctor' ? doctorId : null,
        branch_id: scope === 'branch' ? branchId : null,
        starts_at: startsAt.toISOString(),
        ends_at: endsAt.toISOString(),
        all_day: allDay,
        label: label.trim() || null,
      }, { headers });
      toast.success('Agenda bloqueada');
      onCreated();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al bloquear la agenda');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={true} onOpenChange={onClose}>
      <DialogContent className="max-w-md" data-testid="block-agenda-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Lock className="w-5 h-5 text-slate-600" /> Bloquear agenda
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div>
            <Label className="text-xs font-medium text-slate-600">Tipo de bloqueo *</Label>
            <Select value={scope} onValueChange={setScope}>
              <SelectTrigger className="mt-1" data-testid="block-scope-select"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="doctor">Por médico (todas las sucursales)</SelectItem>
                <SelectItem value="branch">Sucursal completa (todos los médicos)</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {scope === 'doctor' ? (
            <div>
              <Label className="text-xs font-medium text-slate-600">Médico *</Label>
              <Select value={doctorId} onValueChange={setDoctorId}>
                <SelectTrigger className="mt-1" data-testid="block-doctor-select"><SelectValue placeholder="Seleccionar médico" /></SelectTrigger>
                <SelectContent>
                  {(config.doctors || []).map(d => (
                    <SelectItem key={d.id} value={d.id}>{d.first_name} {d.last_name}{d.specialty ? ` - ${d.specialty}` : ''}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : (
            <div>
              <Label className="text-xs font-medium text-slate-600">Sucursal *</Label>
              <Select value={branchId} onValueChange={setBranchId}>
                <SelectTrigger className="mt-1" data-testid="block-branch-select"><SelectValue placeholder="Seleccionar sucursal" /></SelectTrigger>
                <SelectContent>
                  {(branches || []).map(b => (
                    <SelectItem key={b.id} value={b.id}>{b.name}{b.is_main ? ' (Principal)' : ''}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-xs font-medium text-slate-600">Desde *</Label>
              <Input type="date" className="mt-1" value={date} onChange={e => setDate(e.target.value)} data-testid="block-date-input" />
            </div>
            <div>
              <Label className="text-xs font-medium text-slate-600">Hasta</Label>
              <Input type="date" className="mt-1" value={endDate} min={date} onChange={e => setEndDate(e.target.value)} data-testid="block-end-date-input" />
            </div>
          </div>

          <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
            <input type="checkbox" checked={allDay} onChange={e => setAllDay(e.target.checked)} className="w-4 h-4 accent-teal-600" data-testid="block-all-day" />
            Todo el día
          </label>

          {!allDay && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs font-medium text-slate-600">Hora inicio *</Label>
                <Select value={startTime} onValueChange={setStartTime}>
                  <SelectTrigger className="mt-1" data-testid="block-start-time"><SelectValue /></SelectTrigger>
                  <SelectContent className="max-h-60">{TIME_OPTIONS.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs font-medium text-slate-600">Hora fin *</Label>
                <Select value={endTime} onValueChange={setEndTime}>
                  <SelectTrigger className="mt-1" data-testid="block-end-time"><SelectValue /></SelectTrigger>
                  <SelectContent className="max-h-60">{TIME_OPTIONS.map(t => <SelectItem key={t} value={t}>{t}</SelectItem>)}</SelectContent>
                </Select>
              </div>
            </div>
          )}

          <div>
            <Label className="text-xs font-medium text-slate-600">Etiqueta / motivo</Label>
            <Input className="mt-1" placeholder="Ej: Vacaciones, Reunión, Feriado..." value={label} onChange={e => setLabel(e.target.value)} data-testid="block-label-input" />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancelar</Button>
          <Button className="bg-slate-800 hover:bg-slate-900 text-white" onClick={submit} disabled={saving} data-testid="save-block-btn">
            {saving ? 'Bloqueando...' : 'Bloquear'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
