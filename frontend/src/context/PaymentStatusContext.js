import { createContext, useContext, useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { useAuth } from './AuthContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const PaymentStatusContext = createContext({
  isPaymentBlocked: false,
  isCourtesy: false,
  paymentGraceUntil: null,
  stripeSubscriptionStatus: null,
  clinicName: '',
  loading: true,
  daysLeftInGrace: null,
  isInGrace: false,
  refresh: () => {},
});

export const PaymentStatusProvider = ({ children }) => {
  const { user, userType, getAuthHeaders } = useAuth();
  const [state, setState] = useState({
    isPaymentBlocked: false,
    isCourtesy: false,
    paymentGraceUntil: null,
    stripeSubscriptionStatus: null,
    clinicName: '',
    lastAttemptCount: null,
    lastFailureMessage: null,
    nextRetryAt: null,
    loading: true,
  });

  const fetchStatus = useCallback(async () => {
    if (!user || userType !== 'clinic_member') {
      setState(s => ({ ...s, loading: false }));
      return;
    }
    try {
      const res = await axios.get(`${API}/billing/payment-status`, { headers: getAuthHeaders() });
      setState({
        isPaymentBlocked: !!res.data?.is_payment_blocked,
        isCourtesy: !!res.data?.is_courtesy,
        paymentGraceUntil: res.data?.payment_grace_until || null,
        stripeSubscriptionStatus: res.data?.stripe_subscription_status || null,
        clinicName: res.data?.clinic_name || '',
        lastAttemptCount: res.data?.last_attempt_count ?? null,
        lastFailureMessage: res.data?.last_failure_message || null,
        nextRetryAt: res.data?.next_retry_at || null,
        loading: false,
      });
    } catch (e) {
      if (e?.response?.status === 402) {
        setState(s => ({ ...s, isPaymentBlocked: true, loading: false }));
      } else {
        setState(s => ({ ...s, loading: false }));
      }
    }
  }, [user, userType, getAuthHeaders]);

  useEffect(() => {
    fetchStatus();
    // Poll every 2 minutes to catch state changes without a full reload
    const id = setInterval(fetchStatus, 120000);
    return () => clearInterval(id);
  }, [fetchStatus]);

  // Compute derived values
  const now = Date.now();
  const graceMs = state.paymentGraceUntil ? new Date(state.paymentGraceUntil).getTime() : null;
  const daysLeftInGrace = graceMs ? Math.max(0, Math.ceil((graceMs - now) / (1000 * 60 * 60 * 24))) : null;
  // "In grace" = clinic has subscription issues (past_due/unpaid) AND is still within grace window
  const problematicStatuses = ['past_due', 'unpaid', 'incomplete'];
  const isInGrace = !state.isCourtesy
    && !state.isPaymentBlocked
    && problematicStatuses.includes(state.stripeSubscriptionStatus || '')
    && graceMs !== null
    && graceMs > now;

  return (
    <PaymentStatusContext.Provider
      value={{
        ...state,
        daysLeftInGrace,
        isInGrace,
        refresh: fetchStatus,
      }}
    >
      {children}
    </PaymentStatusContext.Provider>
  );
};

export const usePaymentStatus = () => useContext(PaymentStatusContext);
