import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../context/AuthContext';
import { useBranch } from '../../context/BranchContext';
import { useFeatures } from '../../context/FeatureContext';
import { supabase } from '../../lib/supabase';
import axios from 'axios';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { toast } from 'sonner';
import { ChevronLeft, ChevronRight, Plus, Search, CalendarDays, Filter } from 'lucide-react';
import { API, STATUS_CONFIG, STATUS_OPTIONS, MONTH_NAMES } from './agenda/constants';
import { getDoctorColor, getWeekDates, timeToMinutes, formatTime } from './agenda/utils';
import WeekView from './agenda/WeekView';
import DayView from './agenda/DayView';
import MonthView from './agenda/MonthView';
import NewAppointmentModal from './agenda/NewAppointmentModal';
import AppointmentDetailModal from './agenda/AppointmentDetailModal';

export default function AgendaPage() {
  const { getAuthHeaders, clinicId } = useAuth();
  const { activeBranch, branches } = useBranch();
  const { hasFeature } = useFeatures();
  const multiBranch = hasFeature('multi_branch');
  const [config, setConfig] = useState(null);
  const [appointments, setAppointments] = useState([]);
  const [viewMode, setViewMode] = useState('week');
  const [currentDate, setCurrentDate] = useState(new Date());
  const [weekStart, setWeekStart] = useState(() => getWeekDates(new Date())[0]);
  const [filterDoctor, setFilterDoctor] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all');
  const [patientSearch, setPatientSearch] = useState('');

  const [showNewApt, setShowNewApt] = useState(false);
  const [showDetail, setShowDetail] = useState(null);
  const [selectedSlot, setSelectedSlot] = useState(null);

  const [draggingApt, setDraggingApt] = useState(null);
  const [dropTarget, setDropTarget] = useState(null);

  const weekDates = getWeekDates(weekStart);
  const headers = getAuthHeaders();

  // Doctor color map
  const doctorMap = {};
  if (config?.doctors) {
    const docMapBase = Object.fromEntries(config.doctors.map(x => [x.id, x]));
    config.doctors.forEach(d => {
      doctorMap[d.id] = { name: `${d.first_name} ${d.last_name}`, ...getDoctorColor(d.id, docMapBase) };
    });
  }

  useEffect(() => {
    axios.get(`${API}/clinic/config`, { headers })
      .then(res => setConfig(res.data))
      .catch(err => console.error('Config error:', err));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchAppointments = useCallback(async () => {
    try {
      let start, end;
      if (viewMode === 'day') {
        start = new Date(currentDate); start.setHours(0, 0, 0, 0);
        end = new Date(start); end.setDate(end.getDate() + 1);
      } else if (viewMode === 'week') {
        if (!weekDates.length) return;
        start = weekDates[0];
        end = new Date(weekDates[5]); end.setDate(end.getDate() + 1);
      } else {
        start = new Date(currentDate.getFullYear(), currentDate.getMonth(), 1);
        end = new Date(currentDate.getFullYear(), currentDate.getMonth() + 1, 1);
      }
      const params = new URLSearchParams({ start_date: start.toISOString(), end_date: end.toISOString() });
      if (filterDoctor !== 'all') params.append('doctor_id', filterDoctor);
      if (filterStatus !== 'all') params.append('status', filterStatus);
      if (patientSearch) params.append('patient_search', patientSearch);
      if (multiBranch && activeBranch?.id) params.append('branch_id', activeBranch.id);
      const res = await axios.get(`${API}/clinic/appointments?${params}`, { headers });
      setAppointments(res.data || []);
    } catch (err) { console.error('Appointments error:', err); }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewMode, weekStart, currentDate, filterDoctor, filterStatus, patientSearch, multiBranch, activeBranch?.id]);

  useEffect(() => { fetchAppointments(); }, [fetchAppointments]);

  // Supabase Realtime
  useEffect(() => {
    if (!clinicId) return;
    const channel = supabase
      .channel('appointments-realtime')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'appointments', filter: `clinic_id=eq.${clinicId}` }, () => {
        fetchAppointments();
      })
      .subscribe();
    return () => { supabase.removeChannel(channel); };
  }, [clinicId, fetchAppointments]);

  const goToday = () => { const now = new Date(); setCurrentDate(now); setWeekStart(getWeekDates(now)[0]); };

  const navigate = (dir) => {
    if (viewMode === 'day') {
      const next = new Date(currentDate); next.setDate(next.getDate() + dir); setCurrentDate(next);
    } else if (viewMode === 'week') {
      const next = new Date(weekStart); next.setDate(next.getDate() + dir * 7); setWeekStart(next);
    } else {
      const next = new Date(currentDate); next.setMonth(next.getMonth() + dir); setCurrentDate(next);
    }
  };

  const switchView = (mode) => {
    setViewMode(mode);
    if (mode === 'day' || mode === 'month') setCurrentDate(new Date());
    else if (mode === 'week') setWeekStart(getWeekDates(new Date())[0]);
  };

  // Drag & drop
  const handleDragStart = (e, apt) => {
    if (apt.status === 'completed' || apt.status === 'cancelled') return;
    setDraggingApt(apt);
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', apt.id);
    e.currentTarget.style.opacity = '0.4';
  };
  const handleDragEnd = (e) => { e.currentTarget.style.opacity = '1'; setDraggingApt(null); setDropTarget(null); };
  const handleDragOver = (e, dayIdx, slotMin) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    const key = `${dayIdx}-${slotMin}`;
    if (dropTarget !== key) setDropTarget(key);
  };
  const handleDragLeave = () => setDropTarget(null);
  const handleDrop = async (e, date, slotMin) => {
    e.preventDefault();
    setDropTarget(null);
    if (!draggingApt) return;
    const h = Math.floor(slotMin / 60); const m = slotMin % 60;
    const newDate = new Date(date); newDate.setHours(h, m, 0, 0);
    const oldDate = new Date(draggingApt.starts_at);
    if (oldDate.getTime() === newDate.getTime()) { setDraggingApt(null); return; }
    try {
      await axios.put(`${API}/clinic/appointments/${draggingApt.id}`, {
        starts_at: newDate.toISOString(), duration_minutes: draggingApt.duration_minutes,
      }, { headers });
      toast.success(`Cita reprogramada a ${formatTime(slotMin)} del ${newDate.toLocaleDateString('es-GT', { weekday: 'short', day: 'numeric', month: 'short' })}`);
      fetchAppointments();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al reprogramar cita');
    }
    setDraggingApt(null);
  };

  if (!config) {
    return <div className="p-8 flex items-center justify-center h-screen"><div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" /></div>;
  }

  const startMin = timeToMinutes(config.clinic.schedule_start);
  const endMin = timeToMinutes(config.clinic.schedule_end);
  const slot = config.clinic.slot_duration || 30;
  const slots = [];
  for (let m = startMin; m < endMin; m += slot) slots.push(m);

  const handleSlotClick = (date, slotMinutes) => {
    const dt = new Date(date); dt.setHours(Math.floor(slotMinutes / 60), slotMinutes % 60, 0, 0);
    setSelectedSlot(dt);
    setShowNewApt(true);
  };

  const getNavLabel = () => {
    if (viewMode === 'day') return currentDate.toLocaleDateString('es-GT', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
    if (viewMode === 'week') return `${weekDates[0].toLocaleDateString('es-GT', { month: 'short', day: 'numeric' })} - ${weekDates[5].toLocaleDateString('es-GT', { month: 'short', day: 'numeric', year: 'numeric' })}`;
    return `${MONTH_NAMES[currentDate.getMonth()]} ${currentDate.getFullYear()}`;
  };

  return (
    <div className="h-screen flex flex-col" data-testid="agenda-page">
      <div className="bg-white border-b border-slate-200 px-6 py-3 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <CalendarDays className="w-5 h-5 text-teal-600" strokeWidth={1.5} />
          <h1 className="text-lg font-bold text-slate-900">Agenda</h1>
          <div className="flex items-center bg-slate-100 rounded-md p-0.5 ml-2">
            {['day', 'week', 'month'].map(m => (
              <button
                key={m}
                onClick={() => switchView(m)}
                className={`px-3 py-1 text-xs font-medium rounded transition-all ${viewMode === m ? 'bg-white text-teal-700 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
                data-testid={`view-${m}-btn`}
              >
                {m === 'day' ? 'Día' : m === 'week' ? 'Semana' : 'Mes'}
              </button>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => navigate(-1)} data-testid="prev-btn"><ChevronLeft className="w-4 h-4" /></Button>
          <Button variant="outline" size="sm" onClick={goToday} data-testid="today-btn">Hoy</Button>
          <span className="text-sm font-medium text-slate-700 min-w-[200px] text-center capitalize">{getNavLabel()}</span>
          <Button variant="outline" size="sm" onClick={() => navigate(1)} data-testid="next-btn"><ChevronRight className="w-4 h-4" /></Button>
        </div>
        <Button className="bg-teal-600 hover:bg-teal-700 text-white" size="sm" onClick={() => { setSelectedSlot(new Date()); setShowNewApt(true); }} data-testid="new-apt-btn">
          <Plus className="w-4 h-4 mr-1" /> Nueva cita
        </Button>
      </div>

      <div className="bg-white border-b border-slate-100 px-6 py-2 flex items-center gap-3 shrink-0">
        <Filter className="w-4 h-4 text-slate-400" />
        <Select value={filterDoctor} onValueChange={setFilterDoctor}>
          <SelectTrigger className="w-[180px] h-8 text-xs" data-testid="filter-doctor"><SelectValue placeholder="Todos los médicos" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todos los médicos</SelectItem>
            {(config.doctors || []).map(d => <SelectItem key={d.id} value={d.id}>{d.first_name} {d.last_name}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={filterStatus} onValueChange={setFilterStatus}>
          <SelectTrigger className="w-[160px] h-8 text-xs" data-testid="filter-status"><SelectValue placeholder="Todos los estados" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todos los estados</SelectItem>
            {STATUS_OPTIONS.map(s => <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>)}
          </SelectContent>
        </Select>
        <div className="relative">
          <Search className="w-3.5 h-3.5 absolute left-2 top-1/2 -translate-y-1/2 text-slate-400" />
          <Input className="h-8 text-xs pl-7 w-[180px]" placeholder="Buscar paciente..." value={patientSearch} onChange={e => setPatientSearch(e.target.value)} data-testid="filter-patient-search" />
        </div>
      </div>

      {Object.keys(doctorMap).length > 0 && (
        <div className="bg-white border-b border-slate-100 px-6 py-1.5 flex items-center gap-4 shrink-0">
          {Object.entries(doctorMap).map(([id, d]) => (
            <div key={id} className="flex items-center gap-1.5">
              <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: d.accent }} />
              <span className="text-[11px] font-medium text-slate-600">{d.name}</span>
            </div>
          ))}
          <div className="flex items-center gap-3 ml-auto text-[10px] text-slate-400">
            {STATUS_OPTIONS.map(s => {
              const cfg = STATUS_CONFIG[s.value];
              return (
                <div key={s.value} className="flex items-center gap-1">
                  <div className={`w-2 h-2 rounded-full ${cfg.dot}`} />
                  <span>{s.label}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {viewMode === 'week' && (
        <WeekView
          weekDates={weekDates} slots={slots} slot={slot} appointments={appointments} doctorMap={doctorMap}
          dropTarget={dropTarget} onSlotClick={handleSlotClick}
          onDragStart={handleDragStart} onDragEnd={handleDragEnd} onDragOver={handleDragOver} onDragLeave={handleDragLeave}
          onDrop={handleDrop} onAptClick={apt => setShowDetail(apt)}
        />
      )}

      {viewMode === 'day' && (
        <DayView
          date={currentDate} slots={slots} slot={slot} appointments={appointments} doctorMap={doctorMap}
          dropTarget={dropTarget} onSlotClick={handleSlotClick}
          onDragStart={handleDragStart} onDragEnd={handleDragEnd}
          onDragOver={(e, slotMin) => handleDragOver(e, 0, slotMin)} onDragLeave={handleDragLeave}
          onDrop={(e, slotMin) => handleDrop(e, currentDate, slotMin)}
          onAptClick={apt => setShowDetail(apt)}
        />
      )}

      {viewMode === 'month' && (
        <MonthView
          currentDate={currentDate} appointments={appointments} doctorMap={doctorMap}
          onDayClick={(date) => { setCurrentDate(date); setViewMode('day'); }}
          onAptClick={apt => setShowDetail(apt)}
        />
      )}

      {showNewApt && (
        <NewAppointmentModal
          config={config} initialDate={selectedSlot} headers={headers}
          branches={branches} activeBranch={activeBranch} multiBranch={multiBranch}
          onClose={() => setShowNewApt(false)}
          onCreated={() => { setShowNewApt(false); fetchAppointments(); }}
        />
      )}

      {showDetail && (
        <AppointmentDetailModal
          appointment={showDetail} config={config} doctorMap={doctorMap} headers={headers}
          onClose={() => setShowDetail(null)}
          onUpdated={() => { setShowDetail(null); fetchAppointments(); }}
        />
      )}
    </div>
  );
}
