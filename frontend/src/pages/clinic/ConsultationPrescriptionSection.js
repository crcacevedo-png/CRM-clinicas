import { useState, useRef, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
import { Badge } from '../../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { toast } from 'sonner';
import { Plus, Trash2, Printer, MessageCircle, CheckCircle, RotateCcw, Loader2 } from 'lucide-react';
import { shareViaWhatsApp } from '../../lib/whatsappShare';

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
  _searchResults: [], _showSearch: false, _searchQuery: '',
});

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
      _showSearch: false, _searchResults: [],
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
        data-testid={`presc-med-name-${index}`}
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

export default function ConsultationPrescriptionSection({ patientId, headers, ensureRecordId, defaultDiagnosis }) {
  const [items, setItems] = useState([emptyItem()]);
  const [diagnosis, setDiagnosis] = useState(defaultDiagnosis || '');
  const [generalInstructions, setGeneralInstructions] = useState('');
  const [busy, setBusy] = useState(false);
  const [created, setCreated] = useState(null); // { id, pdf_url }
  const dxTouched = useRef(false);

  // Keep diagnosis in sync with the consultation's primary diagnosis until the user edits it
  useEffect(() => {
    if (!dxTouched.current && !created) setDiagnosis(defaultDiagnosis || '');
  }, [defaultDiagnosis, created]);

  const updateItem = useCallback((index, updates) => {
    setItems(prev => prev.map((it, i) => i === index ? { ...it, ...updates } : it));
  }, []);
  const addItem = () => setItems(prev => [...prev, emptyItem()]);
  const removeItem = (i) => { if (items.length <= 1) return; setItems(prev => prev.filter((_, j) => j !== i)); };

  const doCreate = async () => {
    const validItems = items.filter(it => it.medication_name.trim());
    if (validItems.length === 0) { toast.error('Agregue al menos un medicamento'); return null; }
    setBusy(true);
    try {
      const recId = await ensureRecordId();
      const payload = {
        patient_id: patientId,
        medical_record_id: recId || null,
        diagnosis: diagnosis || null,
        general_instructions: generalInstructions || null,
        items: validItems.map(it => ({
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
      const res = await axios.post(`${API}/clinic/prescriptions`, payload, { headers });
      const result = { id: res.data.id, pdf_url: res.data.pdf_url };
      setCreated(result);
      return result;
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al emitir la receta');
      return null;
    } finally {
      setBusy(false);
    }
  };

  const handleEmitPrint = async () => {
    const r = await doCreate();
    if (r) {
      toast.success('Receta emitida');
      if (r.pdf_url) window.open(r.pdf_url, '_blank');
    }
  };

  const handleEmitWhatsApp = async () => {
    const r = await doCreate();
    if (r) {
      toast.success('Receta emitida');
      await shareViaWhatsApp('prescription', r.id, headers);
    }
  };

  const reset = () => {
    setItems([emptyItem()]);
    setGeneralInstructions('');
    setCreated(null);
    dxTouched.current = false;
    setDiagnosis(defaultDiagnosis || '');
  };

  if (created) {
    return (
      <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 space-y-3" data-testid="presc-created-panel">
        <div className="flex items-center gap-2 text-emerald-800">
          <CheckCircle className="w-5 h-5" />
          <span className="text-sm font-semibold">Receta emitida y vinculada a esta consulta</span>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" onClick={() => created.pdf_url && window.open(created.pdf_url, '_blank')} disabled={!created.pdf_url} data-testid="presc-reprint-btn">
            <Printer className="w-4 h-4 mr-1.5" /> Imprimir PDF
          </Button>
          <Button size="sm" className="bg-green-600 hover:bg-green-700" onClick={() => shareViaWhatsApp('prescription', created.id, headers)} data-testid="presc-whatsapp-btn">
            <MessageCircle className="w-4 h-4 mr-1.5" /> Enviar por WhatsApp
          </Button>
          <Button variant="ghost" size="sm" onClick={reset} data-testid="presc-new-btn">
            <RotateCcw className="w-4 h-4 mr-1.5" /> Nueva receta
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3" data-testid="consultation-prescription-section">
      <div>
        <Label className="text-xs text-slate-600">Diagnóstico</Label>
        <Input
          value={diagnosis}
          onChange={e => { dxTouched.current = true; setDiagnosis(e.target.value); }}
          placeholder="Diagnóstico o motivo de la receta"
          className="mt-1 text-sm"
          data-testid="presc-diagnosis-input"
        />
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label className="text-xs font-semibold text-slate-600">
            Medicamentos ({items.filter(i => i.medication_name.trim()).length})
          </Label>
          <Button variant="outline" size="sm" className="text-xs" onClick={addItem} data-testid="presc-add-med-btn">
            <Plus className="w-3.5 h-3.5 mr-1" /> Agregar medicamento
          </Button>
        </div>
        {items.map((item, idx) => (
          <div key={idx} className="p-3 border border-slate-200 rounded-lg bg-slate-50/50 space-y-2" data-testid={`presc-med-row-${idx}`}>
            <div className="flex items-start gap-2">
              <Badge className="bg-teal-600 text-white mt-1 shrink-0">{idx + 1}</Badge>
              <div className="flex-1 grid grid-cols-1 md:grid-cols-2 gap-2">
                <div>
                  <Label className="text-xs text-slate-500">Medicamento *</Label>
                  <MedSearch item={item} index={idx} onUpdate={updateItem} headers={headers} />
                </div>
                <div>
                  <Label className="text-xs text-slate-500">Presentación</Label>
                  <Input value={item.presentation} onChange={e => updateItem(idx, { presentation: e.target.value })} placeholder="Ej: Tabletas 500mg" className="text-sm" data-testid={`presc-med-presentation-${idx}`} />
                </div>
              </div>
              {items.length > 1 && (
                <Button variant="ghost" size="sm" className="h-7 w-7 p-0 mt-4 shrink-0 hover:text-red-600" onClick={() => removeItem(idx)} data-testid={`presc-remove-med-${idx}`}>
                  <Trash2 className="w-3.5 h-3.5" />
                </Button>
              )}
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 ml-8">
              <div>
                <Label className="text-xs text-slate-500">Dosis</Label>
                <Input value={item.dosage} onChange={e => updateItem(idx, { dosage: e.target.value })} placeholder="500mg" className="text-sm" data-testid={`presc-med-dosage-${idx}`} />
              </div>
              <div>
                <Label className="text-xs text-slate-500">Frecuencia</Label>
                <Input value={item.frequency} onChange={e => updateItem(idx, { frequency: e.target.value })} placeholder="Cada 8 horas" className="text-sm" data-testid={`presc-med-frequency-${idx}`} />
              </div>
              <div>
                <Label className="text-xs text-slate-500">Vía</Label>
                <Select value={item.route} onValueChange={v => updateItem(idx, { route: v })}>
                  <SelectTrigger className="text-sm" data-testid={`presc-med-route-${idx}`}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {ROUTES.map(r => (<SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs text-slate-500">Duración</Label>
                <Input value={item.duration} onChange={e => updateItem(idx, { duration: e.target.value })} placeholder="7 días" className="text-sm" data-testid={`presc-med-duration-${idx}`} />
              </div>
            </div>
            <div className="ml-8">
              <Label className="text-xs text-slate-500">Instrucciones especiales</Label>
              <Input value={item.instructions} onChange={e => updateItem(idx, { instructions: e.target.value })} placeholder="Tomar con alimentos, evitar alcohol..." className="text-sm" data-testid={`presc-med-instructions-${idx}`} />
            </div>
          </div>
        ))}
      </div>

      <div>
        <Label className="text-xs text-slate-600">Indicaciones generales</Label>
        <Textarea
          value={generalInstructions}
          onChange={e => setGeneralInstructions(e.target.value)}
          placeholder="Indicaciones generales para el paciente..."
          className="text-sm mt-1 min-h-[60px]"
          data-testid="presc-general-instructions"
        />
      </div>

      <div className="flex flex-wrap items-center justify-end gap-2 pt-1">
        <Button className="bg-teal-600 hover:bg-teal-700" onClick={handleEmitPrint} disabled={busy} data-testid="presc-emit-print-btn">
          {busy ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <Printer className="w-4 h-4 mr-1.5" />}
          Emitir e imprimir
        </Button>
        <Button className="bg-green-600 hover:bg-green-700" onClick={handleEmitWhatsApp} disabled={busy} data-testid="presc-emit-whatsapp-btn">
          {busy ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <MessageCircle className="w-4 h-4 mr-1.5" />}
          Emitir y enviar por WhatsApp
        </Button>
      </div>
    </div>
  );
}
