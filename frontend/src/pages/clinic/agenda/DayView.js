import { Badge } from '../../../components/ui/badge';
import { GripVertical, Lock, X } from 'lucide-react';
import { STATUS_CONFIG, DOCTOR_COLORS } from './constants';
import { formatTime, isSameDay, slotBlockInfo, BLOCK_STRIPE } from './utils';

export default function DayView({
  date, slots, slot, appointments, doctorMap,
  dropTarget, onSlotClick, onDragStart, onDragEnd, onDragOver, onDragLeave, onDrop, onAptClick,
  blocks = [], firstSlotMin, canManageBlocks = false, onDeleteBlock,
}) {
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const isT = isSameDay(date, today);

  const getAptsForSlot = (slotMin) => appointments.filter(apt => {
    const ad = new Date(apt.starts_at);
    if (!isSameDay(ad, date)) return false;
    const aptMin = ad.getHours() * 60 + ad.getMinutes();
    return aptMin >= slotMin && aptMin < slotMin + slot;
  });

  return (
    <div className="flex-1 overflow-auto" data-testid="day-view">
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

      <div className="grid" style={{ gridTemplateColumns: '80px 1fr' }}>
        {slots.map((slotMin) => {
          const aptsInSlot = getAptsForSlot(slotMin);
          const isDragOver = dropTarget === `0-${slotMin}`;
          const blockInfo = slotBlockInfo(blocks, date, slotMin, slot, firstSlotMin);
          return (
            <div key={slotMin} className="contents">
              <div className="border-r border-b border-slate-100 h-20 flex items-start justify-end pr-3 pt-2">
                <span className="text-xs font-medium text-slate-400">{formatTime(slotMin)}</span>
              </div>
              <div
                className={`border-b border-slate-100 h-20 relative cursor-pointer transition-colors ${isDragOver ? 'bg-teal-100/60 ring-2 ring-inset ring-teal-400/50' : 'hover:bg-slate-50/80'}`}
                onClick={() => !aptsInSlot.length && !blockInfo && onSlotClick(date, slotMin)}
                onDragOver={(e) => onDragOver(e, slotMin)}
                onDragLeave={onDragLeave}
                onDrop={(e) => onDrop(e, slotMin)}
                data-testid={`day-slot-${slotMin}`}
              >
                {blockInfo && (
                  <div className="absolute inset-0 z-0 overflow-hidden" style={BLOCK_STRIPE} title={blockInfo.block.label || 'Agenda bloqueada'} data-testid={`day-block-slot-${slotMin}`}>
                    {blockInfo.showLabel && (
                      <div className="flex items-start justify-between px-2 pt-1 gap-1">
                        <span className="text-[11px] font-semibold text-slate-500 flex items-center gap-1 truncate">
                          <Lock className="w-3 h-3 shrink-0" />{blockInfo.block.label || (blockInfo.block.scope === 'branch' ? 'Sucursal bloqueada' : 'Médico no disponible')}
                        </span>
                        {canManageBlocks && (
                          <button onClick={(e) => { e.stopPropagation(); onDeleteBlock && onDeleteBlock(blockInfo.block); }} className="text-slate-400 hover:text-red-500 shrink-0" data-testid={`delete-day-block-${blockInfo.block.id}`}>
                            <X className="w-3 h-3" />
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                )}
                {aptsInSlot.length > 0 && (
                  <div className="absolute inset-1 flex gap-1 z-10">
                    {aptsInSlot.map(apt => {
                      const stCfg = STATUS_CONFIG[apt.status] || STATUS_CONFIG.scheduled;
                      const drColor = doctorMap[apt.doctor_id] || DOCTOR_COLORS[0];
                      const isDraggable = apt.status !== 'completed' && apt.status !== 'cancelled';
                      return (
                        <div
                          key={apt.id}
                          draggable={isDraggable}
                          onDragStart={(e) => onDragStart(e, apt)}
                          onDragEnd={onDragEnd}
                          className={`flex-1 min-w-0 rounded-lg border-l-4 px-3 py-1.5 overflow-hidden transition-all hover:shadow-md ${drColor.bg} ${drColor.text} ${isDraggable ? 'cursor-grab active:cursor-grabbing' : 'cursor-pointer'}`}
                          style={{ borderLeftColor: drColor.accent }}
                          onClick={(e) => { e.stopPropagation(); onAptClick(apt); }}
                          data-testid={`day-apt-${apt.id}`}
                        >
                          <div className="flex items-center gap-2">
                            {isDraggable && <GripVertical className="w-3 h-3 shrink-0 opacity-40" />}
                            <div className={`w-2 h-2 rounded-full shrink-0 ${stCfg.dot}`} />
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
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
