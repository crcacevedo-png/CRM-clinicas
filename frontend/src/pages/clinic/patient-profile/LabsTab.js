import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../../components/ui/card';
import { Button } from '../../../components/ui/button';
import { Badge } from '../../../components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../../components/ui/table';
import { toast } from 'sonner';
import { FlaskConical, Plus, Download } from 'lucide-react';
import { API } from './constants';
import { formatDate } from './utils';

export default function LabsTab({ patientId, labOrders, headers }) {
  const navigate = useNavigate();
  return (
    <Card className="border border-slate-200">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-semibold text-slate-700 flex items-center gap-2">
            <FlaskConical className="w-4 h-4 text-teal-500" /> Órdenes de laboratorio ({labOrders.length})
          </CardTitle>
          <Button className="bg-teal-600 hover:bg-teal-700" size="sm" onClick={() => navigate(`/dashboard/laboratorio/nueva?patient_id=${patientId}`)} data-testid="new-lab-order-from-profile">
            <Plus className="w-4 h-4 mr-1.5" /> Nueva orden
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {labOrders.length === 0 ? (
          <div className="text-center py-8">
            <FlaskConical className="w-10 h-10 text-slate-300 mx-auto mb-2" />
            <p className="text-sm text-slate-500">No hay órdenes de laboratorio</p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="bg-slate-50/50">
                <TableHead className="text-xs font-semibold">Fecha</TableHead>
                <TableHead className="text-xs font-semibold">Médico</TableHead>
                <TableHead className="text-xs font-semibold">Estudios</TableHead>
                <TableHead className="text-xs font-semibold text-center">Prioridad</TableHead>
                <TableHead className="text-xs font-semibold text-center">Estado</TableHead>
                <TableHead className="text-xs font-semibold text-right">PDF</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {labOrders.map(o => (
                <TableRow key={o.id} data-testid={`profile-lab-order-${o.id}`}>
                  <TableCell className="text-sm">{formatDate(o.ordered_at || o.created_at)}</TableCell>
                  <TableCell className="text-sm">{o.doctor_name || '—'}</TableCell>
                  <TableCell className="text-sm text-slate-600 max-w-[250px] truncate">{o.study_summary || `${o.item_count} estudio(s)`}</TableCell>
                  <TableCell className="text-center">
                    <span className={`text-xs ${o.priority === 'urgent' ? 'text-red-600 font-semibold' : 'text-slate-600'}`}>
                      {o.priority === 'urgent' ? 'Urgente' : 'Rutina'}
                    </span>
                  </TableCell>
                  <TableCell className="text-center">
                    <Badge variant="outline" className={`text-xs ${o.status === 'completed' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : o.status === 'cancelled' ? 'bg-red-50 text-red-600 border-red-200' : 'bg-amber-50 text-amber-700 border-amber-200'}`}>
                      {o.status === 'completed' ? 'Completada' : o.status === 'cancelled' ? 'Cancelada' : 'Pendiente'}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={async () => {
                      try { const r = await axios.get(`${API}/clinic/lab-orders/${o.id}/pdf-url`, { headers }); if (r.data.url) window.open(r.data.url, '_blank'); } catch { toast.error('Error al obtener PDF'); }
                    }} data-testid={`profile-download-lab-${o.id}`}>
                      <Download className="w-3.5 h-3.5 text-teal-600" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
