import { useState, useEffect, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import axios from 'axios';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Badge } from '../../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui/table';
import { toast } from 'sonner';
import { Plus, Search, FileText, Download, ChevronLeft, ChevronRight, Send, Pill, Copy, MessageCircle } from 'lucide-react';
import { shareViaWhatsApp } from '../../lib/whatsappShare';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STATUS_MAP = {
  draft: { label: 'Borrador', class: 'bg-amber-50 text-amber-700 border-amber-200' },
  issued: { label: 'Emitida', class: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
};

export default function PrescriptionsPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { getAuthHeaders } = useAuth();
  const headers = getAuthHeaders();

  const [prescriptions, setPrescriptions] = useState([]);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('all');
  const [loading, setLoading] = useState(true);

  const patientIdParam = searchParams.get('patient_id');

  const fetchPrescriptions = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(page), limit: '15' });
      if (statusFilter !== 'all') params.set('status', statusFilter);
      if (patientIdParam) params.set('patient_id', patientIdParam);
      const res = await axios.get(`${API}/clinic/prescriptions?${params}`, { headers });
      setPrescriptions(res.data.prescriptions || []);
      setTotal(res.data.total || 0);
      setPages(res.data.pages || 1);
    } catch {
      toast.error('Error al cargar recetas');
    } finally {
      setLoading(false);
    }
  }, [page, statusFilter, patientIdParam]);

  useEffect(() => { fetchPrescriptions(); }, [fetchPrescriptions]);
  useEffect(() => { setPage(1); }, [statusFilter]);

  const formatDate = (d) => {
    if (!d) return '—';
    return new Date(d).toLocaleDateString('es-GT', { day: '2-digit', month: 'short', year: 'numeric' });
  };

  const downloadPdf = async (prescId) => {
    try {
      const res = await axios.get(`${API}/clinic/prescriptions/${prescId}/pdf-url`, { headers });
      if (res.data.url) window.open(res.data.url, '_blank');
      else toast.error('PDF no disponible');
    } catch {
      toast.error('Error al obtener PDF');
    }
  };

  return (
    <div className="p-6 lg:p-8" data-testid="prescriptions-page">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900" data-testid="prescriptions-title">Recetas Médicas</h1>
          <p className="text-sm text-slate-500 mt-0.5">{total} receta{total !== 1 ? 's' : ''}</p>
        </div>
        <Button className="bg-teal-600 hover:bg-teal-700 shadow-sm" onClick={() => navigate('/dashboard/recetas/nueva')} data-testid="new-prescription-btn">
          <Plus className="w-4 h-4 mr-1.5" /> Nueva receta
        </Button>
      </div>

      <div className="flex gap-3 mb-5">
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-40" data-testid="prescription-status-filter">
            <SelectValue placeholder="Estado" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todas</SelectItem>
            <SelectItem value="draft">Borradores</SelectItem>
            <SelectItem value="issued">Emitidas</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {loading ? (
        <div className="flex justify-center py-16">
          <div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : prescriptions.length === 0 ? (
        <Card className="border-dashed border-2 border-slate-200">
          <CardContent className="p-16 text-center">
            <Pill className="w-12 h-12 text-slate-300 mx-auto mb-3" />
            <p className="text-slate-500 font-medium">No hay recetas</p>
            <p className="text-sm text-slate-400 mt-1">Crea una nueva receta médica para comenzar</p>
          </CardContent>
        </Card>
      ) : (
        <>
          <Card className="border border-slate-200 overflow-hidden" data-testid="prescriptions-table">
            <Table>
              <TableHeader>
                <TableRow className="bg-slate-50/80">
                  <TableHead className="text-xs font-semibold text-slate-600">Fecha</TableHead>
                  <TableHead className="text-xs font-semibold text-slate-600">Paciente</TableHead>
                  <TableHead className="text-xs font-semibold text-slate-600">Médico</TableHead>
                  <TableHead className="text-xs font-semibold text-slate-600">Diagnóstico</TableHead>
                  <TableHead className="text-xs font-semibold text-slate-600 text-center">Medicamentos</TableHead>
                  <TableHead className="text-xs font-semibold text-slate-600 text-center">Estado</TableHead>
                  <TableHead className="text-xs font-semibold text-slate-600 text-right">Acciones</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {prescriptions.map(p => {
                  const st = STATUS_MAP[p.status] || { label: p.status, class: '' };
                  return (
                    <TableRow key={p.id} className="hover:bg-teal-50/30 transition-colors" data-testid={`prescription-row-${p.id}`}>
                      <TableCell className="text-sm">{formatDate(p.issued_at || p.created_at)}</TableCell>
                      <TableCell className="text-sm font-medium">{p.patient_name}</TableCell>
                      <TableCell className="text-sm text-slate-600">{p.doctor_name}</TableCell>
                      <TableCell className="text-sm text-slate-600 max-w-[200px] truncate">{p.diagnosis || '—'}</TableCell>
                      <TableCell className="text-center"><span className="text-sm font-medium">{p.item_count}</span></TableCell>
                      <TableCell className="text-center">
                        <Badge variant="outline" className={`text-xs ${st.class}`}>{st.label}</Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center justify-end gap-1">
                          {p.status === 'draft' && (
                            <Button variant="outline" size="sm" className="h-7 text-xs" onClick={() => navigate(`/dashboard/recetas/nueva?edit=${p.id}`)} data-testid={`edit-prescription-${p.id}`}>
                              Editar
                            </Button>
                          )}
                          {p.status === 'issued' && (
                            <>
                              <Button variant="outline" size="sm" className="h-7 text-xs" onClick={() => navigate(`/dashboard/recetas/nueva?duplicate=${p.id}`)} data-testid={`duplicate-prescription-${p.id}`}>
                                <Copy className="w-3 h-3 mr-1" /> Duplicar
                              </Button>
                              <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => downloadPdf(p.id)} data-testid={`download-pdf-${p.id}`}>
                                <Download className="w-3.5 h-3.5 text-teal-600" />
                              </Button>
                              <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => shareViaWhatsApp('prescription', p.id, headers)} data-testid={`whatsapp-prescription-${p.id}`} title="Enviar por WhatsApp">
                                <MessageCircle className="w-3.5 h-3.5 text-green-600" />
                              </Button>
                            </>
                          )}
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
                <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>
                  <ChevronLeft className="w-4 h-4" />
                </Button>
                <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => setPage(p => p + 1)}>
                  <ChevronRight className="w-4 h-4" />
                </Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
