import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useAuth } from '../../context/AuthContext';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../../components/ui/dialog';
import { Trash2, RotateCcw, AlertTriangle, Building2, Users as UsersIcon, Clock } from 'lucide-react';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function TrashPage() {
  const { getAuthHeaders } = useAuth();
  const [tab, setTab] = useState('clinics');
  const [data, setData] = useState({ clinics: [], users: [] });
  const [loading, setLoading] = useState(true);
  const [purgeTarget, setPurgeTarget] = useState(null); // { type: 'clinic'|'user', item }
  const [confirmText, setConfirmText] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/admin/trash`, { headers: getAuthHeaders() });
      setData(r.data || { clinics: [], users: [] });
    } catch (e) {
      toast.error('Error al cargar papelera');
    } finally { setLoading(false); }
  }, [getAuthHeaders]);

  useEffect(() => { load(); }, [load]);

  const restoreClinic = async (id) => {
    try {
      await axios.post(`${API}/admin/trash/clinics/${id}/restore`, {}, { headers: getAuthHeaders() });
      toast.success('Clínica restaurada');
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Error al restaurar');
    }
  };

  const restoreUser = async (id) => {
    try {
      await axios.post(`${API}/admin/trash/users/${id}/restore`, {}, { headers: getAuthHeaders() });
      toast.success('Usuario restaurado');
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Error al restaurar');
    }
  };

  const purgeNow = async () => {
    if (!purgeTarget) return;
    setBusy(true);
    try {
      const { type, item } = purgeTarget;
      if (type === 'clinic') {
        await axios.delete(`${API}/admin/trash/clinics/${item.id}`, { headers: getAuthHeaders() });
        toast.success('Clínica purgada permanentemente');
      } else {
        await axios.delete(`${API}/admin/trash/users/${item.id}`, { headers: getAuthHeaders() });
        toast.success('Usuario purgado permanentemente');
      }
      setPurgeTarget(null); setConfirmText('');
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Error al purgar');
    } finally { setBusy(false); }
  };

  const formatDeleted = (iso) => {
    if (!iso) return '—';
    return new Date(iso).toLocaleString('es-ES', { dateStyle: 'short', timeStyle: 'short' });
  };

  const purgeConfirmValue = purgeTarget?.type === 'clinic'
    ? (purgeTarget.item?.name || '')
    : (purgeTarget?.item?.email || '');

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-semibold text-zinc-950 tracking-tight flex items-center gap-2">
            <Trash2 className="w-7 h-7 text-red-500" strokeWidth={1.5} />
            Papelera
          </h1>
          <p className="text-sm text-zinc-500 mt-1">
            Clínicas y usuarios eliminados. Se purgan automáticamente después de <strong>30 días</strong>.
          </p>
        </div>
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="bg-zinc-100 mb-4">
          <TabsTrigger value="clinics" data-testid="trash-tab-clinics">
            <Building2 className="w-4 h-4 mr-1.5" strokeWidth={1.5} />
            Clínicas ({data.clinics.length})
          </TabsTrigger>
          <TabsTrigger value="users" data-testid="trash-tab-users">
            <UsersIcon className="w-4 h-4 mr-1.5" strokeWidth={1.5} />
            Usuarios ({data.users.length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="clinics">
          <div className="bg-white border border-zinc-200 overflow-hidden">
            <table className="data-table w-full" data-testid="trash-clinics-table">
              <thead>
                <tr className="bg-zinc-50">
                  <th className="text-left">Nombre</th>
                  <th className="text-left">País</th>
                  <th className="text-left">Plan</th>
                  <th className="text-left">Eliminada</th>
                  <th className="text-left">Por</th>
                  <th className="text-center">Días restantes</th>
                  <th className="text-right">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr><td colSpan={7} className="text-center py-8 text-zinc-500">Cargando...</td></tr>
                ) : data.clinics.length > 0 ? data.clinics.map(c => (
                  <tr key={c.id} data-testid={`trash-clinic-row-${c.id}`}>
                    <td className="font-medium text-zinc-900">{c.name}</td>
                    <td>{c.country || '—'}</td>
                    <td><span className="badge badge-plan">{c.plan}</span></td>
                    <td className="text-xs text-zinc-500">{formatDeleted(c.deleted_at)}</td>
                    <td className="text-xs text-zinc-500">{c.deleted_by || '—'}</td>
                    <td className="text-center">
                      <span className={`inline-flex items-center gap-1 text-xs font-medium ${c.days_left <= 3 ? 'text-red-600' : c.days_left <= 7 ? 'text-amber-600' : 'text-emerald-600'}`}>
                        <Clock className="w-3 h-3" strokeWidth={2} />
                        {c.days_left} días
                      </span>
                    </td>
                    <td className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => restoreClinic(c.id)}
                          data-testid={`restore-clinic-${c.id}`}
                        >
                          <RotateCcw className="w-3.5 h-3.5 mr-1" strokeWidth={2} />
                          Restaurar
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          className="text-red-600 border-red-200 hover:bg-red-50 hover:text-red-700"
                          onClick={() => { setPurgeTarget({ type: 'clinic', item: c }); setConfirmText(''); }}
                          data-testid={`purge-clinic-${c.id}`}
                        >
                          <Trash2 className="w-3.5 h-3.5 mr-1" strokeWidth={2} />
                          Purgar ahora
                        </Button>
                      </div>
                    </td>
                  </tr>
                )) : (
                  <tr><td colSpan={7} className="text-center py-12 text-zinc-400">
                    <Trash2 className="w-10 h-10 mx-auto mb-2 opacity-30" strokeWidth={1} />
                    Papelera vacía
                  </td></tr>
                )}
              </tbody>
            </table>
          </div>
        </TabsContent>

        <TabsContent value="users">
          <div className="bg-white border border-zinc-200 overflow-hidden">
            <table className="data-table w-full" data-testid="trash-users-table">
              <thead>
                <tr className="bg-zinc-50">
                  <th className="text-left">Nombre</th>
                  <th className="text-left">Email</th>
                  <th className="text-left">Clínica</th>
                  <th className="text-left">Rol</th>
                  <th className="text-left">Eliminado</th>
                  <th className="text-center">Días restantes</th>
                  <th className="text-right">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr><td colSpan={7} className="text-center py-8 text-zinc-500">Cargando...</td></tr>
                ) : data.users.length > 0 ? data.users.map(u => (
                  <tr key={u.id} data-testid={`trash-user-row-${u.id}`}>
                    <td className="font-medium text-zinc-900">{u.name} {u.lastname}</td>
                    <td className="text-sm">{u.email || '—'}</td>
                    <td>{u.clinic_name}</td>
                    <td><span className="badge badge-plan">{u.role}</span></td>
                    <td className="text-xs text-zinc-500">{formatDeleted(u.deleted_at)}</td>
                    <td className="text-center">
                      <span className={`inline-flex items-center gap-1 text-xs font-medium ${u.days_left <= 3 ? 'text-red-600' : u.days_left <= 7 ? 'text-amber-600' : 'text-emerald-600'}`}>
                        <Clock className="w-3 h-3" strokeWidth={2} />
                        {u.days_left} días
                      </span>
                    </td>
                    <td className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => restoreUser(u.id)}
                          data-testid={`restore-user-${u.id}`}
                        >
                          <RotateCcw className="w-3.5 h-3.5 mr-1" strokeWidth={2} />
                          Restaurar
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          className="text-red-600 border-red-200 hover:bg-red-50 hover:text-red-700"
                          onClick={() => { setPurgeTarget({ type: 'user', item: u }); setConfirmText(''); }}
                          data-testid={`purge-user-${u.id}`}
                        >
                          <Trash2 className="w-3.5 h-3.5 mr-1" strokeWidth={2} />
                          Purgar ahora
                        </Button>
                      </div>
                    </td>
                  </tr>
                )) : (
                  <tr><td colSpan={7} className="text-center py-12 text-zinc-400">
                    <Trash2 className="w-10 h-10 mx-auto mb-2 opacity-30" strokeWidth={1} />
                    Papelera vacía
                  </td></tr>
                )}
              </tbody>
            </table>
          </div>
        </TabsContent>
      </Tabs>

      {/* Purge confirmation dialog */}
      <Dialog open={!!purgeTarget} onOpenChange={(open) => { if (!open) { setPurgeTarget(null); setConfirmText(''); } }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="text-xl font-semibold text-red-600 flex items-center gap-2">
              <AlertTriangle className="w-5 h-5" strokeWidth={2} />
              Purgar permanentemente
            </DialogTitle>
          </DialogHeader>
          <div className="mt-4 space-y-4">
            <div className="bg-red-50 border border-red-200 p-3 text-sm text-red-800">
              <p className="font-medium mb-1">Esta acción es IRREVERSIBLE y saltará los 30 días de gracia.</p>
              {purgeTarget?.type === 'clinic' ? (
                <p>Se eliminarán todos los datos de <strong>{purgeTarget.item?.name}</strong>: pacientes, citas, recetas, ventas, inventario, usuarios y sus cuentas de acceso.</p>
              ) : (
                <p>Se eliminará el usuario <strong>{purgeTarget?.item?.name} {purgeTarget?.item?.lastname}</strong> junto con su cuenta de acceso.</p>
              )}
            </div>
            <div>
              <Label className="form-label">
                Para confirmar, escribe: <span className="font-mono font-semibold">{purgeConfirmValue}</span>
              </Label>
              <Input
                value={confirmText}
                onChange={(e) => setConfirmText(e.target.value)}
                placeholder={purgeConfirmValue}
                className="form-input mt-2"
                autoFocus
                data-testid="purge-confirm-input"
              />
            </div>
            <div className="flex justify-end gap-3 pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => { setPurgeTarget(null); setConfirmText(''); }}
                disabled={busy}
              >
                Cancelar
              </Button>
              <Button
                type="button"
                onClick={purgeNow}
                disabled={busy || confirmText.trim().toLowerCase() !== purgeConfirmValue.trim().toLowerCase()}
                className="bg-red-600 hover:bg-red-700 text-white"
                data-testid="purge-confirm-btn"
              >
                {busy ? 'Purgando...' : 'Purgar permanentemente'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
