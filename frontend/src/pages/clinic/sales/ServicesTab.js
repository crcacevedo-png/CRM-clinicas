import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Card } from '../../../components/ui/card';
import { Button } from '../../../components/ui/button';
import { Input } from '../../../components/ui/input';
import { Label } from '../../../components/ui/label';
import { Textarea } from '../../../components/ui/textarea';
import { Badge } from '../../../components/ui/badge';
import { Switch } from '../../../components/ui/switch';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../../components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../../components/ui/dialog';
import { toast } from 'sonner';
import { Search, Plus, Receipt } from 'lucide-react';
import { API } from './constants';

export default function ServicesTab({ headers }) {
  const [items, setItems] = useState([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [edit, setEdit] = useState(null);
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/clinic/sales/services?q=${encodeURIComponent(search)}`, { headers });
      setItems(r.data || []);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [search, headers]);

  useEffect(() => { load(); }, [load]);

  const openNew = () => { setEdit(null); setForm({ code: '', name: '', description: '', category: '', price: 0, tax_rate: 12, duration_minutes: 30, is_active: true }); setShowForm(true); };
  const openEdit = (s) => { setEdit(s); setForm({ ...s }); setShowForm(true); };

  const handleSave = async () => {
    if (!form.name) { toast.error('Nombre requerido'); return; }
    setSaving(true);
    try {
      if (edit) await axios.put(`${API}/clinic/sales/services/${edit.id}`, form, { headers });
      else await axios.post(`${API}/clinic/sales/services`, form, { headers });
      toast.success(edit ? 'Servicio actualizado' : 'Servicio creado');
      setShowForm(false); load();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error'); }
    finally { setSaving(false); }
  };

  const uf = (k, v) => setForm(p => ({ ...p, [k]: v }));

  return (
    <>
      <div className="flex gap-3 mb-4">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <Input className="pl-9 text-sm" placeholder="Buscar servicio..." value={search} onChange={e => setSearch(e.target.value)} data-testid="service-search" />
        </div>
        <Button className="bg-teal-600 hover:bg-teal-700" onClick={openNew} data-testid="new-service-btn"><Plus className="w-4 h-4 mr-1" />Nuevo servicio</Button>
      </div>

      {loading ? <div className="flex justify-center py-16"><div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" /></div> :
        <Card className="border overflow-hidden">
          <Table>
            <TableHeader><TableRow className="bg-slate-50/80">
              <TableHead className="text-xs font-semibold">Código</TableHead>
              <TableHead className="text-xs font-semibold">Nombre</TableHead>
              <TableHead className="text-xs font-semibold">Categoría</TableHead>
              <TableHead className="text-xs font-semibold text-right">Precio</TableHead>
              <TableHead className="text-xs font-semibold text-center">Duración</TableHead>
              <TableHead className="text-xs font-semibold text-center">Estado</TableHead>
              <TableHead className="text-xs font-semibold text-right"></TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {items.map(s => (
                <TableRow key={s.id} data-testid={`service-row-${s.id}`}>
                  <TableCell className="text-xs font-mono text-slate-500">{s.code || '—'}</TableCell>
                  <TableCell><p className="text-sm font-medium">{s.name}</p>{s.description && <p className="text-xs text-slate-400 truncate max-w-[280px]">{s.description}</p>}</TableCell>
                  <TableCell className="text-xs text-slate-500">{s.category || '—'}</TableCell>
                  <TableCell className="text-right text-sm font-medium">Q{(s.price || 0).toFixed(2)}</TableCell>
                  <TableCell className="text-center text-xs">{s.duration_minutes ? `${s.duration_minutes} min` : '—'}</TableCell>
                  <TableCell className="text-center"><Badge variant="outline" className={`text-xs ${s.is_active ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-600'}`}>{s.is_active ? 'Activo' : 'Inactivo'}</Badge></TableCell>
                  <TableCell className="text-right"><Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => openEdit(s)}>Editar</Button></TableCell>
                </TableRow>
              ))}
              {items.length === 0 && <TableRow><TableCell colSpan={7} className="text-center py-8 text-slate-400"><Receipt className="w-10 h-10 mx-auto mb-2 text-slate-300" />Sin servicios</TableCell></TableRow>}
            </TableBody>
          </Table>
        </Card>}

      <Dialog open={showForm} onOpenChange={setShowForm}>
        <DialogContent className="max-w-md" data-testid="service-form-dialog">
          <DialogHeader><DialogTitle>{edit ? 'Editar' : 'Nuevo'} servicio</DialogTitle></DialogHeader>
          <div className="space-y-3 py-2">
            <div className="grid grid-cols-2 gap-3">
              <div><Label className="text-xs">Código</Label><Input className="mt-1 text-sm" value={form.code || ''} onChange={e => uf('code', e.target.value)} /></div>
              <div><Label className="text-xs">Categoría</Label><Input className="mt-1 text-sm" value={form.category || ''} onChange={e => uf('category', e.target.value)} placeholder="Consultas" /></div>
            </div>
            <div><Label className="text-xs">Nombre *</Label><Input className="mt-1 text-sm" value={form.name || ''} onChange={e => uf('name', e.target.value)} data-testid="service-name-input" /></div>
            <div><Label className="text-xs">Descripción</Label><Textarea className="mt-1 text-sm min-h-[50px]" value={form.description || ''} onChange={e => uf('description', e.target.value)} /></div>
            <div className="grid grid-cols-3 gap-3">
              <div><Label className="text-xs">Precio (Q)</Label><Input type="number" step="0.01" className="mt-1 text-sm" value={form.price ?? ''} onChange={e => uf('price', parseFloat(e.target.value) || 0)} data-testid="service-price-input" /></div>
              <div><Label className="text-xs">IVA (%)</Label><Input type="number" className="mt-1 text-sm" value={form.tax_rate ?? 12} onChange={e => uf('tax_rate', parseFloat(e.target.value) || 0)} /></div>
              <div><Label className="text-xs">Duración (min)</Label><Input type="number" className="mt-1 text-sm" value={form.duration_minutes ?? ''} onChange={e => uf('duration_minutes', parseInt(e.target.value) || null)} /></div>
            </div>
            <label className="flex items-center gap-2 text-sm"><Switch checked={form.is_active} onCheckedChange={v => uf('is_active', v)} />Activo</label>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowForm(false)}>Cancelar</Button>
            <Button className="bg-teal-600 hover:bg-teal-700" onClick={handleSave} disabled={saving} data-testid="save-service-btn">{saving ? '...' : 'Guardar'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
