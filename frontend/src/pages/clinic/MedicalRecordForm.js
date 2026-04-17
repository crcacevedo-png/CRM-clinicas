import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
import { Badge } from '../../components/ui/badge';
import { Checkbox } from '../../components/ui/checkbox';
import { Separator } from '../../components/ui/separator';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '../../components/ui/collapsible';
import { toast } from 'sonner';
import {
  ArrowLeft, ChevronDown, ChevronUp, Save, CheckCircle, Activity,
  Heart, Thermometer, Wind, Droplets, Weight, Ruler, Search, X, AlertTriangle, FileStack
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const VITAL_RANGES = {
  blood_pressure_systolic: { min: 70, max: 180, unit: 'mmHg', label: 'PA Sistólica' },
  blood_pressure_diastolic: { min: 40, max: 120, unit: 'mmHg', label: 'PA Diastólica' },
  heart_rate: { min: 50, max: 120, unit: 'lpm', label: 'Frecuencia cardíaca' },
  respiratory_rate: { min: 10, max: 30, unit: 'rpm', label: 'Frecuencia respiratoria' },
  temperature: { min: 35.5, max: 38.0, unit: '°C', label: 'Temperatura' },
  oxygen_saturation: { min: 92, max: 100, unit: '%', label: 'SpO2' },
};

const SYSTEMS_REVIEW = {
  general: { label: 'General', items: ['Fiebre', 'Escalofríos', 'Fatiga', 'Pérdida de peso', 'Malestar general'] },
  cardiovascular: { label: 'Cardiovascular', items: ['Dolor torácico', 'Palpitaciones', 'Disnea de esfuerzo', 'Edema', 'Síncope'] },
  respiratory: { label: 'Respiratorio', items: ['Tos', 'Disnea', 'Sibilancias', 'Hemoptisis', 'Dolor pleurítico'] },
  gastrointestinal: { label: 'Gastrointestinal', items: ['Náuseas', 'Vómitos', 'Diarrea', 'Estreñimiento', 'Dolor abdominal', 'Pirosis'] },
  genitourinary: { label: 'Genitourinario', items: ['Disuria', 'Frecuencia', 'Urgencia', 'Hematuria', 'Incontinencia'] },
  musculoskeletal: { label: 'Musculoesquelético', items: ['Dolor articular', 'Rigidez', 'Debilidad muscular', 'Dolor lumbar'] },
  neurological: { label: 'Neurológico', items: ['Cefalea', 'Mareos', 'Parestesias', 'Convulsiones', 'Alteración conciencia'] },
  skin: { label: 'Piel', items: ['Erupciones', 'Prurito', 'Lesiones', 'Cambios de coloración'] },
  endocrine: { label: 'Endocrino', items: ['Poliuria', 'Polidipsia', 'Polifagia', 'Intolerancia al frío/calor'] },
};

const PHYSICAL_EXAM_SECTIONS = [
  { key: 'head', label: 'Cabeza y cara', placeholder: 'Normocéfalo, sin masas, sin lesiones...' },
  { key: 'neck', label: 'Cuello', placeholder: 'Sin adenopatías, tiroides normal, sin rigidez...' },
  { key: 'chest', label: 'Tórax', placeholder: 'Simétrico, murmullo vesicular normal, ruidos cardíacos rítmicos...' },
  { key: 'abdomen', label: 'Abdomen', placeholder: 'Blando, depresible, no doloroso, sin masas...' },
  { key: 'extremities', label: 'Extremidades', placeholder: 'Sin edema, pulsos presentes, movilidad conservada...' },
  { key: 'neurological', label: 'Neurológico', placeholder: 'Glasgow 15, pares craneales normales, fuerza conservada...' },
];

function Section({ title, icon: Icon, defaultOpen = false, children, badge }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger asChild>
        <button
          type="button"
          className="flex items-center justify-between w-full p-3 rounded-lg bg-slate-50 hover:bg-slate-100 transition-colors text-left"
          data-testid={`section-${title.toLowerCase().replace(/\s/g, '-')}`}
        >
          <div className="flex items-center gap-2">
            {Icon && <Icon className="w-4 h-4 text-teal-600" />}
            <span className="text-sm font-semibold text-slate-800">{title}</span>
            {badge}
          </div>
          {open ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
        </button>
      </CollapsibleTrigger>
      <CollapsibleContent className="pt-3 pb-1 px-1">
        {children}
      </CollapsibleContent>
    </Collapsible>
  );
}

function VitalInput({ label, icon: Icon, unit, value, onChange, range, name }) {
  const numVal = parseFloat(value);
  const outOfRange = !isNaN(numVal) && range && (numVal < range.min || numVal > range.max);
  return (
    <div className="space-y-1">
      <Label className="text-xs text-slate-600 flex items-center gap-1">
        {Icon && <Icon className="w-3 h-3" />} {label}
      </Label>
      <div className="relative">
        <Input
          type="number"
          step="any"
          value={value || ''}
          onChange={e => onChange(e.target.value)}
          className={`text-sm pr-12 ${outOfRange ? 'border-orange-400 bg-orange-50' : ''}`}
          data-testid={`vital-${name}`}
        />
        <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-slate-400">{unit}</span>
      </div>
      {outOfRange && (
        <p className="text-xs text-orange-600 flex items-center gap-1">
          <AlertTriangle className="w-3 h-3" /> Fuera de rango normal ({range.min}-{range.max})
        </p>
      )}
    </div>
  );
}

function ICD10Search({ selected, onSelect, onRemove, headers }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [showResults, setShowResults] = useState(false);
  const [searching, setSearching] = useState(false);
  const debounceRef = useRef(null);

  const search = useCallback(async (q) => {
    if (q.length < 2) { setResults([]); return; }
    setSearching(true);
    try {
      const res = await axios.get(`${API}/clinic/icd10/search?q=${encodeURIComponent(q)}&limit=15`, { headers });
      setResults(res.data || []);
    } catch { setResults([]); }
    finally { setSearching(false); }
  }, [headers]);

  const handleInput = (val) => {
    setQuery(val);
    setShowResults(true);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => search(val), 300);
  };

  const addDiagnosis = (code, type = 'secondary') => {
    if (selected.find(d => d.code === code.code)) return;
    const diagType = selected.length === 0 ? 'primary' : type;
    onSelect([...selected, { code: code.code, description: code.description_es, type: diagType }]);
    setQuery('');
    setShowResults(false);
  };

  return (
    <div className="space-y-2">
      <div className="relative">
        <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
        <Input
          value={query}
          onChange={e => handleInput(e.target.value)}
          onFocus={() => query.length >= 2 && setShowResults(true)}
          onBlur={() => setTimeout(() => setShowResults(false), 200)}
          placeholder="Buscar por código o descripción CIE-10..."
          className="pl-9 text-sm"
          data-testid="icd10-search-input"
        />
        {searching && <div className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" />}
      </div>

      {showResults && results.length > 0 && (
        <div className="absolute z-50 w-full max-h-48 overflow-y-auto bg-white border border-slate-200 rounded-lg shadow-lg" data-testid="icd10-results">
          {results.map(r => (
            <button
              key={r.id}
              type="button"
              className="w-full px-3 py-2 text-left hover:bg-teal-50 text-sm flex items-center gap-2 border-b border-slate-50 last:border-0"
              onMouseDown={(e) => { e.preventDefault(); addDiagnosis(r); }}
            >
              <Badge variant="outline" className="text-xs font-mono shrink-0">{r.code}</Badge>
              <span className="text-slate-700 truncate">{r.description_es}</span>
            </button>
          ))}
        </div>
      )}

      {selected.length > 0 && (
        <div className="space-y-1.5 mt-2">
          {selected.map((d, i) => (
            <div key={i} className={`flex items-center gap-2 p-2 rounded-md border ${d.type === 'primary' ? 'bg-teal-50 border-teal-200' : 'bg-slate-50 border-slate-200'}`}>
              <Badge variant="outline" className={`text-xs font-mono shrink-0 ${d.type === 'primary' ? 'bg-teal-100 text-teal-700' : ''}`}>
                {d.code}
              </Badge>
              <span className="text-sm text-slate-700 flex-1 truncate">{d.description}</span>
              {d.type === 'primary' && <Badge className="bg-teal-600 text-white text-xs">Principal</Badge>}
              {d.type !== 'primary' && (
                <button type="button" className="text-xs text-teal-600 hover:underline" onClick={() => {
                  const updated = selected.map((dd, j) => ({ ...dd, type: j === i ? 'primary' : 'secondary' }));
                  onSelect(updated);
                }}>Hacer principal</button>
              )}
              <button type="button" onClick={() => onRemove(i)} className="p-0.5 hover:bg-red-100 rounded">
                <X className="w-3.5 h-3.5 text-red-500" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function MedicalRecordForm() {
  const { patientId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { getAuthHeaders } = useAuth();
  const headers = getAuthHeaders();

  const appointmentId = searchParams.get('appointment_id');
  const recordId = searchParams.get('record_id');

  const [patient, setPatient] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [templates, setTemplates] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState(null);

  // Form state
  const [chiefComplaint, setChiefComplaint] = useState('');
  const [presentIllness, setPresentIllness] = useState('');
  const [reviewOfSystems, setReviewOfSystems] = useState({});
  const [vitals, setVitals] = useState({
    blood_pressure_systolic: '', blood_pressure_diastolic: '',
    heart_rate: '', respiratory_rate: '', temperature: '',
    oxygen_saturation: '', weight_kg: '', height_cm: '',
  });
  const [bmi, setBmi] = useState('');
  const [physicalExam, setPhysicalExam] = useState({});
  const [diagnoses, setDiagnoses] = useState([]);
  const [treatmentPlan, setTreatmentPlan] = useState('');
  const [procedures, setProcedures] = useState('');
  const [notes, setNotes] = useState('');
  const [privateNotes, setPrivateNotes] = useState('');
  const [isFinalized, setIsFinalized] = useState(false);

  // Auto-calculate BMI
  useEffect(() => {
    const w = parseFloat(vitals.weight_kg);
    const h = parseFloat(vitals.height_cm);
    if (w > 0 && h > 0) {
      const hm = h / 100;
      setBmi((w / (hm * hm)).toFixed(1));
    } else {
      setBmi('');
    }
  }, [vitals.weight_kg, vitals.height_cm]);

  useEffect(() => {
    const load = async () => {
      try {
        const [pRes, tRes] = await Promise.all([
          axios.get(`${API}/clinic/patients/${patientId}`, { headers }),
          axios.get(`${API}/clinic/templates`, { headers }),
        ]);
        setPatient(pRes.data.patient);
        setTemplates(tRes.data || []);

        if (recordId) {
          const rRes = await axios.get(`${API}/clinic/medical-records/${recordId}`, { headers });
          const r = rRes.data;
          setChiefComplaint(r.chief_complaint || '');
          setPresentIllness(r.present_illness || '');
          setReviewOfSystems(r.review_of_systems || {});
          setVitals({
            blood_pressure_systolic: r.blood_pressure_systolic?.toString() || '',
            blood_pressure_diastolic: r.blood_pressure_diastolic?.toString() || '',
            heart_rate: r.heart_rate?.toString() || '',
            respiratory_rate: r.respiratory_rate?.toString() || '',
            temperature: r.temperature?.toString() || '',
            oxygen_saturation: r.oxygen_saturation?.toString() || '',
            weight_kg: r.weight_kg?.toString() || '',
            height_cm: r.height_cm?.toString() || '',
          });
          setPhysicalExam(r.physical_exam || {});
          setDiagnoses(r.diagnoses || []);
          setTreatmentPlan(r.treatment_plan || '');
          setProcedures(r.procedures || '');
          setNotes(r.notes || '');
          setPrivateNotes(r.private_notes || '');
          setIsFinalized(r.status === 'finalized');
        }

        if (appointmentId && !recordId) {
          try {
            const aRes = await axios.get(`${API}/clinic/appointments/${appointmentId}`, { headers });
            if (aRes.data?.reason) setChiefComplaint(aRes.data.reason);
          } catch {}
        }
      } catch (err) {
        toast.error('Error al cargar datos');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [patientId, recordId, appointmentId]);

  const applyTemplate = (template) => {
    if (!template) return;
    const td = template.template_data || {};
    if (td.chief_complaint) setChiefComplaint(td.chief_complaint);
    if (td.present_illness) setPresentIllness(td.present_illness);
    if (td.review_of_systems) setReviewOfSystems(prev => ({ ...prev, ...td.review_of_systems }));
    if (td.physical_exam) setPhysicalExam(prev => ({ ...prev, ...td.physical_exam }));
    if (td.diagnoses) setDiagnoses(td.diagnoses);
    if (td.treatment_plan) setTreatmentPlan(td.treatment_plan);
    if (td.procedures) setProcedures(td.procedures);
    if (td.notes) setNotes(td.notes);
    setSelectedTemplate(template.id);
    toast.success(`Plantilla "${template.name}" aplicada`);
  };

  const buildPayload = (status) => {
    const payload = {
      patient_id: patientId,
      appointment_id: appointmentId || null,
      chief_complaint: chiefComplaint || null,
      present_illness: presentIllness || null,
      review_of_systems: reviewOfSystems,
      blood_pressure_systolic: vitals.blood_pressure_systolic ? parseInt(vitals.blood_pressure_systolic) : null,
      blood_pressure_diastolic: vitals.blood_pressure_diastolic ? parseInt(vitals.blood_pressure_diastolic) : null,
      heart_rate: vitals.heart_rate ? parseInt(vitals.heart_rate) : null,
      respiratory_rate: vitals.respiratory_rate ? parseInt(vitals.respiratory_rate) : null,
      temperature: vitals.temperature ? parseFloat(vitals.temperature) : null,
      oxygen_saturation: vitals.oxygen_saturation ? parseFloat(vitals.oxygen_saturation) : null,
      weight_kg: vitals.weight_kg ? parseFloat(vitals.weight_kg) : null,
      height_cm: vitals.height_cm ? parseFloat(vitals.height_cm) : null,
      bmi: bmi ? parseFloat(bmi) : null,
      physical_exam: physicalExam,
      diagnoses,
      treatment_plan: treatmentPlan || null,
      procedures: procedures || null,
      notes: notes || null,
      private_notes: privateNotes || null,
      status,
    };
    return payload;
  };

  const handleSave = async (status) => {
    if (status === 'finalized' && !chiefComplaint) {
      toast.error('El motivo de consulta es requerido para finalizar');
      return;
    }
    if (status === 'finalized' && diagnoses.length === 0) {
      toast.error('Debe agregar al menos un diagnóstico para finalizar');
      return;
    }
    setSaving(true);
    try {
      const payload = buildPayload(status);
      if (recordId) {
        await axios.put(`${API}/clinic/medical-records/${recordId}`, payload, { headers });
      } else {
        await axios.post(`${API}/clinic/medical-records`, payload, { headers });
      }
      toast.success(status === 'finalized' ? 'Consulta finalizada' : 'Borrador guardado');
      navigate(`/dashboard/pacientes/${patientId}`);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al guardar');
    } finally {
      setSaving(false);
    }
  };

  const toggleSystem = (system, item) => {
    setReviewOfSystems(prev => {
      const current = prev[system] || [];
      const exists = current.includes(item);
      return {
        ...prev,
        [system]: exists ? current.filter(i => i !== item) : [...current, item],
      };
    });
  };

  const updateVital = (key, val) => setVitals(prev => ({ ...prev, [key]: val }));
  const updateExam = (key, val) => setPhysicalExam(prev => ({ ...prev, [key]: val }));

  const bmiCategory = (val) => {
    const n = parseFloat(val);
    if (isNaN(n)) return null;
    if (n < 18.5) return { label: 'Bajo peso', color: 'text-blue-600' };
    if (n < 25) return { label: 'Normal', color: 'text-emerald-600' };
    if (n < 30) return { label: 'Sobrepeso', color: 'text-orange-600' };
    return { label: 'Obesidad', color: 'text-red-600' };
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-96">
        <div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="p-6 lg:p-8 max-w-4xl" data-testid="medical-record-form">
      <Button variant="ghost" className="mb-4 text-slate-600 hover:text-slate-900 -ml-2" onClick={() => navigate(`/dashboard/pacientes/${patientId}`)} data-testid="back-to-profile">
        <ArrowLeft className="w-4 h-4 mr-1.5" /> Volver al perfil
      </Button>

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-slate-900" data-testid="form-title">
            {recordId ? (isFinalized ? 'Consulta médica' : 'Editar consulta') : 'Nueva consulta médica'}
          </h1>
          {patient && (
            <p className="text-sm text-slate-500 mt-0.5">
              Paciente: <span className="font-medium text-slate-700">{patient.first_name} {patient.last_name}</span>
              {patient.national_id && <span className="ml-2">DPI: {patient.national_id}</span>}
            </p>
          )}
        </div>
        {isFinalized && <Badge className="bg-emerald-100 text-emerald-700 border-emerald-200">Finalizada</Badge>}
      </div>

      {/* Template selector - only for new records */}
      {!recordId && !isFinalized && templates.length > 0 && (
        <Card className="border border-slate-200 mb-4" data-testid="template-selector">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-3">
              <FileStack className="w-4 h-4 text-teal-600" />
              <span className="text-sm font-semibold text-slate-800">Usar plantilla</span>
              <span className="text-xs text-slate-400">Pre-llena el formulario con datos de la plantilla</span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
              {(() => {
                const categories = { general: 'General', especialidad: 'Especialidades', urgencia: 'Urgencia', cronica: 'Crónicas', procedimiento: 'Procedimientos' };
                const grouped = {};
                templates.forEach(t => {
                  const cat = t.category || 'general';
                  if (!grouped[cat]) grouped[cat] = [];
                  grouped[cat].push(t);
                });
                return Object.entries(grouped).map(([cat, items]) => (
                  <div key={cat} className="space-y-1">
                    <p className="text-xs font-semibold text-slate-500 uppercase">{categories[cat] || cat}</p>
                    {items.map(t => (
                      <button
                        key={t.id}
                        type="button"
                        onClick={() => applyTemplate(t)}
                        className={`w-full text-left px-2.5 py-1.5 text-xs rounded-md border transition-all
                          ${selectedTemplate === t.id
                            ? 'bg-teal-50 border-teal-300 text-teal-700 font-medium'
                            : 'bg-white border-slate-200 text-slate-600 hover:border-teal-300 hover:bg-teal-50/50'
                          }`}
                        data-testid={`template-${t.id}`}
                      >
                        {t.name}
                        {t.clinic_id && <span className="text-xs text-teal-500 ml-1">(Clínica)</span>}
                      </button>
                    ))}
                  </div>
                ));
              })()}
            </div>
          </CardContent>
        </Card>
      )}

      <div className="space-y-3">
        {/* 1. Motivo de consulta */}
        <Section title="Motivo de consulta" defaultOpen={true}>
          <div className="space-y-3">
            <div>
              <Label className="text-xs text-slate-600">Motivo de consulta <span className="text-red-500">*</span></Label>
              <Textarea
                value={chiefComplaint}
                onChange={e => setChiefComplaint(e.target.value)}
                placeholder="Describa el motivo principal de la consulta..."
                className="text-sm mt-1 min-h-[60px]"
                disabled={isFinalized}
                data-testid="chief-complaint"
              />
            </div>
            <div>
              <Label className="text-xs text-slate-600">Historia de la enfermedad actual</Label>
              <Textarea
                value={presentIllness}
                onChange={e => setPresentIllness(e.target.value)}
                placeholder="Descripción cronológica de síntomas, evolución, tratamientos previos..."
                className="text-sm mt-1 min-h-[80px]"
                disabled={isFinalized}
                data-testid="present-illness"
              />
            </div>
          </div>
        </Section>

        {/* 2. Revisión por sistemas */}
        <Section title="Revisión por sistemas">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {Object.entries(SYSTEMS_REVIEW).map(([sysKey, sys]) => {
              const checked = reviewOfSystems[sysKey] || [];
              return (
                <div key={sysKey} className="space-y-1.5">
                  <p className="text-xs font-semibold text-slate-700">{sys.label}</p>
                  {sys.items.map(item => (
                    <label key={item} className="flex items-center gap-2 text-sm text-slate-600 cursor-pointer hover:text-slate-800">
                      <Checkbox
                        checked={checked.includes(item)}
                        onCheckedChange={() => toggleSystem(sysKey, item)}
                        disabled={isFinalized}
                      />
                      {item}
                    </label>
                  ))}
                </div>
              );
            })}
          </div>
        </Section>

        {/* 3. Signos vitales */}
        <Section
          title="Signos vitales"
          icon={Activity}
          badge={bmi ? (
            <span className={`text-xs font-medium ml-2 ${bmiCategory(bmi)?.color || ''}`}>
              IMC: {bmi} ({bmiCategory(bmi)?.label})
            </span>
          ) : null}
        >
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <VitalInput label="PA Sistólica" icon={Heart} unit="mmHg" name="blood_pressure_systolic"
              value={vitals.blood_pressure_systolic} onChange={v => updateVital('blood_pressure_systolic', v)}
              range={VITAL_RANGES.blood_pressure_systolic} />
            <VitalInput label="PA Diastólica" icon={Heart} unit="mmHg" name="blood_pressure_diastolic"
              value={vitals.blood_pressure_diastolic} onChange={v => updateVital('blood_pressure_diastolic', v)}
              range={VITAL_RANGES.blood_pressure_diastolic} />
            <VitalInput label="Frec. Cardíaca" icon={Activity} unit="lpm" name="heart_rate"
              value={vitals.heart_rate} onChange={v => updateVital('heart_rate', v)}
              range={VITAL_RANGES.heart_rate} />
            <VitalInput label="Frec. Respiratoria" icon={Wind} unit="rpm" name="respiratory_rate"
              value={vitals.respiratory_rate} onChange={v => updateVital('respiratory_rate', v)}
              range={VITAL_RANGES.respiratory_rate} />
            <VitalInput label="Temperatura" icon={Thermometer} unit="°C" name="temperature"
              value={vitals.temperature} onChange={v => updateVital('temperature', v)}
              range={VITAL_RANGES.temperature} />
            <VitalInput label="SpO2" icon={Droplets} unit="%" name="oxygen_saturation"
              value={vitals.oxygen_saturation} onChange={v => updateVital('oxygen_saturation', v)}
              range={VITAL_RANGES.oxygen_saturation} />
            <VitalInput label="Peso" icon={Weight} unit="kg" name="weight_kg"
              value={vitals.weight_kg} onChange={v => updateVital('weight_kg', v)} />
            <VitalInput label="Talla" icon={Ruler} unit="cm" name="height_cm"
              value={vitals.height_cm} onChange={v => updateVital('height_cm', v)} />
          </div>
          {bmi && (
            <div className="mt-3 p-2 bg-slate-50 rounded-md">
              <p className="text-sm text-slate-600">
                IMC calculado: <span className={`font-bold ${bmiCategory(bmi)?.color || ''}`}>{bmi} — {bmiCategory(bmi)?.label}</span>
              </p>
            </div>
          )}
        </Section>

        {/* 4. Examen físico */}
        <Section title="Examen físico por región">
          <div className="space-y-3">
            {PHYSICAL_EXAM_SECTIONS.map(sec => (
              <div key={sec.key}>
                <Label className="text-xs text-slate-600">{sec.label}</Label>
                <Textarea
                  value={physicalExam[sec.key] || ''}
                  onChange={e => updateExam(sec.key, e.target.value)}
                  placeholder={sec.placeholder}
                  className="text-sm mt-1 min-h-[50px]"
                  disabled={isFinalized}
                />
              </div>
            ))}
          </div>
        </Section>

        {/* 5. Diagnóstico */}
        <Section title="Diagnóstico CIE-10" defaultOpen={true}>
          <div className="relative">
            <ICD10Search
              selected={diagnoses}
              onSelect={setDiagnoses}
              onRemove={i => setDiagnoses(prev => prev.filter((_, j) => j !== i))}
              headers={headers}
            />
          </div>
        </Section>

        {/* 6. Plan de tratamiento */}
        <Section title="Plan de tratamiento">
          <div className="space-y-3">
            <div>
              <Label className="text-xs text-slate-600">Plan terapéutico</Label>
              <Textarea
                value={treatmentPlan}
                onChange={e => setTreatmentPlan(e.target.value)}
                placeholder="Indicaciones, medicamentos, dosis, frecuencia, duración..."
                className="text-sm mt-1 min-h-[80px]"
                disabled={isFinalized}
                data-testid="treatment-plan"
              />
            </div>
            <div>
              <Label className="text-xs text-slate-600">Procedimientos realizados</Label>
              <Textarea
                value={procedures}
                onChange={e => setProcedures(e.target.value)}
                placeholder="Procedimientos, curaciones, estudios realizados en consulta..."
                className="text-sm mt-1 min-h-[60px]"
                disabled={isFinalized}
              />
            </div>
          </div>
        </Section>

        {/* 7. Notas */}
        <Section title="Notas">
          <div className="space-y-3">
            <div>
              <Label className="text-xs text-slate-600">Notas adicionales</Label>
              <Textarea
                value={notes}
                onChange={e => setNotes(e.target.value)}
                placeholder="Notas visibles para el equipo médico..."
                className="text-sm mt-1 min-h-[60px]"
                disabled={isFinalized}
                data-testid="notes-field"
              />
            </div>
            <div>
              <Label className="text-xs text-slate-600 flex items-center gap-1">
                Notas privadas del médico
                <Badge variant="outline" className="text-xs ml-1 bg-amber-50 text-amber-700 border-amber-200">Solo visible para doctores</Badge>
              </Label>
              <Textarea
                value={privateNotes}
                onChange={e => setPrivateNotes(e.target.value)}
                placeholder="Notas privadas, solo visibles para médicos..."
                className="text-sm mt-1 min-h-[60px] border-amber-200"
                disabled={isFinalized}
                data-testid="private-notes-field"
              />
            </div>
          </div>
        </Section>
      </div>

      {/* Action buttons */}
      {!isFinalized && (
        <div className="flex items-center justify-end gap-3 mt-6 pt-4 border-t" data-testid="form-actions">
          <Button variant="outline" onClick={() => navigate(`/dashboard/pacientes/${patientId}`)} data-testid="cancel-btn">
            Cancelar
          </Button>
          <Button variant="outline" onClick={() => handleSave('draft')} disabled={saving} data-testid="save-draft-btn">
            <Save className="w-4 h-4 mr-1.5" /> Guardar borrador
          </Button>
          <Button className="bg-teal-600 hover:bg-teal-700" onClick={() => handleSave('finalized')} disabled={saving} data-testid="finalize-btn">
            <CheckCircle className="w-4 h-4 mr-1.5" /> Finalizar consulta
          </Button>
        </div>
      )}
    </div>
  );
}
