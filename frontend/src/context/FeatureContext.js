import { createContext, useContext, useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from './AuthContext';

const FeatureContext = createContext({ features: [], plan: '', hasFeature: () => true, loading: true });

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export function FeatureProvider({ children }) {
  const { user, getAuthHeaders } = useAuth();
  const [features, setFeatures] = useState([]);
  const [plan, setPlan] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) { setLoading(false); return; }
    const fetchFeatures = async () => {
      try {
        const res = await axios.get(`${API}/clinic/features`, { headers: getAuthHeaders() });
        setFeatures(res.data.features || []);
        setPlan(res.data.plan || '');
      } catch {
        // Not a clinic user or error — allow all by default
        setFeatures([]);
      } finally {
        setLoading(false);
      }
    };
    fetchFeatures();
  }, [user]);

  const hasFeature = (code) => {
    if (loading) return true; // Don't block while loading
    if (features.length === 0 && !plan) return true; // Fallback: no restrictions if fetch failed
    return features.includes(code);
  };

  return (
    <FeatureContext.Provider value={{ features, plan, hasFeature, loading }}>
      {children}
    </FeatureContext.Provider>
  );
}

export function useFeature(featureCode) {
  const { hasFeature } = useContext(FeatureContext);
  return hasFeature(featureCode);
}

export function useFeatures() {
  return useContext(FeatureContext);
}
