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
  UserPlus, Edit, Upload, Clock, FileText, CreditCard, Shield, Save, Image,
  Download, Database, Loader2, X, FileSpreadsheet
} from 'lucide-react';
import AuditLogTable from '../../components/AuditLogTable';
import RolesTab from './RolesTab';
import PasswordStrengthMeter, { passwordMeetsPolicy, MIN_LENGTH } from '../../components/PasswordStrengthMeter';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const DAY_LABELS = { 0: 'Dom', 1: 'Lun', 2: 'Mar', 3: 'Mié', 4: 'Jue', 5: 'Vie', 6: 'Sáb' };
// ISO weekday labels used by the per-day schedule editor (matches backend isoweekday: 1=Mon..7=Sun)
const ISO_DAYS = [
  { iso: 1, label: 'Lunes' },
  { iso: 2, label: 'Martes' },
  { iso: 3, label: 'Miércoles' },
  { iso: 4, label: 'Jueves' },
  { iso: 5, label: 'Viernes' },
  { iso: 6, label: 'Sábado' },
  { iso: 7, label: 'Domingo' },
];
const SLOT_OPTIONS = [15, 20, 30, 45, 60];
const ROLE_LABELS = { clinic_admin: 'Administrador', doctor: 'Doctor', assistant: 'Asistente', receptionist: 'Recepcionista' };
const PLAN_LABELS = { free: 'Free', professional: 'Professional', enterprise: 'Enterprise' };
const EXCEL_SHEETS = [
  { key: 'patients', label: 'Pacientes', dated: true },
  { key: 'medical_records', label: 'Evaluaciones Médicas', dated: true },
  { key: 'prescriptions', label: 'Recetas (+ medicamentos)', dated: true },
  { key: 'lab_orders', label: 'Laboratorio (+ estudios)', dated: true },
  { key: 'appointments', label: 'Citas', dated: true },
  { key: 'members', label: 'Equipo', dated: false },
  { key: 'branches', label: 'Sucursales', dated: false },
  { key: 'clinic', label: 'Clínica', dated: false },
];

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
  const [inviteForm, setInviteForm] = useState({ email: '', first_name: '', last_name: '', role: 'doctor', specialty: '', password: '' });
  const [inviting, setInviting] = useState(false);
  const [editMember, setEditMember] = useState(null);
  const [editMemberForm, setEditMemberForm] = useState({});
  const [editPassword, setEditPassword] = useState('');
  const [savingPassword, setSavingPassword] = useState(false);

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
          working_hours: c.working_hours || null,
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
    if (inviteForm.password && !passwordMeetsPolicy(inviteForm.password, { email: inviteForm.email, name: `${inviteForm.first_name} ${inviteForm.last_name}` })) {
      toast.error(`La contraseña no cumple la política (mín. ${MIN_LENGTH} caracteres, 3 categorías, sin datos personales)`);
      return;
    }
    setInviting(true);
    try {
      const payload = { ...inviteForm };
      if (!payload.password) delete payload.password; // omit empty so backend auto-generates
      const res = await axios.post(`${API}/clinic/members/invite`, payload, { headers });
      const wasCustom = !!inviteForm.password;
      toast.success(
        wasCustom
          ? 'Miembro invitado con la contraseña proporcionada'
          : (res.data.temp_password ? `Miembro invitado. Contraseña temporal: ${res.data.temp_password}` : 'Miembro invitado')
      );
      setShowInvite(false);
      setInviteForm({ email: '', first_name: '', last_name: '', role: 'doctor', specialty: '', password: '' });
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
    setEditPassword('');
  };

  const handleResetPassword = async () => {
    if (!editMember) return;
    if (!editPassword || !passwordMeetsPolicy(editPassword, { email: editMember?.email, name: `${editMemberForm.first_name || ''} ${editMemberForm.last_name || ''}` })) {
      toast.error(`La contraseña no cumple la política (mín. ${MIN_LENGTH} caracteres, 3 categorías, sin datos personales)`);
      return;
    }
    setSavingPassword(true);
    try {
      await axios.put(`${API}/clinic/members/${editMember.id}/password`, { password: editPassword }, { headers });
      toast.success('Contraseña actualizada');
      setEditPassword('');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al actualizar contraseña');
    } finally {
      setSavingPassword(false);
    }
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

  // ----- Per-day schedule helpers (supports split schedules: multiple blocks per day) -----
  const isPerDayMode = !!clinicForm.working_hours;

  // Internal canonical shape: working_hours[iso] = [{start,end}, ...] (array of blocks)
  // Legacy single-block dict {start,end} is auto-promoted to a 1-element array on read.
  const getDayBlocks = (iso) => {
    const v = (clinicForm.working_hours || {})[String(iso)];
    if (!v) return [];
    if (Array.isArray(v)) return v;
    if (v && typeof v === 'object' && v.start && v.end) return [v];
    return [];
  };

  const setDayBlocks = (iso, blocks) => {
    setClinicForm(prev => {
      const wh = { ...(prev.working_hours || {}) };
      const key = String(iso);
      if (!blocks || blocks.length === 0) delete wh[key];
      else wh[key] = blocks;
      return { ...prev, working_hours: wh };
    });
  };

  const enablePerDay = () => {
    const start = clinicForm.schedule_start || '08:00';
    const end = clinicForm.schedule_end || '17:00';
    const legacyToIso = (d) => (d === 0 ? 7 : d);
    const openIso = new Set((clinicForm.working_days || [1,2,3,4,5]).map(legacyToIso));
    const wh = {};
    [1,2,3,4,5,6,7].forEach(iso => {
      if (openIso.has(iso)) wh[String(iso)] = [{ start, end }];
    });
    setClinicForm(prev => ({ ...prev, working_hours: wh }));
  };

  const disablePerDay = () => {
    setClinicForm(prev => ({ ...prev, working_hours: null }));
  };

  const updateBlock = (iso, idx, field, value) => {
    const blocks = getDayBlocks(iso).slice();
    blocks[idx] = { ...blocks[idx], [field]: value };
    setDayBlocks(iso, blocks);
  };

  const addBlock = (iso) => {
    const blocks = getDayBlocks(iso).slice();
    // Pick a sensible default for the next block: if the last block ends at e.g. 12:00, start there +2h
    const last = blocks[blocks.length - 1];
    const defStart = last ? last.end : '14:00';
    const defEnd = last ? '18:00' : '18:00';
    blocks.push({ start: defStart, end: defEnd });
    setDayBlocks(iso, blocks);
  };

  const removeBlock = (iso, idx) => {
    const blocks = getDayBlocks(iso).slice();
    blocks.splice(idx, 1);
    setDayBlocks(iso, blocks);
  };

  const toggleDayOpen = (iso) => {
    const blocks = getDayBlocks(iso);
    if (blocks.length > 0) {
      setDayBlocks(iso, []); // close
    } else {
      setDayBlocks(iso, [{ start: '08:00', end: '17:00' }]); // open with default
    }
  };

  const uf = (field, value) => setClinicForm(prev => ({ ...prev, [field]: value }));

  // Derived: is current member a clinic_admin?
  const currentMember = members.find(m => m.id === currentMemberId);
  const isClinicAdmin = currentMember?.role === 'clinic_admin';

  const [downloadingExport, setDownloadingExport] = useState(false);
  const [downloadingExcel, setDownloadingExcel] = useState(false);
  const [excelDialogOpen, setExcelDialogOpen] = useState(false);
  const [excelStart, setExcelStart] = useState('');
  const [excelEnd, setExcelEnd] = useState('');
  const [excelSheets, setExcelSheets] = useState(EXCEL_SHEETS.map(s => s.key));

  const toggleExcelSheet = (key) => {
    setExcelSheets(prev => prev.includes(key) ? prev.filter(k => k !== key) : [...prev, key]);
  };

  const downloadExcelExport = async () => {
    if (excelSheets.length === 0) { toast.error('Selecciona al menos una hoja para exportar'); return; }
    if (excelStart && excelEnd && excelStart > excelEnd) { toast.error('La fecha inicial no puede ser mayor que la final'); return; }
    setDownloadingExcel(true);
    try {
      const params = new URLSearchParams();
      if (excelStart) params.append('start_date', excelStart);
      if (excelEnd) params.append('end_date', excelEnd);
      excelSheets.forEach(s => params.append('sheets', s));
      const res = await axios.get(`${API}/clinic/export/excel?${params.toString()}`, { headers, responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a');
      a.href = url;
      const ts = new Date().toISOString().slice(0, 10);
      a.download = `base_datos_${ts}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success('Base de datos descargada en Excel');
      setExcelDialogOpen(false);
    } catch (e) {
      const msg = e?.response?.status === 403
        ? 'Solo el administrador de clínica puede exportar datos'
        : 'Error al generar el Excel';
      toast.error(msg);
    } finally {
      setDownloadingExcel(false);
    }
  };

  const downloadFullExport = async () => {
    if (!window.confirm('¿Descargar export completo de la clínica? Puede tardar varios segundos según el volumen de datos.')) return;
    setDownloadingExport(true);
    try {
      // Kick off a background job
      const start = await axios.post(`${API}/clinic/export/full`, {}, { headers });
      const jobId = start.data.job_id;
      toast.success('Export en curso. Se descargará automáticamente cuando termine.');

      // Poll status every 3s, up to 10 minutes
      let done = false;
      let job = null;
      const maxTicks = 200;
      for (let i = 0; i < maxTicks; i++) {
        await new Promise(r => setTimeout(r, 3000));
        const st = await axios.get(`${API}/clinic/export/jobs/${jobId}`, { headers });
        job = st.data;
        if (job.status === 'done') { done = true; break; }
        if (job.status === 'failed') break;
      }
      if (!done) {
        if (job?.status === 'failed') {
          toast.error(`Export falló: ${job.error || 'error desconocido'}`);
        } else {
          toast.error('El export tardó más de 10 minutos. Revísalo en la sección Datos.');
        }
        return;
      }

      // Download via signed URL
      const a = document.createElement('a');
      a.href = job.signed_url;
      const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
      a.download = `clinic_export_${ts}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      const sizeMb = ((job.file_size || 0) / 1024 / 1024).toFixed(1);
      toast.success(`Export descargado (${sizeMb} MB)`);
    } catch (e) {
      const msg = e?.response?.status === 403
        ? 'Solo el administrador de clínica puede exportar datos'
        : 'Error al generar export';
      toast.error(msg);
    } finally {
      setDownloadingExport(false);
    }
  };

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
          {isClinicAdmin && (
            <TabsTrigger value="roles" data-testid="tab-roles"><Shield className="w-3.5 h-3.5 mr-1.5" />Roles</TabsTrigger>
          )}
          {isClinicAdmin && (
            <TabsTrigger value="data" data-testid="tab-data"><Database className="w-3.5 h-3.5 mr-1.5" />Datos</TabsTrigger>
          )}
          {isClinicAdmin && (
            <TabsTrigger value="audit" data-testid="tab-audit"><Shield className="w-3.5 h-3.5 mr-1.5" />Bitácora</TabsTrigger>
          )}
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
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between gap-3">
                  <CardTitle className="text-sm font-semibold text-slate-700 flex items-center gap-2"><Clock className="w-4 h-4 text-teal-500" />Horario de atención</CardTitle>
                  <div className="flex items-center gap-2 text-xs">
                    <span className={!isPerDayMode ? 'text-teal-600 font-medium' : 'text-slate-400'}>Mismo horario</span>
                    <button
                      type="button"
                      onClick={() => isPerDayMode ? disablePerDay() : enablePerDay()}
                      className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${isPerDayMode ? 'bg-teal-600' : 'bg-slate-300'}`}
                      data-testid="toggle-per-day-schedule"
                    >
                      <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${isPerDayMode ? 'translate-x-5' : 'translate-x-1'}`} />
                    </button>
                    <span className={isPerDayMode ? 'text-teal-600 font-medium' : 'text-slate-400'}>Por día</span>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                {!isPerDayMode ? (
                  <>
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
                  </>
                ) : (
                  <>
                    <div className="grid grid-cols-1 gap-3">
                      <div className="max-w-[200px]">
                        <Label className="text-xs">Duración de cita</Label>
                        <Select value={String(clinicForm.slot_duration)} onValueChange={v => uf('slot_duration', parseInt(v))}>
                          <SelectTrigger className="mt-1 text-sm" data-testid="slot-duration-perday"><SelectValue /></SelectTrigger>
                          <SelectContent>{SLOT_OPTIONS.map(m => <SelectItem key={m} value={String(m)}>{m} min</SelectItem>)}</SelectContent>
                        </Select>
                      </div>
                    </div>
                    <div className="space-y-2 pt-2 border-t border-slate-200">
                      <div className="flex items-center justify-between">
                        <Label className="text-xs text-slate-500">Configuración por día</Label>
                        <span className="text-[10px] text-slate-400">Pulsa <span className="font-mono">+</span> para añadir un horario partido (ej. mañana + tarde)</span>
                      </div>
                      {ISO_DAYS.map(({ iso, label }) => {
                        const blocks = getDayBlocks(iso);
                        const isOpen = blocks.length > 0;
                        return (
                          <div key={iso} className="flex items-start gap-3 py-1" data-testid={`day-row-${iso}`}>
                            <button
                              type="button"
                              onClick={() => toggleDayOpen(iso)}
                              className={`w-24 px-3 py-1.5 mt-1 rounded-lg text-xs font-medium border transition-all flex-shrink-0 ${isOpen ? 'bg-teal-600 text-white border-teal-600' : 'bg-white text-slate-400 border-slate-200 hover:border-teal-300'}`}
                              data-testid={`day-toggle-${iso}`}
                            >
                              {label}
                            </button>
                            {isOpen ? (
                              <div className="flex-1 space-y-1.5">
                                {blocks.map((b, idx) => (
                                  <div key={idx} className="flex items-center gap-2" data-testid={`day-${iso}-block-${idx}`}>
                                    <Input
                                      type="time"
                                      className="text-sm w-28"
                                      value={b.start || '08:00'}
                                      onChange={e => updateBlock(iso, idx, 'start', e.target.value)}
                                      data-testid={`day-start-${iso}-${idx}`}
                                    />
                                    <span className="text-slate-400 text-xs">a</span>
                                    <Input
                                      type="time"
                                      className="text-sm w-28"
                                      value={b.end || '17:00'}
                                      onChange={e => updateBlock(iso, idx, 'end', e.target.value)}
                                      data-testid={`day-end-${iso}-${idx}`}
                                    />
                                    {blocks.length > 1 && (
                                      <button
                                        type="button"
                                        onClick={() => removeBlock(iso, idx)}
                                        className="ml-1 text-slate-400 hover:text-rose-500 transition-colors"
                                        title="Eliminar este bloque"
                                        data-testid={`day-${iso}-remove-${idx}`}
                                      >
                                        <X className="w-3.5 h-3.5" />
                                      </button>
                                    )}
                                    {idx === blocks.length - 1 && (
                                      <button
                                        type="button"
                                        onClick={() => addBlock(iso)}
                                        className="ml-1 text-teal-600 hover:text-teal-700 text-xs font-semibold border border-teal-200 rounded px-1.5 py-0.5 hover:bg-teal-50 transition-colors"
                                        title="Añadir bloque (horario partido)"
                                        data-testid={`day-${iso}-add`}
                                      >
                                        + bloque
                                      </button>
                                    )}
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <span className="text-xs text-slate-400 italic mt-2">Cerrado</span>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </>
                )}
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
                <div>
                  <Label className="text-xs">Contraseña <span className="text-slate-400">(opcional, mín. {MIN_LENGTH} caracteres)</span></Label>
                  <Input
                    type="text"
                    className="mt-1 text-sm font-mono"
                    placeholder="Dejar vacío para generar una contraseña temporal"
                    value={inviteForm.password}
                    onChange={e => setInviteForm(p => ({ ...p, password: e.target.value }))}
                    autoComplete="new-password"
                    data-testid="invite-password"
                  />
                  <PasswordStrengthMeter
                    password={inviteForm.password}
                    email={inviteForm.email}
                    name={`${inviteForm.first_name || ''} ${inviteForm.last_name || ''}`}
                  />
                  <p className="text-[11px] text-slate-400 mt-1">Si la dejas vacía, el sistema generará una contraseña temporal y te la mostrará al confirmar.</p>
                </div>
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
                {editMember?.id !== currentMemberId && (
                  <div className="border-t border-slate-200 pt-3 mt-2">
                    <Label className="text-xs font-semibold text-slate-700">Cambiar contraseña</Label>
                    <p className="text-[11px] text-slate-400 mb-2">Define una nueva contraseña para este usuario (mín. {MIN_LENGTH} caracteres). Útil si el miembro la olvidó.</p>
                    <div className="flex items-center gap-2">
                      <Input
                        type="text"
                        className="text-sm font-mono"
                        placeholder="Nueva contraseña…"
                        value={editPassword}
                        onChange={e => setEditPassword(e.target.value)}
                        autoComplete="new-password"
                        data-testid="edit-password-input"
                      />
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleResetPassword}
                        disabled={savingPassword || !editPassword}
                        data-testid="edit-password-save-btn"
                      >
                        {savingPassword ? 'Guardando…' : 'Aplicar'}
                      </Button>
                    </div>
                    <PasswordStrengthMeter
                      password={editPassword}
                      email={editMember?.email}
                      name={`${editMemberForm.first_name || ''} ${editMemberForm.last_name || ''}`}
                    />
                  </div>
                )}
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

        {/* ===== DATA EXPORT (clinic_admin only) ===== */}
        {isClinicAdmin && (
          <TabsContent value="data">
            <div className="space-y-4">
            <Card className="border border-slate-200" data-testid="excel-export-card">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                  <FileSpreadsheet className="w-4 h-4 text-emerald-600" />Descargar base de datos (Excel)
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 space-y-2">
                  <p className="text-sm text-slate-700">
                    Descarga un archivo <span className="font-semibold">Excel (.xlsx)</span> con una hoja por cada conjunto de datos:
                  </p>
                  <ul className="text-xs text-slate-600 list-disc pl-5 space-y-0.5">
                    <li><span className="font-medium">Pacientes</span> — todas las variables de cada paciente.</li>
                    <li><span className="font-medium">Evaluaciones Médicas</span> — historia clínica / consultas completas.</li>
                    <li><span className="font-medium">Recetas</span> y sus medicamentos.</li>
                    <li><span className="font-medium">Laboratorio</span> y sus estudios.</li>
                    <li><span className="font-medium">Datos generales</span> — citas, equipo, sucursales y clínica.</li>
                  </ul>
                  <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1 mt-2">
                    <Shield className="w-3 h-3 inline mr-1" />
                    Contiene información médica sensible. Guárdalo en un lugar seguro.
                  </p>
                </div>
                <Button
                  onClick={() => setExcelDialogOpen(true)}
                  disabled={downloadingExcel}
                  className="bg-emerald-600 hover:bg-emerald-700"
                  data-testid="download-excel-export-btn"
                >
                  {downloadingExcel ? (
                    <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Generando Excel…</>
                  ) : (
                    <><FileSpreadsheet className="w-4 h-4 mr-2" />Exportar a Excel…</>
                  )}
                </Button>
              </CardContent>
            </Card>

            <Dialog open={excelDialogOpen} onOpenChange={setExcelDialogOpen}>
              <DialogContent className="max-w-lg" data-testid="excel-export-dialog">
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-2">
                    <FileSpreadsheet className="w-4 h-4 text-emerald-600" />Exportar base de datos a Excel
                  </DialogTitle>
                </DialogHeader>
                <div className="space-y-5 py-1">
                  <div className="space-y-2">
                    <Label className="text-xs font-semibold text-slate-600">Rango de fechas (opcional)</Label>
                    <p className="text-xs text-slate-500">
                      Filtra las hojas con fecha por su fecha de creación. Déjalo vacío para exportar todo el historial.
                    </p>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <Label htmlFor="excel-start" className="text-xs text-slate-500">Desde</Label>
                        <Input
                          id="excel-start" type="date" value={excelStart}
                          onChange={(e) => setExcelStart(e.target.value)}
                          data-testid="excel-start-date"
                        />
                      </div>
                      <div>
                        <Label htmlFor="excel-end" className="text-xs text-slate-500">Hasta</Label>
                        <Input
                          id="excel-end" type="date" value={excelEnd}
                          onChange={(e) => setExcelEnd(e.target.value)}
                          data-testid="excel-end-date"
                        />
                      </div>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label className="text-xs font-semibold text-slate-600">Hojas a incluir</Label>
                      <div className="flex gap-2">
                        <button
                          type="button"
                          className="text-xs text-emerald-700 hover:underline"
                          onClick={() => setExcelSheets(EXCEL_SHEETS.map(s => s.key))}
                          data-testid="excel-select-all"
                        >Todas</button>
                        <span className="text-slate-300">·</span>
                        <button
                          type="button"
                          className="text-xs text-slate-500 hover:underline"
                          onClick={() => setExcelSheets([])}
                          data-testid="excel-select-none"
                        >Ninguna</button>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      {EXCEL_SHEETS.map((s) => (
                        <label
                          key={s.key}
                          className="flex items-center gap-2 rounded-md border border-slate-200 px-3 py-2 cursor-pointer hover:bg-slate-50"
                          data-testid={`excel-sheet-${s.key}`}
                        >
                          <Checkbox
                            checked={excelSheets.includes(s.key)}
                            onCheckedChange={() => toggleExcelSheet(s.key)}
                          />
                          <span className="text-sm text-slate-700 flex-1">{s.label}</span>
                          {!s.dated && (excelStart || excelEnd) && (
                            <span className="text-[10px] text-slate-400" title="Esta hoja no se filtra por fecha">completa</span>
                          )}
                        </label>
                      ))}
                    </div>
                    <p className="text-[11px] text-slate-400">
                      Equipo, Sucursales y Clínica se incluyen completas (no dependen de fechas).
                    </p>
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setExcelDialogOpen(false)} data-testid="excel-cancel-btn">
                    Cancelar
                  </Button>
                  <Button
                    onClick={downloadExcelExport}
                    disabled={downloadingExcel || excelSheets.length === 0}
                    className="bg-emerald-600 hover:bg-emerald-700"
                    data-testid="excel-confirm-download-btn"
                  >
                    {downloadingExcel ? (
                      <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Generando…</>
                    ) : (
                      <><Download className="w-4 h-4 mr-2" />Descargar Excel</>
                    )}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
            <Card className="border border-slate-200" data-testid="data-export-card">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                  <Database className="w-4 h-4 text-teal-500" />Export completo de datos
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 space-y-2">
                  <p className="text-sm text-slate-700">
                    Descarga un archivo <span className="font-semibold">ZIP</span> con toda la información de tu clínica:
                  </p>
                  <ul className="text-xs text-slate-600 list-disc pl-5 space-y-0.5">
                    <li>Un archivo <code className="bg-white px-1 rounded">JSON</code> por cada tabla (pacientes, citas, consultas, recetas, ventas, inventario, contabilidad, etc.).</li>
                    <li>Todos los archivos adjuntos de pacientes (estudios de laboratorio, recetas digitalizadas) bajo <code className="bg-white px-1 rounded">files/</code>.</li>
                    <li><code className="bg-white px-1 rounded">manifest.json</code> con metadata y conteos de filas.</li>
                  </ul>
                  <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1 mt-2">
                    <Shield className="w-3 h-3 inline mr-1" />
                    El archivo contiene información médica sensible. Guárdalo en un lugar seguro y cifrado.
                  </p>
                </div>
                <Button
                  onClick={downloadFullExport}
                  disabled={downloadingExport}
                  className="bg-teal-600 hover:bg-teal-700"
                  data-testid="download-full-export-btn"
                >
                  {downloadingExport ? (
                    <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Generando export…</>
                  ) : (
                    <><Download className="w-4 h-4 mr-2" />Descargar export (ZIP)</>
                  )}
                </Button>
              </CardContent>
            </Card>
            </div>
          </TabsContent>
        )}

        {isClinicAdmin && (
          <TabsContent value="roles">
            <RolesTab />
          </TabsContent>
        )}

        {isClinicAdmin && (
          <TabsContent value="audit">
            <AuditLogTable scope="clinic" headers={headers} />
          </TabsContent>
        )}
      </Tabs>
    </div>
  );
}
