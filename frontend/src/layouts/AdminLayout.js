import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import axios from 'axios';
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
  DollarSign,
  LifeBuoy,
  Trash2
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
  { to: '/admin/soporte', icon: LifeBuoy, label: 'Soporte' },
  { to: '/admin/papelera', icon: Trash2, label: 'Papelera' },
  { to: '/admin/configuracion', icon: Settings, label: 'Configuración' },
];

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function AdminLayout() {
  const { user, logout, getAuthHeaders } = useAuth();
  const navigate = useNavigate();
  const [openTickets, setOpenTickets] = useState(0);

  useEffect(() => {
    let mounted = true;
    const loadSummary = async () => {
      try {
        const res = await axios.get(`${API}/admin/support/summary`, { headers: getAuthHeaders() });
        if (mounted) setOpenTickets(res.data?.open || 0);
      } catch { /* silent */ }
    };
    loadSummary();
    const id = setInterval(loadSummary, 60000);
    return () => { mounted = false; clearInterval(id); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
              {item.label === 'Soporte' && openTickets > 0 ? (
                <span className="ml-auto min-w-[20px] h-5 px-1.5 rounded-full bg-teal-500 text-white text-[11px] font-bold flex items-center justify-center" data-testid="support-open-badge">
                  {openTickets}
                </span>
              ) : (
                <ChevronRight className="w-4 h-4 ml-auto opacity-50" strokeWidth={1.5} />
              )}
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
