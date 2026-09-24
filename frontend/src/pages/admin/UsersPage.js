import { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../../context/AuthContext';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '../../components/ui/dropdown-menu';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';
import { 
  Search, 
  MoreVertical, 
  UserCog, 
  Ban, 
  CheckCircle, 
  Key,
  Building2,
  Copy,
  Check,
  Trash2,
  AlertTriangle
} from 'lucide-react';
import { Label } from '../../components/ui/label';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const ROLES = [
  { value: 'clinic_admin', label: 'Administrador' },
  { value: 'doctor', label: 'Doctor' },
  { value: 'nurse', label: 'Enfermero/a' },
  { value: 'receptionist', label: 'Recepcionista' },
  { value: 'staff', label: 'Staff' },
];

export default function UsersPage() {
  const [users, setUsers] = useState([]);
  const [clinics, setClinics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [filterClinic, setFilterClinic] = useState('');
  const [filterRole, setFilterRole] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  
  const [showRoleModal, setShowRoleModal] = useState(false);
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [showMoveModal, setShowMoveModal] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);
  const [newRole, setNewRole] = useState('');
  const [newClinic, setNewClinic] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [copied, setCopied] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null); // user object
  const [deleteConfirmText, setDeleteConfirmText] = useState('');
  const [deleting, setDeleting] = useState(false);

  const { getAuthHeaders } = useAuth();

  useEffect(() => {
    fetchUsers();
    fetchClinics();
  }, [search, filterClinic, filterRole, filterStatus]);

  const fetchUsers = async () => {
    try {
      const params = new URLSearchParams();
      if (search) params.append('search', search);
      if (filterClinic && filterClinic !== 'all') params.append('clinic_id', filterClinic);
      if (filterRole && filterRole !== 'all') params.append('role', filterRole);
      if (filterStatus && filterStatus !== 'all') params.append('status', filterStatus);

      const response = await axios.get(`${API}/admin/users?${params}`, {
        headers: getAuthHeaders()
      });
      setUsers(response.data);
    } catch (error) {
      console.error('Fetch users error:', error);
      toast.error('Error al cargar usuarios');
    } finally {
      setLoading(false);
    }
  };

  const fetchClinics = async () => {
    try {
      const response = await axios.get(`${API}/admin/clinics`, {
        headers: getAuthHeaders()
      });
      setClinics(response.data);
    } catch (error) {
      console.error('Fetch clinics error:', error);
    }
  };

  const handleChangeRole = async () => {
    try {
      await axios.put(`${API}/admin/users/${selectedUser.id}`, 
        { role: newRole },
        { headers: getAuthHeaders() }
      );
      setShowRoleModal(false);
      fetchUsers();
      toast.success('Rol actualizado');
    } catch (error) {
      toast.error('Error al cambiar rol');
    }
  };

  const handleToggleStatus = async (user) => {
    try {
      await axios.put(`${API}/admin/users/${user.id}`, 
        { is_active: !user.is_active },
        { headers: getAuthHeaders() }
      );
      fetchUsers();
      toast.success(user.is_active ? 'Usuario desactivado' : 'Usuario activado');
    } catch (error) {
      toast.error('Error al cambiar estado');
    }
  };

  const handleResetPassword = async () => {
    try {
      const response = await axios.post(`${API}/admin/users/${selectedUser.id}/reset-password`, {}, {
        headers: getAuthHeaders()
      });
      setNewPassword(response.data.new_password);
      setShowPasswordModal(true);
    } catch (error) {
      toast.error('Error al resetear contraseña');
    }
  };

  const handleMoveClinic = async () => {
    try {
      await axios.put(`${API}/admin/users/${selectedUser.id}`, 
        { clinic_id: newClinic },
        { headers: getAuthHeaders() }
      );
      setShowMoveModal(false);
      fetchUsers();
      toast.success('Usuario movido');
    } catch (error) {
      toast.error('Error al mover usuario');
    }
  };

  const copyPassword = () => {
    navigator.clipboard.writeText(newPassword);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    toast.success('Contraseña copiada');
  };

  const handleDeleteUser = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await axios.delete(`${API}/admin/users/${deleteTarget.id}`, {
        headers: getAuthHeaders()
      });
      toast.success(`Usuario "${deleteTarget.name} ${deleteTarget.lastname}" enviado a Papelera (30 días para restaurar)`);
      setDeleteTarget(null);
      setDeleteConfirmText('');
      fetchUsers();
    } catch (error) {
      const msg = error.response?.data?.detail || 'Error al eliminar usuario';
      toast.error(msg);
    } finally {
      setDeleting(false);
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleDateString('es-ES', {
      year: 'numeric', month: 'short', day: 'numeric'
    });
  };

  const getRoleLabel = (role) => {
    return ROLES.find(r => r.value === role)?.label || role;
  };

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-semibold text-zinc-950 tracking-tight">Usuarios</h1>
        <p className="text-sm text-zinc-500 mt-1">Todos los usuarios del sistema</p>
      </div>

      {/* Filters */}
      <div className="bg-white border border-zinc-200 p-4 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" strokeWidth={1.5} />
            <Input
              placeholder="Buscar por nombre o email..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-10 form-input"
              data-testid="search-users-input"
            />
          </div>
          <Select value={filterClinic} onValueChange={setFilterClinic}>
            <SelectTrigger data-testid="filter-clinic">
              <SelectValue placeholder="Clínica" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todas las clínicas</SelectItem>
              {clinics.map(c => (
                <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={filterRole} onValueChange={setFilterRole}>
            <SelectTrigger data-testid="filter-role">
              <SelectValue placeholder="Rol" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos los roles</SelectItem>
              {ROLES.map(r => (
                <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={filterStatus} onValueChange={setFilterStatus}>
            <SelectTrigger data-testid="filter-user-status">
              <SelectValue placeholder="Estado" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos</SelectItem>
              <SelectItem value="active">Activos</SelectItem>
              <SelectItem value="inactive">Inactivos</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white border border-zinc-200">
        <div className="overflow-x-auto">
          <table className="data-table" data-testid="users-table">
            <thead>
              <tr className="bg-zinc-50">
                <th>Nombre</th>
                <th>Email</th>
                <th>Clínica</th>
                <th>Rol</th>
                <th>Estado</th>
                <th>Último login</th>
                <th className="w-12"></th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={7} className="text-center py-8 text-zinc-500">Cargando...</td></tr>
              ) : users.length > 0 ? (
                users.map((user) => (
                  <tr key={user.id} data-testid={`user-row-${user.id}`}>
                    <td className="font-medium text-zinc-900">{user.name} {user.lastname}</td>
                    <td>{user.email}</td>
                    <td>{user.clinic_name}</td>
                    <td><span className="badge badge-plan">{getRoleLabel(user.role)}</span></td>
                    <td>
                      <span className={`badge ${user.is_active ? 'badge-active' : 'badge-inactive'}`}>
                        {user.is_active ? 'Activo' : 'Inactivo'}
                      </span>
                    </td>
                    <td>{formatDate(user.last_login)}</td>
                    <td>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="sm" data-testid={`user-actions-${user.id}`}>
                            <MoreVertical className="w-4 h-4" strokeWidth={1.5} />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => {
                            setSelectedUser(user);
                            setNewRole(user.role);
                            setShowRoleModal(true);
                          }}>
                            <UserCog className="w-4 h-4 mr-2" strokeWidth={1.5} />
                            Cambiar rol
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => handleToggleStatus(user)}>
                            {user.is_active ? (
                              <>
                                <Ban className="w-4 h-4 mr-2" strokeWidth={1.5} />
                                Desactivar
                              </>
                            ) : (
                              <>
                                <CheckCircle className="w-4 h-4 mr-2" strokeWidth={1.5} />
                                Activar
                              </>
                            )}
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => {
                            setSelectedUser(user);
                            handleResetPassword();
                          }}>
                            <Key className="w-4 h-4 mr-2" strokeWidth={1.5} />
                            Resetear contraseña
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => {
                            setSelectedUser(user);
                            setNewClinic('');
                            setShowMoveModal(true);
                          }}>
                            <Building2 className="w-4 h-4 mr-2" strokeWidth={1.5} />
                            Mover a otra clínica
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onClick={() => {
                              setDeleteTarget(user);
                              setDeleteConfirmText('');
                            }}
                            className="text-red-600 focus:text-red-600 focus:bg-red-50"
                            data-testid={`delete-user-${user.id}`}
                          >
                            <Trash2 className="w-4 h-4 mr-2" strokeWidth={1.5} />
                            Enviar a Papelera
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </td>
                  </tr>
                ))
              ) : (
                <tr><td colSpan={7} className="text-center py-8 text-zinc-500">No hay usuarios</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Change Role Modal */}
      <Dialog open={showRoleModal} onOpenChange={setShowRoleModal}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle className="text-xl font-semibold text-zinc-950">Cambiar Rol</DialogTitle>
          </DialogHeader>
          <div className="mt-4 space-y-4">
            <p className="text-sm text-zinc-600">
              Usuario: <span className="font-medium">{selectedUser?.name} {selectedUser?.lastname}</span>
            </p>
            <Select value={newRole} onValueChange={setNewRole}>
              <SelectTrigger data-testid="new-role-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ROLES.map(r => (
                  <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <div className="flex justify-end gap-3">
              <Button variant="outline" onClick={() => setShowRoleModal(false)} className="btn-secondary">
                Cancelar
              </Button>
              <Button onClick={handleChangeRole} className="btn-primary" data-testid="confirm-role-btn">
                Guardar
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Password Modal */}
      <Dialog open={showPasswordModal} onOpenChange={setShowPasswordModal}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle className="text-xl font-semibold text-zinc-950">Nueva Contraseña</DialogTitle>
          </DialogHeader>
          <div className="mt-4">
            <p className="text-sm text-zinc-600 mb-4">
              La contraseña de {selectedUser?.name} ha sido reseteada:
            </p>
            <div className="bg-zinc-50 border border-zinc-200 p-4 font-mono text-sm">
              {newPassword}
            </div>
            <Button onClick={copyPassword} className="w-full mt-4 btn-secondary" data-testid="copy-password-btn">
              {copied ? <Check className="w-4 h-4 mr-2" /> : <Copy className="w-4 h-4 mr-2" />}
              {copied ? 'Copiado' : 'Copiar contraseña'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Move Clinic Modal */}
      <Dialog open={showMoveModal} onOpenChange={setShowMoveModal}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle className="text-xl font-semibold text-zinc-950">Mover a otra Clínica</DialogTitle>
          </DialogHeader>
          <div className="mt-4 space-y-4">
            <p className="text-sm text-zinc-600">
              Usuario: <span className="font-medium">{selectedUser?.name} {selectedUser?.lastname}</span>
            </p>
            <Select value={newClinic} onValueChange={setNewClinic}>
              <SelectTrigger data-testid="new-clinic-select">
                <SelectValue placeholder="Selecciona una clínica" />
              </SelectTrigger>
              <SelectContent>
                {clinics.filter(c => c.id !== selectedUser?.clinic_id).map(c => (
                  <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <div className="flex justify-end gap-3">
              <Button variant="outline" onClick={() => setShowMoveModal(false)} className="btn-secondary">
                Cancelar
              </Button>
              <Button onClick={handleMoveClinic} className="btn-primary" disabled={!newClinic} data-testid="confirm-move-btn">
                Mover
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
      {/* Delete User Confirmation Modal */}
      <Dialog open={!!deleteTarget} onOpenChange={(open) => { if (!open) { setDeleteTarget(null); setDeleteConfirmText(''); } }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="text-xl font-semibold text-red-600 flex items-center gap-2">
              <AlertTriangle className="w-5 h-5" strokeWidth={2} />
              Enviar usuario a la Papelera
            </DialogTitle>
          </DialogHeader>
          <div className="mt-4 space-y-4">
            <div className="bg-amber-50 border border-amber-200 p-3 text-sm text-amber-900">
              <p className="font-medium mb-1">El usuario se moverá a la Papelera por 30 días.</p>
              <p>Se enviará a Papelera al usuario <strong>{deleteTarget?.name} {deleteTarget?.lastname}</strong> ({deleteTarget?.email}) de la clínica <strong>{deleteTarget?.clinic_name}</strong>. Podrás restaurarlo desde <strong>Papelera</strong> antes de 30 días; después se eliminará automáticamente junto con su cuenta de acceso.</p>
            </div>
            <div>
              <Label className="form-label">
                Para confirmar, escribe el email del usuario: <span className="font-mono font-semibold">{deleteTarget?.email}</span>
              </Label>
              <Input
                value={deleteConfirmText}
                onChange={(e) => setDeleteConfirmText(e.target.value)}
                placeholder={deleteTarget?.email || ''}
                className="form-input mt-2"
                autoFocus
                data-testid="delete-user-confirm-input"
              />
            </div>
            <div className="flex justify-end gap-3 pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => { setDeleteTarget(null); setDeleteConfirmText(''); }}
                className="btn-secondary"
                disabled={deleting}
              >
                Cancelar
              </Button>
              <Button
                type="button"
                onClick={handleDeleteUser}
                disabled={deleting || deleteConfirmText.trim().toLowerCase() !== (deleteTarget?.email || '').trim().toLowerCase()}
                className="bg-red-600 hover:bg-red-700 text-white"
                data-testid="confirm-delete-user-btn"
              >
                {deleting ? 'Enviando...' : 'Enviar a Papelera'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
