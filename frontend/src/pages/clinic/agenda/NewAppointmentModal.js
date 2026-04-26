import { useState, useRef } from 'react';
import axios from 'axios';
import { Button } from '../../../components/ui/button';
import { Badge } from '../../../components/ui/badge';
import { Input } from '../../../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../../components/ui/dialog';
import { Label } from '../../../components/ui/label';
import { Textarea } from '../../../components/ui/textarea';
import { toast } from 'sonner';
import { Plus, Search, User, X } from 'lucide-react';
import { API } from './constants';
import { timeToMinutes, formatTime } from './utils';

export default function NewAppointmentModal({
  config, initialDate, headers, onClose, onCreated,
  branches = [], activeBranch = null, multiBranch = false,
}) {
  const [form, setForm] = useState({
    patient_id: '',
    doctor_id: config.doctors?.[0]?.id || '',
    date: initialDate ? initialDate.toISOString().split('T')[0] : new Date().toISOString().split('T')[0],
    time: initialDate ? `${String(initialDate.getHours()).padStart(2, '0')}:${String(initialDate.getMinutes()).padStart(2, '0')}` : config.clinic.schedule_start?.slice(0, 5) || '08:00',
    duration: config.clinic.slot_duration || 30,
    reason: '',
    notes: '',
    branch_id: activeBranch?.id || (branches.find(b => b.is_main)?.id) || branches[0]?.id || '',
  });
  const [patients, setPatients] = useState([]);
  const [patientQuery, setPatientQuery] = useState('');
  const [showPatientDropdown, setShowPatientDropdown] = useState(false);
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [showNewPatient, setShowNewPatient] = useState(false);
  const [newPatient, setNewPatient] = useState({ first_name: '', last_name: '', phone: '' });
  const [saving, setSaving] = useState(false);
  const searchTimeout = useRef(null);

  const searchPatients = (q) => {
    setPatientQuery(q);
    setShowPatientDropdown(true);
    clearTimeout(searchTimeout.current);
    searchTimeout.current = setTimeout(async () => {
      try {
        const res = await axios.get(`${API}/clinic/patients/search?q=${encodeURIComponent(q)}`, { headers });
        setPatients(res.data || []);
      } catch (err) {
        console.error(err);
      }
    }, 300);
  };

  const selectPatient = (p) => {
    setSelectedPatient(p);
    setForm(prev => ({ ...prev, patient_id: p.id }));
    setPatientQuery(`${p.first_name} ${p.last_name}`);
    setShowPatientDropdown(false);
  };

  const createPatientAndSelect = async () => {
    if (!newPatient.first_name || !newPatient.last_name) {
      toast.error('Nombre y apellido son requeridos');
      return;
    }
    try {
      const res = await axios.post(`${API}/clinic/patients`, newPatient, { headers });
      selectPatient(res.data);
      setShowNewPatient(false);
      toast.success('Paciente creado');
    } catch (err) {
      toast.error('Error al crear paciente');
    }
  };

  const handleSubmit = async () => {
    if (!form.patient_id) { toast.error('Selecciona un paciente'); return; }
    if (!form.doctor_id) { toast.error('Selecciona un médico'); return; }
    setSaving(true);
    try {
      const startsAt = new Date(`${form.date}T${form.time}:00`).toISOString();
      await axios.post(`${API}/clinic/appointments`, {
        patient_id: form.patient_id,
        doctor_id: form.doctor_id,
        starts_at: startsAt,
        duration_minutes: parseInt(form.duration),
        reason: form.reason,
        notes: form.notes,
        branch_id: form.branch_id || null,
      }, { headers });
      toast.success('Cita creada exitosamente');
      onCreated();
    } catch (err) {
      const msg = err.response?.data?.detail || 'Error al crear cita';
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  };

  const startMin = timeToMinutes(config.clinic.schedule_start);
  const endMin = timeToMinutes(config.clinic.schedule_end);
  const slotDur = config.clinic.slot_duration || 30;
  const timeOptions = [];
  for (let m = startMin; m < endMin; m += slotDur) {
    const h = Math.floor(m / 60);
    const mm = m % 60;
    timeOptions.push(`${String(h).padStart(2, '0')}:${String(mm).padStart(2, '0')}`);
  }

  return (
    <Dialog open={true} onOpenChange={onClose}>
      <DialogContent className="max-w-lg" data-testid="new-apt-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Plus className="w-5 h-5 text-teal-600" /> Nueva cita
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div>
            <Label className="text-xs font-medium text-slate-600">Paciente *</Label>
            <div className="relative mt-1">
              <Search className="w-4 h-4 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
              <Input
                className="pl-8"
                placeholder="Buscar paciente por nombre..."
                value={patientQuery}
                onChange={e => searchPatients(e.target.value)}
                onFocus={() => searchPatients(patientQuery)}
                data-testid="patient-search-input"
              />
              {showPatientDropdown && (
                <div className="absolute z-50 top-full left-0 right-0 mt-1 bg-white border border-slate-200 rounded-md shadow-lg max-h-48 overflow-auto">
                  {patients.map(p => (
                    <div
                      key={p.id}
                      className="px-3 py-2 hover:bg-slate-50 cursor-pointer text-sm flex items-center justify-between"
                      onClick={() => selectPatient(p)}
                      data-testid={`patient-option-${p.id}`}
                    >
                      <span className="font-medium">{p.first_name} {p.last_name}</span>
                      {p.phone && <span className="text-xs text-slate-400">{p.phone}</span>}
                    </div>
                  ))}
                  {patients.length === 0 && (
                    <div className="px-3 py-2 text-sm text-slate-500">
                      No se encontraron pacientes
                    </div>
                  )}
                  <div
                    className="px-3 py-2 border-t border-slate-100 text-sm font-medium text-teal-600 cursor-pointer hover:bg-teal-50"
                    onClick={() => { setShowPatientDropdown(false); setShowNewPatient(true); }}
                    data-testid="create-patient-btn"
                  >
                    <Plus className="w-3.5 h-3.5 inline mr-1" /> Crear nuevo paciente
                  </div>
                </div>
              )}
            </div>
            {selectedPatient && (
              <div className="mt-1 flex items-center gap-2">
                <Badge variant="outline" className="bg-teal-50 text-teal-700 border-teal-200 text-xs">
                  <User className="w-3 h-3 mr-1" /> {selectedPatient.first_name} {selectedPatient.last_name}
                </Badge>
                <button onClick={() => { setSelectedPatient(null); setForm(p => ({ ...p, patient_id: '' })); setPatientQuery(''); }} className="text-xs text-slate-400 hover:text-red-500">
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            )}
          </div>

          {showNewPatient && (
            <div className="border border-dashed border-teal-300 rounded-md p-3 bg-teal-50/50 space-y-2">
              <p className="text-xs font-semibold text-teal-700">Nuevo paciente</p>
              <div className="grid grid-cols-2 gap-2">
                <Input placeholder="Nombre *" value={newPatient.first_name} onChange={e => setNewPatient(p => ({ ...p, first_name: e.target.value }))} className="h-8 text-sm" data-testid="new-patient-first-name" />
                <Input placeholder="Apellido *" value={newPatient.last_name} onChange={e => setNewPatient(p => ({ ...p, last_name: e.target.value }))} className="h-8 text-sm" data-testid="new-patient-last-name" />
              </div>
              <Input placeholder="Teléfono" value={newPatient.phone} onChange={e => setNewPatient(p => ({ ...p, phone: e.target.value }))} className="h-8 text-sm" />
              <div className="flex gap-2">
                <Button size="sm" className="bg-teal-600 hover:bg-teal-700 text-xs h-7" onClick={createPatientAndSelect} data-testid="save-new-patient-btn">Guardar</Button>
                <Button size="sm" variant="ghost" className="text-xs h-7" onClick={() => setShowNewPatient(false)}>Cancelar</Button>
              </div>
            </div>
          )}

          <div>
            <Label className="text-xs font-medium text-slate-600">Médico *</Label>
            <Select value={form.doctor_id} onValueChange={v => setForm(p => ({ ...p, doctor_id: v }))}>
              <SelectTrigger className="mt-1" data-testid="doctor-select">
                <SelectValue placeholder="Seleccionar médico" />
              </SelectTrigger>
              <SelectContent>
                {(config.doctors || []).map(d => (
                  <SelectItem key={d.id} value={d.id}>{d.first_name} {d.last_name}{d.specialty ? ` - ${d.specialty}` : ''}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {multiBranch && branches.length > 0 && (
            <div>
              <Label className="text-xs font-medium text-slate-600">Sucursal</Label>
              <Select value={form.branch_id || ''} onValueChange={v => setForm(p => ({ ...p, branch_id: v }))}>
                <SelectTrigger className="mt-1" data-testid="apt-branch-select">
                  <SelectValue placeholder="Seleccionar sucursal" />
                </SelectTrigger>
                <SelectContent>
                  {branches.map(b => (
                    <SelectItem key={b.id} value={b.id}>
                      {b.name}{b.is_main ? ' (Principal)' : ''}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          <div className="grid grid-cols-3 gap-3">
            <div>
              <Label className="text-xs font-medium text-slate-600">Fecha *</Label>
              <Input type="date" className="mt-1" value={form.date} onChange={e => setForm(p => ({ ...p, date: e.target.value }))} data-testid="apt-date-input" />
            </div>
            <div>
              <Label className="text-xs font-medium text-slate-600">Hora *</Label>
              <Select value={form.time} onValueChange={v => setForm(p => ({ ...p, time: v }))}>
                <SelectTrigger className="mt-1" data-testid="apt-time-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {timeOptions.map(t => (
                    <SelectItem key={t} value={t}>{formatTime(timeToMinutes(t))}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs font-medium text-slate-600">Duración</Label>
              <Select value={String(form.duration)} onValueChange={v => setForm(p => ({ ...p, duration: parseInt(v) }))}>
                <SelectTrigger className="mt-1" data-testid="apt-duration-select"><SelectValue /></SelectTrigger>
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
            <Label className="text-xs font-medium text-slate-600">Motivo de consulta</Label>
            <Input className="mt-1" placeholder="Ej: Consulta general, control..." value={form.reason} onChange={e => setForm(p => ({ ...p, reason: e.target.value }))} data-testid="apt-reason-input" />
          </div>

          <div>
            <Label className="text-xs font-medium text-slate-600">Notas</Label>
            <Textarea className="mt-1 text-sm" rows={2} placeholder="Notas adicionales..." value={form.notes} onChange={e => setForm(p => ({ ...p, notes: e.target.value }))} data-testid="apt-notes-input" />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancelar</Button>
          <Button className="bg-teal-600 hover:bg-teal-700" onClick={handleSubmit} disabled={saving} data-testid="save-apt-btn">
            {saving ? 'Guardando...' : 'Agendar cita'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
