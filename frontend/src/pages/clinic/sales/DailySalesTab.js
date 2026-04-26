import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Card } from '../../../components/ui/card';
import { Button } from '../../../components/ui/button';
import { Input } from '../../../components/ui/input';
import { Badge } from '../../../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../../components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../../components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../../components/ui/dialog';
import { Separator } from '../../../components/ui/separator';
import { toast } from 'sonner';
import { Banknote, CreditCard, Wallet, Eye, Printer, Ban } from 'lucide-react';
import { API, PAY_LABEL, STATUS_LABEL } from './constants';
import SummaryCard from './SummaryCard';

export default function DailySalesTab({ headers, branches, activeBranch }) {
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [summary, setSummary] = useState(null);
  const [sales, setSales] = useState([]);
  const [branchFilter, setBranchFilter] = useState(activeBranch?.id || 'all');
  const [methodFilter, setMethodFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState(null);

  useEffect(() => {
    if (activeBranch?.id) setBranchFilter(activeBranch.id);
  }, [activeBranch?.id]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ date, date_from: date, date_to: date });
      if (branchFilter !== 'all') params.set('branch_id', branchFilter);
      if (methodFilter !== 'all') params.set('payment_method', methodFilter);
      const [s, l] = await Promise.all([
        axios.get(`${API}/clinic/sales/daily-summary?${branchFilter !== 'all' ? `branch_id=${branchFilter}&` : ''}date=${date}`, { headers }),
        axios.get(`${API}/clinic/sales?${params}&limit=50`, { headers }),
      ]);
      setSummary(s.data); setSales(l.data.sales || []);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [date, branchFilter, methodFilter, headers]);

  useEffect(() => { load(); }, [load]);

  const openDetail = async (id) => {
    try {
      const r = await axios.get(`${API}/clinic/sales/${id}`, { headers });
      setDetail(r.data);
    } catch { toast.error('Error'); }
  };

  const handleCancel = async (id) => {
    const reason = prompt('Motivo de la anulación:');
    if (!reason) return;
    try { await axios.post(`${API}/clinic/sales/${id}/cancel`, { reason }, { headers }); toast.success('Venta anulada'); load(); setDetail(null); }
    catch (err) { toast.error(err.response?.data?.detail || 'Error'); }
  };

  const printReceipt = async (id) => {
    try {
      const r = await axios.get(`${API}/clinic/sales/${id}/pdf-url`, { headers });
      if (r.data.url) window.open(r.data.url, '_blank');
      else toast.error('PDF no disponible');
    } catch { toast.error('Error al obtener PDF'); }
  };

  return (
    <>
      <div className="flex flex-wrap gap-3 mb-4">
        <Input type="date" className="w-44" value={date} onChange={e => setDate(e.target.value)} data-testid="date-filter" />
        <Select value={branchFilter} onValueChange={setBranchFilter}>
          <SelectTrigger className="w-44"><SelectValue placeholder="Sucursal" /></SelectTrigger>
          <SelectContent><SelectItem value="all">Todas</SelectItem>{(branches || []).map(b => <SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>)}</SelectContent>
        </Select>
        <Select value={methodFilter} onValueChange={setMethodFilter}>
          <SelectTrigger className="w-44"><SelectValue placeholder="Método de pago" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todos</SelectItem>
            <SelectItem value="cash">Efectivo</SelectItem>
            <SelectItem value="credit_card">Tarjeta crédito</SelectItem>
            <SelectItem value="debit_card">Tarjeta débito</SelectItem>
            <SelectItem value="transfer">Transferencia</SelectItem>
            <SelectItem value="credit">Crédito</SelectItem>
            <SelectItem value="check">Cheque</SelectItem>
            <SelectItem value="other">Otro</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <SummaryCard label="Total ventas" value={summary?.total} count={summary?.count} color="teal" />
        <SummaryCard label="Efectivo" value={summary?.cash} color="emerald" icon={Banknote} />
        <SummaryCard label="Tarjeta" value={summary?.card} color="blue" icon={CreditCard} />
        <SummaryCard label="Pendiente cobro" value={summary?.pending_due} color="amber" icon={Wallet} />
      </div>

      {loading ? <div className="flex justify-center py-16"><div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" /></div> :
        <Card className="border overflow-hidden">
          <Table>
            <TableHeader><TableRow className="bg-slate-50/80">
              <TableHead className="text-xs font-semibold">Hora</TableHead>
              <TableHead className="text-xs font-semibold">No.</TableHead>
              <TableHead className="text-xs font-semibold">Sucursal</TableHead>
              <TableHead className="text-xs font-semibold">Cliente</TableHead>
              <TableHead className="text-xs font-semibold">Items</TableHead>
              <TableHead className="text-xs font-semibold text-right">Total</TableHead>
              <TableHead className="text-xs font-semibold text-center">Pago</TableHead>
              <TableHead className="text-xs font-semibold text-center">Estado</TableHead>
              <TableHead className="text-xs font-semibold">Cajero</TableHead>
              <TableHead className="text-xs font-semibold text-right"></TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {sales.map(s => (
                <TableRow key={s.id} data-testid={`sale-row-${s.id}`}>
                  <TableCell className="text-xs">{s.created_at?.substring(11, 16)}</TableCell>
                  <TableCell className="text-xs font-mono">{s.sale_number}</TableCell>
                  <TableCell className="text-xs"><Badge variant="outline" className="text-xs bg-slate-50 text-slate-700 border-slate-200">{s.branch_name || '—'}</Badge></TableCell>
                  <TableCell className="text-sm">{s.customer_name || '—'}</TableCell>
                  <TableCell className="text-xs text-slate-500 max-w-[180px] truncate">{s.items_summary}</TableCell>
                  <TableCell className="text-right text-sm font-bold">Q{(s.total || 0).toFixed(2)}</TableCell>
                  <TableCell className="text-center text-xs">{(s.payment_methods || []).map(m => PAY_LABEL[m] || m).join(', ') || '—'}</TableCell>
                  <TableCell className="text-center"><Badge variant="outline" className={`text-xs ${s.status === 'cancelled' ? 'bg-red-50 text-red-700' : s.payment_status === 'paid' ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>{s.status === 'cancelled' ? 'Anulada' : STATUS_LABEL[s.payment_status] || s.payment_status}</Badge></TableCell>
                  <TableCell className="text-xs text-slate-500">{s.cashier_name}</TableCell>
                  <TableCell className="text-right">
                    <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => openDetail(s.id)} data-testid={`view-sale-${s.id}`}><Eye className="w-3.5 h-3.5" /></Button>
                  </TableCell>
                </TableRow>
              ))}
              {sales.length === 0 && <TableRow><TableCell colSpan={10} className="text-center py-8 text-slate-400">Sin ventas en esta fecha</TableCell></TableRow>}
            </TableBody>
          </Table>
        </Card>}

      <Dialog open={!!detail} onOpenChange={() => setDetail(null)}>
        <DialogContent className="max-w-lg" data-testid="sale-detail-dialog">
          <DialogHeader><DialogTitle>Venta {detail?.sale_number}</DialogTitle></DialogHeader>
          {detail && (
            <div className="space-y-3 text-sm">
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div><span className="text-slate-500">Cliente:</span> <span className="font-medium">{detail.customer_name || '—'}</span></div>
                <div><span className="text-slate-500">NIT/DPI:</span> <span className="font-medium">{detail.customer_id || '—'}</span></div>
                <div><span className="text-slate-500">Cajero:</span> <span className="font-medium">{detail.cashier_name}</span></div>
                <div><span className="text-slate-500">Estado:</span> <Badge variant="outline" className="text-xs">{detail.status === 'cancelled' ? 'Anulada' : STATUS_LABEL[detail.payment_status]}</Badge></div>
              </div>
              <Separator />
              <p className="text-xs font-bold text-slate-500">Items</p>
              {(detail.items || []).map(it => (
                <div key={it.id} className="flex justify-between text-xs">
                  <span>{it.quantity} × {it.description}</span>
                  <span className="font-medium">Q{(it.total || 0).toFixed(2)}</span>
                </div>
              ))}
              <Separator />
              <div className="text-right text-sm">
                <p>Subtotal: <b>Q{(detail.subtotal || 0).toFixed(2)}</b></p>
                {(detail.discount_amount || 0) > 0 && <p>Descuento: <b>-Q{(detail.discount_amount).toFixed(2)}</b></p>}
                <p>IVA: <b>Q{(detail.tax_amount || 0).toFixed(2)}</b></p>
                <p className="text-lg font-bold text-teal-600">TOTAL: Q{(detail.total || 0).toFixed(2)}</p>
              </div>
              <Separator />
              <p className="text-xs font-bold text-slate-500">Pagos</p>
              {(detail.payments || []).map(p => (
                <div key={p.id} className="flex justify-between text-xs">
                  <span>{PAY_LABEL[p.payment_method] || p.payment_method} {p.reference ? `— ${p.reference}` : ''}</span>
                  <span className="font-medium">Q{(p.amount || 0).toFixed(2)}</span>
                </div>
              ))}
              {detail.cancellation_reason && <p className="text-xs text-red-600">Motivo anulación: {detail.cancellation_reason}</p>}
            </div>
          )}
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => printReceipt(detail.id)}><Printer className="w-3.5 h-3.5 mr-1" />Imprimir</Button>
            {detail?.status !== 'cancelled' && <Button variant="outline" className="text-red-600" onClick={() => handleCancel(detail.id)} data-testid="cancel-sale-btn"><Ban className="w-3.5 h-3.5 mr-1" />Anular</Button>}
            <Button onClick={() => setDetail(null)}>Cerrar</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
