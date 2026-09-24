import { useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Mail, AlertCircle, CheckCircle2, ArrowLeft } from 'lucide-react';
import AnimatedMedicalBackground from '../components/AnimatedMedicalBackground';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [sent, setSent] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await axios.post(`${API}/auth/forgot-password`, { email });
      setSent(true);
    } catch (err) {
      setError(err.response?.data?.detail || 'No se pudo procesar la solicitud. Intenta de nuevo.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen relative">
      <AnimatedMedicalBackground />
      <div className="relative z-10 min-h-screen flex items-center justify-start p-8 pl-24">
        <div className="w-full max-w-md bg-white p-10 shadow-2xl" style={{ borderRadius: '8px' }} data-testid="forgot-password-page">
          <div className="mb-8">
            <img src="/logo-cortexia-cropped.png" alt="Cortexia Medical" style={{ height: '110px', width: 'auto', objectFit: 'contain' }} />
            <h1 className="text-xl font-bold text-zinc-800 mt-4">Recuperar contraseña</h1>
            <p className="text-sm text-zinc-500 mt-1">Te enviaremos un enlace seguro a tu correo.</p>
          </div>

          {sent ? (
            <div className="space-y-5">
              <div className="flex items-start gap-3 p-4 rounded-lg bg-emerald-50 border border-emerald-200" data-testid="forgot-success">
                <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" />
                <p className="text-sm text-emerald-800">
                  Si el correo está registrado, te enviamos un enlace para restablecer tu contraseña. Revisa tu bandeja de entrada (y spam). El enlace vence en 60 minutos.
                </p>
              </div>
              <Link to="/login" className="inline-flex items-center gap-2 text-sm font-medium text-[#0A2540] hover:text-[#2EC4B6]" data-testid="back-to-login-link">
                <ArrowLeft className="w-4 h-4" /> Volver al inicio de sesión
              </Link>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-6">
              <div>
                <Label htmlFor="email" className="text-sm font-medium text-zinc-700 mb-1 block">Correo electrónico</Label>
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
                    data-testid="forgot-email-input"
                  />
                </div>
              </div>

              {error && (
                <div className="flex items-center gap-2 p-3 text-sm" style={{ backgroundColor: 'rgba(220, 38, 38, 0.08)', border: '1px solid rgba(220, 38, 38, 0.2)', borderRadius: '6px', color: '#DC2626' }} data-testid="forgot-error">
                  <AlertCircle className="w-4 h-4 flex-shrink-0" strokeWidth={1.5} />
                  <span>{error}</span>
                </div>
              )}

              <Button type="submit" className="w-full h-11 text-white font-medium" style={{ backgroundColor: '#0A2540', borderRadius: '6px' }} disabled={loading} data-testid="forgot-submit-btn">
                {loading ? 'Enviando…' : 'Enviar enlace'}
              </Button>

              <Link to="/login" className="inline-flex items-center gap-2 text-sm font-medium text-zinc-500 hover:text-[#0A2540]" data-testid="back-to-login-link">
                <ArrowLeft className="w-4 h-4" /> Volver al inicio de sesión
              </Link>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
