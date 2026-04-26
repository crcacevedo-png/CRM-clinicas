import { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../../components/ui/dialog';
import { Button } from '../../../components/ui/button';
import { Input } from '../../../components/ui/input';
import { Label } from '../../../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../../components/ui/select';
import { toast } from 'sonner';
import { Banknote, CreditCard, ArrowRight, Wallet, Plus, X } from 'lucide-react';

export default function ChargeModal({ open, onClose, total, onConfirm, hasPatient, patientName }) {
  const [payments, setPayments] = useState([{ payment_method: 'cash', amount: 0, reference: '' }]);
  const [submitting, setSubmitting] = useState(false);
  const [arDueDate, setArDueDate] = useState('');
  const [arInstallments, setArInstallments] = useState(1);

  useEffect(() => {
    if (open) {
      setPayments([{ payment_method: 'cash', amount: total, reference: '' }]);
      const d = new Date(); d.setDate(d.getDate() + 30);
      setArDueDate(d.toISOString().slice(0, 10));
      setArInstallments(1);
    }
  }, [open, total]);

  const addPay = () => setPayments(p => [...p, { payment_method: 'credit_card', amount: 0, reference: '' }]);
  const removePay = (i) => setPayments(p => p.filter((_, idx) => idx !== i));
  const updPay = (i, field, value) => setPayments(p => p.map((x, idx) => idx === i ? { ...x, [field]: value } : x));

  const totalPaid = payments.reduce((s, p) => s + (parseFloat(p.amount) || 0), 0);
  const cashGiven = payments.filter(p => p.payment_method === 'cash').reduce((s, p) => s + (parseFloat(p.amount) || 0), 0);
  const change = cashGiven > 0 && totalPaid > total ? totalPaid - total : 0;
  const due = Math.max(0, total - totalPaid);
  const isPartial = due > 0.01;

  const handleConfirm = async () => {
    if (totalPaid <= 0 && !isPartial) { toast.error('Ingrese al menos un pago'); return; }
    if (isPartial && !hasPatient) {
      toast.error('Para pagos parciales o crédito, primero selecciona un paciente registrado en el carrito.');
      return;
    }
    if (isPartial && !arDueDate) {
      toast.error('Indica una fecha de vencimiento para la cuenta por cobrar.');
      return;
    }
    const adjusted = payments.filter(p => (parseFloat(p.amount) || 0) > 0).map(p => {
      let amt = parseFloat(p.amount) || 0;
      if (p.payment_method === 'cash' && totalPaid > total) {
        amt = Math.max(0, amt - change);
      }
      return { ...p, amount: amt };
    }).filter(p => p.amount > 0);
    setSubmitting(true);
    try {
      await onConfirm(adjusted, isPartial ? { ar_due_date: arDueDate, ar_installments: parseInt(arInstallments) || 1 } : {});
    } finally { setSubmitting(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-md" data-testid="charge-dialog">
        <DialogHeader><DialogTitle>Cobrar</DialogTitle></DialogHeader>
        <div className="space-y-3 py-2">
          <div className="text-center bg-teal-50 border border-teal-200 rounded-lg py-3">
            <p className="text-xs text-teal-700">Total a pagar</p>
            <p className="text-3xl font-bold text-teal-600">Q{total.toFixed(2)}</p>
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
          <div className="bg-slate-50 rounded p-2 text-xs space-y-1">
            <div className="flex justify-between"><span>Pagado:</span><span className="font-bold">Q{totalPaid.toFixed(2)}</span></div>
            {change > 0 && <div className="flex justify-between text-emerald-700"><span>Cambio:</span><span className="font-bold">Q{change.toFixed(2)}</span></div>}
            {due > 0 && <div className="flex justify-between text-amber-700"><span>Saldo pendiente:</span><span className="font-bold">Q{due.toFixed(2)}</span></div>}
          </div>

          {isPartial && (
            <div className="border border-amber-300 bg-amber-50/60 rounded-lg p-3 space-y-2" data-testid="ar-options-section">
              <div className="flex items-center gap-1.5 text-sm font-semibold text-amber-900">
                <Wallet className="w-4 h-4" /> Cuenta por cobrar
              </div>
              {!hasPatient ? (
                <p className="text-xs text-red-700 bg-red-50 border border-red-200 rounded p-2">
                  ⚠ Para registrar este pago parcial necesitas <strong>seleccionar un paciente registrado</strong> en el carrito (no basta el nombre del cliente). Cierra este diálogo y elige uno desde el buscador de paciente.
                </p>
              ) : (
                <p className="text-xs text-amber-800">
                  Se creará una cuenta por cobrar a nombre de <strong>{patientName}</strong> por <strong>Q{due.toFixed(2)}</strong>.
                </p>
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
              {arInstallments > 1 && hasPatient && (
                <p className="text-xs text-slate-600">~ Q{(due / arInstallments).toFixed(2)} por cuota</p>
              )}
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancelar</Button>
          <Button className="bg-teal-600 hover:bg-teal-700" onClick={handleConfirm} disabled={submitting} data-testid="confirm-payment-btn">{submitting ? '...' : 'Confirmar pago'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
