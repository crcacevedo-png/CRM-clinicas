import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Badge } from './ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './ui/table';
import { Shield, RefreshCw, ChevronLeft, ChevronRight } from 'lucide-react';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const ACTION_COLORS = {
  login_success: 'bg-emerald-100 text-emerald-700',
  login_failed: 'bg-rose-100 text-rose-700',
  login_denied: 'bg-rose-100 text-rose-700',
  member_password_reset: 'bg-amber-100 text-amber-700',
  member_invited: 'bg-blue-100 text-blue-700',
  member_activated: 'bg-emerald-100 text-emerald-700',
  member_deactivated: 'bg-rose-100 text-rose-700',
  patient_archived: 'bg-rose-100 text-rose-700',
  patient_activated: 'bg-emerald-100 text-emerald-700',
  prescription_issued: 'bg-teal-100 text-teal-700',
  clinic_plan_change: 'bg-violet-100 text-violet-700',
  clinic_activated: 'bg-emerald-100 text-emerald-700',
  clinic_deactivated: 'bg-rose-100 text-rose-700',
  clinic_update: 'bg-slate-100 text-slate-700',
  clinic_data_export: 'bg-amber-100 text-amber-700',
};

/**
 * Reusable audit log table. Set `scope='admin'` (super admin, all clinics) or
 * `scope='clinic'` (clinic_admin, scoped to their clinic).
 */
export default function AuditLogTable({ scope = 'clinic', headers }) {
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({ action: 'all', actor_email: '', entity: 'all', since: '', until: '' });
  const [actions, setActions] = useState([]);

  const endpoint = scope === 'admin' ? `${API}/admin/audit-log` : `${API}/clinic/audit-log`;

  const load = useCallback(async (resetPage = false) => {
    setLoading(true);
    const p = resetPage ? 1 : page;
    if (resetPage) setPage(1);
    try {
      const params = { page: p, limit: 50 };
      if (filters.action && filters.action !== 'all') params.action = filters.action;
      if (filters.entity && filters.entity !== 'all') params.entity = filters.entity;
      if (filters.actor_email) params.actor_email = filters.actor_email;
      if (filters.since) params.since = filters.since;
      if (filters.until) params.until = filters.until;
      const res = await axios.get(endpoint, { headers, params });
      setRows(res.data.rows || []);
      setTotal(res.data.total || 0);
      setPages(res.data.pages || 1);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al cargar bitácora');
    } finally {
      setLoading(false);
    }
  }, [endpoint, headers, page, filters]);

  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [page]);

  useEffect(() => {
    if (scope !== 'admin') return;
    axios.get(`${API}/admin/audit-log/actions`, { headers })
      .then(r => setActions(r.data.actions || []))
      .catch(() => {});
  }, [scope, headers]);

  const formatTime = (iso) => {
    try { return new Date(iso).toLocaleString('es-GT', { dateStyle: 'short', timeStyle: 'medium' }); }
    catch { return iso; }
  };

  return (
    <Card data-testid="audit-log-card">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Shield className="w-4 h-4 text-teal-600" />
          Bitácora de auditoría
          <Badge variant="outline" className="text-xs ml-2">{total} eventos</Badge>
        </CardTitle>
        <p className="text-xs text-slate-500 mt-1">
          Registro inmutable de acciones sensibles (inicios de sesión, cambios de contraseña, ediciones, exportaciones). No se puede modificar ni borrar.
        </p>
      </CardHeader>
      <CardContent>
        {/* Filters */}
        <div className="grid grid-cols-1 md:grid-cols-5 gap-2 mb-4">
          <Select value={filters.action} onValueChange={v => setFilters(p => ({ ...p, action: v }))}>
            <SelectTrigger className="text-xs h-8" data-testid="audit-filter-action"><SelectValue placeholder="Acción" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todas las acciones</SelectItem>
              {(scope === 'admin' ? actions : ['login_success','login_failed','member_password_reset','member_invited','member_activated','member_deactivated','patient_archived','prescription_issued','clinic_data_export']).map(a => (
                <SelectItem key={a} value={a}>{a}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input className="text-xs h-8" placeholder="Email actor..." value={filters.actor_email} onChange={e => setFilters(p => ({ ...p, actor_email: e.target.value }))} data-testid="audit-filter-actor" />
          <Input type="date" className="text-xs h-8" value={filters.since} onChange={e => setFilters(p => ({ ...p, since: e.target.value }))} data-testid="audit-filter-since" />
          <Input type="date" className="text-xs h-8" value={filters.until} onChange={e => setFilters(p => ({ ...p, until: e.target.value }))} data-testid="audit-filter-until" />
          <Button size="sm" className="h-8 bg-teal-600 hover:bg-teal-700 text-xs" onClick={() => load(true)} disabled={loading} data-testid="audit-search-btn">
            <RefreshCw className={`w-3 h-3 mr-1 ${loading ? 'animate-spin' : ''}`} />
            Filtrar
          </Button>
        </div>

        {/* Table */}
        <div className="rounded-md border overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-xs">Fecha</TableHead>
                <TableHead className="text-xs">Acción</TableHead>
                <TableHead className="text-xs">Entidad</TableHead>
                <TableHead className="text-xs">Actor</TableHead>
                <TableHead className="text-xs">IP</TableHead>
                {scope === 'admin' && <TableHead className="text-xs">Clínica</TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading && (
                <TableRow><TableCell colSpan={scope === 'admin' ? 6 : 5} className="text-center text-xs text-slate-400 py-6">Cargando…</TableCell></TableRow>
              )}
              {!loading && rows.length === 0 && (
                <TableRow><TableCell colSpan={scope === 'admin' ? 6 : 5} className="text-center text-xs text-slate-400 py-6">No hay eventos</TableCell></TableRow>
              )}
              {rows.map(r => (
                <TableRow key={r.id} data-testid={`audit-row-${r.action}`}>
                  <TableCell className="text-xs text-slate-600 whitespace-nowrap">{formatTime(r.occurred_at)}</TableCell>
                  <TableCell>
                    <Badge className={`text-[10px] ${ACTION_COLORS[r.action] || 'bg-slate-100 text-slate-700'}`}>{r.action}</Badge>
                  </TableCell>
                  <TableCell className="text-xs text-slate-700">
                    {r.entity || '-'}
                    {r.entity_id && <span className="text-[10px] text-slate-400 block">{r.entity_id.slice(0, 8)}</span>}
                  </TableCell>
                  <TableCell className="text-xs">
                    <div className="text-slate-800">{r.actor_email || '-'}</div>
                    {r.actor_role && <span className="text-[10px] text-slate-400">{r.actor_role}</span>}
                  </TableCell>
                  <TableCell className="text-xs text-slate-500 font-mono">{r.ip_address || '-'}</TableCell>
                  {scope === 'admin' && (
                    <TableCell className="text-[10px] text-slate-500 font-mono">{r.clinic_id ? r.clinic_id.slice(0, 8) : '-'}</TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        {/* Pagination */}
        {pages > 1 && (
          <div className="flex items-center justify-between mt-3 text-xs text-slate-500">
            <span>Página {page} de {pages}</span>
            <div className="flex gap-1">
              <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1 || loading} data-testid="audit-prev-btn">
                <ChevronLeft className="w-3 h-3" />
              </Button>
              <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => setPage(p => Math.min(pages, p + 1))} disabled={page >= pages || loading} data-testid="audit-next-btn">
                <ChevronRight className="w-3 h-3" />
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
