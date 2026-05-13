import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import {
  CalendarDays, Users, Clock, ArrowRight, Activity, Pill, Stethoscope,
  UserPlus, FileText, CalendarPlus, ChevronRight, FlaskConical,
  DollarSign, ShoppingCart, AlertTriangle, AlertCircle, PackageX,
  CalendarX, Wallet, TrendingUp, Receipt, Percent, BellRing,
} from 'lucide-react';
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts';
import AnnouncementsBanner from '../../components/AnnouncementsBanner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STATUS_CONFIG = {
  scheduled: { label: 'Pendiente', color: 'bg-blue-100 text-blue-700 border-blue-200', dot: 'bg-blue-500' },
  confirmed: { label: 'Confirmada', color: 'bg-indigo-100 text-indigo-700 border-indigo-200', dot: 'bg-indigo-500' },
  in_progress: { label: 'En curso', color: 'bg-amber-100 text-amber-700 border-amber-200', dot: 'bg-amber-500' },
  completed: { label: 'Completada', color: 'bg-emerald-100 text-emerald-700 border-emerald-200', dot: 'bg-emerald-500' },
  cancelled: { label: 'Cancelada', color: 'bg-red-100 text-red-600 border-red-200', dot: 'bg-red-500' },
  no_show: { label: 'No asistió', color: 'bg-orange-100 text-orange-600 border-orange-200', dot: 'bg-orange-500' },
};

const ACTIVITY_ICONS = {
  appointment: { icon: CalendarDays, color: 'text-blue-500 bg-blue-50' },
  prescription: { icon: Pill, color: 'text-teal-500 bg-teal-50' },
  patient: { icon: UserPlus, color: 'text-purple-500 bg-purple-50' },
};

const ALERT_ICONS = {
  low_stock: { icon: PackageX, bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200' },
  expiring: { icon: CalendarX, bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200' },
  ar_overdue: { icon: AlertCircle, bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200' },
  installment_overdue: { icon: AlertCircle, bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200' },
  cash_session: { icon: Wallet, bg: 'bg-orange-50', text: 'text-orange-700', border: 'border-orange-200' },
};

function StatCard({ label, value, subtitle, icon: Icon, color, onClick, testId }) {
  return (
    <Card
      className={`border border-slate-200 shadow-sm hover:shadow-md transition-shadow ${onClick ? 'cursor-pointer text-left w-full' : ''}`}
      onClick={onClick}
      data-testid={testId}
    >
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div className="min-w-0">
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">{label}</p>
            <p className="text-3xl font-bold text-slate-900 mt-1 truncate">{value}</p>
            {subtitle && <p className="text-xs text-slate-400 mt-0.5 truncate">{subtitle}</p>}
          </div>
          <div className={`w-10 h-10 rounded-lg flex items-center justify-center shrink-0 ${color}`}>
            <Icon className="w-5 h-5" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function formatTime(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleTimeString('es-GT', { hour: '2-digit', minute: '2-digit', hour12: true });
}

function formatRelative(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  const now = new Date();
  const diffMs = now - d;
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return 'Ahora';
  if (mins < 60) return `Hace ${mins} min`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `Hace ${hrs}h`;
  const days = Math.floor(hrs / 24);
  if (days === 1) return 'Ayer';
  if (days < 7) return `Hace ${days} días`;
  return d.toLocaleDateString('es-GT', { day: '2-digit', month: 'short' });
}

function formatCurrency(amount) {
  const n = Number(amount || 0);
  return `Q${n.toLocaleString('es-GT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatChartDate(iso) {
  if (!iso) return '';
  const [, m, d] = iso.split('-');
  return `${d}/${m}`;
}

function AdminStatsRow({ data, navigate }) {
  const features = data.features || [];
  const stats = data.admin_stats || {};
  const has = (f) => features.includes(f);
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 mb-6" data-testid="admin-stats-row">
      {has('sales') && (
        <>
          <StatCard
            label="Ventas hoy"
            value={formatCurrency(stats.sales_today_amount)}
            subtitle={`${stats.sales_today_count || 0} venta(s)`}
            icon={ShoppingCart}
            color="bg-emerald-50 text-emerald-600"
            onClick={() => navigate('/dashboard/ventas')}
            testId="stat-sales-today"
          />
          <StatCard
            label="Pendiente de cobro"
            value={formatCurrency(stats.ar_pending_amount)}
            subtitle="Cuentas por cobrar"
            icon={Receipt}
            color="bg-rose-50 text-rose-600"
            onClick={() => navigate('/dashboard/cuentas-por-cobrar')}
            testId="stat-ar-pending"
          />
        </>
      )}
      {has('inventory') && (
        <>
          <StatCard
            label="Stock bajo"
            value={stats.low_stock_count ?? 0}
            subtitle="Productos críticos"
            icon={PackageX}
            color="bg-amber-50 text-amber-600"
            onClick={() => navigate('/dashboard/inventario')}
            testId="stat-low-stock"
          />
          <StatCard
            label="Próximos a vencer"
            value={stats.expiring_count ?? 0}
            subtitle="60 días"
            icon={CalendarX}
            color="bg-orange-50 text-orange-600"
            onClick={() => navigate('/dashboard/inventario')}
            testId="stat-expiring"
          />
        </>
      )}
      {has('expenses') && (
        <StatCard
          label="Gastos del mes"
          value={formatCurrency(stats.expenses_month)}
          subtitle="Acumulado"
          icon={Wallet}
          color="bg-indigo-50 text-indigo-600"
          onClick={() => navigate('/dashboard/gastos')}
          testId="stat-expenses-month"
        />
      )}
      {has('commissions') && (
        <StatCard
          label="Comisiones del mes"
          value={formatCurrency(stats.commissions_month)}
          subtitle={`Pendiente: ${formatCurrency(stats.commissions_pending)}`}
          icon={Percent}
          color="bg-violet-50 text-violet-600"
          onClick={() => navigate('/dashboard/comisiones')}
          testId="stat-commissions-month"
        />
      )}
    </div>
  );
}

function AlertsCard({ alerts, navigate }) {
  if (!alerts || alerts.length === 0) {
    return (
      <Card className="border border-emerald-200 bg-emerald-50/40" data-testid="alerts-card-empty">
        <CardContent className="p-5 flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-emerald-100 flex items-center justify-center">
            <BellRing className="w-4 h-4 text-emerald-600" />
          </div>
          <div>
            <p className="text-sm font-semibold text-emerald-800">Todo en orden</p>
            <p className="text-xs text-emerald-700">No hay alertas activas en tu clínica</p>
          </div>
        </CardContent>
      </Card>
    );
  }
  return (
    <Card className="border border-slate-200" data-testid="alerts-card">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold text-slate-700 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-500" /> Alertas y notificaciones
          <Badge variant="outline" className="ml-1 text-xs bg-amber-50 text-amber-700 border-amber-200">{alerts.length}</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {alerts.map((a, i) => {
            const cfg = ALERT_ICONS[a.type] || ALERT_ICONS.low_stock;
            const Icon = cfg.icon;
            return (
              <button
                key={i}
                className={`w-full flex items-center gap-3 p-2.5 rounded-lg border ${cfg.border} ${cfg.bg} hover:brightness-95 transition text-left`}
                onClick={() => a.link && navigate(a.link)}
                data-testid={`alert-${a.type}`}
              >
                <div className={`w-8 h-8 rounded-md bg-white/70 flex items-center justify-center shrink-0`}>
                  <Icon className={`w-4 h-4 ${cfg.text}`} />
                </div>
                <p className={`text-sm flex-1 ${cfg.text}`}>{a.message}</p>
                <ChevronRight className={`w-4 h-4 ${cfg.text} opacity-60`} />
              </button>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}

function IncomeChartCard({ income_chart }) {
  if (!income_chart || income_chart.length === 0) return null;
  const data = income_chart.map(p => ({ ...p, label: formatChartDate(p.date) }));
  return (
    <Card className="border border-slate-200" data-testid="income-chart-card">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold text-slate-700 flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-emerald-500" /> Ingresos del mes
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div style={{ width: '100%', height: 220 }}>
          <ResponsiveContainer>
            <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="label" tick={{ fontSize: 11 }} stroke="#94a3b8" />
              <YAxis tick={{ fontSize: 11 }} stroke="#94a3b8" tickFormatter={(v) => `Q${v >= 1000 ? `${(v / 1000).toFixed(1)}k` : v}`} />
              <Tooltip
                formatter={(v) => [formatCurrency(v), 'Ingresos']}
                labelFormatter={(l) => `Día ${l}`}
                contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }}
              />
              <Line type="monotone" dataKey="income" stroke="#0d9488" strokeWidth={2} dot={{ r: 2 }} activeDot={{ r: 4 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

function MyCommissionsCard({ data, navigate }) {
  const c = data.my_commissions_month;
  if (!c) return null;
  return (
    <Card className="border border-violet-200 bg-gradient-to-br from-violet-50 to-white" data-testid="my-commissions-card">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold text-slate-700 flex items-center gap-2">
          <Percent className="w-4 h-4 text-violet-500" /> Mis comisiones del mes
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-3xl font-bold text-violet-900">{formatCurrency(c.earned)}</p>
        <div className="mt-3 flex gap-4 text-xs">
          <div>
            <span className="text-slate-500">Pendiente: </span>
            <span className="font-semibold text-amber-600">{formatCurrency(c.pending)}</span>
          </div>
          <div>
            <span className="text-slate-500">Pagado: </span>
            <span className="font-semibold text-emerald-600">{formatCurrency(c.paid)}</span>
          </div>
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="mt-3 -ml-2 text-xs text-violet-700 hover:bg-violet-100"
          onClick={() => navigate('/dashboard/comisiones')}
          data-testid="my-commissions-detail-btn"
        >
          Ver detalle <ChevronRight className="w-3.5 h-3.5 ml-0.5" />
        </Button>
      </CardContent>
    </Card>
  );
}

function CashSessionCard({ data, navigate }) {
  const open = data.admin_stats?.open_cash_sessions ?? 0;
  return (
    <Card className="border border-slate-200" data-testid="cash-session-card">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-semibold text-slate-700 flex items-center gap-2">
          <Wallet className="w-4 h-4 text-emerald-500" /> Caja
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-2xl font-bold text-slate-900">{open}</p>
        <p className="text-xs text-slate-500 mt-0.5">{open === 0 ? 'Sin sesiones abiertas' : open === 1 ? 'Sesión abierta' : 'Sesiones abiertas'}</p>
        <Button size="sm" variant="outline" className="mt-3 text-xs" onClick={() => navigate('/dashboard/ventas')} data-testid="cash-session-go-btn">
          {open === 0 ? 'Abrir caja' : 'Ir a ventas'} <ChevronRight className="w-3.5 h-3.5 ml-0.5" />
        </Button>
      </CardContent>
    </Card>
  );
}

export default function ClinicDashboardPage() {
  const { getAuthHeaders } = useAuth();
  const navigate = useNavigate();
  const headers = getAuthHeaders();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activityFilter, setActivityFilter] = useState('all');

  const fetchDashboard = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/clinic/dashboard`, { headers });
      setData(res.data);
    } catch (err) {
      console.error('Dashboard error:', err);
    } finally {
      setLoading(false);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { fetchDashboard(); }, [fetchDashboard]);

  // Auto-refresh every 60s
  useEffect(() => {
    const interval = setInterval(fetchDashboard, 60000);
    return () => clearInterval(interval);
  }, [fetchDashboard]);

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center h-[80vh]">
        <div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const role = data?.role || 'staff';
  const features = data?.features || [];
  const isAdmin = role === 'clinic_admin' || role === 'cashier';
  const isFrontDesk = role === 'assistant' || role === 'receptionist';
  const isDoctor = role === 'doctor';
  const showFinancialChart = isAdmin && features.includes('financial_reports') && (data?.income_chart || []).length > 0;
  const nextApt = data?.next_appointment;
  const activities = (data?.activity || []).filter(a => activityFilter === 'all' || a.type === activityFilter);

  return (
    <div className="p-6 lg:p-8" data-testid="clinic-dashboard">
      {/* Global announcements banner (super admin → all clinics) */}
      <AnnouncementsBanner />

      {/* Greeting */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            Hola, {data?.current_member?.first_name || 'Doctor'}
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {new Date().toLocaleDateString('es-GT', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
          </p>
        </div>
        <Badge variant="outline" className="capitalize text-xs" data-testid="role-badge">
          {role.replace('_', ' ')}
        </Badge>
      </div>

      {/* Top Stats: agenda-related (always visible) */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard
          label="Citas hoy"
          value={data?.today_count || 0}
          subtitle={`${data?.pending_today || 0} pendientes`}
          icon={CalendarDays}
          color="bg-blue-50 text-blue-600"
          testId="stat-today-appts"
        />
        {!isDoctor && (
          <StatCard
            label="Pacientes nuevos"
            value={data?.new_patients_month || 0}
            subtitle="Este mes"
            icon={Users}
            color="bg-purple-50 text-purple-600"
            testId="stat-new-patients"
          />
        )}
        <StatCard
          label="Recetas emitidas"
          value={data?.rx_issued_month || 0}
          subtitle="Este mes"
          icon={Pill}
          color="bg-teal-50 text-teal-600"
          testId="stat-rx-month"
        />
        {nextApt ? (
          <Card className="border border-slate-200 shadow-sm hover:shadow-md transition-shadow cursor-pointer" onClick={() => navigate('/dashboard/agenda')} data-testid="next-apt-card">
            <CardContent className="p-5">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Próxima cita</p>
                  <p className="text-sm font-bold text-slate-900 mt-1 truncate max-w-[150px]">{nextApt.patient_name}</p>
                  <p className="text-xs text-slate-500 mt-0.5">{formatTime(nextApt.starts_at)}</p>
                  {nextApt.reason && <p className="text-xs text-slate-400 truncate max-w-[150px]">{nextApt.reason}</p>}
                </div>
                <div className="w-10 h-10 rounded-lg flex items-center justify-center bg-amber-50 text-amber-600">
                  <Clock className="w-5 h-5" />
                </div>
              </div>
            </CardContent>
          </Card>
        ) : (
          <StatCard label="Próxima cita" value="—" subtitle="Sin citas próximas" icon={Clock} color="bg-slate-50 text-slate-400" testId="stat-no-next-apt" />
        )}
      </div>

      {/* Admin stats row (clinic_admin / cashier full view) */}
      {isAdmin && <AdminStatsRow data={data} navigate={navigate} />}

      {/* Front-desk simplified row: agenda already up top + cash session card */}
      {isFrontDesk && features.includes('sales') && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <CashSessionCard data={data} navigate={navigate} />
        </div>
      )}

      {/* Doctor: my commissions card if applicable */}
      {isDoctor && data?.my_commissions_month && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
          <MyCommissionsCard data={data} navigate={navigate} />
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column: agenda + chart + activity */}
        <div className="lg:col-span-2 space-y-6">
          {/* Today's appointments */}
          <Card className="border border-slate-200" data-testid="today-agenda">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                  <CalendarDays className="w-4 h-4 text-teal-500" /> Agenda del día {isDoctor && <Badge variant="outline" className="text-xs">Mis citas</Badge>}
                </CardTitle>
                <Button variant="outline" size="sm" className="text-xs" onClick={() => navigate('/dashboard/agenda')} data-testid="go-to-agenda-btn">
                  Ver completa <ArrowRight className="w-3.5 h-3.5 ml-1" />
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {(!data?.today_appointments || data.today_appointments.length === 0) ? (
                <div className="text-center py-10">
                  <CalendarDays className="w-10 h-10 text-slate-300 mx-auto mb-2" />
                  <p className="text-sm text-slate-500">No hay citas para hoy</p>
                  <Button size="sm" className="mt-3 bg-teal-600 hover:bg-teal-700" onClick={() => navigate('/dashboard/agenda')}>
                    <CalendarPlus className="w-3.5 h-3.5 mr-1" /> Agendar cita
                  </Button>
                </div>
              ) : (
                <div className="space-y-1">
                  {data.today_appointments.map(apt => {
                    const cfg = STATUS_CONFIG[apt.status] || STATUS_CONFIG.scheduled;
                    return (
                      <div key={apt.id} className="flex items-center gap-3 p-2.5 rounded-lg hover:bg-slate-50 transition-colors group" data-testid={`today-apt-${apt.id}`}>
                        <div className="flex items-center gap-2 min-w-[75px]">
                          <div className={`w-2 h-2 rounded-full ${cfg.dot}`} />
                          <span className="text-sm font-medium text-slate-700 tabular-nums">{formatTime(apt.starts_at)}</span>
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-slate-900 truncate">{apt.patient_name}</p>
                          <p className="text-xs text-slate-400 truncate">{apt.reason || 'Sin motivo'} · Dr. {apt.doctor_name}</p>
                        </div>
                        <Badge variant="outline" className={`text-xs shrink-0 ${cfg.color}`}>{cfg.label}</Badge>
                        <div className="opacity-0 group-hover:opacity-100 transition-opacity flex gap-1">
                          {apt.status === 'scheduled' && (
                            <Button variant="ghost" size="sm" className="h-6 text-xs px-2" onClick={() => navigate(`/dashboard/pacientes/${apt.patient_id}/consulta?appointment_id=${apt.id}`)}>
                              <Stethoscope className="w-3 h-3 mr-0.5" /> Consulta
                            </Button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Income chart (only for full-admin views with feature) */}
          {showFinancialChart && <IncomeChartCard income_chart={data.income_chart} />}

          {/* Activity log (skip for doctor — too noisy) */}
          {!isDoctor && (
            <Card className="border border-slate-200" data-testid="activity-log">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                    <Activity className="w-4 h-4 text-teal-500" /> Actividad reciente
                  </CardTitle>
                  <Select value={activityFilter} onValueChange={setActivityFilter}>
                    <SelectTrigger className="w-36 text-xs h-7" data-testid="activity-filter">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">Todo</SelectItem>
                      <SelectItem value="appointment">Citas</SelectItem>
                      <SelectItem value="prescription">Recetas</SelectItem>
                      <SelectItem value="patient">Pacientes</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </CardHeader>
              <CardContent>
                {activities.length === 0 ? (
                  <p className="text-sm text-slate-400 text-center py-6">Sin actividad reciente</p>
                ) : (
                  <div className="space-y-1">
                    {activities.map((a, i) => {
                      const ai = ACTIVITY_ICONS[a.type] || ACTIVITY_ICONS.appointment;
                      const AIcon = ai.icon;
                      return (
                        <div key={i} className="flex items-center gap-3 py-2 border-b border-slate-50 last:border-0">
                          <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 ${ai.color}`}>
                            <AIcon className="w-3.5 h-3.5" />
                          </div>
                          <p className="text-sm text-slate-600 flex-1">{a.message}</p>
                          <span className="text-xs text-slate-400 shrink-0">{formatRelative(a.timestamp)}</span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>

        {/* Right column: Alerts (admin) + Quick actions + Recent patients */}
        <div className="space-y-6">
          {/* Alerts — admin/front-desk only */}
          {(isAdmin || isFrontDesk) && <AlertsCard alerts={data?.alerts || []} navigate={navigate} />}

          {/* Quick Actions */}
          <Card className="border border-slate-200">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold text-slate-700">Acciones rápidas</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-2">
              <Button variant="outline" size="sm" className="h-auto py-3 flex-col gap-1.5 text-xs" onClick={() => navigate('/dashboard/agenda')} data-testid="quick-appointment">
                <CalendarPlus className="w-4 h-4 text-blue-500" /> Nueva cita
              </Button>
              <Button variant="outline" size="sm" className="h-auto py-3 flex-col gap-1.5 text-xs" onClick={() => navigate('/dashboard/pacientes')} data-testid="quick-patient">
                <UserPlus className="w-4 h-4 text-purple-500" /> Nuevo paciente
              </Button>
              <Button variant="outline" size="sm" className="h-auto py-3 flex-col gap-1.5 text-xs" onClick={() => navigate('/dashboard/recetas/nueva')} data-testid="quick-prescription">
                <FileText className="w-4 h-4 text-teal-500" /> Nueva receta
              </Button>
              <Button variant="outline" size="sm" className="h-auto py-3 flex-col gap-1.5 text-xs" onClick={() => navigate('/dashboard/laboratorio/nueva')} data-testid="quick-lab">
                <FlaskConical className="w-4 h-4 text-orange-500" /> Orden lab
              </Button>
              {isAdmin && features.includes('sales') && (
                <Button variant="outline" size="sm" className="h-auto py-3 flex-col gap-1.5 text-xs col-span-2" onClick={() => navigate('/dashboard/ventas')} data-testid="quick-sale">
                  <DollarSign className="w-4 h-4 text-emerald-500" /> Nueva venta
                </Button>
              )}
            </CardContent>
          </Card>

          {/* Recent patients */}
          <Card className="border border-slate-200" data-testid="recent-patients">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                  <Users className="w-4 h-4 text-teal-500" /> Pacientes recientes
                </CardTitle>
                <Button variant="ghost" size="sm" className="text-xs" onClick={() => navigate('/dashboard/pacientes')}>
                  Ver todos <ChevronRight className="w-3.5 h-3.5 ml-0.5" />
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {(!data?.recent_patients || data.recent_patients.length === 0) ? (
                <p className="text-sm text-slate-400 text-center py-4">Sin pacientes recientes</p>
              ) : (
                <div className="space-y-1">
                  {data.recent_patients.map(p => (
                    <button
                      key={p.id}
                      className="w-full flex items-center gap-3 p-2 rounded-lg hover:bg-teal-50/50 transition-colors text-left"
                      onClick={() => navigate(`/dashboard/pacientes/${p.id}`)}
                      data-testid={`recent-patient-${p.id}`}
                    >
                      <div className="w-8 h-8 rounded-full bg-teal-100 text-teal-700 flex items-center justify-center text-xs font-bold shrink-0">
                        {(p.first_name?.[0] || '').toUpperCase()}{(p.last_name?.[0] || '').toUpperCase()}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-slate-800 truncate">{p.first_name} {p.last_name}</p>
                        {p.phone && <p className="text-xs text-slate-400">{p.phone}</p>}
                      </div>
                      <ChevronRight className="w-3.5 h-3.5 text-slate-300" />
                    </button>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
