import { Fragment } from 'react';
import { Lock, X } from 'lucide-react';
import { STATUS_CONFIG, DOCTOR_COLORS, DAY_NAMES } from './constants';
import { formatTime, isSameDay, slotBlockInfo, BLOCK_STRIPE } from './utils';

export default function WeekView({
  weekDates, slots, slot, appointments, doctorMap,
  dropTarget, onSlotClick, onDragStart, onDragEnd, onDragOver, onDragLeave, onDrop, onAptClick,
  blocks = [], firstSlotMin, canManageBlocks = false, onDeleteBlock,
}) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const getAptsForSlot = (date, slotMinutes) => appointments.filter(apt => {
    const ad = new Date(apt.starts_at);
    if (!isSameDay(ad, date)) return false;
    const aptMin = ad.getHours() * 60 + ad.getMinutes();
    return aptMin >= slotMinutes && aptMin < slotMinutes + slot;
  });

  return (
    <div className="flex-1 overflow-auto">
      <div className="grid min-w-[900px]" style={{ gridTemplateColumns: '64px repeat(6, 1fr)' }}>
        <div className="sticky top-0 z-10 bg-slate-50 border-b border-r border-slate-200 h-14" />
        {weekDates.map((date, i) => {
          const isT = isSameDay(date, today);
          return (
            <div key={i} className={`sticky top-0 z-10 border-b border-r border-slate-200 h-14 flex flex-col items-center justify-center ${isT ? 'bg-teal-50' : 'bg-slate-50'}`}>
              <span className={`text-xs font-medium ${isT ? 'text-teal-600' : 'text-slate-500'}`}>{DAY_NAMES[i]}</span>
              <span className={`text-lg font-bold ${isT ? 'text-teal-700 bg-teal-200 w-8 h-8 rounded-full flex items-center justify-center' : 'text-slate-800'}`}>
                {date.getDate()}
              </span>
            </div>
          );
        })}

        {slots.map((slotMin) => (
          <Fragment key={`row-${slotMin}`}>
            <div className="border-r border-b border-slate-100 h-16 flex items-start justify-end pr-2 pt-1">
              <span className="text-[10px] font-medium text-slate-400">{formatTime(slotMin)}</span>
            </div>
            {weekDates.map((date, dayIdx) => {
              const aptsInSlot = getAptsForSlot(date, slotMin);
              const isT = isSameDay(date, today);
              const isDragOver = dropTarget === `${dayIdx}-${slotMin}`;
              const blockInfo = slotBlockInfo(blocks, date, slotMin, slot, firstSlotMin);
              return (
                <div
                  key={`s-${slotMin}-${dayIdx}`}
                  className={`border-r border-b border-slate-100 h-16 relative cursor-pointer transition-colors ${isT ? 'bg-teal-50/30' : ''} ${isDragOver ? 'bg-teal-100/60 ring-2 ring-inset ring-teal-400/50' : 'hover:bg-slate-50/80'}`}
                  onClick={() => !aptsInSlot.length && !blockInfo && onSlotClick(date, slotMin)}
                  onDragOver={(e) => onDragOver(e, dayIdx, slotMin)}
                  onDragLeave={onDragLeave}
                  onDrop={(e) => onDrop(e, date, slotMin)}
                  data-testid={`slot-${dayIdx}-${slotMin}`}
                >
                  {blockInfo && (
                    <div className="absolute inset-0 z-0 overflow-hidden" style={BLOCK_STRIPE} title={blockInfo.block.label || 'Agenda bloqueada'} data-testid={`block-slot-${dayIdx}-${slotMin}`}>
                      {blockInfo.showLabel && (
                        <div className="flex items-start justify-between px-1 pt-0.5 gap-0.5">
                          <span className="text-[9px] font-semibold text-slate-500 flex items-center gap-0.5 truncate">
                            <Lock className="w-2.5 h-2.5 shrink-0" />{blockInfo.block.label || (blockInfo.block.scope === 'branch' ? 'Sucursal' : 'Médico')}
                          </span>
                          {canManageBlocks && (
                            <button onClick={(e) => { e.stopPropagation(); onDeleteBlock && onDeleteBlock(blockInfo.block); }} className="text-slate-400 hover:text-red-500 shrink-0" data-testid={`delete-block-${blockInfo.block.id}`}>
                              <X className="w-2.5 h-2.5" />
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                  {aptsInSlot.length > 0 && (
                    <div className="absolute inset-0.5 flex gap-0.5 z-10">
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
                            className={`flex-1 min-w-0 rounded-md border-l-[3px] px-1 py-0.5 overflow-hidden transition-all hover:shadow-md ${drColor.bg} ${drColor.text} ${isDraggable ? 'cursor-grab active:cursor-grabbing' : 'cursor-pointer'}`}
                            style={{ borderLeftColor: drColor.accent }}
                            onClick={(e) => { e.stopPropagation(); onAptClick(apt); }}
                            data-testid={`apt-block-${apt.id}`}
                          >
                            <div className="flex items-center gap-0.5">
                              <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${stCfg.dot}`} />
                              <span className="text-[10px] font-semibold truncate">{apt.patient_name}</span>
                            </div>
                            <p className="text-[9px] opacity-70 truncate">{apt.reason || 'Sin motivo'}</p>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </Fragment>
        ))}
      </div>
    </div>
  );
}
