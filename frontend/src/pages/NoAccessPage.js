import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { AlertCircle, LogOut } from 'lucide-react';
import { Button } from '../components/ui/button';

export default function NoAccessPage() {
  const { logout, isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  const handleLogout = async () => {
    await logout();
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-zinc-50 p-8">
      <div className="max-w-md w-full bg-white border border-zinc-200 p-8 text-center">
        <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-6">
          <AlertCircle className="w-8 h-8 text-red-600" strokeWidth={1.5} />
        </div>
        <h1 className="text-2xl font-semibold text-zinc-900 mb-2">Sin acceso</h1>
        <p className="text-zinc-500 mb-6">
          No tienes acceso al sistema. Contacta al administrador si crees que esto es un error.
        </p>
        <Button onClick={handleLogout} className="btn-primary" data-testid="no-access-logout-btn">
          <LogOut className="w-4 h-4 mr-2" strokeWidth={1.5} />
          Cerrar sesión
        </Button>
      </div>
    </div>
  );
}
