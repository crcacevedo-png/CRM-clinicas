import { useEffect, useState } from 'react';
import axios from 'axios';
import { useAuth } from '../../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import {
  TrendingUp, TrendingDown, Users, Activity, Building2, DollarSign,
  Calendar, Pill, ShoppingCart, AlertTriangle, MapPin, Zap, CheckCircle2,
  Download,
} from 'lucide-react';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid,
  PieChart, Pie, Cell, Legend,
} from 'recharts';
import { exportToCsv } from '../../lib/csv';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const fmtMoney = (n) => `$${(Number(n) || 0).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
const fmtPct = (n) => (n === null || n === undefined ? '—' : `${n > 0 ? '+' : ''}${n}%`);

function Kpi({ label, value, sub, trend, icon: Icon, color = 'teal' }) {
  const colorMap = {
    teal: 'bg-teal-50 text-teal-700 border-teal-200',
    blue: 'bg-blue-50 text-blue-700 border-blue-200',
    emerald: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    amber: 'bg-amber-50 text-amber-700 border-amber-200',
    rose: 'bg-rose-50 text-rose-700 border-rose-200',
    slate: 'bg-slate-50 text-slate-700 border-slate-200',
  };
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 hover:shadow-md transition-shadow" data-testid={`kpi-${label.toLowerCase().replace(/\s+/g, '-')}`}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">{label}</p>
          <p className="text-2xl font-bold text-slate-900 mt-1">{value}</p>
          {sub && <p className="text-xs text-slate-500 mt-0.5">{sub}</p>}
        </div>
        <div className={`p-2 rounded-lg border ${colorMap[color]}`}>
          {Icon && <Icon className="w-4 h-4" />}
        </div>
      </div>
      {trend !== undefined && trend !== null && (
        <div className={`mt-2 text-xs font-semibold flex items-center gap-1 ${trend >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
          {trend >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
          {fmtPct(trend)} vs. anterior
        </div>
      )}
    </div>
  );
}

function SectionTitle({ icon: Icon, children, hint }) {
  return (
    <div className="flex items-center gap-2 mt-6 mb-3">
      <Icon className="w-4 h-4 text-teal-600" />
      <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wider">{children}</h2>
      {hint && <span className="text-xs text-slate-400 font-normal normal-case">{hint}</span>}
    </div>
  );
}

function CsvBtn({ onClick, testId, disabled }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`text-[10px] px-2 py-1 rounded border inline-flex items-center gap-1 transition-all ${disabled ? 'border-slate-200 text-slate-300 cursor-not-allowed' : 'border-slate-200 text-slate-500 hover:border-teal-300 hover:text-teal-700 hover:bg-teal-50'}`}
      title="Exportar a CSV"
      data-testid={testId}
    >
      <Download className="w-3 h-3" /> CSV
    </button>
  );
}

function CardHeaderRow({ children, csv }) {
  return (
    <div className="flex items-center justify-between gap-2">
      {children}
      {csv}
    </div>
  );
}

const PLAN_COLORS = { free: '#94A3B8', basic: '#60A5FA', professional: '#14B8A6', enterprise: '#A855F7' };
const STATUS_COLORS = { scheduled: '#3B82F6', confirmed: '#14B8A6', completed: '#10B981', cancelled: '#94A3B8', no_show: '#EF4444', unknown: '#CBD5E1' };

export default function AdminDashboard() {
  const { getAuthHeaders } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    axios.get(`${API}/admin/dashboard/saas`, { headers: getAuthHeaders() })
      .then((res) => { if (!cancelled) setData(res.data); })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (loading) return <div className="p-8 flex items-center justify-center min-h-screen"><div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" /></div>;
  if (!data) return <div className="p-8 text-sm text-rose-600">Error al cargar el dashboard.</div>;

  const g = data.growth || {};
  const a = data.activation || {};
  const e = data.engagement || {};
  const f = data.financial || {};
  const o = data.ops || {};

  return (
    <div className="p-6 space-y-2" data-testid="admin-dashboard">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Panel SaaS</h1>
          <p className="text-sm text-slate-500">Métricas en tiempo real · Generado {new Date(data.generated_at).toLocaleString('es-GT')}</p>
        </div>
        <button
          type="button"
          onClick={() => {
            // Exporta TODOS los datasets en un único CSV con secciones marcadas
            const blob = new Blob(['\ufeff' + JSON.stringify(data, null, 2)], { type: 'application/json;charset=utf-8;' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            const ts = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-');
            a.download = `saas_dashboard_snapshot_${ts}.json`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(url);
          }}
          className="text-xs px-3 py-1.5 rounded-md border border-slate-200 text-slate-600 hover:border-teal-300 hover:text-teal-700 hover:bg-teal-50 inline-flex items-center gap-1.5"
          title="Descargar snapshot completo en JSON"
          data-testid="export-snapshot"
        >
          <Download className="w-3.5 h-3.5" /> Snapshot JSON
        </button>
      </div>

      {/* ===== BLOQUE 1 — GROWTH ===== */}
      <SectionTitle icon={TrendingUp}>Crecimiento</SectionTitle>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Kpi label="MRR" value={fmtMoney(g.mrr)} sub={`ARR ${fmtMoney(g.arr)}`} icon={DollarSign} color="emerald" />
        <Kpi label="Clínicas activas" value={g.active_clinics} sub={`${g.inactive_clinics} inactivas · ${g.total_clinics} total`} icon={Building2} color="teal" />
        <Kpi label="Nuevas 30d" value={g.new_clinics?.d30} sub={`Hoy ${g.new_clinics?.today} · 7d ${g.new_clinics?.d7}`} trend={g.new_clinics?.mom_pct} icon={TrendingUp} color="blue" />
        <Kpi label="Free→Paid 30d" value={g.free_to_paid?.d30} sub={`60d ${g.free_to_paid?.d60} · 90d ${g.free_to_paid?.d90}`} icon={CheckCircle2} color="emerald" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 mt-3">
        {/* Funnel */}
        <Card className="border border-slate-200">
          <CardHeader className="pb-2"><CardHeaderRow csv={
            <CsvBtn testId="csv-funnel" disabled={!g.funnel} onClick={() => {
              const rows = [
                { paso: 'Registradas', clinicas: g.funnel?.registered || 0 },
                { paso: 'Con >=1 paciente', clinicas: g.funnel?.with_patient || 0 },
                { paso: 'Con >=1 cita', clinicas: g.funnel?.with_appointment || 0 },
                { paso: 'Con >=1 venta', clinicas: g.funnel?.with_sale || 0 },
              ];
              exportToCsv('funnel_onboarding', rows);
            }} />
          }><CardTitle className="text-sm font-semibold text-slate-700">Funnel de onboarding</CardTitle></CardHeaderRow></CardHeader>
          <CardContent>
            {(() => {
              const steps = [
                { label: 'Registradas', value: g.funnel?.registered || 0 },
                { label: 'Con ≥1 paciente', value: g.funnel?.with_patient || 0 },
                { label: 'Con ≥1 cita', value: g.funnel?.with_appointment || 0 },
                { label: 'Con ≥1 venta', value: g.funnel?.with_sale || 0 },
              ];
              const max = Math.max(1, ...steps.map((s) => s.value));
              return (
                <div className="space-y-1.5">
                  {steps.map((s, i) => {
                    const prev = i > 0 ? steps[i - 1].value : null;
                    const conv = prev ? Math.round((s.value / prev) * 100) : null;
                    return (
                      <div key={s.label} className="flex items-center gap-2">
                        <span className="text-xs text-slate-600 w-32 flex-shrink-0">{s.label}</span>
                        <div className="flex-1 bg-slate-100 rounded h-6 relative overflow-hidden">
                          <div className="bg-teal-500 h-full rounded transition-all" style={{ width: `${(s.value / max) * 100}%` }} />
                          <span className="absolute inset-0 flex items-center px-2 text-xs font-bold text-white mix-blend-difference">{s.value}</span>
                        </div>
                        <span className="text-xs text-slate-500 w-12 text-right">{conv !== null ? `${conv}%` : ''}</span>
                      </div>
                    );
                  })}
                </div>
              );
            })()}
          </CardContent>
        </Card>

        {/* Geographic */}
        <Card className="border border-slate-200">
          <CardHeader className="pb-2"><CardHeaderRow csv={
            <CsvBtn testId="csv-geo" disabled={!g.geo?.length} onClick={() => exportToCsv('distribucion_geografica', g.geo || [], [
              { key: 'country', label: 'Pais' },
              { key: 'count', label: 'Total clinicas' },
              { key: 'active', label: 'Activas' },
              { key: 'mrr', label: 'MRR USD' },
            ])} />
          }><CardTitle className="text-sm font-semibold text-slate-700 flex items-center gap-2"><MapPin className="w-3.5 h-3.5" />Distribución geográfica</CardTitle></CardHeaderRow></CardHeader>
          <CardContent>
            <div className="space-y-1.5 max-h-56 overflow-y-auto">
              {(g.geo || []).map((c) => (
                <div key={c.country} className="flex items-center justify-between text-xs border-b border-slate-100 pb-1 last:border-0">
                  <span className="capitalize text-slate-700">{c.country.replace('_', ' ')}</span>
                  <span className="text-slate-500">{c.active}/{c.count} activas · {fmtMoney(c.mrr)} MRR</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* ===== BLOQUE 2 — ACTIVATION ===== */}
      <SectionTitle icon={Activity}>Adopción y activación</SectionTitle>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <Kpi label="DAU" value={a.dau} sub="Usuarios activos hoy" icon={Users} color="teal" />
        <Kpi label="WAU" value={a.wau} sub="Activos últimos 7d" icon={Users} color="blue" />
        <Kpi label="MAU" value={a.mau} sub="Activos últimos 30d" icon={Users} color="emerald" />
        <Kpi label="Sticky Ratio" value={`${a.sticky_ratio_pct || 0}%`} sub="DAU/MAU · ideal > 20%" icon={Zap} color={a.sticky_ratio_pct >= 20 ? 'emerald' : 'amber'} />
        <Kpi label="Inactivas 14d" value={a.inactive_clinics?.d14} sub={`7d: ${a.inactive_clinics?.d7} · 30d: ${a.inactive_clinics?.d30}`} icon={AlertTriangle} color="amber" />
      </div>

      <Card className="border border-slate-200 mt-3">
        <CardHeader className="pb-2"><CardHeaderRow csv={
          <CsvBtn testId="csv-modules" disabled={!a.module_adoption?.length} onClick={() => exportToCsv('adopcion_por_modulo', a.module_adoption || [], [
            { key: 'module', label: 'Modulo' },
            { key: 'clinics', label: 'Clinicas que lo usan' },
            { key: 'pct', label: '% de adopcion' },
          ])} />
        }><CardTitle className="text-sm font-semibold text-slate-700">Adopción por módulo</CardTitle></CardHeaderRow></CardHeader>
        <CardContent>
          <div className="space-y-1.5">
            {(a.module_adoption || []).map((m) => (
              <div key={m.module} className="flex items-center gap-2">
                <span className="text-xs text-slate-600 w-32 flex-shrink-0">{m.module}</span>
                <div className="flex-1 bg-slate-100 rounded h-5 relative overflow-hidden">
                  <div
                    className={`h-full rounded transition-all ${m.pct >= 70 ? 'bg-emerald-500' : m.pct >= 40 ? 'bg-teal-500' : m.pct >= 20 ? 'bg-amber-500' : 'bg-rose-400'}`}
                    style={{ width: `${m.pct}%` }}
                  />
                </div>
                <span className="text-xs text-slate-700 font-semibold w-20 text-right">{m.pct}% <span className="text-slate-400 font-normal">({m.clinics})</span></span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* ===== BLOQUE 3 — ENGAGEMENT ===== */}
      <SectionTitle icon={Calendar}>Engagement clínico</SectionTitle>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Kpi label="Citas hoy" value={e.periods?.today?.appointments} sub={`7d ${e.periods?.d7?.appointments} · 30d ${e.periods?.d30?.appointments}`} icon={Calendar} color="teal" />
        <Kpi label="Recetas hoy" value={e.periods?.today?.prescriptions} sub={`7d ${e.periods?.d7?.prescriptions} · 30d ${e.periods?.d30?.prescriptions}`} icon={Pill} color="blue" />
        <Kpi label="Ventas hoy" value={e.periods?.today?.sales} sub={`7d ${e.periods?.d7?.sales} · 30d ${e.periods?.d30?.sales}`} icon={ShoppingCart} color="emerald" />
        <Kpi label="Pacientes nuevos 30d" value={e.periods?.d30?.patients} sub={`Hoy ${e.periods?.today?.patients}`} icon={Users} color="slate" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3 mt-3">
        {/* Top 10 */}
        <Card className="border border-slate-200 lg:col-span-1">
          <CardHeader className="pb-2"><CardHeaderRow csv={
            <CsvBtn testId="csv-top10" disabled={!e.top10?.length} onClick={() => exportToCsv('top10_clinicas_activas', e.top10 || [], [
              { key: 'name', label: 'Clinica' }, { key: 'plan', label: 'Plan' }, { key: 'country', label: 'Pais' },
              { key: 'score', label: 'Score' }, { key: 'appointments', label: 'Citas 30d' },
              { key: 'prescriptions', label: 'Recetas 30d' }, { key: 'sales', label: 'Ventas 30d' }, { key: 'patients', label: 'Pacientes 30d' },
            ])} />
          }><CardTitle className="text-sm font-semibold text-slate-700">Top 10 clínicas activas (30d)</CardTitle></CardHeaderRow></CardHeader>
          <CardContent>
            <ol className="space-y-1.5">
              {(e.top10 || []).map((c, i) => (
                <li key={c.id} className="flex items-center justify-between text-xs border-b border-slate-100 pb-1 last:border-0">
                  <span className="flex items-center gap-1.5 min-w-0">
                    <span className="text-slate-400 font-mono w-4">{i + 1}.</span>
                    <span className="truncate text-slate-700">{c.name}</span>
                  </span>
                  <span className="text-slate-500 font-semibold">{c.score}</span>
                </li>
              ))}
              {(!e.top10 || e.top10.length === 0) && <li className="text-xs text-slate-400 italic">Sin actividad reciente</li>}
            </ol>
          </CardContent>
        </Card>

        {/* Bottom 10 (in-risk) */}
        <Card className="border border-slate-200">
          <CardHeader className="pb-2"><CardHeaderRow csv={
            <CsvBtn testId="csv-bottom10" disabled={!e.bottom10?.length} onClick={() => exportToCsv('bottom10_clinicas_outreach', e.bottom10 || [], [
              { key: 'name', label: 'Clinica' }, { key: 'plan', label: 'Plan' }, { key: 'country', label: 'Pais' },
              { key: 'score', label: 'Score' }, { key: 'appointments', label: 'Citas 30d' },
              { key: 'prescriptions', label: 'Recetas 30d' }, { key: 'sales', label: 'Ventas 30d' },
            ])} />
          }><CardTitle className="text-sm font-semibold text-slate-700 flex items-center gap-2"><AlertTriangle className="w-3.5 h-3.5 text-rose-500" />Bottom 10 — Outreach</CardTitle></CardHeaderRow></CardHeader>
          <CardContent>
            <ol className="space-y-1.5">
              {(e.bottom10 || []).map((c, i) => (
                <li key={c.id} className="flex items-center justify-between text-xs border-b border-slate-100 pb-1 last:border-0">
                  <span className="flex items-center gap-1.5 min-w-0">
                    <span className="text-slate-400 font-mono w-4">{i + 1}.</span>
                    <span className="truncate text-slate-700">{c.name}</span>
                  </span>
                  <span className={`font-semibold ${c.score === 0 ? 'text-rose-600' : 'text-amber-600'}`}>{c.score}</span>
                </li>
              ))}
              {(!e.bottom10 || e.bottom10.length === 0) && <li className="text-xs text-slate-400 italic">—</li>}
            </ol>
          </CardContent>
        </Card>

        {/* Appointment status */}
        <Card className="border border-slate-200">
          <CardHeader className="pb-2"><CardHeaderRow csv={
            <CsvBtn testId="csv-apt-status" disabled={!e.appointment_status?.length} onClick={() => exportToCsv('estado_de_citas_30d', e.appointment_status || [], [
              { key: 'status', label: 'Estado' }, { key: 'count', label: 'Cantidad' }, { key: 'pct', label: '% del total' },
            ])} />
          }><CardTitle className="text-sm font-semibold text-slate-700">Estado de citas (30d)</CardTitle></CardHeaderRow></CardHeader>
          <CardContent>
            {e.appointment_status?.length > 0 ? (
              <ResponsiveContainer width="100%" height={170}>
                <PieChart>
                  <Pie data={e.appointment_status} dataKey="count" nameKey="status" innerRadius={40} outerRadius={70} paddingAngle={2}>
                    {e.appointment_status.map((entry, i) => (
                      <Cell key={i} fill={STATUS_COLORS[entry.status] || '#CBD5E1'} />
                    ))}
                  </Pie>
                  <Tooltip />
                  <Legend wrapperStyle={{ fontSize: 10 }} />
                </PieChart>
              </ResponsiveContainer>
            ) : <p className="text-xs text-slate-400 italic">Sin citas en los últimos 30 días</p>}
          </CardContent>
        </Card>
      </div>

      {/* ===== BLOQUE 4 — FINANCIAL ===== */}
      <SectionTitle icon={DollarSign}>Salud financiera</SectionTitle>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Kpi label="MRR total" value={fmtMoney(g.mrr)} sub={`ARR ${fmtMoney(g.arr)}`} icon={DollarSign} color="emerald" />
        <Kpi label="AR total" value={fmtMoney(f.ar_total)} sub="Saldo pendiente agregado" icon={DollarSign} color="amber" />
        <Kpi label="Vencen 7d" value={f.expiring_soon_counts?.d7} sub={`14d: ${f.expiring_soon_counts?.d14} · 30d: ${f.expiring_soon_counts?.d30}`} icon={AlertTriangle} color="rose" />
        <Kpi label="Citas 30d" value={e.total_appointments_30d} sub="Volumen del ecosistema" icon={Calendar} color="blue" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 mt-3">
        {/* MRR by plan */}
        <Card className="border border-slate-200">
          <CardHeader className="pb-2"><CardHeaderRow csv={
            <CsvBtn testId="csv-mrr-plan" disabled={!f.mrr_by_plan?.length} onClick={() => exportToCsv('mrr_por_plan', f.mrr_by_plan || [], [
              { key: 'plan', label: 'Plan' }, { key: 'clinics', label: 'Clinicas activas' }, { key: 'mrr', label: 'MRR USD' },
            ])} />
          }><CardTitle className="text-sm font-semibold text-slate-700">MRR por plan</CardTitle></CardHeaderRow></CardHeader>
          <CardContent>
            {f.mrr_by_plan?.length > 0 ? (
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={f.mrr_by_plan}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="plan" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(v, n) => (n === 'mrr' ? fmtMoney(v) : v)} />
                  <Bar dataKey="mrr" name="MRR">
                    {f.mrr_by_plan.map((p, i) => (<Cell key={i} fill={PLAN_COLORS[p.plan] || '#14B8A6'} />))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : <p className="text-xs text-slate-400">Sin datos</p>}
            <div className="mt-2 flex flex-wrap gap-3 text-[11px]">
              {f.mrr_by_plan?.map((p) => (
                <span key={p.plan} className="text-slate-500">
                  <span className="inline-block w-2 h-2 rounded-full mr-1" style={{ background: PLAN_COLORS[p.plan] || '#14B8A6' }} />
                  {p.plan}: {p.clinics} clínicas · {fmtMoney(p.mrr)}
                </span>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Expiring plans */}
        <Card className="border border-slate-200">
          <CardHeader className="pb-2"><CardHeaderRow csv={
            <CsvBtn testId="csv-expiring" disabled={!f.expiring_soon_d30?.length} onClick={() => exportToCsv('planes_vencen_30d', f.expiring_soon_d30 || [], [
              { key: 'name', label: 'Clinica' }, { key: 'plan', label: 'Plan' }, { key: 'days', label: 'Dias para vencer' },
            ])} />
          }><CardTitle className="text-sm font-semibold text-slate-700 flex items-center gap-2"><AlertTriangle className="w-3.5 h-3.5 text-amber-500" />Planes próximos a vencer (30d)</CardTitle></CardHeaderRow></CardHeader>
          <CardContent>
            {f.expiring_soon_d30?.length > 0 ? (
              <ul className="space-y-1.5 max-h-52 overflow-y-auto">
                {f.expiring_soon_d30.map((c) => (
                  <li key={c.clinic_id} className="flex items-center justify-between text-xs border-b border-slate-100 pb-1 last:border-0">
                    <span className="truncate text-slate-700">{c.name}</span>
                    <span className="flex items-center gap-2">
                      <span className="text-slate-400 capitalize">{c.plan}</span>
                      <span className={`font-semibold ${c.days <= 7 ? 'text-rose-600' : c.days <= 14 ? 'text-amber-600' : 'text-slate-500'}`}>
                        {c.days <= 1 ? 'mañana' : `en ${Math.round(c.days)}d`}
                      </span>
                    </span>
                  </li>
                ))}
              </ul>
            ) : <p className="text-xs text-slate-400 italic">Ningún plan vence en los próximos 30 días</p>}
          </CardContent>
        </Card>
      </div>

      {/* ===== BLOQUE 6 — OPERATIONS ===== */}
      <SectionTitle icon={AlertTriangle} hint="Oportunidades de upsell y alertas técnicas">Operaciones</SectionTitle>
      <Card className="border border-slate-200">
        <CardHeader className="pb-2"><CardHeaderRow csv={
          <CsvBtn testId="csv-plan-warnings" disabled={!o.plan_limit_warnings?.length} onClick={() => exportToCsv('plan_limit_warnings', o.plan_limit_warnings || [], [
            { key: 'name', label: 'Clinica' }, { key: 'plan', label: 'Plan' }, { key: 'metric', label: 'Metrica' },
            { key: 'used', label: 'Usado' }, { key: 'limit', label: 'Limite' }, { key: 'pct', label: '% del limite' },
          ])} />
        }><CardTitle className="text-sm font-semibold text-slate-700">Clínicas cerca del límite del plan (pacientes)</CardTitle></CardHeaderRow></CardHeader>
        <CardContent>
          {o.plan_limit_warnings?.length > 0 ? (
            <table className="w-full text-xs">
              <thead>
                <tr className="text-slate-500 border-b border-slate-200">
                  <th className="text-left py-1.5">Clínica</th>
                  <th className="text-left">Plan</th>
                  <th className="text-right">Usado</th>
                  <th className="text-right">Límite</th>
                  <th className="text-right">% del límite</th>
                </tr>
              </thead>
              <tbody>
                {o.plan_limit_warnings.map((w) => (
                  <tr key={w.clinic_id} className="border-b border-slate-100 last:border-0">
                    <td className="py-1.5 text-slate-700">{w.name}</td>
                    <td className="capitalize text-slate-500">{w.plan}</td>
                    <td className="text-right">{w.used}</td>
                    <td className="text-right text-slate-400">{w.limit}</td>
                    <td className={`text-right font-semibold ${w.pct >= 100 ? 'text-rose-600' : w.pct >= 90 ? 'text-amber-600' : 'text-slate-600'}`}>{w.pct}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <p className="text-xs text-slate-400 italic">Ninguna clínica supera el 80% del límite — todo holgado.</p>}
        </CardContent>
      </Card>

      <div className="h-6" />
    </div>
  );
}
