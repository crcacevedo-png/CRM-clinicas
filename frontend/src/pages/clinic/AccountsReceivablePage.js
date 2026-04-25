import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../context/AuthContext';
import FeatureGate from '../../components/FeatureGate';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
import { Badge } from '../../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../components/ui/dialog';
import { Separator } from '../../components/ui/separator';
import { toast } from 'sonner';
import {
  Receipt, Search, AlertCircle, Clock, Users as UsersIcon, DollarSign,
  CalendarDays, FileText, Wallet, Layers, ChevronLeft, ChevronRight, CreditCard
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const STATUS_LABEL = { pending: 'Pendiente', partial: 'Parcial', paid: 'Pagada' };
const PAY_LABEL = { cash: 'Efectivo', credit_card: 'Tarjeta crédito', debit_card: 'Tarjeta débito', transfer: 'Transferencia', credit: 'Crédito', check: 'Cheque', other: 'Otro' };
const TRAFFIC_CLASS = { green: 'bg-emerald-50 text-emerald-700', amber: 'bg-amber-50 text-amber-700', red: 'bg-red-50 text-red-700' };

export default function AccountsReceivablePage() {
  const { getAuthHeaders } = useAuth();
  const headers = getAuthHeaders();
  const [tab, setTab] = useState('accounts');

  return (
    <FeatureGate feature="accounts_receivable" planRequired="Professional">
      <div className="p-6 lg:p-8" data-testid="ar-page">
        <h1 className="text-2xl font-bold text-slate-900 mb-1">Cuentas por cobrar</h1>
        <p className="text-sm text-slate-500 mb-4">Gestión de saldos pendientes y planes de pago</p>
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="bg-slate-100 mb-4">
            <TabsTrigger value="accounts" data-testid="ar-tab-accounts"><Receipt className="w-3.5 h-3.5 mr-1" />Cuentas</TabsTrigger>
            <TabsTrigger value="installments" data-testid="ar-tab-installments"><CalendarDays className="w-3.5 h-3.5 mr-1" />Cuotas</TabsTrigger>
            <TabsTrigger value="aging" data-testid="ar-tab-aging"><Layers className="w-3.5 h-3.5 mr-1" />Antigüedad</TabsTrigger>
          </TabsList>
          <TabsContent value="accounts"><AccountsTab headers={headers} /></TabsContent>
          <TabsContent value="installments"><InstallmentsTab headers={headers} /></TabsContent>
          <TabsContent value="aging"><AgingTab headers={headers} /></TabsContent>
        </Tabs>
      </div>
    </FeatureGate>
  );
}

/* ============ ACCOUNTS TAB ============ */
function AccountsTab({ headers }) {
  const [dashboard, setDashboard] = useState(null);
  const [accounts, setAccounts] = useState([]);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [onlyOverdue, setOnlyOverdue] = useState(false);
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState(null);
  const [showPay, setShowPay] = useState(false);
  const [showPlan, setShowPlan] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(page), limit: '20' });
      if (statusFilter !== 'all') params.set('status', statusFilter);
      if (onlyOverdue) params.set('only_overdue', 'true');
      if (search) params.set('q', search);
      const [d, l] = await Promise.all([
        axios.get(`${API}/clinic/accounts-receivable/dashboard`, { headers }),
        axios.get(`${API}/clinic/accounts-receivable?${params}`, { headers }),
      ]);
      setDashboard(d.data);
      setAccounts(l.data.accounts || []);
      setPages(l.data.pages || 1);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [page, statusFilter, onlyOverdue, search, headers]);

  useEffect(() => { load(); }, [load]);

  const openDetail = async (id) => {
    try {
      const r = await axios.get(`${API}/clinic/accounts-receivable/${id}`, { headers });
      setDetail(r.data);
    } catch { toast.error('Error'); }
  };

  return (
    <>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <SummaryCard label="Total por cobrar" value={`Q${(dashboard?.total_balance || 0).toFixed(2)}`} icon={DollarSign} color="teal" />
        <SummaryCard label="Pacientes con deuda" value={dashboard?.patients_with_debt ?? 0} icon={UsersIcon} color="blue" />
        <SummaryCard label="Vencidas" value={`Q${(dashboard?.overdue?.amount || 0).toFixed(2)}`} sub={`${dashboard?.overdue?.count || 0} cuentas`} icon={AlertCircle} color="red" />
        <SummaryCard label="Vencen en 30 días" value={`Q${(dashboard?.upcoming_30d?.amount || 0).toFixed(2)}`} sub={`${dashboard?.upcoming_30d?.count || 0} cuentas`} icon={Clock} color="amber" />
      </div>

      <div className="flex flex-wrap gap-3 mb-4">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <Input className="pl-9 text-sm" placeholder="Buscar paciente o No. venta..." value={search} onChange={e => setSearch(e.target.value)} data-testid="ar-search" />
        </div>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-44"><SelectValue placeholder="Estado" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todos</SelectItem>
            <SelectItem value="pending">Pendiente</SelectItem>
            <SelectItem value="partial">Parcial</SelectItem>
            <SelectItem value="paid">Pagada</SelectItem>
          </SelectContent>
        </Select>
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" className="rounded" checked={onlyOverdue} onChange={e => setOnlyOverdue(e.target.checked)} data-testid="only-overdue-cb" />
          Solo vencidas
        </label>
      </div>

      {loading ? <div className="flex justify-center py-16"><div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" /></div> :
        <Card className="border overflow-hidden">
          <Table>
            <TableHeader><TableRow className="bg-slate-50/80">
              <TableHead className="text-xs font-semibold">Paciente</TableHead>
              <TableHead className="text-xs font-semibold">No. Venta</TableHead>
              <TableHead className="text-xs font-semibold">Origen</TableHead>
              <TableHead className="text-xs font-semibold text-right">Original</TableHead>
              <TableHead className="text-xs font-semibold text-right">Pagado</TableHead>
              <TableHead className="text-xs font-semibold text-right">Saldo</TableHead>
              <TableHead className="text-xs font-semibold text-center">Vence</TableHead>
              <TableHead className="text-xs font-semibold text-center">Estado</TableHead>
              <TableHead className="text-xs font-semibold text-right"></TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {accounts.map(a => (
                <TableRow key={a.id} data-testid={`ar-row-${a.id}`}>
                  <TableCell className="text-sm font-medium">{a.patient_name}</TableCell>
                  <TableCell className="text-xs font-mono">{a.sale_number || '—'}</TableCell>
                  <TableCell className="text-xs text-slate-500">{a.sale_created_at?.substring(0, 10) || a.created_at?.substring(0, 10)}</TableCell>
                  <TableCell className="text-right text-sm">Q{(a.original_amount || 0).toFixed(2)}</TableCell>
                  <TableCell className="text-right text-sm text-emerald-600">Q{(a.paid_amount || 0).toFixed(2)}</TableCell>
                  <TableCell className="text-right text-sm font-bold">Q{(a.balance || 0).toFixed(2)}</TableCell>
                  <TableCell className="text-center text-xs">
                    {a.due_date ? a.due_date : '—'}
                    {a.days_overdue > 0 && <p className="text-[10px] text-red-600">+{a.days_overdue}d</p>}
                  </TableCell>
                  <TableCell className="text-center">
                    <Badge variant="outline" className={`text-xs ${TRAFFIC_CLASS[a.traffic] || 'bg-slate-50'}`}>{STATUS_LABEL[a.status] || a.status}</Badge>
                  </TableCell>
                  <TableCell className="text-right"><Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => openDetail(a.id)} data-testid={`ar-open-${a.id}`}>Ver</Button></TableCell>
                </TableRow>
              ))}
              {accounts.length === 0 && <TableRow><TableCell colSpan={9} className="text-center py-8 text-slate-400">Sin cuentas por cobrar</TableCell></TableRow>}
            </TableBody>
          </Table>
        </Card>}

      {pages > 1 && <div className="flex justify-between mt-4"><p className="text-xs text-slate-500">Pág {page}/{pages}</p><div className="flex gap-1"><Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}><ChevronLeft className="w-4 h-4" /></Button><Button variant="outline" size="sm" disabled={page >= pages} onClick={() => setPage(p => p + 1)}><ChevronRight className="w-4 h-4" /></Button></div></div>}

      {/* Detail */}
      <Dialog open={!!detail} onOpenChange={() => setDetail(null)}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto" data-testid="ar-detail-dialog">
          <DialogHeader><DialogTitle>Cuenta — {detail?.patient_name}</DialogTitle></DialogHeader>
          {detail && (
            <div className="space-y-3 text-sm">
              <div className="grid grid-cols-3 gap-3 bg-slate-50 rounded p-3">
                <div><p className="text-xs text-slate-500">Original</p><p className="font-bold">Q{(detail.original_amount || 0).toFixed(2)}</p></div>
                <div><p className="text-xs text-slate-500">Pagado</p><p className="font-bold text-emerald-600">Q{(detail.paid_amount || 0).toFixed(2)}</p></div>
                <div><p className="text-xs text-slate-500">Saldo</p><p className="font-bold text-red-600">Q{(detail.balance || 0).toFixed(2)}</p></div>
              </div>
              <div className="grid grid-cols-3 gap-3 text-xs">
                <div><span className="text-slate-500">Estado:</span> <Badge variant="outline" className={`text-xs ${TRAFFIC_CLASS[detail.traffic]}`}>{STATUS_LABEL[detail.status]}</Badge></div>
                <div><span className="text-slate-500">Vence:</span> <span className="font-medium">{detail.due_date}</span></div>
                <div><span className="text-slate-500">Tel:</span> <span className="font-medium">{detail.patient_phone || '—'}</span></div>
              </div>

              {detail.sale && (
                <>
                  <Separator />
                  <p className="text-xs font-bold text-slate-500 uppercase">Venta original — {detail.sale.sale_number}</p>
                  {(detail.sale.items || []).map((it, i) => (
                    <div key={i} className="flex justify-between text-xs">
                      <span>{it.quantity} × {it.description}</span>
                      <span className="font-medium">Q{(it.total || 0).toFixed(2)}</span>
                    </div>
                  ))}
                  {(detail.initial_payments || []).length > 0 && (
                    <>
                      <p className="text-xs text-slate-500 mt-2">Pagos al momento de la venta:</p>
                      {detail.initial_payments.map(p => (
                        <div key={p.id} className="flex justify-between text-xs"><span>{PAY_LABEL[p.payment_method] || p.payment_method}</span><span>Q{(+p.amount).toFixed(2)}</span></div>
                      ))}
                    </>
                  )}
                </>
              )}

              {(detail.ar_payments || []).length > 0 && (
                <>
                  <Separator />
                  <p className="text-xs font-bold text-slate-500 uppercase">Abonos posteriores</p>
                  {detail.ar_payments.map(p => (
                    <div key={p.id} className="flex justify-between text-xs">
                      <span>{p.paid_at?.substring(0, 10)} — {PAY_LABEL[p.payment_method] || p.payment_method} {p.reference ? `(${p.reference})` : ''}</span>
                      <span className="font-medium text-emerald-600">+Q{(+p.amount).toFixed(2)}</span>
                    </div>
                  ))}
                </>
              )}

              {detail.has_payment_plan && (
                <>
                  <Separator />
                  <p className="text-xs font-bold text-slate-500 uppercase">Plan de pagos ({detail.installments} cuotas)</p>
                  <Table>
                    <TableHeader><TableRow><TableHead className="text-xs">#</TableHead><TableHead className="text-xs">Vence</TableHead><TableHead className="text-xs text-right">Monto</TableHead><TableHead className="text-xs text-right">Pagado</TableHead><TableHead className="text-xs text-center">Estado</TableHead></TableRow></TableHeader>
                    <TableBody>
                      {(detail.installments_list || []).map(i => (
                        <TableRow key={i.id}>
                          <TableCell className="text-xs">{i.installment_number}</TableCell>
                          <TableCell className="text-xs">{i.due_date}</TableCell>
                          <TableCell className="text-xs text-right">Q{(+i.amount).toFixed(2)}</TableCell>
                          <TableCell className="text-xs text-right text-emerald-600">Q{(+(i.paid_amount || 0)).toFixed(2)}</TableCell>
                          <TableCell className="text-center"><Badge variant="outline" className="text-xs">{STATUS_LABEL[i.status] || i.status}</Badge></TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </>
              )}
            </div>
          )}
          <DialogFooter className="gap-2 flex-wrap">
            {detail?.status !== 'paid' && (
              <>
                {!detail?.has_payment_plan && <Button variant="outline" onClick={() => setShowPlan(true)} data-testid="create-plan-btn"><CalendarDays className="w-3.5 h-3.5 mr-1" />Convertir a plan de pagos</Button>}
                <Button className="bg-teal-600 hover:bg-teal-700" onClick={() => setShowPay(true)} data-testid="register-payment-btn"><Wallet className="w-3.5 h-3.5 mr-1" />Registrar pago</Button>
              </>
            )}
            <Button variant="outline" onClick={() => setDetail(null)}>Cerrar</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <RegisterPaymentDialog open={showPay} onClose={() => setShowPay(false)} ar={detail} headers={headers} onDone={() => { setShowPay(false); openDetail(detail.id); load(); }} />
      <CreatePlanDialog open={showPlan} onClose={() => setShowPlan(false)} ar={detail} headers={headers} onDone={() => { setShowPlan(false); openDetail(detail.id); load(); }} />
    </>
  );
}

function SummaryCard({ label, value, sub, icon: Icon, color = 'slate' }) {
  const c = { teal: 'text-teal-600', blue: 'text-blue-600', red: 'text-red-600', amber: 'text-amber-600' };
  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
          <p className="text-xs text-slate-500 font-medium">{label}</p>
          {Icon && <Icon className={`w-4 h-4 ${c[color]}`} />}
        </div>
        <p className={`text-2xl font-bold mt-1 ${c[color]}`}>{value}</p>
        {sub && <p className="text-xs text-slate-400">{sub}</p>}
      </CardContent>
    </Card>
  );
}

/* ============ REGISTER PAYMENT DIALOG ============ */
function RegisterPaymentDialog({ open, onClose, ar, headers, onDone }) {
  const [form, setForm] = useState({ amount: 0, payment_method: 'cash', reference: '', notes: '' });
  const [saving, setSaving] = useState(false);
  useEffect(() => { if (open && ar) setForm({ amount: ar.balance || 0, payment_method: 'cash', reference: '', notes: '' }); }, [open, ar]);

  const handleSave = async () => {
    if (!form.amount || form.amount <= 0) { toast.error('Monto inválido'); return; }
    if (form.amount > (ar.balance || 0) + 0.01) { toast.error('Monto excede el saldo'); return; }
    setSaving(true);
    try {
      await axios.post(`${API}/clinic/accounts-receivable/${ar.id}/payment`, form, { headers });
      toast.success('Pago registrado');
      onDone();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error'); }
    finally { setSaving(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-sm" data-testid="register-payment-dialog">
        <DialogHeader><DialogTitle>Registrar pago</DialogTitle></DialogHeader>
        <div className="space-y-3 py-2">
          <div className="bg-slate-50 rounded p-2 text-center">
            <p className="text-xs text-slate-500">Saldo actual</p>
            <p className="text-2xl font-bold text-red-600">Q{(ar?.balance || 0).toFixed(2)}</p>
          </div>
          <div><Label className="text-xs">Monto a pagar</Label><Input type="number" step="0.01" className="mt-1" value={form.amount} onChange={e => setForm(f => ({ ...f, amount: parseFloat(e.target.value) || 0 }))} data-testid="payment-amount-input" /></div>
          <div>
            <Label className="text-xs">Método de pago</Label>
            <Select value={form.payment_method} onValueChange={v => setForm(f => ({ ...f, payment_method: v }))}>
              <SelectTrigger className="mt-1 text-sm" data-testid="payment-method-select"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="cash">Efectivo</SelectItem>
                <SelectItem value="credit_card">Tarjeta crédito</SelectItem>
                <SelectItem value="debit_card">Tarjeta débito</SelectItem>
                <SelectItem value="transfer">Transferencia</SelectItem>
                <SelectItem value="check">Cheque</SelectItem>
                <SelectItem value="other">Otro</SelectItem>
              </SelectContent>
            </Select>
          </div>
          {(form.payment_method !== 'cash' && form.payment_method !== 'other') && (
            <div><Label className="text-xs">Referencia</Label><Input className="mt-1 text-sm" value={form.reference} onChange={e => setForm(f => ({ ...f, reference: e.target.value }))} placeholder="No. autorización" /></div>
          )}
          <div><Label className="text-xs">Notas</Label><Textarea className="mt-1 text-sm min-h-[40px]" value={form.notes} onChange={e => setForm(f => ({ ...f, notes: e.target.value }))} /></div>
          <div className="text-right text-xs text-slate-500">Saldo después: <span className="font-bold">Q{Math.max(0, (ar?.balance || 0) - (form.amount || 0)).toFixed(2)}</span></div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancelar</Button>
          <Button className="bg-teal-600 hover:bg-teal-700" onClick={handleSave} disabled={saving} data-testid="confirm-payment-btn">{saving ? '...' : 'Registrar'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/* ============ CREATE PLAN DIALOG ============ */
function CreatePlanDialog({ open, onClose, ar, headers, onDone }) {
  const [form, setForm] = useState({ installments: 3, first_due_date: '', frequency: 'monthly', amount_per_installment: '' });
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    if (open && ar) {
      const today = new Date(); today.setDate(today.getDate() + 30);
      setForm({ installments: 3, first_due_date: today.toISOString().slice(0, 10), frequency: 'monthly', amount_per_installment: '' });
    }
  }, [open, ar]);

  const balance = ar?.balance || 0;
  const computedAmount = form.installments > 0 ? +(balance / form.installments).toFixed(2) : 0;

  const handleSave = async () => {
    if (form.installments < 2) { toast.error('Mínimo 2 cuotas'); return; }
    if (!form.first_due_date) { toast.error('Fecha requerida'); return; }
    setSaving(true);
    try {
      const payload = { ...form };
      if (!payload.amount_per_installment) delete payload.amount_per_installment;
      await axios.post(`${API}/clinic/accounts-receivable/${ar.id}/payment-plan`, payload, { headers });
      toast.success('Plan de pagos creado');
      onDone();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error'); }
    finally { setSaving(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-sm" data-testid="create-plan-dialog">
        <DialogHeader><DialogTitle>Plan de pagos</DialogTitle></DialogHeader>
        <div className="space-y-3 py-2">
          <div className="bg-slate-50 rounded p-2 text-center">
            <p className="text-xs text-slate-500">Saldo a fraccionar</p>
            <p className="text-xl font-bold">Q{balance.toFixed(2)}</p>
          </div>
          <div><Label className="text-xs">Número de cuotas</Label><Input type="number" min={2} className="mt-1" value={form.installments} onChange={e => setForm(f => ({ ...f, installments: parseInt(e.target.value) || 0 }))} data-testid="plan-installments-input" /></div>
          <div>
            <Label className="text-xs">Frecuencia</Label>
            <Select value={form.frequency} onValueChange={v => setForm(f => ({ ...f, frequency: v }))}>
              <SelectTrigger className="mt-1 text-sm" data-testid="plan-frequency-select"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="weekly">Semanal</SelectItem>
                <SelectItem value="biweekly">Quincenal</SelectItem>
                <SelectItem value="monthly">Mensual</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div><Label className="text-xs">Primera cuota</Label><Input type="date" className="mt-1" value={form.first_due_date} onChange={e => setForm(f => ({ ...f, first_due_date: e.target.value }))} data-testid="plan-firstdue-input" /></div>
          <div><Label className="text-xs">Monto por cuota (opcional)</Label><Input type="number" step="0.01" className="mt-1" value={form.amount_per_installment} placeholder={`Auto: Q${computedAmount.toFixed(2)}`} onChange={e => setForm(f => ({ ...f, amount_per_installment: e.target.value }))} /></div>
          <p className="text-xs text-slate-500">{form.installments} cuotas × ~Q{computedAmount.toFixed(2)} = Q{(form.installments * computedAmount).toFixed(2)}</p>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancelar</Button>
          <Button className="bg-teal-600 hover:bg-teal-700" onClick={handleSave} disabled={saving} data-testid="confirm-plan-btn">{saving ? '...' : 'Crear plan'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/* ============ INSTALLMENTS TAB ============ */
function InstallmentsTab({ headers }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(60);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/clinic/accounts-receivable/installments?days_ahead=${days}`, { headers });
      setItems(r.data || []);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [days, headers]);

  useEffect(() => { load(); }, [load]);

  return (
    <>
      <div className="flex gap-3 mb-4 items-center">
        <Label className="text-xs">Próximos</Label>
        <Select value={String(days)} onValueChange={v => setDays(parseInt(v))}>
          <SelectTrigger className="w-36"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="7">7 días</SelectItem>
            <SelectItem value="30">30 días</SelectItem>
            <SelectItem value="60">60 días</SelectItem>
            <SelectItem value="90">90 días</SelectItem>
            <SelectItem value="365">1 año</SelectItem>
          </SelectContent>
        </Select>
        <p className="text-xs text-slate-500 ml-auto">{items.length} cuotas pendientes</p>
      </div>

      {loading ? <div className="flex justify-center py-16"><div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" /></div> :
        <Card className="border overflow-hidden">
          <Table>
            <TableHeader><TableRow className="bg-slate-50/80">
              <TableHead className="text-xs font-semibold">Vence</TableHead>
              <TableHead className="text-xs font-semibold">Paciente</TableHead>
              <TableHead className="text-xs font-semibold text-center">Cuota #</TableHead>
              <TableHead className="text-xs font-semibold text-right">Monto</TableHead>
              <TableHead className="text-xs font-semibold text-right">Pagado</TableHead>
              <TableHead className="text-xs font-semibold text-center">Días</TableHead>
              <TableHead className="text-xs font-semibold text-center">Estado</TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {items.map(i => {
                const days_to = i.days_to_due ?? 0;
                const traffic = days_to < 0 ? 'red' : days_to <= 7 ? 'amber' : 'green';
                return (
                  <TableRow key={i.id} data-testid={`installment-row-${i.id}`}>
                    <TableCell className="text-sm">{i.due_date}</TableCell>
                    <TableCell className="text-sm">{i.patient_name}</TableCell>
                    <TableCell className="text-center text-xs">{i.installment_number}</TableCell>
                    <TableCell className="text-right text-sm font-medium">Q{(+i.amount).toFixed(2)}</TableCell>
                    <TableCell className="text-right text-sm text-emerald-600">Q{(+(i.paid_amount || 0)).toFixed(2)}</TableCell>
                    <TableCell className="text-center text-xs"><Badge variant="outline" className={`text-xs ${TRAFFIC_CLASS[traffic]}`}>{days_to < 0 ? `+${Math.abs(days_to)}d vencida` : days_to === 0 ? 'Hoy' : `${days_to}d`}</Badge></TableCell>
                    <TableCell className="text-center"><Badge variant="outline" className="text-xs">{STATUS_LABEL[i.status] || i.status}</Badge></TableCell>
                  </TableRow>
                );
              })}
              {items.length === 0 && <TableRow><TableCell colSpan={7} className="text-center py-8 text-slate-400">Sin cuotas pendientes</TableCell></TableRow>}
            </TableBody>
          </Table>
        </Card>}
    </>
  );
}

/* ============ AGING TAB ============ */
function AgingTab({ headers }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const r = await axios.get(`${API}/clinic/accounts-receivable/aging`, { headers });
        setData(r.data);
      } catch { /* ignore */ }
      finally { setLoading(false); }
    })();
  }, [headers]);

  if (loading) return <div className="flex justify-center py-16"><div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" /></div>;
  if (!data) return null;

  const buckets = [
    { key: 'current', label: 'Al día', color: 'bg-emerald-50 border-emerald-200', text: 'text-emerald-700' },
    { key: 'd1_30', label: '1 - 30 días vencidas', color: 'bg-amber-50 border-amber-200', text: 'text-amber-700' },
    { key: 'd31_60', label: '31 - 60 días vencidas', color: 'bg-orange-50 border-orange-200', text: 'text-orange-700' },
    { key: 'd61_90', label: '61 - 90 días vencidas', color: 'bg-red-50 border-red-200', text: 'text-red-700' },
    { key: 'd90_plus', label: 'Más de 90 días', color: 'bg-red-100 border-red-300', text: 'text-red-800' },
  ];
  const totalAmount = buckets.reduce((s, b) => s + (data[b.key]?.amount || 0), 0);
  const totalCount = buckets.reduce((s, b) => s + (data[b.key]?.count || 0), 0);

  return (
    <>
      <Card className="mb-4">
        <CardHeader className="pb-2"><CardTitle className="text-sm font-semibold">Reporte de antigüedad</CardTitle></CardHeader>
        <CardContent>
          <p className="text-xs text-slate-500 mb-3">Distribución de cuentas pendientes según los días desde su fecha de vencimiento.</p>
          <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
            {buckets.map(b => {
              const pct = totalAmount > 0 ? ((data[b.key]?.amount || 0) / totalAmount * 100) : 0;
              return (
                <div key={b.key} className={`border rounded-lg p-3 ${b.color}`} data-testid={`aging-${b.key}`}>
                  <p className={`text-xs font-bold ${b.text}`}>{b.label}</p>
                  <p className={`text-2xl font-bold mt-1 ${b.text}`}>Q{(data[b.key]?.amount || 0).toFixed(2)}</p>
                  <p className="text-xs text-slate-500 mt-1">{data[b.key]?.count || 0} cuentas · {pct.toFixed(1)}%</p>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-4 flex items-center gap-4">
          <FileText className="w-8 h-8 text-slate-300" />
          <div>
            <p className="text-xs text-slate-500">TOTAL POR COBRAR</p>
            <p className="text-3xl font-bold text-slate-800">Q{totalAmount.toFixed(2)}</p>
            <p className="text-xs text-slate-500">{totalCount} cuentas activas</p>
          </div>
        </CardContent>
      </Card>
    </>
  );
}
