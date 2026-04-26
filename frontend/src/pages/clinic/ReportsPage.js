import { useState, useEffect, useCallback, useMemo } from 'react';
import { useAuth } from '../../context/AuthContext';
import { useBranch } from '../../context/BranchContext';
import { useFeatures } from '../../context/FeatureContext';
import FeatureGate from '../../components/FeatureGate';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Badge } from '../../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { Separator } from '../../components/ui/separator';
import { toast } from 'sonner';
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts';
import {
  TrendingUp, TrendingDown, DollarSign, Wallet, Users, CalendarCheck,
  Receipt, ShoppingCart, Building2, FileDown, Layers, AlertCircle, Package
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const COLORS = ['#0D9488', '#0EA5E9', '#F59E0B', '#EF4444', '#8B5CF6', '#10B981', '#F97316', '#EC4899', '#64748B', '#3B82F6'];
const PAY_LABEL = { cash: 'Efectivo', credit_card: 'Tarjeta crédito', debit_card: 'Tarjeta débito', transfer: 'Transferencia', credit: 'Crédito', check: 'Cheque', other: 'Otro' };

export default function ReportsPage() {
  const { getAuthHeaders } = useAuth();
  const { branches } = useBranch();
  const { hasFeature } = useFeatures();
  const headers = getAuthHeaders();
  const [tab, setTab] = useState('summary');

  return (
    <FeatureGate feature="financial_reports" planRequired="Professional">
      <div className="p-6 lg:p-8" data-testid="reports-page">
        <h1 className="text-2xl font-bold text-slate-900 mb-1">Reportes financieros</h1>
        <p className="text-sm text-slate-500 mb-4">Análisis ejecutivo y operacional de la clínica</p>
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="bg-slate-100 mb-4 flex-wrap h-auto">
            <TabsTrigger value="summary" data-testid="rep-tab-summary"><TrendingUp className="w-3.5 h-3.5 mr-1" />Resumen ejecutivo</TabsTrigger>
            <TabsTrigger value="income" data-testid="rep-tab-income"><DollarSign className="w-3.5 h-3.5 mr-1" />Ingresos</TabsTrigger>
            <TabsTrigger value="pnl" data-testid="rep-tab-pnl"><Receipt className="w-3.5 h-3.5 mr-1" />Estado de resultados</TabsTrigger>
            <TabsTrigger value="inventory" data-testid="rep-tab-inventory"><Package className="w-3.5 h-3.5 mr-1" />Inventario</TabsTrigger>
            {hasFeature('multi_branch') && <TabsTrigger value="branch" data-testid="rep-tab-branch"><Building2 className="w-3.5 h-3.5 mr-1" />Por sucursal</TabsTrigger>}
          </TabsList>
          <TabsContent value="summary"><SummaryTab headers={headers} branches={branches} /></TabsContent>
          <TabsContent value="income"><IncomeTab headers={headers} branches={branches} /></TabsContent>
          <TabsContent value="pnl"><PnLTab headers={headers} branches={branches} /></TabsContent>
          <TabsContent value="inventory"><InventoryTab headers={headers} branches={branches} /></TabsContent>
          {hasFeature('multi_branch') && <TabsContent value="branch"><BranchTab headers={headers} /></TabsContent>}
        </Tabs>
      </div>
    </FeatureGate>
  );
}

/* ============ PERIOD PICKER ============ */
function PeriodPicker({ period, setPeriod, dateFrom, setDateFrom, dateTo, setDateTo, branchId, setBranchId, branches }) {
  return (
    <div className="flex flex-wrap gap-3 items-end mb-4">
      <div>
        <Label className="text-xs">Período</Label>
        <Select value={period} onValueChange={setPeriod}>
          <SelectTrigger className="w-44 mt-1" data-testid="period-select"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="current_month">Mes actual</SelectItem>
            <SelectItem value="previous_month">Mes anterior</SelectItem>
            <SelectItem value="quarter">Trimestre</SelectItem>
            <SelectItem value="year">Año</SelectItem>
            <SelectItem value="custom">Personalizado</SelectItem>
          </SelectContent>
        </Select>
      </div>
      {period === 'custom' && (
        <>
          <div><Label className="text-xs">Desde</Label><Input type="date" className="mt-1 w-40" value={dateFrom} onChange={e => setDateFrom(e.target.value)} data-testid="period-from" /></div>
          <div><Label className="text-xs">Hasta</Label><Input type="date" className="mt-1 w-40" value={dateTo} onChange={e => setDateTo(e.target.value)} data-testid="period-to" /></div>
        </>
      )}
      {branches && setBranchId && (
        <div>
          <Label className="text-xs">Sucursal</Label>
          <Select value={branchId} onValueChange={setBranchId}>
            <SelectTrigger className="w-44 mt-1"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todas</SelectItem>
              {(branches || []).map(b => <SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      )}
    </div>
  );
}

function buildParams({ period, dateFrom, dateTo, branchId, ...rest }) {
  const p = new URLSearchParams({ period });
  if (period === 'custom') { if (dateFrom) p.set('date_from', dateFrom); if (dateTo) p.set('date_to', dateTo); }
  if (branchId && branchId !== 'all') p.set('branch_id', branchId);
  Object.entries(rest).forEach(([k, v]) => { if (v != null && v !== '' && v !== 'all') p.set(k, v); });
  return p;
}

/* ============ SUMMARY TAB ============ */
function SummaryTab({ headers, branches }) {
  const [period, setPeriod] = useState('current_month');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [branchId, setBranchId] = useState('all');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = buildParams({ period, dateFrom, dateTo, branchId });
      const r = await axios.get(`${API}/clinic/reports/executive-summary?${params}`, { headers });
      setData(r.data);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [period, dateFrom, dateTo, branchId, headers]);

  useEffect(() => { load(); }, [load]);

  const k = data?.kpis;
  const trend = data?.trend_12m || [];
  const byMethod = (data?.income_by_method || []).map(x => ({ name: PAY_LABEL[x.method] || x.method, value: x.amount }));
  const byCategory = data?.expenses_by_category || [];
  const byBranch = data?.income_by_branch || [];

  return (
    <>
      <PeriodPicker period={period} setPeriod={setPeriod} dateFrom={dateFrom} setDateFrom={setDateFrom} dateTo={dateTo} setDateTo={setDateTo} branchId={branchId} setBranchId={setBranchId} branches={branches} />
      {loading ? <Spinner /> : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            <KpiCard label="Ingresos" value={k?.income?.value} delta={k?.income?.delta_pct} icon={DollarSign} color="teal" prefix="Q" />
            <KpiCard label="Gastos" value={k?.expenses?.value} delta={k?.expenses?.delta_pct} deltaInverted icon={Wallet} color="red" prefix="Q" />
            <KpiCard label="Utilidad neta" value={k?.net_profit?.value} extra={`${k?.net_profit?.margin_pct ?? 0}% margen`} icon={TrendingUp} color="emerald" prefix="Q" />
            <KpiCard label="CxC pendiente" value={k?.ar_pending} icon={Receipt} color="amber" prefix="Q" />
            <KpiCard label="Ticket promedio" value={k?.avg_ticket} icon={ShoppingCart} color="blue" prefix="Q" />
            <KpiCard label="Pacientes nuevos" value={k?.new_patients} icon={Users} color="purple" />
            <KpiCard label="Citas" value={k?.appointments} icon={CalendarCheck} color="slate" />
            <KpiCard label="# Ventas" value={k?.sales_count} icon={ShoppingCart} color="slate" />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
            <Card><CardHeader className="pb-2"><CardTitle className="text-sm font-semibold">Ingresos vs Gastos (12 meses)</CardTitle></CardHeader>
              <CardContent style={{ height: 280 }}>
                <ResponsiveContainer>
                  <LineChart data={trend} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                    <XAxis dataKey="month" fontSize={10} />
                    <YAxis fontSize={10} />
                    <Tooltip formatter={v => `Q${v.toFixed(2)}`} />
                    <Legend />
                    <Line type="monotone" dataKey="income" name="Ingresos" stroke="#0D9488" strokeWidth={2} />
                    <Line type="monotone" dataKey="expenses" name="Gastos" stroke="#EF4444" strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
            <Card><CardHeader className="pb-2"><CardTitle className="text-sm font-semibold">Ingresos por método de pago</CardTitle></CardHeader>
              <CardContent style={{ height: 280 }}>
                <ResponsiveContainer>
                  <BarChart data={byMethod}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                    <XAxis dataKey="name" fontSize={10} />
                    <YAxis fontSize={10} />
                    <Tooltip formatter={v => `Q${v.toFixed(2)}`} />
                    <Bar dataKey="value" fill="#0EA5E9" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card><CardHeader className="pb-2"><CardTitle className="text-sm font-semibold">Distribución de gastos</CardTitle></CardHeader>
              <CardContent style={{ height: 280 }}>
                {byCategory.length === 0 ? <EmptyChart /> : (
                  <ResponsiveContainer>
                    <PieChart>
                      <Pie data={byCategory} dataKey="amount" nameKey="label" outerRadius={90} label={(e) => `${e.label}`}>
                        {byCategory.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                      </Pie>
                      <Tooltip formatter={v => `Q${v.toFixed(2)}`} />
                    </PieChart>
                  </ResponsiveContainer>
                )}
              </CardContent>
            </Card>
            <Card><CardHeader className="pb-2"><CardTitle className="text-sm font-semibold">Ingresos por sucursal</CardTitle></CardHeader>
              <CardContent style={{ height: 280 }}>
                {byBranch.length === 0 ? <EmptyChart /> : (
                  <ResponsiveContainer>
                    <BarChart data={byBranch} layout="vertical">
                      <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                      <XAxis type="number" fontSize={10} />
                      <YAxis dataKey="branch_name" type="category" fontSize={10} width={120} />
                      <Tooltip formatter={v => `Q${v.toFixed(2)}`} />
                      <Bar dataKey="amount" fill="#0D9488" radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </>
  );
}

function KpiCard({ label, value, delta, deltaInverted, extra, icon: Icon, color = 'slate', prefix = '' }) {
  const colorMap = { teal: 'text-teal-600', red: 'text-red-600', emerald: 'text-emerald-600', amber: 'text-amber-600', blue: 'text-blue-600', purple: 'text-purple-600', slate: 'text-slate-700' };
  const display = typeof value === 'number'
    ? (prefix ? `${prefix}${value.toFixed(2)}` : `${Math.round(value)}`)
    : (value ?? '—');
  const deltaPositive = delta != null && delta >= 0;
  const deltaGood = deltaInverted ? !deltaPositive : deltaPositive;
  return (
    <Card><CardContent className="p-4">
      <div className="flex items-center justify-between">
        <p className="text-xs text-slate-500 font-medium truncate">{label}</p>
        {Icon && <Icon className={`w-4 h-4 ${colorMap[color]}`} />}
      </div>
      <p className={`text-xl font-bold mt-1 ${colorMap[color]}`}>{display}</p>
      {delta != null && <p className={`text-[10px] mt-0.5 flex items-center gap-1 ${deltaGood ? 'text-emerald-600' : 'text-red-600'}`}>
        {deltaPositive ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}{Math.abs(delta).toFixed(1)}%
      </p>}
      {extra && <p className="text-[10px] text-slate-500 mt-0.5">{extra}</p>}
    </CardContent></Card>
  );
}
function EmptyChart() { return <div className="flex items-center justify-center h-full text-xs text-slate-400">Sin datos</div>; }
function Spinner() { return <div className="flex justify-center py-16"><div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" /></div>; }

/* ============ INCOME TAB ============ */
function IncomeTab({ headers, branches }) {
  const [period, setPeriod] = useState('current_month');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [branchId, setBranchId] = useState('all');
  const [grouping, setGrouping] = useState('day');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = buildParams({ period, dateFrom, dateTo, branchId, grouping });
      const r = await axios.get(`${API}/clinic/reports/income?${params}`, { headers });
      setData(r.data);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [period, dateFrom, dateTo, branchId, grouping, headers]);

  useEffect(() => { load(); }, [load]);

  const exportCsv = () => {
    if (!data?.time_series) return;
    const rows = [['Fecha', 'Ingresos']];
    data.time_series.forEach(t => rows.push([t.date, t.amount.toFixed(2)]));
    const csv = rows.map(r => r.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `ingresos_${data.period.from}_${data.period.to}.csv`; a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <>
      <div className="flex items-end justify-between flex-wrap gap-3">
        <PeriodPicker period={period} setPeriod={setPeriod} dateFrom={dateFrom} setDateFrom={setDateFrom} dateTo={dateTo} setDateTo={setDateTo} branchId={branchId} setBranchId={setBranchId} branches={branches} />
        <div className="flex gap-2 items-end">
          <div><Label className="text-xs">Agrupar</Label>
            <Select value={grouping} onValueChange={setGrouping}>
              <SelectTrigger className="w-32 mt-1" data-testid="grouping-select"><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value="day">Día</SelectItem><SelectItem value="week">Semana</SelectItem><SelectItem value="month">Mes</SelectItem></SelectContent>
            </Select>
          </div>
          <Button variant="outline" onClick={exportCsv} data-testid="export-csv-btn"><FileDown className="w-4 h-4 mr-1" />CSV</Button>
        </div>
      </div>
      {loading ? <Spinner /> : (
        <>
          <Card className="mb-4"><CardContent className="p-4 flex items-center justify-between">
            <div><p className="text-xs text-slate-500">Total ingresos</p><p className="text-3xl font-bold text-teal-600">Q{(data?.total_income || 0).toFixed(2)}</p></div>
            <div className="text-right"><p className="text-xs text-slate-500">Ventas</p><p className="text-2xl font-bold">{data?.sales_count || 0}</p></div>
          </CardContent></Card>

          <Card className="mb-4"><CardHeader className="pb-2"><CardTitle className="text-sm font-semibold">Tendencia de ingresos</CardTitle></CardHeader>
            <CardContent style={{ height: 280 }}>
              {(data?.time_series || []).length === 0 ? <EmptyChart /> : (
                <ResponsiveContainer><LineChart data={data.time_series}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                  <XAxis dataKey="date" fontSize={10} />
                  <YAxis fontSize={10} />
                  <Tooltip formatter={v => `Q${v.toFixed(2)}`} />
                  <Line type="monotone" dataKey="amount" stroke="#0D9488" strokeWidth={2} dot={false} />
                </LineChart></ResponsiveContainer>
              )}
            </CardContent>
          </Card>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
            <Card><CardHeader className="pb-2"><CardTitle className="text-sm font-semibold">Top servicios</CardTitle></CardHeader>
              <CardContent>
                <Table><TableBody>
                  {(data?.top_services || []).map(s => (
                    <TableRow key={s.id}><TableCell className="text-sm font-medium">{s.name}</TableCell><TableCell className="text-xs text-slate-500 text-center">{s.quantity}</TableCell><TableCell className="text-sm font-bold text-right">Q{s.amount.toFixed(2)}</TableCell></TableRow>
                  ))}
                  {(data?.top_services || []).length === 0 && <TableRow><TableCell className="text-center py-4 text-slate-400">Sin datos</TableCell></TableRow>}
                </TableBody></Table>
              </CardContent>
            </Card>
            <Card><CardHeader className="pb-2"><CardTitle className="text-sm font-semibold">Top productos</CardTitle></CardHeader>
              <CardContent>
                <Table><TableBody>
                  {(data?.top_products || []).map(s => (
                    <TableRow key={s.id}><TableCell className="text-sm font-medium">{s.name}</TableCell><TableCell className="text-xs text-slate-500 text-center">{s.quantity}</TableCell><TableCell className="text-sm font-bold text-right">Q{s.amount.toFixed(2)}</TableCell></TableRow>
                  ))}
                  {(data?.top_products || []).length === 0 && <TableRow><TableCell className="text-center py-4 text-slate-400">Sin datos</TableCell></TableRow>}
                </TableBody></Table>
              </CardContent>
            </Card>
            <Card><CardHeader className="pb-2"><CardTitle className="text-sm font-semibold">Ingresos por médico</CardTitle></CardHeader>
              <CardContent>
                <Table><TableBody>
                  {(data?.by_doctor || []).map(s => (
                    <TableRow key={s.doctor_id}><TableCell className="text-sm">{s.name}</TableCell><TableCell className="text-sm font-bold text-right">Q{s.amount.toFixed(2)}</TableCell></TableRow>
                  ))}
                  {(data?.by_doctor || []).length === 0 && <TableRow><TableCell className="text-center py-4 text-slate-400">Sin datos</TableCell></TableRow>}
                </TableBody></Table>
              </CardContent>
            </Card>
            <Card><CardHeader className="pb-2"><CardTitle className="text-sm font-semibold">Por método de pago</CardTitle></CardHeader>
              <CardContent style={{ height: 220 }}>
                <ResponsiveContainer><BarChart data={(data?.by_method || []).map(x => ({ name: PAY_LABEL[x.method] || x.method, value: x.amount }))}>
                  <XAxis dataKey="name" fontSize={10} /><YAxis fontSize={10} />
                  <Tooltip formatter={v => `Q${v.toFixed(2)}`} />
                  <Bar dataKey="value" fill="#0EA5E9" radius={[4, 4, 0, 0]} />
                </BarChart></ResponsiveContainer>
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </>
  );
}

/* ============ P&L TAB ============ */
function PnLTab({ headers, branches }) {
  const [period, setPeriod] = useState('current_month');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [branchId, setBranchId] = useState('all');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [pdfLoading, setPdfLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = buildParams({ period, dateFrom, dateTo, branchId });
      const r = await axios.get(`${API}/clinic/reports/pnl?${params}`, { headers });
      setData(r.data);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [period, dateFrom, dateTo, branchId, headers]);

  useEffect(() => { load(); }, [load]);

  const exportPdf = async () => {
    setPdfLoading(true);
    try {
      const params = buildParams({ period, dateFrom, dateTo, branchId });
      const r = await axios.get(`${API}/clinic/reports/pnl-pdf?${params}`, { headers });
      if (r.data.url) window.open(r.data.url, '_blank');
      else toast.error('No se pudo generar');
    } catch (err) { toast.error(err.response?.data?.detail || 'Error'); }
    finally { setPdfLoading(false); }
  };

  const cur = data?.current; const prev = data?.previous;
  const Row = ({ label, cur, prev, total, indent }) => {
    const diff = cur != null && prev != null ? cur - prev : null;
    return (
      <TableRow className={total ? 'bg-slate-50 font-bold' : ''}>
        <TableCell className={`text-sm ${indent ? 'pl-6 text-slate-600' : ''} ${total ? 'font-bold' : ''}`}>{label}</TableCell>
        <TableCell className="text-right text-sm">{cur != null ? `Q${(+cur).toFixed(2)}` : '—'}</TableCell>
        <TableCell className="text-right text-sm text-slate-500">{prev != null ? `Q${(+prev).toFixed(2)}` : '—'}</TableCell>
        <TableCell className={`text-right text-xs ${diff > 0 ? 'text-emerald-600' : diff < 0 ? 'text-red-600' : 'text-slate-400'}`}>{diff != null && prev != null && prev !== 0 ? `${(diff / prev * 100).toFixed(1)}%` : '—'}</TableCell>
      </TableRow>
    );
  };

  return (
    <>
      <div className="flex items-end justify-between flex-wrap gap-3">
        <PeriodPicker period={period} setPeriod={setPeriod} dateFrom={dateFrom} setDateFrom={setDateFrom} dateTo={dateTo} setDateTo={setDateTo} branchId={branchId} setBranchId={setBranchId} branches={branches} />
        <Button variant="outline" onClick={exportPdf} disabled={pdfLoading} data-testid="pnl-pdf-btn"><FileDown className="w-4 h-4 mr-1" />{pdfLoading ? '...' : 'Exportar PDF'}</Button>
      </div>
      {loading ? <Spinner /> : !cur ? <EmptyChart /> : (
        <Card className="border overflow-hidden">
          <Table>
            <TableHeader><TableRow className="bg-slate-100">
              <TableHead className="text-xs font-semibold">Concepto</TableHead>
              <TableHead className="text-xs font-semibold text-right">Actual ({data.period.from} → {data.period.to})</TableHead>
              <TableHead className="text-xs font-semibold text-right text-slate-500">Anterior</TableHead>
              <TableHead className="text-xs font-semibold text-right">Δ %</TableHead>
            </TableRow></TableHeader>
            <TableBody>
              <Row label="INGRESOS" cur={null} prev={null} />
              <Row label="Servicios médicos" cur={cur.income.services} prev={prev.income.services} indent />
              <Row label="Productos" cur={cur.income.products} prev={prev.income.products} indent />
              <Row label="Otros ingresos" cur={cur.income.other} prev={prev.income.other} indent />
              <Row label="TOTAL INGRESOS" cur={cur.income.total} prev={prev.income.total} total />
              <Row label="Costo de productos vendidos" cur={-cur.cogs} prev={-prev.cogs} indent />
              <Row label="MARGEN BRUTO" cur={cur.gross_margin} prev={prev.gross_margin} total />
              <Row label="GASTOS OPERATIVOS" cur={null} prev={null} />
              {(cur.expenses.by_category || []).map(c => {
                const prevC = (prev.expenses.by_category || []).find(x => x.key === c.key);
                return <Row key={c.key} label={c.label} cur={-c.amount} prev={-(prevC?.amount || 0)} indent />;
              })}
              <Row label="TOTAL GASTOS" cur={-cur.expenses.total} prev={-prev.expenses.total} total />
              <Row label="UTILIDAD ANTES DE COMISIONES" cur={cur.ebit_before_commissions} prev={prev.ebit_before_commissions} total />
              <Row label="Comisiones médicos" cur={-cur.commissions} prev={-prev.commissions} indent />
              <TableRow className="bg-teal-50 font-bold border-t-2 border-teal-500">
                <TableCell className="text-base font-bold text-teal-700">UTILIDAD NETA</TableCell>
                <TableCell className="text-right text-lg font-bold text-teal-700">Q{(+cur.net_profit).toFixed(2)}</TableCell>
                <TableCell className="text-right text-base text-slate-600">Q{(+prev.net_profit).toFixed(2)}</TableCell>
                <TableCell className="text-right text-xs text-slate-500"></TableCell>
              </TableRow>
              <TableRow>
                <TableCell className="text-sm font-bold pl-6">Margen neto</TableCell>
                <TableCell className="text-right text-sm font-bold">{cur.net_margin_pct}%</TableCell>
                <TableCell className="text-right text-sm text-slate-500">{prev.net_margin_pct}%</TableCell>
                <TableCell></TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </Card>
      )}
    </>
  );
}

/* ============ INVENTORY TAB ============ */
function InventoryTab({ headers, branches }) {
  const [branchId, setBranchId] = useState('all');
  const [days, setDays] = useState(60);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ days_no_movement: String(days) });
      if (branchId !== 'all') params.set('branch_id', branchId);
      const r = await axios.get(`${API}/clinic/reports/inventory?${params}`, { headers });
      setData(r.data);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [branchId, days, headers]);

  useEffect(() => { load(); }, [load]);

  const v = data?.valuation;
  return (
    <>
      <div className="flex flex-wrap gap-3 items-end mb-4">
        <div>
          <Label className="text-xs">Sucursal</Label>
          <Select value={branchId} onValueChange={setBranchId}>
            <SelectTrigger className="w-44 mt-1"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="all">Todas</SelectItem>{(branches || []).map(b => <SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div>
          <Label className="text-xs">Sin movimiento</Label>
          <Select value={String(days)} onValueChange={x => setDays(parseInt(x))}>
            <SelectTrigger className="w-36 mt-1"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value="30">30 días</SelectItem><SelectItem value="60">60 días</SelectItem><SelectItem value="90">90 días</SelectItem></SelectContent>
          </Select>
        </div>
      </div>
      {loading ? <Spinner /> : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
            <KpiCard label="Valor a costo" value={v?.cost_total} icon={DollarSign} color="teal" prefix="Q" />
            <KpiCard label="Valor a precio venta" value={v?.retail_total} icon={DollarSign} color="emerald" prefix="Q" />
            <KpiCard label="Margen potencial" value={v?.potential_margin} icon={TrendingUp} color="blue" prefix="Q" />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
            <Card><CardHeader className="pb-2"><CardTitle className="text-sm font-semibold">Por sucursal</CardTitle></CardHeader>
              <CardContent>
                <Table><TableHeader><TableRow><TableHead className="text-xs">Sucursal</TableHead><TableHead className="text-xs text-right">Costo</TableHead><TableHead className="text-xs text-right">Venta</TableHead></TableRow></TableHeader>
                  <TableBody>{(v?.by_branch || []).map(b => (<TableRow key={b.branch_id}><TableCell className="text-sm">{b.branch_name}</TableCell><TableCell className="text-right text-sm">Q{b.cost.toFixed(2)}</TableCell><TableCell className="text-right text-sm font-medium">Q{b.retail.toFixed(2)}</TableCell></TableRow>))}
                  {(v?.by_branch || []).length === 0 && <TableRow><TableCell colSpan={3} className="text-center py-4 text-slate-400">Sin datos</TableCell></TableRow>}</TableBody>
                </Table>
              </CardContent>
            </Card>
            <Card><CardHeader className="pb-2"><CardTitle className="text-sm font-semibold">Por categoría</CardTitle></CardHeader>
              <CardContent>
                <Table><TableHeader><TableRow><TableHead className="text-xs">Categoría</TableHead><TableHead className="text-xs text-center">Items</TableHead><TableHead className="text-xs text-right">Costo</TableHead></TableRow></TableHeader>
                  <TableBody>{(v?.by_category || []).map((c, i) => (<TableRow key={i}><TableCell className="text-sm">{c.category}</TableCell><TableCell className="text-center text-xs">{c.items}</TableCell><TableCell className="text-right text-sm">Q{c.cost.toFixed(2)}</TableCell></TableRow>))}
                  {(v?.by_category || []).length === 0 && <TableRow><TableCell colSpan={3} className="text-center py-4 text-slate-400">Sin datos</TableCell></TableRow>}</TableBody>
                </Table>
              </CardContent>
            </Card>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
            <Card><CardHeader className="pb-2"><CardTitle className="text-sm font-semibold">Sin movimiento ({days} días)</CardTitle></CardHeader>
              <CardContent>
                <Table><TableHeader><TableRow><TableHead className="text-xs">Producto</TableHead><TableHead className="text-xs text-center">Stock</TableHead><TableHead className="text-xs text-right">Valor</TableHead></TableRow></TableHeader>
                  <TableBody>{(data?.no_movement_products || []).slice(0, 15).map(p => (<TableRow key={p.id}><TableCell className="text-sm">{p.name}<p className="text-[10px] text-slate-400">{p.sku}</p></TableCell><TableCell className="text-center text-xs">{p.quantity}</TableCell><TableCell className="text-right text-sm">Q{p.value_cost.toFixed(2)}</TableCell></TableRow>))}
                  {(data?.no_movement_products || []).length === 0 && <TableRow><TableCell colSpan={3} className="text-center py-4 text-slate-400">Sin productos sin movimiento</TableCell></TableRow>}</TableBody>
                </Table>
              </CardContent>
            </Card>
            <Card><CardHeader className="pb-2"><CardTitle className="text-sm font-semibold">Top vendidos (90 días)</CardTitle></CardHeader>
              <CardContent>
                <Table><TableHeader><TableRow><TableHead className="text-xs">Producto</TableHead><TableHead className="text-xs text-center">Cant.</TableHead><TableHead className="text-xs text-right">Total</TableHead></TableRow></TableHeader>
                  <TableBody>{(data?.top_sold_90d || []).slice(0, 15).map(p => (<TableRow key={p.id}><TableCell className="text-sm">{p.name}</TableCell><TableCell className="text-center text-xs">{p.quantity}</TableCell><TableCell className="text-right text-sm font-bold">Q{p.amount.toFixed(2)}</TableCell></TableRow>))}
                  {(data?.top_sold_90d || []).length === 0 && <TableRow><TableCell colSpan={3} className="text-center py-4 text-slate-400">Sin ventas</TableCell></TableRow>}</TableBody>
                </Table>
              </CardContent>
            </Card>
          </div>

          {(data?.expiring || []).length > 0 && (
            <Card className="mb-4 border-amber-200">
              <CardHeader className="pb-2"><CardTitle className="text-sm font-semibold flex items-center gap-1 text-amber-700"><AlertCircle className="w-4 h-4" />Próximos a vencer</CardTitle></CardHeader>
              <CardContent>
                <Table><TableHeader><TableRow><TableHead className="text-xs">Producto</TableHead><TableHead className="text-xs">Lote</TableHead><TableHead className="text-xs">Vence</TableHead><TableHead className="text-xs text-center">Stock</TableHead></TableRow></TableHeader>
                  <TableBody>{data.expiring.map((e, i) => (<TableRow key={i}><TableCell className="text-sm">{e.product_name}</TableCell><TableCell className="text-xs font-mono">{e.batch_number || '—'}</TableCell><TableCell className="text-xs">{e.expiration_date}</TableCell><TableCell className="text-center text-xs">{e.quantity}</TableCell></TableRow>))}</TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </>
  );
}

/* ============ BRANCH COMPARATIVE ============ */
function BranchTab({ headers }) {
  const [period, setPeriod] = useState('current_month');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = buildParams({ period, dateFrom, dateTo });
      const r = await axios.get(`${API}/clinic/reports/by-branch?${params}`, { headers });
      setData(r.data);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [period, dateFrom, dateTo, headers]);

  useEffect(() => { load(); }, [load]);

  return (
    <>
      <PeriodPicker period={period} setPeriod={setPeriod} dateFrom={dateFrom} setDateFrom={setDateFrom} dateTo={dateTo} setDateTo={setDateTo} />
      {loading ? <Spinner /> : (
        <>
          <Card className="mb-4 border overflow-hidden">
            <Table>
              <TableHeader><TableRow className="bg-slate-50/80">
                <TableHead className="text-xs font-semibold">Sucursal</TableHead>
                <TableHead className="text-xs font-semibold text-right">Ingresos</TableHead>
                <TableHead className="text-xs font-semibold text-right">Gastos</TableHead>
                <TableHead className="text-xs font-semibold text-right">Utilidad</TableHead>
                <TableHead className="text-xs font-semibold text-center"># Ventas</TableHead>
                <TableHead className="text-xs font-semibold text-center"># Citas</TableHead>
                <TableHead className="text-xs font-semibold text-right">Ticket prom.</TableHead>
              </TableRow></TableHeader>
              <TableBody>
                {(data?.branches || []).map(b => (
                  <TableRow key={b.branch_id} data-testid={`branch-row-${b.branch_id}`}>
                    <TableCell className="text-sm font-medium">{b.branch_name}</TableCell>
                    <TableCell className="text-right text-sm">Q{b.income.toFixed(2)}</TableCell>
                    <TableCell className="text-right text-sm text-red-600">Q{b.expenses.toFixed(2)}</TableCell>
                    <TableCell className={`text-right text-sm font-bold ${b.profit >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>Q{b.profit.toFixed(2)}</TableCell>
                    <TableCell className="text-center text-sm">{b.sales_count}</TableCell>
                    <TableCell className="text-center text-sm">{b.appointments}</TableCell>
                    <TableCell className="text-right text-sm">Q{b.avg_ticket.toFixed(2)}</TableCell>
                  </TableRow>
                ))}
                {(data?.branches || []).length === 0 && <TableRow><TableCell colSpan={7} className="text-center py-8 text-slate-400">Sin datos</TableCell></TableRow>}
                {data?.totals && (
                  <TableRow className="bg-teal-50 font-bold border-t-2 border-teal-500">
                    <TableCell className="font-bold text-teal-700">TOTAL</TableCell>
                    <TableCell className="text-right font-bold text-teal-700">Q{data.totals.income.toFixed(2)}</TableCell>
                    <TableCell className="text-right font-bold text-red-700">Q{data.totals.expenses.toFixed(2)}</TableCell>
                    <TableCell className="text-right font-bold text-teal-700">Q{data.totals.profit.toFixed(2)}</TableCell>
                    <TableCell className="text-center font-bold">{data.totals.sales_count}</TableCell>
                    <TableCell className="text-center font-bold">{data.totals.appointments}</TableCell>
                    <TableCell></TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </Card>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card><CardHeader className="pb-2"><CardTitle className="text-sm font-semibold">Ingresos por sucursal</CardTitle></CardHeader>
              <CardContent style={{ height: 280 }}>
                <ResponsiveContainer><BarChart data={data?.branches || []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                  <XAxis dataKey="branch_name" fontSize={10} />
                  <YAxis fontSize={10} />
                  <Tooltip formatter={v => `Q${v.toFixed(2)}`} />
                  <Bar dataKey="income" fill="#0D9488" name="Ingresos" radius={[4, 4, 0, 0]} />
                </BarChart></ResponsiveContainer>
              </CardContent>
            </Card>
            <Card><CardHeader className="pb-2"><CardTitle className="text-sm font-semibold">Utilidad por sucursal</CardTitle></CardHeader>
              <CardContent style={{ height: 280 }}>
                <ResponsiveContainer><BarChart data={data?.branches || []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                  <XAxis dataKey="branch_name" fontSize={10} />
                  <YAxis fontSize={10} />
                  <Tooltip formatter={v => `Q${v.toFixed(2)}`} />
                  <Bar dataKey="profit" fill="#10B981" name="Utilidad" radius={[4, 4, 0, 0]} />
                </BarChart></ResponsiveContainer>
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </>
  );
}
