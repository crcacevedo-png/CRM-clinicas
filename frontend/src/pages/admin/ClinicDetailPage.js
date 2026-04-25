import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../../context/AuthContext';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Switch } from '../../components/ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';
import { 
  ArrowLeft, 
  Building2, 
  Users, 
  UserCheck,
  Calendar,
  FileText,
  Plus,
  RefreshCw,
  Copy,
  Check,
  Edit2,
  Save
} from 'lucide-react';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const PLANS = [
  { value: 'free', label: 'Free' },
  { value: 'professional', label: 'Professional' },
  { value: 'enterprise', label: 'Enterprise' },
];

const ROLES = [
  { value: 'clinic_admin', label: 'Administrador' },
  { value: 'doctor', label: 'Doctor' },
  { value: 'nurse', label: 'Enfermero/a' },
  { value: 'receptionist', label: 'Recepcionista' },
  { value: 'staff', label: 'Staff' },
];

export default function ClinicDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { getAuthHeaders } = useAuth();
  
  const [clinic, setClinic] = useState(null);
  const [members, setMembers] = useState([]);
  const [stats, setStats] = useState({});
  const [activity, setActivity] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [showMemberModal, setShowMemberModal] = useState(false);
  const [showCredentials, setShowCredentials] = useState(false);
  const [credentials, setCredentials] = useState(null);
  const [copied, setCopied] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [clinicFeatures, setClinicFeatures] = useState([]);
  const [clinicPlan, setClinicPlan] = useState('');
  const [allPlans, setAllPlans] = useState([]);

  const [editData, setEditData] = useState({});
  const [memberForm, setMemberForm] = useState({
    name: '', lastname: '', email: '', phone: '', password: '', role: 'staff'
  });

  useEffect(() => {
    fetchClinicDetail();
    fetchClinicFeatures();
    fetchAllPlans();
  }, [id]);

  const fetchClinicDetail = async () => {
    try {
      const response = await axios.get(`${API}/admin/clinics/${id}`, {
        headers: getAuthHeaders()
      });
      setClinic(response.data.clinic);
      setMembers(response.data.members);
      setStats(response.data.stats);
      setActivity(response.data.activity);
      setEditData(response.data.clinic);
    } catch (error) {
      console.error('Fetch clinic error:', error);
      toast.error('Error al cargar clínica');
    } finally {
      setLoading(false);
    }
  };

  const fetchClinicFeatures = async () => {
    try {
      const res = await axios.get(`${API}/admin/clinics/${id}/features`, { headers: getAuthHeaders() });
      setClinicFeatures(res.data.features || []);
      setClinicPlan(res.data.plan || '');
    } catch {}
  };

  const fetchAllPlans = async () => {
    try {
      const res = await axios.get(`${API}/admin/plans`, { headers: getAuthHeaders() });
      setAllPlans(res.data || []);
    } catch {}
  };

  const handleChangePlan = async (planCode) => {
    try {
      await axios.put(`${API}/admin/clinics/${id}/plan`, { plan: planCode }, { headers: getAuthHeaders() });
      toast.success('Plan actualizado');
      fetchClinicDetail();
      fetchClinicFeatures();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error'); }
  };

  const handleToggleFeatureOverride = async (featureId, currentOverride, inPlan) => {
    try {
      let newEnabled;
      if (currentOverride === null || currentOverride === undefined) {
        newEnabled = !inPlan;
      } else {
        newEnabled = null;
      }
      await axios.put(`${API}/admin/clinics/${id}/features/${featureId}`,
        { is_enabled: newEnabled }, { headers: getAuthHeaders() });
      toast.success('Override actualizado');
      fetchClinicFeatures();
    } catch { toast.error('Error'); }
  };

  const handleSave = async () => {
    setSubmitting(true);
    try {
      await axios.put(`${API}/admin/clinics/${id}`, editData, {
        headers: getAuthHeaders()
      });
      setClinic(editData);
      setEditing(false);
      toast.success('Clínica actualizada');
    } catch (error) {
      toast.error('Error al actualizar');
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleActive = async () => {
    try {
      const newStatus = !clinic.is_active;
      await axios.put(`${API}/admin/clinics/${id}`, { is_active: newStatus }, {
        headers: getAuthHeaders()
      });
      setClinic(prev => ({ ...prev, is_active: newStatus }));
      setEditData(prev => ({ ...prev, is_active: newStatus }));
      toast.success(newStatus ? 'Clínica activada' : 'Clínica desactivada');
    } catch (error) {
      toast.error('Error al cambiar estado');
    }
  };

  const generatePassword = () => {
    const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789!@#$%';
    let password = '';
    for (let i = 0; i < 12; i++) {
      password += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    setMemberForm(prev => ({ ...prev, password }));
  };

  const handleAddMember = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const response = await axios.post(`${API}/admin/clinics/${id}/members`, memberForm, {
        headers: getAuthHeaders()
      });
      setCredentials(response.data.credentials);
      setShowMemberModal(false);
      setShowCredentials(true);
      setMemberForm({ name: '', lastname: '', email: '', phone: '', password: '', role: 'staff' });
      fetchClinicDetail();
      toast.success('Usuario creado');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Error al crear usuario');
    } finally {
      setSubmitting(false);
    }
  };

  const copyCredentials = () => {
    const text = `Email: ${credentials.email}\nContraseña: ${credentials.password}`;
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    toast.success('Credenciales copiadas');
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleDateString('es-ES', {
      year: 'numeric', month: 'short', day: 'numeric'
    });
  };

  const getRoleLabel = (role) => {
    return ROLES.find(r => r.value === role)?.label || role;
  };

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-screen">
        <div className="text-zinc-500">Cargando...</div>
      </div>
    );
  }

  if (!clinic) {
    return (
      <div className="p-8">
        <p className="text-zinc-500">Clínica no encontrada</p>
      </div>
    );
  }

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center gap-4 mb-8">
        <Button variant="ghost" onClick={() => navigate('/admin/clinicas')} className="p-2" data-testid="back-btn">
          <ArrowLeft className="w-5 h-5" strokeWidth={1.5} />
        </Button>
        <div className="flex-1">
          <h1 className="text-3xl font-semibold text-zinc-950 tracking-tight">{clinic.name}</h1>
          <p className="text-sm text-zinc-500 mt-1">Detalle de la clínica</p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="text-sm text-zinc-600">Estado:</span>
            <Switch 
              checked={clinic.is_active} 
              onCheckedChange={handleToggleActive}
              data-testid="toggle-active"
            />
            <span className={`text-sm ${clinic.is_active ? 'text-green-600' : 'text-red-600'}`}>
              {clinic.is_active ? 'Activa' : 'Inactiva'}
            </span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Info */}
        <div className="lg:col-span-2 space-y-6">
          {/* Clinic Data */}
          <div className="bg-white border border-zinc-200 p-6">
            <div className="flex items-center justify-between mb-4 pb-2 border-b border-zinc-200">
              <div className="flex items-center gap-2">
                <Building2 className="w-5 h-5 text-violet-600" strokeWidth={1.5} />
                <h3 className="font-medium text-zinc-900">Datos de la Clínica</h3>
              </div>
              {!editing ? (
                <Button variant="ghost" size="sm" onClick={() => setEditing(true)} data-testid="edit-clinic-btn">
                  <Edit2 className="w-4 h-4 mr-1" strokeWidth={1.5} />
                  Editar
                </Button>
              ) : (
                <div className="flex gap-2">
                  <Button variant="ghost" size="sm" onClick={() => setEditing(false)}>Cancelar</Button>
                  <Button size="sm" onClick={handleSave} disabled={submitting} className="btn-primary" data-testid="save-clinic-btn">
                    <Save className="w-4 h-4 mr-1" strokeWidth={1.5} />
                    Guardar
                  </Button>
                </div>
              )}
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label className="text-xs text-zinc-500">Nombre</Label>
                {editing ? (
                  <Input 
                    value={editData.name || ''} 
                    onChange={(e) => setEditData(prev => ({ ...prev, name: e.target.value }))}
                    className="form-input mt-1"
                  />
                ) : (
                  <p className="text-sm text-zinc-900 mt-1">{clinic.name}</p>
                )}
              </div>
              <div>
                <Label className="text-xs text-zinc-500">Slug</Label>
                <p className="text-sm text-zinc-500 font-mono mt-1">{clinic.slug}</p>
              </div>
              <div>
                <Label className="text-xs text-zinc-500">País</Label>
                <p className="text-sm text-zinc-900 mt-1">{clinic.country}</p>
              </div>
              <div>
                <Label className="text-xs text-zinc-500">Ciudad</Label>
                {editing ? (
                  <Input 
                    value={editData.city || ''} 
                    onChange={(e) => setEditData(prev => ({ ...prev, city: e.target.value }))}
                    className="form-input mt-1"
                  />
                ) : (
                  <p className="text-sm text-zinc-900 mt-1">{clinic.city || '-'}</p>
                )}
              </div>
              <div className="col-span-2">
                <Label className="text-xs text-zinc-500">Dirección</Label>
                {editing ? (
                  <Input 
                    value={editData.address || ''} 
                    onChange={(e) => setEditData(prev => ({ ...prev, address: e.target.value }))}
                    className="form-input mt-1"
                  />
                ) : (
                  <p className="text-sm text-zinc-900 mt-1">{clinic.address || '-'}</p>
                )}
              </div>
              <div>
                <Label className="text-xs text-zinc-500">Teléfono</Label>
                {editing ? (
                  <Input 
                    value={editData.phone || ''} 
                    onChange={(e) => setEditData(prev => ({ ...prev, phone: e.target.value }))}
                    className="form-input mt-1"
                  />
                ) : (
                  <p className="text-sm text-zinc-900 mt-1">{clinic.phone || '-'}</p>
                )}
              </div>
              <div>
                <Label className="text-xs text-zinc-500">Email</Label>
                {editing ? (
                  <Input 
                    value={editData.email || ''} 
                    onChange={(e) => setEditData(prev => ({ ...prev, email: e.target.value }))}
                    className="form-input mt-1"
                  />
                ) : (
                  <p className="text-sm text-zinc-900 mt-1">{clinic.email || '-'}</p>
                )}
              </div>
              <div>
                <Label className="text-xs text-zinc-500">Plan</Label>
                {editing ? (
                  <Select value={editData.plan} onValueChange={(v) => setEditData(prev => ({ ...prev, plan: v }))}>
                    <SelectTrigger className="mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {PLANS.map(p => (
                        <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                ) : (
                  <p className="mt-1"><span className="badge badge-plan">{clinic.plan}</span></p>
                )}
              </div>
              <div>
                <Label className="text-xs text-zinc-500">Zona horaria</Label>
                <p className="text-sm text-zinc-900 mt-1">{clinic.timezone || '-'}</p>
              </div>
            </div>
          </div>

          {/* Members */}
          <div className="bg-white border border-zinc-200">
            <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-200">
              <div className="flex items-center gap-2">
                <Users className="w-5 h-5 text-violet-600" strokeWidth={1.5} />
                <h3 className="font-medium text-zinc-900">Miembros ({members.length})</h3>
              </div>
              <Button size="sm" onClick={() => setShowMemberModal(true)} className="btn-primary" data-testid="add-member-btn">
                <Plus className="w-4 h-4 mr-1" strokeWidth={1.5} />
                Agregar usuario
              </Button>
            </div>
            <div className="overflow-x-auto">
              <table className="data-table" data-testid="members-table">
                <thead>
                  <tr className="bg-zinc-50">
                    <th>Nombre</th>
                    <th>Email</th>
                    <th>Rol</th>
                    <th>Estado</th>
                    <th>Último login</th>
                  </tr>
                </thead>
                <tbody>
                  {members.length > 0 ? (
                    members.map((member) => (
                      <tr key={member.id} data-testid={`member-row-${member.id}`}>
                        <td className="font-medium text-zinc-900">{member.name} {member.lastname}</td>
                        <td>{member.email}</td>
                        <td><span className="badge badge-plan">{getRoleLabel(member.role)}</span></td>
                        <td>
                          <span className={`badge ${member.is_active ? 'badge-active' : 'badge-inactive'}`}>
                            {member.is_active ? 'Activo' : 'Inactivo'}
                          </span>
                        </td>
                        <td>{formatDate(member.last_login)}</td>
                      </tr>
                    ))
                  ) : (
                    <tr><td colSpan={5} className="text-center py-8 text-zinc-500">Sin miembros</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Stats */}
          <div className="bg-white border border-zinc-200 p-6">
            <h3 className="font-medium text-zinc-900 mb-4">Estadísticas</h3>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-zinc-600">
                  <UserCheck className="w-4 h-4" strokeWidth={1.5} />
                  <span className="text-sm">Pacientes</span>
                </div>
                <span className="font-mono text-lg text-zinc-950">{stats.total_patients || 0}</span>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-zinc-600">
                  <Calendar className="w-4 h-4" strokeWidth={1.5} />
                  <span className="text-sm">Citas</span>
                </div>
                <span className="font-mono text-lg text-zinc-950">{stats.total_appointments || 0}</span>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-zinc-600">
                  <FileText className="w-4 h-4" strokeWidth={1.5} />
                  <span className="text-sm">Recetas</span>
                </div>
                <span className="font-mono text-lg text-zinc-950">{stats.total_prescriptions || 0}</span>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-zinc-600">
                  <Users className="w-4 h-4" strokeWidth={1.5} />
                  <span className="text-sm">Miembros</span>
                </div>
                <span className="font-mono text-lg text-zinc-950">{stats.members_count || 0}</span>
              </div>
            </div>
          </div>

          {/* Info */}
          <div className="bg-white border border-zinc-200 p-6">
            <h3 className="font-medium text-zinc-900 mb-4">Información</h3>
            <div className="space-y-3 text-sm">
              <div>
                <span className="text-zinc-500">Creada:</span>
                <p className="text-zinc-900">{formatDate(clinic.created_at)}</p>
              </div>
              <div>
                <span className="text-zinc-500">Actualizada:</span>
                <p className="text-zinc-900">{formatDate(clinic.updated_at)}</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Add Member Modal */}
      <Dialog open={showMemberModal} onOpenChange={setShowMemberModal}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="text-xl font-semibold text-zinc-950">Agregar Usuario</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleAddMember} className="mt-4 space-y-4">
            <div>
              <Label className="form-label">Nombre *</Label>
              <Input
                value={memberForm.name}
                onChange={(e) => setMemberForm(prev => ({ ...prev, name: e.target.value }))}
                className="form-input"
                required
                data-testid="member-name-input"
              />
            </div>
            <div>
              <Label className="form-label">Apellido *</Label>
              <Input
                value={memberForm.lastname}
                onChange={(e) => setMemberForm(prev => ({ ...prev, lastname: e.target.value }))}
                className="form-input"
                required
                data-testid="member-lastname-input"
              />
            </div>
            <div>
              <Label className="form-label">Email *</Label>
              <Input
                type="email"
                value={memberForm.email}
                onChange={(e) => setMemberForm(prev => ({ ...prev, email: e.target.value }))}
                className="form-input"
                required
                data-testid="member-email-input"
              />
            </div>
            <div>
              <Label className="form-label">Teléfono</Label>
              <Input
                value={memberForm.phone}
                onChange={(e) => setMemberForm(prev => ({ ...prev, phone: e.target.value }))}
                className="form-input"
                data-testid="member-phone-input"
              />
            </div>
            <div>
              <Label className="form-label">Rol</Label>
              <Select value={memberForm.role} onValueChange={(v) => setMemberForm(prev => ({ ...prev, role: v }))}>
                <SelectTrigger data-testid="member-role-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ROLES.map(r => (
                    <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="form-label">Contraseña *</Label>
              <div className="flex gap-2">
                <Input
                  type="text"
                  value={memberForm.password}
                  onChange={(e) => setMemberForm(prev => ({ ...prev, password: e.target.value }))}
                  className="form-input flex-1"
                  required
                  minLength={8}
                  data-testid="member-password-input"
                />
                <Button type="button" variant="outline" onClick={generatePassword} className="btn-secondary">
                  <RefreshCw className="w-4 h-4" strokeWidth={1.5} />
                </Button>
              </div>
            </div>
            <div className="flex justify-end gap-3 pt-4">
              <Button type="button" variant="outline" onClick={() => setShowMemberModal(false)} className="btn-secondary">
                Cancelar
              </Button>
              <Button type="submit" className="btn-primary" disabled={submitting} data-testid="submit-member-btn">
                {submitting ? 'Creando...' : 'Crear usuario'}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* Plan y Módulos Section */}
      {clinicFeatures.length > 0 && (
        <div className="mt-8 bg-white rounded-xl border border-zinc-200 overflow-hidden" data-testid="plan-modules-section">
          <div className="p-5 border-b border-zinc-100">
            <h3 className="text-lg font-semibold text-zinc-900">Plan y Módulos</h3>
          </div>
          <div className="p-5 space-y-4">
            <div className="flex items-center gap-3">
              <span className="text-sm text-zinc-600">Plan actual:</span>
              <Select value={clinicPlan} onValueChange={handleChangePlan}>
                <SelectTrigger className="w-48" data-testid="change-plan-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {allPlans.map(p => <SelectItem key={p.code} value={p.code}>{p.name} — ${p.price_monthly}/mes</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <p className="text-sm font-medium text-zinc-700 mb-2">Módulos</p>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                {clinicFeatures.map(f => {
                  const isActive = f.override !== null && f.override !== undefined ? f.override : f.in_plan;
                  const hasOverride = f.override !== null && f.override !== undefined;
                  return (
                    <div key={f.id} className={`flex items-center justify-between p-2.5 rounded-lg border text-sm ${isActive ? 'bg-emerald-50 border-emerald-200' : 'bg-slate-50 border-slate-200'}`} data-testid={`feature-${f.code}`}>
                      <div className="flex-1 min-w-0">
                        <p className={`font-medium truncate ${isActive ? 'text-emerald-800' : 'text-slate-500'}`}>{f.name}</p>
                        <div className="flex items-center gap-1 mt-0.5">
                          {f.in_plan && <span className="text-xs bg-teal-100 text-teal-700 px-1 rounded">Plan</span>}
                          {hasOverride && <span className="text-xs bg-amber-100 text-amber-700 px-1 rounded">Override</span>}
                        </div>
                      </div>
                      <Switch checked={isActive} onCheckedChange={() => handleToggleFeatureOverride(f.id, f.override, f.in_plan)} data-testid={`toggle-feature-${f.code}`} />
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Credentials Modal */}
      <Dialog open={showCredentials} onOpenChange={setShowCredentials}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="text-xl font-semibold text-zinc-950 flex items-center gap-2">
              <Check className="w-5 h-5 text-green-600" />
              Usuario creado
            </DialogTitle>
          </DialogHeader>
          <div className="mt-4">
            <p className="text-sm text-zinc-600 mb-4">Credenciales del nuevo usuario:</p>
            <div className="bg-zinc-50 border border-zinc-200 p-4 font-mono text-sm">
              <p><span className="text-zinc-500">Email:</span> {credentials?.email}</p>
              <p><span className="text-zinc-500">Contraseña:</span> {credentials?.password}</p>
            </div>
            <Button onClick={copyCredentials} className="w-full mt-4 btn-secondary" data-testid="copy-member-credentials-btn">
              {copied ? <Check className="w-4 h-4 mr-2" /> : <Copy className="w-4 h-4 mr-2" />}
              {copied ? 'Copiado' : 'Copiar credenciales'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
