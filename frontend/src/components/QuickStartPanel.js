import { useState, useEffect, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import axios from 'axios';
import { Card, CardContent } from './ui/card';
import { Button } from './ui/button';
import { toast } from 'sonner';
import {
  Rocket, CheckCircle2, Circle, ArrowRight, X, Loader2,
  Building2, Users, Shield, UserPlus, CalendarPlus, Pill, FlaskConical,
  Package, ShoppingCart, Receipt, Wallet, Percent, TrendingUp,
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Step catalog. `feature` (optional) gates a step behind an active clinic feature.
const STEPS = [
  { key: 'clinic_config', title: 'Configura tu clínica', desc: 'Datos, logo y horario de atención', route: '/dashboard/configuracion', icon: Building2 },
  { key: 'team', title: 'Agrega a tu equipo', desc: 'Invita médicos y personal', route: '/dashboard/configuracion?tab=members', icon: Users },
  { key: 'roles', title: 'Define roles y permisos', desc: 'Controla el acceso por módulo', route: '/dashboard/configuracion?tab=roles', icon: Shield },
  { key: 'patients', title: 'Registra tus pacientes', desc: 'Crea o importa tu base de pacientes', route: '/dashboard/pacientes', icon: UserPlus },
  { key: 'agenda', title: 'Agenda tu primera cita', desc: 'Programa una cita en la agenda', route: '/dashboard/agenda', icon: CalendarPlus },
  { key: 'prescriptions', title: 'Emite una receta', desc: 'Crea una receta médica', route: '/dashboard/recetas/nueva', icon: Pill },
  { key: 'lab_orders', title: 'Crea una orden de laboratorio', desc: 'Solicita estudios de laboratorio', route: '/dashboard/laboratorio/nueva', icon: FlaskConical },
  { key: 'inventory', title: 'Configura tu inventario', desc: 'Productos y existencias', route: '/dashboard/inventario', icon: Package, feature: 'inventory' },
  { key: 'sales', title: 'Abre caja y registra una venta', desc: 'Punto de venta (POS)', route: '/dashboard/ventas', icon: ShoppingCart, feature: 'sales' },
  { key: 'accounts_receivable', title: 'Revisa cuentas por cobrar', desc: 'Saldos pendientes de pacientes', route: '/dashboard/cuentas', icon: Receipt, feature: 'accounts_receivable' },
  { key: 'expenses', title: 'Registra gastos', desc: 'Control de egresos de la clínica', route: '/dashboard/gastos', icon: Wallet, feature: 'expenses' },
  { key: 'commissions', title: 'Configura comisiones', desc: 'Reglas de comisión por médico', route: '/dashboard/comisiones', icon: Percent, feature: 'commissions' },
  { key: 'reports', title: 'Consulta reportes financieros', desc: 'Ingresos, gastos y utilidad', route: '/dashboard/reportes', icon: TrendingUp, feature: 'financial_reports' },
  { key: 'branches', title: 'Registra tus sucursales', desc: 'Gestión multi-sucursal', route: '/dashboard/sucursales', icon: Building2, feature: 'multi_branch' },
];

export default function QuickStartPanel({ features = [] }) {
  const navigate = useNavigate();
  const { getAuthHeaders } = useAuth();
  const [loading, setLoading] = useState(true);
  const [dismissed, setDismissed] = useState(false);
  const [completed, setCompleted] = useState([]);
  const [saving, setSaving] = useState(false);

  const headers = getAuthHeaders();

  const visibleSteps = useMemo(
    () => STEPS.filter(s => !s.feature || features.includes(s.feature)),
    [features],
  );

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await axios.get(`${API}/clinic/quick-start`, { headers });
        if (!alive) return;
        setCompleted(res.data?.completed || []);
        setDismissed(!!res.data?.dismissed);
      } catch {
        if (alive) setDismissed(true); // fail closed — don't show a broken panel
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const persist = useCallback(async (payload, optimistic, rollback) => {
    optimistic();
    setSaving(true);
    try {
      await axios.put(`${API}/clinic/quick-start`, payload, { headers });
    } catch {
      rollback();
      toast.error('No se pudo guardar el cambio');
    } finally {
      setSaving(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggleStep = (key) => {
    const isDone = completed.includes(key);
    const next = isDone ? completed.filter(k => k !== key) : [...completed, key];
    persist({ completed: next }, () => setCompleted(next), () => setCompleted(completed));
  };

  const handleDismiss = () => {
    persist({ dismissed: true }, () => setDismissed(true), () => setDismissed(false));
    toast.success('Inicio rápido retirado. Puedes volver a mostrarlo desde Configuración › Datos.');
  };

  if (loading || dismissed || visibleSteps.length === 0) return null;

  const doneCount = visibleSteps.filter(s => completed.includes(s.key)).length;
  const total = visibleSteps.length;
  const pct = Math.round((doneCount / total) * 100);
  const allDone = doneCount === total;

  const go = (route) => navigate(route);

  return (
    <Card className="border border-teal-200 shadow-sm mb-6 overflow-hidden" data-testid="quick-start-panel">
      <div className="bg-gradient-to-r from-teal-600 to-teal-500 px-5 py-4 text-white">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-white/15 flex items-center justify-center shrink-0">
              <Rocket className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold leading-tight">Inicio rápido</h2>
              <p className="text-xs text-teal-50/90 mt-0.5">Pon en orden tu clínica paso a paso</p>
            </div>
          </div>
          <div className="text-right">
            <p className="text-sm font-semibold tabular-nums" data-testid="quick-start-progress-text">
              {doneCount} de {total} completados
            </p>
            <div className="w-32 h-2 rounded-full bg-white/25 mt-1.5 overflow-hidden">
              <div
                className="h-full bg-white rounded-full transition-all duration-500"
                style={{ width: `${pct}%` }}
                data-testid="quick-start-progress-bar"
              />
            </div>
          </div>
        </div>
      </div>

      <CardContent className="p-4">
        {allDone && (
          <div className="mb-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 rounded-lg border border-emerald-200 bg-emerald-50 p-3" data-testid="quick-start-complete-banner">
            <div className="flex items-center gap-2 text-emerald-800">
              <CheckCircle2 className="w-5 h-5" />
              <span className="text-sm font-semibold">¡Completaste todos los pasos! Tu clínica está lista.</span>
            </div>
            <Button
              size="sm"
              className="bg-emerald-600 hover:bg-emerald-700 shrink-0"
              onClick={handleDismiss}
              disabled={saving}
              data-testid="quick-start-dismiss-btn"
            >
              {saving ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <X className="w-4 h-4 mr-1.5" />}
              Retirar inicio rápido
            </Button>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          {visibleSteps.map((step) => {
            const done = completed.includes(step.key);
            const Icon = step.icon;
            return (
              <div
                key={step.key}
                className={`flex items-center gap-3 p-3 rounded-lg border transition-colors ${done ? 'border-emerald-200 bg-emerald-50/50' : 'border-slate-200 hover:bg-slate-50'}`}
                data-testid={`quick-start-step-${step.key}`}
              >
                <button
                  type="button"
                  onClick={() => toggleStep(step.key)}
                  disabled={saving}
                  className="shrink-0"
                  title={done ? 'Marcar como pendiente' : 'Marcar como hecho'}
                  data-testid={`quick-start-toggle-${step.key}`}
                >
                  {done
                    ? <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                    : <Circle className="w-5 h-5 text-slate-300 hover:text-teal-500" />}
                </button>
                <div className={`w-8 h-8 rounded-md flex items-center justify-center shrink-0 ${done ? 'bg-emerald-100 text-emerald-600' : 'bg-teal-50 text-teal-600'}`}>
                  <Icon className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className={`text-sm font-medium truncate ${done ? 'text-emerald-800 line-through decoration-emerald-300' : 'text-slate-800'}`}>{step.title}</p>
                  <p className="text-xs text-slate-400 truncate">{step.desc}</p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-xs shrink-0 text-teal-700 hover:bg-teal-50"
                  onClick={() => go(step.route)}
                  data-testid={`quick-start-go-${step.key}`}
                >
                  Ir <ArrowRight className="w-3.5 h-3.5 ml-1" />
                </Button>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
