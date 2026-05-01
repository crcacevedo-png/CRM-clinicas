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
import { Switch } from '../../components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../components/ui/dialog';
import { Separator } from '../../components/ui/separator';
import { toast } from 'sonner';
import {
  Percent, Plus, Edit, Trash2, FileDown, DollarSign, Wallet, Clock, CheckCircle2, Eye
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const APPLIES_TO_LABEL = {
  all_consultations: 'Todas las consultas',
  all_products: 'Todos los productos',
  service: 'Servicio específico',
  product: 'Producto específico',
};

export default function CommissionsPage() {
  const { getAuthHeaders } = useAuth();
  const headers = getAuthHeaders();
  const [tab, setTab] = useState('dashboard');

  return (
    <FeatureGate feature="commissions" planRequired="Professional">
      <div className="p-6 lg:p-8" data-testid="commissions-page">
        <h1 className="text-2xl font-bold text-slate-900 mb-1">Comisiones</h1>
        <p className="text-sm text-slate-500 mb-4">Configuración y liquidación de comisiones por médico</p>
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="bg-slate-100 mb-4">
            <TabsTrigger value="dashboard" data-testid="comm-tab-dashboard"><DollarSign className="w-3.5 h-3.5 mr-1" />Liquidación</TabsTrigger>
            <TabsTrigger value="settings" data-testid="comm-tab-settings"><Percent className="w-3.5 h-3.5 mr-1" />Reglas</TabsTrigger>
          </TabsList>
          <TabsContent value="dashboard"><DashboardTab headers={headers} /></TabsContent>
          <TabsContent value="settings"><SettingsTab headers={headers} /></TabsContent>
        </Tabs>
      </div>
    </FeatureGate>
  );
}

/* ============ DASHBOARD TAB ============ */
function DashboardTab({ headers }) {
  const today = new Date();
  const firstThis = new Date(today.getFullYear(), today.getMonth(), 1).toISOString().slice(0, 10);
  const lastThis = new Date(today.getFullYear(), today.getMonth() + 1, 0).toISOString().slice(0, 10);
  const [from, setFrom] = useState(firstThis);
  const [to, setTo] = useState(lastThis);
  const [doctorId, setDoctorId] = useState('all');
  const [members, setMembers] = useState([]);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [drilldown, setDrilldown] = useState(null);
  const [generatingPdf, setGeneratingPdf] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ date_from: from, date_to: to });
      if (doctorId !== 'all') params.set('doctor_id', doctorId);
      const [d, m] = await Promise.all([
        axios.get(`${API}/clinic/commissions/dashboard?${params}`, { headers }),
        members.length === 0 ? axios.get(`${API}/clinic/members`, { headers }).catch(() => ({ data: [] })) : Promise.resolve({ data: members }),
      ]);
      setData(d.data);
      if (members.length === 0 && Array.isArray(m.data)) setMembers(m.data.filter(x => x.role === 'doctor'));
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [from, to, doctorId, headers, members.length, members]);

  useEffect(() => { load(); }, [load]);

  const openDrill = (did) => setDrilldown({ doctor_id: did });

  const generatePdf = async () => {
    setGeneratingPdf(true);
    try {
      const params = new URLSearchParams({ date_from: from, date_to: to });
      if (doctorId !== 'all') params.set('doctor_id', doctorId);
      const r = await axios.get(`${API}/clinic/commissions/report-pdf?${params}`, { headers });
      if (r.data.url) {
        window.open(r.data.url, '_blank');
        toast.success(`Reporte: ${r.data.count} comisiones, Q${r.data.total.toFixed(2)}`);
      } else toast.error('No se pudo generar');
    } catch (err) { toast.error(err.response?.data?.detail || 'Error'); }
    finally { setGeneratingPdf(false); }
  };

  return (
    <>
      <div className="flex flex-wrap gap-3 mb-4 items-end">
        <div><Label className="text-xs">Desde</Label><Input type="date" className="mt-1 w-40" value={from} onChange={e => setFrom(e.target.value)} data-testid="comm-from" /></div>
        <div><Label className="text-xs">Hasta</Label><Input type="date" className="mt-1 w-40" value={to} onChange={e => setTo(e.target.value)} data-testid="comm-to" /></div>
        <div>
          <Label className="text-xs">Médico</Label>
          <Select value={doctorId} onValueChange={setDoctorId}>
            <SelectTrigger className="w-52 mt-1"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos</SelectItem>
              {members.map(m => <SelectItem key={m.id} value={m.id}>Dr(a). {m.first_name} {m.last_name}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <Button variant="outline" className="ml-auto" onClick={generatePdf} disabled={generatingPdf} data-testid="export-pdf-btn">
          <FileDown className="w-4 h-4 mr-1" />{generatingPdf ? 'Generando...' : 'Reporte PDF'}
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
        <Card><CardContent className="p-4">
          <p className="text-xs text-slate-500 font-medium flex items-center gap-1"><DollarSign className="w-3.5 h-3.5" />Total generado</p>
          <p className="text-2xl font-bold text-teal-600 mt-1">Q{(data?.total_earned || 0).toFixed(2)}</p>
        </CardContent></Card>
        <Card><CardContent className="p-4">
          <p className="text-xs text-slate-500 font-medium flex items-center gap-1 text-emerald-700"><CheckCircle2 className="w-3.5 h-3.5" />Pagadas</p>
          <p className="text-2xl font-bold text-emerald-600 mt-1">Q{(data?.total_paid || 0).toFixed(2)}</p>
        </CardContent></Card>
        <Card><CardContent className="p-4">
          <p className="text-xs text-slate-500 font-medium flex items-center gap-1 text-amber-700"><Clock className="w-3.5 h-3.5" />Pendientes</p>
          <p className="text-2xl font-bold text-amber-600 mt-1">Q{(data?.total_pending || 0).toFixed(2)}</p>
        </CardContent></Card>
      </div>

      {loading ? <div className="flex justify-center py-12"><div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" /></div> :
        <Card className="border overflow-hidden">
          <Table>
            <TableHeader><TableRow className="bg-slate-50/80">
              <TableHead className="text-xs font-semibold">Médico</TableHead>
              <TableHead className="text-xs font-semibold text-center">Comisiones</TableHead>
              <TableHead className="text-xs font-semibold text-right">Base total</TableHead>
              <TableHead className="text-xs font-semibold text-right">Ganadas</TableHead>
              <TableHead className="text-xs font-semibold text-right">Pagadas</TableHead>
              <TableHead className="text-xs font-semibold text-right">Pendientes</TableHead>
              <TableHead className="text-xs font-semibold text-right"></TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {(data?.by_doctor || []).map(d => (
                <TableRow key={d.doctor_id} data-testid={`doctor-row-${d.doctor_id}`}>
                  <TableCell className="text-sm font-medium">{d.doctor_name}</TableCell>
                  <TableCell className="text-center text-sm">{d.count}</TableCell>
                  <TableCell className="text-right text-sm">Q{d.base_total.toFixed(2)}</TableCell>
                  <TableCell className="text-right text-sm font-medium">Q{d.earned_total.toFixed(2)}</TableCell>
                  <TableCell className="text-right text-sm text-emerald-700">Q{d.paid_total.toFixed(2)}</TableCell>
                  <TableCell className="text-right text-sm text-amber-700 font-bold">Q{d.pending_total.toFixed(2)}</TableCell>
                  <TableCell className="text-right">
                    <Button variant="outline" size="sm" className="h-7 text-xs" onClick={() => openDrill(d.doctor_id)} data-testid={`drill-${d.doctor_id}`}><Eye className="w-3 h-3 mr-1" />Detalle</Button>
                  </TableCell>
                </TableRow>
              ))}
              {(data?.by_doctor || []).length === 0 && <TableRow><TableCell colSpan={7} className="text-center py-8 text-slate-400">Sin comisiones en el período</TableCell></TableRow>}
            </TableBody>
          </Table>
        </Card>}

      <DoctorDrillDialog open={!!drilldown} onClose={() => setDrilldown(null)} doctorId={drilldown?.doctor_id} from={from} to={to} headers={headers} onPaid={load} />
    </>
  );
}

/* ============ DOCTOR DRILLDOWN ============ */
function DoctorDrillDialog({ open, onClose, doctorId, from, to, headers, onPaid }) {
  const [items, setItems] = useState([]);
  const [selected, setSelected] = useState(new Set());
  const [loading, setLoading] = useState(true);
  const [showPay, setShowPay] = useState(false);
  const [doctorName, setDoctorName] = useState('');

  const load = useCallback(async () => {
    if (!doctorId) return;
    setLoading(true);
    try {
      const params = new URLSearchParams({ doctor_id: doctorId, date_from: from, date_to: to, limit: '100' });
      const r = await axios.get(`${API}/clinic/commissions/earned?${params}`, { headers });
      setItems(r.data.commissions || []);
      if (r.data.commissions?.[0]) setDoctorName(r.data.commissions[0].doctor_name || '');
      setSelected(new Set());
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [doctorId, from, to, headers]);

  useEffect(() => { if (open) load(); }, [open, load]);

  const toggleAll = () => {
    const pendingIds = items.filter(i => i.status === 'earned').map(i => i.id);
    if (selected.size === pendingIds.length) setSelected(new Set());
    else setSelected(new Set(pendingIds));
  };
  const toggle = (id) => {
    const n = new Set(selected);
    if (n.has(id)) n.delete(id); else n.add(id);
    setSelected(n);
  };

  const totalSelected = items.filter(i => selected.has(i.id)).reduce((s, i) => s + (+i.commission_amount || 0), 0);
  const pendingCount = items.filter(i => i.status === 'earned').length;

  return (
    <>
      <Dialog open={open} onOpenChange={onClose}>
        <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto" data-testid="doctor-drill-dialog">
          <DialogHeader><DialogTitle>Comisiones de {doctorName || '...'}</DialogTitle></DialogHeader>
          <div className="flex justify-between items-center text-xs text-slate-500 pb-2">
            <span>Período: {from} a {to}</span>
            {pendingCount > 0 && (
              <Button size="sm" variant="outline" onClick={toggleAll}>{selected.size === pendingCount ? 'Deseleccionar' : 'Seleccionar todas las pendientes'}</Button>
            )}
          </div>
          {loading ? <div className="flex justify-center py-12"><div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" /></div> :
            <Table>
              <TableHeader><TableRow><TableHead className="w-8"></TableHead><TableHead className="text-xs">Fecha</TableHead><TableHead className="text-xs">Venta</TableHead><TableHead className="text-xs">Item</TableHead><TableHead className="text-xs text-right">Base</TableHead><TableHead className="text-xs text-right">Comisión</TableHead><TableHead className="text-xs text-center">Estado</TableHead></TableRow></TableHeader>
              <TableBody>
                {items.map(i => (
                  <TableRow key={i.id} data-testid={`comm-row-${i.id}`}>
                    <TableCell><input type="checkbox" disabled={i.status !== 'earned'} checked={selected.has(i.id)} onChange={() => toggle(i.id)} data-testid={`comm-cb-${i.id}`} /></TableCell>
                    <TableCell className="text-xs">{(i.earned_at || '').slice(0, 10)}</TableCell>
                    <TableCell className="text-xs font-mono">{i.sale_number || '—'}</TableCell>
                    <TableCell className="text-xs">{i.item_description || '—'}</TableCell>
                    <TableCell className="text-right text-xs">Q{(+i.base_amount || 0).toFixed(2)}</TableCell>
                    <TableCell className="text-right text-xs font-bold">Q{(+i.commission_amount || 0).toFixed(2)}</TableCell>
                    <TableCell className="text-center">
                      {i.status === 'paid' ? (
                        <div>
                          <Badge variant="outline" className="text-xs bg-emerald-50 text-emerald-700">Pagada</Badge>
                          {i.paid_at && <p className="text-[10px] text-slate-400 mt-0.5">{i.paid_at.slice(0, 10)} {i.payment_reference ? `· ${i.payment_reference}` : ''}</p>}
                        </div>
                      ) : <Badge variant="outline" className="text-xs bg-amber-50 text-amber-700">Pendiente</Badge>}
                    </TableCell>
                  </TableRow>
                ))}
                {items.length === 0 && <TableRow><TableCell colSpan={7} className="text-center py-8 text-slate-400">Sin comisiones</TableCell></TableRow>}
              </TableBody>
            </Table>}
          <DialogFooter>
            {selected.size > 0 && <Button className="bg-teal-600 hover:bg-teal-700" onClick={() => setShowPay(true)} data-testid="bulk-pay-btn">
              Marcar como pagadas ({selected.size}) — Q{totalSelected.toFixed(2)}
            </Button>}
            <Button variant="outline" onClick={onClose}>Cerrar</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <PayDialog open={showPay} onClose={() => setShowPay(false)} ids={Array.from(selected)} total={totalSelected} headers={headers} onDone={() => { setShowPay(false); load(); onPaid?.(); }} />
    </>
  );
}

function PayDialog({ open, onClose, ids, total, headers, onDone }) {
  const [reference, setReference] = useState('');
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);
  useEffect(() => { if (open) { setReference(''); setNotes(''); } }, [open]);
  const submit = async () => {
    setSaving(true);
    try {
      await axios.post(`${API}/clinic/commissions/pay`, { commission_ids: ids, payment_reference: reference, notes }, { headers });
      toast.success(`${ids.length} comisión(es) pagada(s)`);
      onDone();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error'); }
    finally { setSaving(false); }
  };
  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-sm" data-testid="bulk-pay-dialog">
        <DialogHeader><DialogTitle>Pagar comisiones</DialogTitle></DialogHeader>
        <div className="space-y-3 py-2">
          <div className="bg-teal-50 border border-teal-200 rounded p-3 text-center">
            <p className="text-xs text-teal-700">Pagar {ids.length} comisión(es)</p>
            <p className="text-2xl font-bold text-teal-600">Q{total.toFixed(2)}</p>
          </div>
          <div><Label className="text-xs">Referencia</Label><Input className="mt-1 text-sm" value={reference} onChange={e => setReference(e.target.value)} placeholder="No. transacción" data-testid="pay-reference-input" /></div>
          <div><Label className="text-xs">Notas</Label><Textarea className="mt-1 text-sm min-h-[40px]" value={notes} onChange={e => setNotes(e.target.value)} /></div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancelar</Button>
          <Button className="bg-teal-600 hover:bg-teal-700" onClick={submit} disabled={saving} data-testid="confirm-bulk-pay-btn">{saving ? '...' : 'Confirmar'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/* ============ SETTINGS TAB ============ */
function SettingsTab({ headers }) {
  const [rules, setRules] = useState([]);
  const [members, setMembers] = useState([]);
  const [services, setServices] = useState([]);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [edit, setEdit] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [r, m, s, p] = await Promise.all([
        axios.get(`${API}/clinic/commissions/settings`, { headers }),
        axios.get(`${API}/clinic/members`, { headers }).catch(() => ({ data: [] })),
        axios.get(`${API}/clinic/sales/services?active_only=true`, { headers }).catch(() => ({ data: [] })),
        axios.get(`${API}/clinic/inventory/products?limit=200`, { headers }).catch(() => ({ data: { products: [] } })),
      ]);
      setRules(r.data || []);
      setMembers(Array.isArray(m.data) ? m.data.filter(x => x.role === 'doctor') : []);
      setServices(s.data || []);
      setProducts(p.data.products || []);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [headers]);

  useEffect(() => { load(); }, [load]);

  const remove = async (id) => {
    if (!window.confirm('¿Eliminar esta regla?')) return;
    try { await axios.delete(`${API}/clinic/commissions/settings/${id}`, { headers }); toast.success('Regla eliminada'); load(); }
    catch (err) { toast.error(err.response?.data?.detail || 'Error'); }
  };
  const toggleActive = async (rule) => {
    try { await axios.put(`${API}/clinic/commissions/settings/${rule.id}`, { is_active: !rule.is_active }, { headers }); load(); }
    catch (err) { toast.error(err.response?.data?.detail || 'Error'); }
  };

  return (
    <>
      <div className="flex justify-end mb-4">
        <Button className="bg-teal-600 hover:bg-teal-700" onClick={() => { setEdit(null); setShowForm(true); }} data-testid="new-rule-btn"><Plus className="w-4 h-4 mr-1" />Nueva regla</Button>
      </div>

      {loading ? <div className="flex justify-center py-12"><div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" /></div> :
        <Card className="border overflow-hidden">
          <Table>
            <TableHeader><TableRow className="bg-slate-50/80">
              <TableHead className="text-xs font-semibold">Médico</TableHead>
              <TableHead className="text-xs font-semibold">Aplica a</TableHead>
              <TableHead className="text-xs font-semibold text-right">Valor</TableHead>
              <TableHead className="text-xs font-semibold">Vigencia</TableHead>
              <TableHead className="text-xs font-semibold text-center">Activa</TableHead>
              <TableHead className="text-xs font-semibold text-right"></TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {rules.map(r => (
                <TableRow key={r.id} data-testid={`rule-row-${r.id}`}>
                  <TableCell className="text-sm font-medium">{r.doctor_name}</TableCell>
                  <TableCell className="text-xs">
                    {APPLIES_TO_LABEL[r.applies_to]}
                    {r.service_name && <p className="text-[10px] text-slate-500">{r.service_name}</p>}
                    {r.product_name && <p className="text-[10px] text-slate-500">{r.product_name}</p>}
                  </TableCell>
                  <TableCell className="text-right text-sm font-bold">{r.calculation_type === 'percentage' ? `${r.percentage}%` : `Q${(+r.fixed_amount || 0).toFixed(2)}`}</TableCell>
                  <TableCell className="text-xs">{r.effective_from}{r.effective_to ? ` → ${r.effective_to}` : ''}</TableCell>
                  <TableCell className="text-center">
                    <Switch checked={r.is_active} onCheckedChange={() => toggleActive(r)} data-testid={`rule-active-${r.id}`} />
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => { setEdit(r); setShowForm(true); }}><Edit className="w-3.5 h-3.5" /></Button>
                      <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => remove(r.id)}><Trash2 className="w-3.5 h-3.5 text-red-500" /></Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {rules.length === 0 && <TableRow><TableCell colSpan={6} className="text-center py-8 text-slate-400">Sin reglas configuradas. Cree una para empezar a generar comisiones automáticamente.</TableCell></TableRow>}
            </TableBody>
          </Table>
        </Card>}

      <RuleFormDialog open={showForm} onClose={() => setShowForm(false)} edit={edit} members={members} services={services} products={products} headers={headers} onDone={() => { setShowForm(false); load(); }} />
    </>
  );
}

function RuleFormDialog({ open, onClose, edit, members, services, products, headers, onDone }) {
  const activeServices = (services || []).filter(s => s.is_active !== false);
  const activeProducts = (products || []).filter(p => (p.is_active !== false) && (p.sale_price !== null || p.total_stock > 0));
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    if (edit) setForm({ ...edit });
    else setForm({
      doctor_id: '', applies_to: 'all_consultations', calculation_type: 'percentage',
      percentage: 30, fixed_amount: 0, service_id: null, product_id: null,
      effective_from: new Date().toISOString().slice(0, 10), effective_to: '', is_active: true,
    });
  }, [open, edit]);

  const uf = (k, v) => setForm(p => ({ ...p, [k]: v }));

  const save = async () => {
    if (!form.doctor_id) { toast.error('Médico requerido'); return; }
    if (form.applies_to === 'service' && !form.service_id) { toast.error('Servicio requerido'); return; }
    if (form.applies_to === 'product' && !form.product_id) { toast.error('Producto requerido'); return; }
    setSaving(true);
    try {
      const payload = { ...form };
      if (!payload.effective_to) delete payload.effective_to;
      if (payload.applies_to !== 'service') payload.service_id = null;
      if (payload.applies_to !== 'product') payload.product_id = null;
      if (edit) await axios.put(`${API}/clinic/commissions/settings/${edit.id}`, payload, { headers });
      else await axios.post(`${API}/clinic/commissions/settings`, payload, { headers });
      toast.success(edit ? 'Regla actualizada' : 'Regla creada');
      onDone();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error'); }
    finally { setSaving(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-md max-h-[85vh] overflow-y-auto" data-testid="rule-form-dialog">
        <DialogHeader><DialogTitle>{edit ? 'Editar' : 'Nueva'} regla de comisión</DialogTitle></DialogHeader>
        <div className="space-y-3 py-2">
          <div>
            <Label className="text-xs">Médico *</Label>
            <Select value={form.doctor_id || ''} onValueChange={v => uf('doctor_id', v)} disabled={!!edit}>
              <SelectTrigger className="mt-1 text-sm" data-testid="rule-doctor-select"><SelectValue placeholder="Seleccionar médico" /></SelectTrigger>
              <SelectContent>{members.map(m => <SelectItem key={m.id} value={m.id}>Dr(a). {m.first_name} {m.last_name}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-xs">Aplica a</Label>
            <Select value={form.applies_to} onValueChange={v => uf('applies_to', v)}>
              <SelectTrigger className="mt-1 text-sm" data-testid="rule-applies-select"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all_consultations">Todas las consultas (servicios)</SelectItem>
                <SelectItem value="all_products">Todos los productos</SelectItem>
                <SelectItem value="service">Servicio específico</SelectItem>
                <SelectItem value="product">Producto específico</SelectItem>
              </SelectContent>
            </Select>
          </div>
          {form.applies_to === 'service' && (
            <div>
              <Label className="text-xs">Servicio *</Label>
              <Select value={form.service_id || ''} onValueChange={v => uf('service_id', v)}>
                <SelectTrigger className="mt-1 text-sm" data-testid="rule-service-select"><SelectValue placeholder={activeServices.length === 0 ? 'Sin servicios disponibles' : 'Seleccionar'} /></SelectTrigger>
                <SelectContent>{activeServices.map(s => <SelectItem key={s.id} value={s.id}>{s.name} (Q{(s.price || 0).toFixed(2)})</SelectItem>)}</SelectContent>
              </Select>
              <p className="text-[11px] text-slate-500 mt-1">
                ¿No aparece el servicio? Créalo en <a href="/dashboard/ventas" target="_blank" rel="noopener noreferrer" className="text-teal-600 hover:underline font-medium">Ventas → Servicios</a>
              </p>
            </div>
          )}
          {form.applies_to === 'product' && (
            <div>
              <Label className="text-xs">Producto *</Label>
              <Select value={form.product_id || ''} onValueChange={v => uf('product_id', v)}>
                <SelectTrigger className="mt-1 text-sm" data-testid="rule-product-select"><SelectValue placeholder={activeProducts.length === 0 ? 'Sin productos disponibles' : 'Seleccionar'} /></SelectTrigger>
                <SelectContent>{activeProducts.map(p => <SelectItem key={p.id} value={p.id}>{p.name}{p.sale_price ? ` (Q${(p.sale_price || 0).toFixed(2)})` : ''}</SelectItem>)}</SelectContent>
              </Select>
              <p className="text-[11px] text-slate-500 mt-1">
                ¿No aparece el producto? Créalo en <a href="/dashboard/inventario" target="_blank" rel="noopener noreferrer" className="text-teal-600 hover:underline font-medium">Inventario → Productos</a>
              </p>
            </div>
          )}
          {(form.applies_to === 'all_consultations' || form.applies_to === 'all_products') && (
            <div className="p-2.5 bg-slate-50 border border-slate-200 rounded text-xs text-slate-600">
              {form.applies_to === 'all_consultations' ? (
                <>La comisión se aplicará a <strong>todos los servicios/consultas</strong> que venda este médico. Para gestionar el catálogo visita <a href="/dashboard/ventas" target="_blank" rel="noopener noreferrer" className="text-teal-600 hover:underline font-medium">Ventas → Servicios</a>.</>
              ) : (
                <>La comisión se aplicará a <strong>todos los productos</strong> que venda este médico. Para gestionar el catálogo visita <a href="/dashboard/inventario" target="_blank" rel="noopener noreferrer" className="text-teal-600 hover:underline font-medium">Inventario → Productos</a>.</>
              )}
            </div>
          )}
          <Separator />
          <div>
            <Label className="text-xs">Tipo de cálculo</Label>
            <Select value={form.calculation_type} onValueChange={v => uf('calculation_type', v)}>
              <SelectTrigger className="mt-1 text-sm" data-testid="rule-calc-select"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="percentage">Porcentaje (%)</SelectItem>
                <SelectItem value="fixed">Monto fijo (Q por unidad)</SelectItem>
              </SelectContent>
            </Select>
          </div>
          {form.calculation_type === 'percentage' ? (
            <div><Label className="text-xs">Porcentaje (%)</Label><Input type="number" step="0.01" min={0} max={100} className="mt-1" value={form.percentage ?? ''} onChange={e => uf('percentage', parseFloat(e.target.value) || 0)} data-testid="rule-percentage-input" /></div>
          ) : (
            <div><Label className="text-xs">Monto fijo (Q)</Label><Input type="number" step="0.01" min={0} className="mt-1" value={form.fixed_amount ?? ''} onChange={e => uf('fixed_amount', parseFloat(e.target.value) || 0)} data-testid="rule-fixed-input" /></div>
          )}
          <div className="grid grid-cols-2 gap-3">
            <div><Label className="text-xs">Inicio</Label><Input type="date" className="mt-1" value={form.effective_from || ''} onChange={e => uf('effective_from', e.target.value)} /></div>
            <div><Label className="text-xs">Fin (opcional)</Label><Input type="date" className="mt-1" value={form.effective_to || ''} onChange={e => uf('effective_to', e.target.value)} /></div>
          </div>
          <label className="flex items-center gap-2 text-sm pt-1"><Switch checked={form.is_active} onCheckedChange={v => uf('is_active', v)} />Activa</label>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancelar</Button>
          <Button className="bg-teal-600 hover:bg-teal-700" onClick={save} disabled={saving} data-testid="save-rule-btn">{saving ? '...' : 'Guardar'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
