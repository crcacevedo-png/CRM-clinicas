import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
import { Badge } from '../../components/ui/badge';
import { Checkbox } from '../../components/ui/checkbox';
import { toast } from 'sonner';
import { ArrowLeft, CheckCircle, Search, X, FlaskConical, AlertCircle } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function PatientSearch({ value, onSelect, headers }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [show, setShow] = useState(false);
  const debounceRef = useRef(null);

  const search = useCallback(async (q) => {
    if (q.length < 2) { setResults([]); return; }
    try {
      const res = await axios.get(`${API}/clinic/patients/search?q=${encodeURIComponent(q)}`, { headers });
      setResults(res.data || []);
    } catch { setResults([]); }
  }, [headers]);

  const handleInput = (val) => {
    setQuery(val);
    setShow(true);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => search(val), 300);
  };

  return (
    <div className="relative">
      {value ? (
        <div className="flex items-center gap-2 p-2 bg-teal-50 border border-teal-200 rounded-md">
          <span className="text-sm font-medium text-teal-800">{value.first_name} {value.last_name}</span>
          {value.national_id && <span className="text-xs text-teal-600">DPI: {value.national_id}</span>}
          <button type="button" onClick={() => onSelect(null)} className="ml-auto p-0.5 hover:bg-teal-200 rounded">
            <X className="w-3.5 h-3.5 text-teal-600" />
          </button>
        </div>
      ) : (
        <>
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <Input
            value={query} onChange={e => handleInput(e.target.value)}
            onFocus={() => query.length >= 2 && setShow(true)}
            onBlur={() => setTimeout(() => setShow(false), 200)}
            placeholder="Buscar paciente por nombre, DPI..."
            className="pl-9 text-sm" data-testid="patient-search-input"
          />
        </>
      )}
      {show && results.length > 0 && (
        <div className="absolute z-50 w-full max-h-48 overflow-y-auto bg-white border border-slate-200 rounded-lg shadow-lg mt-1">
          {results.map(p => (
            <button key={p.id} type="button" className="w-full px-3 py-2 text-left hover:bg-teal-50 text-sm border-b border-slate-50 last:border-0"
              onMouseDown={e => { e.preventDefault(); onSelect(p); setQuery(''); setShow(false); }}>
              <span className="font-medium">{p.first_name} {p.last_name}</span>
              {p.national_id && <span className="text-xs text-slate-400 ml-2">DPI: {p.national_id}</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function NewLabOrderPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { getAuthHeaders } = useAuth();
  const headers = getAuthHeaders();

  const patientIdParam = searchParams.get('patient_id');

  const [patient, setPatient] = useState(null);
  const [diagnosis, setDiagnosis] = useState('');
  const [priority, setPriority] = useState('routine');
  const [specialInstructions, setSpecialInstructions] = useState('');
  const [notes, setNotes] = useState('');
  const [studies, setStudies] = useState([]);
  const [selectedStudies, setSelectedStudies] = useState(new Set());
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [searchFilter, setSearchFilter] = useState('');

  useEffect(() => {
    const load = async () => {
      try {
        const res = await axios.get(`${API}/clinic/lab-studies`, { headers });
        setStudies(res.data || []);
        if (patientIdParam) {
          const pRes = await axios.get(`${API}/clinic/patients/${patientIdParam}`, { headers });
          setPatient(pRes.data.patient);
        }
      } catch {
        toast.error('Error al cargar estudios');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [patientIdParam]);

  const toggleStudy = (studyId) => {
    setSelectedStudies(prev => {
      const next = new Set(prev);
      if (next.has(studyId)) next.delete(studyId);
      else next.add(studyId);
      return next;
    });
  };

  const grouped = {};
  studies.forEach(s => {
    const cat = s.category || 'Otros';
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(s);
  });

  // Filter studies by search
  const filteredGrouped = {};
  if (searchFilter.trim()) {
    const q = searchFilter.toLowerCase();
    Object.entries(grouped).forEach(([cat, items]) => {
      const filtered = items.filter(s =>
        s.name.toLowerCase().includes(q) || cat.toLowerCase().includes(q)
      );
      if (filtered.length > 0) filteredGrouped[cat] = filtered;
    });
  }
  const displayGrouped = searchFilter.trim() ? filteredGrouped : grouped;

  const handleSubmit = async () => {
    if (!patient) { toast.error('Seleccione un paciente'); return; }
    if (selectedStudies.size === 0) { toast.error('Seleccione al menos un estudio'); return; }

    setSaving(true);
    try {
      const itemsList = studies
        .filter(s => selectedStudies.has(s.id))
        .map(s => ({
          study_id: s.id,
          study_name: s.name,
          category: s.category || '',
        }));

      const payload = {
        patient_id: patient.id,
        presumptive_diagnosis: diagnosis || null,
        special_instructions: specialInstructions || null,
        priority,
        notes: notes || null,
        items: itemsList,
        status: 'pending',
      };

      const res = await axios.post(`${API}/clinic/lab-orders`, payload, { headers });
      toast.success('Orden de laboratorio creada');
      if (res.data.pdf_url) window.open(res.data.pdf_url, '_blank');
      navigate('/dashboard/laboratorio');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al crear orden');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-96">
        <div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="p-6 lg:p-8 max-w-5xl" data-testid="new-lab-order-page">
      <Button variant="ghost" className="mb-4 text-slate-600 hover:text-slate-900 -ml-2" onClick={() => navigate('/dashboard/laboratorio')} data-testid="back-to-lab-orders">
        <ArrowLeft className="w-4 h-4 mr-1.5" /> Volver a órdenes
      </Button>

      <h1 className="text-xl font-bold text-slate-900 mb-5" data-testid="form-title">Nueva orden de laboratorio</h1>

      {/* Patient, Diagnosis, Priority */}
      <Card className="border border-slate-200 mb-4">
        <CardContent className="p-4 space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label className="text-xs text-slate-600">Paciente <span className="text-red-500">*</span></Label>
              <div className="mt-1"><PatientSearch value={patient} onSelect={setPatient} headers={headers} /></div>
            </div>
            <div>
              <Label className="text-xs text-slate-600">Diagnóstico presuntivo</Label>
              <Input value={diagnosis} onChange={e => setDiagnosis(e.target.value)} placeholder="Diagnóstico presuntivo" className="mt-1 text-sm" data-testid="diagnosis-input" />
            </div>
          </div>
          <div>
            <Label className="text-xs text-slate-600">Prioridad</Label>
            <div className="flex gap-4 mt-1.5">
              <label className={`flex items-center gap-2 px-4 py-2 rounded-lg border cursor-pointer transition-all ${priority === 'routine' ? 'bg-slate-100 border-slate-400' : 'border-slate-200 hover:border-slate-300'}`}>
                <input type="radio" name="priority" value="routine" checked={priority === 'routine'} onChange={e => setPriority(e.target.value)} className="accent-teal-600" data-testid="priority-routine" />
                <span className="text-sm">Rutina</span>
              </label>
              <label className={`flex items-center gap-2 px-4 py-2 rounded-lg border cursor-pointer transition-all ${priority === 'urgent' ? 'bg-red-50 border-red-400' : 'border-slate-200 hover:border-slate-300'}`}>
                <input type="radio" name="priority" value="urgent" checked={priority === 'urgent'} onChange={e => setPriority(e.target.value)} className="accent-red-600" data-testid="priority-urgent" />
                <AlertCircle className="w-3.5 h-3.5 text-red-500" />
                <span className="text-sm text-red-700 font-medium">Urgente</span>
              </label>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Studies Selection */}
      <Card className="border border-slate-200 mb-4" data-testid="studies-card">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-semibold text-slate-700 flex items-center gap-2">
              <FlaskConical className="w-4 h-4 text-teal-500" /> Estudios solicitados ({selectedStudies.size})
            </CardTitle>
          </div>
          <div className="relative mt-2">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <Input value={searchFilter} onChange={e => setSearchFilter(e.target.value)} placeholder="Filtrar estudios..." className="pl-9 text-sm" data-testid="study-search" />
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {Object.entries(displayGrouped).map(([cat, catStudies]) => (
              <div key={cat} className="space-y-1" data-testid={`category-${cat}`}>
                <p className="text-xs font-bold text-slate-700 uppercase tracking-wide border-b border-slate-100 pb-1 mb-1">{cat}</p>
                {catStudies.map(s => {
                  const isSelected = selectedStudies.has(s.id);
                  return (
                    <div key={s.id} className={`rounded-md px-2 py-1.5 transition-colors ${isSelected ? 'bg-teal-50' : ''}`}>
                      <label className="flex items-start gap-2 cursor-pointer">
                        <Checkbox
                          checked={isSelected}
                          onCheckedChange={() => toggleStudy(s.id)}
                          className="mt-0.5"
                          data-testid={`study-checkbox-${s.id}`}
                        />
                        <div className="flex-1">
                          <span className={`text-sm ${isSelected ? 'font-medium text-teal-800' : 'text-slate-700'}`}>{s.name}</span>
                          {s.preparation && (
                            <p className="text-xs text-slate-400 mt-0.5 leading-tight">{s.preparation}</p>
                          )}
                        </div>
                      </label>
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
          {Object.keys(displayGrouped).length === 0 && (
            <p className="text-sm text-slate-400 text-center py-6">No se encontraron estudios</p>
          )}
        </CardContent>
      </Card>

      {/* Instructions & Notes */}
      <Card className="border border-slate-200 mb-4">
        <CardContent className="p-4 space-y-3">
          <div>
            <Label className="text-xs text-slate-600">Indicaciones especiales</Label>
            <Textarea value={specialInstructions} onChange={e => setSpecialInstructions(e.target.value)} placeholder="Indicaciones especiales para el laboratorio..." className="text-sm mt-1 min-h-[60px]" data-testid="special-instructions" />
          </div>
          <div>
            <Label className="text-xs text-slate-600">Notas</Label>
            <Textarea value={notes} onChange={e => setNotes(e.target.value)} placeholder="Notas adicionales..." className="text-sm mt-1 min-h-[50px]" data-testid="notes-field" />
          </div>
        </CardContent>
      </Card>

      {/* Actions */}
      <div className="flex items-center justify-end gap-3 pt-2" data-testid="lab-order-actions">
        <Button variant="outline" onClick={() => navigate('/dashboard/laboratorio')} data-testid="cancel-btn">Cancelar</Button>
        <Button className="bg-teal-600 hover:bg-teal-700" onClick={handleSubmit} disabled={saving} data-testid="submit-btn">
          <CheckCircle className="w-4 h-4 mr-1.5" /> {saving ? 'Creando...' : 'Crear orden'}
        </Button>
      </div>
    </div>
  );
}
