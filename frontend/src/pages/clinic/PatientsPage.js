import { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import axios from 'axios';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Badge } from '../../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../components/ui/dialog';
import { Label } from '../../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { toast } from 'sonner';
import { Users, Plus, Search, Phone, Mail } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function PatientsPage() {
  const { getAuthHeaders } = useAuth();
  const [patients, setPatients] = useState([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [showNew, setShowNew] = useState(false);
  const [form, setForm] = useState({ first_name: '', last_name: '', phone: '', email: '', date_of_birth: '', gender: '', national_id: '' });
  const [saving, setSaving] = useState(false);
  const headers = getAuthHeaders();

  useEffect(() => { fetchPatients(); }, [search]);

  const fetchPatients = async () => {
    try {
      const res = await axios.get(`${API}/clinic/patients?q=${encodeURIComponent(search)}`, { headers });
      setPatients(res.data || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const createPatient = async () => {
    if (!form.first_name || !form.last_name) { toast.error('Nombre y apellido requeridos'); return; }
    setSaving(true);
    try {
      await axios.post(`${API}/clinic/patients`, form, { headers });
      toast.success('Paciente creado');
      setShowNew(false);
      setForm({ first_name: '', last_name: '', phone: '', email: '', date_of_birth: '', gender: '', national_id: '' });
      fetchPatients();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="p-8" data-testid="patients-page">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Pacientes</h1>
          <p className="text-sm text-slate-500 mt-1">{patients.length} paciente{patients.length !== 1 ? 's' : ''} registrado{patients.length !== 1 ? 's' : ''}</p>
        </div>
        <Button className="bg-teal-600 hover:bg-teal-700" onClick={() => setShowNew(true)} data-testid="new-patient-btn">
          <Plus className="w-4 h-4 mr-1" /> Nuevo paciente
        </Button>
      </div>

      <div className="relative mb-4 max-w-sm">
        <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
        <Input className="pl-9" placeholder="Buscar paciente..." value={search} onChange={e => setSearch(e.target.value)} data-testid="patient-search" />
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : patients.length === 0 ? (
        <Card className="border-dashed border-2 border-slate-200">
          <CardContent className="p-12 text-center">
            <Users className="w-12 h-12 text-slate-300 mx-auto mb-3" />
            <p className="text-slate-500">No hay pacientes registrados</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {patients.map(p => (
            <Card key={p.id} className="border border-slate-200 hover:shadow-md transition-shadow">
              <CardContent className="p-4">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-semibold text-slate-900">{p.first_name} {p.last_name}</p>
                    {p.national_id && <p className="text-xs text-slate-500">ID: {p.national_id}</p>}
                  </div>
                  <Badge variant="outline" className={`text-xs ${p.is_active ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-red-50 text-red-600 border-red-200'}`}>
                    {p.is_active ? 'Activo' : 'Inactivo'}
                  </Badge>
                </div>
                <div className="mt-3 space-y-1">
                  {p.phone && <div className="flex items-center gap-2 text-xs text-slate-600"><Phone className="w-3 h-3" />{p.phone}</div>}
                  {p.email && <div className="flex items-center gap-2 text-xs text-slate-600"><Mail className="w-3 h-3" />{p.email}</div>}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={showNew} onOpenChange={setShowNew}>
        <DialogContent className="max-w-md" data-testid="new-patient-modal">
          <DialogHeader>
            <DialogTitle>Nuevo paciente</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs">Nombre *</Label>
                <Input className="mt-1" value={form.first_name} onChange={e => setForm(p => ({ ...p, first_name: e.target.value }))} data-testid="patient-first-name" />
              </div>
              <div>
                <Label className="text-xs">Apellido *</Label>
                <Input className="mt-1" value={form.last_name} onChange={e => setForm(p => ({ ...p, last_name: e.target.value }))} data-testid="patient-last-name" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs">Teléfono</Label>
                <Input className="mt-1" value={form.phone} onChange={e => setForm(p => ({ ...p, phone: e.target.value }))} />
              </div>
              <div>
                <Label className="text-xs">Email</Label>
                <Input className="mt-1" type="email" value={form.email} onChange={e => setForm(p => ({ ...p, email: e.target.value }))} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs">Fecha de nacimiento</Label>
                <Input className="mt-1" type="date" value={form.date_of_birth} onChange={e => setForm(p => ({ ...p, date_of_birth: e.target.value }))} />
              </div>
              <div>
                <Label className="text-xs">Género</Label>
                <Select value={form.gender} onValueChange={v => setForm(p => ({ ...p, gender: v }))}>
                  <SelectTrigger className="mt-1"><SelectValue placeholder="Seleccionar" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="male">Masculino</SelectItem>
                    <SelectItem value="female">Femenino</SelectItem>
                    <SelectItem value="other">Otro</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div>
              <Label className="text-xs">Número de identificación</Label>
              <Input className="mt-1" value={form.national_id} onChange={e => setForm(p => ({ ...p, national_id: e.target.value }))} placeholder="DPI/CUI" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowNew(false)}>Cancelar</Button>
            <Button className="bg-teal-600 hover:bg-teal-700" onClick={createPatient} disabled={saving} data-testid="save-patient-btn">
              {saving ? 'Guardando...' : 'Guardar'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
