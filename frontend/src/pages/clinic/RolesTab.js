import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useAuth } from '../../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
import { Badge } from '../../components/ui/badge';
import { Checkbox } from '../../components/ui/checkbox';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui/table';
import { toast } from 'sonner';
import { Shield, Plus, Edit, Trash2, Lock, Users } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function RolesTab() {
  const { getAuthHeaders } = useAuth();
  const headers = getAuthHeaders();
  const [roles, setRoles] = useState([]);
  const [modulesCatalog, setModulesCatalog] = useState([]);
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editRole, setEditRole] = useState(null);
  const [form, setForm] = useState({ name: '', description: '', modules: [] });
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const [r, m] = await Promise.all([
        axios.get(`${API}/clinic/roles`, { headers }),
        axios.get(`${API}/clinic/members`, { headers }),
      ]);
      setRoles(r.data.roles || []);
      setModulesCatalog(r.data.modules || []);
      setMembers((m.data || []).filter((x) => x.is_active));
    } catch {
      toast.error('Error al cargar roles');
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { load(); }, [load]);

  const openNew = () => { setForm({ name: '', description: '', modules: [] }); setEditRole({ new: true }); };
  const openEdit = (role) => {
    setForm({ name: role.name, description: role.description || '', modules: [...(role.modules || [])] });
    setEditRole(role);
  };
  const toggleModule = (key) =>
    setForm((f) => ({ ...f, modules: f.modules.includes(key) ? f.modules.filter((k) => k !== key) : [...f.modules, key] }));

  const save = async () => {
    if (editRole?.new && !form.name.trim()) { toast.error('El nombre es requerido'); return; }
    setSaving(true);
    try {
      if (editRole?.new) {
        await axios.post(`${API}/clinic/roles`, { name: form.name, description: form.description, modules: form.modules }, { headers });
        toast.success('Rol creado');
      } else {
        await axios.put(`${API}/clinic/roles/${editRole.id}`, { name: form.name, description: form.description, modules: form.modules }, { headers });
        toast.success('Rol actualizado');
      }
      setEditRole(null);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Error al guardar el rol');
    } finally {
      setSaving(false);
    }
  };

  const del = async (role) => {
    if (!window.confirm(`¿Eliminar el rol "${role.name}"?`)) return;
    try {
      await axios.delete(`${API}/clinic/roles/${role.id}`, { headers });
      toast.success('Rol eliminado');
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Error al eliminar el rol');
    }
  };

  const assignRole = async (memberId, roleKey) => {
    try {
      await axios.put(`${API}/clinic/members/${memberId}/role`, { role: roleKey }, { headers });
      toast.success('Rol asignado');
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Error al asignar el rol');
    }
  };

  const modLabel = (key) => modulesCatalog.find((m) => m.key === key)?.label || key;

  if (loading) return <div className="py-10 text-center text-slate-400" data-testid="roles-loading">Cargando roles…</div>;

  return (
    <div className="space-y-6" data-testid="roles-tab">
      {/* ===== Roles list ===== */}
      <Card className="border border-slate-200">
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="text-base flex items-center gap-2">
              <Shield className="w-4 h-4 text-teal-600" /> Roles y permisos
            </CardTitle>
            <p className="text-xs text-slate-500 mt-1">Define qué módulos del menú puede ver cada rol.</p>
          </div>
          <Button size="sm" className="bg-teal-600 hover:bg-teal-700 text-white" onClick={openNew} data-testid="new-role-btn">
            <Plus className="w-4 h-4 mr-1" /> Nuevo rol
          </Button>
        </CardHeader>
        <CardContent className="space-y-3">
          {roles.map((role) => (
            <div key={role.id} className="border border-slate-200 rounded-lg p-3 flex items-start justify-between gap-3" data-testid={`role-row-${role.key}`}>
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-semibold text-slate-800">{role.name}</span>
                  {role.is_system
                    ? <Badge variant="outline" className="text-[10px]">Sistema</Badge>
                    : <Badge className="bg-teal-100 text-teal-700 border-0 text-[10px]">Personalizado</Badge>}
                  <span className="text-xs text-slate-400 flex items-center gap-1"><Users className="w-3 h-3" />{role.member_count}</span>
                </div>
                {role.description && <p className="text-xs text-slate-500 mt-0.5">{role.description}</p>}
                <div className="flex flex-wrap gap-1 mt-2">
                  {role.locked
                    ? <span className="text-xs text-slate-500 flex items-center gap-1"><Lock className="w-3 h-3" /> Acceso total (no editable)</span>
                    : (role.modules.length
                      ? role.modules.map((k) => <Badge key={k} variant="secondary" className="text-[10px] font-normal">{modLabel(k)}</Badge>)
                      : <span className="text-xs text-slate-400">Sin módulos asignados</span>)}
                </div>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                {role.locked ? (
                  <Lock className="w-4 h-4 text-slate-300" />
                ) : (
                  <>
                    <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => openEdit(role)} data-testid={`edit-role-${role.key}`}>
                      <Edit className="w-4 h-4" />
                    </Button>
                    {!role.is_system && (
                      <Button size="icon" variant="ghost" className="h-8 w-8 text-red-500 hover:text-red-600" onClick={() => del(role)} data-testid={`delete-role-${role.key}`}>
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    )}
                  </>
                )}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      {/* ===== Member assignment ===== */}
      <Card className="border border-slate-200">
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Users className="w-4 h-4 text-teal-600" /> Asignación de roles al equipo
          </CardTitle>
          <p className="text-xs text-slate-500 mt-1">Cambia el rol de cada miembro. El acceso se actualiza al instante.</p>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Miembro</TableHead>
                <TableHead className="w-[220px]">Rol</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {members.map((m) => (
                <TableRow key={m.id} data-testid={`member-assign-${m.id}`}>
                  <TableCell>
                    <div className="font-medium text-slate-800">{m.first_name} {m.last_name}</div>
                    <div className="text-xs text-slate-400">{m.email}</div>
                  </TableCell>
                  <TableCell>
                    <Select value={m.role} onValueChange={(v) => assignRole(m.id, v)}>
                      <SelectTrigger className="w-[200px] h-9" data-testid={`member-role-select-${m.id}`}>
                        <SelectValue placeholder="Sin rol" />
                      </SelectTrigger>
                      <SelectContent>
                        {roles.map((r) => <SelectItem key={r.key} value={r.key}>{r.name}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* ===== Create / Edit dialog ===== */}
      {editRole && (
        <Dialog open onOpenChange={() => setEditRole(null)}>
          <DialogContent className="max-w-lg" data-testid="role-dialog">
            <DialogHeader>
              <DialogTitle>{editRole.new ? 'Nuevo rol' : `Editar rol: ${editRole.name}`}</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-2">
              <div>
                <Label className="text-xs">Nombre *</Label>
                <Input
                  className="mt-1"
                  value={form.name}
                  disabled={!editRole.new && editRole.is_system}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  data-testid="role-name-input"
                />
                {!editRole.new && editRole.is_system && (
                  <p className="text-[11px] text-slate-400 mt-1">El nombre de un rol del sistema no se puede cambiar.</p>
                )}
              </div>
              <div>
                <Label className="text-xs">Descripción</Label>
                <Textarea
                  className="mt-1"
                  rows={2}
                  value={form.description}
                  disabled={!editRole.new && editRole.is_system}
                  onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                  data-testid="role-desc-input"
                />
              </div>
              <div>
                <Label className="text-xs mb-2 block">Módulos con acceso</Label>
                <div className="grid grid-cols-2 gap-2">
                  {modulesCatalog.map((mod) => (
                    <label
                      key={mod.key}
                      className="flex items-center gap-2 text-sm cursor-pointer border border-slate-200 rounded-md px-2 py-1.5 hover:bg-slate-50"
                      data-testid={`module-row-${mod.key}`}
                    >
                      <Checkbox
                        checked={form.modules.includes(mod.key)}
                        onCheckedChange={() => toggleModule(mod.key)}
                        data-testid={`module-checkbox-${mod.key}`}
                      />
                      <span>{mod.label}</span>
                    </label>
                  ))}
                </div>
                <p className="text-[11px] text-slate-400 mt-2">Panel y Configuración siempre están disponibles para todos los roles.</p>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setEditRole(null)}>Cancelar</Button>
              <Button className="bg-teal-600 hover:bg-teal-700 text-white" onClick={save} disabled={saving} data-testid="save-role-btn">
                {saving ? 'Guardando…' : 'Guardar'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}
