import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../context/AuthContext';
import { useBranch } from '../../context/BranchContext';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Badge } from '../../components/ui/badge';
import { Switch } from '../../components/ui/switch';
import { Checkbox } from '../../components/ui/checkbox';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../components/ui/dialog';
import { Separator } from '../../components/ui/separator';
import FeatureGate from '../../components/FeatureGate';
import { toast } from 'sonner';
import { Plus, Edit, MapPin, Users, Star, Building2, Save } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function BranchesPage() {
  const { getAuthHeaders } = useAuth();
  const { refetchBranches } = useBranch();
  const headers = getAuthHeaders();

  const [branches, setBranches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editBranch, setEditBranch] = useState(null);
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);
  const [showMembers, setShowMembers] = useState(null);
  const [branchMembers, setBranchMembers] = useState([]);

  const fetchBranches = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/clinic/branches`, { headers });
      setBranches(res.data || []);
    } catch { toast.error('Error al cargar sucursales'); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchBranches(); }, [fetchBranches]);

  const openNew = () => {
    setEditBranch(null);
    setForm({ name: '', code: '', address: '', city: '', state: '', phone: '', email: '', schedule_start: '08:00', schedule_end: '17:00', is_main: false, is_active: true });
    setShowForm(true);
  };

  const openEdit = (b) => {
    setEditBranch(b);
    setForm({
      name: b.name || '', code: b.code || '', address: b.address || '', city: b.city || '',
      state: b.state || '', phone: b.phone || '', email: b.email || '',
      schedule_start: b.schedule_start?.substring(0, 5) || '08:00',
      schedule_end: b.schedule_end?.substring(0, 5) || '17:00',
      is_main: b.is_main || false, is_active: b.is_active !== false,
    });
    setShowForm(true);
  };

  const handleSave = async () => {
    if (!form.name) { toast.error('Nombre requerido'); return; }
    setSaving(true);
    try {
      if (editBranch) {
        await axios.put(`${API}/clinic/branches/${editBranch.id}`, form, { headers });
        toast.success('Sucursal actualizada');
      } else {
        await axios.post(`${API}/clinic/branches`, form, { headers });
        toast.success('Sucursal creada');
      }
      setShowForm(false);
      fetchBranches();
      refetchBranches();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error'); }
    finally { setSaving(false); }
  };

  const openMembers = async (branch) => {
    setShowMembers(branch);
    try {
      const res = await axios.get(`${API}/clinic/branches/${branch.id}/members`, { headers });
      setBranchMembers(res.data || []);
    } catch { setBranchMembers([]); }
  };

  const toggleMember = (memberId) => {
    setBranchMembers(prev => prev.map(m =>
      m.id === memberId ? { ...m, assigned: !m.assigned, is_primary: !m.assigned ? m.is_primary : false } : m
    ));
  };

  const togglePrimary = (memberId) => {
    setBranchMembers(prev => prev.map(m =>
      m.id === memberId ? { ...m, is_primary: !m.is_primary } : m
    ));
  };

  const saveMembers = async () => {
    if (!showMembers) return;
    try {
      const assigned = branchMembers.filter(m => m.assigned).map(m => ({ member_id: m.id, is_primary: m.is_primary }));
      await axios.put(`${API}/clinic/branches/${showMembers.id}/members`, { members: assigned }, { headers });
      toast.success('Miembros actualizados');
      setShowMembers(null);
      fetchBranches();
    } catch { toast.error('Error'); }
  };

  const uf = (field, value) => setForm(prev => ({ ...prev, [field]: value }));

  return (
    <FeatureGate feature="multi_branch" planRequired="Enterprise">
      <div className="p-6 lg:p-8 max-w-4xl" data-testid="branches-page">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Sucursales</h1>
            <p className="text-sm text-slate-500 mt-0.5">{branches.length} sucursal{branches.length !== 1 ? 'es' : ''}</p>
          </div>
          <Button className="bg-teal-600 hover:bg-teal-700" onClick={openNew} data-testid="new-branch-btn">
            <Plus className="w-4 h-4 mr-1.5" /> Nueva sucursal
          </Button>
        </div>

        {loading ? (
          <div className="flex justify-center py-16"><div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" /></div>
        ) : branches.length === 0 ? (
          <Card className="border-dashed border-2 border-slate-200">
            <CardContent className="p-16 text-center">
              <Building2 className="w-12 h-12 text-slate-300 mx-auto mb-3" />
              <p className="text-slate-500 font-medium">No hay sucursales</p>
              <p className="text-sm text-slate-400 mt-1">Crea tu primera sucursal para comenzar</p>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {branches.map(b => (
              <Card key={b.id} className={`border ${b.is_main ? 'border-teal-300 bg-teal-50/30' : 'border-slate-200'}`} data-testid={`branch-card-${b.id}`}>
                <CardContent className="p-4">
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-sm font-bold text-slate-900">{b.name}</h3>
                        {b.is_main && <Badge className="bg-teal-600 text-white text-xs">Principal</Badge>}
                        {b.code && <Badge variant="outline" className="text-xs">{b.code}</Badge>}
                      </div>
                      <Badge variant="outline" className={`text-xs mt-1 ${b.is_active ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-red-50 text-red-600 border-red-200'}`}>
                        {b.is_active ? 'Activa' : 'Inactiva'}
                      </Badge>
                    </div>
                    <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => openEdit(b)}>
                      <Edit className="w-3 h-3 mr-1" /> Editar
                    </Button>
                  </div>
                  {(b.address || b.city) && (
                    <p className="text-xs text-slate-500 flex items-center gap-1 mb-1">
                      <MapPin className="w-3 h-3" /> {[b.address, b.city, b.state].filter(Boolean).join(', ')}
                    </p>
                  )}
                  {b.phone && <p className="text-xs text-slate-500 mb-1">{b.phone}</p>}
                  <div className="flex items-center justify-between mt-3 pt-2 border-t border-slate-100">
                    <span className="text-xs text-slate-500 flex items-center gap-1">
                      <Users className="w-3 h-3" /> {b.member_count} usuario{b.member_count !== 1 ? 's' : ''}
                    </span>
                    <Button variant="outline" size="sm" className="h-6 text-xs" onClick={() => openMembers(b)} data-testid={`manage-members-${b.id}`}>
                      Gestionar usuarios
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Branch Form Dialog */}
        <Dialog open={showForm} onOpenChange={setShowForm}>
          <DialogContent className="max-w-lg" data-testid="branch-form-dialog">
            <DialogHeader><DialogTitle>{editBranch ? 'Editar sucursal' : 'Nueva sucursal'}</DialogTitle></DialogHeader>
            <div className="space-y-3 py-2">
              <div className="grid grid-cols-2 gap-3">
                <div><Label className="text-xs">Nombre *</Label><Input className="mt-1 text-sm" value={form.name} onChange={e => uf('name', e.target.value)} data-testid="branch-name" /></div>
                <div><Label className="text-xs">Código corto</Label><Input className="mt-1 text-sm" value={form.code} onChange={e => uf('code', e.target.value)} placeholder="ZN10" /></div>
              </div>
              <div><Label className="text-xs">Dirección</Label><Input className="mt-1 text-sm" value={form.address} onChange={e => uf('address', e.target.value)} /></div>
              <div className="grid grid-cols-2 gap-3">
                <div><Label className="text-xs">Ciudad</Label><Input className="mt-1 text-sm" value={form.city} onChange={e => uf('city', e.target.value)} /></div>
                <div><Label className="text-xs">Departamento</Label><Input className="mt-1 text-sm" value={form.state} onChange={e => uf('state', e.target.value)} /></div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div><Label className="text-xs">Teléfono</Label><Input className="mt-1 text-sm" value={form.phone} onChange={e => uf('phone', e.target.value)} /></div>
                <div><Label className="text-xs">Email</Label><Input className="mt-1 text-sm" value={form.email} onChange={e => uf('email', e.target.value)} /></div>
              </div>
              <Separator />
              <div className="grid grid-cols-2 gap-3">
                <div><Label className="text-xs">Hora inicio</Label><Input type="time" className="mt-1 text-sm" value={form.schedule_start} onChange={e => uf('schedule_start', e.target.value)} /></div>
                <div><Label className="text-xs">Hora fin</Label><Input type="time" className="mt-1 text-sm" value={form.schedule_end} onChange={e => uf('schedule_end', e.target.value)} /></div>
              </div>
              <div className="flex items-center justify-between">
                <Label className="text-sm">Sucursal principal</Label>
                <Switch checked={form.is_main} onCheckedChange={v => uf('is_main', v)} data-testid="branch-is-main" />
              </div>
              <div className="flex items-center justify-between">
                <Label className="text-sm">Activa</Label>
                <Switch checked={form.is_active} onCheckedChange={v => uf('is_active', v)} />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowForm(false)}>Cancelar</Button>
              <Button className="bg-teal-600 hover:bg-teal-700" onClick={handleSave} disabled={saving} data-testid="save-branch-btn">
                <Save className="w-4 h-4 mr-1" /> {saving ? 'Guardando...' : 'Guardar'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Members Dialog */}
        <Dialog open={!!showMembers} onOpenChange={() => setShowMembers(null)}>
          <DialogContent className="max-w-md" data-testid="branch-members-dialog">
            <DialogHeader><DialogTitle>Usuarios - {showMembers?.name}</DialogTitle></DialogHeader>
            <div className="py-2">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs w-8"></TableHead>
                    <TableHead className="text-xs">Nombre</TableHead>
                    <TableHead className="text-xs">Rol</TableHead>
                    <TableHead className="text-xs text-center">Principal</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {branchMembers.map(m => (
                    <TableRow key={m.id}>
                      <TableCell><Checkbox checked={m.assigned} onCheckedChange={() => toggleMember(m.id)} /></TableCell>
                      <TableCell className="text-sm">{m.first_name} {m.last_name}</TableCell>
                      <TableCell><Badge variant="outline" className="text-xs">{m.role}</Badge></TableCell>
                      <TableCell className="text-center">
                        {m.assigned && (
                          <button onClick={() => togglePrimary(m.id)} className={`p-0.5 rounded ${m.is_primary ? 'text-amber-500' : 'text-slate-300 hover:text-amber-400'}`}>
                            <Star className="w-4 h-4" fill={m.is_primary ? 'currentColor' : 'none'} />
                          </button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowMembers(null)}>Cancelar</Button>
              <Button className="bg-teal-600 hover:bg-teal-700" onClick={saveMembers} data-testid="save-members-btn">Guardar</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </FeatureGate>
  );
}
