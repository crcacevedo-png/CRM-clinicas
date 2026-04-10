import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../../context/AuthContext';
import { 
  Building2, 
  Users, 
  UserCheck,
  Activity,
  TrendingUp,
  ArrowRight
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function AdminDashboard() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const { getAuthHeaders } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    fetchDashboard();
  }, []);

  const fetchDashboard = async () => {
    try {
      const response = await axios.get(`${API}/admin/dashboard`, {
        headers: getAuthHeaders()
      });
      setStats(response.data);
    } catch (error) {
      console.error('Dashboard fetch error:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleDateString('es-ES', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-screen">
        <div className="text-zinc-500">Cargando...</div>
      </div>
    );
  }

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-semibold text-zinc-950 tracking-tight">Dashboard</h1>
        <p className="text-sm text-zinc-500 mt-1">Resumen general de la plataforma</p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <div className="kpi-card" data-testid="kpi-active-clinics">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Clínicas Activas</p>
              <p className="text-4xl font-mono font-semibold text-zinc-950 tracking-tighter mt-2">
                {stats?.active_clinics || 0}
              </p>
            </div>
            <div className="w-10 h-10 bg-green-100 flex items-center justify-center">
              <Building2 className="w-5 h-5 text-green-600" strokeWidth={1.5} />
            </div>
          </div>
          <div className="mt-4 flex items-center text-xs text-green-600">
            <TrendingUp className="w-3 h-3 mr-1" />
            <span>En funcionamiento</span>
          </div>
        </div>

        <div className="kpi-card" data-testid="kpi-inactive-clinics">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Clínicas Inactivas</p>
              <p className="text-4xl font-mono font-semibold text-zinc-950 tracking-tighter mt-2">
                {stats?.inactive_clinics || 0}
              </p>
            </div>
            <div className="w-10 h-10 bg-red-100 flex items-center justify-center">
              <Building2 className="w-5 h-5 text-red-600" strokeWidth={1.5} />
            </div>
          </div>
          <div className="mt-4 flex items-center text-xs text-red-600">
            <Activity className="w-3 h-3 mr-1" />
            <span>Desactivadas</span>
          </div>
        </div>

        <div className="kpi-card" data-testid="kpi-total-users">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Total Usuarios</p>
              <p className="text-4xl font-mono font-semibold text-zinc-950 tracking-tighter mt-2">
                {stats?.total_users || 0}
              </p>
            </div>
            <div className="w-10 h-10 bg-violet-100 flex items-center justify-center">
              <Users className="w-5 h-5 text-violet-600" strokeWidth={1.5} />
            </div>
          </div>
          <div className="mt-4 flex items-center text-xs text-violet-600">
            <UserCheck className="w-3 h-3 mr-1" />
            <span>En el sistema</span>
          </div>
        </div>

        <div className="kpi-card" data-testid="kpi-total-patients">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider">Total Pacientes</p>
              <p className="text-4xl font-mono font-semibold text-zinc-950 tracking-tighter mt-2">
                {stats?.total_patients || 0}
              </p>
            </div>
            <div className="w-10 h-10 bg-blue-100 flex items-center justify-center">
              <UserCheck className="w-5 h-5 text-blue-600" strokeWidth={1.5} />
            </div>
          </div>
          <div className="mt-4 flex items-center text-xs text-blue-600">
            <Activity className="w-3 h-3 mr-1" />
            <span>Registrados</span>
          </div>
        </div>
      </div>

      {/* Recent Clinics Table */}
      <div className="bg-white border border-zinc-200">
        <div className="px-6 py-4 border-b border-zinc-200 flex items-center justify-between">
          <h2 className="text-lg font-medium text-zinc-900 tracking-tight">Clínicas Recientes</h2>
          <button 
            onClick={() => navigate('/admin/clinicas')}
            className="text-sm text-violet-600 hover:text-violet-700 flex items-center gap-1"
            data-testid="view-all-clinics-btn"
          >
            Ver todas
            <ArrowRight className="w-4 h-4" strokeWidth={1.5} />
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="data-table" data-testid="recent-clinics-table">
            <thead>
              <tr className="bg-zinc-50">
                <th>Nombre</th>
                <th>País</th>
                <th>Plan</th>
                <th>Usuarios</th>
                <th>Pacientes</th>
                <th>Creada</th>
                <th>Estado</th>
              </tr>
            </thead>
            <tbody>
              {stats?.recent_clinics?.length > 0 ? (
                stats.recent_clinics.map((clinic) => (
                  <tr 
                    key={clinic.id} 
                    className="cursor-pointer"
                    onClick={() => navigate(`/admin/clinicas/${clinic.id}`)}
                    data-testid={`clinic-row-${clinic.id}`}
                  >
                    <td className="font-medium text-zinc-900">{clinic.name}</td>
                    <td>{clinic.country}</td>
                    <td>
                      <span className="badge badge-plan">{clinic.plan}</span>
                    </td>
                    <td>{clinic.users_count || 0}</td>
                    <td>{clinic.patients_count || 0}</td>
                    <td>{formatDate(clinic.created_at)}</td>
                    <td>
                      <span className={`badge ${clinic.is_active ? 'badge-active' : 'badge-inactive'}`}>
                        {clinic.is_active ? 'Activa' : 'Inactiva'}
                      </span>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={7} className="text-center py-8 text-zinc-500">
                    No hay clínicas registradas
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
