import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useAuth } from './AuthContext';
import { useFeatures } from './FeatureContext';

const BranchContext = createContext({ branches: [], activeBranch: null, setActiveBranch: () => {}, loading: true, hasBranches: false });

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const STORAGE_KEY = 'cliniccrm.activeBranchId';

export function BranchProvider({ children }) {
  const { user, getAuthHeaders } = useAuth();
  const { hasFeature } = useFeatures();
  const [branches, setBranches] = useState([]);
  const [activeBranch, setActiveBranchState] = useState(null);
  const [loading, setLoading] = useState(true);

  // Wrap setter so any change is also persisted to localStorage
  const setActiveBranch = useCallback((branch) => {
    setActiveBranchState(branch);
    try {
      if (branch?.id) localStorage.setItem(STORAGE_KEY, branch.id);
      else localStorage.removeItem(STORAGE_KEY);
    } catch { /* ignore quota / privacy mode errors */ }
  }, []);

  const fetchBranches = useCallback(async () => {
    if (!user || !hasFeature('multi_branch')) { setLoading(false); return; }
    try {
      const res = await axios.get(`${API}/clinic/branches`, { headers: getAuthHeaders() });
      const data = res.data || [];
      setBranches(data);
      if (data.length > 0) {
        // Prefer persisted choice, fall back to main, then first
        let stored = null;
        try { stored = localStorage.getItem(STORAGE_KEY); } catch { /* ignore */ }
        const persisted = stored ? data.find(b => b.id === stored) : null;
        const main = data.find(b => b.is_main);
        setActiveBranchState(persisted || main || data[0]);
      }
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [user, hasFeature]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { fetchBranches(); }, [fetchBranches]);

  const hasBranches = branches.length > 1;

  return (
    <BranchContext.Provider value={{ branches, activeBranch, setActiveBranch, loading, hasBranches, refetchBranches: fetchBranches }}>
      {children}
    </BranchContext.Provider>
  );
}

export function useBranch() {
  return useContext(BranchContext);
}
