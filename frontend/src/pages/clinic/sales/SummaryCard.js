import { Card, CardContent } from '../../../components/ui/card';

export default function SummaryCard({ label, value, count, color = 'slate', icon: Icon }) {
  const colorMap = {
    teal: 'text-teal-600',
    emerald: 'text-emerald-600',
    blue: 'text-blue-600',
    amber: 'text-amber-600',
    slate: 'text-slate-600',
  };
  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
          <p className="text-xs text-slate-500 font-medium">{label}</p>
          {Icon && <Icon className={`w-4 h-4 ${colorMap[color]}`} />}
        </div>
        <p className={`text-2xl font-bold mt-1 ${colorMap[color]}`}>Q{(value || 0).toFixed(2)}</p>
        {count != null && <p className="text-xs text-slate-400">{count} ventas</p>}
      </CardContent>
    </Card>
  );
}
