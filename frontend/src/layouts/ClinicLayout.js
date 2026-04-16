import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { 
  LayoutDashboard, 
  CalendarDays, 
  Users, 
  LogOut,
  ChevronRight,
  Building2
} from 'lucide-react';
import { Button } from '../components/ui/button';

const navItems = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard', end: true },
  { to: '/dashboard/agenda', icon: CalendarDays, label: 'Agenda' },
  { to: '/dashboard/pacientes', icon: Users, label: 'Pacientes' },
];

export default function ClinicLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <div className="flex min-h-screen bg-[#F8FAFC]">
      <aside className="w-64 flex flex-col fixed h-full" style={{ backgroundColor: '#0F172A' }}>
        <div className="p-4 border-b border-white/10">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-teal-500 flex items-center justify-center rounded">
              <Building2 className="w-5 h-5 text-white" strokeWidth={1.5} />
            </div>
            <div>
              <span className="text-base font-semibold text-white">ClinicCRM</span>
              <p className="text-xs text-teal-400">Panel Clínico</p>
            </div>
          </div>
        </div>

        <nav className="flex-1 py-4 px-3 space-y-1">
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
              data-testid={`clinic-nav-${item.label.toLowerCase()}`}
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

      <main className="flex-1 ml-64">
        <Outlet />
      </main>
    </div>
  );
}
