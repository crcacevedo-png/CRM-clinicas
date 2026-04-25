import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../context/AuthContext';
import { useBranch } from '../../context/BranchContext';
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
  CreditCard, Plus, Search, ChevronLeft, ChevronRight, TrendingUp, TrendingDown,
  AlertCircle, Trash2, Paperclip, BarChart3, Building2, FileText, Edit
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const CATEGORIES = [
  { v: 'rent', l: 'Alquiler' }, { v: 'utilities', l: 'Servicios públicos' },
  { v: 'salaries', l: 'Salarios' }, { v: 'supplies', l: 'Suministros' },
  { v: 'equipment', l: 'Equipo' }, { v: 'marketing', l: 'Marketing' },
  { v: 'professional_services', l: 'Servicios profesionales' }, { v: 'taxes', l: 'Impuestos' },
  { v: 'maintenance', l: 'Mantenimiento' }, { v: 'other', l: 'Otro' },
];
const PAY_LABEL = { cash: 'Efectivo', credit_card: 'Tarjeta crédito', debit_card: 'Tarjeta débito', transfer: 'Transferencia', credit: 'Crédito', check: 'Cheque', other: 'Otro' };
const STATUS_LABEL = { pending: 'Pendiente', partial: 'Parcial', paid: 'Pagado' };

export default function ExpensesPage() {
  const { getAuthHeaders } = useAuth();
  const { branches, activeBranch } = useBranch();
  const headers = getAuthHeaders();
  const [tab, setTab] = useState('list');

  return (
    <FeatureGate feature="expenses" planRequired="Professional">
      <div className="p-6 lg:p-8" data-testid="expenses-page">
        <h1 className="text-2xl font-bold text-slate-900 mb-1">Gastos</h1>
        <p className="text-sm text-slate-500 mb-4">Registro y análisis de egresos operativos</p>
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="bg-slate-100 mb-4">
            <TabsTrigger value="list" data-testid="exp-tab-list"><FileText className="w-3.5 h-3.5 mr-1" />Gastos</TabsTrigger>
            <TabsTrigger value="category" data-testid="exp-tab-category"><BarChart3 className="w-3.5 h-3.5 mr-1" />Por categoría</TabsTrigger>
            <TabsTrigger value="supplier" data-testid="exp-tab-supplier"><Building2 className="w-3.5 h-3.5 mr-1" />Por proveedor</TabsTrigger>
          </TabsList>
          <TabsContent value="list"><ListTab headers={headers} branches={branches} activeBranch={activeBranch} /></TabsContent>
          <TabsContent value="category"><CategoryReportTab headers={headers} branches={branches} /></TabsContent>
          <TabsContent value="supplier"><SupplierReportTab headers={headers} /></TabsContent>
        </Tabs>
      </div>
    </FeatureGate>
  );
}

/* ============ LIST TAB ============ */
function ListTab({ headers, branches, activeBranch }) {
  const [dashboard, setDashboard] = useState(null);
  const [expenses, setExpenses] = useState([]);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [filters, setFilters] = useState({ q: '', category: 'all', status: 'all', branch: 'all', dateFrom: '', dateTo: '' });
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [edit, setEdit] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(page), limit: '20' });
      if (filters.q) params.set('q', filters.q);
      if (filters.category !== 'all') params.set('category', filters.category);
      if (filters.status !== 'all') params.set('payment_status', filters.status);
      if (filters.branch !== 'all') params.set('branch_id', filters.branch);
      if (filters.dateFrom) params.set('date_from', filters.dateFrom);
      if (filters.dateTo) params.set('date_to', filters.dateTo);
      const [d, l] = await Promise.all([
        axios.get(`${API}/clinic/expenses/dashboard`, { headers }),
        axios.get(`${API}/clinic/expenses?${params}`, { headers }),
      ]);
      setDashboard(d.data);
      setExpenses(l.data.expenses || []);
      setPages(l.data.pages || 1);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [page, filters, headers]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setPage(1); }, [filters]);

  const handleDelete = async (id) => {
    if (!window.confirm('¿Eliminar este gasto?')) return;
    try {
      await axios.delete(`${API}/clinic/expenses/${id}`, { headers });
      toast.success('Gasto eliminado'); load();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error'); }
  };

  const handleAttachment = async (id) => {
    try {
      const r = await axios.get(`${API}/clinic/expenses/${id}/attachment-url`, { headers });
      if (r.data.url) window.open(r.data.url, '_blank');
      else toast.error('Sin adjunto');
    } catch { toast.error('Error'); }
  };

  const delta = dashboard?.delta_pct;
  return (
    <>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <Card><CardContent className="p-4">
          <p className="text-xs text-slate-500 font-medium">Gastos del mes</p>
          <p className="text-2xl font-bold text-teal-600 mt-1">Q{(dashboard?.this_month || 0).toFixed(2)}</p>
        </CardContent></Card>
        <Card><CardContent className="p-4">
          <p className="text-xs text-slate-500 font-medium">Mes anterior</p>
          <p className="text-2xl font-bold text-slate-700 mt-1">Q{(dashboard?.prev_month || 0).toFixed(2)}</p>
          {delta != null && <p className={`text-xs mt-0.5 flex items-center gap-1 ${delta >= 0 ? 'text-red-600' : 'text-emerald-600'}`}>{delta >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}{Math.abs(delta).toFixed(1)}% vs mes anterior</p>}
        </CardContent></Card>
        <Card><CardContent className="p-4">
          <p className="text-xs text-slate-500 font-medium">Top categoría</p>
          <p className="text-base font-bold text-slate-800 mt-1">{dashboard?.top_category?.label || '—'}</p>
          <p className="text-sm text-slate-600">Q{(dashboard?.top_category?.amount || 0).toFixed(2)}</p>
        </CardContent></Card>
        <Card><CardContent className="p-4">
          <p className="text-xs text-slate-500 font-medium flex items-center gap-1"><AlertCircle className="w-3 h-3 text-amber-600" />Pendientes</p>
          <p className="text-2xl font-bold text-amber-600 mt-1">Q{(dashboard?.pending?.amount || 0).toFixed(2)}</p>
          <p className="text-xs text-slate-400">{dashboard?.pending?.count || 0} sin pagar</p>
        </CardContent></Card>
      </div>

      <div className="flex flex-wrap gap-2 mb-4">
        <div className="relative flex-1 min-w-[200px] max-w-md">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <Input className="pl-9 text-sm" placeholder="Buscar..." value={filters.q} onChange={e => setFilters(f => ({ ...f, q: e.target.value }))} data-testid="expense-search" />
        </div>
        <Select value={filters.category} onValueChange={v => setFilters(f => ({ ...f, category: v }))}>
          <SelectTrigger className="w-44"><SelectValue placeholder="Categoría" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todas</SelectItem>
            {CATEGORIES.map(c => <SelectItem key={c.v} value={c.v}>{c.l}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={filters.status} onValueChange={v => setFilters(f => ({ ...f, status: v }))}>
          <SelectTrigger className="w-40"><SelectValue placeholder="Estado" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todos</SelectItem>
            <SelectItem value="paid">Pagado</SelectItem>
            <SelectItem value="pending">Pendiente</SelectItem>
            <SelectItem value="partial">Parcial</SelectItem>
          </SelectContent>
        </Select>
        <Select value={filters.branch} onValueChange={v => setFilters(f => ({ ...f, branch: v }))}>
          <SelectTrigger className="w-44"><SelectValue placeholder="Sucursal" /></SelectTrigger>
          <SelectContent><SelectItem value="all">Todas</SelectItem>{(branches || []).map(b => <SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>)}</SelectContent>
        </Select>
        <Input type="date" className="w-40" value={filters.dateFrom} onChange={e => setFilters(f => ({ ...f, dateFrom: e.target.value }))} placeholder="Desde" />
        <Input type="date" className="w-40" value={filters.dateTo} onChange={e => setFilters(f => ({ ...f, dateTo: e.target.value }))} placeholder="Hasta" />
        <Button className="bg-teal-600 hover:bg-teal-700 ml-auto" onClick={() => { setEdit(null); setShowForm(true); }} data-testid="new-expense-btn"><Plus className="w-4 h-4 mr-1" />Nuevo gasto</Button>
      </div>

      {loading ? <div className="flex justify-center py-16"><div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" /></div> :
        <Card className="border overflow-hidden">
          <Table>
            <TableHeader><TableRow className="bg-slate-50/80">
              <TableHead className="text-xs font-semibold">Fecha</TableHead>
              <TableHead className="text-xs font-semibold">Categoría</TableHead>
              <TableHead className="text-xs font-semibold">Descripción</TableHead>
              <TableHead className="text-xs font-semibold">Proveedor</TableHead>
              <TableHead className="text-xs font-semibold text-right">Total</TableHead>
              <TableHead className="text-xs font-semibold text-center">Pago</TableHead>
              <TableHead className="text-xs font-semibold text-center">Estado</TableHead>
              <TableHead className="text-xs font-semibold">Sucursal</TableHead>
              <TableHead className="text-xs font-semibold text-right"></TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {expenses.map(e => (
                <TableRow key={e.id} data-testid={`expense-row-${e.id}`}>
                  <TableCell className="text-xs">{e.expense_date}</TableCell>
                  <TableCell className="text-sm">{e.category_label}{e.subcategory && <p className="text-xs text-slate-400">{e.subcategory}</p>}</TableCell>
                  <TableCell className="text-sm max-w-[220px] truncate">{e.description}{e.document_number && <p className="text-xs text-slate-400">{e.document_type || 'Doc'}: {e.document_number}</p>}</TableCell>
                  <TableCell className="text-xs text-slate-500">{e.supplier_name || '—'}</TableCell>
                  <TableCell className="text-right text-sm font-bold">Q{(+e.total || 0).toFixed(2)}</TableCell>
                  <TableCell className="text-center text-xs">{PAY_LABEL[e.payment_method] || '—'}</TableCell>
                  <TableCell className="text-center"><Badge variant="outline" className={`text-xs ${e.payment_status === 'paid' ? 'bg-emerald-50 text-emerald-700' : e.payment_status === 'pending' ? 'bg-amber-50 text-amber-700' : 'bg-blue-50 text-blue-700'}`}>{STATUS_LABEL[e.payment_status]}</Badge></TableCell>
                  <TableCell className="text-xs text-slate-500">{e.branch_name || '—'}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      {e.attachment_url && <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => handleAttachment(e.id)} title="Ver adjunto"><Paperclip className="w-3.5 h-3.5 text-teal-600" /></Button>}
                      <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => { setEdit(e); setShowForm(true); }} data-testid={`edit-expense-${e.id}`}><Edit className="w-3.5 h-3.5" /></Button>
                      <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => handleDelete(e.id)}><Trash2 className="w-3.5 h-3.5 text-red-500" /></Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {expenses.length === 0 && <TableRow><TableCell colSpan={9} className="text-center py-8 text-slate-400">Sin gastos registrados</TableCell></TableRow>}
            </TableBody>
          </Table>
        </Card>}

      {pages > 1 && <div className="flex justify-between mt-4"><p className="text-xs text-slate-500">Pág {page}/{pages}</p><div className="flex gap-1"><Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}><ChevronLeft className="w-4 h-4" /></Button><Button variant="outline" size="sm" disabled={page >= pages} onClick={() => setPage(p => p + 1)}><ChevronRight className="w-4 h-4" /></Button></div></div>}

      <ExpenseFormDialog open={showForm} onClose={() => setShowForm(false)} edit={edit} headers={headers} branches={branches} activeBranch={activeBranch} onDone={() => { setShowForm(false); load(); }} />
    </>
  );
}

/* ============ EXPENSE FORM ============ */
function ExpenseFormDialog({ open, onClose, edit, headers, branches, activeBranch, onDone }) {
  const [form, setForm] = useState({});
  const [suppliers, setSuppliers] = useState([]);
  const [supplierSearch, setSupplierSearch] = useState('');
  const [saving, setSaving] = useState(false);
  const [file, setFile] = useState(null);

  useEffect(() => {
    if (!open) return;
    if (edit) {
      setForm({ ...edit });
      setSupplierSearch(edit.supplier_name || '');
    } else {
      const today = new Date().toISOString().slice(0, 10);
      setForm({
        expense_date: today, category: 'other', subcategory: '', description: '',
        amount: 0, tax_amount: 0, payment_method: 'cash', payment_status: 'paid',
        document_type: '', document_number: '',
        branch_id: activeBranch?.id || (branches || [])[0]?.id || null,
        supplier_id: null, notes: '',
      });
      setSupplierSearch('');
    }
    setFile(null);
    (async () => {
      try {
        const r = await axios.get(`${API}/clinic/inventory/suppliers`, { headers });
        setSuppliers(r.data || []);
      } catch { /* ignore */ }
    })();
  }, [open, edit, activeBranch, branches, headers]);

  const total = (parseFloat(form.amount) || 0) + (parseFloat(form.tax_amount) || 0);
  const uf = (k, v) => setForm(p => ({ ...p, [k]: v }));

  const handleSave = async () => {
    if (!form.description) { toast.error('Descripción requerida'); return; }
    if (!form.category) { toast.error('Categoría requerida'); return; }
    setSaving(true);
    try {
      const payload = { ...form };
      if (!payload.supplier_id) delete payload.supplier_id;
      if (!payload.branch_id) delete payload.branch_id;
      let id = edit?.id;
      if (edit) {
        await axios.put(`${API}/clinic/expenses/${edit.id}`, payload, { headers });
      } else {
        const r = await axios.post(`${API}/clinic/expenses`, payload, { headers });
        id = r.data.id;
      }
      // Upload attachment if any
      if (file && id) {
        const fd = new FormData();
        fd.append('file', file);
        await axios.post(`${API}/clinic/expenses/${id}/attachment`, fd, { headers: { ...headers, 'Content-Type': 'multipart/form-data' } });
      }
      toast.success(edit ? 'Gasto actualizado' : 'Gasto registrado');
      onDone();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error'); }
    finally { setSaving(false); }
  };

  const filteredSuppliers = suppliers.filter(s => !supplierSearch || s.name.toLowerCase().includes(supplierSearch.toLowerCase()));

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-xl max-h-[88vh] overflow-y-auto" data-testid="expense-form-dialog">
        <DialogHeader><DialogTitle>{edit ? 'Editar' : 'Nuevo'} gasto</DialogTitle></DialogHeader>
        <div className="space-y-3 py-2">
          <div className="grid grid-cols-3 gap-3">
            <div><Label className="text-xs">Fecha *</Label><Input type="date" className="mt-1 text-sm" value={form.expense_date || ''} onChange={e => uf('expense_date', e.target.value)} data-testid="expense-date-input" /></div>
            <div className="col-span-2">
              <Label className="text-xs">Sucursal</Label>
              <Select value={form.branch_id || 'none'} onValueChange={v => uf('branch_id', v === 'none' ? null : v)}>
                <SelectTrigger className="mt-1 text-sm"><SelectValue placeholder="Sin sucursal" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">Sin sucursal</SelectItem>
                  {(branches || []).map(b => <SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-xs">Categoría *</Label>
              <Select value={form.category} onValueChange={v => uf('category', v)}>
                <SelectTrigger className="mt-1 text-sm" data-testid="expense-category-select"><SelectValue /></SelectTrigger>
                <SelectContent>{CATEGORIES.map(c => <SelectItem key={c.v} value={c.v}>{c.l}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div><Label className="text-xs">Subcategoría</Label><Input className="mt-1 text-sm" value={form.subcategory || ''} onChange={e => uf('subcategory', e.target.value)} placeholder="Específico" /></div>
          </div>

          <div className="relative">
            <Label className="text-xs">Proveedor (opcional)</Label>
            <Input className="mt-1 text-sm" value={supplierSearch} onChange={e => { setSupplierSearch(e.target.value); if (!e.target.value) uf('supplier_id', null); }} placeholder="Buscar proveedor..." />
            {supplierSearch && filteredSuppliers.length > 0 && supplierSearch !== (suppliers.find(s => s.id === form.supplier_id)?.name || '') && (
              <div className="absolute z-50 w-full bg-white border rounded shadow-lg mt-1 max-h-32 overflow-y-auto">
                {filteredSuppliers.slice(0, 6).map(s => (
                  <button key={s.id} type="button" className="w-full px-3 py-1.5 text-left hover:bg-teal-50 text-sm" onMouseDown={() => { uf('supplier_id', s.id); setSupplierSearch(s.name); }}>
                    {s.name}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div><Label className="text-xs">Descripción *</Label><Textarea className="mt-1 text-sm min-h-[50px]" value={form.description || ''} onChange={e => uf('description', e.target.value)} data-testid="expense-description-input" /></div>

          <div className="grid grid-cols-3 gap-3">
            <div><Label className="text-xs">Monto sin IVA (Q)</Label><Input type="number" step="0.01" className="mt-1 text-sm" value={form.amount ?? 0} onChange={e => uf('amount', parseFloat(e.target.value) || 0)} data-testid="expense-amount-input" /></div>
            <div><Label className="text-xs">IVA (Q)</Label><Input type="number" step="0.01" className="mt-1 text-sm" value={form.tax_amount ?? 0} onChange={e => uf('tax_amount', parseFloat(e.target.value) || 0)} /></div>
            <div><Label className="text-xs">Total</Label><p className="mt-2 text-base font-bold text-teal-600">Q{total.toFixed(2)}</p></div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-xs">Método de pago</Label>
              <Select value={form.payment_method || 'cash'} onValueChange={v => uf('payment_method', v)}>
                <SelectTrigger className="mt-1 text-sm"><SelectValue /></SelectTrigger>
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
            <div>
              <Label className="text-xs">Estado</Label>
              <Select value={form.payment_status || 'paid'} onValueChange={v => uf('payment_status', v)}>
                <SelectTrigger className="mt-1 text-sm" data-testid="expense-status-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="paid">Pagado</SelectItem>
                  <SelectItem value="pending">Pendiente</SelectItem>
                  <SelectItem value="partial">Parcial</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div><Label className="text-xs">Tipo de documento</Label><Input className="mt-1 text-sm" value={form.document_type || ''} onChange={e => uf('document_type', e.target.value)} placeholder="Factura, Recibo..." /></div>
            <div><Label className="text-xs">Número</Label><Input className="mt-1 text-sm" value={form.document_number || ''} onChange={e => uf('document_number', e.target.value)} /></div>
          </div>

          <div>
            <Label className="text-xs">Adjuntar comprobante (PDF/imagen)</Label>
            <Input type="file" accept=".pdf,image/*" className="mt-1 text-sm" onChange={e => setFile(e.target.files?.[0] || null)} data-testid="expense-file-input" />
            {file && <p className="text-xs text-slate-500 mt-1">{file.name} ({(file.size / 1024).toFixed(0)} KB)</p>}
            {edit?.attachment_url && !file && <p className="text-xs text-emerald-600 mt-1 flex items-center gap-1"><Paperclip className="w-3 h-3" />Ya tiene adjunto</p>}
          </div>

          <div><Label className="text-xs">Notas</Label><Textarea className="mt-1 text-sm min-h-[40px]" value={form.notes || ''} onChange={e => uf('notes', e.target.value)} /></div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancelar</Button>
          <Button className="bg-teal-600 hover:bg-teal-700" onClick={handleSave} disabled={saving} data-testid="save-expense-btn">{saving ? '...' : 'Guardar'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/* ============ CATEGORY REPORT ============ */
function CategoryReportTab({ headers, branches }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const today = new Date();
  const firstThis = new Date(today.getFullYear(), today.getMonth(), 1).toISOString().slice(0, 10);
  const lastThis = new Date(today.getFullYear(), today.getMonth() + 1, 0).toISOString().slice(0, 10);
  const [from, setFrom] = useState(firstThis);
  const [to, setTo] = useState(lastThis);
  const [branch, setBranch] = useState('all');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (from) params.set('date_from', from);
      if (to) params.set('date_to', to);
      if (branch !== 'all') params.set('branch_id', branch);
      const r = await axios.get(`${API}/clinic/expenses/by-category?${params}`, { headers });
      setData(r.data);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [from, to, branch, headers]);

  useEffect(() => { load(); }, [load]);

  return (
    <>
      <div className="flex flex-wrap gap-3 mb-4 items-end">
        <div><Label className="text-xs">Desde</Label><Input type="date" className="mt-1" value={from} onChange={e => setFrom(e.target.value)} data-testid="cat-from" /></div>
        <div><Label className="text-xs">Hasta</Label><Input type="date" className="mt-1" value={to} onChange={e => setTo(e.target.value)} data-testid="cat-to" /></div>
        <div><Label className="text-xs">Sucursal</Label>
          <Select value={branch} onValueChange={setBranch}>
            <SelectTrigger className="w-44 mt-1"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="all">Todas</SelectItem>{(branches || []).map(b => <SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>)}</SelectContent>
          </Select>
        </div>
      </div>

      {loading ? <div className="flex justify-center py-16"><div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" /></div> :
        <>
          <Card className="mb-4">
            <CardContent className="p-4">
              <p className="text-xs text-slate-500 mb-1">Total del período</p>
              <p className="text-3xl font-bold text-teal-600">Q{(data?.total || 0).toFixed(2)}</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm font-semibold">Distribución por categoría</CardTitle></CardHeader>
            <CardContent>
              <div className="space-y-3">
                {(data?.categories || []).map(c => {
                  const pct = data.total > 0 ? (c.amount / data.total * 100) : 0;
                  return (
                    <div key={c.category} data-testid={`cat-bar-${c.category}`}>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="font-medium text-slate-700">{c.label}</span>
                        <span className="text-slate-500">Q{c.amount.toFixed(2)} ({pct.toFixed(1)}% · {c.count})</span>
                      </div>
                      <div className="h-3 bg-slate-100 rounded-full overflow-hidden">
                        <div className="h-full bg-gradient-to-r from-teal-500 to-teal-600 rounded-full transition-all" style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  );
                })}
                {(data?.categories || []).length === 0 && <p className="text-sm text-slate-400 text-center py-6">Sin gastos en este período</p>}
              </div>
            </CardContent>
          </Card>
        </>}
    </>
  );
}

/* ============ SUPPLIER REPORT ============ */
function SupplierReportTab({ headers }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const today = new Date();
  const firstYear = `${today.getFullYear()}-01-01`;
  const lastYear = `${today.getFullYear()}-12-31`;
  const [from, setFrom] = useState(firstYear);
  const [to, setTo] = useState(lastYear);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (from) params.set('date_from', from);
      if (to) params.set('date_to', to);
      const r = await axios.get(`${API}/clinic/expenses/by-supplier?${params}`, { headers });
      setData(r.data);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [from, to, headers]);

  useEffect(() => { load(); }, [load]);

  return (
    <>
      <div className="flex flex-wrap gap-3 mb-4 items-end">
        <div><Label className="text-xs">Desde</Label><Input type="date" className="mt-1" value={from} onChange={e => setFrom(e.target.value)} data-testid="sup-from" /></div>
        <div><Label className="text-xs">Hasta</Label><Input type="date" className="mt-1" value={to} onChange={e => setTo(e.target.value)} data-testid="sup-to" /></div>
      </div>

      {loading ? <div className="flex justify-center py-16"><div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" /></div> :
        <Card className="border overflow-hidden">
          <Table>
            <TableHeader><TableRow className="bg-slate-50/80">
              <TableHead className="text-xs font-semibold">Proveedor</TableHead>
              <TableHead className="text-xs font-semibold text-center">Transacciones</TableHead>
              <TableHead className="text-xs font-semibold text-right">Total gastado</TableHead>
              <TableHead className="text-xs font-semibold text-right">% del total</TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {(data?.suppliers || []).map(s => {
                const pct = data.total > 0 ? (s.amount / data.total * 100) : 0;
                return (
                  <TableRow key={s.supplier_id} data-testid={`sup-row-${s.supplier_id}`}>
                    <TableCell className="text-sm font-medium">{s.supplier_name}</TableCell>
                    <TableCell className="text-center text-sm">{s.count}</TableCell>
                    <TableCell className="text-right text-sm font-bold">Q{s.amount.toFixed(2)}</TableCell>
                    <TableCell className="text-right text-xs text-slate-500">{pct.toFixed(1)}%</TableCell>
                  </TableRow>
                );
              })}
              {(data?.suppliers || []).length === 0 && <TableRow><TableCell colSpan={4} className="text-center py-8 text-slate-400">Sin gastos asociados a proveedores</TableCell></TableRow>}
            </TableBody>
          </Table>
          {data?.total > 0 && <div className="bg-slate-50 p-3 text-right text-sm font-bold">Total: Q{data.total.toFixed(2)}</div>}
        </Card>}
    </>
  );
}
