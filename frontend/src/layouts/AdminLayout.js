import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { 
  LayoutDashboard, 
  Building2, 
  Users, 
  BookOpen, 
  Settings, 
  LogOut,
  ChevronRight,
  CreditCard,
  Megaphone,
  Shield,
  Activity,
  DollarSign
} from 'lucide-react';
import { Button } from '../components/ui/button';

const navItems = [
  { to: '/admin', icon: LayoutDashboard, label: 'Dashboard', end: true },
  { to: '/admin/clinicas', icon: Building2, label: 'Clínicas' },
  { to: '/admin/usuarios', icon: Users, label: 'Usuarios' },
  { to: '/admin/catalogos', icon: BookOpen, label: 'Catálogos' },
  { to: '/admin/planes', icon: CreditCard, label: 'Planes' },
  { to: '/admin/cobros', icon: DollarSign, label: 'Cobros' },
  { to: '/admin/comunicacion', icon: Megaphone, label: 'Comunicación' },
  { to: '/admin/auditoria', icon: Shield, label: 'Auditoría' },
  { to: '/admin/salud', icon: Activity, label: 'Salud sistema' },
  { to: '/admin/configuracion', icon: Settings, label: 'Configuración' },
];

export default function AdminLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <div className="flex min-h-screen bg-[#FAFAFA]">
      {/* Sidebar */}
      <aside className="w-64 admin-sidebar flex flex-col fixed h-full" style={{ backgroundColor: '#0A2540' }}>
        {/* Logo */}
        <div className="p-4 border-b" style={{ borderColor: 'rgba(46, 196, 182, 0.2)' }}>
          <img 
            src="/logo-cortexia-cropped.png" 
            alt="Cortexia Medical" 
            className="h-20 w-auto brightness-0 invert"
          />
          <p className="text-xs mt-2" style={{ color: '#2EC4B6' }}>Super Admin</p>
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-4 px-3 space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 text-sm font-medium transition-all rounded-sm ${
                  isActive 
                    ? 'text-white bg-[#2EC4B6]/20 border-l-2 border-[#2EC4B6]' 
                    : 'text-zinc-400 hover:text-white hover:bg-white/5'
                }`
              }
              data-testid={`nav-${item.label.toLowerCase()}`}
            >
              <item.icon className="w-5 h-5" strokeWidth={1.5} />
              <span>{item.label}</span>
              <ChevronRight className="w-4 h-4 ml-auto opacity-50" strokeWidth={1.5} />
            </NavLink>
          ))}
        </nav>

        {/* User Info & Logout */}
        <div className="p-4 border-t" style={{ borderColor: 'rgba(46, 196, 182, 0.2)' }}>
          <div className="mb-3">
            <p className="text-sm font-medium text-white truncate">{user?.email}</p>
            <p className="text-xs text-zinc-400">Administrador</p>
          </div>
          <Button
            variant="ghost"
            className="w-full justify-start text-zinc-400 hover:text-white hover:bg-white/10"
            onClick={handleLogout}
            data-testid="logout-btn"
          >
            <LogOut className="w-4 h-4 mr-2" strokeWidth={1.5} />
            Cerrar sesión
          </Button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 ml-64">
        <Outlet />
      </main>
    </div>
  );
}
