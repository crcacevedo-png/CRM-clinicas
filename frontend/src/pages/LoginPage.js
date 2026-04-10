import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { AlertCircle, Lock, Mail } from 'lucide-react';
import AnimatedMedicalBackground from '../components/AnimatedMedicalBackground';

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
          {/* Logo */}
          <div className="mb-10">
            <img 
              src="/logo-cortexia-cropped.png" 
              alt="Cortexia Medical" 
              style={{ 
                height: '52px',
                width: 'auto',
                objectFit: 'contain'
              }}
            />
            <p className="text-sm text-zinc-500 mt-4">
              Sistema de gestión para clínicas médicas
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <Label htmlFor="email" className="text-sm font-medium text-zinc-700 mb-1 block">
                Correo electrónico
              </Label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" strokeWidth={1.5} />
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="tu@email.com"
                  className="pl-10 h-11 border-zinc-200 focus:border-[#2EC4B6] focus:ring-[#2EC4B6]"
                  style={{ borderRadius: '6px' }}
                  required
                  data-testid="login-email-input"
                />
              </div>
            </div>

            <div>
              <Label htmlFor="password" className="text-sm font-medium text-zinc-700 mb-1 block">
                Contraseña
              </Label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" strokeWidth={1.5} />
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="pl-10 h-11 border-zinc-200 focus:border-[#2EC4B6] focus:ring-[#2EC4B6]"
                  style={{ borderRadius: '6px' }}
                  required
                  data-testid="login-password-input"
                />
              </div>
            </div>

            {error && (
              <div 
                className="flex items-center gap-2 p-3 text-sm"
                style={{ 
                  backgroundColor: 'rgba(220, 38, 38, 0.08)', 
                  border: '1px solid rgba(220, 38, 38, 0.2)',
                  borderRadius: '6px',
                  color: '#DC2626'
                }}
                data-testid="login-error"
              >
                <AlertCircle className="w-4 h-4 flex-shrink-0" strokeWidth={1.5} />
                <span>{error}</span>
              </div>
            )}

            <Button
              type="submit"
              className="w-full h-11 text-white font-medium transition-all duration-200"
              style={{ 
                backgroundColor: '#0A2540',
                borderRadius: '6px'
              }}
              disabled={loading}
              data-testid="login-submit-btn"
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"/>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                  </svg>
                  Iniciando sesión...
                </span>
              ) : 'Iniciar sesión'}
            </Button>
          </form>

          <p className="text-xs text-zinc-400 text-center mt-8">
            El acceso al sistema es solo para usuarios autorizados.<br />
            Contacta al administrador si necesitas acceso.
          </p>
        </div>
      </div>

      {/* Right Panel - Animated Visual */}
      <div className="hidden lg:flex flex-1 items-center justify-center relative overflow-hidden">
        {/* Animated Background */}
        <AnimatedMedicalBackground />
        
        {/* Content Overlay */}
        <div className="relative z-10 max-w-lg text-center px-12">
          {/* Subtle glow behind text */}
          <div 
            className="absolute inset-0 blur-3xl opacity-20"
            style={{ 
              background: 'radial-gradient(ellipse at center, rgba(46, 196, 182, 0.3) 0%, transparent 70%)'
            }}
          />
          
          <h1 
            className="text-4xl font-semibold text-white tracking-tight mb-4 relative"
            style={{ 
              textShadow: '0 2px 20px rgba(0, 0, 0, 0.3)'
            }}
          >
            Panel de Administración
          </h1>
          <p 
            className="text-lg leading-relaxed relative"
            style={{ 
              color: 'rgba(255, 255, 255, 0.8)',
              textShadow: '0 1px 10px rgba(0, 0, 0, 0.2)'
            }}
          >
            Gestiona clínicas, usuarios y catálogos médicos desde un solo lugar.
          </p>

          {/* Feature indicators */}
          <div className="flex justify-center gap-8 mt-10 relative">
            {[
              { label: 'Clínicas', icon: '🏥' },
              { label: 'Usuarios', icon: '👥' },
              { label: 'Catálogos', icon: '📋' },
            ].map((item, index) => (
              <div 
                key={index}
                className="flex flex-col items-center gap-2 opacity-70"
              >
                <div 
                  className="w-12 h-12 flex items-center justify-center text-xl"
                  style={{ 
                    backgroundColor: 'rgba(46, 196, 182, 0.15)',
                    border: '1px solid rgba(46, 196, 182, 0.3)',
                    borderRadius: '12px'
                  }}
                >
                  {item.icon}
                </div>
                <span className="text-xs text-white/60">{item.label}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Bottom gradient fade */}
        <div 
          className="absolute bottom-0 left-0 right-0 h-32 pointer-events-none"
          style={{
            background: 'linear-gradient(to top, rgba(10, 37, 64, 0.8) 0%, transparent 100%)'
          }}
        />
      </div>
    </div>
  );
}
