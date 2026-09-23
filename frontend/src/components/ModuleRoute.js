import { Navigate } from 'react-router-dom';
import { useFeatures } from '../context/FeatureContext';

/**
 * Guards a clinic module route. Redirects to the dashboard when the current
 * member's role does not have the given module enabled. Menu-level RBAC — the
 * backend enforces the same permission on the module's API endpoints.
 */
export function ModuleRoute({ module, children }) {
  const { hasModule, loading } = useFeatures();
  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center h-screen">
        <div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }
  if (!hasModule(module)) {
    return <Navigate to="/dashboard" replace />;
  }
  return children;
}
