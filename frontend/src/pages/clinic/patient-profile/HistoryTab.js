import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../../../components/ui/card';
import { Button } from '../../../components/ui/button';
import { Input } from '../../../components/ui/input';
import { Badge } from '../../../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../../components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../../components/ui/table';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '../../../components/ui/collapsible';
import { Textarea } from '../../../components/ui/textarea';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../../components/ui/dialog';
import { Plus, Stethoscope, Edit, ChevronDown, ChevronUp, AlertCircle } from 'lucide-react';
import { STATUS_MAP } from './constants';
import { formatDateTime } from './utils';
import RecordDetail from './RecordDetail';

export default function HistoryTab({
  patientId, medicalRecords, doctors, doctorFilter, setDoctorFilter,
  dateFrom, setDateFrom, dateTo, setDateTo, expandedRecord, setExpandedRecord,
  appointments, showAddendum, setShowAddendum, addendumText, setAddendumText, onAddAddendum,
}) {
  const navigate = useNavigate();
  return (
    <>
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <Select value={doctorFilter} onValueChange={setDoctorFilter}>
              <SelectTrigger className="w-44 text-sm" data-testid="filter-doctor">
                <SelectValue placeholder="Filtrar por médico" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos los médicos</SelectItem>
                {doctors.map(d => (
                  <SelectItem key={d.id} value={d.id}>{d.first_name} {d.last_name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)} className="w-36 text-sm" data-testid="filter-date-from" />
            <span className="text-xs text-slate-400">a</span>
            <Input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)} className="w-36 text-sm" data-testid="filter-date-to" />
            {(doctorFilter !== 'all' || dateFrom || dateTo) && (
              <Button variant="ghost" size="sm" onClick={() => { setDoctorFilter('all'); setDateFrom(''); setDateTo(''); }}>
                Limpiar
              </Button>
            )}
          </div>
          <Button className="bg-teal-600 hover:bg-teal-700" size="sm" onClick={() => navigate(`/dashboard/pacientes/${patientId}/consulta`)} data-testid="new-consultation-btn">
            <Plus className="w-4 h-4 mr-1.5" /> Nueva consulta
          </Button>
        </div>

        {medicalRecords.length === 0 ? (
          <Card className="border border-slate-200">
            <CardContent className="p-12 text-center">
              <Stethoscope className="w-10 h-10 text-slate-300 mx-auto mb-2" />
              <p className="text-sm text-slate-500 font-medium">No hay consultas registradas</p>
              <p className="text-xs text-slate-400 mt-1">Cree una nueva consulta médica para comenzar el historial</p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {medicalRecords.map(record => {
              const isExpanded = expandedRecord === record.id;
              const primaryDx = (record.diagnoses || []).find(d => d.type === 'primary');
              const hasVitalAlert = record.blood_pressure_systolic > 180 || record.blood_pressure_systolic < 70 ||
                record.heart_rate > 120 || record.heart_rate < 50 ||
                record.temperature > 38.0 || record.oxygen_saturation < 92;
              return (
                <Card key={record.id} className={`border transition-all ${record.status === 'draft' ? 'border-amber-200 bg-amber-50/30' : 'border-slate-200'}`} data-testid={`record-card-${record.id}`}>
                  <Collapsible open={isExpanded} onOpenChange={() => setExpandedRecord(isExpanded ? null : record.id)}>
                    <CollapsibleTrigger asChild>
                      <button className="w-full text-left p-4 hover:bg-slate-50/50 transition-colors">
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="text-sm font-semibold text-slate-800">
                                {new Date(record.created_at).toLocaleDateString('es-GT', { day: '2-digit', month: 'long', year: 'numeric' })}
                              </span>
                              <Badge variant="outline" className={`text-xs ${record.status === 'finalized' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-amber-50 text-amber-700 border-amber-200'}`}>
                                {record.status === 'finalized' ? 'Finalizada' : 'Borrador'}
                              </Badge>
                              {hasVitalAlert && (
                                <Badge variant="outline" className="text-xs bg-red-50 text-red-600 border-red-200">
                                  <AlertCircle className="w-3 h-3 mr-0.5" /> Signos vitales alterados
                                </Badge>
                              )}
                            </div>
                            <p className="text-xs text-slate-500">Dr. {record.doctor_name}</p>
                            {primaryDx && (
                              <p className="text-sm text-slate-700 mt-1">
                                <span className="font-mono text-xs text-teal-600 mr-1">{primaryDx.code}</span>
                                {primaryDx.description}
                              </p>
                            )}
                            {record.chief_complaint && (
                              <p className="text-xs text-slate-500 mt-0.5 truncate max-w-lg">Motivo: {record.chief_complaint}</p>
                            )}
                          </div>
                          <div className="flex items-center gap-2">
                            {record.status === 'draft' && (
                              <Button variant="outline" size="sm" className="h-7 text-xs" onClick={(e) => { e.stopPropagation(); navigate(`/dashboard/pacientes/${patientId}/consulta?record_id=${record.id}`); }}>
                                <Edit className="w-3 h-3 mr-1" /> Editar
                              </Button>
                            )}
                            {isExpanded ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
                          </div>
                        </div>
                      </button>
                    </CollapsibleTrigger>
                    <CollapsibleContent>
                      <div className="px-4 pb-4 pt-1 border-t border-slate-100">
                        <RecordDetail record={record} onAddAddendum={() => setShowAddendum(record.id)} />
                      </div>
                    </CollapsibleContent>
                  </Collapsible>
                </Card>
              );
            })}
          </div>
        )}

        {appointments.length > 0 && (
          <Card className="border border-slate-200 mt-4">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-semibold text-slate-700">Historial de citas</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow className="bg-slate-50/50">
                    <TableHead className="text-xs font-semibold">Fecha</TableHead>
                    <TableHead className="text-xs font-semibold">Doctor</TableHead>
                    <TableHead className="text-xs font-semibold">Motivo</TableHead>
                    <TableHead className="text-xs font-semibold text-center">Estado</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {appointments.map(apt => {
                    const st = STATUS_MAP[apt.status] || { label: apt.status, class: 'bg-slate-50 text-slate-600' };
                    return (
                      <TableRow key={apt.id} data-testid={`appointment-row-${apt.id}`}>
                        <TableCell className="text-sm">{formatDateTime(apt.starts_at)}</TableCell>
                        <TableCell className="text-sm">{apt.doctor_name || '—'}</TableCell>
                        <TableCell className="text-sm text-slate-600 max-w-xs truncate">{apt.reason || '—'}</TableCell>
                        <TableCell className="text-center">
                          <Badge variant="outline" className={`text-xs ${st.class}`}>{st.label}</Badge>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}
      </div>

      <Dialog open={!!showAddendum} onOpenChange={() => { setShowAddendum(null); setAddendumText(''); }}>
        <DialogContent className="max-w-md" data-testid="addendum-dialog">
          <DialogHeader>
            <DialogTitle>Agregar addendum</DialogTitle>
          </DialogHeader>
          <div className="py-2">
            <Textarea
              value={addendumText}
              onChange={e => setAddendumText(e.target.value)}
              placeholder="Escriba el addendum o nota adicional..."
              className="text-sm min-h-[100px]"
              data-testid="addendum-text"
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAddendum(null)}>Cancelar</Button>
            <Button className="bg-teal-600 hover:bg-teal-700" onClick={() => onAddAddendum(showAddendum)} data-testid="save-addendum-btn">
              Guardar addendum
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
