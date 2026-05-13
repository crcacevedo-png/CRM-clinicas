import { useEffect, useState } from 'react';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import { Megaphone, X, Info, CheckCircle, AlertTriangle, Zap } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const SEV_STYLES = {
  info:     { bg: 'bg-blue-50',    border: 'border-blue-200',    text: 'text-blue-800',    iconColor: 'text-blue-500',    Icon: Info },
  success:  { bg: 'bg-emerald-50', border: 'border-emerald-200', text: 'text-emerald-800', iconColor: 'text-emerald-500', Icon: CheckCircle },
  warning:  { bg: 'bg-amber-50',   border: 'border-amber-200',   text: 'text-amber-800',   iconColor: 'text-amber-500',   Icon: AlertTriangle },
  critical: { bg: 'bg-rose-50',    border: 'border-rose-200',    text: 'text-rose-800',    iconColor: 'text-rose-500',    Icon: Zap },
};

export default function AnnouncementsBanner() {
  const { getAuthHeaders, user, token } = useAuth();
  const [items, setItems] = useState([]);

  useEffect(() => {
    if (!user || !token) return;
    let cancelled = false;
    axios.get(`${API}/clinic/announcements`, { headers: getAuthHeaders() })
      .then((res) => { if (!cancelled) setItems(res.data || []); })
      .catch(() => {});
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id, token]);

  const dismiss = async (id) => {
    // optimistic UI
    setItems((prev) => prev.filter((x) => x.id !== id));
    try {
      await axios.post(`${API}/clinic/announcements/${id}/dismiss`, {}, { headers: getAuthHeaders() });
    } catch {
      // ignore — already removed locally
    }
  };

  if (!items.length) return null;

  return (
    <div className="space-y-2 mb-4" data-testid="announcements-banner">
      {items.map((a) => {
        const s = SEV_STYLES[a.severity] || SEV_STYLES.info;
        const Icon = s.Icon;
        return (
          <div
            key={a.id}
            className={`flex items-start gap-3 rounded-lg border ${s.bg} ${s.border} px-3 py-2.5`}
            data-testid={`announcement-banner-${a.id}`}
          >
            <Icon className={`w-5 h-5 mt-0.5 flex-shrink-0 ${s.iconColor}`} />
            <div className="flex-1 min-w-0">
              <p className={`text-sm font-semibold ${s.text}`}>
                <Megaphone className="w-3.5 h-3.5 inline mr-1.5 opacity-60" />
                {a.title}
              </p>
              <p className={`text-xs ${s.text} opacity-90 whitespace-pre-wrap mt-0.5`}>{a.body}</p>
              {a.cta_label && a.cta_url && (
                <a
                  href={a.cta_url}
                  className={`inline-block mt-1.5 text-xs font-semibold underline ${s.text}`}
                  data-testid={`announcement-cta-${a.id}`}
                >
                  {a.cta_label} →
                </a>
              )}
            </div>
            <button
              type="button"
              onClick={() => dismiss(a.id)}
              className={`flex-shrink-0 ${s.iconColor} hover:opacity-70 transition-opacity`}
              title="Descartar"
              data-testid={`dismiss-${a.id}`}
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
