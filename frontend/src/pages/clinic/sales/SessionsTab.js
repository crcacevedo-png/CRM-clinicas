import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../../components/ui/card';
import { Button } from '../../../components/ui/button';
import { Input } from '../../../components/ui/input';
import { Label } from '../../../components/ui/label';
import { Badge } from '../../../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../../components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../../components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../../components/ui/dialog';
import { toast } from 'sonner';
import { Plus } from 'lucide-react';
import { API } from './constants';

export default function SessionsTab({ headers, branches, activeBranch }) {
  const [sessions, setSessions] = useState([]);
  const [registers, setRegisters] = useState([]);
  const [showCRForm, setShowCRForm] = useState(false);
  const [crForm, setCrForm] = useState({ name: '', branch_id: '' });
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const branchQS = activeBranch?.id ? `?branch_id=${activeBranch.id}` : '';
      const branchAmp = activeBranch?.id ? `&branch_id=${activeBranch.id}` : '';
      const [s, r] = await Promise.all([
        axios.get(`${API}/clinic/sales/cash-sessions?limit=30${branchAmp}`, { headers }),
        axios.get(`${API}/clinic/sales/cash-registers${branchQS}`, { headers }),
      ]);
      setSessions(s.data.sessions || []);
      setRegisters(r.data || []);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [headers, activeBranch?.id]);

  useEffect(() => { load(); }, [load]);

  const handleCreateCR = async () => {
    if (!crForm.name || !crForm.branch_id) { toast.error('Nombre y sucursal'); return; }
    try {
      await axios.post(`${API}/clinic/sales/cash-registers`, crForm, { headers });
      toast.success('Caja creada');
      setShowCRForm(false); setCrForm({ name: '', branch_id: '' }); load();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error'); }
  };

  return (
    <>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
        <Card className="md:col-span-2">
          <CardHeader className="pb-2"><CardTitle className="text-sm font-semibold flex items-center justify-between">Cajas registradoras
            <Button size="sm" variant="outline" onClick={() => setShowCRForm(true)} data-testid="new-cash-register-btn"><Plus className="w-3.5 h-3.5 mr-1" />Nueva caja</Button>
          </CardTitle></CardHeader>
          <CardContent>
            {registers.length === 0 ? <p className="text-xs text-slate-400">No hay cajas registradas</p> :
              <div className="space-y-1.5">
                {registers.map(r => (
                  <div key={r.id} className="flex items-center justify-between p-2 border rounded text-sm">
                    <div><p className="font-medium">{r.name}</p><p className="text-xs text-slate-500">{r.branch_name}</p></div>
                    <Badge variant="outline" className="text-xs bg-emerald-50 text-emerald-700">Activa</Badge>
                  </div>
                ))}
              </div>}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="pb-2"><CardTitle className="text-sm font-semibold">Historial de sesiones</CardTitle></CardHeader>
        <CardContent>
          {loading ? <div className="flex justify-center py-8"><div className="w-6 h-6 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" /></div> :
            <Table>
              <TableHeader><TableRow className="bg-slate-50/80">
                <TableHead className="text-xs font-semibold">Apertura</TableHead>
                <TableHead className="text-xs font-semibold">Caja / Sucursal</TableHead>
                <TableHead className="text-xs font-semibold">Cajero</TableHead>
                <TableHead className="text-xs font-semibold text-right">Apertura</TableHead>
                <TableHead className="text-xs font-semibold text-right">Esperado</TableHead>
                <TableHead className="text-xs font-semibold text-right">Real</TableHead>
                <TableHead className="text-xs font-semibold text-right">Diferencia</TableHead>
                <TableHead className="text-xs font-semibold text-center">Estado</TableHead>
              </TableRow></TableHeader>
              <TableBody>
                {sessions.map(s => (
                  <TableRow key={s.id} data-testid={`session-row-${s.id}`}>
                    <TableCell className="text-xs">{s.opened_at?.substring(0, 16).replace('T', ' ')}</TableCell>
                    <TableCell className="text-sm"><p>{s.cash_register_name}</p><p className="text-xs text-slate-400">{s.branch_name}</p></TableCell>
                    <TableCell className="text-xs">{s.opened_by_name}</TableCell>
                    <TableCell className="text-right text-sm">Q{(s.opening_amount || 0).toFixed(2)}</TableCell>
                    <TableCell className="text-right text-sm">{s.expected_amount != null ? `Q${(+s.expected_amount).toFixed(2)}` : '—'}</TableCell>
                    <TableCell className="text-right text-sm">{s.actual_amount != null ? `Q${(+s.actual_amount).toFixed(2)}` : '—'}</TableCell>
                    <TableCell className={`text-right text-sm font-medium ${s.difference > 0 ? 'text-blue-600' : s.difference < 0 ? 'text-red-600' : 'text-slate-700'}`}>{s.difference != null ? `Q${(+s.difference).toFixed(2)}` : '—'}</TableCell>
                    <TableCell className="text-center"><Badge variant="outline" className={`text-xs ${s.status === 'open' ? 'bg-amber-50 text-amber-700' : 'bg-slate-50 text-slate-600'}`}>{s.status === 'open' ? 'Abierta' : 'Cerrada'}</Badge></TableCell>
                  </TableRow>
                ))}
                {sessions.length === 0 && <TableRow><TableCell colSpan={8} className="text-center py-8 text-slate-400">Sin sesiones</TableCell></TableRow>}
              </TableBody>
            </Table>}
        </CardContent>
      </Card>

      <Dialog open={showCRForm} onOpenChange={setShowCRForm}>
        <DialogContent className="max-w-sm" data-testid="cash-register-form-dialog">
          <DialogHeader><DialogTitle>Nueva caja</DialogTitle></DialogHeader>
          <div className="space-y-3 py-2">
            <div><Label className="text-xs">Nombre</Label><Input className="mt-1 text-sm" value={crForm.name} onChange={e => setCrForm(f => ({ ...f, name: e.target.value }))} placeholder="Caja Principal" data-testid="cr-name-input" /></div>
            <div>
              <Label className="text-xs">Sucursal</Label>
              <Select value={crForm.branch_id} onValueChange={v => setCrForm(f => ({ ...f, branch_id: v }))}>
                <SelectTrigger className="mt-1 text-sm" data-testid="cr-branch-select"><SelectValue placeholder="Seleccionar" /></SelectTrigger>
                <SelectContent>{(branches || []).map(b => <SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>)}</SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCRForm(false)}>Cancelar</Button>
            <Button className="bg-teal-600 hover:bg-teal-700" onClick={handleCreateCR} data-testid="save-cr-btn">Guardar</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
