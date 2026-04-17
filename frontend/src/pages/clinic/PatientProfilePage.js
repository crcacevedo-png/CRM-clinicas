import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Separator } from '../../components/ui/separator';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '../../components/ui/collapsible';
import { Textarea } from '../../components/ui/textarea';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../components/ui/dialog';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '../../components/ui/sheet';
import { Label } from '../../components/ui/label';
import { toast } from 'sonner';
import {
  ArrowLeft, Phone, Mail, MapPin, Calendar, Heart, Shield, User,
  FileText, Upload, Download, Trash2, Eye, Droplets, Pill, Activity,
  Clock, CalendarPlus, ClipboardList, FlaskConical, AlertTriangle, Edit,
  Plus, ChevronDown, ChevronUp, Stethoscope, AlertCircle, MessageSquarePlus
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

const VITAL_RANGES = {
  blood_pressure_systolic: { min: 70, max: 180 },
  blood_pressure_diastolic: { min: 40, max: 120 },
  heart_rate: { min: 50, max: 120 },
  respiratory_rate: { min: 10, max: 30 },
  temperature: { min: 35.5, max: 38.0 },
  oxygen_saturation: { min: 92, max: 100 },
};

function VitalBadge({ label, value, unit, rangeKey }) {
  if (!value && value !== 0) return null;
  const range = VITAL_RANGES[rangeKey];
  const outOfRange = range && (value < range.min || value > range.max);
  return (
    <div className={`px-2.5 py-1.5 rounded-md text-center ${outOfRange ? 'bg-red-50 border border-red-200' : 'bg-slate-50 border border-slate-100'}`}>
      <p className="text-xs text-slate-500">{label}</p>
      <p className={`text-sm font-bold ${outOfRange ? 'text-red-600' : 'text-slate-800'}`}>
        {value} <span className="text-xs font-normal">{unit}</span>
      </p>
      {outOfRange && <AlertCircle className="w-3 h-3 text-red-500 mx-auto mt-0.5" />}
    </div>
  );
}

function RecordDetail({ record, formatDate, onAddAddendum }) {
  const ROS_LABELS = {
    general: 'General', cardiovascular: 'Cardiovascular', respiratory: 'Respiratorio',
    gastrointestinal: 'Gastrointestinal', genitourinary: 'Genitourinario',
    musculoskeletal: 'Musculoesquelético', neurological: 'Neurológico',
    skin: 'Piel', endocrine: 'Endocrino',
  };
  const EXAM_LABELS = {
    head: 'Cabeza', neck: 'Cuello', chest: 'Tórax',
    abdomen: 'Abdomen', extremities: 'Extremidades', neurological: 'Neurológico',
  };

  const ros = record.review_of_systems || {};
  const hasROS = Object.values(ros).some(v => v && v.length > 0);
  const exam = record.physical_exam || {};
  const hasExam = Object.values(exam).some(v => v && v.trim());
  const hasVitals = record.blood_pressure_systolic || record.heart_rate || record.temperature;

  return (
    <div className="space-y-4 text-sm">
      {/* Chief complaint and present illness */}
      {record.chief_complaint && (
        <div>
          <p className="text-xs font-semibold text-slate-500 uppercase mb-1">Motivo de consulta</p>
          <p className="text-slate-700">{record.chief_complaint}</p>
        </div>
      )}
      {record.present_illness && (
        <div>
          <p className="text-xs font-semibold text-slate-500 uppercase mb-1">Historia de enfermedad actual</p>
          <p className="text-slate-700 whitespace-pre-wrap">{record.present_illness}</p>
        </div>
      )}

      {/* Review of Systems */}
      {hasROS && (
        <div>
          <p className="text-xs font-semibold text-slate-500 uppercase mb-1">Revisión por sistemas</p>
          <div className="flex flex-wrap gap-2">
            {Object.entries(ros).filter(([_, items]) => items && items.length > 0).map(([sys, items]) => (
              <div key={sys} className="bg-slate-50 rounded px-2 py-1">
                <span className="text-xs font-medium text-slate-600">{ROS_LABELS[sys] || sys}: </span>
                <span className="text-xs text-slate-500">{items.join(', ')}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Vital signs */}
      {hasVitals && (
        <div>
          <p className="text-xs font-semibold text-slate-500 uppercase mb-2">Signos vitales</p>
          <div className="grid grid-cols-4 md:grid-cols-8 gap-2">
            <VitalBadge label="PA Sist." value={record.blood_pressure_systolic} unit="mmHg" rangeKey="blood_pressure_systolic" />
            <VitalBadge label="PA Diast." value={record.blood_pressure_diastolic} unit="mmHg" rangeKey="blood_pressure_diastolic" />
            <VitalBadge label="FC" value={record.heart_rate} unit="lpm" rangeKey="heart_rate" />
            <VitalBadge label="FR" value={record.respiratory_rate} unit="rpm" rangeKey="respiratory_rate" />
            <VitalBadge label="Temp" value={record.temperature} unit="°C" rangeKey="temperature" />
            <VitalBadge label="SpO2" value={record.oxygen_saturation} unit="%" rangeKey="oxygen_saturation" />
            <VitalBadge label="Peso" value={record.weight_kg} unit="kg" />
            <VitalBadge label="Talla" value={record.height_cm} unit="cm" />
          </div>
          {record.bmi && (
            <p className="text-xs text-slate-500 mt-1">IMC: <span className="font-bold">{record.bmi}</span></p>
          )}
        </div>
      )}

      {/* Physical Exam */}
      {hasExam && (
        <div>
          <p className="text-xs font-semibold text-slate-500 uppercase mb-1">Examen físico</p>
          <div className="space-y-1">
            {Object.entries(exam).filter(([_, v]) => v && v.trim()).map(([key, val]) => (
              <div key={key} className="flex gap-2">
                <span className="text-xs font-medium text-slate-600 min-w-[90px]">{EXAM_LABELS[key] || key}:</span>
                <span className="text-xs text-slate-600">{val}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Diagnoses */}
      {record.diagnoses?.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-slate-500 uppercase mb-1">Diagnósticos</p>
          <div className="space-y-1">
            {record.diagnoses.map((d, i) => (
              <div key={i} className="flex items-center gap-2">
                <Badge variant="outline" className={`text-xs font-mono ${d.type === 'primary' ? 'bg-teal-50 text-teal-700 border-teal-200' : ''}`}>{d.code}</Badge>
                <span className="text-sm text-slate-700">{d.description}</span>
                {d.type === 'primary' && <Badge className="bg-teal-600 text-white text-xs">Principal</Badge>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Treatment and Procedures */}
      {record.treatment_plan && (
        <div>
          <p className="text-xs font-semibold text-slate-500 uppercase mb-1">Plan de tratamiento</p>
          <p className="text-slate-700 whitespace-pre-wrap">{record.treatment_plan}</p>
        </div>
      )}
      {record.procedures && (
        <div>
          <p className="text-xs font-semibold text-slate-500 uppercase mb-1">Procedimientos</p>
          <p className="text-slate-700 whitespace-pre-wrap">{record.procedures}</p>
        </div>
      )}

      {/* Notes */}
      {record.notes && (
        <div>
          <p className="text-xs font-semibold text-slate-500 uppercase mb-1">Notas</p>
          <p className="text-slate-700 whitespace-pre-wrap">{record.notes}</p>
        </div>
      )}
      {record.private_notes && (
        <div className="p-2 bg-amber-50 rounded-md border border-amber-200">
          <p className="text-xs font-semibold text-amber-700 uppercase mb-1">Notas privadas del médico</p>
          <p className="text-slate-700 whitespace-pre-wrap text-xs">{record.private_notes}</p>
        </div>
      )}

      {/* Addenda */}
      {record.addenda?.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-slate-500 uppercase mb-1">Addendums</p>
          <div className="space-y-2">
            {record.addenda.map((a, i) => (
              <div key={i} className="p-2 bg-blue-50 rounded border border-blue-100">
                <p className="text-xs text-blue-600 mb-0.5">
                  {a.doctor_name} — {new Date(a.created_at).toLocaleString('es-GT', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}
                </p>
                <p className="text-sm text-slate-700">{a.text}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Addendum button for finalized records */}
      {record.status === 'finalized' && (
        <Button variant="outline" size="sm" className="text-xs" onClick={onAddAddendum} data-testid={`add-addendum-${record.id}`}>
          <MessageSquarePlus className="w-3.5 h-3.5 mr-1" /> Agregar addendum
        </Button>
      )}
    </div>
  );
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

  // Medical records state
  const [medicalRecords, setMedicalRecords] = useState([]);
  const [expandedRecord, setExpandedRecord] = useState(null);
  const [doctorFilter, setDoctorFilter] = useState('all');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [doctors, setDoctors] = useState([]);
  const [showAddendum, setShowAddendum] = useState(null);
  const [addendumText, setAddendumText] = useState('');
  const [showEdit, setShowEdit] = useState(false);
  const [editForm, setEditForm] = useState({});
  const [savingEdit, setSavingEdit] = useState(false);
  const [prescriptions, setPrescriptions] = useState([]);
  const [labOrders, setLabOrders] = useState([]);
  const fetchPatient = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/clinic/patients/${id}`, { headers });
      setPatient(res.data.patient);
      setStats(res.data.stats || {});
      setAppointments(res.data.appointments || []);
      setFiles(res.data.files || []);
      // Fetch doctors for filter
      try {
        const cfgRes = await axios.get(`${API}/clinic/config`, { headers });
        setDoctors(cfgRes.data.doctors || []);
      } catch {}
    } catch (err) {
      toast.error('Error al cargar paciente');
      navigate('/dashboard/pacientes');
    } finally {
      setLoading(false);
    }
  }, [id]);

  const fetchMedicalRecords = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (doctorFilter !== 'all') params.set('doctor_id', doctorFilter);
      if (dateFrom) params.set('date_from', dateFrom);
      if (dateTo) params.set('date_to', dateTo);
      const res = await axios.get(`${API}/clinic/patients/${id}/medical-records?${params}`, { headers });
      setMedicalRecords(res.data || []);
    } catch { /* role may not have access */ }
  }, [id, doctorFilter, dateFrom, dateTo]);

  useEffect(() => { fetchPatient(); }, [fetchPatient]);
  useEffect(() => { fetchMedicalRecords(); }, [fetchMedicalRecords]);

  useEffect(() => {
    const fetchPatientPrescriptions = async () => {
      try {
        const res = await axios.get(`${API}/clinic/prescriptions?patient_id=${id}&limit=50`, { headers });
        setPrescriptions(res.data.prescriptions || []);
      } catch {}
    };
    const fetchPatientLabOrders = async () => {
      try {
        const res = await axios.get(`${API}/clinic/lab-orders?patient_id=${id}&limit=50`, { headers });
        setLabOrders(res.data.orders || []);
      } catch {}
    };
    fetchPatientPrescriptions();
    fetchPatientLabOrders();
  }, [id]);

  const handleAddAddendum = async (recordId) => {
    if (!addendumText.trim()) return;
    try {
      await axios.post(`${API}/clinic/medical-records/${recordId}/addendum`, { text: addendumText }, { headers });
      toast.success('Addendum agregado');
      setShowAddendum(null);
      setAddendumText('');
      fetchMedicalRecords();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al agregar addendum');
    }
  };

  const toggleActive = async () => {
    try {
      const res = await axios.put(`${API}/clinic/patients/${id}/toggle-active`, {}, { headers });
      setPatient(prev => ({ ...prev, is_active: res.data.is_active }));
      toast.success(res.data.is_active ? 'Paciente activado' : 'Paciente desactivado');
    } catch {
      toast.error('Error al cambiar estado');
    }
  };

  const openEditForm = () => {
    if (!patient) return;
    setEditForm({
      first_name: patient.first_name || '',
      last_name: patient.last_name || '',
      date_of_birth: patient.date_of_birth || '',
      gender: patient.gender || '',
      national_id: patient.national_id || '',
      nationality: patient.nationality || '',
      phone: patient.phone || '',
      phone_secondary: patient.phone_secondary || '',
      email: patient.email || '',
      address: patient.address || '',
      city: patient.city || '',
      state: patient.state || '',
      country: patient.country || '',
      emergency_contact_name: patient.emergency_contact_name || '',
      emergency_contact_relation: patient.emergency_contact_relation || '',
      emergency_contact_phone: patient.emergency_contact_phone || '',
      blood_type: patient.blood_type || '',
      allergies: (patient.allergies || []).join(', '),
      chronic_conditions: (patient.chronic_conditions || []).join(', '),
      current_medications: (patient.current_medications || []).join(', '),
      insurance_provider: patient.insurance_provider || '',
      insurance_policy_number: patient.insurance_policy_number || '',
      insurance_expiry: patient.insurance_expiry || '',
      notes: patient.notes || '',
    });
    setShowEdit(true);
  };

  const saveEditForm = async () => {
    if (!editForm.first_name || !editForm.last_name) { toast.error('Nombre y apellido son requeridos'); return; }
    setSavingEdit(true);
    try {
      const payload = { ...editForm };
      payload.allergies = editForm.allergies ? editForm.allergies.split(',').map(s => s.trim()).filter(Boolean) : [];
      payload.chronic_conditions = editForm.chronic_conditions ? editForm.chronic_conditions.split(',').map(s => s.trim()).filter(Boolean) : [];
      payload.current_medications = editForm.current_medications ? editForm.current_medications.split(',').map(s => s.trim()).filter(Boolean) : [];
      Object.keys(payload).forEach(k => { if (payload[k] === '') payload[k] = null; });

      await axios.put(`${API}/clinic/patients/${id}`, payload, { headers });
      toast.success('Paciente actualizado');
      setShowEdit(false);
      fetchPatient();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al actualizar');
    } finally {
      setSavingEdit(false);
    }
  };

  const updateField = (field, value) => setEditForm(prev => ({ ...prev, [field]: value }));

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
              <Button variant="outline" size="sm" onClick={() => navigate(`/dashboard/pacientes/${id}/consulta`)} data-testid="quick-appointment-btn">
                <Stethoscope className="w-4 h-4 mr-1.5" /> Nueva consulta
              </Button>
              <Button variant="outline" size="sm" onClick={() => navigate(`/dashboard/agenda`)} data-testid="new-appointment-btn">
                <CalendarPlus className="w-4 h-4 mr-1.5" /> Nueva cita
              </Button>
              <Button variant="outline" size="sm" onClick={toggleActive} data-testid="toggle-active-btn">
                {patient.is_active ? 'Desactivar' : 'Activar'}
              </Button>
              <Button variant="outline" size="sm" onClick={openEditForm} data-testid="edit-patient-btn">
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

        {/* Clinical History - Medical Records Timeline */}
        <TabsContent value="history">
          <div className="space-y-4">
            {/* Filters and New consultation button */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-2">
                <Select value={doctorFilter} onValueChange={setDoctorFilter}>
                  <SelectTrigger className="w-44 text-sm" data-testid="filter-doctor">
                    <SelectValue placeholder="Filtrar por médico" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Todos los médicos</SelectItem>
                    {doctors.map(d => (
                      <SelectItem key={d.id} value={d.id}>{d.first_name} {d.last_name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)} className="w-36 text-sm" data-testid="filter-date-from" />
                <span className="text-xs text-slate-400">a</span>
                <Input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)} className="w-36 text-sm" data-testid="filter-date-to" />
                {(doctorFilter !== 'all' || dateFrom || dateTo) && (
                  <Button variant="ghost" size="sm" onClick={() => { setDoctorFilter('all'); setDateFrom(''); setDateTo(''); }}>
                    Limpiar
                  </Button>
                )}
              </div>
              <Button className="bg-teal-600 hover:bg-teal-700" size="sm" onClick={() => navigate(`/dashboard/pacientes/${id}/consulta`)} data-testid="new-consultation-btn">
                <Plus className="w-4 h-4 mr-1.5" /> Nueva consulta
              </Button>
            </div>

            {/* Medical Records List */}
            {medicalRecords.length === 0 ? (
              <Card className="border border-slate-200">
                <CardContent className="p-12 text-center">
                  <Stethoscope className="w-10 h-10 text-slate-300 mx-auto mb-2" />
                  <p className="text-sm text-slate-500 font-medium">No hay consultas registradas</p>
                  <p className="text-xs text-slate-400 mt-1">Cree una nueva consulta médica para comenzar el historial</p>
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-3">
                {medicalRecords.map(record => {
                  const isExpanded = expandedRecord === record.id;
                  const primaryDx = (record.diagnoses || []).find(d => d.type === 'primary');
                  const hasVitalAlert = record.blood_pressure_systolic > 180 || record.blood_pressure_systolic < 70 ||
                    record.heart_rate > 120 || record.heart_rate < 50 ||
                    record.temperature > 38.0 || record.oxygen_saturation < 92;

                  return (
                    <Card key={record.id} className={`border transition-all ${record.status === 'draft' ? 'border-amber-200 bg-amber-50/30' : 'border-slate-200'}`} data-testid={`record-card-${record.id}`}>
                      <Collapsible open={isExpanded} onOpenChange={() => setExpandedRecord(isExpanded ? null : record.id)}>
                        <CollapsibleTrigger asChild>
                          <button className="w-full text-left p-4 hover:bg-slate-50/50 transition-colors">
                            <div className="flex items-start justify-between gap-3">
                              <div className="flex-1">
                                <div className="flex items-center gap-2 mb-1">
                                  <span className="text-sm font-semibold text-slate-800">
                                    {new Date(record.created_at).toLocaleDateString('es-GT', { day: '2-digit', month: 'long', year: 'numeric' })}
                                  </span>
                                  <Badge variant="outline" className={`text-xs ${record.status === 'finalized' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-amber-50 text-amber-700 border-amber-200'}`}>
                                    {record.status === 'finalized' ? 'Finalizada' : 'Borrador'}
                                  </Badge>
                                  {hasVitalAlert && (
                                    <Badge variant="outline" className="text-xs bg-red-50 text-red-600 border-red-200">
                                      <AlertCircle className="w-3 h-3 mr-0.5" /> Signos vitales alterados
                                    </Badge>
                                  )}
                                </div>
                                <p className="text-xs text-slate-500">Dr. {record.doctor_name}</p>
                                {primaryDx && (
                                  <p className="text-sm text-slate-700 mt-1">
                                    <span className="font-mono text-xs text-teal-600 mr-1">{primaryDx.code}</span>
                                    {primaryDx.description}
                                  </p>
                                )}
                                {record.chief_complaint && (
                                  <p className="text-xs text-slate-500 mt-0.5 truncate max-w-lg">Motivo: {record.chief_complaint}</p>
                                )}
                              </div>
                              <div className="flex items-center gap-2">
                                {record.status === 'draft' && (
                                  <Button variant="outline" size="sm" className="h-7 text-xs" onClick={(e) => { e.stopPropagation(); navigate(`/dashboard/pacientes/${id}/consulta?record_id=${record.id}`); }}>
                                    <Edit className="w-3 h-3 mr-1" /> Editar
                                  </Button>
                                )}
                                {isExpanded ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
                              </div>
                            </div>
                          </button>
                        </CollapsibleTrigger>
                        <CollapsibleContent>
                          <div className="px-4 pb-4 pt-1 border-t border-slate-100">
                            <RecordDetail record={record} formatDate={formatDate} onAddAddendum={() => setShowAddendum(record.id)} />
                          </div>
                        </CollapsibleContent>
                      </Collapsible>
                    </Card>
                  );
                })}
              </div>
            )}

            {/* Appointments table */}
            {appointments.length > 0 && (
              <Card className="border border-slate-200 mt-4">
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-semibold text-slate-700">Historial de citas</CardTitle>
                </CardHeader>
                <CardContent>
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
                </CardContent>
              </Card>
            )}
          </div>

          {/* Addendum Dialog */}
          <Dialog open={!!showAddendum} onOpenChange={() => { setShowAddendum(null); setAddendumText(''); }}>
            <DialogContent className="max-w-md" data-testid="addendum-dialog">
              <DialogHeader>
                <DialogTitle>Agregar addendum</DialogTitle>
              </DialogHeader>
              <div className="py-2">
                <Textarea
                  value={addendumText}
                  onChange={e => setAddendumText(e.target.value)}
                  placeholder="Escriba el addendum o nota adicional..."
                  className="text-sm min-h-[100px]"
                  data-testid="addendum-text"
                />
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setShowAddendum(null)}>Cancelar</Button>
                <Button className="bg-teal-600 hover:bg-teal-700" onClick={() => handleAddAddendum(showAddendum)} data-testid="save-addendum-btn">
                  Guardar addendum
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </TabsContent>

        {/* Prescriptions */}
        <TabsContent value="prescriptions">
          <Card className="border border-slate-200">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                  <Pill className="w-4 h-4 text-teal-500" /> Recetas médicas ({prescriptions.length})
                </CardTitle>
                <Button className="bg-teal-600 hover:bg-teal-700" size="sm" onClick={() => navigate(`/dashboard/recetas/nueva?patient_id=${id}`)} data-testid="new-prescription-from-profile">
                  <Plus className="w-4 h-4 mr-1.5" /> Nueva receta
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {prescriptions.length === 0 ? (
                <div className="text-center py-8">
                  <ClipboardList className="w-10 h-10 text-slate-300 mx-auto mb-2" />
                  <p className="text-sm text-slate-500">No hay recetas registradas</p>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow className="bg-slate-50/50">
                      <TableHead className="text-xs font-semibold">Fecha</TableHead>
                      <TableHead className="text-xs font-semibold">Médico</TableHead>
                      <TableHead className="text-xs font-semibold">Diagnóstico</TableHead>
                      <TableHead className="text-xs font-semibold text-center">Medicamentos</TableHead>
                      <TableHead className="text-xs font-semibold text-center">Estado</TableHead>
                      <TableHead className="text-xs font-semibold text-right">PDF</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {prescriptions.map(p => (
                      <TableRow key={p.id} data-testid={`profile-prescription-${p.id}`}>
                        <TableCell className="text-sm">{formatDate(p.issued_at || p.created_at)}</TableCell>
                        <TableCell className="text-sm">{p.doctor_name || '—'}</TableCell>
                        <TableCell className="text-sm text-slate-600 max-w-[200px] truncate">{p.diagnosis || '—'}</TableCell>
                        <TableCell className="text-center text-sm font-medium">{p.item_count ?? 0}</TableCell>
                        <TableCell className="text-center">
                          <Badge variant="outline" className={`text-xs ${p.status === 'issued' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-amber-50 text-amber-700 border-amber-200'}`}>
                            {p.status === 'issued' ? 'Emitida' : 'Borrador'}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          {p.status === 'issued' && (
                            <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={async () => {
                              try { const r = await axios.get(`${API}/clinic/prescriptions/${p.id}/pdf-url`, { headers }); if (r.data.url) window.open(r.data.url, '_blank'); } catch { toast.error('Error al obtener PDF'); }
                            }} data-testid={`profile-download-rx-${p.id}`}>
                              <Download className="w-3.5 h-3.5 text-teal-600" />
                            </Button>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Lab Orders */}
        <TabsContent value="labs">
          <Card className="border border-slate-200">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                  <FlaskConical className="w-4 h-4 text-teal-500" /> Órdenes de laboratorio ({labOrders.length})
                </CardTitle>
                <Button className="bg-teal-600 hover:bg-teal-700" size="sm" onClick={() => navigate(`/dashboard/laboratorio/nueva?patient_id=${id}`)} data-testid="new-lab-order-from-profile">
                  <Plus className="w-4 h-4 mr-1.5" /> Nueva orden
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {labOrders.length === 0 ? (
                <div className="text-center py-8">
                  <FlaskConical className="w-10 h-10 text-slate-300 mx-auto mb-2" />
                  <p className="text-sm text-slate-500">No hay órdenes de laboratorio</p>
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow className="bg-slate-50/50">
                      <TableHead className="text-xs font-semibold">Fecha</TableHead>
                      <TableHead className="text-xs font-semibold">Médico</TableHead>
                      <TableHead className="text-xs font-semibold">Estudios</TableHead>
                      <TableHead className="text-xs font-semibold text-center">Prioridad</TableHead>
                      <TableHead className="text-xs font-semibold text-center">Estado</TableHead>
                      <TableHead className="text-xs font-semibold text-right">PDF</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {labOrders.map(o => (
                      <TableRow key={o.id} data-testid={`profile-lab-order-${o.id}`}>
                        <TableCell className="text-sm">{formatDate(o.ordered_at || o.created_at)}</TableCell>
                        <TableCell className="text-sm">{o.doctor_name || '—'}</TableCell>
                        <TableCell className="text-sm text-slate-600 max-w-[250px] truncate">{o.study_summary || `${o.item_count} estudio(s)`}</TableCell>
                        <TableCell className="text-center">
                          <span className={`text-xs ${o.priority === 'urgent' ? 'text-red-600 font-semibold' : 'text-slate-600'}`}>
                            {o.priority === 'urgent' ? 'Urgente' : 'Rutina'}
                          </span>
                        </TableCell>
                        <TableCell className="text-center">
                          <Badge variant="outline" className={`text-xs ${o.status === 'completed' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : o.status === 'cancelled' ? 'bg-red-50 text-red-600 border-red-200' : 'bg-amber-50 text-amber-700 border-amber-200'}`}>
                            {o.status === 'completed' ? 'Completada' : o.status === 'cancelled' ? 'Cancelada' : 'Pendiente'}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={async () => {
                            try { const r = await axios.get(`${API}/clinic/lab-orders/${o.id}/pdf-url`, { headers }); if (r.data.url) window.open(r.data.url, '_blank'); } catch { toast.error('Error al obtener PDF'); }
                          }} data-testid={`profile-download-lab-${o.id}`}>
                            <Download className="w-3.5 h-3.5 text-teal-600" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
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

      {/* Edit Patient Sheet */}
      <Sheet open={showEdit} onOpenChange={setShowEdit}>
        <SheetContent className="sm:max-w-xl overflow-y-auto" data-testid="edit-patient-sheet">
          <SheetHeader className="mb-4">
            <SheetTitle>Editar paciente</SheetTitle>
          </SheetHeader>
          <div className="space-y-3">
            <p className="text-xs font-semibold text-slate-500 uppercase">Datos personales</p>
            <div className="grid grid-cols-2 gap-3">
              <div><Label className="text-xs">Nombre *</Label><Input className="mt-1 text-sm" value={editForm.first_name || ''} onChange={e => updateField('first_name', e.target.value)} data-testid="edit-first-name" /></div>
              <div><Label className="text-xs">Apellido *</Label><Input className="mt-1 text-sm" value={editForm.last_name || ''} onChange={e => updateField('last_name', e.target.value)} data-testid="edit-last-name" /></div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label className="text-xs">Fecha de nacimiento</Label><Input type="date" className="mt-1 text-sm" value={editForm.date_of_birth || ''} onChange={e => updateField('date_of_birth', e.target.value)} /></div>
              <div>
                <Label className="text-xs">Género</Label>
                <Select value={editForm.gender || ''} onValueChange={v => updateField('gender', v)}>
                  <SelectTrigger className="mt-1 text-sm"><SelectValue placeholder="Seleccionar" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="male">Masculino</SelectItem>
                    <SelectItem value="female">Femenino</SelectItem>
                    <SelectItem value="other">Otro</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label className="text-xs">DPI</Label><Input className="mt-1 text-sm" value={editForm.national_id || ''} onChange={e => updateField('national_id', e.target.value)} /></div>
              <div><Label className="text-xs">Nacionalidad</Label><Input className="mt-1 text-sm" value={editForm.nationality || ''} onChange={e => updateField('nationality', e.target.value)} /></div>
            </div>

            <Separator />
            <p className="text-xs font-semibold text-slate-500 uppercase">Contacto</p>
            <div className="grid grid-cols-2 gap-3">
              <div><Label className="text-xs">Teléfono</Label><Input className="mt-1 text-sm" value={editForm.phone || ''} onChange={e => updateField('phone', e.target.value)} data-testid="edit-phone" /></div>
              <div><Label className="text-xs">Teléfono secundario</Label><Input className="mt-1 text-sm" value={editForm.phone_secondary || ''} onChange={e => updateField('phone_secondary', e.target.value)} /></div>
            </div>
            <div><Label className="text-xs">Email</Label><Input type="email" className="mt-1 text-sm" value={editForm.email || ''} onChange={e => updateField('email', e.target.value)} /></div>
            <div><Label className="text-xs">Dirección</Label><Input className="mt-1 text-sm" value={editForm.address || ''} onChange={e => updateField('address', e.target.value)} /></div>
            <div className="grid grid-cols-3 gap-3">
              <div><Label className="text-xs">Ciudad</Label><Input className="mt-1 text-sm" value={editForm.city || ''} onChange={e => updateField('city', e.target.value)} /></div>
              <div><Label className="text-xs">Departamento</Label><Input className="mt-1 text-sm" value={editForm.state || ''} onChange={e => updateField('state', e.target.value)} /></div>
              <div><Label className="text-xs">País</Label><Input className="mt-1 text-sm" value={editForm.country || ''} onChange={e => updateField('country', e.target.value)} /></div>
            </div>

            <Separator />
            <p className="text-xs font-semibold text-slate-500 uppercase">Contacto de emergencia</p>
            <div className="grid grid-cols-3 gap-3">
              <div><Label className="text-xs">Nombre</Label><Input className="mt-1 text-sm" value={editForm.emergency_contact_name || ''} onChange={e => updateField('emergency_contact_name', e.target.value)} /></div>
              <div><Label className="text-xs">Relación</Label><Input className="mt-1 text-sm" value={editForm.emergency_contact_relation || ''} onChange={e => updateField('emergency_contact_relation', e.target.value)} /></div>
              <div><Label className="text-xs">Teléfono</Label><Input className="mt-1 text-sm" value={editForm.emergency_contact_phone || ''} onChange={e => updateField('emergency_contact_phone', e.target.value)} /></div>
            </div>

            <Separator />
            <p className="text-xs font-semibold text-slate-500 uppercase">Información médica</p>
            <div>
              <Label className="text-xs">Tipo de sangre</Label>
              <Select value={editForm.blood_type || ''} onValueChange={v => updateField('blood_type', v)}>
                <SelectTrigger className="mt-1 text-sm"><SelectValue placeholder="Seleccionar" /></SelectTrigger>
                <SelectContent>
                  {['A+','A-','B+','B-','AB+','AB-','O+','O-'].map(bt => <SelectItem key={bt} value={bt}>{bt}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div><Label className="text-xs">Alergias (separadas por coma)</Label><Input className="mt-1 text-sm" value={editForm.allergies || ''} onChange={e => updateField('allergies', e.target.value)} /></div>
            <div><Label className="text-xs">Condiciones crónicas (separadas por coma)</Label><Input className="mt-1 text-sm" value={editForm.chronic_conditions || ''} onChange={e => updateField('chronic_conditions', e.target.value)} /></div>
            <div><Label className="text-xs">Medicamentos actuales (separados por coma)</Label><Input className="mt-1 text-sm" value={editForm.current_medications || ''} onChange={e => updateField('current_medications', e.target.value)} /></div>

            <Separator />
            <p className="text-xs font-semibold text-slate-500 uppercase">Seguro médico</p>
            <div><Label className="text-xs">Proveedor de seguro</Label><Input className="mt-1 text-sm" value={editForm.insurance_provider || ''} onChange={e => updateField('insurance_provider', e.target.value)} /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label className="text-xs">Número de póliza</Label><Input className="mt-1 text-sm" value={editForm.insurance_policy_number || ''} onChange={e => updateField('insurance_policy_number', e.target.value)} /></div>
              <div><Label className="text-xs">Vencimiento</Label><Input type="date" className="mt-1 text-sm" value={editForm.insurance_expiry || ''} onChange={e => updateField('insurance_expiry', e.target.value)} /></div>
            </div>
            <div><Label className="text-xs">Notas clínicas</Label><Textarea className="mt-1 text-sm min-h-[60px]" value={editForm.notes || ''} onChange={e => updateField('notes', e.target.value)} /></div>
          </div>

          <div className="flex justify-end gap-3 mt-6 pt-4 border-t">
            <Button variant="outline" onClick={() => setShowEdit(false)}>Cancelar</Button>
            <Button className="bg-teal-600 hover:bg-teal-700" onClick={saveEditForm} disabled={savingEdit} data-testid="save-edit-btn">
              {savingEdit ? 'Guardando...' : 'Guardar cambios'}
            </Button>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
