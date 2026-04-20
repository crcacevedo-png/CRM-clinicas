import { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '../../context/AuthContext';
import { useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
import { Badge } from '../../components/ui/badge';
import { Switch } from '../../components/ui/switch';
import { Checkbox } from '../../components/ui/checkbox';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Separator } from '../../components/ui/separator';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui/table';
import { toast } from 'sonner';
import {
  Building2, Calendar, Link2, Unlink, RefreshCw, CheckCircle, Users,
  UserPlus, Edit, Upload, Clock, FileText, CreditCard, Shield, Save, Image
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const DAY_LABELS = { 0: 'Dom', 1: 'Lun', 2: 'Mar', 3: 'Mié', 4: 'Jue', 5: 'Vie', 6: 'Sáb' };
const SLOT_OPTIONS = [15, 20, 30, 45, 60];
const ROLE_LABELS = { clinic_admin: 'Administrador', doctor: 'Doctor', assistant: 'Asistente', receptionist: 'Recepcionista' };
const PLAN_LABELS = { free: 'Free', professional: 'Professional', enterprise: 'Enterprise' };

export default function ClinicSettingsPage() {
  const { user, getAuthHeaders } = useAuth();
  const [searchParams] = useSearchParams();
  const headers = getAuthHeaders();
  const logoRef = useRef(null);

  const [activeTab, setActiveTab] = useState('clinic');
  const [loading, setLoading] = useState(true);
  const [currentMemberId, setCurrentMemberId] = useState(null);

  // Clinic data
  const [clinic, setClinic] = useState({});
  const [clinicForm, setClinicForm] = useState({});
  const [savingClinic, setSavingClinic] = useState(false);
  const [uploadingLogo, setUploadingLogo] = useState(false);

  // Members
  const [members, setMembers] = useState([]);
  const [showInvite, setShowInvite] = useState(false);
  const [inviteForm, setInviteForm] = useState({ email: '', first_name: '', last_name: '', role: 'doctor', specialty: '' });
  const [inviting, setInviting] = useState(false);
  const [editMember, setEditMember] = useState(null);
  const [editMemberForm, setEditMemberForm] = useState({});

  // Google Calendar
  const [gcalStatus, setGcalStatus] = useState({ connected: false });
  const [calendars, setCalendars] = useState([]);
  const [selectedCalendar, setSelectedCalendar] = useState('primary');
  const [syncActive, setSyncActive] = useState(true);
  const [loadingCalendars, setLoadingCalendars] = useState(false);

  useEffect(() => {
    const success = searchParams.get('gcal_success');
    const error = searchParams.get('gcal_error');
    if (success === 'true') toast.success('Google Calendar conectado exitosamente');
    if (error) toast.error(`Error al conectar: ${error}`);
  }, [searchParams]);

  useEffect(() => {
    const load = async () => {
      try {
        const [clinicRes, gcalRes, configRes] = await Promise.all([
          axios.get(`${API}/clinic/settings`, { headers }),
          axios.get(`${API}/google-calendar/status`, { headers }).catch(() => ({ data: { connected: false } })),
          axios.get(`${API}/clinic/config`, { headers }).catch(() => ({ data: {} })),
        ]);
        const c = clinicRes.data;
        setClinic(c);
        if (configRes.data?.current_member?.id) setCurrentMemberId(configRes.data.current_member.id);
        setClinicForm({
          name: c.name || '', address: c.address || '', city: c.city || '', state: c.state || '',
          country: c.country || '', phone: c.phone || '', email: c.email || '', website: c.website || '',
          timezone: c.timezone || 'America/Guatemala',
          schedule_start: c.schedule_start?.substring(0, 5) || '08:00',
          schedule_end: c.schedule_end?.substring(0, 5) || '17:00',
          slot_duration: c.slot_duration || 30,
          working_days: c.working_days || [1, 2, 3, 4, 5],
          prescription_footer: c.prescription_footer || '',
          prescription_validity_days: c.prescription_validity_days || 30,
        });
        setGcalStatus(gcalRes.data);
        if (gcalRes.data.connected) {
          setSelectedCalendar(gcalRes.data.calendar_id || 'primary');
          fetchCalendars();
        }
      } catch {} finally { setLoading(false); }
    };
    load();
    fetchMembers();
  }, []);

  const fetchMembers = async () => {
    try {
      const res = await axios.get(`${API}/clinic/members`, { headers });
      setMembers(res.data || []);
    } catch {}
  };

  const fetchCalendars = async () => {
    setLoadingCalendars(true);
    try {
      const res = await axios.get(`${API}/google-calendar/calendars`, { headers });
      setCalendars(res.data || []);
    } catch {} finally { setLoadingCalendars(false); }
  };

  const saveClinic = async () => {
    setSavingClinic(true);
    try {
      await axios.put(`${API}/clinic/settings`, clinicForm, { headers });
      toast.success('Configuración guardada');
    } catch (err) { toast.error(err.response?.data?.detail || 'Error al guardar'); }
    finally { setSavingClinic(false); }
  };

  const handleLogoUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) { toast.error('Logo máximo 2MB'); return; }
    setUploadingLogo(true);
    try {
      const fd = new FormData(); fd.append('file', file);
      const res = await axios.post(`${API}/clinic/settings/logo`, fd, { headers: { ...headers, 'Content-Type': 'multipart/form-data' } });
      setClinic(prev => ({ ...prev, logo_url: res.data.logo_url }));
      toast.success('Logo actualizado');
    } catch { toast.error('Error al subir logo'); }
    finally { setUploadingLogo(false); if (logoRef.current) logoRef.current.value = ''; }
  };

  const handleInvite = async () => {
    if (!inviteForm.email || !inviteForm.first_name || !inviteForm.last_name) { toast.error('Complete todos los campos'); return; }
    setInviting(true);
    try {
      const res = await axios.post(`${API}/clinic/members/invite`, inviteForm, { headers });
      toast.success(res.data.temp_password ? `Miembro invitado. Contraseña temporal: ${res.data.temp_password}` : 'Miembro invitado');
      setShowInvite(false);
      setInviteForm({ email: '', first_name: '', last_name: '', role: 'doctor', specialty: '' });
      fetchMembers();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error al invitar'); }
    finally { setInviting(false); }
  };

  const handleToggleMember = async (memberId) => {
    try {
      const res = await axios.put(`${API}/clinic/members/${memberId}/toggle`, {}, { headers });
      toast.success(res.data.message);
      fetchMembers();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error'); }
  };

  const handleSaveMember = async () => {
    if (!editMember) return;
    try {
      await axios.put(`${API}/clinic/members/${editMember.id}`, editMemberForm, { headers });
      toast.success('Miembro actualizado');
      setEditMember(null);
      fetchMembers();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error'); }
  };

  const openEditMember = (m) => {
    setEditMember(m);
    setEditMemberForm({ first_name: m.first_name || '', last_name: m.last_name || '', specialty: m.specialty || '', license_number: m.license_number || '', phone: m.phone || '', role: m.role });
  };

  const connectGcal = async () => {
    try { const res = await axios.get(`${API}/google-calendar/auth-url`, { headers }); if (res.data.auth_url) window.location.href = res.data.auth_url; }
    catch { toast.error('Error'); }
  };

  const disconnectGcal = async () => {
    if (!window.confirm('¿Desconectar Google Calendar?')) return;
    try { await axios.delete(`${API}/google-calendar/disconnect`, { headers }); setGcalStatus({ connected: false }); setCalendars([]); toast.success('Desconectado'); }
    catch { toast.error('Error'); }
  };

  const updateGcalSettings = async (calId, active) => {
    try { await axios.put(`${API}/google-calendar/settings`, { calendar_id: calId, is_active: active }, { headers }); setSelectedCalendar(calId); setSyncActive(active); toast.success('Actualizado'); }
    catch { toast.error('Error'); }
  };

  const toggleDay = (day) => {
    setClinicForm(prev => {
      const days = prev.working_days || [];
      return { ...prev, working_days: days.includes(day) ? days.filter(d => d !== day) : [...days, day].sort() };
    });
  };

  const uf = (field, value) => setClinicForm(prev => ({ ...prev, [field]: value }));

  if (loading) return <div className="flex justify-center items-center h-96"><div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" /></div>;

  const usedStorage = 0; // placeholder
  const patientCount = 0; // placeholder

  return (
    <div className="p-6 lg:p-8 max-w-4xl" data-testid="clinic-settings-page">
      <h1 className="text-2xl font-bold text-slate-900 mb-1">Configuración</h1>
      <p className="text-sm text-slate-500 mb-5">Administración de la clínica</p>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="bg-slate-100 mb-4">
          <TabsTrigger value="clinic" data-testid="tab-clinic"><Building2 className="w-3.5 h-3.5 mr-1.5" />Clínica</TabsTrigger>
          <TabsTrigger value="members" data-testid="tab-members"><Users className="w-3.5 h-3.5 mr-1.5" />Equipo</TabsTrigger>
          <TabsTrigger value="prescriptions" data-testid="tab-prescriptions"><FileText className="w-3.5 h-3.5 mr-1.5" />Recetas</TabsTrigger>
          <TabsTrigger value="billing" data-testid="tab-billing"><CreditCard className="w-3.5 h-3.5 mr-1.5" />Plan</TabsTrigger>
          <TabsTrigger value="integrations" data-testid="tab-integrations"><Calendar className="w-3.5 h-3.5 mr-1.5" />Integraciones</TabsTrigger>
        </TabsList>

        {/* ===== CLINIC DATA ===== */}
        <TabsContent value="clinic">
          <div className="space-y-4">
            {/* Logo */}
            <Card className="border border-slate-200">
              <CardContent className="p-4">
                <div className="flex items-center gap-4">
                  <div className="w-20 h-20 rounded-lg border-2 border-dashed border-slate-200 flex items-center justify-center overflow-hidden bg-slate-50 shrink-0">
                    {clinic.logo_url ? <img src={clinic.logo_url} alt="Logo" className="w-full h-full object-contain" /> : <Image className="w-8 h-8 text-slate-300" />}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-slate-700">Logo de la clínica</p>
                    <p className="text-xs text-slate-400 mb-2">PNG, JPG. Máximo 2MB.</p>
                    <input type="file" ref={logoRef} onChange={handleLogoUpload} accept="image/*" className="hidden" />
                    <Button variant="outline" size="sm" onClick={() => logoRef.current?.click()} disabled={uploadingLogo} data-testid="upload-logo-btn">
                      <Upload className="w-3.5 h-3.5 mr-1" /> {uploadingLogo ? 'Subiendo...' : 'Cambiar logo'}
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Info */}
            <Card className="border border-slate-200">
              <CardHeader className="pb-2"><CardTitle className="text-sm font-semibold text-slate-700">Información general</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div><Label className="text-xs">Nombre *</Label><Input className="mt-1 text-sm" value={clinicForm.name} onChange={e => uf('name', e.target.value)} data-testid="clinic-name" /></div>
                  <div><Label className="text-xs">Email</Label><Input className="mt-1 text-sm" value={clinicForm.email} onChange={e => uf('email', e.target.value)} /></div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div><Label className="text-xs">Teléfono</Label><Input className="mt-1 text-sm" value={clinicForm.phone} onChange={e => uf('phone', e.target.value)} /></div>
                  <div><Label className="text-xs">Sitio web</Label><Input className="mt-1 text-sm" value={clinicForm.website} onChange={e => uf('website', e.target.value)} placeholder="https://" /></div>
                </div>
                <div><Label className="text-xs">Dirección</Label><Input className="mt-1 text-sm" value={clinicForm.address} onChange={e => uf('address', e.target.value)} /></div>
                <div className="grid grid-cols-3 gap-3">
                  <div><Label className="text-xs">Ciudad</Label><Input className="mt-1 text-sm" value={clinicForm.city} onChange={e => uf('city', e.target.value)} /></div>
                  <div><Label className="text-xs">Departamento</Label><Input className="mt-1 text-sm" value={clinicForm.state} onChange={e => uf('state', e.target.value)} /></div>
                  <div><Label className="text-xs">País</Label><Input className="mt-1 text-sm" value={clinicForm.country} onChange={e => uf('country', e.target.value)} /></div>
                </div>
                <div><Label className="text-xs">Zona horaria</Label><Input className="mt-1 text-sm" value={clinicForm.timezone} onChange={e => uf('timezone', e.target.value)} /></div>
              </CardContent>
            </Card>

            {/* Schedule */}
            <Card className="border border-slate-200">
              <CardHeader className="pb-2"><CardTitle className="text-sm font-semibold text-slate-700 flex items-center gap-2"><Clock className="w-4 h-4 text-teal-500" />Horario de atención</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                <div className="grid grid-cols-3 gap-3">
                  <div><Label className="text-xs">Hora inicio</Label><Input type="time" className="mt-1 text-sm" value={clinicForm.schedule_start} onChange={e => uf('schedule_start', e.target.value)} data-testid="schedule-start" /></div>
                  <div><Label className="text-xs">Hora fin</Label><Input type="time" className="mt-1 text-sm" value={clinicForm.schedule_end} onChange={e => uf('schedule_end', e.target.value)} data-testid="schedule-end" /></div>
                  <div>
                    <Label className="text-xs">Duración de cita</Label>
                    <Select value={String(clinicForm.slot_duration)} onValueChange={v => uf('slot_duration', parseInt(v))}>
                      <SelectTrigger className="mt-1 text-sm" data-testid="slot-duration"><SelectValue /></SelectTrigger>
                      <SelectContent>{SLOT_OPTIONS.map(m => <SelectItem key={m} value={String(m)}>{m} min</SelectItem>)}</SelectContent>
                    </Select>
                  </div>
                </div>
                <div>
                  <Label className="text-xs mb-2 block">Días laborales</Label>
                  <div className="flex gap-2">
                    {[1, 2, 3, 4, 5, 6, 0].map(d => (
                      <button key={d} type="button" onClick={() => toggleDay(d)}
                        className={`w-10 h-10 rounded-lg text-xs font-medium border transition-all ${(clinicForm.working_days || []).includes(d) ? 'bg-teal-600 text-white border-teal-600' : 'bg-white text-slate-500 border-slate-200 hover:border-teal-300'}`}
                        data-testid={`day-${d}`}>{DAY_LABELS[d]}</button>
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>

            <div className="flex justify-end">
              <Button className="bg-teal-600 hover:bg-teal-700" onClick={saveClinic} disabled={savingClinic} data-testid="save-clinic-btn">
                <Save className="w-4 h-4 mr-1.5" /> {savingClinic ? 'Guardando...' : 'Guardar configuración'}
              </Button>
            </div>
          </div>
        </TabsContent>

        {/* ===== MEMBERS ===== */}
        <TabsContent value="members">
          <Card className="border border-slate-200">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-semibold text-slate-700">Equipo ({members.length})</CardTitle>
                <Button size="sm" className="bg-teal-600 hover:bg-teal-700" onClick={() => setShowInvite(true)} data-testid="invite-member-btn">
                  <UserPlus className="w-3.5 h-3.5 mr-1" /> Invitar miembro
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow className="bg-slate-50/50">
                    <TableHead className="text-xs font-semibold">Nombre</TableHead>
                    <TableHead className="text-xs font-semibold">Email</TableHead>
                    <TableHead className="text-xs font-semibold">Rol</TableHead>
                    <TableHead className="text-xs font-semibold">Especialidad</TableHead>
                    <TableHead className="text-xs font-semibold text-center">Estado</TableHead>
                    <TableHead className="text-xs font-semibold text-right">Acciones</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {members.map(m => (
                    <TableRow key={m.id} data-testid={`member-row-${m.id}`}>
                      <TableCell className="text-sm font-medium">{m.first_name} {m.last_name}</TableCell>
                      <TableCell className="text-sm text-slate-500">{m.email}</TableCell>
                      <TableCell><Badge variant="outline" className="text-xs">{ROLE_LABELS[m.role] || m.role}</Badge></TableCell>
                      <TableCell className="text-sm text-slate-500">{m.specialty || '—'}</TableCell>
                      <TableCell className="text-center">
                        <Badge variant="outline" className={`text-xs ${m.is_active ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-red-50 text-red-600 border-red-200'}`}>
                          {m.is_active ? 'Activo' : 'Inactivo'}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center justify-end gap-1">
                          <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => openEditMember(m)}>Editar</Button>
                          <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => handleToggleMember(m.id)}>
                            {m.is_active ? 'Desactivar' : 'Activar'}
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          {/* Invite Dialog */}
          <Dialog open={showInvite} onOpenChange={setShowInvite}>
            <DialogContent className="max-w-md" data-testid="invite-dialog">
              <DialogHeader><DialogTitle>Invitar miembro</DialogTitle></DialogHeader>
              <div className="space-y-3 py-2">
                <div><Label className="text-xs">Email *</Label><Input className="mt-1 text-sm" value={inviteForm.email} onChange={e => setInviteForm(p => ({ ...p, email: e.target.value }))} data-testid="invite-email" /></div>
                <div className="grid grid-cols-2 gap-3">
                  <div><Label className="text-xs">Nombre *</Label><Input className="mt-1 text-sm" value={inviteForm.first_name} onChange={e => setInviteForm(p => ({ ...p, first_name: e.target.value }))} data-testid="invite-first-name" /></div>
                  <div><Label className="text-xs">Apellido *</Label><Input className="mt-1 text-sm" value={inviteForm.last_name} onChange={e => setInviteForm(p => ({ ...p, last_name: e.target.value }))} data-testid="invite-last-name" /></div>
                </div>
                <div><Label className="text-xs">Rol</Label>
                  <Select value={inviteForm.role} onValueChange={v => setInviteForm(p => ({ ...p, role: v }))}>
                    <SelectTrigger className="mt-1 text-sm" data-testid="invite-role"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="doctor">Doctor</SelectItem>
                      <SelectItem value="assistant">Asistente</SelectItem>
                      <SelectItem value="receptionist">Recepcionista</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div><Label className="text-xs">Especialidad</Label><Input className="mt-1 text-sm" value={inviteForm.specialty} onChange={e => setInviteForm(p => ({ ...p, specialty: e.target.value }))} /></div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setShowInvite(false)}>Cancelar</Button>
                <Button className="bg-teal-600 hover:bg-teal-700" onClick={handleInvite} disabled={inviting} data-testid="confirm-invite-btn">{inviting ? 'Invitando...' : 'Invitar'}</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          {/* Edit Member Dialog */}
          <Dialog open={!!editMember} onOpenChange={() => setEditMember(null)}>
            <DialogContent className="max-w-md" data-testid="edit-member-dialog">
              <DialogHeader><DialogTitle>Editar miembro</DialogTitle></DialogHeader>
              <div className="space-y-3 py-2">
                <div className="grid grid-cols-2 gap-3">
                  <div><Label className="text-xs">Nombre</Label><Input className="mt-1 text-sm" value={editMemberForm.first_name} onChange={e => setEditMemberForm(p => ({ ...p, first_name: e.target.value }))} /></div>
                  <div><Label className="text-xs">Apellido</Label><Input className="mt-1 text-sm" value={editMemberForm.last_name} onChange={e => setEditMemberForm(p => ({ ...p, last_name: e.target.value }))} /></div>
                </div>
                <div><Label className="text-xs">Rol</Label>
                  {editMember?.id === currentMemberId ? (
                    <p className="text-xs text-amber-600 mt-1">No puedes cambiar tu propio rol</p>
                  ) : (
                    <Select value={editMemberForm.role} onValueChange={v => setEditMemberForm(p => ({ ...p, role: v }))}>
                      <SelectTrigger className="mt-1 text-sm"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="clinic_admin">Administrador</SelectItem>
                        <SelectItem value="doctor">Doctor</SelectItem>
                        <SelectItem value="assistant">Asistente</SelectItem>
                        <SelectItem value="receptionist">Recepcionista</SelectItem>
                      </SelectContent>
                    </Select>
                  )}
                </div>
                <div><Label className="text-xs">Especialidad</Label><Input className="mt-1 text-sm" value={editMemberForm.specialty} onChange={e => setEditMemberForm(p => ({ ...p, specialty: e.target.value }))} /></div>
                <div><Label className="text-xs">No. Colegiado</Label><Input className="mt-1 text-sm" value={editMemberForm.license_number} onChange={e => setEditMemberForm(p => ({ ...p, license_number: e.target.value }))} data-testid="edit-license" /></div>
                <div><Label className="text-xs">Teléfono</Label><Input className="mt-1 text-sm" value={editMemberForm.phone} onChange={e => setEditMemberForm(p => ({ ...p, phone: e.target.value }))} /></div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setEditMember(null)}>Cancelar</Button>
                <Button className="bg-teal-600 hover:bg-teal-700" onClick={handleSaveMember} data-testid="save-member-btn">Guardar</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </TabsContent>

        {/* ===== PRESCRIPTIONS ===== */}
        <TabsContent value="prescriptions">
          <Card className="border border-slate-200">
            <CardHeader className="pb-2"><CardTitle className="text-sm font-semibold text-slate-700 flex items-center gap-2"><FileText className="w-4 h-4 text-teal-500" />Personalización de recetas</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label className="text-xs">Texto del footer de la receta</Label>
                <Textarea className="mt-1 text-sm min-h-[80px]" value={clinicForm.prescription_footer} onChange={e => uf('prescription_footer', e.target.value)} placeholder="Texto que aparece al final de cada receta..." data-testid="rx-footer" />
              </div>
              <div>
                <Label className="text-xs">Validez de la receta (días)</Label>
                <Input type="number" className="mt-1 text-sm w-32" value={clinicForm.prescription_validity_days} onChange={e => uf('prescription_validity_days', parseInt(e.target.value) || 30)} data-testid="rx-validity" />
              </div>
              <Separator />
              <p className="text-xs text-slate-400">Vista previa del footer:</p>
              <div className="p-3 bg-slate-50 rounded-md border border-slate-100">
                <p className="text-xs text-slate-600 italic">{clinicForm.prescription_footer || '(Sin texto configurado)'}</p>
              </div>
              <div className="flex justify-end">
                <Button className="bg-teal-600 hover:bg-teal-700" onClick={saveClinic} disabled={savingClinic} data-testid="save-rx-btn">
                  <Save className="w-4 h-4 mr-1.5" /> Guardar
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ===== BILLING ===== */}
        <TabsContent value="billing">
          <div className="space-y-4">
            <Card className="border border-slate-200">
              <CardHeader className="pb-2"><CardTitle className="text-sm font-semibold text-slate-700 flex items-center gap-2"><CreditCard className="w-4 h-4 text-teal-500" />Plan actual</CardTitle></CardHeader>
              <CardContent>
                <div className="flex items-center justify-between p-4 bg-teal-50 rounded-lg border border-teal-200 mb-4">
                  <div>
                    <Badge className="bg-teal-600 text-white text-sm mb-1">{PLAN_LABELS[clinic.plan] || clinic.plan}</Badge>
                    <p className="text-xs text-teal-600 mt-1">
                      {clinic.plan_expires_at ? `Expira: ${new Date(clinic.plan_expires_at).toLocaleDateString('es-GT')}` : 'Sin fecha de expiración'}
                    </p>
                  </div>
                  <Button variant="outline" disabled className="text-xs opacity-60">Cambiar plan (próximamente)</Button>
                </div>

                <div className="grid grid-cols-3 gap-4">
                  <div className="p-3 bg-slate-50 rounded-lg border border-slate-100 text-center">
                    <p className="text-xs text-slate-500">Usuarios</p>
                    <p className="text-lg font-bold text-slate-800">{members.filter(m => m.is_active).length}<span className="text-sm font-normal text-slate-400">/{clinic.max_users || '∞'}</span></p>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-lg border border-slate-100 text-center">
                    <p className="text-xs text-slate-500">Pacientes</p>
                    <p className="text-lg font-bold text-slate-800">—<span className="text-sm font-normal text-slate-400">/{clinic.max_patients || '∞'}</span></p>
                  </div>
                  <div className="p-3 bg-slate-50 rounded-lg border border-slate-100 text-center">
                    <p className="text-xs text-slate-500">Almacenamiento</p>
                    <p className="text-lg font-bold text-slate-800">—<span className="text-sm font-normal text-slate-400">/{clinic.max_storage_mb ? `${(clinic.max_storage_mb / 1024).toFixed(0)}GB` : '∞'}</span></p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="border border-dashed border-slate-300">
              <CardContent className="p-8 text-center">
                <Shield className="w-10 h-10 text-slate-300 mx-auto mb-2" />
                <p className="text-sm text-slate-500 font-medium">Integración de pagos</p>
                <p className="text-xs text-slate-400 mt-1">Stripe / dLocal — Próximamente</p>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* ===== INTEGRATIONS (Google Calendar) ===== */}
        <TabsContent value="integrations">
          <Card className="border border-slate-200" data-testid="gcal-card">
            <CardHeader className="pb-2"><CardTitle className="text-sm font-semibold text-slate-700 flex items-center gap-2"><Calendar className="w-4 h-4 text-teal-500" />Google Calendar</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <p className="text-xs text-slate-500">Sincroniza citas del CRM con Google Calendar automáticamente.</p>
              {!gcalStatus.connected ? (
                <div className="p-4 border-2 border-dashed border-slate-200 rounded-lg text-center">
                  <Calendar className="w-10 h-10 text-slate-300 mx-auto mb-2" />
                  <p className="text-sm text-slate-500 mb-3">No conectado</p>
                  <Button className="bg-teal-600 hover:bg-teal-700" onClick={connectGcal} data-testid="connect-gcal-btn"><Link2 className="w-4 h-4 mr-1.5" />Conectar Google Calendar</Button>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="flex items-center justify-between p-3 bg-emerald-50 rounded-lg border border-emerald-200">
                    <div className="flex items-center gap-2"><CheckCircle className="w-4 h-4 text-emerald-600" /><span className="text-sm font-medium text-emerald-700">Conectado</span></div>
                    <Button variant="outline" size="sm" className="text-xs text-red-600 border-red-200 hover:bg-red-50" onClick={disconnectGcal} data-testid="disconnect-gcal-btn"><Unlink className="w-3.5 h-3.5 mr-1" />Desconectar</Button>
                  </div>
                  <Separator />
                  <div className="flex items-center justify-between">
                    <div><p className="text-sm font-medium text-slate-700">Sincronización activa</p><p className="text-xs text-slate-400">Nuevas citas se sincronizan automáticamente</p></div>
                    <Switch checked={syncActive} onCheckedChange={v => updateGcalSettings(selectedCalendar, v)} data-testid="sync-toggle" />
                  </div>
                  <Separator />
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-sm font-medium text-slate-700">Calendario</p>
                      <Button variant="ghost" size="sm" onClick={fetchCalendars} disabled={loadingCalendars} className="text-xs"><RefreshCw className={`w-3.5 h-3.5 mr-1 ${loadingCalendars ? 'animate-spin' : ''}`} />Actualizar</Button>
                    </div>
                    {calendars.length > 0 ? (
                      <Select value={selectedCalendar} onValueChange={v => updateGcalSettings(v, syncActive)}>
                        <SelectTrigger className="text-sm" data-testid="calendar-select"><SelectValue /></SelectTrigger>
                        <SelectContent>{calendars.map(c => <SelectItem key={c.id} value={c.id}>{c.summary}{c.primary ? ' (Principal)' : ''}</SelectItem>)}</SelectContent>
                      </Select>
                    ) : <p className="text-xs text-slate-400">Usando calendario principal.</p>}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
