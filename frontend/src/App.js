import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { FeatureProvider } from "./context/FeatureContext";
import { BranchProvider } from "./context/BranchContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { ModuleRoute } from "./components/ModuleRoute";
import ErrorBoundary from "./components/ErrorBoundary";
import { Toaster } from "./components/ui/sonner";

// Pages
import LoginPage from "./pages/LoginPage";
import NoAccessPage from "./pages/NoAccessPage";
import ChangePasswordPage from "./pages/ChangePasswordPage";
import ForgotPasswordPage from "./pages/ForgotPasswordPage";
import ResetPasswordPage from "./pages/ResetPasswordPage";

// Admin Pages
import AdminLayout from "./layouts/AdminLayout";
import AdminDashboard from "./pages/admin/AdminDashboard";
import ClinicsPage from "./pages/admin/ClinicsPage";
import ClinicDetailPage from "./pages/admin/ClinicDetailPage";
import UsersPage from "./pages/admin/UsersPage";
import CatalogsPage from "./pages/admin/CatalogsPage";
import SettingsPage from "./pages/admin/SettingsPage";
import PlansPage from "./pages/admin/PlansPage";
import CobrosPage from "./pages/admin/CobrosPage";
import AnnouncementsPage from "./pages/admin/AnnouncementsPage";
import AuditLogPage from "./pages/admin/AuditLogPage";
import SystemHealthPage from "./pages/admin/SystemHealthPage";
import AdminSupportPage from "./pages/admin/AdminSupportPage";

// Clinic Pages
import ClinicLayout from "./layouts/ClinicLayout";
import ClinicDashboardPage from "./pages/clinic/ClinicDashboardPage";
import AgendaPage from "./pages/clinic/AgendaPage";
import PatientsPage from "./pages/clinic/PatientsPage";
import PatientProfilePage from "./pages/clinic/PatientProfilePage";
import MedicalRecordForm from "./pages/clinic/MedicalRecordForm";
import PrescriptionsPage from "./pages/clinic/PrescriptionsPage";
import NewPrescriptionPage from "./pages/clinic/NewPrescriptionPage";
import LabOrdersPage from "./pages/clinic/LabOrdersPage";
import NewLabOrderPage from "./pages/clinic/NewLabOrderPage";
import ClinicSettingsPage from "./pages/clinic/ClinicSettingsPage";
import BranchesPage from "./pages/clinic/BranchesPage";
import InventoryPage from "./pages/clinic/InventoryPage";
import SalesPage from "./pages/clinic/SalesPage";
import AccountsReceivablePage from "./pages/clinic/AccountsReceivablePage";
import ExpensesPage from "./pages/clinic/ExpensesPage";
import CommissionsPage from "./pages/clinic/CommissionsPage";
import ReportsPage from "./pages/clinic/ReportsPage";
import SupportPage from "./pages/clinic/SupportPage";

function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
      <FeatureProvider>
      <BranchProvider>
      <BrowserRouter>
        <Routes>
          {/* Public Routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/no-access" element={<NoAccessPage />} />
          <Route path="/recuperar-password" element={<ForgotPasswordPage />} />
          <Route path="/restablecer-password" element={<ResetPasswordPage />} />

          {/* Self-service password change (authenticated but bypasses type gate) */}
          <Route
            path="/cambiar-password"
            element={
              <ProtectedRoute>
                <ChangePasswordPage />
              </ProtectedRoute>
            }
          />

          {/* Super Admin Routes */}
          <Route
            path="/admin"
            element={
              <ProtectedRoute requiredType="super_admin">
                <AdminLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<AdminDashboard />} />
            <Route path="clinicas" element={<ClinicsPage />} />
            <Route path="clinicas/:id" element={<ClinicDetailPage />} />
            <Route path="usuarios" element={<UsersPage />} />
            <Route path="catalogos" element={<CatalogsPage />} />
            <Route path="planes" element={<PlansPage />} />
            <Route path="cobros" element={<CobrosPage />} />
            <Route path="comunicacion" element={<AnnouncementsPage />} />
            <Route path="auditoria" element={<AuditLogPage />} />
            <Route path="salud" element={<SystemHealthPage />} />
            <Route path="soporte" element={<AdminSupportPage />} />
            <Route path="configuracion" element={<SettingsPage />} />
          </Route>

          {/* Clinic Member Routes */}
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute requiredType="clinic_member">
                <ClinicLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<ClinicDashboardPage />} />
            <Route path="agenda" element={<ModuleRoute module="agenda"><AgendaPage /></ModuleRoute>} />
            <Route path="pacientes" element={<ModuleRoute module="patients"><PatientsPage /></ModuleRoute>} />
            <Route path="pacientes/:id" element={<ModuleRoute module="patients"><PatientProfilePage /></ModuleRoute>} />
            <Route path="pacientes/:patientId/consulta" element={<ModuleRoute module="patients"><MedicalRecordForm /></ModuleRoute>} />
            <Route path="recetas" element={<ModuleRoute module="prescriptions"><PrescriptionsPage /></ModuleRoute>} />
            <Route path="recetas/nueva" element={<ModuleRoute module="prescriptions"><NewPrescriptionPage /></ModuleRoute>} />
            <Route path="laboratorio" element={<ModuleRoute module="lab_orders"><LabOrdersPage /></ModuleRoute>} />
            <Route path="laboratorio/nueva" element={<ModuleRoute module="lab_orders"><NewLabOrderPage /></ModuleRoute>} />
            <Route path="configuracion" element={<ClinicSettingsPage />} />
            <Route path="soporte" element={<SupportPage />} />
            <Route path="sucursales" element={<ModuleRoute module="branches"><BranchesPage /></ModuleRoute>} />
            <Route path="inventario" element={<ModuleRoute module="inventory"><InventoryPage /></ModuleRoute>} />
            <Route path="ventas" element={<ModuleRoute module="sales"><SalesPage /></ModuleRoute>} />
            <Route path="cuentas" element={<ModuleRoute module="accounts_receivable"><AccountsReceivablePage /></ModuleRoute>} />
            <Route path="gastos" element={<ModuleRoute module="expenses"><ExpensesPage /></ModuleRoute>} />
            <Route path="comisiones" element={<ModuleRoute module="commissions"><CommissionsPage /></ModuleRoute>} />
            <Route path="reportes" element={<ModuleRoute module="reports"><ReportsPage /></ModuleRoute>} />
          </Route>

          {/* Default Redirect */}
          <Route path="/" element={<Navigate to="/login" replace />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </BrowserRouter>
      <Toaster position="top-right" />
      </BranchProvider>
      </FeatureProvider>
    </AuthProvider>
    </ErrorBoundary>
  );
}

export default App;

