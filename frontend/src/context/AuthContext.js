import { createContext, useContext, useState, useEffect } from 'react';
import { supabase } from '../lib/supabase';
import axios from 'axios';

const AuthContext = createContext();

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [userType, setUserType] = useState(null);
  const [clinicId, setClinicId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState(localStorage.getItem('access_token'));

  useEffect(() => {
    checkSession();
  }, []);

  const checkSession = async () => {
    try {
      const storedToken = localStorage.getItem('access_token');
      const storedUserType = localStorage.getItem('user_type');
      const storedUserId = localStorage.getItem('user_id');
      const storedEmail = localStorage.getItem('user_email');
      const storedClinicId = localStorage.getItem('clinic_id');

      if (storedToken && storedUserType && storedUserId) {
        setToken(storedToken);
        setUserType(storedUserType);
        setClinicId(storedClinicId);
        setUser({ id: storedUserId, email: storedEmail });
      }
    } catch (error) {
      console.error('Session check error:', error);
    } finally {
      setLoading(false);
    }
  };

  const login = async (email, password) => {
    try {
      const response = await axios.post(`${API}/auth/login`, { email, password });
      const data = response.data;

      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);
      localStorage.setItem('user_type', data.user_type);
      localStorage.setItem('user_id', data.user_id);
      localStorage.setItem('user_email', data.email);
      if (data.clinic_id) {
        localStorage.setItem('clinic_id', data.clinic_id);
      }

      setToken(data.access_token);
      setUserType(data.user_type);
      setClinicId(data.clinic_id);
      setUser({ id: data.user_id, email: data.email });

      return { success: true, userType: data.user_type };
    } catch (error) {
      const message = error.response?.data?.detail || 'Error de autenticación';
      return { success: false, error: message };
    }
  };

  const logout = async () => {
    try {
      await axios.post(`${API}/auth/logout`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
    } catch (error) {
      console.error('Logout error:', error);
    }

    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user_type');
    localStorage.removeItem('user_id');
    localStorage.removeItem('user_email');
    localStorage.removeItem('clinic_id');

    setToken(null);
    setUserType(null);
    setClinicId(null);
    setUser(null);
  };

  const getAuthHeaders = () => ({
    Authorization: `Bearer ${token}`
  });

  return (
    <AuthContext.Provider value={{
      user,
      userType,
      clinicId,
      loading,
      token,
      login,
      logout,
      getAuthHeaders,
      isAuthenticated: !!token
    }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
