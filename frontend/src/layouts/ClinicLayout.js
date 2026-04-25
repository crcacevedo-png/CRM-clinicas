import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useFeatures } from '../context/FeatureContext';
import { 
  LayoutDashboard, 
  CalendarDays, 
  Users, 
  LogOut,
  ChevronRight,
  Building2,
  Pill,
  FlaskConical,
  Settings,
  Package,
  ShoppingCart,
  Receipt,
  CreditCard,
  BarChart3,
  GitBranch,
  Percent
} from 'lucide-react';
import { Button } from '../components/ui/button';

const allNavItems = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard', end: true },
  { to: '/dashboard/agenda', icon: CalendarDays, label: 'Agenda', feature: 'agenda' },
  { to: '/dashboard/pacientes', icon: Users, label: 'Pacientes', feature: 'patients' },
  { to: '/dashboard/recetas', icon: Pill, label: 'Recetas', feature: 'prescriptions' },
  { to: '/dashboard/laboratorio', icon: FlaskConical, label: 'Laboratorio', feature: 'lab_orders' },
  { to: '/dashboard/inventario', icon: Package, label: 'Inventario', feature: 'inventory' },
  { to: '/dashboard/ventas', icon: ShoppingCart, label: 'Ventas', feature: 'sales' },
  { to: '/dashboard/cuentas', icon: Receipt, label: 'Cuentas por cobrar', feature: 'accounts_receivable' },
  { to: '/dashboard/gastos', icon: CreditCard, label: 'Gastos', feature: 'expenses' },
  { to: '/dashboard/reportes', icon: BarChart3, label: 'Reportes', feature: 'financial_reports' },
  { to: '/dashboard/configuracion', icon: Settings, label: 'Configuración' },
];

export default function ClinicLayout() {
  const { user, logout } = useAuth();
  const { hasFeature } = useFeatures();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const navItems = allNavItems.filter(item => !item.feature || hasFeature(item.feature));

  return (
    <div className="flex min-h-screen bg-[#FAFAFA]">
      <aside className="w-52 flex flex-col fixed h-full" style={{ backgroundColor: '#0F1A2E' }}>
        <div className="p-4 border-b border-white/10">
          <h1 className="text-lg font-bold text-white">ClinicCRM</h1>
          <p className="text-xs text-teal-400">Panel Clínico</p>
        </div>

        <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 text-sm font-medium transition-all rounded-md ${
                  isActive 
                    ? 'text-white bg-teal-500/20 border-l-2 border-teal-400' 
                    : 'text-slate-400 hover:text-white hover:bg-white/5'
                }`
              }
              data-testid={`clinic-nav-${item.label.toLowerCase().replace(/\s/g, '-')}`}
            >
              <item.icon className="w-5 h-5" strokeWidth={1.5} />
              <span>{item.label}</span>
              <ChevronRight className="w-4 h-4 ml-auto opacity-50" strokeWidth={1.5} />
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t border-white/10">
          <div className="mb-3">
            <p className="text-sm font-medium text-white truncate">{user?.email}</p>
            <p className="text-xs text-slate-400">Miembro de clínica</p>
          </div>
          <Button
            variant="ghost"
            className="w-full justify-start text-slate-400 hover:text-white hover:bg-white/10"
            onClick={handleLogout}
            data-testid="clinic-logout-btn"
          >
            <LogOut className="w-4 h-4 mr-2" strokeWidth={1.5} />
            Cerrar sesión
          </Button>
        </div>
      </aside>

      <main className="flex-1 ml-52">
        <Outlet />
      </main>
    </div>
  );
}
