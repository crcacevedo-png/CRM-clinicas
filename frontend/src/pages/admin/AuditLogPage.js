import { useAuth } from '../../context/AuthContext';
import AuditLogTable from '../../components/AuditLogTable';

export default function AuditLogPage() {
  const { getAuthHeaders } = useAuth();
  const headers = getAuthHeaders();
  return (
    <div className="space-y-6" data-testid="admin-audit-log-page">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Bitácora de auditoría</h1>
        <p className="text-sm text-slate-500 mt-1">
          Registro inmutable de eventos críticos en todo el sistema (todas las clínicas).
        </p>
      </div>
      <AuditLogTable scope="admin" headers={headers} />
    </div>
  );
}
