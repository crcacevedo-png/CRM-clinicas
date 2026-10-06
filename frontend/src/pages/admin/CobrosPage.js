import { useState, useEffect, useCallback, useMemo } from 'react';
import axios from 'axios';
import { useAuth } from '../../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import {
  CreditCard, DollarSign, Building2, TrendingUp, RefreshCw, CheckCircle2,
  AlertTriangle, Zap, Receipt, ExternalLink, Loader2, Repeat,
} from 'lucide-react';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const money = (n, cur = 'USD') =>
  `${cur === 'GTQ' ? 'Q' : '$'}${(n ?? 0).toLocaleString('es-GT', {
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  })}`;

const STATUS_LABEL = {
  active: 'Activa', trialing: 'Prueba', canceled: 'Cancelada',
  past_due: 'Pago vencido', unpaid: 'Impago', incomplete: 'Incompleta',
  incomplete_expired: 'Expirada',
};
const STATUS_CLASS = {
  active: 'bg-emerald-100 text-emerald-700',
  trialing: 'bg-blue-100 text-blue-700',
  canceled: 'bg-slate-100 text-slate-600',
  past_due: 'bg-amber-100 text-amber-700',
  unpaid: 'bg-rose-100 text-rose-700',
  incomplete: 'bg-amber-100 text-amber-700',
  incomplete_expired: 'bg-rose-100 text-rose-700',
};

function KpiCard({ title, value, sub, icon: Icon, testid, color = 'teal' }) {
  const colors = {
    teal: 'text-teal-500',
    emerald: 'text-emerald-500',
    blue: 'text-blue-500',
    amber: 'text-amber-500',
  };
  return (
    <Card className="border border-slate-200" data-testid={testid}>
      <CardContent className="p-5">
        <div className="flex items-center justify-between">
          <span className="text-xs uppercase tracking-wide text-slate-400">{title}</span>
          {Icon && <Icon className={`w-4 h-4 ${colors[color]}`} />}
        </div>
        <div className="mt-2 text-2xl font-bold text-slate-900">{value}</div>
        {sub && <div className="text-xs text-slate-400 mt-1">{sub}</div>}
      </CardContent>
    </Card>
  );
}

export default function CobrosPage() {
  const { getAuthHeaders } = useAuth();
  const headers = useMemo(() => getAuthHeaders(), [getAuthHeaders]);
  const [data, setData] = useState(null);
  const [txs, setTxs] = useState([]);
  const [retryData, setRetryData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [overview, transactions, retries] = await Promise.all([
        axios.get(`${API}/admin/billing/overview`, { headers }),
        axios.get(`${API}/admin/billing/transactions?limit=20`, { headers }),
        axios.get(`${API}/admin/billing/retry-dashboard`, { headers }),
      ]);
      setData(overview.data);
      setTxs(transactions.data?.transactions || []);
      setRetryData(retries.data);
    } catch (err) {
      toast.error('Error al cargar cobros: ' + (err.response?.data?.detail || err.message));
    } finally { setLoading(false); }
  }, [headers]);

  useEffect(() => { load(); }, [load]);

  const syncCatalog = async () => {
    setSyncing(true);
    try {
      const r = await axios.post(`${API}/admin/billing/sync-stripe-catalog`, {}, { headers });
      const c = r.data?.counters;
      if (c?.errors?.length) {
        toast.error(`Sincronización con errores: ${c.errors[0]}`);
      } else {
        toast.success(`Sincronizado: ${c?.prices_created || 0} precios creados, ${c?.prices_reused || 0} reutilizados`);
      }
      load();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al sincronizar');
    } finally { setSyncing(false); }
  };

  if (loading) {
    return <div className="p-6 lg:p-8 flex justify-center items-center h-96">
      <Loader2 className="w-8 h-8 text-teal-600 animate-spin" />
    </div>;
  }
  if (!data) return <div className="p-6 text-sm text-slate-500">Sin datos</div>;

  const s = data.summary || {};
  const stripeConfigured = data.stripe_configured;
  const anyPlanSynced = (data.by_plan || []).some(p => p.synced);

  return (
    <div className="p-6 lg:p-8 space-y-6" data-testid="cobros-page">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 mb-1 flex items-center gap-2">
            <CreditCard className="w-6 h-6 text-teal-600" /> Cobros SaaS
          </h1>
          <p className="text-sm text-slate-500">Suscripciones mensuales de clínicas vía Stripe</p>
        </div>
        <div className="flex gap-2">
          {stripeConfigured && (
            <Button
              variant="outline"
              size="sm"
              onClick={syncCatalog}
              disabled={syncing}
              data-testid="sync-catalog-btn"
            >
              {syncing ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Zap className="w-4 h-4 mr-1" />}
              {anyPlanSynced ? 'Resincronizar planes' : 'Sincronizar planes con Stripe'}
            </Button>
          )}
          <Button variant="outline" size="sm" onClick={load} data-testid="cobros-refresh-btn">
            <RefreshCw className="w-4 h-4 mr-1" /> Actualizar
          </Button>
        </div>
      </div>

      {/* Stripe connection banner */}
      <Card className={`border ${stripeConfigured ? 'border-emerald-200 bg-emerald-50/60' : 'border-amber-200 bg-amber-50/60'}`} data-testid="stripe-status-card">
        <CardContent className="p-4">
          <div className="flex items-start gap-3">
            {stripeConfigured ? <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
              : <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />}
            <div className="flex-1">
              <p className="text-sm font-medium text-slate-800">
                {stripeConfigured ? 'Stripe conectado' : 'Stripe no configurado'}
              </p>
              {stripeConfigured ? (
                <>
                  <p className="text-xs text-slate-600 mt-1">
                    Los cobros automáticos están activos. {!anyPlanSynced && 'Antes de activar cobros, presiona Sincronizar planes para crear los productos en Stripe.'}
                  </p>
                  {anyPlanSynced && (
                    <p className="text-xs text-emerald-700 mt-1">
                      ✓ Catálogo sincronizado — las clínicas ya pueden suscribirse desde Configuración → Plan.
                    </p>
                  )}
                </>
              ) : (
                <div className="text-xs text-slate-600 mt-1 space-y-1">
                  <p>Agrega tu clave secreta de Stripe en <strong>Manage → Secrets → STRIPE_API_KEY</strong> para activar los cobros SaaS.</p>
                  <p className="text-amber-700">⚠ Guatemala no soporta cuentas Stripe nativas — usa una cuenta de otro país (US, MX, PA, ES, etc.).</p>
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <KpiCard title="MRR real" value={money(s.mrr)} sub="Suscripciones activas" icon={DollarSign} color="emerald" testid="kpi-mrr" />
        <KpiCard title="ARR estimado" value={money(s.arr)} sub="MRR × 12" icon={TrendingUp} color="blue" testid="kpi-arr" />
        <KpiCard title="Con suscripción" value={s.with_subscription ?? 0} sub="pagando por Stripe" icon={CheckCircle2} color="emerald" testid="kpi-with-sub" />
        <KpiCard title="Clínicas activas" value={s.active_clinics ?? 0} sub={`de ${s.total_clinics ?? 0} totales`} icon={Building2} color="teal" testid="kpi-active" />
        <KpiCard title="Total clínicas" value={s.total_clinics ?? 0} sub="en la plataforma" icon={Building2} color="teal" testid="kpi-total" />
      </div>

      <Tabs defaultValue="clinics">
        <TabsList>
          <TabsTrigger value="clinics" data-testid="cobros-tab-clinics"><Building2 className="w-3.5 h-3.5 mr-1" />Clínicas</TabsTrigger>
          <TabsTrigger value="retries" data-testid="cobros-tab-retries">
            <Repeat className="w-3.5 h-3.5 mr-1" />En reintento
            {retryData?.summary?.clinics_in_retry > 0 && (
              <Badge className="ml-1.5 bg-amber-500 text-white text-[10px] h-4 px-1.5">
                {retryData.summary.clinics_in_retry}
              </Badge>
            )}
            {retryData?.summary?.clinics_blocked > 0 && (
              <Badge className="ml-1 bg-rose-600 text-white text-[10px] h-4 px-1.5">
                {retryData.summary.clinics_blocked} bloq.
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="plans" data-testid="cobros-tab-plans"><Receipt className="w-3.5 h-3.5 mr-1" />Planes</TabsTrigger>
          <TabsTrigger value="transactions" data-testid="cobros-tab-tx"><CreditCard className="w-3.5 h-3.5 mr-1" />Transacciones</TabsTrigger>
        </TabsList>

        <TabsContent value="clinics">
          <Card className="border border-slate-200">
            <CardContent className="pt-6">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs">Clínica</TableHead>
                    <TableHead className="text-xs">Plan</TableHead>
                    <TableHead className="text-xs">Ciclo</TableHead>
                    <TableHead className="text-xs text-right">Precio/mes</TableHead>
                    <TableHead className="text-xs text-center">Stripe</TableHead>
                    <TableHead className="text-xs">Expira</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(data.clinics || []).map((c) => (
                    <TableRow key={c.clinic_id} data-testid={`cobro-row-${c.clinic_id}`}>
                      <TableCell className="text-sm font-medium">{c.name}</TableCell>
                      <TableCell><Badge variant="outline" className="text-xs">{c.plan_name || '—'}</Badge></TableCell>
                      <TableCell className="text-xs text-slate-500">{c.billing_cycle === 'yearly' ? 'Anual' : 'Mensual'}</TableCell>
                      <TableCell className="text-sm text-right font-mono">{money(c.price_monthly, c.currency)}</TableCell>
                      <TableCell className="text-center">
                        {c.stripe_subscription_status ? (
                          <Badge className={`text-[10px] ${STATUS_CLASS[c.stripe_subscription_status] || 'bg-slate-100 text-slate-600'}`}>
                            {STATUS_LABEL[c.stripe_subscription_status] || c.stripe_subscription_status}
                          </Badge>
                        ) : (
                          <span className="text-xs text-slate-400">Sin suscripción</span>
                        )}
                      </TableCell>
                      <TableCell className="text-xs text-slate-500">
                        {c.expires_at ? new Date(c.expires_at).toLocaleDateString('es-GT') : '—'}
                      </TableCell>
                    </TableRow>
                  ))}
                  {(data.clinics || []).length === 0 && (
                    <TableRow><TableCell colSpan={6} className="text-center text-sm text-slate-400 py-8">No hay clínicas</TableCell></TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="retries">
          <Card className="border border-slate-200">
            <CardContent className="pt-6 space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3" data-testid="retry-kpi-in-retry">
                  <div className="flex items-center gap-2 text-xs font-semibold text-amber-700 uppercase tracking-wide">
                    <Repeat className="w-3.5 h-3.5" />En reintento
                  </div>
                  <div className="text-2xl font-bold text-amber-900 mt-1">
                    {retryData?.summary?.clinics_in_retry ?? 0}
                  </div>
                  <div className="text-[11px] text-amber-700/80">Stripe reintentará automáticamente</div>
                </div>
                <div className="bg-rose-50 border border-rose-200 rounded-lg px-4 py-3" data-testid="retry-kpi-blocked">
                  <div className="flex items-center gap-2 text-xs font-semibold text-rose-700 uppercase tracking-wide">
                    <AlertTriangle className="w-3.5 h-3.5" />Bloqueadas
                  </div>
                  <div className="text-2xl font-bold text-rose-900 mt-1">
                    {retryData?.summary?.clinics_blocked ?? 0}
                  </div>
                  <div className="text-[11px] text-rose-700/80">Gracia expirada — acceso suspendido</div>
                </div>
                <div className="bg-slate-50 border border-slate-200 rounded-lg px-4 py-3" data-testid="retry-kpi-mrr-risk">
                  <div className="flex items-center gap-2 text-xs font-semibold text-slate-600 uppercase tracking-wide">
                    <DollarSign className="w-3.5 h-3.5" />MRR en riesgo
                  </div>
                  <div className="text-2xl font-bold text-slate-900 mt-1">
                    {money(retryData?.summary?.mrr_at_risk || 0)}
                  </div>
                  <div className="text-[11px] text-slate-500">Ingreso mensual bajo reintento</div>
                </div>
              </div>

              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs">Clínica</TableHead>
                    <TableHead className="text-xs">Estado</TableHead>
                    <TableHead className="text-xs text-right">MRR</TableHead>
                    <TableHead className="text-xs text-center">Intento</TableHead>
                    <TableHead className="text-xs">Motivo</TableHead>
                    <TableHead className="text-xs">Próximo reintento</TableHead>
                    <TableHead className="text-xs">Gracia hasta</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(retryData?.clinics || []).map((c) => (
                    <TableRow key={c.clinic_id} data-testid={`retry-row-${c.clinic_id}`}>
                      <TableCell className="text-sm font-medium">{c.clinic_name}</TableCell>
                      <TableCell>
                        {c.is_payment_blocked ? (
                          <Badge className="bg-rose-100 text-rose-700 text-[10px]">Bloqueada</Badge>
                        ) : (
                          <Badge className={`text-[10px] ${STATUS_CLASS[c.stripe_status] || 'bg-slate-100 text-slate-600'}`}>
                            {STATUS_LABEL[c.stripe_status] || c.stripe_status}
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-sm text-right font-mono">{money(c.monthly_price)}</TableCell>
                      <TableCell className="text-center text-xs font-semibold">
                        {c.last_attempt_count ? `#${c.last_attempt_count}` : '—'}
                      </TableCell>
                      <TableCell className="text-xs text-slate-600 max-w-[200px] truncate" title={c.last_failure_message || ''}>
                        {c.last_failure_message || <span className="text-slate-400">—</span>}
                      </TableCell>
                      <TableCell className="text-xs text-slate-600">
                        {c.next_retry_at ? (
                          <>
                            <Zap className="w-3 h-3 inline mr-1 text-amber-500" />
                            {new Date(c.next_retry_at).toLocaleString('es-GT', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
                          </>
                        ) : (
                          <span className="text-slate-400">Agotados</span>
                        )}
                      </TableCell>
                      <TableCell className="text-xs text-slate-600">
                        {c.payment_grace_until ? new Date(c.payment_grace_until).toLocaleDateString('es-GT') : '—'}
                      </TableCell>
                    </TableRow>
                  ))}
                  {(retryData?.clinics || []).length === 0 && (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center text-sm text-slate-400 py-10">
                        <CheckCircle2 className="w-8 h-8 mx-auto mb-2 text-emerald-400" strokeWidth={1.5} />
                        No hay clínicas en reintento. Todas las suscripciones están al día.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="plans">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {(data.by_plan || []).map((p) => (
              <Card key={p.plan_code || 'none'} className="border border-slate-200" data-testid={`plan-agg-${p.plan_code}`}>
                <CardContent className="p-5">
                  <div className="flex items-center justify-between mb-3">
                    <Badge className="bg-teal-600 text-white text-xs">{p.plan_name || 'Sin plan'}</Badge>
                    {p.synced ? (
                      <Badge className="bg-emerald-50 text-emerald-700 text-[10px]"><CheckCircle2 className="w-3 h-3 mr-0.5" />Sincronizado</Badge>
                    ) : (
                      <Badge className="bg-amber-50 text-amber-700 text-[10px]">Sin sync</Badge>
                    )}
                  </div>
                  <p className="text-xl font-bold text-slate-800">{money(p.mrr)}<span className="text-xs font-normal text-slate-400"> /mes</span></p>
                  <p className="text-xs text-slate-500 mt-1">{p.count} clínica{p.count !== 1 ? 's' : ''}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="transactions">
          <Card className="border border-slate-200">
            <CardContent className="pt-6">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs">Fecha</TableHead>
                    <TableHead className="text-xs">Clínica</TableHead>
                    <TableHead className="text-xs">Plan</TableHead>
                    <TableHead className="text-xs">Ciclo</TableHead>
                    <TableHead className="text-xs text-center">Estado</TableHead>
                    <TableHead className="text-xs font-mono">Session ID</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {txs.map((t) => (
                    <TableRow key={t.id} data-testid={`tx-row-${t.session_id}`}>
                      <TableCell className="text-xs">{new Date(t.created_at).toLocaleString('es-GT')}</TableCell>
                      <TableCell className="text-sm">{t.clinic_name}</TableCell>
                      <TableCell><Badge variant="outline" className="text-xs">{t.plan_code || '—'}</Badge></TableCell>
                      <TableCell className="text-xs text-slate-500">{t.billing_cycle === 'yearly' ? 'Anual' : 'Mensual'}</TableCell>
                      <TableCell className="text-center">
                        {t.payment_status === 'paid' ? (
                          <Badge className="bg-emerald-100 text-emerald-700 text-[10px]">Pagado</Badge>
                        ) : t.payment_status === 'pending' ? (
                          <Badge className="bg-amber-100 text-amber-700 text-[10px]">Pendiente</Badge>
                        ) : (
                          <Badge className="bg-slate-100 text-slate-600 text-[10px]">{t.payment_status || t.status}</Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-[10px] font-mono text-slate-400 truncate max-w-[160px]">{t.session_id?.substring(0, 24)}...</TableCell>
                    </TableRow>
                  ))}
                  {txs.length === 0 && (
                    <TableRow><TableCell colSpan={6} className="text-center text-sm text-slate-400 py-8">
                      <CreditCard className="w-8 h-8 mx-auto mb-2 opacity-30" strokeWidth={1} />
                      Aún no hay transacciones Stripe. Cuando una clínica se suscriba, aparecerán aquí.
                    </TableCell></TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <p className="text-xs text-slate-400 text-center">
        <ExternalLink className="w-3 h-3 inline mr-1" />
        Para probar en vivo, agrega tu clave Stripe real en Manage → Secrets, luego presiona "Sincronizar planes".
      </p>
    </div>
  );
}
