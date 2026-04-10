import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../../context/AuthContext';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
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
  Plus, 
  Search, 
  Building2, 
  Copy,
  Check,
  RefreshCw,
  X,
  Users
} from 'lucide-react';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const COUNTRIES = [
  { value: 'guatemala', label: 'Guatemala', tz: 'America/Guatemala' },
  { value: 'mexico', label: 'México', tz: 'America/Mexico_City' },
  { value: 'colombia', label: 'Colombia', tz: 'America/Bogota' },
  { value: 'el_salvador', label: 'El Salvador', tz: 'America/El_Salvador' },
  { value: 'honduras', label: 'Honduras', tz: 'America/Tegucigalpa' },
  { value: 'costa_rica', label: 'Costa Rica', tz: 'America/Costa_Rica' },
  { value: 'panama', label: 'Panamá', tz: 'America/Panama' },
  { value: 'ecuador', label: 'Ecuador', tz: 'America/Guayaquil' },
  { value: 'peru', label: 'Perú', tz: 'America/Lima' },
  { value: 'chile', label: 'Chile', tz: 'America/Santiago' },
  { value: 'argentina', label: 'Argentina', tz: 'America/Buenos_Aires' },
  { value: 'republica_dominicana', label: 'Rep. Dominicana', tz: 'America/Santo_Domingo' },
];

const PLANS = [
  { value: 'free', label: 'Free' },
  { value: 'professional', label: 'Professional' },
  { value: 'enterprise', label: 'Enterprise' },
];

export default function ClinicsPage() {
  const [clinics, setClinics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [showSuccessModal, setShowSuccessModal] = useState(false);
  const [createdCredentials, setCreatedCredentials] = useState(null);
  const [search, setSearch] = useState('');
  const [filterCountry, setFilterCountry] = useState('');
  const [filterPlan, setFilterPlan] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [copied, setCopied] = useState(false);
  
  const [formData, setFormData] = useState({
    name: '',
    country: '',
    city: '',
    address: '',
    phone: '',
    email: '',
    timezone: '',
    plan: 'free',
    admin_name: '',
    admin_lastname: '',
    admin_email: '',
    admin_phone: '',
    admin_password: ''
  });

  const { getAuthHeaders } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    fetchClinics();
  }, [search, filterCountry, filterPlan, filterStatus]);

  const fetchClinics = async () => {
    try {
      const params = new URLSearchParams();
      if (search) params.append('search', search);
      if (filterCountry && filterCountry !== 'all') params.append('country', filterCountry);
      if (filterPlan && filterPlan !== 'all') params.append('plan', filterPlan);
      if (filterStatus && filterStatus !== 'all') params.append('status', filterStatus);

      const response = await axios.get(`${API}/admin/clinics?${params}`, {
        headers: getAuthHeaders()
      });
      setClinics(response.data);
    } catch (error) {
      console.error('Fetch clinics error:', error);
      toast.error('Error al cargar clínicas');
    } finally {
      setLoading(false);
    }
  };

  const handleCountryChange = (value) => {
    const country = COUNTRIES.find(c => c.value === value);
    setFormData(prev => ({
      ...prev,
      country: value,
      timezone: country?.tz || ''
    }));
  };

  const generatePassword = async () => {
    try {
      const response = await axios.post(`${API}/generate-password`, {}, {
        headers: getAuthHeaders()
      });
      setFormData(prev => ({ ...prev, admin_password: response.data.password }));
    } catch (error) {
      const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789!@#$%';
      let password = '';
      for (let i = 0; i < 12; i++) {
        password += chars.charAt(Math.floor(Math.random() * chars.length));
      }
      setFormData(prev => ({ ...prev, admin_password: password }));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);

    try {
      const response = await axios.post(`${API}/admin/clinics`, formData, {
        headers: getAuthHeaders()
      });
      
      setCreatedCredentials(response.data.admin_credentials);
      setShowModal(false);
      setShowSuccessModal(true);
      
      setFormData({
        name: '', country: '', city: '', address: '', phone: '', email: '',
        timezone: '', plan: 'free', admin_name: '', admin_lastname: '',
        admin_email: '', admin_phone: '', admin_password: ''
      });
      
      fetchClinics();
      toast.success('Clínica creada exitosamente');
    } catch (error) {
      const msg = error.response?.data?.detail || 'Error al crear clínica';
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const copyCredentials = () => {
    const text = `Email: ${createdCredentials.email}\nContraseña: ${createdCredentials.password}`;
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

  const getCountryLabel = (value) => {
    const country = COUNTRIES.find(c => c.value === value);
    return country?.label || value;
  };

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-semibold text-zinc-950 tracking-tight">Clínicas</h1>
          <p className="text-sm text-zinc-500 mt-1">Gestiona las clínicas de la plataforma</p>
        </div>
        <Button onClick={() => setShowModal(true)} className="btn-primary" data-testid="new-clinic-btn">
          <Plus className="w-4 h-4 mr-2" strokeWidth={1.5} />
          Nueva clínica
        </Button>
      </div>

      {/* Filters */}
      <div className="bg-white border border-zinc-200 p-4 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" strokeWidth={1.5} />
            <Input
              placeholder="Buscar por nombre..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-10 form-input"
              data-testid="search-clinics-input"
            />
          </div>
          <Select value={filterCountry} onValueChange={setFilterCountry}>
            <SelectTrigger data-testid="filter-country">
              <SelectValue placeholder="País" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos los países</SelectItem>
              {COUNTRIES.map(c => (
                <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={filterPlan} onValueChange={setFilterPlan}>
            <SelectTrigger data-testid="filter-plan">
              <SelectValue placeholder="Plan" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos los planes</SelectItem>
              {PLANS.map(p => (
                <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={filterStatus} onValueChange={setFilterStatus}>
            <SelectTrigger data-testid="filter-status">
              <SelectValue placeholder="Estado" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos</SelectItem>
              <SelectItem value="active">Activas</SelectItem>
              <SelectItem value="inactive">Inactivas</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white border border-zinc-200">
        <div className="overflow-x-auto">
          <table className="data-table" data-testid="clinics-table">
            <thead>
              <tr className="bg-zinc-50">
                <th>Nombre</th>
                <th>Slug</th>
                <th>País</th>
                <th>Ciudad</th>
                <th>Plan</th>
                <th>Usuarios</th>
                <th>Pacientes</th>
                <th>Estado</th>
                <th>Creada</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={9} className="text-center py-8 text-zinc-500">Cargando...</td></tr>
              ) : clinics.length > 0 ? (
                clinics.map((clinic) => (
                  <tr 
                    key={clinic.id} 
                    className="cursor-pointer"
                    onClick={() => navigate(`/admin/clinicas/${clinic.id}`)}
                    data-testid={`clinic-row-${clinic.id}`}
                  >
                    <td className="font-medium text-zinc-900">{clinic.name}</td>
                    <td className="text-zinc-500 font-mono text-xs">{clinic.slug}</td>
                    <td>{getCountryLabel(clinic.country)}</td>
                    <td>{clinic.city || '-'}</td>
                    <td><span className="badge badge-plan">{clinic.plan}</span></td>
                    <td>{clinic.users_count || 0}</td>
                    <td>{clinic.patients_count || 0}</td>
                    <td>
                      <span className={`badge ${clinic.is_active ? 'badge-active' : 'badge-inactive'}`}>
                        {clinic.is_active ? 'Activa' : 'Inactiva'}
                      </span>
                    </td>
                    <td>{formatDate(clinic.created_at)}</td>
                  </tr>
                ))
              ) : (
                <tr><td colSpan={9} className="text-center py-8 text-zinc-500">No hay clínicas</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create Clinic Modal */}
      <Dialog open={showModal} onOpenChange={setShowModal}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-xl font-semibold text-zinc-950">Nueva Clínica</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="mt-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Clinic Data */}
              <div className="space-y-4">
                <div className="flex items-center gap-2 mb-4 pb-2 border-b border-zinc-200">
                  <Building2 className="w-5 h-5 text-violet-600" strokeWidth={1.5} />
                  <h3 className="font-medium text-zinc-900">Datos de la Clínica</h3>
                </div>

                <div>
                  <Label className="form-label">Nombre de la clínica *</Label>
                  <Input
                    value={formData.name}
                    onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                    className="form-input"
                    required
                    data-testid="clinic-name-input"
                  />
                </div>

                <div>
                  <Label className="form-label">País *</Label>
                  <Select value={formData.country} onValueChange={handleCountryChange} required>
                    <SelectTrigger data-testid="clinic-country-select">
                      <SelectValue placeholder="Selecciona un país" />
                    </SelectTrigger>
                    <SelectContent>
                      {COUNTRIES.map(c => (
                        <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <Label className="form-label">Ciudad</Label>
                  <Input
                    value={formData.city}
                    onChange={(e) => setFormData(prev => ({ ...prev, city: e.target.value }))}
                    className="form-input"
                    data-testid="clinic-city-input"
                  />
                </div>

                <div>
                  <Label className="form-label">Dirección</Label>
                  <Input
                    value={formData.address}
                    onChange={(e) => setFormData(prev => ({ ...prev, address: e.target.value }))}
                    className="form-input"
                    data-testid="clinic-address-input"
                  />
                </div>

                <div>
                  <Label className="form-label">Teléfono</Label>
                  <Input
                    value={formData.phone}
                    onChange={(e) => setFormData(prev => ({ ...prev, phone: e.target.value }))}
                    className="form-input"
                    data-testid="clinic-phone-input"
                  />
                </div>

                <div>
                  <Label className="form-label">Email de la clínica</Label>
                  <Input
                    type="email"
                    value={formData.email}
                    onChange={(e) => setFormData(prev => ({ ...prev, email: e.target.value }))}
                    className="form-input"
                    data-testid="clinic-email-input"
                  />
                </div>

                <div>
                  <Label className="form-label">Plan</Label>
                  <Select value={formData.plan} onValueChange={(v) => setFormData(prev => ({ ...prev, plan: v }))}>
                    <SelectTrigger data-testid="clinic-plan-select">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {PLANS.map(p => (
                        <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* Admin Data */}
              <div className="space-y-4">
                <div className="flex items-center gap-2 mb-4 pb-2 border-b border-zinc-200">
                  <Users className="w-5 h-5 text-violet-600" strokeWidth={1.5} />
                  <h3 className="font-medium text-zinc-900">Administrador Inicial</h3>
                </div>

                <div>
                  <Label className="form-label">Nombre *</Label>
                  <Input
                    value={formData.admin_name}
                    onChange={(e) => setFormData(prev => ({ ...prev, admin_name: e.target.value }))}
                    className="form-input"
                    required
                    data-testid="admin-name-input"
                  />
                </div>

                <div>
                  <Label className="form-label">Apellido *</Label>
                  <Input
                    value={formData.admin_lastname}
                    onChange={(e) => setFormData(prev => ({ ...prev, admin_lastname: e.target.value }))}
                    className="form-input"
                    required
                    data-testid="admin-lastname-input"
                  />
                </div>

                <div>
                  <Label className="form-label">Email del admin *</Label>
                  <Input
                    type="email"
                    value={formData.admin_email}
                    onChange={(e) => setFormData(prev => ({ ...prev, admin_email: e.target.value }))}
                    className="form-input"
                    required
                    data-testid="admin-email-input"
                  />
                </div>

                <div>
                  <Label className="form-label">Teléfono del admin</Label>
                  <Input
                    value={formData.admin_phone}
                    onChange={(e) => setFormData(prev => ({ ...prev, admin_phone: e.target.value }))}
                    className="form-input"
                    data-testid="admin-phone-input"
                  />
                </div>

                <div>
                  <Label className="form-label">Contraseña temporal *</Label>
                  <div className="flex gap-2">
                    <Input
                      type="text"
                      value={formData.admin_password}
                      onChange={(e) => setFormData(prev => ({ ...prev, admin_password: e.target.value }))}
                      className="form-input flex-1"
                      required
                      minLength={8}
                      data-testid="admin-password-input"
                    />
                    <Button 
                      type="button" 
                      variant="outline" 
                      onClick={generatePassword}
                      className="btn-secondary"
                      data-testid="generate-password-btn"
                    >
                      <RefreshCw className="w-4 h-4" strokeWidth={1.5} />
                    </Button>
                  </div>
                  <p className="text-xs text-zinc-500 mt-1">Mínimo 8 caracteres</p>
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-3 mt-8 pt-4 border-t border-zinc-200">
              <Button type="button" variant="outline" onClick={() => setShowModal(false)} className="btn-secondary">
                Cancelar
              </Button>
              <Button type="submit" className="btn-primary" disabled={submitting} data-testid="submit-clinic-btn">
                {submitting ? 'Creando...' : 'Crear clínica'}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* Success Modal */}
      <Dialog open={showSuccessModal} onOpenChange={setShowSuccessModal}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="text-xl font-semibold text-zinc-950 flex items-center gap-2">
              <Check className="w-5 h-5 text-green-600" />
              Clínica creada
            </DialogTitle>
          </DialogHeader>
          <div className="mt-4">
            <p className="text-sm text-zinc-600 mb-4">
              La clínica se ha creado exitosamente. Estas son las credenciales del administrador:
            </p>
            <div className="bg-zinc-50 border border-zinc-200 p-4 font-mono text-sm">
              <p><span className="text-zinc-500">Email:</span> {createdCredentials?.email}</p>
              <p><span className="text-zinc-500">Contraseña:</span> {createdCredentials?.password}</p>
            </div>
            <Button 
              onClick={copyCredentials} 
              className="w-full mt-4 btn-secondary"
              data-testid="copy-credentials-btn"
            >
              {copied ? <Check className="w-4 h-4 mr-2" /> : <Copy className="w-4 h-4 mr-2" />}
              {copied ? 'Copiado' : 'Copiar credenciales'}
            </Button>
            <p className="text-xs text-zinc-500 text-center mt-4">
              Estas credenciales solo se mostrarán una vez. Asegúrate de enviarlas al administrador.
            </p>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
