import { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui/table';
import { CreditCard, DollarSign, Building2, TrendingUp, Plug, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const money = (n, cur = 'USD') => `${cur === 'GTQ' ? 'Q' : '$'}${(n ?? 0).toLocaleString('es-GT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

function KpiCard({ title, value, sub, icon: Icon, testid }) {
  return (
    <Card className="border border-slate-200" data-testid={testid}>
      <CardContent className="p-5">
        <div className="flex items-center justify-between">
          <span className="text-xs uppercase tracking-wide text-slate-400">{title}</span>
          {Icon && <Icon className="w-4 h-4 text-teal-500" />}
        </div>
        <div className="mt-2 text-2xl font-bold text-slate-900">{value}</div>
        {sub && <div className="text-xs text-slate-400 mt-1">{sub}</div>}
      </CardContent>
    </Card>
  );
}

export default function CobrosPage() {
  const { getAuthHeaders } = useAuth();
  const headers = getAuthHeaders();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/admin/billing/overview`, { headers });
      setData(res.data);
    } catch (err) {
      toast.error('Error al cargar cobros: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  const connectStripe = async () => {
    try {
      const res = await axios.post(`${API}/admin/billing/stripe/connect`, {}, { headers });
      toast.info(res.data?.message || 'Integración pendiente');
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message);
    }
  };

  if (loading) return <div className="p-6 lg:p-8 flex justify-center items-center h-96"><div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" /></div>;
  if (!data) return <div className="p-6 text-sm text-slate-500">Sin datos</div>;

  const s = data.summary || {};

  return (
    <div className="p-6 lg:p-8 space-y-6" data-testid="cobros-page">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 mb-1 flex items-center gap-2">
            <CreditCard className="w-6 h-6 text-teal-600" /> Cobros
          </h1>
          <p className="text-sm text-slate-500">Suscripciones y facturación SaaS de las clínicas</p>
        </div>
        <Button variant="outline" size="sm" onClick={load} data-testid="cobros-refresh-btn">
          <RefreshCw className="w-4 h-4 mr-1" /> Actualizar
        </Button>
      </div>

      {/* Stripe connection banner */}
      <Card className={`border ${data.stripe_configured ? 'border-emerald-200 bg-emerald-50' : 'border-amber-200 bg-amber-50'}`} data-testid="stripe-status-card">
        <CardContent className="p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Plug className={`w-5 h-5 ${data.stripe_configured ? 'text-emerald-600' : 'text-amber-600'}`} />
            <div>
              <p className="text-sm font-medium text-slate-800">
                {data.stripe_configured ? 'Stripe conectado' : 'Stripe no configurado'}
              </p>
              <p className="text-xs text-slate-500">
                {data.stripe_configured
                  ? 'Los cobros automáticos están activos.'
                  : 'La ruta de cobros está lista. Conecta la API de Stripe para automatizar el cobro mensual.'}
              </p>
            </div>
          </div>
          {!data.stripe_configured && (
            <Button size="sm" className="bg-teal-600 hover:bg-teal-700" onClick={connectStripe} data-testid="connect-stripe-btn">
              Conectar Stripe
            </Button>
          )}
        </CardContent>
      </Card>

      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard title="MRR estimado" value={money(s.mrr)} sub="Ingreso recurrente mensual" icon={DollarSign} testid="kpi-mrr" />
        <KpiCard title="ARR estimado" value={money(s.arr)} sub="Ingreso recurrente anual" icon={TrendingUp} testid="kpi-arr" />
        <KpiCard title="Clínicas activas" value={s.active_clinics ?? 0} sub={`de ${s.total_clinics ?? 0} totales`} icon={Building2} testid="kpi-active" />
        <KpiCard title="Total clínicas" value={s.total_clinics ?? 0} sub="en la plataforma" icon={Building2} testid="kpi-total" />
      </div>

      {/* By plan */}
      <Card className="border border-slate-200">
        <CardHeader className="pb-2"><CardTitle className="text-base">Ingresos por plan</CardTitle></CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {(data.by_plan || []).map((p) => (
              <div key={p.plan_code || 'none'} className="p-4 rounded-lg border border-slate-100 bg-slate-50" data-testid={`plan-agg-${p.plan_code}`}>
                <Badge className="bg-teal-600 text-white text-xs mb-2">{p.plan_name || 'Sin plan'}</Badge>
                <p className="text-lg font-bold text-slate-800">{money(p.mrr)}<span className="text-xs font-normal text-slate-400"> /mes</span></p>
                <p className="text-xs text-slate-500">{p.count} clínica{p.count !== 1 ? 's' : ''}</p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Clinics table */}
      <Card className="border border-slate-200">
        <CardHeader className="pb-2"><CardTitle className="text-base">Clínicas y suscripciones</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-xs">Clínica</TableHead>
                <TableHead className="text-xs">Plan</TableHead>
                <TableHead className="text-xs text-right">Precio/mes</TableHead>
                <TableHead className="text-xs text-center">Estado</TableHead>
                <TableHead className="text-xs">Expira</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(data.clinics || []).map((c) => (
                <TableRow key={c.clinic_id} data-testid={`cobro-row-${c.clinic_id}`}>
                  <TableCell className="text-sm font-medium">{c.name}</TableCell>
                  <TableCell><Badge variant="outline" className="text-xs">{c.plan_name || '—'}</Badge></TableCell>
                  <TableCell className="text-sm text-right font-mono">{money(c.price_monthly, c.currency)}</TableCell>
                  <TableCell className="text-center">
                    {c.status === 'active'
                      ? <Badge className="bg-emerald-100 text-emerald-700 text-[10px]">Activa</Badge>
                      : <Badge className="bg-rose-100 text-rose-700 text-[10px]">Suspendida</Badge>}
                  </TableCell>
                  <TableCell className="text-xs text-slate-500">
                    {c.expires_at ? new Date(c.expires_at).toLocaleDateString('es-GT') : '—'}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
