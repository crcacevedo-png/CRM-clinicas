import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { FeatureProvider } from "./context/FeatureContext";
import { BranchProvider } from "./context/BranchContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { Toaster } from "./components/ui/sonner";

// Pages
import LoginPage from "./pages/LoginPage";
import NoAccessPage from "./pages/NoAccessPage";

// Admin Pages
import AdminLayout from "./layouts/AdminLayout";
import AdminDashboard from "./pages/admin/AdminDashboard";
import ClinicsPage from "./pages/admin/ClinicsPage";
import ClinicDetailPage from "./pages/admin/ClinicDetailPage";
import UsersPage from "./pages/admin/UsersPage";
import CatalogsPage from "./pages/admin/CatalogsPage";
import SettingsPage from "./pages/admin/SettingsPage";
import PlansPage from "./pages/admin/PlansPage";

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

function App() {
  return (
    <AuthProvider>
      <FeatureProvider>
      <BranchProvider>
      <BrowserRouter>
        <Routes>
          {/* Public Routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/no-access" element={<NoAccessPage />} />

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
            <Route path="agenda" element={<AgendaPage />} />
            <Route path="pacientes" element={<PatientsPage />} />
            <Route path="pacientes/:id" element={<PatientProfilePage />} />
            <Route path="pacientes/:patientId/consulta" element={<MedicalRecordForm />} />
            <Route path="recetas" element={<PrescriptionsPage />} />
            <Route path="recetas/nueva" element={<NewPrescriptionPage />} />
            <Route path="laboratorio" element={<LabOrdersPage />} />
            <Route path="laboratorio/nueva" element={<NewLabOrderPage />} />
            <Route path="configuracion" element={<ClinicSettingsPage />} />
            <Route path="sucursales" element={<BranchesPage />} />
            <Route path="inventario" element={<InventoryPage />} />
            <Route path="ventas" element={<SalesPage />} />
            <Route path="cuentas" element={<AccountsReceivablePage />} />
            <Route path="gastos" element={<ExpensesPage />} />
            <Route path="comisiones" element={<CommissionsPage />} />
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
  );
}

export default App;

