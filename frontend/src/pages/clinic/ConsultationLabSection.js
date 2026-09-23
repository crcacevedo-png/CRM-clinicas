import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
import { Checkbox } from '../../components/ui/checkbox';
import { toast } from 'sonner';
import { Search, Printer, MessageCircle, CheckCircle, RotateCcw, Loader2, AlertCircle } from 'lucide-react';
import { shareViaWhatsApp } from '../../lib/whatsappShare';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function ConsultationLabSection({ patientId, headers, ensureRecordId, defaultDiagnosis }) {
  const [studies, setStudies] = useState([]);
  const [selectedStudies, setSelectedStudies] = useState(new Set());
  const [diagnosis, setDiagnosis] = useState(defaultDiagnosis || '');
  const [priority, setPriority] = useState('routine');
  const [specialInstructions, setSpecialInstructions] = useState('');
  const [searchFilter, setSearchFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [created, setCreated] = useState(null); // { id, pdf_url }
  const dxTouched = useRef(false);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await axios.get(`${API}/clinic/lab-studies`, { headers });
        setStudies(res.data || []);
      } catch {
        toast.error('Error al cargar estudios');
      } finally {
        setLoading(false);
      }
    };
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!dxTouched.current && !created) setDiagnosis(defaultDiagnosis || '');
  }, [defaultDiagnosis, created]);

  const toggleStudy = (studyId) => {
    setSelectedStudies(prev => {
      const next = new Set(prev);
      if (next.has(studyId)) next.delete(studyId); else next.add(studyId);
      return next;
    });
  };

  const grouped = {};
  studies.forEach(s => {
    const cat = s.category || 'Otros';
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(s);
  });
  const filteredGrouped = {};
  if (searchFilter.trim()) {
    const q = searchFilter.toLowerCase();
    Object.entries(grouped).forEach(([cat, list]) => {
      const f = list.filter(s => s.name.toLowerCase().includes(q) || cat.toLowerCase().includes(q));
      if (f.length > 0) filteredGrouped[cat] = f;
    });
  }
  const displayGrouped = searchFilter.trim() ? filteredGrouped : grouped;

  const doCreate = async () => {
    if (selectedStudies.size === 0) { toast.error('Seleccione al menos un estudio'); return null; }
    setBusy(true);
    try {
      const recId = await ensureRecordId();
      const itemsList = studies
        .filter(s => selectedStudies.has(s.id))
        .map(s => ({ study_id: s.id, study_name: s.name, category: s.category || '' }));
      const payload = {
        patient_id: patientId,
        medical_record_id: recId || null,
        presumptive_diagnosis: diagnosis || null,
        special_instructions: specialInstructions || null,
        priority,
        items: itemsList,
        status: 'pending',
      };
      const res = await axios.post(`${API}/clinic/lab-orders`, payload, { headers });
      const result = { id: res.data.id, pdf_url: res.data.pdf_url };
      setCreated(result);
      return result;
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al crear la orden');
      return null;
    } finally {
      setBusy(false);
    }
  };

  const handleCreatePrint = async () => {
    const r = await doCreate();
    if (r) {
      toast.success('Orden de laboratorio creada');
      if (r.pdf_url) window.open(r.pdf_url, '_blank');
    }
  };

  const handleCreateWhatsApp = async () => {
    const r = await doCreate();
    if (r) {
      toast.success('Orden de laboratorio creada');
      await shareViaWhatsApp('lab_order', r.id, headers);
    }
  };

  const reset = () => {
    setSelectedStudies(new Set());
    setSpecialInstructions('');
    setPriority('routine');
    setSearchFilter('');
    setCreated(null);
    dxTouched.current = false;
    setDiagnosis(defaultDiagnosis || '');
  };

  if (loading) {
    return <div className="flex justify-center py-6"><div className="w-6 h-6 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" /></div>;
  }

  if (created) {
    return (
      <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 space-y-3" data-testid="lab-created-panel">
        <div className="flex items-center gap-2 text-emerald-800">
          <CheckCircle className="w-5 h-5" />
          <span className="text-sm font-semibold">Orden de laboratorio creada y vinculada a esta consulta</span>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" onClick={() => created.pdf_url && window.open(created.pdf_url, '_blank')} disabled={!created.pdf_url} data-testid="lab-reprint-btn">
            <Printer className="w-4 h-4 mr-1.5" /> Imprimir PDF
          </Button>
          <Button size="sm" className="bg-green-600 hover:bg-green-700" onClick={() => shareViaWhatsApp('lab_order', created.id, headers)} data-testid="lab-whatsapp-btn">
            <MessageCircle className="w-4 h-4 mr-1.5" /> Enviar por WhatsApp
          </Button>
          <Button variant="ghost" size="sm" onClick={reset} data-testid="lab-new-btn">
            <RotateCcw className="w-4 h-4 mr-1.5" /> Nueva orden
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3" data-testid="consultation-lab-section">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div>
          <Label className="text-xs text-slate-600">Diagnóstico presuntivo</Label>
          <Input
            value={diagnosis}
            onChange={e => { dxTouched.current = true; setDiagnosis(e.target.value); }}
            placeholder="Diagnóstico presuntivo"
            className="mt-1 text-sm"
            data-testid="lab-diagnosis-input"
          />
        </div>
        <div>
          <Label className="text-xs text-slate-600">Prioridad</Label>
          <div className="flex gap-3 mt-1.5">
            <label className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border cursor-pointer transition-all ${priority === 'routine' ? 'bg-slate-100 border-slate-400' : 'border-slate-200 hover:border-slate-300'}`}>
              <input type="radio" name="lab-priority" value="routine" checked={priority === 'routine'} onChange={e => setPriority(e.target.value)} className="accent-teal-600" data-testid="lab-priority-routine" />
              <span className="text-sm">Rutina</span>
            </label>
            <label className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border cursor-pointer transition-all ${priority === 'urgent' ? 'bg-red-50 border-red-400' : 'border-slate-200 hover:border-slate-300'}`}>
              <input type="radio" name="lab-priority" value="urgent" checked={priority === 'urgent'} onChange={e => setPriority(e.target.value)} className="accent-red-600" data-testid="lab-priority-urgent" />
              <AlertCircle className="w-3.5 h-3.5 text-red-500" />
              <span className="text-sm text-red-700 font-medium">Urgente</span>
            </label>
          </div>
        </div>
      </div>

      <div className="relative">
        <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
        <Input value={searchFilter} onChange={e => setSearchFilter(e.target.value)} placeholder="Filtrar estudios..." className="pl-9 text-sm" data-testid="lab-study-search" />
      </div>

      <div className="border border-slate-200 rounded-lg p-3 max-h-72 overflow-y-auto">
        <p className="text-xs font-semibold text-slate-500 mb-2">Estudios solicitados ({selectedStudies.size})</p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Object.entries(displayGrouped).map(([cat, catStudies]) => (
            <div key={cat} className="space-y-1">
              <p className="text-xs font-bold text-slate-700 uppercase tracking-wide border-b border-slate-100 pb-1 mb-1">{cat}</p>
              {catStudies.map(s => {
                const isSelected = selectedStudies.has(s.id);
                return (
                  <label key={s.id} className={`flex items-start gap-2 cursor-pointer rounded-md px-2 py-1.5 transition-colors ${isSelected ? 'bg-teal-50' : ''}`}>
                    <Checkbox checked={isSelected} onCheckedChange={() => toggleStudy(s.id)} className="mt-0.5" data-testid={`lab-study-checkbox-${s.id}`} />
                    <div className="flex-1">
                      <span className={`text-sm ${isSelected ? 'font-medium text-teal-800' : 'text-slate-700'}`}>{s.name}</span>
                      {s.preparation && <p className="text-xs text-slate-400 mt-0.5 leading-tight">{s.preparation}</p>}
                    </div>
                  </label>
                );
              })}
            </div>
          ))}
        </div>
        {Object.keys(displayGrouped).length === 0 && (
          <p className="text-sm text-slate-400 text-center py-6">No se encontraron estudios</p>
        )}
      </div>

      <div>
        <Label className="text-xs text-slate-600">Indicaciones especiales</Label>
        <Textarea value={specialInstructions} onChange={e => setSpecialInstructions(e.target.value)} placeholder="Indicaciones especiales para el laboratorio..." className="text-sm mt-1 min-h-[50px]" data-testid="lab-special-instructions" />
      </div>

      <div className="flex flex-wrap items-center justify-end gap-2 pt-1">
        <Button className="bg-teal-600 hover:bg-teal-700" onClick={handleCreatePrint} disabled={busy} data-testid="lab-create-print-btn">
          {busy ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <Printer className="w-4 h-4 mr-1.5" />}
          Crear e imprimir
        </Button>
        <Button className="bg-green-600 hover:bg-green-700" onClick={handleCreateWhatsApp} disabled={busy} data-testid="lab-create-whatsapp-btn">
          {busy ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <MessageCircle className="w-4 h-4 mr-1.5" />}
          Crear y enviar por WhatsApp
        </Button>
      </div>
    </div>
  );
}
