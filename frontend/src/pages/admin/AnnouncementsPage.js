import { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { useAuth } from '../../context/AuthContext';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../../components/ui/dialog';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../../components/ui/select';
import { Megaphone, Plus, Trash2, Edit, X, AlertTriangle, Info, CheckCircle, Zap, BarChart3, Eye } from 'lucide-react';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const SEVERITIES = [
  { value: 'info', label: 'Informativo', icon: Info, color: 'bg-blue-50 text-blue-700 border-blue-200' },
  { value: 'success', label: 'Éxito', icon: CheckCircle, color: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  { value: 'warning', label: 'Advertencia', icon: AlertTriangle, color: 'bg-amber-50 text-amber-700 border-amber-200' },
  { value: 'critical', label: 'Crítico', icon: Zap, color: 'bg-rose-50 text-rose-700 border-rose-200' },
];

const PLAN_OPTIONS = ['free', 'basic', 'professional', 'enterprise'];
const COUNTRY_OPTIONS = ['guatemala', 'mexico', 'colombia', 'el_salvador', 'honduras', 'nicaragua', 'costa_rica', 'panama'];

const emptyForm = {
  title: '',
  body: '',
  severity: 'info',
  cta_label: '',
  cta_url: '',
  segment_plans: [],
  segment_countries: [],
  is_active: true,
  starts_at: '',
  ends_at: '',
};

export default function AnnouncementsPage() {
  const { getAuthHeaders } = useAuth();
  const headers = useMemo(() => getAuthHeaders(), [getAuthHeaders]);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showDialog, setShowDialog] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);
  const [metrics, setMetrics] = useState(null);
  const [metricsLoading, setMetricsLoading] = useState(false);

  const openMetrics = async (a) => {
    setMetrics({ announcement: { id: a.id, title: a.title, severity: a.severity }, totals: null });
    setMetricsLoading(true);
    try {
      const res = await axios.get(`${API}/admin/announcements/${a.id}/metrics`, { headers });
      setMetrics(res.data);
    } catch {
      toast.error('Error al cargar métricas');
      setMetrics(null);
    } finally {
      setMetricsLoading(false);
    }
  };

  const fetchItems = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/admin/announcements`, { headers });
      setItems(res.data || []);
    } catch {
      toast.error('Error al cargar anuncios');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchItems(); /* eslint-disable-next-line */ }, []);

  const openCreate = () => {
    setEditingId(null);
    setForm(emptyForm);
    setShowDialog(true);
  };

  const openEdit = (a) => {
    setEditingId(a.id);
    setForm({
      title: a.title || '',
      body: a.body || '',
      severity: a.severity || 'info',
      cta_label: a.cta_label || '',
      cta_url: a.cta_url || '',
      segment_plans: a.segment_plans || [],
      segment_countries: a.segment_countries || [],
      is_active: !!a.is_active,
      starts_at: a.starts_at ? a.starts_at.slice(0, 16) : '',
      ends_at: a.ends_at ? a.ends_at.slice(0, 16) : '',
    });
    setShowDialog(true);
  };

  const toggleArr = (key, value) => {
    setForm((prev) => {
      const cur = prev[key] || [];
      return { ...prev, [key]: cur.includes(value) ? cur.filter((x) => x !== value) : [...cur, value] };
    });
  };

  const save = async () => {
    if (!form.title.trim() || !form.body.trim()) {
      toast.error('Título y cuerpo son requeridos');
      return;
    }
    setSaving(true);
    try {
      const payload = {
        ...form,
        segment_plans: form.segment_plans.length ? form.segment_plans : null,
        segment_countries: form.segment_countries.length ? form.segment_countries : null,
        starts_at: form.starts_at ? new Date(form.starts_at).toISOString() : null,
        ends_at: form.ends_at ? new Date(form.ends_at).toISOString() : null,
      };
      if (editingId) {
        await axios.put(`${API}/admin/announcements/${editingId}`, payload, { headers });
        toast.success('Anuncio actualizado');
      } else {
        await axios.post(`${API}/admin/announcements`, payload, { headers });
        toast.success('Anuncio creado');
      }
      setShowDialog(false);
      fetchItems();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Error al guardar');
    } finally {
      setSaving(false);
    }
  };

  const remove = async (a) => {
    if (!window.confirm(`¿Eliminar el anuncio "${a.title}"? Esta acción es irreversible.`)) return;
    try {
      await axios.delete(`${API}/admin/announcements/${a.id}`, { headers });
      toast.success('Anuncio eliminado');
      fetchItems();
    } catch {
      toast.error('Error al eliminar');
    }
  };

  const toggleActive = async (a) => {
    try {
      await axios.put(`${API}/admin/announcements/${a.id}`, { is_active: !a.is_active }, { headers });
      fetchItems();
    } catch {
      toast.error('Error al cambiar estado');
    }
  };

  const sevMeta = (v) => SEVERITIES.find((s) => s.value === v) || SEVERITIES[0];

  return (
    <div className="p-6 space-y-4" data-testid="announcements-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800 flex items-center gap-2">
            <Megaphone className="w-6 h-6 text-teal-600" /> Comunicación
          </h1>
          <p className="text-sm text-slate-500">Anuncios globales para todas las clínicas con segmentación por plan o región.</p>
        </div>
        <Button className="bg-teal-600 hover:bg-teal-700" onClick={openCreate} data-testid="create-announcement-btn">
          <Plus className="w-4 h-4 mr-1.5" /> Nuevo anuncio
        </Button>
      </div>

      <Card className="border border-slate-200">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-semibold text-slate-700">Anuncios ({items.length})</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {loading ? (
            <p className="text-sm text-slate-400">Cargando…</p>
          ) : items.length === 0 ? (
            <p className="text-sm text-slate-400 italic">Aún no hay anuncios. Crea el primero con el botón superior.</p>
          ) : (
            items.map((a) => {
              const sm = sevMeta(a.severity);
              const Sev = sm.icon;
              return (
                <div
                  key={a.id}
                  className={`border rounded-lg p-3 flex items-start gap-3 ${a.is_active ? 'bg-white' : 'bg-slate-50 opacity-70'}`}
                  data-testid={`announcement-${a.id}`}
                >
                  <div className={`p-2 rounded-md border ${sm.color} flex-shrink-0`}>
                    <Sev className="w-4 h-4" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-semibold text-slate-800">{a.title}</span>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full border ${sm.color}`}>{sm.label}</span>
                      {!a.is_active && <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-slate-200 text-slate-600">Inactivo</span>}
                      {(a.segment_plans?.length || a.segment_countries?.length) ? (
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-teal-50 text-teal-700 border border-teal-200">
                          Segmentado
                        </span>
                      ) : (
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200">
                          Global
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-slate-600 mt-1 whitespace-pre-wrap">{a.body}</p>
                    <div className="flex items-center gap-3 mt-1.5 text-[11px] text-slate-400 flex-wrap">
                      {a.segment_plans?.length > 0 && <span>Planes: {a.segment_plans.join(', ')}</span>}
                      {a.segment_countries?.length > 0 && <span>Países: {a.segment_countries.join(', ')}</span>}
                      {a.cta_label && <span>CTA: "{a.cta_label}" → {a.cta_url}</span>}
                      <span className="flex items-center gap-1" title="Clínicas distintas que han visto el anuncio">
                        <Eye className="w-3 h-3" /> {a.clinics_reached || 0} clínicas · {a.users_viewed || 0} usuarios · {a.total_views || 0} vistas
                      </span>
                      <span>· {a.users_dismissed || 0} descartado(s)</span>
                    </div>
                  </div>
                  <div className="flex gap-1 flex-shrink-0">
                    <Button variant="ghost" size="sm" onClick={() => openMetrics(a)} title="Métricas detalladas" data-testid={`metrics-${a.id}`}>
                      <BarChart3 className="w-3.5 h-3.5" />
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => toggleActive(a)} title={a.is_active ? 'Desactivar' : 'Activar'} data-testid={`toggle-${a.id}`}>
                      {a.is_active ? 'Desactivar' : 'Activar'}
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => openEdit(a)} data-testid={`edit-${a.id}`}>
                      <Edit className="w-3.5 h-3.5" />
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => remove(a)} className="text-rose-600 hover:text-rose-700" data-testid={`delete-${a.id}`}>
                      <Trash2 className="w-3.5 h-3.5" />
                    </Button>
                  </div>
                </div>
              );
            })
          )}
        </CardContent>
      </Card>

      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{editingId ? 'Editar anuncio' : 'Nuevo anuncio'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label className="text-xs">Título *</Label>
              <Input className="mt-1 text-sm" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} data-testid="ann-title" />
            </div>
            <div>
              <Label className="text-xs">Cuerpo *</Label>
              <Textarea className="mt-1 text-sm" rows={3} value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} data-testid="ann-body" />
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <Label className="text-xs">Severidad</Label>
                <Select value={form.severity} onValueChange={(v) => setForm({ ...form, severity: v })}>
                  <SelectTrigger className="mt-1 text-sm" data-testid="ann-severity"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {SEVERITIES.map((s) => (<SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs">Activa desde</Label>
                <Input type="datetime-local" className="mt-1 text-sm" value={form.starts_at} onChange={(e) => setForm({ ...form, starts_at: e.target.value })} />
              </div>
              <div>
                <Label className="text-xs">Activa hasta</Label>
                <Input type="datetime-local" className="mt-1 text-sm" value={form.ends_at} onChange={(e) => setForm({ ...form, ends_at: e.target.value })} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs">CTA Etiqueta</Label>
                <Input className="mt-1 text-sm" value={form.cta_label} onChange={(e) => setForm({ ...form, cta_label: e.target.value })} placeholder="Ver planes" />
              </div>
              <div>
                <Label className="text-xs">CTA URL</Label>
                <Input className="mt-1 text-sm" value={form.cta_url} onChange={(e) => setForm({ ...form, cta_url: e.target.value })} placeholder="/dashboard/plan" />
              </div>
            </div>
            <div className="border-t border-slate-200 pt-3">
              <Label className="text-xs font-semibold text-slate-700">Segmentación (vacío = todos)</Label>
              <div className="mt-2">
                <p className="text-[11px] text-slate-500 mb-1">Planes</p>
                <div className="flex flex-wrap gap-1.5">
                  {PLAN_OPTIONS.map((p) => (
                    <button key={p} type="button" onClick={() => toggleArr('segment_plans', p)}
                      className={`px-2.5 py-1 text-xs rounded-md border ${form.segment_plans.includes(p) ? 'bg-teal-600 text-white border-teal-600' : 'bg-white text-slate-600 border-slate-200 hover:border-teal-300'}`}
                      data-testid={`plan-${p}`}>{p}</button>
                  ))}
                </div>
              </div>
              <div className="mt-2">
                <p className="text-[11px] text-slate-500 mb-1">Países</p>
                <div className="flex flex-wrap gap-1.5">
                  {COUNTRY_OPTIONS.map((c) => (
                    <button key={c} type="button" onClick={() => toggleArr('segment_countries', c)}
                      className={`px-2.5 py-1 text-xs rounded-md border ${form.segment_countries.includes(c) ? 'bg-teal-600 text-white border-teal-600' : 'bg-white text-slate-600 border-slate-200 hover:border-teal-300'}`}
                      data-testid={`country-${c}`}>{c.replace('_', ' ')}</button>
                  ))}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2 border-t border-slate-200 pt-3">
              <input type="checkbox" id="ann-active" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
              <Label htmlFor="ann-active" className="text-xs cursor-pointer">Activo (visible para las clínicas)</Label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDialog(false)} disabled={saving}>Cancelar</Button>
            <Button className="bg-teal-600 hover:bg-teal-700" onClick={save} disabled={saving} data-testid="save-announcement">
              {saving ? 'Guardando…' : (editingId ? 'Actualizar' : 'Crear')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Metrics dialog */}
      <Dialog open={!!metrics} onOpenChange={(o) => !o && setMetrics(null)}>
        <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><BarChart3 className="w-4 h-4 text-teal-600" /> Métricas — {metrics?.announcement?.title}</DialogTitle>
          </DialogHeader>
          {metricsLoading || !metrics?.totals ? (
            <p className="text-sm text-slate-400 py-6 text-center">Cargando métricas…</p>
          ) : (
            <div className="space-y-4">
              {/* KPIs */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                {[
                  { label: 'Clínicas alcanzadas', value: metrics.totals.clinics_reached, sub: `de ${metrics.totals.eligible_clinics} elegibles` },
                  { label: '% Cobertura', value: `${metrics.totals.reach_pct}%`, sub: 'clínicas que vieron' },
                  { label: 'Usuarios que vieron', value: metrics.totals.users_viewed, sub: `${metrics.totals.total_views} vistas totales` },
                  { label: 'Tasa de descarte', value: `${metrics.totals.dismiss_rate_pct}%`, sub: `${metrics.totals.clinics_dismissed} clínicas` },
                ].map((k) => (
                  <div key={k.label} className="rounded-lg border border-slate-200 bg-slate-50 p-3" data-testid={`metric-${k.label}`}>
                    <p className="text-[10px] uppercase tracking-wide text-slate-500">{k.label}</p>
                    <p className="text-xl font-bold text-slate-800 mt-0.5">{k.value}</p>
                    <p className="text-[11px] text-slate-400">{k.sub}</p>
                  </div>
                ))}
              </div>

              {/* By Plan */}
              <div className="border border-slate-200 rounded-lg p-3">
                <p className="text-xs font-semibold text-slate-700 mb-2">Por plan</p>
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-slate-500 border-b border-slate-200">
                      <th className="text-left py-1">Plan</th>
                      <th className="text-right">Elegibles</th>
                      <th className="text-right">Vieron</th>
                      <th className="text-right">Descartaron</th>
                      <th className="text-right">% Cobertura</th>
                    </tr>
                  </thead>
                  <tbody>
                    {metrics.by_plan.map((p) => (
                      <tr key={p.plan} className="border-b border-slate-100 last:border-0">
                        <td className="py-1 capitalize">{p.plan}</td>
                        <td className="text-right">{p.eligible}</td>
                        <td className="text-right font-semibold text-teal-700">{p.viewed}</td>
                        <td className="text-right text-rose-600">{p.dismissed}</td>
                        <td className="text-right">{p.eligible ? Math.round((p.viewed / p.eligible) * 100) : 0}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* By Country */}
              <div className="border border-slate-200 rounded-lg p-3">
                <p className="text-xs font-semibold text-slate-700 mb-2">Por país</p>
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-slate-500 border-b border-slate-200">
                      <th className="text-left py-1">País</th>
                      <th className="text-right">Elegibles</th>
                      <th className="text-right">Vieron</th>
                      <th className="text-right">Descartaron</th>
                      <th className="text-right">% Cobertura</th>
                    </tr>
                  </thead>
                  <tbody>
                    {metrics.by_country.map((c) => (
                      <tr key={c.country} className="border-b border-slate-100 last:border-0">
                        <td className="py-1 capitalize">{c.country?.replace('_', ' ') || '—'}</td>
                        <td className="text-right">{c.eligible}</td>
                        <td className="text-right font-semibold text-teal-700">{c.viewed}</td>
                        <td className="text-right text-rose-600">{c.dismissed}</td>
                        <td className="text-right">{c.eligible ? Math.round((c.viewed / c.eligible) * 100) : 0}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Recent clinics */}
              {metrics.recent_clinics?.length > 0 && (
                <div className="border border-slate-200 rounded-lg p-3">
                  <p className="text-xs font-semibold text-slate-700 mb-2">Clínicas más recientes que vieron</p>
                  <ul className="space-y-1">
                    {metrics.recent_clinics.map((c) => (
                      <li key={c.clinic_id} className="text-xs flex items-center justify-between">
                        <span className="text-slate-700">{c.clinic_name}</span>
                        <span className="text-slate-400">{c.plan} · {c.country} · {new Date(c.last_viewed_at).toLocaleString('es-GT')}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setMetrics(null)}>Cerrar</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
