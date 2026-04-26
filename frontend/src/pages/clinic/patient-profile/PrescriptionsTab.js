import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../../components/ui/card';
import { Button } from '../../../components/ui/button';
import { Badge } from '../../../components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../../components/ui/table';
import { toast } from 'sonner';
import { Pill, Plus, ClipboardList, Download } from 'lucide-react';
import { API } from './constants';
import { formatDate } from './utils';

export default function PrescriptionsTab({ patientId, prescriptions, headers }) {
  const navigate = useNavigate();
  return (
    <Card className="border border-slate-200">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-semibold text-slate-700 flex items-center gap-2">
            <Pill className="w-4 h-4 text-teal-500" /> Recetas médicas ({prescriptions.length})
          </CardTitle>
          <Button className="bg-teal-600 hover:bg-teal-700" size="sm" onClick={() => navigate(`/dashboard/recetas/nueva?patient_id=${patientId}`)} data-testid="new-prescription-from-profile">
            <Plus className="w-4 h-4 mr-1.5" /> Nueva receta
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {prescriptions.length === 0 ? (
          <div className="text-center py-8">
            <ClipboardList className="w-10 h-10 text-slate-300 mx-auto mb-2" />
            <p className="text-sm text-slate-500">No hay recetas registradas</p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="bg-slate-50/50">
                <TableHead className="text-xs font-semibold">Fecha</TableHead>
                <TableHead className="text-xs font-semibold">Médico</TableHead>
                <TableHead className="text-xs font-semibold">Diagnóstico</TableHead>
                <TableHead className="text-xs font-semibold text-center">Medicamentos</TableHead>
                <TableHead className="text-xs font-semibold text-center">Estado</TableHead>
                <TableHead className="text-xs font-semibold text-right">PDF</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {prescriptions.map(p => (
                <TableRow key={p.id} data-testid={`profile-prescription-${p.id}`}>
                  <TableCell className="text-sm">{formatDate(p.issued_at || p.created_at)}</TableCell>
                  <TableCell className="text-sm">{p.doctor_name || '—'}</TableCell>
                  <TableCell className="text-sm text-slate-600 max-w-[200px] truncate">{p.diagnosis || '—'}</TableCell>
                  <TableCell className="text-center text-sm font-medium">{p.item_count ?? 0}</TableCell>
                  <TableCell className="text-center">
                    <Badge variant="outline" className={`text-xs ${p.status === 'issued' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-amber-50 text-amber-700 border-amber-200'}`}>
                      {p.status === 'issued' ? 'Emitida' : 'Borrador'}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    {p.status === 'issued' && (
                      <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={async () => {
                        try { const r = await axios.get(`${API}/clinic/prescriptions/${p.id}/pdf-url`, { headers }); if (r.data.url) window.open(r.data.url, '_blank'); } catch { toast.error('Error al obtener PDF'); }
                      }} data-testid={`profile-download-rx-${p.id}`}>
                        <Download className="w-3.5 h-3.5 text-teal-600" />
                      </Button>
                    )}
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
