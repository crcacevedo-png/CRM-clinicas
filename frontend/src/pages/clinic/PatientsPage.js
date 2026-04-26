import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import axios from 'axios';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Badge } from '../../components/ui/badge';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '../../components/ui/sheet';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { toast } from 'sonner';
import { Users, Plus, Search, Phone, Mail, ChevronLeft, ChevronRight, Calendar, UserCheck, UserX, X, Upload } from 'lucide-react';
import CsvImportDialog from '../../components/CsvImportDialog';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const patientSchema = z.object({
  first_name: z.string().min(2, 'El nombre debe tener al menos 2 caracteres'),
  last_name: z.string().min(2, 'El apellido debe tener al menos 2 caracteres'),
  date_of_birth: z.string().optional().or(z.literal('')),
  gender: z.string().optional().or(z.literal('')),
  national_id: z.string().optional().or(z.literal('')),
  nationality: z.string().optional().or(z.literal('')),
  phone: z.string().optional().or(z.literal('')),
  phone_secondary: z.string().optional().or(z.literal('')),
  email: z.string().email('Correo electrónico inválido').optional().or(z.literal('')),
  address: z.string().optional().or(z.literal('')),
  city: z.string().optional().or(z.literal('')),
  state: z.string().optional().or(z.literal('')),
  country: z.string().optional().or(z.literal('')),
  emergency_contact_name: z.string().optional().or(z.literal('')),
  emergency_contact_relation: z.string().optional().or(z.literal('')),
  emergency_contact_phone: z.string().optional().or(z.literal('')),
  blood_type: z.string().optional().or(z.literal('')),
  allergies: z.string().optional().or(z.literal('')),
  chronic_conditions: z.string().optional().or(z.literal('')),
  current_medications: z.string().optional().or(z.literal('')),
  insurance_provider: z.string().optional().or(z.literal('')),
  insurance_policy_number: z.string().optional().or(z.literal('')),
  insurance_expiry: z.string().optional().or(z.literal('')),
  notes: z.string().optional().or(z.literal('')),
});

const defaultValues = {
  first_name: '', last_name: '', date_of_birth: '', gender: '', national_id: '',
  nationality: '', phone: '', phone_secondary: '', email: '', address: '',
  city: '', state: '', country: '', emergency_contact_name: '',
  emergency_contact_relation: '', emergency_contact_phone: '', blood_type: '',
  allergies: '', chronic_conditions: '', current_medications: '',
  insurance_provider: '', insurance_policy_number: '', insurance_expiry: '', notes: '',
};

const BLOOD_TYPES = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'];

function FormField({ label, required, error, children }) {
  return (
    <div className="space-y-1">
      <Label className="text-xs font-medium text-slate-600">
        {label}{required && <span className="text-red-500 ml-0.5">*</span>}
      </Label>
      {children}
      {error && <p className="text-xs text-red-500">{error.message}</p>}
    </div>
  );
}

function TagInput({ value, onChange, placeholder }) {
  const [input, setInput] = useState('');
  const tags = value ? value.split(',').map(t => t.trim()).filter(Boolean) : [];

  const addTag = () => {
    const trimmed = input.trim();
    if (trimmed && !tags.includes(trimmed)) {
      const next = [...tags, trimmed].join(', ');
      onChange(next);
      setInput('');
    }
  };

  const removeTag = (idx) => {
    const next = tags.filter((_, i) => i !== idx).join(', ');
    onChange(next);
  };

  return (
    <div>
      <div className="flex gap-1.5 flex-wrap mb-1.5">
        {tags.map((tag, i) => (
          <Badge key={i} variant="secondary" className="text-xs gap-1 pl-2 pr-1 py-0.5 bg-teal-50 text-teal-700 border-teal-200">
            {tag}
            <button type="button" onClick={() => removeTag(i)} className="hover:bg-teal-200 rounded-full p-0.5">
              <X className="w-2.5 h-2.5" />
            </button>
          </Badge>
        ))}
      </div>
      <Input
        value={input}
        onChange={e => setInput(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addTag(); } }}
        placeholder={placeholder}
        className="text-sm"
      />
    </div>
  );
}

export default function PatientsPage() {
  const { getAuthHeaders } = useAuth();
  const navigate = useNavigate();
  const [patients, setPatients] = useState([]);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [editingPatient, setEditingPatient] = useState(null);
  const [saving, setSaving] = useState(false);
  const [formTab, setFormTab] = useState('personal');
  const headers = getAuthHeaders();

  const { register, handleSubmit, control, reset, formState: { errors }, setValue, watch } = useForm({
    resolver: zodResolver(patientSchema),
    defaultValues,
  });

  const fetchPatients = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(page), limit: '15' });
      if (search) params.set('q', search);
      if (statusFilter !== 'all') params.set('status', statusFilter);
      const res = await axios.get(`${API}/clinic/patients?${params}`, { headers });
      setPatients(res.data.patients || []);
      setTotal(res.data.total || 0);
      setPages(res.data.pages || 1);
    } catch (err) {
      console.error(err);
      toast.error('Error al cargar pacientes');
    } finally {
      setLoading(false);
    }
  }, [page, search, statusFilter]);

  useEffect(() => { fetchPatients(); }, [fetchPatients]);

  useEffect(() => { setPage(1); }, [search, statusFilter]);

  const openNewPatient = () => {
    setEditingPatient(null);
    reset(defaultValues);
    setFormTab('personal');
    setShowForm(true);
  };

  const openEditPatient = async (patient) => {
    try {
      const res = await axios.get(`${API}/clinic/patients/${patient.id}`, { headers });
      const p = res.data.patient;
      reset({
        first_name: p.first_name || '',
        last_name: p.last_name || '',
        date_of_birth: p.date_of_birth || '',
        gender: p.gender || '',
        national_id: p.national_id || '',
        nationality: p.nationality || '',
        phone: p.phone || '',
        phone_secondary: p.phone_secondary || '',
        email: p.email || '',
        address: p.address || '',
        city: p.city || '',
        state: p.state || '',
        country: p.country || '',
        emergency_contact_name: p.emergency_contact_name || '',
        emergency_contact_relation: p.emergency_contact_relation || '',
        emergency_contact_phone: p.emergency_contact_phone || '',
        blood_type: p.blood_type || '',
        allergies: (p.allergies || []).join(', '),
        chronic_conditions: (p.chronic_conditions || []).join(', '),
        current_medications: (p.current_medications || []).join(', '),
        insurance_provider: p.insurance_provider || '',
        insurance_policy_number: p.insurance_policy_number || '',
        insurance_expiry: p.insurance_expiry || '',
        notes: p.notes || '',
      });
      setEditingPatient(p);
      setFormTab('personal');
      setShowForm(true);
    } catch {
      toast.error('Error al cargar datos del paciente');
    }
  };

  const onSubmit = async (data) => {
    setSaving(true);
    try {
      const payload = { ...data };
      // Convert comma-separated strings to arrays
      payload.allergies = data.allergies ? data.allergies.split(',').map(s => s.trim()).filter(Boolean) : [];
      payload.chronic_conditions = data.chronic_conditions ? data.chronic_conditions.split(',').map(s => s.trim()).filter(Boolean) : [];
      payload.current_medications = data.current_medications ? data.current_medications.split(',').map(s => s.trim()).filter(Boolean) : [];
      // Remove empty strings
      Object.keys(payload).forEach(k => { if (payload[k] === '') payload[k] = null; });

      if (editingPatient) {
        await axios.put(`${API}/clinic/patients/${editingPatient.id}`, payload, { headers });
        toast.success('Paciente actualizado');
      } else {
        await axios.post(`${API}/clinic/patients`, payload, { headers });
        toast.success('Paciente creado exitosamente');
      }
      setShowForm(false);
      fetchPatients();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al guardar paciente');
    } finally {
      setSaving(false);
    }
  };

  const formatDate = (d) => {
    if (!d) return '—';
    return new Date(d).toLocaleDateString('es-GT', { day: '2-digit', month: 'short', year: 'numeric' });
  };

  const calcAge = (dob) => {
    if (!dob) return null;
    const diff = Date.now() - new Date(dob).getTime();
    return Math.floor(diff / 31557600000);
  };

  return (
    <div className="p-6 lg:p-8" data-testid="patients-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900" data-testid="patients-title">Pacientes</h1>
          <p className="text-sm text-slate-500 mt-0.5">{total} paciente{total !== 1 ? 's' : ''} registrado{total !== 1 ? 's' : ''}</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" className="border-teal-600 text-teal-600 hover:bg-teal-50" onClick={() => setShowImport(true)} data-testid="import-patients-btn">
            <Upload className="w-4 h-4 mr-1.5" /> Importar
          </Button>
          <Button className="bg-teal-600 hover:bg-teal-700 shadow-sm" onClick={openNewPatient} data-testid="new-patient-btn">
            <Plus className="w-4 h-4 mr-1.5" /> Nuevo paciente
          </Button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3 mb-5">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <Input
            className="pl-9 text-sm"
            placeholder="Buscar por nombre, DPI o teléfono..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            data-testid="patient-search"
          />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-40" data-testid="patient-status-filter">
            <SelectValue placeholder="Estado" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todos</SelectItem>
            <SelectItem value="active">Activos</SelectItem>
            <SelectItem value="inactive">Inactivos</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex justify-center py-16">
          <div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : patients.length === 0 ? (
        <Card className="border-dashed border-2 border-slate-200">
          <CardContent className="p-16 text-center">
            <Users className="w-12 h-12 text-slate-300 mx-auto mb-3" />
            <p className="text-slate-500 font-medium">No se encontraron pacientes</p>
            <p className="text-sm text-slate-400 mt-1">Crea un nuevo paciente para comenzar</p>
          </CardContent>
        </Card>
      ) : (
        <>
          <Card className="border border-slate-200 overflow-hidden" data-testid="patients-table-card">
            <Table>
              <TableHeader>
                <TableRow className="bg-slate-50/80">
                  <TableHead className="text-xs font-semibold text-slate-600">Paciente</TableHead>
                  <TableHead className="text-xs font-semibold text-slate-600">DPI / ID</TableHead>
                  <TableHead className="text-xs font-semibold text-slate-600">Contacto</TableHead>
                  <TableHead className="text-xs font-semibold text-slate-600 text-center">Edad</TableHead>
                  <TableHead className="text-xs font-semibold text-slate-600 text-center">Visitas</TableHead>
                  <TableHead className="text-xs font-semibold text-slate-600">Última visita</TableHead>
                  <TableHead className="text-xs font-semibold text-slate-600 text-center">Estado</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {patients.map(p => (
                  <TableRow
                    key={p.id}
                    className="cursor-pointer hover:bg-teal-50/40 transition-colors"
                    onClick={() => navigate(`/dashboard/pacientes/${p.id}`)}
                    data-testid={`patient-row-${p.id}`}
                  >
                    <TableCell>
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-teal-100 text-teal-700 flex items-center justify-center text-xs font-bold flex-shrink-0">
                          {(p.first_name?.[0] || '').toUpperCase()}{(p.last_name?.[0] || '').toUpperCase()}
                        </div>
                        <div>
                          <p className="font-medium text-sm text-slate-900">{p.first_name} {p.last_name}</p>
                          {p.gender && <p className="text-xs text-slate-400">{p.gender === 'male' ? 'Masculino' : p.gender === 'female' ? 'Femenino' : 'Otro'}</p>}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell className="text-sm text-slate-600">{p.national_id || '—'}</TableCell>
                    <TableCell>
                      <div className="space-y-0.5">
                        {p.phone && <div className="flex items-center gap-1.5 text-xs text-slate-600"><Phone className="w-3 h-3" />{p.phone}</div>}
                        {p.email && <div className="flex items-center gap-1.5 text-xs text-slate-500"><Mail className="w-3 h-3" />{p.email}</div>}
                        {!p.phone && !p.email && <span className="text-xs text-slate-400">—</span>}
                      </div>
                    </TableCell>
                    <TableCell className="text-center text-sm text-slate-600">
                      {calcAge(p.date_of_birth) !== null ? `${calcAge(p.date_of_birth)} años` : '—'}
                    </TableCell>
                    <TableCell className="text-center">
                      <span className="text-sm font-medium text-slate-700">{p.visit_count ?? 0}</span>
                    </TableCell>
                    <TableCell className="text-xs text-slate-500">{formatDate(p.last_visit)}</TableCell>
                    <TableCell className="text-center">
                      <Badge variant="outline" className={`text-xs ${p.is_active ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-red-50 text-red-600 border-red-200'}`}>
                        {p.is_active ? 'Activo' : 'Inactivo'}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>

          {/* Pagination */}
          {pages > 1 && (
            <div className="flex items-center justify-between mt-4 px-1" data-testid="patients-pagination">
              <p className="text-xs text-slate-500">
                Mostrando {(page - 1) * 15 + 1}-{Math.min(page * 15, total)} de {total}
              </p>
              <div className="flex items-center gap-1">
                <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)} data-testid="patients-prev-page">
                  <ChevronLeft className="w-4 h-4" />
                </Button>
                {Array.from({ length: Math.min(pages, 5) }, (_, i) => {
                  let num;
                  if (pages <= 5) num = i + 1;
                  else if (page <= 3) num = i + 1;
                  else if (page >= pages - 2) num = pages - 4 + i;
                  else num = page - 2 + i;
                  return (
                    <Button
                      key={num}
                      variant={page === num ? 'default' : 'outline'}
                      size="sm"
                      className={`w-8 h-8 p-0 text-xs ${page === num ? 'bg-teal-600 hover:bg-teal-700' : ''}`}
                      onClick={() => setPage(num)}
                    >
                      {num}
                    </Button>
                  );
                })}
                <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => setPage(p => p + 1)} data-testid="patients-next-page">
                  <ChevronRight className="w-4 h-4" />
                </Button>
              </div>
            </div>
          )}
        </>
      )}

      {/* Patient Form Sheet */}
      <Sheet open={showForm} onOpenChange={setShowForm}>
        <SheetContent className="sm:max-w-2xl overflow-y-auto" data-testid="patient-form-sheet">
          <SheetHeader className="mb-4">
            <SheetTitle className="text-lg">{editingPatient ? 'Editar paciente' : 'Nuevo paciente'}</SheetTitle>
          </SheetHeader>

          <form onSubmit={handleSubmit(onSubmit)}>
            <Tabs value={formTab} onValueChange={setFormTab} className="w-full">
              <TabsList className="grid grid-cols-4 w-full mb-4">
                <TabsTrigger value="personal" className="text-xs" data-testid="form-tab-personal">Personal</TabsTrigger>
                <TabsTrigger value="contact" className="text-xs" data-testid="form-tab-contact">Contacto</TabsTrigger>
                <TabsTrigger value="medical" className="text-xs" data-testid="form-tab-medical">Médico</TabsTrigger>
                <TabsTrigger value="insurance" className="text-xs" data-testid="form-tab-insurance">Seguro</TabsTrigger>
              </TabsList>

              {/* Tab Personal */}
              <TabsContent value="personal" className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <FormField label="Nombre" required error={errors.first_name}>
                    <Input {...register('first_name')} className="text-sm" data-testid="patient-first-name" />
                  </FormField>
                  <FormField label="Apellido" required error={errors.last_name}>
                    <Input {...register('last_name')} className="text-sm" data-testid="patient-last-name" />
                  </FormField>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <FormField label="Fecha de nacimiento" error={errors.date_of_birth}>
                    <Input type="date" {...register('date_of_birth')} className="text-sm" data-testid="patient-dob" />
                  </FormField>
                  <FormField label="Género" error={errors.gender}>
                    <Controller
                      name="gender"
                      control={control}
                      render={({ field }) => (
                        <Select value={field.value} onValueChange={field.onChange}>
                          <SelectTrigger className="text-sm" data-testid="patient-gender">
                            <SelectValue placeholder="Seleccionar" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="male">Masculino</SelectItem>
                            <SelectItem value="female">Femenino</SelectItem>
                            <SelectItem value="other">Otro</SelectItem>
                          </SelectContent>
                        </Select>
                      )}
                    />
                  </FormField>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <FormField label="Número de identificación (DPI)" error={errors.national_id}>
                    <Input {...register('national_id')} placeholder="0000 00000 0000" className="text-sm" data-testid="patient-national-id" />
                  </FormField>
                  <FormField label="Nacionalidad" error={errors.nationality}>
                    <Input {...register('nationality')} placeholder="Guatemalteca" className="text-sm" />
                  </FormField>
                </div>
              </TabsContent>

              {/* Tab Contacto */}
              <TabsContent value="contact" className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <FormField label="Teléfono principal" error={errors.phone}>
                    <Input {...register('phone')} placeholder="+502 0000-0000" className="text-sm" data-testid="patient-phone" />
                  </FormField>
                  <FormField label="Teléfono secundario" error={errors.phone_secondary}>
                    <Input {...register('phone_secondary')} className="text-sm" />
                  </FormField>
                </div>
                <FormField label="Correo electrónico" error={errors.email}>
                  <Input type="email" {...register('email')} className="text-sm" data-testid="patient-email" />
                </FormField>
                <FormField label="Dirección" error={errors.address}>
                  <Input {...register('address')} className="text-sm" />
                </FormField>
                <div className="grid grid-cols-3 gap-3">
                  <FormField label="Ciudad" error={errors.city}>
                    <Input {...register('city')} className="text-sm" />
                  </FormField>
                  <FormField label="Departamento" error={errors.state}>
                    <Input {...register('state')} className="text-sm" />
                  </FormField>
                  <FormField label="País" error={errors.country}>
                    <Input {...register('country')} placeholder="Guatemala" className="text-sm" />
                  </FormField>
                </div>

                <div className="border-t pt-3 mt-3">
                  <p className="text-sm font-medium text-slate-700 mb-3">Contacto de emergencia</p>
                  <div className="grid grid-cols-3 gap-3">
                    <FormField label="Nombre" error={errors.emergency_contact_name}>
                      <Input {...register('emergency_contact_name')} className="text-sm" data-testid="patient-emergency-name" />
                    </FormField>
                    <FormField label="Relación" error={errors.emergency_contact_relation}>
                      <Input {...register('emergency_contact_relation')} placeholder="Madre, Padre, Esposo/a" className="text-sm" />
                    </FormField>
                    <FormField label="Teléfono" error={errors.emergency_contact_phone}>
                      <Input {...register('emergency_contact_phone')} className="text-sm" data-testid="patient-emergency-phone" />
                    </FormField>
                  </div>
                </div>
              </TabsContent>

              {/* Tab Médico */}
              <TabsContent value="medical" className="space-y-3">
                <FormField label="Tipo de sangre" error={errors.blood_type}>
                  <Controller
                    name="blood_type"
                    control={control}
                    render={({ field }) => (
                      <Select value={field.value} onValueChange={field.onChange}>
                        <SelectTrigger className="text-sm" data-testid="patient-blood-type">
                          <SelectValue placeholder="Seleccionar tipo" />
                        </SelectTrigger>
                        <SelectContent>
                          {BLOOD_TYPES.map(bt => (
                            <SelectItem key={bt} value={bt}>{bt}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  />
                </FormField>

                <FormField label="Alergias" error={errors.allergies}>
                  <Controller
                    name="allergies"
                    control={control}
                    render={({ field }) => (
                      <TagInput value={field.value} onChange={field.onChange} placeholder="Escribe y presiona Enter" />
                    )}
                  />
                </FormField>

                <FormField label="Condiciones crónicas" error={errors.chronic_conditions}>
                  <Controller
                    name="chronic_conditions"
                    control={control}
                    render={({ field }) => (
                      <TagInput value={field.value} onChange={field.onChange} placeholder="Escribe y presiona Enter" />
                    )}
                  />
                </FormField>

                <FormField label="Medicamentos actuales" error={errors.current_medications}>
                  <Controller
                    name="current_medications"
                    control={control}
                    render={({ field }) => (
                      <TagInput value={field.value} onChange={field.onChange} placeholder="Escribe y presiona Enter" />
                    )}
                  />
                </FormField>

                <FormField label="Notas clínicas" error={errors.notes}>
                  <Textarea {...register('notes')} placeholder="Observaciones relevantes..." className="text-sm min-h-[80px]" />
                </FormField>
              </TabsContent>

              {/* Tab Seguro */}
              <TabsContent value="insurance" className="space-y-3">
                <FormField label="Proveedor de seguro" error={errors.insurance_provider}>
                  <Input {...register('insurance_provider')} placeholder="Nombre de aseguradora" className="text-sm" data-testid="patient-insurance-provider" />
                </FormField>
                <FormField label="Número de póliza" error={errors.insurance_policy_number}>
                  <Input {...register('insurance_policy_number')} className="text-sm" data-testid="patient-insurance-policy" />
                </FormField>
                <FormField label="Fecha de vencimiento" error={errors.insurance_expiry}>
                  <Input type="date" {...register('insurance_expiry')} className="text-sm" />
                </FormField>
              </TabsContent>
            </Tabs>

            <div className="flex justify-end gap-3 mt-6 pt-4 border-t">
              <Button type="button" variant="outline" onClick={() => setShowForm(false)} data-testid="patient-form-cancel">
                Cancelar
              </Button>
              <Button type="submit" className="bg-teal-600 hover:bg-teal-700" disabled={saving} data-testid="patient-form-save">
                {saving ? 'Guardando...' : editingPatient ? 'Actualizar' : 'Crear paciente'}
              </Button>
            </div>
          </form>
        </SheetContent>
      </Sheet>

      {/* Bulk Import Dialog */}
      <CsvImportDialog
        open={showImport}
        onOpenChange={setShowImport}
        catalog="patients"
        acceptXlsx
        headers={getAuthHeaders()}
        onSuccess={() => fetchPatients()}
      />
    </div>
  );
}
