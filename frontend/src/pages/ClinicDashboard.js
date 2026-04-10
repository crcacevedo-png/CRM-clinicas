import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { useNavigate } from 'react-router-dom';
import { Building2 } from 'lucide-react';

export default function ClinicDashboard() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-zinc-50">
      {/* Header */}
      <header className="bg-white border-b border-zinc-200 px-6 py-4">
        <div className="flex items-center justify-between max-w-7xl mx-auto">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-blue-600 flex items-center justify-center">
              <Building2 className="w-5 h-5 text-white" strokeWidth={1.5} />
            </div>
            <span className="text-lg font-semibold text-zinc-950">ClinicCRM</span>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-zinc-600">{user?.email}</span>
            <Button variant="outline" onClick={handleLogout} data-testid="clinic-logout-btn">
              Cerrar sesión
            </Button>
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="p-8 max-w-7xl mx-auto">
        <div className="bg-white border border-zinc-200 p-12 text-center">
          <Building2 className="w-16 h-16 text-zinc-300 mx-auto mb-4" strokeWidth={1.5} />
          <h1 className="text-2xl font-semibold text-zinc-900 mb-2">Dashboard de Clínica</h1>
          <p className="text-zinc-500 mb-6">
            El panel de gestión de clínicas estará disponible próximamente.
          </p>
          <p className="text-sm text-zinc-400">
            Has iniciado sesión como miembro de una clínica.
          </p>
        </div>
      </main>
    </div>
  );
}
