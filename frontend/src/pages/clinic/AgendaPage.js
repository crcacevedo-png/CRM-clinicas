import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '../../context/AuthContext';
import { supabase } from '../../lib/supabase';
import axios from 'axios';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../components/ui/dialog';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
import { toast } from 'sonner';
import {
  ChevronLeft, ChevronRight, Plus, Search, Clock, User, X, CalendarDays, Filter, Edit, Ban, GripVertical, Calendar, LayoutGrid
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STATUS_CONFIG = {
  scheduled:   { label: 'Pendiente',   bg: 'bg-blue-500',   light: 'bg-blue-50 border-blue-200 text-blue-700',   dot: 'bg-blue-500' },
  confirmed:   { label: 'Confirmada',  bg: 'bg-emerald-500', light: 'bg-emerald-50 border-emerald-200 text-emerald-700', dot: 'bg-emerald-500' },
  in_progress: { label: 'En curso',    bg: 'bg-amber-500',   light: 'bg-amber-50 border-amber-200 text-amber-700',   dot: 'bg-amber-500' },
  completed:   { label: 'Completada',  bg: 'bg-slate-400',   light: 'bg-slate-50 border-slate-200 text-slate-500',   dot: 'bg-slate-400' },
  cancelled:   { label: 'Cancelada',   bg: 'bg-red-500',     light: 'bg-red-50 border-red-200 text-red-600',     dot: 'bg-red-500' },
  no_show:     { label: 'No asistió',  bg: 'bg-orange-400',  light: 'bg-orange-50 border-orange-200 text-orange-600', dot: 'bg-orange-400' },
};
const STATUS_OPTIONS = Object.entries(STATUS_CONFIG).map(([k, v]) => ({ value: k, label: v.label }));

function getWeekDates(date) {
  const d = new Date(date);
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1);
  const monday = new Date(d.setDate(diff));
  monday.setHours(0, 0, 0, 0);
  return Array.from({ length: 6 }, (_, i) => {
    const dd = new Date(monday);
    dd.setDate(monday.getDate() + i);
    return dd;
  });
}

function timeToMinutes(timeStr) {
  const [h, m] = timeStr.split(':').map(Number);
  return h * 60 + (m || 0);
}

function formatTime(minutes) {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  const ampm = h >= 12 ? 'PM' : 'AM';
  const h12 = h === 0 ? 12 : h > 12 ? h - 12 : h;
  return `${h12}:${String(m).padStart(2, '0')} ${ampm}`;
}

const DAY_NAMES = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb'];
const DAY_FULL = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado'];
const MONTH_NAMES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];
const DAY_NAMES_FULL_WEEK = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'];

function getMonthDays(year, month) {
  const first = new Date(year, month, 1);
  const lastDay = new Date(year, month + 1, 0).getDate();
  let startDow = first.getDay();
  startDow = startDow === 0 ? 6 : startDow - 1;
  const days = [];
  for (let i = 0; i < startDow; i++) {
    const d = new Date(year, month, -startDow + i + 1);
    days.push({ date: d, inMonth: false });
  }
  for (let i = 1; i <= lastDay; i++) {
    days.push({ date: new Date(year, month, i), inMonth: true });
  }
  while (days.length % 7 !== 0) {
    const d = new Date(year, month + 1, days.length - startDow - lastDay + 1);
    days.push({ date: d, inMonth: false });
  }
  return days;
}

export default function AgendaPage() {
  const { getAuthHeaders, clinicId } = useAuth();
  const [config, setConfig] = useState(null);
  const [appointments, setAppointments] = useState([]);
  const [viewMode, setViewMode] = useState('week'); // 'day' | 'week' | 'month'
  const [currentDate, setCurrentDate] = useState(new Date());
  const [weekStart, setWeekStart] = useState(() => {
    const dates = getWeekDates(new Date());
    return dates[0];
  });
  const [loading, setLoading] = useState(true);
  const [filterDoctor, setFilterDoctor] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all');
  const [patientSearch, setPatientSearch] = useState('');

  // Modal states
  const [showNewApt, setShowNewApt] = useState(false);
  const [showDetail, setShowDetail] = useState(null);
  const [selectedSlot, setSelectedSlot] = useState(null);

  // Drag & drop state
  const [draggingApt, setDraggingApt] = useState(null);
  const [dropTarget, setDropTarget] = useState(null);

  const weekDates = getWeekDates(weekStart);
  const headers = getAuthHeaders();

  // Load clinic config
  useEffect(() => {
    axios.get(`${API}/clinic/config`, { headers })
      .then(res => setConfig(res.data))
      .catch(err => console.error('Config error:', err));
  }, []);

  // Load appointments based on current view
  const fetchAppointments = useCallback(async () => {
    setLoading(true);
    try {
      let start, end;
      if (viewMode === 'day') {
        start = new Date(currentDate);
        start.setHours(0, 0, 0, 0);
        end = new Date(start);
        end.setDate(end.getDate() + 1);
      } else if (viewMode === 'week') {
        if (!weekDates.length) return;
        start = weekDates[0];
        end = new Date(weekDates[5]);
        end.setDate(end.getDate() + 1);
      } else {
        start = new Date(currentDate.getFullYear(), currentDate.getMonth(), 1);
        end = new Date(currentDate.getFullYear(), currentDate.getMonth() + 1, 1);
      }
      const params = new URLSearchParams({ start_date: start.toISOString(), end_date: end.toISOString() });
      if (filterDoctor !== 'all') params.append('doctor_id', filterDoctor);
      if (filterStatus !== 'all') params.append('status', filterStatus);
      if (patientSearch) params.append('patient_search', patientSearch);

      const res = await axios.get(`${API}/clinic/appointments?${params}`, { headers });
      setAppointments(res.data || []);
    } catch (err) {
      console.error('Appointments error:', err);
    } finally {
      setLoading(false);
    }
  }, [viewMode, weekStart, currentDate, filterDoctor, filterStatus, patientSearch]);

  useEffect(() => { fetchAppointments(); }, [fetchAppointments]);

  // Supabase Realtime
  useEffect(() => {
    if (!clinicId) return;
    const channel = supabase
      .channel('appointments-realtime')
      .on('postgres_changes', {
        event: '*',
        schema: 'public',
        table: 'appointments',
        filter: `clinic_id=eq.${clinicId}`,
      }, () => {
        fetchAppointments();
      })
      .subscribe();
    return () => { supabase.removeChannel(channel); };
  }, [clinicId, fetchAppointments]);

  const navigateWeek = (dir) => {
    const next = new Date(weekStart);
    next.setDate(next.getDate() + dir * 7);
    setWeekStart(next);
  };

  const goToday = () => {
    const now = new Date();
    setCurrentDate(now);
    setWeekStart(getWeekDates(now)[0]);
  };

  const navigate = (dir) => {
    if (viewMode === 'day') {
      const next = new Date(currentDate);
      next.setDate(next.getDate() + dir);
      setCurrentDate(next);
    } else if (viewMode === 'week') {
      navigateWeek(dir);
    } else {
      const next = new Date(currentDate);
      next.setMonth(next.getMonth() + dir);
      setCurrentDate(next);
    }
  };

  const switchView = (mode) => {
    setViewMode(mode);
    if (mode === 'day') {
      setCurrentDate(new Date());
    } else if (mode === 'week') {
      setWeekStart(getWeekDates(new Date())[0]);
    } else {
      setCurrentDate(new Date());
    }
  };

  // Drag & drop handlers
  const handleDragStart = (e, apt) => {
    if (apt.status === 'completed' || apt.status === 'cancelled') return;
    setDraggingApt(apt);
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', apt.id);
    e.currentTarget.style.opacity = '0.4';
  };

  const handleDragEnd = (e) => {
    e.currentTarget.style.opacity = '1';
    setDraggingApt(null);
    setDropTarget(null);
  };

  const handleDragOver = (e, dayIdx, slotMin) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    const key = `${dayIdx}-${slotMin}`;
    if (dropTarget !== key) setDropTarget(key);
  };

  const handleDragLeave = () => {
    setDropTarget(null);
  };

  const handleDrop = async (e, date, slotMin) => {
    e.preventDefault();
    setDropTarget(null);
    if (!draggingApt) return;

    const h = Math.floor(slotMin / 60);
    const m = slotMin % 60;
    const newDate = new Date(date);
    newDate.setHours(h, m, 0, 0);
    const newStartsAt = newDate.toISOString();

    // Check if same slot — skip
    const oldDate = new Date(draggingApt.starts_at);
    if (oldDate.getFullYear() === newDate.getFullYear() &&
        oldDate.getMonth() === newDate.getMonth() &&
        oldDate.getDate() === newDate.getDate() &&
        oldDate.getHours() === newDate.getHours() &&
        oldDate.getMinutes() === newDate.getMinutes()) {
      setDraggingApt(null);
      return;
    }

    try {
      await axios.put(`${API}/clinic/appointments/${draggingApt.id}`, {
        starts_at: newStartsAt,
        duration_minutes: draggingApt.duration_minutes,
      }, { headers });
      toast.success(`Cita reprogramada a ${formatTime(slotMin)} del ${newDate.toLocaleDateString('es-GT', { weekday: 'short', day: 'numeric', month: 'short' })}`);
      fetchAppointments();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al reprogramar cita');
    }
    setDraggingApt(null);
  };

  if (!config) {
    return (
      <div className="p-8 flex items-center justify-center h-screen">
        <div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const clinic = config.clinic;
  const startMin = timeToMinutes(clinic.schedule_start);
  const endMin = timeToMinutes(clinic.schedule_end);
  const slot = clinic.slot_duration || 30;
  const slots = [];
  for (let m = startMin; m < endMin; m += slot) {
    slots.push(m);
  }

  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const isToday = (d) => d.getFullYear() === today.getFullYear() && d.getMonth() === today.getMonth() && d.getDate() === today.getDate();

  const getAptsForSlot = (date, slotMinutes) => {
    return appointments.filter(apt => {
      const aptDate = new Date(apt.starts_at);
      if (aptDate.getFullYear() !== date.getFullYear() ||
          aptDate.getMonth() !== date.getMonth() ||
          aptDate.getDate() !== date.getDate()) return false;
      const aptMin = aptDate.getHours() * 60 + aptDate.getMinutes();
      return aptMin >= slotMinutes && aptMin < slotMinutes + slot;
    });
  };

  const handleSlotClick = (date, slotMinutes) => {
    const h = Math.floor(slotMinutes / 60);
    const m = slotMinutes % 60;
    const dt = new Date(date);
    dt.setHours(h, m, 0, 0);
    setSelectedSlot(dt);
    setShowNewApt(true);
  };

  const getNavLabel = () => {
    if (viewMode === 'day') {
      return currentDate.toLocaleDateString('es-GT', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
    } else if (viewMode === 'week') {
      return `${weekDates[0].toLocaleDateString('es-GT', { month: 'short', day: 'numeric' })} - ${weekDates[5].toLocaleDateString('es-GT', { month: 'short', day: 'numeric', year: 'numeric' })}`;
    } else {
      return `${MONTH_NAMES[currentDate.getMonth()]} ${currentDate.getFullYear()}`;
    }
  };

  return (
    <div className="h-screen flex flex-col" data-testid="agenda-page">
      {/* Top Bar */}
      <div className="bg-white border-b border-slate-200 px-6 py-3 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <CalendarDays className="w-5 h-5 text-teal-600" strokeWidth={1.5} />
          <h1 className="text-lg font-bold text-slate-900">Agenda</h1>
          {/* View mode toggle */}
          <div className="flex items-center bg-slate-100 rounded-md p-0.5 ml-2">
            <button
              onClick={() => switchView('day')}
              className={`px-3 py-1 text-xs font-medium rounded transition-all ${viewMode === 'day' ? 'bg-white text-teal-700 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
              data-testid="view-day-btn"
            >
              Día
            </button>
            <button
              onClick={() => switchView('week')}
              className={`px-3 py-1 text-xs font-medium rounded transition-all ${viewMode === 'week' ? 'bg-white text-teal-700 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
              data-testid="view-week-btn"
            >
              Semana
            </button>
            <button
              onClick={() => switchView('month')}
              className={`px-3 py-1 text-xs font-medium rounded transition-all ${viewMode === 'month' ? 'bg-white text-teal-700 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
              data-testid="view-month-btn"
            >
              Mes
            </button>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => navigate(-1)} data-testid="prev-btn">
            <ChevronLeft className="w-4 h-4" />
          </Button>
          <Button variant="outline" size="sm" onClick={goToday} data-testid="today-btn">Hoy</Button>
          <span className="text-sm font-medium text-slate-700 min-w-[200px] text-center capitalize">{getNavLabel()}</span>
          <Button variant="outline" size="sm" onClick={() => navigate(1)} data-testid="next-btn">
            <ChevronRight className="w-4 h-4" />
          </Button>
        </div>
        <Button className="bg-teal-600 hover:bg-teal-700 text-white" size="sm" onClick={() => { setSelectedSlot(new Date()); setShowNewApt(true); }} data-testid="new-apt-btn">
          <Plus className="w-4 h-4 mr-1" /> Nueva cita
        </Button>
      </div>

      {/* Filters */}
      <div className="bg-white border-b border-slate-100 px-6 py-2 flex items-center gap-3 shrink-0">
        <Filter className="w-4 h-4 text-slate-400" />
        <Select value={filterDoctor} onValueChange={setFilterDoctor}>
          <SelectTrigger className="w-[180px] h-8 text-xs" data-testid="filter-doctor">
            <SelectValue placeholder="Todos los médicos" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todos los médicos</SelectItem>
            {(config.doctors || []).map(d => (
              <SelectItem key={d.id} value={d.id}>{d.first_name} {d.last_name}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={filterStatus} onValueChange={setFilterStatus}>
          <SelectTrigger className="w-[160px] h-8 text-xs" data-testid="filter-status">
            <SelectValue placeholder="Todos los estados" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todos los estados</SelectItem>
            {STATUS_OPTIONS.map(s => (
              <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <div className="relative">
          <Search className="w-3.5 h-3.5 absolute left-2 top-1/2 -translate-y-1/2 text-slate-400" />
          <Input
            className="h-8 text-xs pl-7 w-[180px]"
            placeholder="Buscar paciente..."
            value={patientSearch}
            onChange={e => setPatientSearch(e.target.value)}
            data-testid="filter-patient-search"
          />
        </div>
      </div>

      {/* Calendar View */}
      {viewMode === 'week' && (
      <div className="flex-1 overflow-auto">
        <div className="grid min-w-[900px]" style={{ gridTemplateColumns: '64px repeat(6, 1fr)' }}>
          {/* Header */}
          <div className="sticky top-0 z-10 bg-slate-50 border-b border-r border-slate-200 h-14" />
          {weekDates.map((date, i) => {
            const isT = isToday(date);
            return (
              <div key={i} className={`sticky top-0 z-10 border-b border-r border-slate-200 h-14 flex flex-col items-center justify-center ${isT ? 'bg-teal-50' : 'bg-slate-50'}`}>
                <span className={`text-xs font-medium ${isT ? 'text-teal-600' : 'text-slate-500'}`}>{DAY_NAMES[i]}</span>
                <span className={`text-lg font-bold ${isT ? 'text-teal-700 bg-teal-200 w-8 h-8 rounded-full flex items-center justify-center' : 'text-slate-800'}`}>
                  {date.getDate()}
                </span>
              </div>
            );
          })}

          {/* Time slots */}
          {slots.map((slotMin) => (
            <>
              <div key={`t-${slotMin}`} className="border-r border-b border-slate-100 h-16 flex items-start justify-end pr-2 pt-1">
                <span className="text-[10px] font-medium text-slate-400">{formatTime(slotMin)}</span>
              </div>
              {weekDates.map((date, dayIdx) => {
                const aptsInSlot = getAptsForSlot(date, slotMin);
                const isT = isToday(date);
                const isDragOver = dropTarget === `${dayIdx}-${slotMin}`;
                return (
                  <div
                    key={`s-${slotMin}-${dayIdx}`}
                    className={`border-r border-b border-slate-100 h-16 relative cursor-pointer transition-colors ${isT ? 'bg-teal-50/30' : ''} ${isDragOver ? 'bg-teal-100/60 ring-2 ring-inset ring-teal-400/50' : 'hover:bg-slate-50/80'}`}
                    onClick={() => !aptsInSlot.length && handleSlotClick(date, slotMin)}
                    onDragOver={(e) => handleDragOver(e, dayIdx, slotMin)}
                    onDragLeave={handleDragLeave}
                    onDrop={(e) => handleDrop(e, date, slotMin)}
                    data-testid={`slot-${dayIdx}-${slotMin}`}
                  >
                    {aptsInSlot.map(apt => {
                      const cfg = STATUS_CONFIG[apt.status] || STATUS_CONFIG.scheduled;
                      const isDraggable = apt.status !== 'completed' && apt.status !== 'cancelled';
                      return (
                        <div
                          key={apt.id}
                          draggable={isDraggable}
                          onDragStart={(e) => handleDragStart(e, apt)}
                          onDragEnd={handleDragEnd}
                          className={`absolute inset-x-0.5 inset-y-0.5 rounded-md border px-1.5 py-0.5 overflow-hidden transition-all hover:shadow-md ${cfg.light} ${isDraggable ? 'cursor-grab active:cursor-grabbing' : 'cursor-pointer'}`}
                          onClick={(e) => { e.stopPropagation(); setShowDetail(apt); }}
                          data-testid={`apt-block-${apt.id}`}
                        >
                          <div className="flex items-center gap-1">
                            {isDraggable && <GripVertical className="w-2.5 h-2.5 shrink-0 opacity-40" />}
                            <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${cfg.dot}`} />
                            <span className="text-[10px] font-semibold truncate">{apt.patient_name}</span>
                          </div>
                          <p className="text-[9px] opacity-75 truncate">{apt.reason || 'Sin motivo'}</p>
                        </div>
                      );
                    })}
                  </div>
                );
              })}
            </>
          ))}
        </div>
      </div>
      )}

      {/* Day View */}
      {viewMode === 'day' && (
        <DayView
          date={currentDate}
          slots={slots}
          slot={slot}
          appointments={appointments}
          isToday={isToday}
          draggingApt={draggingApt}
          dropTarget={dropTarget}
          onSlotClick={handleSlotClick}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
          onDragOver={(e, slotMin) => handleDragOver(e, 0, slotMin)}
          onDragLeave={handleDragLeave}
          onDrop={(e, slotMin) => handleDrop(e, currentDate, slotMin)}
          onAptClick={(apt) => setShowDetail(apt)}
        />
      )}

      {/* Month View */}
      {viewMode === 'month' && (
        <MonthView
          currentDate={currentDate}
          appointments={appointments}
          onDayClick={(date) => { setCurrentDate(date); setViewMode('day'); }}
          onAptClick={(apt) => setShowDetail(apt)}
        />
      )}

      {/* New Appointment Modal */}
      {showNewApt && (
        <NewAppointmentModal
          config={config}
          initialDate={selectedSlot}
          headers={headers}
          onClose={() => setShowNewApt(false)}
          onCreated={() => { setShowNewApt(false); fetchAppointments(); }}
        />
      )}

      {/* Appointment Detail Modal */}
      {showDetail && (
        <AppointmentDetailModal
          appointment={showDetail}
          config={config}
          headers={headers}
          onClose={() => setShowDetail(null)}
          onUpdated={() => { setShowDetail(null); fetchAppointments(); }}
        />
      )}
    </div>
  );
}

// ============ DAY VIEW ============
function DayView({ date, slots, slot, appointments, isToday: isTodayFn, draggingApt, dropTarget, onSlotClick, onDragStart, onDragEnd, onDragOver, onDragLeave, onDrop, onAptClick }) {
  const isT = isTodayFn(date);

  const getAptsForSlot = (slotMin) => {
    return appointments.filter(apt => {
      const ad = new Date(apt.starts_at);
      if (ad.getFullYear() !== date.getFullYear() || ad.getMonth() !== date.getMonth() || ad.getDate() !== date.getDate()) return false;
      const aptMin = ad.getHours() * 60 + ad.getMinutes();
      return aptMin >= slotMin && aptMin < slotMin + slot;
    });
  };

  return (
    <div className="flex-1 overflow-auto" data-testid="day-view">
      {/* Day header */}
      <div className={`sticky top-0 z-10 border-b px-6 py-3 flex items-center gap-3 ${isT ? 'bg-teal-50' : 'bg-slate-50'}`}>
        <span className={`text-2xl font-bold ${isT ? 'text-teal-700 bg-teal-200 w-10 h-10 rounded-full flex items-center justify-center' : 'text-slate-800'}`}>
          {date.getDate()}
        </span>
        <div>
          <p className={`text-sm font-semibold capitalize ${isT ? 'text-teal-700' : 'text-slate-700'}`}>
            {date.toLocaleDateString('es-GT', { weekday: 'long' })}
          </p>
          <p className="text-xs text-slate-500 capitalize">
            {date.toLocaleDateString('es-GT', { month: 'long', year: 'numeric' })}
          </p>
        </div>
        {isT && <Badge className="bg-teal-100 text-teal-700 border-teal-200 text-xs ml-2">Hoy</Badge>}
      </div>

      {/* Time grid - single column */}
      <div className="grid" style={{ gridTemplateColumns: '80px 1fr' }}>
        {slots.map((slotMin) => {
          const aptsInSlot = getAptsForSlot(slotMin);
          const isDragOver = dropTarget === `0-${slotMin}`;
          return (
            <div key={slotMin} className="contents">
              <div className="border-r border-b border-slate-100 h-20 flex items-start justify-end pr-3 pt-2">
                <span className="text-xs font-medium text-slate-400">{formatTime(slotMin)}</span>
              </div>
              <div
                className={`border-b border-slate-100 h-20 relative cursor-pointer transition-colors ${isDragOver ? 'bg-teal-100/60 ring-2 ring-inset ring-teal-400/50' : 'hover:bg-slate-50/80'}`}
                onClick={() => !aptsInSlot.length && onSlotClick(date, slotMin)}
                onDragOver={(e) => onDragOver(e, slotMin)}
                onDragLeave={onDragLeave}
                onDrop={(e) => onDrop(e, slotMin)}
                data-testid={`day-slot-${slotMin}`}
              >
                {aptsInSlot.map(apt => {
                  const cfg = STATUS_CONFIG[apt.status] || STATUS_CONFIG.scheduled;
                  const isDraggable = apt.status !== 'completed' && apt.status !== 'cancelled';
                  return (
                    <div
                      key={apt.id}
                      draggable={isDraggable}
                      onDragStart={(e) => onDragStart(e, apt)}
                      onDragEnd={onDragEnd}
                      className={`absolute left-1 right-4 top-1 bottom-1 rounded-lg border px-3 py-1.5 overflow-hidden transition-all hover:shadow-md ${cfg.light} ${isDraggable ? 'cursor-grab active:cursor-grabbing' : 'cursor-pointer'}`}
                      onClick={(e) => { e.stopPropagation(); onAptClick(apt); }}
                      data-testid={`day-apt-${apt.id}`}
                    >
                      <div className="flex items-center gap-2">
                        {isDraggable && <GripVertical className="w-3 h-3 shrink-0 opacity-40" />}
                        <div className={`w-2 h-2 rounded-full shrink-0 ${cfg.dot}`} />
                        <span className="text-sm font-semibold truncate">{apt.patient_name}</span>
                        <span className="text-xs opacity-60 ml-auto">{apt.duration_minutes} min</span>
                      </div>
                      <div className="flex items-center gap-3 mt-0.5">
                        <span className="text-xs opacity-75">{apt.reason || 'Sin motivo'}</span>
                        <span className="text-xs opacity-50">Dr. {apt.doctor_name}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ============ MONTH VIEW ============
function MonthView({ currentDate, appointments, onDayClick, onAptClick }) {
  const days = getMonthDays(currentDate.getFullYear(), currentDate.getMonth());
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const getAptsForDay = (date) => {
    return appointments.filter(apt => {
      const ad = new Date(apt.starts_at);
      return ad.getFullYear() === date.getFullYear() && ad.getMonth() === date.getMonth() && ad.getDate() === date.getDate();
    });
  };

  const isSameDay = (a, b) => a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();

  return (
    <div className="flex-1 overflow-auto p-4" data-testid="month-view">
      {/* Day headers */}
      <div className="grid grid-cols-7 mb-1">
        {DAY_NAMES_FULL_WEEK.map(d => (
          <div key={d} className="text-center text-xs font-semibold text-slate-500 py-2">{d}</div>
        ))}
      </div>

      {/* Calendar grid */}
      <div className="grid grid-cols-7 border-t border-l border-slate-200">
        {days.map(({ date, inMonth }, idx) => {
          const isT = isSameDay(date, today);
          const dayApts = getAptsForDay(date);
          const maxShow = 3;
          return (
            <div
              key={idx}
              className={`border-r border-b border-slate-200 min-h-[100px] p-1.5 cursor-pointer transition-colors ${!inMonth ? 'bg-slate-50/50' : 'hover:bg-slate-50'} ${isT ? 'bg-teal-50/60' : ''}`}
              onClick={() => onDayClick(date)}
              data-testid={`month-day-${date.getDate()}-${date.getMonth()}`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className={`text-xs font-bold w-6 h-6 flex items-center justify-center rounded-full ${isT ? 'bg-teal-500 text-white' : inMonth ? 'text-slate-700' : 'text-slate-300'}`}>
                  {date.getDate()}
                </span>
                {dayApts.length > maxShow && (
                  <span className="text-[9px] text-slate-400 font-medium">+{dayApts.length - maxShow}</span>
                )}
              </div>
              <div className="space-y-0.5">
                {dayApts.slice(0, maxShow).map(apt => {
                  const cfg = STATUS_CONFIG[apt.status] || STATUS_CONFIG.scheduled;
                  const time = new Date(apt.starts_at).toLocaleTimeString('es-GT', { hour: '2-digit', minute: '2-digit', hour12: false });
                  return (
                    <div
                      key={apt.id}
                      className={`text-[9px] px-1 py-0.5 rounded truncate border ${cfg.light} cursor-pointer hover:shadow-sm`}
                      onClick={(e) => { e.stopPropagation(); onAptClick(apt); }}
                      data-testid={`month-apt-${apt.id}`}
                    >
                      <span className="font-semibold">{time}</span> {apt.patient_name}
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ============ NEW APPOINTMENT MODAL ============
function NewAppointmentModal({ config, initialDate, headers, onClose, onCreated }) {
  const [form, setForm] = useState({
    patient_id: '',
    doctor_id: config.doctors?.[0]?.id || '',
    date: initialDate ? initialDate.toISOString().split('T')[0] : new Date().toISOString().split('T')[0],
    time: initialDate ? `${String(initialDate.getHours()).padStart(2,'0')}:${String(initialDate.getMinutes()).padStart(2,'0')}` : config.clinic.schedule_start?.slice(0, 5) || '08:00',
    duration: config.clinic.slot_duration || 30,
    reason: '',
    notes: '',
  });
  const [patients, setPatients] = useState([]);
  const [patientQuery, setPatientQuery] = useState('');
  const [showPatientDropdown, setShowPatientDropdown] = useState(false);
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [showNewPatient, setShowNewPatient] = useState(false);
  const [newPatient, setNewPatient] = useState({ first_name: '', last_name: '', phone: '' });
  const [saving, setSaving] = useState(false);
  const searchTimeout = useRef(null);

  const searchPatients = (q) => {
    setPatientQuery(q);
    setShowPatientDropdown(true);
    clearTimeout(searchTimeout.current);
    searchTimeout.current = setTimeout(async () => {
      try {
        const res = await axios.get(`${API}/clinic/patients/search?q=${encodeURIComponent(q)}`, { headers });
        setPatients(res.data || []);
      } catch (err) {
        console.error(err);
      }
    }, 300);
  };

  const selectPatient = (p) => {
    setSelectedPatient(p);
    setForm(prev => ({ ...prev, patient_id: p.id }));
    setPatientQuery(`${p.first_name} ${p.last_name}`);
    setShowPatientDropdown(false);
  };

  const createPatientAndSelect = async () => {
    if (!newPatient.first_name || !newPatient.last_name) {
      toast.error('Nombre y apellido son requeridos');
      return;
    }
    try {
      const res = await axios.post(`${API}/clinic/patients`, newPatient, { headers });
      selectPatient(res.data);
      setShowNewPatient(false);
      toast.success('Paciente creado');
    } catch (err) {
      toast.error('Error al crear paciente');
    }
  };

  const handleSubmit = async () => {
    if (!form.patient_id) { toast.error('Selecciona un paciente'); return; }
    if (!form.doctor_id) { toast.error('Selecciona un médico'); return; }
    setSaving(true);
    try {
      const startsAt = new Date(`${form.date}T${form.time}:00`).toISOString();
      await axios.post(`${API}/clinic/appointments`, {
        patient_id: form.patient_id,
        doctor_id: form.doctor_id,
        starts_at: startsAt,
        duration_minutes: parseInt(form.duration),
        reason: form.reason,
        notes: form.notes,
      }, { headers });
      toast.success('Cita creada exitosamente');
      onCreated();
    } catch (err) {
      const msg = err.response?.data?.detail || 'Error al crear cita';
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  };

  // Time options based on clinic schedule
  const startMin = timeToMinutes(config.clinic.schedule_start);
  const endMin = timeToMinutes(config.clinic.schedule_end);
  const slotDur = config.clinic.slot_duration || 30;
  const timeOptions = [];
  for (let m = startMin; m < endMin; m += slotDur) {
    const h = Math.floor(m / 60);
    const mm = m % 60;
    timeOptions.push(`${String(h).padStart(2, '0')}:${String(mm).padStart(2, '0')}`);
  }

  return (
    <Dialog open={true} onOpenChange={onClose}>
      <DialogContent className="max-w-lg" data-testid="new-apt-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Plus className="w-5 h-5 text-teal-600" /> Nueva cita
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Patient search */}
          <div>
            <Label className="text-xs font-medium text-slate-600">Paciente *</Label>
            <div className="relative mt-1">
              <Search className="w-4 h-4 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
              <Input
                className="pl-8"
                placeholder="Buscar paciente por nombre..."
                value={patientQuery}
                onChange={e => searchPatients(e.target.value)}
                onFocus={() => searchPatients(patientQuery)}
                data-testid="patient-search-input"
              />
              {showPatientDropdown && (
                <div className="absolute z-50 top-full left-0 right-0 mt-1 bg-white border border-slate-200 rounded-md shadow-lg max-h-48 overflow-auto">
                  {patients.map(p => (
                    <div
                      key={p.id}
                      className="px-3 py-2 hover:bg-slate-50 cursor-pointer text-sm flex items-center justify-between"
                      onClick={() => selectPatient(p)}
                      data-testid={`patient-option-${p.id}`}
                    >
                      <span className="font-medium">{p.first_name} {p.last_name}</span>
                      {p.phone && <span className="text-xs text-slate-400">{p.phone}</span>}
                    </div>
                  ))}
                  {patients.length === 0 && (
                    <div className="px-3 py-2 text-sm text-slate-500">
                      No se encontraron pacientes
                    </div>
                  )}
                  <div
                    className="px-3 py-2 border-t border-slate-100 text-sm font-medium text-teal-600 cursor-pointer hover:bg-teal-50"
                    onClick={() => { setShowPatientDropdown(false); setShowNewPatient(true); }}
                    data-testid="create-patient-btn"
                  >
                    <Plus className="w-3.5 h-3.5 inline mr-1" /> Crear nuevo paciente
                  </div>
                </div>
              )}
            </div>
            {selectedPatient && (
              <div className="mt-1 flex items-center gap-2">
                <Badge variant="outline" className="bg-teal-50 text-teal-700 border-teal-200 text-xs">
                  <User className="w-3 h-3 mr-1" /> {selectedPatient.first_name} {selectedPatient.last_name}
                </Badge>
                <button onClick={() => { setSelectedPatient(null); setForm(p => ({ ...p, patient_id: '' })); setPatientQuery(''); }} className="text-xs text-slate-400 hover:text-red-500">
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            )}
          </div>

          {/* Quick new patient inline */}
          {showNewPatient && (
            <div className="border border-dashed border-teal-300 rounded-md p-3 bg-teal-50/50 space-y-2">
              <p className="text-xs font-semibold text-teal-700">Nuevo paciente</p>
              <div className="grid grid-cols-2 gap-2">
                <Input placeholder="Nombre *" value={newPatient.first_name} onChange={e => setNewPatient(p => ({ ...p, first_name: e.target.value }))} className="h-8 text-sm" data-testid="new-patient-first-name" />
                <Input placeholder="Apellido *" value={newPatient.last_name} onChange={e => setNewPatient(p => ({ ...p, last_name: e.target.value }))} className="h-8 text-sm" data-testid="new-patient-last-name" />
              </div>
              <Input placeholder="Teléfono" value={newPatient.phone} onChange={e => setNewPatient(p => ({ ...p, phone: e.target.value }))} className="h-8 text-sm" />
              <div className="flex gap-2">
                <Button size="sm" className="bg-teal-600 hover:bg-teal-700 text-xs h-7" onClick={createPatientAndSelect} data-testid="save-new-patient-btn">Guardar</Button>
                <Button size="sm" variant="ghost" className="text-xs h-7" onClick={() => setShowNewPatient(false)}>Cancelar</Button>
              </div>
            </div>
          )}

          {/* Doctor */}
          <div>
            <Label className="text-xs font-medium text-slate-600">Médico *</Label>
            <Select value={form.doctor_id} onValueChange={v => setForm(p => ({ ...p, doctor_id: v }))}>
              <SelectTrigger className="mt-1" data-testid="doctor-select">
                <SelectValue placeholder="Seleccionar médico" />
              </SelectTrigger>
              <SelectContent>
                {(config.doctors || []).map(d => (
                  <SelectItem key={d.id} value={d.id}>{d.first_name} {d.last_name}{d.specialty ? ` - ${d.specialty}` : ''}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Date & Time */}
          <div className="grid grid-cols-3 gap-3">
            <div>
              <Label className="text-xs font-medium text-slate-600">Fecha *</Label>
              <Input type="date" className="mt-1" value={form.date} onChange={e => setForm(p => ({ ...p, date: e.target.value }))} data-testid="apt-date-input" />
            </div>
            <div>
              <Label className="text-xs font-medium text-slate-600">Hora *</Label>
              <Select value={form.time} onValueChange={v => setForm(p => ({ ...p, time: v }))}>
                <SelectTrigger className="mt-1" data-testid="apt-time-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {timeOptions.map(t => (
                    <SelectItem key={t} value={t}>{formatTime(timeToMinutes(t))}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs font-medium text-slate-600">Duración</Label>
              <Select value={String(form.duration)} onValueChange={v => setForm(p => ({ ...p, duration: parseInt(v) }))}>
                <SelectTrigger className="mt-1" data-testid="apt-duration-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="15">15 min</SelectItem>
                  <SelectItem value="20">20 min</SelectItem>
                  <SelectItem value="30">30 min</SelectItem>
                  <SelectItem value="45">45 min</SelectItem>
                  <SelectItem value="60">60 min</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Reason */}
          <div>
            <Label className="text-xs font-medium text-slate-600">Motivo de consulta</Label>
            <Input className="mt-1" placeholder="Ej: Consulta general, control..." value={form.reason} onChange={e => setForm(p => ({ ...p, reason: e.target.value }))} data-testid="apt-reason-input" />
          </div>

          {/* Notes */}
          <div>
            <Label className="text-xs font-medium text-slate-600">Notas</Label>
            <Textarea className="mt-1 text-sm" rows={2} placeholder="Notas adicionales..." value={form.notes} onChange={e => setForm(p => ({ ...p, notes: e.target.value }))} data-testid="apt-notes-input" />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancelar</Button>
          <Button className="bg-teal-600 hover:bg-teal-700" onClick={handleSubmit} disabled={saving} data-testid="save-apt-btn">
            {saving ? 'Guardando...' : 'Agendar cita'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ============ APPOINTMENT DETAIL MODAL ============
function AppointmentDetailModal({ appointment, config, headers, onClose, onUpdated }) {
  const [status, setStatus] = useState(appointment.status);
  const [cancellationReason, setCancellationReason] = useState('');
  const [showEdit, setShowEdit] = useState(false);
  const [editForm, setEditForm] = useState({
    doctor_id: appointment.doctor_id,
    starts_at: appointment.starts_at ? new Date(appointment.starts_at).toISOString().slice(0, 16) : '',
    duration_minutes: appointment.duration_minutes,
    reason: appointment.reason || '',
    notes: appointment.notes || '',
  });
  const [saving, setSaving] = useState(false);

  const cfg = STATUS_CONFIG[appointment.status] || STATUS_CONFIG.scheduled;

  const changeStatus = async (newStatus) => {
    if (newStatus === 'cancelled' && !cancellationReason) {
      toast.error('Ingresa el motivo de cancelación');
      return;
    }
    setSaving(true);
    try {
      await axios.put(`${API}/clinic/appointments/${appointment.id}/status`, {
        status: newStatus,
        cancellation_reason: newStatus === 'cancelled' ? cancellationReason : undefined,
      }, { headers });
      toast.success('Estado actualizado');
      onUpdated();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error');
    } finally {
      setSaving(false);
    }
  };

  const saveEdit = async () => {
    setSaving(true);
    try {
      await axios.put(`${API}/clinic/appointments/${appointment.id}`, {
        doctor_id: editForm.doctor_id,
        starts_at: editForm.starts_at ? new Date(editForm.starts_at).toISOString() : undefined,
        duration_minutes: editForm.duration_minutes,
        reason: editForm.reason,
        notes: editForm.notes,
      }, { headers });
      toast.success('Cita actualizada');
      onUpdated();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al actualizar');
    } finally {
      setSaving(false);
    }
  };

  const time = new Date(appointment.starts_at).toLocaleTimeString('es-GT', { hour: '2-digit', minute: '2-digit', hour12: true });
  const date = new Date(appointment.starts_at).toLocaleDateString('es-GT', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });

  return (
    <Dialog open={true} onOpenChange={onClose}>
      <DialogContent className="max-w-md" data-testid="apt-detail-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-base pr-6">
            Detalle de cita
            <Badge variant="outline" className={`text-xs ${cfg.light}`}>{cfg.label}</Badge>
          </DialogTitle>
        </DialogHeader>

        {!showEdit ? (
          <div className="space-y-4 py-2">
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <p className="text-xs text-slate-500">Paciente</p>
                <p className="font-semibold text-slate-900">{appointment.patient_name}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Médico</p>
                <p className="font-semibold text-slate-900">{appointment.doctor_name}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Fecha</p>
                <p className="font-medium text-slate-700 capitalize">{date}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Hora</p>
                <p className="font-medium text-slate-700">{time} ({appointment.duration_minutes} min)</p>
              </div>
            </div>
            {appointment.reason && (
              <div>
                <p className="text-xs text-slate-500">Motivo</p>
                <p className="text-sm text-slate-800">{appointment.reason}</p>
              </div>
            )}
            {appointment.notes && (
              <div>
                <p className="text-xs text-slate-500">Notas</p>
                <p className="text-sm text-slate-700">{appointment.notes}</p>
              </div>
            )}

            {/* Status actions */}
            {appointment.status !== 'cancelled' && appointment.status !== 'completed' && (
              <div className="border-t border-slate-100 pt-3">
                <p className="text-xs font-medium text-slate-600 mb-2">Cambiar estado:</p>
                <div className="flex flex-wrap gap-2">
                  {appointment.status === 'scheduled' && (
                    <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700 text-xs h-7" onClick={() => changeStatus('confirmed')} disabled={saving} data-testid="confirm-apt-btn">
                      Confirmar
                    </Button>
                  )}
                  {(appointment.status === 'scheduled' || appointment.status === 'confirmed') && (
                    <Button size="sm" className="bg-amber-500 hover:bg-amber-600 text-xs h-7" onClick={() => changeStatus('in_progress')} disabled={saving} data-testid="start-apt-btn">
                      Iniciar consulta
                    </Button>
                  )}
                  {appointment.status === 'in_progress' && (
                    <Button size="sm" className="bg-slate-600 hover:bg-slate-700 text-xs h-7" onClick={() => changeStatus('completed')} disabled={saving} data-testid="complete-apt-btn">
                      Completar
                    </Button>
                  )}
                  <Button size="sm" variant="outline" className="text-xs h-7" onClick={() => changeStatus('no_show')} disabled={saving}>
                    No asistió
                  </Button>
                </div>

                <div className="mt-3">
                  <div className="flex items-center gap-2">
                    <Input
                      className="text-xs h-7 flex-1"
                      placeholder="Motivo de cancelación..."
                      value={cancellationReason}
                      onChange={e => setCancellationReason(e.target.value)}
                      data-testid="cancel-reason-input"
                    />
                    <Button size="sm" variant="destructive" className="text-xs h-7" onClick={() => changeStatus('cancelled')} disabled={saving} data-testid="cancel-apt-btn">
                      <Ban className="w-3 h-3 mr-1" /> Cancelar
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </div>
        ) : (
          /* Edit form */
          <div className="space-y-3 py-2">
            <div>
              <Label className="text-xs">Médico</Label>
              <Select value={editForm.doctor_id} onValueChange={v => setEditForm(p => ({ ...p, doctor_id: v }))}>
                <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {(config.doctors || []).map(d => (
                    <SelectItem key={d.id} value={d.id}>{d.first_name} {d.last_name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <Label className="text-xs">Fecha y hora</Label>
                <Input type="datetime-local" className="mt-1 text-sm" value={editForm.starts_at} onChange={e => setEditForm(p => ({ ...p, starts_at: e.target.value }))} />
              </div>
              <div>
                <Label className="text-xs">Duración</Label>
                <Select value={String(editForm.duration_minutes)} onValueChange={v => setEditForm(p => ({ ...p, duration_minutes: parseInt(v) }))}>
                  <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="15">15 min</SelectItem>
                    <SelectItem value="20">20 min</SelectItem>
                    <SelectItem value="30">30 min</SelectItem>
                    <SelectItem value="45">45 min</SelectItem>
                    <SelectItem value="60">60 min</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div>
              <Label className="text-xs">Motivo</Label>
              <Input className="mt-1 text-sm" value={editForm.reason} onChange={e => setEditForm(p => ({ ...p, reason: e.target.value }))} />
            </div>
            <div>
              <Label className="text-xs">Notas</Label>
              <Textarea className="mt-1 text-sm" rows={2} value={editForm.notes} onChange={e => setEditForm(p => ({ ...p, notes: e.target.value }))} />
            </div>
          </div>
        )}

        <DialogFooter>
          {!showEdit ? (
            <>
              <Button variant="outline" onClick={onClose}>Cerrar</Button>
              {appointment.status !== 'cancelled' && appointment.status !== 'completed' && (
                <Button variant="outline" onClick={() => setShowEdit(true)} data-testid="edit-apt-btn">
                  <Edit className="w-3.5 h-3.5 mr-1" /> Editar
                </Button>
              )}
            </>
          ) : (
            <>
              <Button variant="outline" onClick={() => setShowEdit(false)}>Cancelar</Button>
              <Button className="bg-teal-600 hover:bg-teal-700" onClick={saveEdit} disabled={saving} data-testid="save-edit-apt-btn">
                {saving ? 'Guardando...' : 'Guardar cambios'}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
