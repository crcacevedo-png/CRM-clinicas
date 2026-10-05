import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../../components/ui/dialog';
import { Button } from '../../../components/ui/button';
import { Input } from '../../../components/ui/input';
import { Label } from '../../../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../../components/ui/select';
import { toast } from 'sonner';
import { Banknote, CreditCard, ArrowRight, Wallet, Plus, X, ShieldCheck, ChevronDown, ChevronUp } from 'lucide-react';
import { useAuth } from '../../../context/AuthContext';
import { API } from './constants';

/**
 * Charge dialog with:
 *   - A dedicated "Pago con seguro" panel ABOVE the payment methods.
 *     Insurance is a charge to the insurer (AR), not cash in caja.
 *   - A clean payment-methods list for what the PATIENT pays today.
 *   - A clear summary line: Pagado hoy / Cargo al seguro / Saldo pendiente.
 */
export default function ChargeModal({ open, onClose, total, onConfirm, hasPatient, patientName }) {
  const [payments, setPayments] = useState([{ payment_method: 'cash', amount: 0, reference: '' }]);
  const [submitting, setSubmitting] = useState(false);
  const [arDueDate, setArDueDate] = useState('');
  const [arInstallments, setArInstallments] = useState(1);
  const [insuranceProviders, setInsuranceProviders] = useState([]);
  const [insuranceName, setInsuranceName] = useState('');
  const [insuranceAmount, setInsuranceAmount] = useState(0);
  const [showInsurance, setShowInsurance] = useState(false);
  const { getAuthHeaders } = useAuth();

  useEffect(() => {
    if (open) {
      setPayments([{ payment_method: 'cash', amount: total, reference: '' }]);
      const d = new Date(); d.setDate(d.getDate() + 30);
      setArDueDate(d.toISOString().slice(0, 10));
      setArInstallments(1);
      setInsuranceName('');
      setInsuranceAmount(0);
      // Load insurance providers for autocomplete + decide whether to pre-open the panel
      axios.get(`${API}/clinic/insurance-providers`, { headers: getAuthHeaders() })
        .then(r => {
          const list = r.data || [];
          setInsuranceProviders(list);
          // Auto-expand if the clinic already uses insurance
          setShowInsurance(list.length > 0);
        })
        .catch(() => { setInsuranceProviders([]); setShowInsurance(false); });
    }
  }, [open, total, getAuthHeaders]);

  // When insurance amount changes, auto-adjust the first cash payment so the sum
  // of insurance + patient payments equals total (if there's only one payment line).
  useEffect(() => {
    if (!open) return;
    if (payments.length === 1) {
      const diff = Math.max(0, round2(total - (parseFloat(insuranceAmount) || 0)));
      setPayments([{ ...payments[0], amount: diff }]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [insuranceAmount]);

  const round2 = (n) => Math.round(n * 100) / 100;

  const addPay = () => setPayments(p => [...p, { payment_method: 'credit_card', amount: 0, reference: '' }]);
  const removePay = (i) => setPayments(p => p.filter((_, idx) => idx !== i));
  const updPay = (i, field, value) => setPayments(p => p.map((x, idx) => idx === i ? { ...x, [field]: value } : x));

  const insuranceAmt = parseFloat(insuranceAmount) || 0;
  const totalPaid = payments.reduce((s, p) => s + (parseFloat(p.amount) || 0), 0);
  const cashGiven = payments.filter(p => p.payment_method === 'cash').reduce((s, p) => s + (parseFloat(p.amount) || 0), 0);
  const patientPortion = Math.max(0, round2(total - insuranceAmt));
  // Change only applies to CASH overpayment of the PATIENT portion
  const change = cashGiven > 0 && totalPaid > patientPortion ? round2(totalPaid - patientPortion) : 0;
  const patientDue = Math.max(0, round2(patientPortion - totalPaid));
  const dueTotal = round2(patientDue + insuranceAmt);
  const isPartial = dueTotal > 0.01;

  const handleConfirm = async () => {
    if (insuranceAmt > 0 && !insuranceName.trim()) {
      toast.error('Escribe el nombre de la aseguradora.');
      return;
    }
    if (insuranceAmt > total + 0.01) {
      toast.error('El cargo al seguro no puede ser mayor al total.');
      return;
    }
    if (totalPaid <= 0 && insuranceAmt <= 0 && total > 0) {
      toast.error('Ingrese al menos un pago o un cargo al seguro.');
      return;
    }
    if (isPartial && !hasPatient) {
      toast.error('Para pagos parciales, cargos a seguro o crédito, primero selecciona un paciente registrado en el carrito.');
      return;
    }
    if (isPartial && !arDueDate) {
      toast.error('Indica una fecha de vencimiento para la cuenta por cobrar.');
      return;
    }
    const adjusted = payments.filter(p => (parseFloat(p.amount) || 0) > 0).map(p => {
      let amt = parseFloat(p.amount) || 0;
      if (p.payment_method === 'cash' && totalPaid > patientPortion) {
        amt = Math.max(0, amt - change);
      }
      return { payment_method: p.payment_method, amount: amt, reference: p.reference || '', notes: p.notes || '' };
    }).filter(p => p.amount > 0);

    const insurancePayload = insuranceAmt > 0
      ? { insurance_name: insuranceName.trim(), insurance_amount: insuranceAmt }
      : {};
    const arPayload = isPartial ? { ar_due_date: arDueDate, ar_installments: parseInt(arInstallments) || 1 } : {};
    setSubmitting(true);
    try {
      await onConfirm(adjusted, { ...arPayload, ...insurancePayload });
    } finally { setSubmitting(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-md max-h-[92vh] overflow-y-auto" data-testid="charge-dialog">
        <DialogHeader><DialogTitle>Cobrar</DialogTitle></DialogHeader>
        <div className="space-y-3 py-2">
          <div className="text-center bg-teal-50 border border-teal-200 rounded-lg py-3">
            <p className="text-xs text-teal-700">Total a pagar</p>
            <p className="text-3xl font-bold text-teal-600">Q{total.toFixed(2)}</p>
          </div>

          {/* Insurance panel — above payments. Collapsed by default on clinics without insurers. */}
          {showInsurance ? (
            <div className="border border-blue-200 bg-blue-50/40 rounded-lg p-3 space-y-2" data-testid="insurance-panel">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5 text-sm font-semibold text-blue-900">
                  <ShieldCheck className="w-4 h-4" /> ¿Parte del total va a un seguro médico?
                </div>
                <button
                  type="button"
                  className="text-xs text-blue-700 hover:text-blue-900 flex items-center gap-0.5"
                  onClick={() => { setShowInsurance(false); setInsuranceName(''); setInsuranceAmount(0); }}
                  data-testid="insurance-collapse-btn"
                >
                  <ChevronUp className="w-3.5 h-3.5" /> Ocultar
                </button>
              </div>
              <p className="text-[11px] text-blue-800">
                El cargo al seguro se registra como una cuenta por cobrar a la aseguradora. No cuenta como dinero recibido hoy.
              </p>
              <div className="grid grid-cols-[1fr_120px] gap-2">
                <InsuranceInput
                  value={insuranceName}
                  onChange={setInsuranceName}
                  providers={insuranceProviders}
                  testid="insurance-name-input"
                />
                <div>
                  <Label className="text-xs">Cargo al seguro</Label>
                  <Input
                    type="number"
                    step="0.01"
                    min="0"
                    className="mt-1 text-sm h-8"
                    value={insuranceAmount}
                    onChange={(e) => setInsuranceAmount(e.target.value)}
                    placeholder="0.00"
                    data-testid="insurance-amount-input"
                  />
                </div>
              </div>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setShowInsurance(true)}
              className="w-full border border-dashed border-blue-200 bg-blue-50/20 rounded-lg py-2 text-xs text-blue-700 hover:bg-blue-50 flex items-center justify-center gap-1.5 transition-colors"
              data-testid="insurance-expand-btn"
            >
              <ShieldCheck className="w-3.5 h-3.5" />
              ¿Parte va a un seguro? <ChevronDown className="w-3.5 h-3.5" />
            </button>
          )}

          {/* Patient payments */}
          <div className="pt-1">
            <p className="text-xs font-semibold text-emerald-800 mb-1.5 uppercase tracking-wide">Pago del paciente</p>
          </div>
          {payments.map((p, i) => (
            <div key={i} className="flex items-end gap-2 p-2 border rounded">
              <div className="flex-1">
                <Label className="text-xs">Método</Label>
                <Select value={p.payment_method} onValueChange={v => updPay(i, 'payment_method', v)}>
                  <SelectTrigger className="mt-1 text-sm h-8" data-testid={`pay-method-${i}`}><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="cash"><Banknote className="w-3 h-3 inline mr-1" />Efectivo</SelectItem>
                    <SelectItem value="credit_card"><CreditCard className="w-3 h-3 inline mr-1" />Tarjeta crédito</SelectItem>
                    <SelectItem value="debit_card"><CreditCard className="w-3 h-3 inline mr-1" />Tarjeta débito</SelectItem>
                    <SelectItem value="transfer"><ArrowRight className="w-3 h-3 inline mr-1" />Transferencia</SelectItem>
                    <SelectItem value="credit"><Wallet className="w-3 h-3 inline mr-1" />Crédito</SelectItem>
                    <SelectItem value="check">Cheque</SelectItem>
                    <SelectItem value="other">Otro</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="w-24">
                <Label className="text-xs">Monto</Label>
                <Input type="number" step="0.01" className="mt-1 text-sm h-8" value={p.amount} onChange={e => updPay(i, 'amount', e.target.value)} data-testid={`pay-amount-${i}`} />
              </div>
              {(p.payment_method === 'credit_card' || p.payment_method === 'debit_card' || p.payment_method === 'transfer' || p.payment_method === 'check') && (
                <div className="w-24">
                  <Label className="text-xs">Ref.</Label>
                  <Input className="mt-1 text-sm h-8" value={p.reference || ''} onChange={e => updPay(i, 'reference', e.target.value)} placeholder="Auth" />
                </div>
              )}
              {payments.length > 1 && <Button variant="ghost" size="sm" className="h-8 w-8 p-0" onClick={() => removePay(i)}><X className="w-3.5 h-3.5 text-red-500" /></Button>}
            </div>
          ))}
          <Button variant="outline" size="sm" onClick={addPay}><Plus className="w-3.5 h-3.5 mr-1" />Agregar método</Button>

          {/* 3-column summary */}
          <div className="grid grid-cols-3 gap-2 pt-2">
            <div className="bg-emerald-50 border border-emerald-200 rounded p-2 text-center">
              <p className="text-[10px] text-emerald-700 font-medium uppercase">Pagado hoy</p>
              <p className="text-base font-bold text-emerald-700">Q{Math.min(totalPaid, patientPortion).toFixed(2)}</p>
            </div>
            <div className={`${insuranceAmt > 0 ? 'bg-blue-50 border-blue-200' : 'bg-slate-50 border-slate-200'} border rounded p-2 text-center`}>
              <p className="text-[10px] text-blue-700 font-medium uppercase">Cargo al seguro</p>
              <p className={`text-base font-bold ${insuranceAmt > 0 ? 'text-blue-700' : 'text-slate-400'}`}>Q{insuranceAmt.toFixed(2)}</p>
            </div>
            <div className={`${dueTotal > 0.01 ? 'bg-amber-50 border-amber-200' : 'bg-slate-50 border-slate-200'} border rounded p-2 text-center`}>
              <p className="text-[10px] text-amber-700 font-medium uppercase">Saldo pendiente</p>
              <p className={`text-base font-bold ${dueTotal > 0.01 ? 'text-amber-700' : 'text-slate-400'}`}>Q{dueTotal.toFixed(2)}</p>
            </div>
          </div>
          {change > 0 && (
            <div className="text-xs text-emerald-700 text-right">
              Cambio para el paciente: <span className="font-bold">Q{change.toFixed(2)}</span>
            </div>
          )}

          {/* AR options */}
          {isPartial && (
            <div className="border border-amber-300 bg-amber-50/60 rounded-lg p-3 space-y-2" data-testid="ar-options-section">
              <div className="flex items-center gap-1.5 text-sm font-semibold text-amber-900">
                <Wallet className="w-4 h-4" /> Cuenta por cobrar
              </div>
              {!hasPatient ? (
                <p className="text-xs text-red-700 bg-red-50 border border-red-200 rounded p-2">
                  ⚠ Para registrar un cargo al seguro o un saldo pendiente necesitas <strong>seleccionar un paciente registrado</strong> en el carrito.
                </p>
              ) : (
                <div className="text-xs text-amber-900 space-y-0.5">
                  <p>Se creará una cuenta por cobrar a nombre de <strong>{patientName}</strong> por <strong>Q{dueTotal.toFixed(2)}</strong>:</p>
                  {insuranceAmt > 0 && <p className="ml-3">• Cargo a <strong>{insuranceName || '(seguro)'}</strong>: Q{insuranceAmt.toFixed(2)}</p>}
                  {patientDue > 0 && <p className="ml-3">• Saldo del paciente: Q{patientDue.toFixed(2)}</p>}
                </div>
              )}
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <Label className="text-xs">Vence el</Label>
                  <Input type="date" className="mt-1 text-sm h-8" value={arDueDate} onChange={e => setArDueDate(e.target.value)} disabled={!hasPatient} data-testid="ar-due-date-input" />
                </div>
                <div>
                  <Label className="text-xs">Cuotas</Label>
                  <Input type="number" min="1" max="36" className="mt-1 text-sm h-8" value={arInstallments} onChange={e => setArInstallments(e.target.value)} disabled={!hasPatient} data-testid="ar-installments-input" />
                </div>
              </div>
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancelar</Button>
          <Button className="bg-teal-600 hover:bg-teal-700" onClick={handleConfirm} disabled={submitting} data-testid="confirm-payment-btn">{submitting ? '...' : 'Confirmar cobro'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/* Insurance autocomplete input */
function InsuranceInput({ value, onChange, providers, testid }) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);

  useEffect(() => {
    const onDoc = (e) => { if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);

  const q = (value || '').toLowerCase();
  const suggestions = (providers || []).filter(p => !q || p.name.toLowerCase().includes(q)).slice(0, 8);

  return (
    <div ref={wrapRef} className="relative">
      <Label className="text-xs">Aseguradora</Label>
      <Input
        className="mt-1 text-sm h-8"
        placeholder="Ej: Mapfre, Aseguradora General…"
        value={value}
        onFocus={() => setOpen(true)}
        onChange={(e) => { onChange(e.target.value); setOpen(true); }}
        data-testid={testid}
      />
      {open && suggestions.length > 0 && (
        <div className="absolute z-20 left-0 right-0 mt-1 bg-white border border-slate-200 rounded shadow-sm max-h-40 overflow-auto">
          {suggestions.map(s => (
            <button
              type="button"
              key={s.id}
              className="block w-full text-left px-3 py-1.5 text-sm hover:bg-blue-50"
              onClick={() => { onChange(s.name); setOpen(false); }}
              data-testid={`${testid}-suggestion-${s.id}`}
            >
              {s.name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
