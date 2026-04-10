import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { AlertCircle, Building2, Lock, Mail } from 'lucide-react';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    const result = await login(email, password);

    if (result.success) {
      if (result.userType === 'super_admin') {
        navigate('/admin');
      } else if (result.userType === 'clinic_member') {
        navigate('/dashboard');
      }
    } else {
      setError(result.error);
    }

    setLoading(false);
  };

  return (
    <div className="min-h-screen flex">
      {/* Left Panel - Form */}
      <div className="flex-1 flex items-center justify-center p-8 bg-white">
        <div className="w-full max-w-md">
          <div className="mb-10">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-10 h-10 bg-[#120B29] flex items-center justify-center">
                <Building2 className="w-5 h-5 text-white" strokeWidth={1.5} />
              </div>
              <span className="text-2xl font-semibold text-zinc-950 tracking-tight">ClinicCRM</span>
            </div>
            <p className="text-sm text-zinc-500 mt-4">
              Sistema de gestión para clínicas médicas
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <Label htmlFor="email" className="form-label">Correo electrónico</Label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" strokeWidth={1.5} />
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="tu@email.com"
                  className="pl-10 form-input"
                  required
                  data-testid="login-email-input"
                />
              </div>
            </div>

            <div>
              <Label htmlFor="password" className="form-label">Contraseña</Label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" strokeWidth={1.5} />
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="pl-10 form-input"
                  required
                  data-testid="login-password-input"
                />
              </div>
            </div>

            {error && (
              <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 text-red-700 text-sm" data-testid="login-error">
                <AlertCircle className="w-4 h-4 flex-shrink-0" strokeWidth={1.5} />
                <span>{error}</span>
              </div>
            )}

            <Button
              type="submit"
              className="w-full btn-primary h-11"
              disabled={loading}
              data-testid="login-submit-btn"
            >
              {loading ? 'Iniciando sesión...' : 'Iniciar sesión'}
            </Button>
          </form>

          <p className="text-xs text-zinc-400 text-center mt-8">
            El acceso al sistema es solo para usuarios autorizados.<br />
            Contacta al administrador si necesitas acceso.
          </p>
        </div>
      </div>

      {/* Right Panel - Visual */}
      <div 
        className="hidden lg:flex flex-1 items-center justify-center p-12 relative overflow-hidden"
        style={{ 
          backgroundColor: '#120B29',
          backgroundImage: `url('https://images.unsplash.com/photo-1754738381772-897447d10eb6?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA1OTN8MHwxfHNlYXJjaHwxfHxhYnN0cmFjdCUyMHRlY2hub2xvZ2ljYWwlMjBiYWNrZ3JvdW5kJTIwcHVycGxlJTIwZGFya3xlbnwwfHx8fDE3NzU3ODYwMjB8MA&ixlib=rb-4.1.0&q=85')`,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          backgroundBlendMode: 'overlay'
        }}
      >
        <div className="max-w-lg text-center z-10">
          <h1 className="text-4xl font-semibold text-white tracking-tight mb-4">
            Panel de Administración
          </h1>
          <p className="text-lg text-zinc-300 leading-relaxed">
            Gestiona clínicas, usuarios y catálogos médicos desde un solo lugar.
          </p>
        </div>
      </div>
    </div>
  );
}
