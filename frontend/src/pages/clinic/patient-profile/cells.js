import { AlertCircle } from 'lucide-react';
import { VITAL_RANGES } from './constants';

export function InfoRow({ icon: Icon, label, value }) {
  if (!value) return null;
  return (
    <div className="flex items-start gap-3 py-2">
      <Icon className="w-4 h-4 text-slate-400 mt-0.5 flex-shrink-0" />
      <div>
        <p className="text-xs text-slate-500">{label}</p>
        <p className="text-sm text-slate-800 font-medium">{value}</p>
      </div>
    </div>
  );
}

export function StatCard({ label, value, icon: Icon, color }) {
  return (
    <div className="flex items-center gap-3 p-3 rounded-lg bg-white border border-slate-100">
      <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${color}`}>
        <Icon className="w-4 h-4" />
      </div>
      <div>
        <p className="text-xs text-slate-500">{label}</p>
        <p className="text-lg font-bold text-slate-800">{value}</p>
      </div>
    </div>
  );
}

export function VitalBadge({ label, value, unit, rangeKey }) {
  if (!value && value !== 0) return null;
  const range = VITAL_RANGES[rangeKey];
  const outOfRange = range && (value < range.min || value > range.max);
  return (
    <div className={`px-2.5 py-1.5 rounded-md text-center ${outOfRange ? 'bg-red-50 border border-red-200' : 'bg-slate-50 border border-slate-100'}`}>
      <p className="text-xs text-slate-500">{label}</p>
      <p className={`text-sm font-bold ${outOfRange ? 'text-red-600' : 'text-slate-800'}`}>
        {value} <span className="text-xs font-normal">{unit}</span>
      </p>
      {outOfRange && <AlertCircle className="w-3 h-3 text-red-500 mx-auto mt-0.5" />}
    </div>
  );
}
