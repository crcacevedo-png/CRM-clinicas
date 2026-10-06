import axios from 'axios';
import { AlertTriangle } from 'lucide-react';
import { usePaymentStatus } from '../context/PaymentStatusContext';
import { useAuth } from '../context/AuthContext';
import { useState } from 'react';
import { Button } from '../components/ui/button';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Red overdue banner shown across the clinic app while the subscription is in
 * the grace window (past_due / unpaid but not yet blocked). Clicking the CTA
 * opens the Stripe Customer Portal so the admin can update their card.
 */
export default function PaymentOverdueBanner() {
  const { isInGrace, daysLeftInGrace, nextRetryAt, lastAttemptCount, lastFailureMessage, loading } = usePaymentStatus();
  const { getAuthHeaders, role } = useAuth();
  const [opening, setOpening] = useState(false);

  if (loading || !isInGrace) return null;

  const openPortal = async () => {
    setOpening(true);
    try {
      const res = await axios.post(`${API}/billing/portal`, {}, { headers: getAuthHeaders() });
      if (res.data?.url) window.location.href = res.data.url;
    } catch {
      alert('No se pudo abrir el portal de pago. Contacta al administrador de la clínica.');
    } finally {
      setOpening(false);
    }
  };

  const isAdmin = role === 'clinic_admin';
  const dayText = daysLeftInGrace === 1 ? 'día' : 'días';

  // Format next retry date in "6 oct" style
  const nextRetryLabel = nextRetryAt
    ? new Date(nextRetryAt).toLocaleDateString('es', { day: 'numeric', month: 'short' })
    : null;

  return (
    <div
      data-testid="payment-overdue-banner"
      className="w-full bg-red-600 text-white px-4 py-2.5 flex items-center justify-between shadow-sm gap-4"
    >
      <div className="flex items-center gap-2.5 text-sm min-w-0">
        <AlertTriangle className="w-4 h-4 shrink-0" strokeWidth={2} />
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 min-w-0">
          <span>
            <strong>Pago vencido.</strong>{' '}
            {daysLeftInGrace !== null && daysLeftInGrace > 0 ? (
              <>Tu clínica será bloqueada en <strong>{daysLeftInGrace} {dayText}</strong> si no se actualiza el método de pago.</>
            ) : (
              <>Actualiza tu método de pago para evitar la suspensión del servicio.</>
            )}
          </span>
          {nextRetryLabel && (
            <span className="text-xs text-red-100" data-testid="payment-overdue-next-retry">
              Stripe reintentará el <strong>{nextRetryLabel}</strong>
              {lastAttemptCount ? ` · intento #${lastAttemptCount}` : ''}
            </span>
          )}
          {lastFailureMessage && !nextRetryLabel && (
            <span className="text-xs text-red-100 truncate max-w-md" title={lastFailureMessage}>
              Motivo: {lastFailureMessage}
            </span>
          )}
        </div>
      </div>
      {isAdmin && (
        <Button
          size="sm"
          variant="secondary"
          className="bg-white text-red-700 hover:bg-red-50 h-8 text-xs font-semibold shrink-0"
          onClick={openPortal}
          disabled={opening}
          data-testid="payment-overdue-portal-btn"
        >
          {opening ? 'Abriendo…' : 'Actualizar método de pago'}
        </Button>
      )}
    </div>
  );
}
