import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { KeyRound, AlertCircle, Eye, EyeOff, Loader2 } from 'lucide-react';
import AnimatedMedicalBackground from '../components/AnimatedMedicalBackground';
import PasswordStrengthMeter, { passwordMeetsPolicy, MIN_LENGTH } from '../components/PasswordStrengthMeter';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token') || '';
  const isWelcome = searchParams.get('welcome') === '1';

  const [checking, setChecking] = useState(true);
  const [valid, setValid] = useState(false);
  const [email, setEmail] = useState('');
  const [newPw, setNewPw] = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const validate = async () => {
      if (!token) { setChecking(false); setValid(false); return; }
      try {
        const res = await axios.get(`${API}/auth/reset-token/validate`, { params: { token } });
        setValid(!!res.data?.valid);
        setEmail(res.data?.email || '');
      } catch {
        setValid(false);
      } finally {
        setChecking(false);
      }
    };
    validate();
  }, [token]);

  const canSubmit = !!newPw && newPw === confirmPw && passwordMeetsPolicy(newPw, { email });

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!canSubmit) { toast.error('Revisa las reglas de la nueva contraseña'); return; }
    setSubmitting(true);
    try {
      await axios.post(`${API}/auth/reset-password`, { token, new_password: newPw });
      toast.success('Contraseña establecida. Ya puedes iniciar sesión.');
      navigate('/login');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'No se pudo actualizar la contraseña');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen relative">
      <AnimatedMedicalBackground />
      <div className="relative z-10 min-h-screen flex items-center justify-start p-8 pl-24">
        <div className="w-full max-w-md bg-white p-10 shadow-2xl" style={{ borderRadius: '8px' }} data-testid="reset-password-page">
          <div className="mb-8">
            <img src="/logo-cortexia-cropped.png" alt="Cortexia Medical" style={{ height: '110px', width: 'auto', objectFit: 'contain' }} />
            <h1 className="text-xl font-bold text-zinc-800 mt-4">
              {isWelcome ? 'Crea tu contraseña' : 'Restablecer contraseña'}
            </h1>
            {email && <p className="text-sm text-zinc-500 mt-1">Para <strong>{email}</strong></p>}
          </div>

          {checking ? (
            <div className="flex items-center gap-2 text-sm text-zinc-500" data-testid="reset-checking">
              <Loader2 className="w-4 h-4 animate-spin" /> Verificando enlace…
            </div>
          ) : !valid ? (
            <div className="space-y-5">
              <div className="flex items-start gap-3 p-4 rounded-lg bg-rose-50 border border-rose-200" data-testid="reset-invalid">
                <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
                <p className="text-sm text-rose-800">
                  Este enlace es inválido o ya expiró. Solicita uno nuevo desde “¿Olvidaste tu contraseña?”.
                </p>
              </div>
              <Button className="w-full h-11 text-white" style={{ backgroundColor: '#0A2540', borderRadius: '6px' }} onClick={() => navigate('/recuperar-password')} data-testid="request-new-link-btn">
                Solicitar nuevo enlace
              </Button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <Label className="text-sm font-medium text-zinc-700 mb-1 block">Nueva contraseña</Label>
                <div className="relative">
                  <KeyRound className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" strokeWidth={1.5} />
                  <Input
                    type={showPw ? 'text' : 'password'}
                    value={newPw}
                    onChange={(e) => setNewPw(e.target.value)}
                    minLength={MIN_LENGTH}
                    className="pl-10 pr-10 h-11 border-zinc-200"
                    style={{ borderRadius: '6px' }}
                    required
                    autoComplete="new-password"
                    data-testid="reset-new-password-input"
                  />
                  <button type="button" onClick={() => setShowPw((v) => !v)} className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-zinc-600" data-testid="reset-toggle-visibility">
                    {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                <PasswordStrengthMeter password={newPw} email={email} />
              </div>
              <div>
                <Label className="text-sm font-medium text-zinc-700 mb-1 block">Confirmar contraseña</Label>
                <Input
                  type={showPw ? 'text' : 'password'}
                  value={confirmPw}
                  onChange={(e) => setConfirmPw(e.target.value)}
                  className="h-11 border-zinc-200"
                  style={{ borderRadius: '6px' }}
                  required
                  autoComplete="new-password"
                  data-testid="reset-confirm-password-input"
                />
                {confirmPw && newPw !== confirmPw && (
                  <p className="text-[11px] text-rose-600 mt-1" data-testid="reset-mismatch">Las contraseñas no coinciden</p>
                )}
              </div>
              <Button type="submit" disabled={!canSubmit || submitting} className="w-full h-11 text-white font-medium" style={{ backgroundColor: '#0A2540', borderRadius: '6px' }} data-testid="reset-submit-btn">
                {submitting ? 'Guardando…' : (isWelcome ? 'Crear contraseña' : 'Restablecer contraseña')}
              </Button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
