import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useAuth } from './AuthContext';
import { useFeatures } from './FeatureContext';

const BranchContext = createContext({ branches: [], activeBranch: null, setActiveBranch: () => {}, loading: true, hasBranches: false });

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export function BranchProvider({ children }) {
  const { user, getAuthHeaders } = useAuth();
  const { hasFeature } = useFeatures();
  const [branches, setBranches] = useState([]);
  const [activeBranch, setActiveBranch] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchBranches = useCallback(async () => {
    if (!user || !hasFeature('multi_branch')) { setLoading(false); return; }
    try {
      const res = await axios.get(`${API}/clinic/branches`, { headers: getAuthHeaders() });
      const data = res.data || [];
      setBranches(data);
      if (data.length > 0 && !activeBranch) {
        const main = data.find(b => b.is_main) || data[0];
        setActiveBranch(main);
      }
    } catch {} finally { setLoading(false); }
  }, [user, hasFeature]);

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
