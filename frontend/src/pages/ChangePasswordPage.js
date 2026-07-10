import { useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Button } from '../components/ui/button';
import { KeyRound, ShieldAlert, LogOut } from 'lucide-react';
import PasswordStrengthMeter, {
  passwordMeetsPolicy,
  MIN_LENGTH,
} from '../components/PasswordStrengthMeter';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function ChangePasswordPage() {
  const { user, getAuthHeaders, logout, userType, passwordNeedsReset, clearPasswordResetFlag } = useAuth();

  const [currentPw, setCurrentPw] = useState('');
  const [newPw, setNewPw] = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const emailForCheck = user?.email || '';
  const nameForCheck = user?.name || '';

  const canSubmit =
    !!currentPw &&
    !!newPw &&
    newPw === confirmPw &&
    newPw !== currentPw &&
    passwordMeetsPolicy(newPw, { email: emailForCheck, name: nameForCheck });

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!canSubmit) {
      toast.error('Revise las reglas de la nueva contraseña');
      return;
    }
    setSubmitting(true);
    try {
      await axios.post(
        `${API}/auth/change-password`,
        { current_password: currentPw, new_password: newPw },
        { headers: getAuthHeaders() },
      );
      toast.success('Contraseña actualizada correctamente');
      // Clear the flag before redirect
      if (clearPasswordResetFlag) clearPasswordResetFlag();
      const target = userType === 'super_admin' ? '/admin' : '/dashboard';
      // Hard reload sidesteps React 18 state batching — guarantees ProtectedRoute
      // reads the freshly-cleared flag on the next render cycle.
      window.location.assign(target);
    } catch (err) {
      const msg = err.response?.data?.detail || 'Error al cambiar contraseña';
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 px-4">
      <Card className="w-full max-w-md" data-testid="change-password-page">
        <CardHeader className="text-center space-y-2">
          <div className="mx-auto w-12 h-12 rounded-full bg-teal-50 flex items-center justify-center">
            <KeyRound className="w-6 h-6 text-teal-600" />
          </div>
          <CardTitle className="text-xl">Actualizar contraseña</CardTitle>
          {passwordNeedsReset ? (
            <div className="flex items-start gap-2 rounded-lg bg-amber-50 border border-amber-200 p-3 text-left">
              <ShieldAlert className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
              <p className="text-xs text-amber-800">
                Por seguridad, debe establecer una nueva contraseña personal antes de continuar.
                Su credencial actual fue asignada por un administrador.
              </p>
            </div>
          ) : (
            <p className="text-xs text-slate-500">Cambia tu contraseña. Estará activa inmediatamente.</p>
          )}
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <Label className="text-xs">Contraseña actual</Label>
              <Input
                type="password"
                autoComplete="current-password"
                value={currentPw}
                onChange={(e) => setCurrentPw(e.target.value)}
                required
                data-testid="current-password-input"
                className="mt-1"
              />
            </div>
            <div>
              <Label className="text-xs">Nueva contraseña</Label>
              <Input
                type="password"
                autoComplete="new-password"
                value={newPw}
                onChange={(e) => setNewPw(e.target.value)}
                required
                minLength={MIN_LENGTH}
                data-testid="new-password-input"
                className="mt-1"
              />
              <PasswordStrengthMeter
                password={newPw}
                email={emailForCheck}
                name={nameForCheck}
              />
            </div>
            <div>
              <Label className="text-xs">Confirmar nueva contraseña</Label>
              <Input
                type="password"
                autoComplete="new-password"
                value={confirmPw}
                onChange={(e) => setConfirmPw(e.target.value)}
                required
                data-testid="confirm-password-input"
                className="mt-1"
              />
              {confirmPw && newPw !== confirmPw && (
                <p className="text-[11px] text-rose-600 mt-1" data-testid="confirm-mismatch">Las contraseñas no coinciden</p>
              )}
              {currentPw && newPw && currentPw === newPw && (
                <p className="text-[11px] text-rose-600 mt-1" data-testid="same-as-current">
                  La nueva contraseña debe ser distinta a la actual
                </p>
              )}
            </div>
            <Button
              type="submit"
              disabled={!canSubmit || submitting}
              className="w-full bg-teal-600 hover:bg-teal-700"
              data-testid="change-password-submit"
            >
              {submitting ? 'Guardando…' : 'Actualizar contraseña'}
            </Button>
            {passwordNeedsReset && (
              <Button
                type="button"
                variant="ghost"
                className="w-full text-slate-500"
                onClick={async () => { await logout(); window.location.assign('/login'); }}
                data-testid="logout-btn"
              >
                <LogOut className="w-4 h-4 mr-2" />
                Cerrar sesión
              </Button>
            )}
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
