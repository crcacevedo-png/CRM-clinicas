import { STATUS_CONFIG, DOCTOR_COLORS, DAY_NAMES_FULL_WEEK } from './constants';
import { getMonthDays, isSameDay } from './utils';

export default function MonthView({ currentDate, appointments, doctorMap, onDayClick, onAptClick }) {
  const days = getMonthDays(currentDate.getFullYear(), currentDate.getMonth());
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const getAptsForDay = (date) => appointments.filter(apt => isSameDay(new Date(apt.starts_at), date));

  return (
    <div className="flex-1 overflow-auto p-4" data-testid="month-view">
      <div className="grid grid-cols-7 mb-1">
        {DAY_NAMES_FULL_WEEK.map(d => (
          <div key={d} className="text-center text-xs font-semibold text-slate-500 py-2">{d}</div>
        ))}
      </div>

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
                  const drColor = doctorMap[apt.doctor_id] || DOCTOR_COLORS[0];
                  const stCfg = STATUS_CONFIG[apt.status] || STATUS_CONFIG.scheduled;
                  const time = new Date(apt.starts_at).toLocaleTimeString('es-GT', { hour: '2-digit', minute: '2-digit', hour12: false });
                  return (
                    <div
                      key={apt.id}
                      className={`text-[9px] px-1 py-0.5 rounded truncate border-l-2 ${drColor.bg} ${drColor.text} cursor-pointer hover:shadow-sm`}
                      style={{ borderLeftColor: drColor.accent }}
                      onClick={(e) => { e.stopPropagation(); onAptClick(apt); }}
                      data-testid={`month-apt-${apt.id}`}
                    >
                      <div className={`w-1.5 h-1.5 rounded-full inline-block mr-0.5 ${stCfg.dot}`} />
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
