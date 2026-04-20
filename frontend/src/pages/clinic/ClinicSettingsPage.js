import { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import { useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Switch } from '../../components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Separator } from '../../components/ui/separator';
import { toast } from 'sonner';
import { Calendar, Link2, Unlink, RefreshCw, CheckCircle, Settings, User } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function ClinicSettingsPage() {
  const { user, getAuthHeaders } = useAuth();
  const [searchParams] = useSearchParams();
  const headers = getAuthHeaders();

  const [gcalStatus, setGcalStatus] = useState({ connected: false });
  const [calendars, setCalendars] = useState([]);
  const [selectedCalendar, setSelectedCalendar] = useState('primary');
  const [syncActive, setSyncActive] = useState(true);
  const [loading, setLoading] = useState(true);
  const [loadingCalendars, setLoadingCalendars] = useState(false);

  useEffect(() => {
    // Check for callback params
    const success = searchParams.get('gcal_success');
    const error = searchParams.get('gcal_error');
    if (success === 'true') toast.success('Google Calendar conectado exitosamente');
    if (error) toast.error(`Error al conectar Google Calendar: ${error}`);
  }, [searchParams]);

  useEffect(() => {
    fetchStatus();
  }, []);

  const fetchStatus = async () => {
    try {
      const res = await axios.get(`${API}/google-calendar/status`, { headers });
      setGcalStatus(res.data);
      if (res.data.connected) {
        setSelectedCalendar(res.data.calendar_id || 'primary');
        setSyncActive(true);
        fetchCalendars();
      }
    } catch {} finally {
      setLoading(false);
    }
  };

  const fetchCalendars = async () => {
    setLoadingCalendars(true);
    try {
      const res = await axios.get(`${API}/google-calendar/calendars`, { headers });
      setCalendars(res.data || []);
    } catch {
      // May fail if token expired
    } finally {
      setLoadingCalendars(false);
    }
  };

  const connectGoogleCalendar = async () => {
    try {
      const res = await axios.get(`${API}/google-calendar/auth-url`, { headers });
      if (res.data.auth_url) {
        window.location.href = res.data.auth_url;
      }
    } catch (err) {
      toast.error('Error al generar enlace de autenticación');
    }
  };

  const disconnectGoogleCalendar = async () => {
    if (!window.confirm('¿Desconectar Google Calendar? Las citas existentes en Google no se eliminarán.')) return;
    try {
      await axios.delete(`${API}/google-calendar/disconnect`, { headers });
      setGcalStatus({ connected: false });
      setCalendars([]);
      toast.success('Google Calendar desconectado');
    } catch {
      toast.error('Error al desconectar');
    }
  };

  const updateSettings = async (calId, active) => {
    try {
      await axios.put(`${API}/google-calendar/settings`, {
        calendar_id: calId,
        is_active: active,
      }, { headers });
      setSelectedCalendar(calId);
      setSyncActive(active);
      toast.success('Configuración actualizada');
    } catch {
      toast.error('Error al actualizar');
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-96">
        <div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="p-6 lg:p-8 max-w-3xl" data-testid="clinic-settings-page">
      <h1 className="text-2xl font-bold text-slate-900 mb-1">Configuración</h1>
      <p className="text-sm text-slate-500 mb-6">Mi cuenta e integraciones</p>

      {/* User Info */}
      <Card className="border border-slate-200 mb-4">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold text-slate-700 flex items-center gap-2">
            <User className="w-4 h-4 text-teal-500" /> Mi cuenta
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-slate-600">{user?.email}</p>
        </CardContent>
      </Card>

      {/* Google Calendar Integration */}
      <Card className="border border-slate-200" data-testid="gcal-card">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold text-slate-700 flex items-center gap-2">
            <Calendar className="w-4 h-4 text-teal-500" /> Google Calendar
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-xs text-slate-500">
            Sincroniza tus citas del CRM con Google Calendar. Al crear, modificar o cancelar una cita, se reflejará automáticamente en tu calendario de Google.
          </p>

          {!gcalStatus.connected ? (
            <div className="p-4 border-2 border-dashed border-slate-200 rounded-lg text-center">
              <Calendar className="w-10 h-10 text-slate-300 mx-auto mb-2" />
              <p className="text-sm text-slate-500 mb-3">Google Calendar no está conectado</p>
              <Button className="bg-teal-600 hover:bg-teal-700" onClick={connectGoogleCalendar} data-testid="connect-gcal-btn">
                <Link2 className="w-4 h-4 mr-1.5" /> Conectar Google Calendar
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Connected status */}
              <div className="flex items-center justify-between p-3 bg-emerald-50 rounded-lg border border-emerald-200">
                <div className="flex items-center gap-2">
                  <CheckCircle className="w-4 h-4 text-emerald-600" />
                  <span className="text-sm font-medium text-emerald-700">Conectado</span>
                  {gcalStatus.since && (
                    <span className="text-xs text-emerald-500">
                      desde {new Date(gcalStatus.since).toLocaleDateString('es-GT', { day: '2-digit', month: 'short', year: 'numeric' })}
                    </span>
                  )}
                </div>
                <Button variant="outline" size="sm" className="text-xs text-red-600 border-red-200 hover:bg-red-50" onClick={disconnectGoogleCalendar} data-testid="disconnect-gcal-btn">
                  <Unlink className="w-3.5 h-3.5 mr-1" /> Desconectar
                </Button>
              </div>

              <Separator />

              {/* Sync toggle */}
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-slate-700">Sincronización activa</p>
                  <p className="text-xs text-slate-400">Las nuevas citas se sincronizan automáticamente</p>
                </div>
                <Switch
                  checked={syncActive}
                  onCheckedChange={v => updateSettings(selectedCalendar, v)}
                  data-testid="sync-toggle"
                />
              </div>

              <Separator />

              {/* Calendar selection */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div>
                    <p className="text-sm font-medium text-slate-700">Calendario</p>
                    <p className="text-xs text-slate-400">Selecciona en qué calendario guardar las citas</p>
                  </div>
                  <Button variant="ghost" size="sm" onClick={fetchCalendars} disabled={loadingCalendars} className="text-xs">
                    <RefreshCw className={`w-3.5 h-3.5 mr-1 ${loadingCalendars ? 'animate-spin' : ''}`} /> Actualizar
                  </Button>
                </div>
                {calendars.length > 0 ? (
                  <Select value={selectedCalendar} onValueChange={v => updateSettings(v, syncActive)}>
                    <SelectTrigger className="text-sm" data-testid="calendar-select">
                      <SelectValue placeholder="Seleccionar calendario" />
                    </SelectTrigger>
                    <SelectContent>
                      {calendars.map(c => (
                        <SelectItem key={c.id} value={c.id}>
                          {c.summary} {c.primary && <span className="text-xs text-slate-400">(Principal)</span>}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                ) : (
                  <p className="text-xs text-slate-400">Usando calendario principal. Presiona "Actualizar" para ver todos tus calendarios.</p>
                )}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
