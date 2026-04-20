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
  UserPlus, FileText, CalendarPlus, ChevronRight, FlaskConical
} from 'lucide-react';

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

function StatCard({ label, value, subtitle, icon: Icon, color }) {
  return (
    <Card className="border border-slate-200 shadow-sm hover:shadow-md transition-shadow">
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">{label}</p>
            <p className="text-3xl font-bold text-slate-900 mt-1">{value}</p>
            {subtitle && <p className="text-xs text-slate-400 mt-0.5">{subtitle}</p>}
          </div>
          <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${color}`}>
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
  }, []);

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

  const nextApt = data?.next_appointment;
  const activities = (data?.activity || []).filter(a => activityFilter === 'all' || a.type === activityFilter);

  return (
    <div className="p-6 lg:p-8" data-testid="clinic-dashboard">
      {/* Greeting */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">
          Hola, {data?.current_member?.first_name || 'Doctor'}
        </h1>
        <p className="text-sm text-slate-500 mt-0.5">
          {new Date().toLocaleDateString('es-GT', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
        </p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard
          label="Citas hoy"
          value={data?.today_count || 0}
          subtitle={`${data?.pending_today || 0} pendientes`}
          icon={CalendarDays}
          color="bg-blue-50 text-blue-600"
        />
        <StatCard
          label="Pacientes nuevos"
          value={data?.new_patients_month || 0}
          subtitle="Este mes"
          icon={Users}
          color="bg-purple-50 text-purple-600"
        />
        <StatCard
          label="Recetas emitidas"
          value={data?.rx_issued_month || 0}
          subtitle="Este mes"
          icon={Pill}
          color="bg-teal-50 text-teal-600"
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
          <StatCard label="Próxima cita" value="—" subtitle="Sin citas próximas" icon={Clock} color="bg-slate-50 text-slate-400" />
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column: Today's agenda */}
        <div className="lg:col-span-2 space-y-6">
          {/* Today's appointments */}
          <Card className="border border-slate-200" data-testid="today-agenda">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm font-semibold text-slate-700 flex items-center gap-2">
                  <CalendarDays className="w-4 h-4 text-teal-500" /> Agenda del día
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
                        {/* Time */}
                        <div className="flex items-center gap-2 min-w-[75px]">
                          <div className={`w-2 h-2 rounded-full ${cfg.dot}`} />
                          <span className="text-sm font-medium text-slate-700 tabular-nums">{formatTime(apt.starts_at)}</span>
                        </div>
                        {/* Info */}
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-slate-900 truncate">{apt.patient_name}</p>
                          <p className="text-xs text-slate-400 truncate">{apt.reason || 'Sin motivo'} · Dr. {apt.doctor_name}</p>
                        </div>
                        {/* Status */}
                        <Badge variant="outline" className={`text-xs shrink-0 ${cfg.color}`}>{cfg.label}</Badge>
                        {/* Quick actions */}
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

          {/* Activity log */}
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
        </div>

        {/* Right column: Recent patients + quick actions */}
        <div className="space-y-6">
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
