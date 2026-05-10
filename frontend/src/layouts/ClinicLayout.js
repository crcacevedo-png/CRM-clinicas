import { useEffect, useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import { useFeatures } from '../context/FeatureContext';
import { useBranch } from '../context/BranchContext';
import { 
  LayoutDashboard, CalendarDays, Users, LogOut, ChevronRight,
  Pill, FlaskConical, Settings, Package, ShoppingCart, Receipt,
  CreditCard, BarChart3, GitBranch, MapPin, Percent
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

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
  { to: '/dashboard/comisiones', icon: Percent, label: 'Comisiones', feature: 'commissions' },
  { to: '/dashboard/reportes', icon: BarChart3, label: 'Reportes', feature: 'financial_reports' },
  { to: '/dashboard/sucursales', icon: GitBranch, label: 'Sucursales', feature: 'multi_branch' },
  { to: '/dashboard/configuracion', icon: Settings, label: 'Configuración' },
];

export default function ClinicLayout() {
  const { user, logout, getAuthHeaders } = useAuth();
  const { hasFeature } = useFeatures();
  const { branches, activeBranch, setActiveBranch, hasBranches } = useBranch();
  const navigate = useNavigate();

  const [clinicBrand, setClinicBrand] = useState({ name: '', logo_url: null });
  useEffect(() => {
    if (!user) return;
    let mounted = true;
    axios.get(`${API}/clinic/settings`, { headers: getAuthHeaders() })
      .then(res => { if (mounted) setClinicBrand({ name: res.data?.name || '', logo_url: res.data?.logo_url || null }); })
      .catch(() => {});
    return () => { mounted = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id]);

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const navItems = allNavItems.filter(item => !item.feature || hasFeature(item.feature));

  return (
    <div className="flex min-h-screen bg-[#FAFAFA]">
      <aside className="w-52 flex flex-col fixed h-full" style={{ backgroundColor: '#0F1A2E' }}>
        <div className="p-4 border-b border-white/10" data-testid="clinic-brand">
          {clinicBrand.logo_url ? (
            <div className="flex flex-col items-center gap-1.5">
              <img
                src={clinicBrand.logo_url}
                alt={clinicBrand.name || 'Logo'}
                className="h-14 w-auto max-w-full object-contain"
                data-testid="sidebar-clinic-logo"
              />
              {clinicBrand.name && (
                <p className="text-[11px] text-teal-400 truncate w-full text-center" title={clinicBrand.name}>
                  {clinicBrand.name}
                </p>
              )}
            </div>
          ) : (
            <>
              <h1 className="text-lg font-bold text-white truncate" title={clinicBrand.name || 'ClinicCRM'}>
                {clinicBrand.name || 'ClinicCRM'}
              </h1>
              <p className="text-xs text-teal-400">Panel Clínico</p>
            </>
          )}
        </div>

        {hasBranches && (
          <div className="px-3 pt-3 pb-1">
            <Select value={activeBranch?.id || ''} onValueChange={id => {
              const b = branches.find(br => br.id === id);
              if (b) setActiveBranch(b);
            }}>
              <SelectTrigger className="bg-white/10 border-white/20 text-white text-xs h-8" data-testid="branch-selector">
                <MapPin className="w-3 h-3 mr-1 text-teal-400 shrink-0" />
                <SelectValue placeholder="Sucursal" />
              </SelectTrigger>
              <SelectContent>
                {branches.filter(b => b.is_active).map(b => (
                  <SelectItem key={b.id} value={b.id}>
                    {b.name} {b.is_main ? '(Principal)' : ''}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}

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
