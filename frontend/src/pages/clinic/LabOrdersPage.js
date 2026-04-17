import { useState, useEffect, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import axios from 'axios';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui/table';
import { toast } from 'sonner';
import { Plus, Download, ChevronLeft, ChevronRight, FlaskConical, AlertCircle } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STATUS_MAP = {
  pending: { label: 'Pendiente', class: 'bg-amber-50 text-amber-700 border-amber-200' },
  in_progress: { label: 'En proceso', class: 'bg-blue-50 text-blue-700 border-blue-200' },
  completed: { label: 'Completada', class: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  cancelled: { label: 'Cancelada', class: 'bg-red-50 text-red-600 border-red-200' },
};

const PRIORITY_MAP = {
  routine: { label: 'Rutina', class: 'text-slate-600' },
  urgent: { label: 'Urgente', class: 'text-red-600 font-semibold' },
};

export default function LabOrdersPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { getAuthHeaders } = useAuth();
  const headers = getAuthHeaders();

  const [orders, setOrders] = useState([]);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('all');
  const [loading, setLoading] = useState(true);

  const patientIdParam = searchParams.get('patient_id');

  const fetchOrders = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(page), limit: '15' });
      if (statusFilter !== 'all') params.set('status', statusFilter);
      if (patientIdParam) params.set('patient_id', patientIdParam);
      const res = await axios.get(`${API}/clinic/lab-orders?${params}`, { headers });
      setOrders(res.data.orders || []);
      setTotal(res.data.total || 0);
      setPages(res.data.pages || 1);
    } catch {
      toast.error('Error al cargar órdenes');
    } finally {
      setLoading(false);
    }
  }, [page, statusFilter, patientIdParam]);

  useEffect(() => { fetchOrders(); }, [fetchOrders]);
  useEffect(() => { setPage(1); }, [statusFilter]);

  const formatDate = (d) => {
    if (!d) return '—';
    return new Date(d).toLocaleDateString('es-GT', { day: '2-digit', month: 'short', year: 'numeric' });
  };

  const downloadPdf = async (orderId) => {
    try {
      const res = await axios.get(`${API}/clinic/lab-orders/${orderId}/pdf-url`, { headers });
      if (res.data.url) window.open(res.data.url, '_blank');
      else toast.error('PDF no disponible');
    } catch { toast.error('Error al obtener PDF'); }
  };

  return (
    <div className="p-6 lg:p-8" data-testid="lab-orders-page">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900" data-testid="lab-orders-title">Órdenes de Laboratorio</h1>
          <p className="text-sm text-slate-500 mt-0.5">{total} orden{total !== 1 ? 'es' : ''}</p>
        </div>
        <Button className="bg-teal-600 hover:bg-teal-700 shadow-sm" onClick={() => navigate('/dashboard/laboratorio/nueva')} data-testid="new-lab-order-btn">
          <Plus className="w-4 h-4 mr-1.5" /> Nueva orden
        </Button>
      </div>

      <div className="flex gap-3 mb-5">
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-40" data-testid="lab-status-filter">
            <SelectValue placeholder="Estado" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todas</SelectItem>
            <SelectItem value="pending">Pendientes</SelectItem>
            <SelectItem value="completed">Completadas</SelectItem>
            <SelectItem value="cancelled">Canceladas</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {loading ? (
        <div className="flex justify-center py-16">
          <div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : orders.length === 0 ? (
        <Card className="border-dashed border-2 border-slate-200">
          <CardContent className="p-16 text-center">
            <FlaskConical className="w-12 h-12 text-slate-300 mx-auto mb-3" />
            <p className="text-slate-500 font-medium">No hay órdenes de laboratorio</p>
            <p className="text-sm text-slate-400 mt-1">Crea una nueva orden para comenzar</p>
          </CardContent>
        </Card>
      ) : (
        <>
          <Card className="border border-slate-200 overflow-hidden" data-testid="lab-orders-table">
            <Table>
              <TableHeader>
                <TableRow className="bg-slate-50/80">
                  <TableHead className="text-xs font-semibold text-slate-600">Fecha</TableHead>
                  <TableHead className="text-xs font-semibold text-slate-600">Paciente</TableHead>
                  <TableHead className="text-xs font-semibold text-slate-600">Estudios</TableHead>
                  <TableHead className="text-xs font-semibold text-slate-600 text-center">Cant.</TableHead>
                  <TableHead className="text-xs font-semibold text-slate-600 text-center">Prioridad</TableHead>
                  <TableHead className="text-xs font-semibold text-slate-600 text-center">Estado</TableHead>
                  <TableHead className="text-xs font-semibold text-slate-600 text-right">Acciones</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {orders.map(o => {
                  const st = STATUS_MAP[o.status] || { label: o.status, class: '' };
                  const pr = PRIORITY_MAP[o.priority] || PRIORITY_MAP.routine;
                  return (
                    <TableRow key={o.id} className="hover:bg-teal-50/30 transition-colors" data-testid={`lab-order-row-${o.id}`}>
                      <TableCell className="text-sm">{formatDate(o.ordered_at || o.created_at)}</TableCell>
                      <TableCell className="text-sm font-medium">{o.patient_name}</TableCell>
                      <TableCell className="text-sm text-slate-600 max-w-[250px] truncate">{o.study_summary || '—'}</TableCell>
                      <TableCell className="text-center"><span className="text-sm font-medium">{o.item_count}</span></TableCell>
                      <TableCell className="text-center">
                        <span className={`text-xs ${pr.class}`}>
                          {o.priority === 'urgent' && <AlertCircle className="w-3 h-3 inline mr-0.5" />}
                          {pr.label}
                        </span>
                      </TableCell>
                      <TableCell className="text-center">
                        <Badge variant="outline" className={`text-xs ${st.class}`}>{st.label}</Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center justify-end gap-1">
                          <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => downloadPdf(o.id)} data-testid={`download-lab-pdf-${o.id}`}>
                            <Download className="w-3.5 h-3.5 text-teal-600" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </Card>

          {pages > 1 && (
            <div className="flex items-center justify-between mt-4 px-1">
              <p className="text-xs text-slate-500">Mostrando {(page - 1) * 15 + 1}-{Math.min(page * 15, total)} de {total}</p>
              <div className="flex items-center gap-1">
                <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}><ChevronLeft className="w-4 h-4" /></Button>
                <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => setPage(p => p + 1)}><ChevronRight className="w-4 h-4" /></Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
