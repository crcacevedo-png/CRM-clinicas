import { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { CalendarDays, Users, Clock, ArrowRight, Activity } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STATUS_CONFIG = {
  scheduled: { label: 'Pendiente', color: 'bg-blue-100 text-blue-700 border-blue-200' },
  confirmed: { label: 'Confirmada', color: 'bg-emerald-100 text-emerald-700 border-emerald-200' },
  in_progress: { label: 'En curso', color: 'bg-amber-100 text-amber-700 border-amber-200' },
  completed: { label: 'Completada', color: 'bg-slate-100 text-slate-500 border-slate-200' },
  cancelled: { label: 'Cancelada', color: 'bg-red-100 text-red-600 border-red-200' },
  no_show: { label: 'No asistió', color: 'bg-orange-100 text-orange-600 border-orange-200' },
};

export default function ClinicDashboardPage() {
  const { getAuthHeaders } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboard();
  }, []);

  const fetchDashboard = async () => {
    try {
      const res = await axios.get(`${API}/clinic/dashboard`, { headers: getAuthHeaders() });
      setData(res.data);
    } catch (err) {
      console.error('Dashboard error:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center h-screen">
        <div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const stats = [
    { label: 'Citas hoy', value: data?.today_count || 0, icon: CalendarDays, accent: 'text-teal-600 bg-teal-50' },
    { label: 'Total pacientes', value: data?.total_patients || 0, icon: Users, accent: 'text-blue-600 bg-blue-50' },
    { label: 'Citas este mes', value: data?.month_appointments || 0, icon: Activity, accent: 'text-violet-600 bg-violet-50' },
  ];

  return (
    <div className="p-8" data-testid="clinic-dashboard">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">
          Hola, {data?.current_member?.first_name || 'Doctor'}
        </h1>
        <p className="text-sm text-slate-500 mt-1">Resumen del día</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-8">
        {stats.map((s) => (
          <Card key={s.label} className="border border-slate-200 shadow-sm">
            <CardContent className="p-5 flex items-center gap-4">
              <div className={`w-11 h-11 rounded-lg flex items-center justify-center ${s.accent}`}>
                <s.icon className="w-5 h-5" strokeWidth={1.5} />
              </div>
              <div>
                <p className="text-2xl font-bold text-slate-900">{s.value}</p>
                <p className="text-xs text-slate-500">{s.label}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-slate-900">Citas de hoy</h2>
        <Button
          variant="outline"
          size="sm"
          onClick={() => navigate('/dashboard/agenda')}
          data-testid="go-to-agenda-btn"
        >
          Ver agenda completa <ArrowRight className="w-4 h-4 ml-1" />
        </Button>
      </div>

      {(!data?.today_appointments || data.today_appointments.length === 0) ? (
        <Card className="border-dashed border-2 border-slate-200">
          <CardContent className="p-12 text-center">
            <CalendarDays className="w-12 h-12 text-slate-300 mx-auto mb-3" strokeWidth={1.5} />
            <p className="text-slate-500">No hay citas programadas para hoy</p>
            <Button
              className="mt-4 bg-teal-600 hover:bg-teal-700"
              onClick={() => navigate('/dashboard/agenda')}
            >
              Agendar cita
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {data.today_appointments.map((apt) => {
            const cfg = STATUS_CONFIG[apt.status] || STATUS_CONFIG.scheduled;
            const time = new Date(apt.starts_at).toLocaleTimeString('es-GT', { hour: '2-digit', minute: '2-digit', hour12: true });
            return (
              <Card key={apt.id} className="border border-slate-200 shadow-sm hover:shadow-md transition-shadow">
                <CardContent className="p-4 flex items-center gap-4">
                  <div className="flex items-center gap-2 min-w-[80px]">
                    <Clock className="w-4 h-4 text-slate-400" strokeWidth={1.5} />
                    <span className="text-sm font-medium text-slate-700">{time}</span>
                  </div>
                  <div className="flex-1">
                    <p className="text-sm font-semibold text-slate-900">{apt.patient_name}</p>
                    <p className="text-xs text-slate-500">{apt.reason || 'Sin motivo'} &middot; Dr. {apt.doctor_name}</p>
                  </div>
                  <Badge variant="outline" className={`text-xs ${cfg.color}`} data-testid={`apt-status-${apt.id}`}>
                    {cfg.label}
                  </Badge>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
