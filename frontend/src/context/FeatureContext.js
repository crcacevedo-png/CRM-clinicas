import { createContext, useContext, useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from './AuthContext';

const FeatureContext = createContext({ features: [], plan: '', modules: null, hasFeature: () => true, hasModule: () => true, loading: true });

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export function FeatureProvider({ children }) {
  const { user, getAuthHeaders } = useAuth();
  const [features, setFeatures] = useState([]);
  const [plan, setPlan] = useState('');
  const [modules, setModules] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) { setFeatures([]); setModules(null); setPlan(''); setLoading(false); return; }
    setLoading(true);
    setModules(null);
    const fetchFeatures = async () => {
      try {
        const res = await axios.get(`${API}/clinic/features`, { headers: getAuthHeaders() });
        setFeatures(res.data.features || []);
        setPlan(res.data.plan || '');
        setModules(Array.isArray(res.data.modules) ? res.data.modules : null);
      } catch {
        // Not a clinic user or error — allow all by default
        setFeatures([]);
        setModules(null);
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

  const hasModule = (key) => {
    if (loading) return true; // Don't block while loading
    if (modules === null) return true; // Fallback: no restrictions if fetch failed / not a clinic user
    return modules.includes(key);
  };

  return (
    <FeatureContext.Provider value={{ features, plan, modules, hasFeature, hasModule, loading }}>
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
