import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import axios from 'axios';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { toast } from 'sonner';
import {
  ArrowLeft, Calendar, Clock, Droplets, Activity, CalendarPlus, Edit, Stethoscope,
} from 'lucide-react';
import { API } from './patient-profile/constants';
import { formatDate, calcAge, genderLabel } from './patient-profile/utils';
import { StatCard } from './patient-profile/cells';
import GeneralTab from './patient-profile/GeneralTab';
import HistoryTab from './patient-profile/HistoryTab';
import PrescriptionsTab from './patient-profile/PrescriptionsTab';
import LabsTab from './patient-profile/LabsTab';
import FilesTab from './patient-profile/FilesTab';
import EditPatientSheet from './patient-profile/EditPatientSheet';

export default function PatientProfilePage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { getAuthHeaders } = useAuth();
  const headers = getAuthHeaders();

  const [patient, setPatient] = useState(null);
  const [stats, setStats] = useState({});
  const [appointments, setAppointments] = useState([]);
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [activeTab, setActiveTab] = useState('general');

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
  const [tabsLoaded, setTabsLoaded] = useState({ history: false, prescriptions: false, labs: false });
  const [tabsLoading, setTabsLoading] = useState({ history: false, prescriptions: false, labs: false });

  const fetchPatient = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/clinic/patients/${id}`, { headers });
      setPatient(res.data.patient);
      setStats(res.data.stats || {});
      setAppointments(res.data.appointments || []);
      setFiles(res.data.files || []);
      try {
        const cfgRes = await axios.get(`${API}/clinic/config`, { headers });
        setDoctors(cfgRes.data.doctors || []);
      } catch { /* ignore */ }
    } catch (err) {
      toast.error('Error al cargar paciente');
      navigate('/dashboard/pacientes');
    } finally {
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const fetchMedicalRecords = useCallback(async () => {
    setTabsLoading(s => ({ ...s, history: true }));
    try {
      const params = new URLSearchParams();
      if (doctorFilter !== 'all') params.set('doctor_id', doctorFilter);
      if (dateFrom) params.set('date_from', dateFrom);
      if (dateTo) params.set('date_to', dateTo);
      const res = await axios.get(`${API}/clinic/patients/${id}/medical-records?${params}`, { headers });
      setMedicalRecords(res.data || []);
      setTabsLoaded(s => ({ ...s, history: true }));
    } catch { /* role may not have access */ }
    finally { setTabsLoading(s => ({ ...s, history: false })); }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, doctorFilter, dateFrom, dateTo]);

  const fetchPrescriptions = useCallback(async () => {
    setTabsLoading(s => ({ ...s, prescriptions: true }));
    try {
      const r = await axios.get(`${API}/clinic/prescriptions?patient_id=${id}&limit=50`, { headers });
      setPrescriptions(r.data.prescriptions || []);
      setTabsLoaded(s => ({ ...s, prescriptions: true }));
    } catch { /* ignore */ }
    finally { setTabsLoading(s => ({ ...s, prescriptions: false })); }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const fetchLabOrders = useCallback(async () => {
    setTabsLoading(s => ({ ...s, labs: true }));
    try {
      const r = await axios.get(`${API}/clinic/lab-orders?patient_id=${id}&limit=50`, { headers });
      setLabOrders(r.data.orders || []);
      setTabsLoaded(s => ({ ...s, labs: true }));
    } catch { /* ignore */ }
    finally { setTabsLoading(s => ({ ...s, labs: false })); }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  useEffect(() => { fetchPatient(); }, [fetchPatient]);

  // Re-fetch medical records when filters change (only if tab already loaded once)
  useEffect(() => {
    if (tabsLoaded.history) fetchMedicalRecords();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [doctorFilter, dateFrom, dateTo]);

  // Lazy: fetch on tab switch (only first time, then cached)
  const handleTabChange = (newTab) => {
    setActiveTab(newTab);
    if (newTab === 'history' && !tabsLoaded.history && !tabsLoading.history) fetchMedicalRecords();
    else if (newTab === 'prescriptions' && !tabsLoaded.prescriptions && !tabsLoading.prescriptions) fetchPrescriptions();
    else if (newTab === 'labs' && !tabsLoaded.labs && !tabsLoading.labs) fetchLabOrders();
  };

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
    } catch { toast.error('Error al cambiar estado'); }
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
    if (!allowed.includes(file.type)) { toast.error('Solo se permiten archivos JPG, PNG, PDF o DICOM'); return; }
    if (file.size > 10 * 1024 * 1024) { toast.error('El archivo excede el límite de 10MB'); return; }
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
    }
  };

  const downloadFile = async (filename) => {
    try {
      const res = await axios.get(`${API}/clinic/patients/${id}/files/${encodeURIComponent(filename)}/url`, { headers });
      const url = res.data.url;
      if (url) window.open(url, '_blank');
      else toast.error('No se pudo obtener la URL del archivo');
    } catch { toast.error('Error al descargar archivo'); }
  };

  const deleteFile = async (filename) => {
    if (!window.confirm(`¿Eliminar el archivo "${filename}"?`)) return;
    try {
      await axios.delete(`${API}/clinic/patients/${id}/files/${encodeURIComponent(filename)}`, { headers });
      toast.success('Archivo eliminado');
      setFiles(prev => prev.filter(f => f.name !== filename));
    } catch { toast.error('Error al eliminar archivo'); }
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
      <Button variant="ghost" className="mb-4 text-slate-600 hover:text-slate-900 -ml-2" onClick={() => navigate('/dashboard/pacientes')} data-testid="back-to-patients">
        <ArrowLeft className="w-4 h-4 mr-1.5" /> Volver a pacientes
      </Button>

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

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-5">
            <StatCard label="Visitas completadas" value={stats.completed_visits ?? 0} icon={Activity} color="bg-emerald-100 text-emerald-600" />
            <StatCard label="Total citas" value={stats.total_appointments ?? 0} icon={Calendar} color="bg-blue-100 text-blue-600" />
            <StatCard label="Última visita" value={stats.last_visit ? formatDate(stats.last_visit.starts_at) : '—'} icon={Clock} color="bg-amber-100 text-amber-600" />
            <StatCard label="Próxima cita" value={stats.next_appointment ? formatDate(stats.next_appointment.starts_at) : '—'} icon={CalendarPlus} color="bg-purple-100 text-purple-600" />
          </div>
        </CardContent>
      </Card>

      <Tabs value={activeTab} onValueChange={handleTabChange} data-testid="patient-tabs">
        <TabsList className="bg-slate-100 mb-4">
          <TabsTrigger value="general" data-testid="tab-general">Info General</TabsTrigger>
          <TabsTrigger value="history" data-testid="tab-history">Historial Clínico</TabsTrigger>
          <TabsTrigger value="prescriptions" data-testid="tab-prescriptions">Recetas</TabsTrigger>
          <TabsTrigger value="labs" data-testid="tab-labs">Órdenes Lab</TabsTrigger>
          <TabsTrigger value="files" data-testid="tab-files">Archivos ({files.length})</TabsTrigger>
        </TabsList>

        <TabsContent value="general"><GeneralTab patient={patient} /></TabsContent>

        <TabsContent value="history">
          {tabsLoading.history && !tabsLoaded.history ? (
            <div className="flex justify-center py-16" data-testid="history-loading"><div className="w-6 h-6 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" /></div>
          ) : (
            <HistoryTab
              patientId={id} medicalRecords={medicalRecords} doctors={doctors}
              doctorFilter={doctorFilter} setDoctorFilter={setDoctorFilter}
              dateFrom={dateFrom} setDateFrom={setDateFrom} dateTo={dateTo} setDateTo={setDateTo}
              expandedRecord={expandedRecord} setExpandedRecord={setExpandedRecord}
              appointments={appointments}
              showAddendum={showAddendum} setShowAddendum={setShowAddendum}
              addendumText={addendumText} setAddendumText={setAddendumText}
              onAddAddendum={handleAddAddendum}
            />
          )}
        </TabsContent>

        <TabsContent value="prescriptions">
          {tabsLoading.prescriptions && !tabsLoaded.prescriptions ? (
            <div className="flex justify-center py-16" data-testid="prescriptions-loading"><div className="w-6 h-6 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" /></div>
          ) : (
            <PrescriptionsTab patientId={id} prescriptions={prescriptions} headers={headers} />
          )}
        </TabsContent>
        <TabsContent value="labs">
          {tabsLoading.labs && !tabsLoaded.labs ? (
            <div className="flex justify-center py-16" data-testid="labs-loading"><div className="w-6 h-6 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" /></div>
          ) : (
            <LabsTab patientId={id} labOrders={labOrders} headers={headers} />
          )}
        </TabsContent>
        <TabsContent value="files">
          <FilesTab files={files} uploading={uploading} onUpload={handleFileUpload} onDownload={downloadFile} onDelete={deleteFile} />
        </TabsContent>
      </Tabs>

      <EditPatientSheet open={showEdit} onClose={() => setShowEdit(false)} form={editForm} updateField={updateField} onSave={saveEditForm} saving={savingEdit} />
    </div>
  );
}
