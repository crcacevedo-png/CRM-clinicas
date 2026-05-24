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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../components/ui/dialog';
import { toast } from 'sonner';
import {
  ArrowLeft, Plus, Trash2, Save, CheckCircle, Send, Search, Pill, X
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const ROUTES = [
  { value: 'oral', label: 'Oral' },
  { value: 'intramuscular', label: 'Intramuscular' },
  { value: 'intravenosa', label: 'Intravenosa' },
  { value: 'topica', label: 'Tópica' },
  { value: 'inhalada', label: 'Inhalada' },
  { value: 'sublingual', label: 'Sublingual' },
  { value: 'rectal', label: 'Rectal' },
  { value: 'oftalmica', label: 'Oftálmica' },
];

const emptyItem = () => ({
  medication_name: '', presentation: '', dosage: '',
  frequency: '', route: 'oral', duration: '', instructions: '',
  _presentations: [], _searchResults: [], _searchQuery: '', _showSearch: false,
});

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
            value={query}
            onChange={e => handleInput(e.target.value)}
            onFocus={() => query.length >= 2 && setShow(true)}
            onBlur={() => setTimeout(() => setShow(false), 200)}
            placeholder="Buscar paciente por nombre, DPI..."
            className="pl-9 text-sm"
            data-testid="patient-search-input"
          />
        </>
      )}
      {show && results.length > 0 && (
        <div className="absolute z-50 w-full max-h-48 overflow-y-auto bg-white border border-slate-200 rounded-lg shadow-lg mt-1" data-testid="patient-search-results">
          {results.map(p => (
            <button
              key={p.id}
              type="button"
              className="w-full px-3 py-2 text-left hover:bg-teal-50 text-sm border-b border-slate-50 last:border-0"
              onMouseDown={e => { e.preventDefault(); onSelect(p); setQuery(''); setShow(false); }}
            >
              <span className="font-medium">{p.first_name} {p.last_name}</span>
              {p.national_id && <span className="text-xs text-slate-400 ml-2">DPI: {p.national_id}</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function MedSearch({ item, index, onUpdate, headers }) {
  const debounceRef = useRef(null);

  const search = useCallback(async (q) => {
    if (q.length < 2) return;
    try {
      const res = await axios.get(`${API}/clinic/medications/search?q=${encodeURIComponent(q)}`, { headers });
      onUpdate(index, { _searchResults: res.data || [], _showSearch: true });
    } catch {}
  }, [headers, index, onUpdate]);

  const handleInput = (val) => {
    onUpdate(index, { medication_name: val, _searchQuery: val, _showSearch: true });
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => search(val), 300);
  };

  const selectMed = (med) => {
    onUpdate(index, {
      medication_name: `${med.generic_name}${med.brand_name ? ` (${med.brand_name})` : ''}`,
      _presentations: med.presentations || [],
      _showSearch: false,
      _searchResults: [],
    });
  };

  return (
    <div className="relative">
      <Input
        value={item.medication_name}
        onChange={e => handleInput(e.target.value)}
        onFocus={() => item._searchQuery?.length >= 2 && onUpdate(index, { _showSearch: true })}
        onBlur={() => setTimeout(() => onUpdate(index, { _showSearch: false }), 200)}
        placeholder="Buscar medicamento..."
        className="text-sm"
        data-testid={`med-name-${index}`}
      />
      {item._showSearch && item._searchResults?.length > 0 && (
        <div className="absolute z-50 w-full max-h-40 overflow-y-auto bg-white border border-slate-200 rounded-lg shadow-lg mt-1">
          {item._searchResults.map(m => (
            <button
              key={m.id}
              type="button"
              className="w-full px-3 py-1.5 text-left hover:bg-teal-50 text-sm border-b border-slate-50 last:border-0"
              onMouseDown={e => { e.preventDefault(); selectMed(m); }}
            >
              <span className="font-medium">{m.generic_name}</span>
              {m.brand_name && <span className="text-xs text-slate-400 ml-1">({m.brand_name})</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function NewPrescriptionPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { getAuthHeaders } = useAuth();
  const headers = getAuthHeaders();

  const editId = searchParams.get('edit');
  const duplicateId = searchParams.get('duplicate');
  const patientIdParam = searchParams.get('patient_id');

  const [patient, setPatient] = useState(null);
  const [diagnosis, setDiagnosis] = useState('');
  const [generalInstructions, setGeneralInstructions] = useState('');
  const [items, setItems] = useState([emptyItem()]);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(!!editId || !!patientIdParam || !!duplicateId);
  const [showNewMed, setShowNewMed] = useState(false);
  const [newMedForm, setNewMedForm] = useState({ generic_name: '', brand_name: '', presentations: '', category: '' });

  useEffect(() => {
    const load = async () => {
      try {
        if (editId) {
          const res = await axios.get(`${API}/clinic/prescriptions/${editId}`, { headers });
          const p = res.data;
          setPatient(p.patient);
          setDiagnosis(p.diagnosis || '');
          setGeneralInstructions(p.general_instructions || '');
          setItems((p.items || []).map(it => ({
            ...it,
            _presentations: [], _searchResults: [], _searchQuery: '', _showSearch: false,
          })));
          if (p.items?.length === 0) setItems([emptyItem()]);
        }
        if (duplicateId) {
          const res = await axios.get(`${API}/clinic/prescriptions/${duplicateId}`, { headers });
          const p = res.data;
          setPatient(p.patient);
          setDiagnosis(p.diagnosis || '');
          setGeneralInstructions(p.general_instructions || '');
          setItems((p.items || []).map(it => ({
            medication_name: it.medication_name || '',
            presentation: it.presentation || '',
            dosage: it.dosage || '',
            frequency: it.frequency || '',
            route: it.route || 'oral',
            duration: it.duration || '',
            instructions: it.instructions || '',
            _presentations: [], _searchResults: [], _searchQuery: '', _showSearch: false,
          })));
          if (p.items?.length === 0) setItems([emptyItem()]);
        }
        if (patientIdParam && !editId && !duplicateId) {
          const res = await axios.get(`${API}/clinic/patients/${patientIdParam}`, { headers });
          setPatient(res.data.patient);
        }
      } catch {
        toast.error('Error al cargar datos');
      } finally {
        setLoading(false);
      }
    };
    if (editId || patientIdParam || duplicateId) load();
  }, [editId, patientIdParam, duplicateId]);

  const updateItem = useCallback((index, updates) => {
    setItems(prev => prev.map((it, i) => i === index ? { ...it, ...updates } : it));
  }, []);

  const addItem = () => setItems(prev => [...prev, emptyItem()]);
  const removeItem = (index) => {
    if (items.length <= 1) return;
    setItems(prev => prev.filter((_, i) => i !== index));
  };

  const handleSave = async (status) => {
    if (!patient) { toast.error('Seleccione un paciente'); return; }
    if (items.every(it => !it.medication_name.trim())) { toast.error('Agregue al menos un medicamento'); return; }

    setSaving(true);
    try {
      const payload = {
        patient_id: patient.id,
        diagnosis: diagnosis || null,
        general_instructions: generalInstructions || null,
        items: items.filter(it => it.medication_name.trim()).map(it => ({
          medication_name: it.medication_name,
          presentation: it.presentation || null,
          dosage: it.dosage || null,
          frequency: it.frequency || null,
          route: it.route || null,
          duration: it.duration || null,
          instructions: it.instructions || null,
        })),
        status,
      };

      let res;
      if (editId) {
        res = await axios.put(`${API}/clinic/prescriptions/${editId}`, payload, { headers });
      } else {
        res = await axios.post(`${API}/clinic/prescriptions`, payload, { headers });
      }

      if (status === 'issued' && res.data.pdf_url) {
        const hasEmail = patient?.email && patient.email.includes('@');
        toast.success(hasEmail
          ? `Receta emitida — PDF generado y enviado por email a ${patient.email}`
          : 'Receta emitida y PDF generado (paciente sin email registrado)');
        window.open(res.data.pdf_url, '_blank');
      } else {
        toast.success(status === 'issued' ? 'Receta emitida' : 'Borrador guardado');
      }
      navigate('/dashboard/recetas');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al guardar receta');
    } finally {
      setSaving(false);
    }
  };

  const handleSendWhatsApp = async () => {
    if (!patient) { toast.error('Seleccione un paciente'); return; }
    setSaving(true);
    try {
      const payload = {
        patient_id: patient.id,
        diagnosis: diagnosis || null,
        general_instructions: generalInstructions || null,
        items: items.filter(it => it.medication_name.trim()).map(it => ({
          medication_name: it.medication_name,
          presentation: it.presentation || null,
          dosage: it.dosage || null,
          frequency: it.frequency || null,
          route: it.route || null,
          duration: it.duration || null,
          instructions: it.instructions || null,
        })),
        status: 'issued',
      };

      let res;
      if (editId) {
        res = await axios.put(`${API}/clinic/prescriptions/${editId}`, payload, { headers });
      } else {
        res = await axios.post(`${API}/clinic/prescriptions`, payload, { headers });
      }

      const prescId = res.data.id || editId;
      await axios.put(`${API}/clinic/prescriptions/${prescId}/send`, {}, { headers });

      toast.success('Receta emitida y marcada para envío por WhatsApp');
      if (res.data.pdf_url) window.open(res.data.pdf_url, '_blank');
      navigate('/dashboard/recetas');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error');
    } finally {
      setSaving(false);
    }
  };

  const handleCreateMed = async () => {
    if (!newMedForm.generic_name.trim()) { toast.error('Nombre genérico requerido'); return; }
    try {
      await axios.post(`${API}/clinic/medications`, newMedForm, { headers });
      toast.success('Medicamento registrado');
      setShowNewMed(false);
      setNewMedForm({ generic_name: '', brand_name: '', presentations: '', category: '' });
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al crear medicamento');
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
    <div className="p-6 lg:p-8 max-w-5xl" data-testid="new-prescription-page">
      <Button variant="ghost" className="mb-4 text-slate-600 hover:text-slate-900 -ml-2" onClick={() => navigate('/dashboard/recetas')} data-testid="back-to-prescriptions">
        <ArrowLeft className="w-4 h-4 mr-1.5" /> Volver a recetas
      </Button>

      <h1 className="text-xl font-bold text-slate-900 mb-5" data-testid="form-title">
        {editId ? 'Editar receta' : duplicateId ? 'Duplicar receta' : 'Nueva receta médica'}
      </h1>

      {/* Patient & Diagnosis */}
      <Card className="border border-slate-200 mb-4">
        <CardContent className="p-4 space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label className="text-xs text-slate-600">Paciente <span className="text-red-500">*</span></Label>
              <div className="mt-1">
                <PatientSearch value={patient} onSelect={setPatient} headers={headers} />
              </div>
            </div>
            <div>
              <Label className="text-xs text-slate-600">Diagnóstico</Label>
              <Input value={diagnosis} onChange={e => setDiagnosis(e.target.value)} placeholder="Diagnóstico o motivo de receta" className="mt-1 text-sm" data-testid="diagnosis-input" />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Medications Table */}
      <Card className="border border-slate-200 mb-4" data-testid="medications-card">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-semibold text-slate-700 flex items-center gap-2">
              <Pill className="w-4 h-4 text-teal-500" /> Medicamentos ({items.filter(i => i.medication_name.trim()).length})
            </CardTitle>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" className="text-xs" onClick={() => setShowNewMed(true)} data-testid="register-med-btn">
                Registrar medicamento
              </Button>
              <Button variant="outline" size="sm" className="text-xs" onClick={addItem} data-testid="add-med-btn">
                <Plus className="w-3.5 h-3.5 mr-1" /> Agregar medicamento
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {items.map((item, idx) => (
            <div key={idx} className="p-3 border border-slate-200 rounded-lg bg-slate-50/50 space-y-2" data-testid={`med-row-${idx}`}>
              <div className="flex items-start gap-2">
                <Badge className="bg-teal-600 text-white mt-1 shrink-0">{idx + 1}</Badge>
                <div className="flex-1 grid grid-cols-1 md:grid-cols-2 gap-2">
                  <div>
                    <Label className="text-xs text-slate-500">Medicamento *</Label>
                    <MedSearch item={item} index={idx} onUpdate={updateItem} headers={headers} />
                  </div>
                  <div>
                    <Label className="text-xs text-slate-500">Presentación</Label>
                    {item._presentations?.length > 0 ? (
                      <Select value={item.presentation} onValueChange={v => updateItem(idx, { presentation: v })}>
                        <SelectTrigger className="text-sm" data-testid={`med-presentation-${idx}`}>
                          <SelectValue placeholder="Seleccionar" />
                        </SelectTrigger>
                        <SelectContent>
                          {item._presentations.map(p => (
                            <SelectItem key={p} value={p}>{p}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    ) : (
                      <Input value={item.presentation} onChange={e => updateItem(idx, { presentation: e.target.value })} placeholder="Ej: Tabletas 500mg" className="text-sm" data-testid={`med-presentation-${idx}`} />
                    )}
                  </div>
                </div>
                {items.length > 1 && (
                  <Button variant="ghost" size="sm" className="h-7 w-7 p-0 mt-4 shrink-0 hover:text-red-600" onClick={() => removeItem(idx)} data-testid={`remove-med-${idx}`}>
                    <Trash2 className="w-3.5 h-3.5" />
                  </Button>
                )}
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2 ml-8">
                <div>
                  <Label className="text-xs text-slate-500">Dosis</Label>
                  <Input value={item.dosage} onChange={e => updateItem(idx, { dosage: e.target.value })} placeholder="500mg" className="text-sm" data-testid={`med-dosage-${idx}`} />
                </div>
                <div>
                  <Label className="text-xs text-slate-500">Frecuencia</Label>
                  <Input value={item.frequency} onChange={e => updateItem(idx, { frequency: e.target.value })} placeholder="Cada 8 horas" className="text-sm" data-testid={`med-frequency-${idx}`} />
                </div>
                <div>
                  <Label className="text-xs text-slate-500">Vía</Label>
                  <Select value={item.route} onValueChange={v => updateItem(idx, { route: v })}>
                    <SelectTrigger className="text-sm" data-testid={`med-route-${idx}`}>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {ROUTES.map(r => (
                        <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-xs text-slate-500">Duración</Label>
                  <Input value={item.duration} onChange={e => updateItem(idx, { duration: e.target.value })} placeholder="7 días" className="text-sm" data-testid={`med-duration-${idx}`} />
                </div>
              </div>
              <div className="ml-8">
                <Label className="text-xs text-slate-500">Instrucciones especiales</Label>
                <Input value={item.instructions} onChange={e => updateItem(idx, { instructions: e.target.value })} placeholder="Tomar con alimentos, evitar alcohol..." className="text-sm" data-testid={`med-instructions-${idx}`} />
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      {/* General Instructions */}
      <Card className="border border-slate-200 mb-4">
        <CardContent className="p-4">
          <Label className="text-xs text-slate-600">Indicaciones generales</Label>
          <Textarea
            value={generalInstructions}
            onChange={e => setGeneralInstructions(e.target.value)}
            placeholder="Indicaciones generales para el paciente..."
            className="text-sm mt-1 min-h-[70px]"
            data-testid="general-instructions"
          />
        </CardContent>
      </Card>

      {/* Actions */}
      <div className="flex items-center justify-end gap-3 pt-2" data-testid="prescription-actions">
        <Button variant="outline" onClick={() => navigate('/dashboard/recetas')} data-testid="cancel-btn">
          Cancelar
        </Button>
        <Button variant="outline" onClick={() => handleSave('draft')} disabled={saving} data-testid="save-draft-btn">
          <Save className="w-4 h-4 mr-1.5" /> Guardar borrador
        </Button>
        <Button className="bg-teal-600 hover:bg-teal-700" onClick={() => handleSave('issued')} disabled={saving} data-testid="issue-btn">
          <CheckCircle className="w-4 h-4 mr-1.5" /> Emitir receta
        </Button>
        <Button className="bg-green-600 hover:bg-green-700" onClick={handleSendWhatsApp} disabled={saving} data-testid="send-whatsapp-btn">
          <Send className="w-4 h-4 mr-1.5" /> Emitir y enviar
        </Button>
      </div>

      {/* New Medication Dialog */}
      <Dialog open={showNewMed} onOpenChange={setShowNewMed}>
        <DialogContent className="max-w-md" data-testid="new-med-dialog">
          <DialogHeader>
            <DialogTitle>Registrar medicamento</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div>
              <Label className="text-xs">Nombre genérico *</Label>
              <Input className="mt-1 text-sm" value={newMedForm.generic_name} onChange={e => setNewMedForm(p => ({ ...p, generic_name: e.target.value }))} placeholder="Ej: Amoxicilina" data-testid="new-med-generic" />
            </div>
            <div>
              <Label className="text-xs">Marca comercial</Label>
              <Input className="mt-1 text-sm" value={newMedForm.brand_name} onChange={e => setNewMedForm(p => ({ ...p, brand_name: e.target.value }))} placeholder="Ej: Amoxil" />
            </div>
            <div>
              <Label className="text-xs">Presentaciones (separadas por coma)</Label>
              <Input className="mt-1 text-sm" value={newMedForm.presentations} onChange={e => setNewMedForm(p => ({ ...p, presentations: e.target.value }))} placeholder="Tabletas 500mg, Suspensión 250mg/5ml" />
            </div>
            <div>
              <Label className="text-xs">Categoría</Label>
              <Input className="mt-1 text-sm" value={newMedForm.category} onChange={e => setNewMedForm(p => ({ ...p, category: e.target.value }))} placeholder="Antibiótico" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowNewMed(false)}>Cancelar</Button>
            <Button className="bg-teal-600 hover:bg-teal-700" onClick={handleCreateMed} data-testid="save-new-med-btn">Registrar</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
