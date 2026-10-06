import axios from 'axios';
import { useState } from 'react';
import { Lock, CreditCard, LogOut } from 'lucide-react';
import { usePaymentStatus } from '../context/PaymentStatusContext';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/button';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Full-screen hard-block shown when `is_payment_blocked = true`.
 * The only actions available are: open Stripe Customer Portal (admins only)
 * and logout. All other routes are inaccessible until the subscription is
 * restored.
 */
export default function PaymentBlockedScreen() {
  const { clinicName, refresh } = usePaymentStatus();
  const { getAuthHeaders, logout, role } = useAuth();
  const [opening, setOpening] = useState(false);

  const openPortal = async () => {
    setOpening(true);
    try {
      const res = await axios.post(`${API}/billing/portal`, {}, { headers: getAuthHeaders() });
      if (res.data?.url) window.location.href = res.data.url;
    } catch {
      alert('No se pudo abrir el portal de pago. Intenta de nuevo o contacta a soporte.');
    } finally {
      setOpening(false);
    }
  };

  const handleLogout = async () => {
    await logout();
    window.location.href = '/login';
  };

  const isAdmin = role === 'clinic_admin';

  return (
    <div
      data-testid="payment-blocked-screen"
      className="min-h-screen flex items-center justify-center bg-slate-50 p-6"
    >
      <div className="max-w-lg w-full bg-white rounded-xl shadow-xl border border-red-200 overflow-hidden">
        <div className="bg-red-600 text-white px-6 py-5 flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-white/20 flex items-center justify-center">
            <Lock className="w-5 h-5" strokeWidth={2} />
          </div>
          <div>
            <h1 className="text-xl font-bold">Pago vencido</h1>
            <p className="text-xs text-red-100">Acceso suspendido</p>
          </div>
        </div>

        <div className="px-6 py-6 space-y-4">
          <p className="text-sm text-slate-700 leading-relaxed">
            {clinicName && <strong className="text-slate-900">{clinicName}</strong>}
            {clinicName && <> — </>}
            Tu suscripción tiene un pago vencido y el período de gracia ha
            terminado. El acceso al sistema está suspendido hasta que se
            actualice el método de pago.
          </p>

          <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 text-xs text-amber-900">
            {isAdmin ? (
              <>
                <strong>Acción requerida:</strong> Abre el portal de pago,
                actualiza tu tarjeta y confirma el cobro pendiente. El acceso
                se restablece automáticamente una vez que Stripe confirma el
                pago (puede tardar unos segundos).
              </>
            ) : (
              <>
                <strong>Acción requerida:</strong> Contacta al administrador
                de tu clínica para que actualice el método de pago.
              </>
            )}
          </div>

          <div className="flex flex-col gap-2 pt-2">
            {isAdmin && (
              <Button
                className="w-full bg-red-600 hover:bg-red-700 text-white font-semibold"
                onClick={openPortal}
                disabled={opening}
                data-testid="payment-blocked-portal-btn"
              >
                <CreditCard className="w-4 h-4 mr-2" strokeWidth={2} />
                {opening ? 'Abriendo portal…' : 'Actualizar método de pago'}
              </Button>
            )}
            <Button
              variant="outline"
              className="w-full"
              onClick={refresh}
              data-testid="payment-blocked-refresh-btn"
            >
              Ya pagué — Verificar estado
            </Button>
            <Button
              variant="ghost"
              className="w-full text-slate-500 hover:text-slate-700"
              onClick={handleLogout}
              data-testid="payment-blocked-logout-btn"
            >
              <LogOut className="w-4 h-4 mr-2" strokeWidth={1.5} />
              Cerrar sesión
            </Button>
          </div>
        </div>

        <div className="bg-slate-50 border-t border-slate-200 px-6 py-3 text-[11px] text-slate-500 text-center">
          ¿Necesitas ayuda? Escríbenos a soporte y te asistimos de inmediato.
        </div>
      </div>
    </div>
  );
}
