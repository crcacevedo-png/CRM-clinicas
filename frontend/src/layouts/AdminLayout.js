import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { 
  LayoutDashboard, 
  Building2, 
  Users, 
  BookOpen, 
  Settings, 
  LogOut,
  ChevronRight
} from 'lucide-react';
import { Button } from '../components/ui/button';

const navItems = [
  { to: '/admin', icon: LayoutDashboard, label: 'Dashboard', end: true },
  { to: '/admin/clinicas', icon: Building2, label: 'Clínicas' },
  { to: '/admin/usuarios', icon: Users, label: 'Usuarios' },
  { to: '/admin/catalogos', icon: BookOpen, label: 'Catálogos' },
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
        <div className="p-6 border-b" style={{ borderColor: 'rgba(46, 196, 182, 0.2)' }}>
          <div className="flex items-center gap-3">
            <div className="relative w-9 h-9">
              <svg viewBox="0 0 44 44" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full h-full">
                <rect width="44" height="44" rx="8" fill="#133B5C"/>
                <path 
                  d="M22 8C14.268 8 8 14.268 8 22s6.268 14 14 14 14-6.268 14-14S29.732 8 22 8zm0 24c-5.523 0-10-4.477-10-10s4.477-10 10-10 10 4.477 10 10-4.477 10-10 10z" 
                  fill="#2EC4B6" 
                  opacity="0.3"
                />
                <path 
                  d="M22 14c-4.418 0-8 3.582-8 8s3.582 8 8 8 8-3.582 8-8-3.582-8-8-8zm0 12c-2.21 0-4-1.79-4-4s1.79-4 4-4 4 1.79 4 4-1.79 4-4 4z" 
                  fill="#2EC4B6"
                />
                <circle cx="22" cy="22" r="2" fill="#2EC4B6"/>
                <line x1="22" y1="12" x2="22" y2="16" stroke="#2EC4B6" strokeWidth="1.5" strokeLinecap="round"/>
                <line x1="22" y1="28" x2="22" y2="32" stroke="#2EC4B6" strokeWidth="1.5" strokeLinecap="round"/>
                <line x1="12" y1="22" x2="16" y2="22" stroke="#2EC4B6" strokeWidth="1.5" strokeLinecap="round"/>
                <line x1="28" y1="22" x2="32" y2="22" stroke="#2EC4B6" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
            </div>
            <div>
              <span className="text-lg font-semibold text-white tracking-tight">Cortexia</span>
              <p className="text-xs" style={{ color: '#2EC4B6' }}>Super Admin</p>
            </div>
          </div>
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
