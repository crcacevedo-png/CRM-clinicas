import { useState, useEffect } from 'react';
import axios from 'axios';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../../components/ui/dialog';
import { Button } from '../../../components/ui/button';
import { Input } from '../../../components/ui/input';
import { Label } from '../../../components/ui/label';
import { Separator } from '../../../components/ui/separator';
import { toast } from 'sonner';
import { API } from './constants';

export default function CloseSessionDialog({ open, onClose, session, headers, onClosed }) {
  const [summary, setSummary] = useState(null);
  const [actual, setActual] = useState(0);
  const [closing, setClosing] = useState(false);

  useEffect(() => {
    if (!open || !session) return;
    (async () => {
      try {
        const r = await axios.get(`${API}/clinic/sales/cash-session/${session.id}/summary`, { headers });
        setSummary(r.data);
        setActual(r.data.expected || 0);
      } catch { /* ignore */ }
    })();
  }, [open, session, headers]);

  const handleClose = async () => {
    setClosing(true);
    try {
      await axios.post(`${API}/clinic/sales/cash-session/${session.id}/close`, { actual_amount: actual }, { headers });
      toast.success('Caja cerrada');
      onClosed();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error'); }
    finally { setClosing(false); }
  };

  if (!summary) return null;
  const diff = (parseFloat(actual) || 0) - (summary.expected || 0);

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-sm" data-testid="close-cash-dialog">
        <DialogHeader><DialogTitle>Cerrar caja</DialogTitle></DialogHeader>
        <div className="space-y-2 py-2 text-sm">
          <div className="flex justify-between"><span className="text-slate-500">Apertura:</span><span className="font-medium">Q{(summary.opening || 0).toFixed(2)}</span></div>
          <div className="flex justify-between"><span className="text-slate-500">Ventas en efectivo:</span><span className="font-medium">Q{(summary.totals?.cash || 0).toFixed(2)}</span></div>
          <div className="flex justify-between"><span className="text-slate-500">Ventas en tarjeta:</span><span className="font-medium">Q{((summary.totals?.credit_card || 0) + (summary.totals?.debit_card || 0)).toFixed(2)}</span></div>
          <div className="flex justify-between"><span className="text-slate-500">Transferencias:</span><span className="font-medium">Q{(summary.totals?.transfer || 0).toFixed(2)}</span></div>
          <Separator />
          <div className="flex justify-between text-base"><span className="font-bold">Total esperado en caja:</span><span className="font-bold text-teal-600">Q{(summary.expected || 0).toFixed(2)}</span></div>
          <div>
            <Label className="text-xs">Monto físico contado</Label>
            <Input type="number" step="0.01" className="mt-1" value={actual} onChange={e => setActual(parseFloat(e.target.value) || 0)} data-testid="actual-amount-input" />
          </div>
          <div className={`flex justify-between p-2 rounded ${Math.abs(diff) < 0.01 ? 'bg-emerald-50 text-emerald-700' : diff > 0 ? 'bg-blue-50 text-blue-700' : 'bg-red-50 text-red-700'}`}>
            <span className="font-bold">{diff > 0 ? 'Sobrante' : diff < 0 ? 'Faltante' : 'Cuadrado'}:</span>
            <span className="font-bold">Q{Math.abs(diff).toFixed(2)}</span>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancelar</Button>
          <Button className="bg-teal-600 hover:bg-teal-700" onClick={handleClose} disabled={closing} data-testid="confirm-close-btn">{closing ? '...' : 'Confirmar cierre'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
