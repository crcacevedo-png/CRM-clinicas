import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui/table';
import { Separator } from '../../components/ui/separator';
import { toast } from 'sonner';
import {
  ArrowLeft, Phone, Mail, MapPin, Calendar, Heart, Shield, User,
  FileText, Upload, Download, Trash2, Eye, Droplets, Pill, Activity,
  Clock, CalendarPlus, ClipboardList, FlaskConical, AlertTriangle, Edit
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function InfoRow({ icon: Icon, label, value }) {
  if (!value) return null;
  return (
    <div className="flex items-start gap-3 py-2">
      <Icon className="w-4 h-4 text-slate-400 mt-0.5 flex-shrink-0" />
      <div>
        <p className="text-xs text-slate-500">{label}</p>
        <p className="text-sm text-slate-800 font-medium">{value}</p>
      </div>
    </div>
  );
}

function StatCard({ label, value, icon: Icon, color }) {
  return (
    <div className="flex items-center gap-3 p-3 rounded-lg bg-white border border-slate-100">
      <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${color}`}>
        <Icon className="w-4 h-4" />
      </div>
      <div>
        <p className="text-xs text-slate-500">{label}</p>
        <p className="text-lg font-bold text-slate-800">{value}</p>
      </div>
    </div>
  );
}

const STATUS_MAP = {
  scheduled: { label: 'Programada', class: 'bg-blue-50 text-blue-700 border-blue-200' },
  confirmed: { label: 'Confirmada', class: 'bg-indigo-50 text-indigo-700 border-indigo-200' },
  in_progress: { label: 'En curso', class: 'bg-amber-50 text-amber-700 border-amber-200' },
  completed: { label: 'Completada', class: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  cancelled: { label: 'Cancelada', class: 'bg-red-50 text-red-600 border-red-200' },
  no_show: { label: 'No asistió', class: 'bg-slate-100 text-slate-600 border-slate-300' },
};

const FILE_ICONS = {
  'application/pdf': { icon: FileText, color: 'text-red-500 bg-red-50' },
  'image/jpeg': { icon: Eye, color: 'text-blue-500 bg-blue-50' },
  'image/png': { icon: Eye, color: 'text-green-500 bg-green-50' },
  'application/dicom': { icon: Activity, color: 'text-purple-500 bg-purple-50' },
};

function formatFileSize(bytes) {
  if (!bytes) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1048576).toFixed(1)} MB`;
}

export default function PatientProfilePage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { getAuthHeaders } = useAuth();
  const headers = getAuthHeaders();
  const fileInputRef = useRef(null);

  const [patient, setPatient] = useState(null);
  const [stats, setStats] = useState({});
  const [appointments, setAppointments] = useState([]);
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [activeTab, setActiveTab] = useState('general');

  const fetchPatient = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/clinic/patients/${id}`, { headers });
      setPatient(res.data.patient);
      setStats(res.data.stats || {});
      setAppointments(res.data.appointments || []);
      setFiles(res.data.files || []);
    } catch (err) {
      toast.error('Error al cargar paciente');
      navigate('/dashboard/pacientes');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { fetchPatient(); }, [fetchPatient]);

  const toggleActive = async () => {
    try {
      const res = await axios.put(`${API}/clinic/patients/${id}/toggle-active`, {}, { headers });
      setPatient(prev => ({ ...prev, is_active: res.data.is_active }));
      toast.success(res.data.is_active ? 'Paciente activado' : 'Paciente desactivado');
    } catch {
      toast.error('Error al cambiar estado');
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const allowed = ['image/jpeg', 'image/png', 'application/pdf', 'application/dicom'];
    if (!allowed.includes(file.type)) {
      toast.error('Solo se permiten archivos JPG, PNG, PDF o DICOM');
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      toast.error('El archivo excede el límite de 10MB');
      return;
    }

    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      await axios.post(`${API}/clinic/patients/${id}/files`, formData, {
        headers: { ...headers, 'Content-Type': 'multipart/form-data' },
      });
      toast.success('Archivo subido exitosamente');
      fetchPatient();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al subir archivo');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const downloadFile = async (filename) => {
    try {
      const res = await axios.get(`${API}/clinic/patients/${id}/files/${encodeURIComponent(filename)}/url`, { headers });
      const url = res.data.url;
      if (url) window.open(url, '_blank');
      else toast.error('No se pudo obtener la URL del archivo');
    } catch {
      toast.error('Error al descargar archivo');
    }
  };

  const deleteFile = async (filename) => {
    if (!window.confirm(`¿Eliminar el archivo "${filename}"?`)) return;
    try {
      await axios.delete(`${API}/clinic/patients/${id}/files/${encodeURIComponent(filename)}`, { headers });
      toast.success('Archivo eliminado');
      setFiles(prev => prev.filter(f => f.name !== filename));
    } catch {
      toast.error('Error al eliminar archivo');
    }
  };

  const formatDate = (d) => {
    if (!d) return '—';
    return new Date(d).toLocaleDateString('es-GT', { day: '2-digit', month: 'short', year: 'numeric' });
  };

  const formatDateTime = (d) => {
    if (!d) return '—';
    return new Date(d).toLocaleString('es-GT', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  };

  const calcAge = (dob) => {
    if (!dob) return null;
    const diff = Date.now() - new Date(dob).getTime();
    return Math.floor(diff / 31557600000);
  };

  const genderLabel = (g) => {
    if (g === 'male') return 'Masculino';
    if (g === 'female') return 'Femenino';
    if (g === 'other') return 'Otro';
    return g || '—';
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-96">
        <div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!patient) return null;

  const age = calcAge(patient.date_of_birth);

  return (
    <div className="p-6 lg:p-8 max-w-6xl" data-testid="patient-profile-page">
      {/* Back button */}
      <Button variant="ghost" className="mb-4 text-slate-600 hover:text-slate-900 -ml-2" onClick={() => navigate('/dashboard/pacientes')} data-testid="back-to-patients">
        <ArrowLeft className="w-4 h-4 mr-1.5" /> Volver a pacientes
      </Button>

      {/* Profile Header */}
      <Card className="border border-slate-200 mb-6" data-testid="patient-header-card">
        <CardContent className="p-5">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="w-14 h-14 rounded-full bg-teal-100 text-teal-700 flex items-center justify-center text-xl font-bold flex-shrink-0">
                {(patient.first_name?.[0] || '').toUpperCase()}{(patient.last_name?.[0] || '').toUpperCase()}
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-xl font-bold text-slate-900" data-testid="patient-name">
                    {patient.first_name} {patient.last_name}
                  </h1>
                  <Badge variant="outline" className={`text-xs ${patient.is_active ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-red-50 text-red-600 border-red-200'}`} data-testid="patient-status-badge">
                    {patient.is_active ? 'Activo' : 'Inactivo'}
                  </Badge>
                </div>
                <div className="flex items-center gap-4 mt-1 text-sm text-slate-500">
                  {patient.national_id && <span>DPI: {patient.national_id}</span>}
                  {age !== null && <span>{age} años</span>}
                  {patient.gender && <span>{genderLabel(patient.gender)}</span>}
                  {patient.blood_type && (
                    <span className="flex items-center gap-1"><Droplets className="w-3 h-3" />{patient.blood_type}</span>
                  )}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <Button variant="outline" size="sm" onClick={() => navigate(`/dashboard/agenda`)} data-testid="quick-appointment-btn">
                <CalendarPlus className="w-4 h-4 mr-1.5" /> Nueva cita
              </Button>
              <Button variant="outline" size="sm" onClick={toggleActive} data-testid="toggle-active-btn">
                {patient.is_active ? 'Desactivar' : 'Activar'}
              </Button>
              <Button variant="outline" size="sm" onClick={() => navigate('/dashboard/pacientes', { state: { editId: patient.id } })} data-testid="edit-patient-btn">
                <Edit className="w-4 h-4 mr-1.5" /> Editar
              </Button>
            </div>
          </div>

          {/* Quick Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-5">
            <StatCard label="Visitas completadas" value={stats.completed_visits ?? 0} icon={Activity} color="bg-emerald-100 text-emerald-600" />
            <StatCard label="Total citas" value={stats.total_appointments ?? 0} icon={Calendar} color="bg-blue-100 text-blue-600" />
            <StatCard
              label="Última visita"
              value={stats.last_visit ? formatDate(stats.last_visit.starts_at) : '—'}
              icon={Clock}
              color="bg-amber-100 text-amber-600"
            />
            <StatCard
              label="Próxima cita"
              value={stats.next_appointment ? formatDate(stats.next_appointment.starts_at) : '—'}
              icon={CalendarPlus}
              color="bg-purple-100 text-purple-600"
            />
          </div>
        </CardContent>
      </Card>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} data-testid="patient-tabs">
        <TabsList className="bg-slate-100 mb-4">
          <TabsTrigger value="general" data-testid="tab-general">Info General</TabsTrigger>
          <TabsTrigger value="history" data-testid="tab-history">Historial Clínico</TabsTrigger>
          <TabsTrigger value="prescriptions" data-testid="tab-prescriptions">Recetas</TabsTrigger>
          <TabsTrigger value="labs" data-testid="tab-labs">Órdenes Lab</TabsTrigger>
          <TabsTrigger value="files" data-testid="tab-files">Archivos ({files.length})</TabsTrigger>
        </TabsList>

        {/* General Info */}
        <TabsContent value="general">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Personal Data */}
            <Card className="border border-slate-200">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                  <User className="w-4 h-4 text-teal-500" /> Datos personales
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <InfoRow icon={User} label="Nombre completo" value={`${patient.first_name} ${patient.last_name}`} />
                <InfoRow icon={Calendar} label="Fecha de nacimiento" value={patient.date_of_birth ? `${formatDate(patient.date_of_birth)}${age !== null ? ` (${age} años)` : ''}` : null} />
                <InfoRow icon={User} label="Género" value={genderLabel(patient.gender)} />
                <InfoRow icon={Shield} label="DPI / Identificación" value={patient.national_id} />
                <InfoRow icon={MapPin} label="Nacionalidad" value={patient.nationality} />
              </CardContent>
            </Card>

            {/* Contact */}
            <Card className="border border-slate-200">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                  <Phone className="w-4 h-4 text-teal-500" /> Contacto
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <InfoRow icon={Phone} label="Teléfono principal" value={patient.phone} />
                <InfoRow icon={Phone} label="Teléfono secundario" value={patient.phone_secondary} />
                <InfoRow icon={Mail} label="Correo electrónico" value={patient.email} />
                <InfoRow icon={MapPin} label="Dirección" value={[patient.address, patient.city, patient.state, patient.country].filter(Boolean).join(', ') || null} />
              </CardContent>
            </Card>

            {/* Emergency Contact */}
            <Card className="border border-slate-200">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-orange-500" /> Contacto de emergencia
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <InfoRow icon={User} label="Nombre" value={patient.emergency_contact_name} />
                <InfoRow icon={Heart} label="Relación" value={patient.emergency_contact_relation} />
                <InfoRow icon={Phone} label="Teléfono" value={patient.emergency_contact_phone} />
                {!patient.emergency_contact_name && !patient.emergency_contact_phone && (
                  <p className="text-sm text-slate-400 py-2">Sin contacto de emergencia registrado</p>
                )}
              </CardContent>
            </Card>

            {/* Medical Info */}
            <Card className="border border-slate-200">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                  <Heart className="w-4 h-4 text-red-500" /> Información médica
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <InfoRow icon={Droplets} label="Tipo de sangre" value={patient.blood_type} />
                <div className="py-2">
                  <p className="text-xs text-slate-500 mb-1">Alergias</p>
                  {patient.allergies?.length > 0 ? (
                    <div className="flex flex-wrap gap-1">
                      {patient.allergies.map((a, i) => (
                        <Badge key={i} variant="outline" className="text-xs bg-red-50 text-red-600 border-red-200">{a}</Badge>
                      ))}
                    </div>
                  ) : <p className="text-sm text-slate-400">Ninguna registrada</p>}
                </div>
                <div className="py-2">
                  <p className="text-xs text-slate-500 mb-1">Condiciones crónicas</p>
                  {patient.chronic_conditions?.length > 0 ? (
                    <div className="flex flex-wrap gap-1">
                      {patient.chronic_conditions.map((c, i) => (
                        <Badge key={i} variant="outline" className="text-xs bg-amber-50 text-amber-700 border-amber-200">{c}</Badge>
                      ))}
                    </div>
                  ) : <p className="text-sm text-slate-400">Ninguna registrada</p>}
                </div>
                <div className="py-2">
                  <p className="text-xs text-slate-500 mb-1">Medicamentos actuales</p>
                  {patient.current_medications?.length > 0 ? (
                    <div className="flex flex-wrap gap-1">
                      {patient.current_medications.map((m, i) => (
                        <Badge key={i} variant="outline" className="text-xs bg-blue-50 text-blue-700 border-blue-200">{m}</Badge>
                      ))}
                    </div>
                  ) : <p className="text-sm text-slate-400">Ninguno registrado</p>}
                </div>
                {patient.insurance_provider && (
                  <>
                    <Separator className="my-2" />
                    <InfoRow icon={Shield} label="Aseguradora" value={patient.insurance_provider} />
                    <InfoRow icon={FileText} label="Número de póliza" value={patient.insurance_policy_number} />
                    <InfoRow icon={Calendar} label="Vencimiento" value={formatDate(patient.insurance_expiry)} />
                  </>
                )}
                {patient.notes && (
                  <>
                    <Separator className="my-2" />
                    <div className="py-2">
                      <p className="text-xs text-slate-500 mb-1">Notas clínicas</p>
                      <p className="text-sm text-slate-700 whitespace-pre-wrap">{patient.notes}</p>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Clinical History */}
        <TabsContent value="history">
          <Card className="border border-slate-200">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold text-slate-700">Historial de citas</CardTitle>
            </CardHeader>
            <CardContent>
              {appointments.length === 0 ? (
                <div className="text-center py-10">
                  <Calendar className="w-10 h-10 text-slate-300 mx-auto mb-2" />
                  <p className="text-sm text-slate-500">No hay citas registradas</p>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow className="bg-slate-50/50">
                      <TableHead className="text-xs font-semibold">Fecha</TableHead>
                      <TableHead className="text-xs font-semibold">Doctor</TableHead>
                      <TableHead className="text-xs font-semibold">Motivo</TableHead>
                      <TableHead className="text-xs font-semibold text-center">Estado</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {appointments.map(apt => {
                      const st = STATUS_MAP[apt.status] || { label: apt.status, class: 'bg-slate-50 text-slate-600' };
                      return (
                        <TableRow key={apt.id} data-testid={`appointment-row-${apt.id}`}>
                          <TableCell className="text-sm">{formatDateTime(apt.starts_at)}</TableCell>
                          <TableCell className="text-sm">{apt.doctor_name || '—'}</TableCell>
                          <TableCell className="text-sm text-slate-600 max-w-xs truncate">{apt.reason || '—'}</TableCell>
                          <TableCell className="text-center">
                            <Badge variant="outline" className={`text-xs ${st.class}`}>{st.label}</Badge>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Prescriptions (placeholder) */}
        <TabsContent value="prescriptions">
          <Card className="border border-slate-200">
            <CardContent className="p-12 text-center">
              <ClipboardList className="w-10 h-10 text-slate-300 mx-auto mb-2" />
              <p className="text-sm text-slate-500 font-medium">Módulo de recetas médicas</p>
              <p className="text-xs text-slate-400 mt-1">Próximamente disponible</p>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Lab Orders (placeholder) */}
        <TabsContent value="labs">
          <Card className="border border-slate-200">
            <CardContent className="p-12 text-center">
              <FlaskConical className="w-10 h-10 text-slate-300 mx-auto mb-2" />
              <p className="text-sm text-slate-500 font-medium">Órdenes de laboratorio</p>
              <p className="text-xs text-slate-400 mt-1">Próximamente disponible</p>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Files / Attachments */}
        <TabsContent value="files">
          <Card className="border border-slate-200" data-testid="files-section">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-semibold text-slate-700">
                  Archivos adjuntos ({files.length})
                </CardTitle>
                <div>
                  <input
                    type="file"
                    ref={fileInputRef}
                    onChange={handleFileUpload}
                    accept=".pdf,.jpg,.jpeg,.png,.dcm"
                    className="hidden"
                    data-testid="file-upload-input"
                  />
                  <Button
                    size="sm"
                    className="bg-teal-600 hover:bg-teal-700"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={uploading}
                    data-testid="upload-file-btn"
                  >
                    <Upload className="w-3.5 h-3.5 mr-1.5" />
                    {uploading ? 'Subiendo...' : 'Subir archivo'}
                  </Button>
                </div>
              </div>
              <p className="text-xs text-slate-400 mt-1">Formatos permitidos: PDF, JPG, PNG, DICOM. Máx 10MB</p>
            </CardHeader>
            <CardContent>
              {files.length === 0 ? (
                <div className="text-center py-10 border-2 border-dashed border-slate-200 rounded-lg">
                  <FileText className="w-10 h-10 text-slate-300 mx-auto mb-2" />
                  <p className="text-sm text-slate-500">No hay archivos adjuntos</p>
                  <p className="text-xs text-slate-400 mt-1">Sube documentos, imágenes o estudios del paciente</p>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow className="bg-slate-50/50">
                      <TableHead className="text-xs font-semibold">Archivo</TableHead>
                      <TableHead className="text-xs font-semibold">Tipo</TableHead>
                      <TableHead className="text-xs font-semibold">Tamaño</TableHead>
                      <TableHead className="text-xs font-semibold">Fecha</TableHead>
                      <TableHead className="text-xs font-semibold text-right">Acciones</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {files.map((f, idx) => {
                      const ft = FILE_ICONS[f.content_type] || { icon: FileText, color: 'text-slate-500 bg-slate-50' };
                      const FIcon = ft.icon;
                      return (
                        <TableRow key={idx} data-testid={`file-row-${idx}`}>
                          <TableCell>
                            <div className="flex items-center gap-2.5">
                              <div className={`w-8 h-8 rounded flex items-center justify-center ${ft.color}`}>
                                <FIcon className="w-4 h-4" />
                              </div>
                              <span className="text-sm font-medium text-slate-700 truncate max-w-[200px]">{f.name}</span>
                            </div>
                          </TableCell>
                          <TableCell className="text-xs text-slate-500">{f.content_type || '—'}</TableCell>
                          <TableCell className="text-xs text-slate-500">{formatFileSize(f.size)}</TableCell>
                          <TableCell className="text-xs text-slate-500">{formatDate(f.created_at)}</TableCell>
                          <TableCell>
                            <div className="flex items-center justify-end gap-1">
                              <Button variant="ghost" size="sm" onClick={() => downloadFile(f.name)} className="h-7 w-7 p-0" data-testid={`download-file-${idx}`}>
                                <Download className="w-3.5 h-3.5 text-slate-600" />
                              </Button>
                              <Button variant="ghost" size="sm" onClick={() => deleteFile(f.name)} className="h-7 w-7 p-0 hover:text-red-600" data-testid={`delete-file-${idx}`}>
                                <Trash2 className="w-3.5 h-3.5" />
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
