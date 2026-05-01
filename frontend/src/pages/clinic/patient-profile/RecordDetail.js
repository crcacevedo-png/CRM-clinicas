import { Button } from '../../../components/ui/button';
import { Badge } from '../../../components/ui/badge';
import { MessageSquarePlus } from 'lucide-react';
import { ROS_LABELS, EXAM_LABELS } from './constants';
import { VitalBadge } from './cells';

export default function RecordDetail({ record, onAddAddendum }) {
  const ros = record.review_of_systems || {};
  const hasROS = Object.values(ros).some(v => v && v.length > 0);
  const exam = record.physical_exam || {};
  const hasExam = Object.values(exam).some(v => v && v.trim());
  const hasVitals = record.blood_pressure_systolic || record.heart_rate || record.temperature;

  return (
    <div className="space-y-4 text-sm">
      {record.chief_complaint && (
        <div>
          <p className="text-xs font-semibold text-slate-500 uppercase mb-1">Motivo de consulta</p>
          <p className="text-slate-700">{record.chief_complaint}</p>
        </div>
      )}
      {record.present_illness && (
        <div>
          <p className="text-xs font-semibold text-slate-500 uppercase mb-1">Historia de enfermedad actual</p>
          <p className="text-slate-700 whitespace-pre-wrap">{record.present_illness}</p>
        </div>
      )}

      {hasROS && (
        <div>
          <p className="text-xs font-semibold text-slate-500 uppercase mb-1">Revisión por sistemas</p>
          <div className="flex flex-wrap gap-2">
            {Object.entries(ros).filter(([_, items]) => items && items.length > 0).map(([sys, items]) => (
              <div key={sys} className="bg-slate-50 rounded px-2 py-1">
                <span className="text-xs font-medium text-slate-600">{ROS_LABELS[sys] || sys}: </span>
                <span className="text-xs text-slate-500">{items.join(', ')}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {hasVitals && (
        <div>
          <p className="text-xs font-semibold text-slate-500 uppercase mb-2">Signos vitales</p>
          <div className="grid grid-cols-4 md:grid-cols-8 gap-2">
            <VitalBadge label="PA Sist." value={record.blood_pressure_systolic} unit="mmHg" rangeKey="blood_pressure_systolic" />
            <VitalBadge label="PA Diast." value={record.blood_pressure_diastolic} unit="mmHg" rangeKey="blood_pressure_diastolic" />
            <VitalBadge label="FC" value={record.heart_rate} unit="lpm" rangeKey="heart_rate" />
            <VitalBadge label="FR" value={record.respiratory_rate} unit="rpm" rangeKey="respiratory_rate" />
            <VitalBadge label="Temp" value={record.temperature} unit="°C" rangeKey="temperature" />
            <VitalBadge label="SpO2" value={record.oxygen_saturation} unit="%" rangeKey="oxygen_saturation" />
            <VitalBadge label="Peso" value={record.weight_kg} unit="kg" />
            <VitalBadge label="Talla" value={record.height_cm} unit="cm" />
          </div>
          {record.bmi && <p className="text-xs text-slate-500 mt-1">IMC: <span className="font-bold">{record.bmi}</span></p>}
        </div>
      )}

      {hasExam && (
        <div>
          <p className="text-xs font-semibold text-slate-500 uppercase mb-1">Examen físico</p>
          <div className="space-y-1">
            {Object.entries(exam).filter(([_, v]) => v && v.trim()).map(([key, val]) => (
              <div key={key} className="flex gap-2">
                <span className="text-xs font-medium text-slate-600 min-w-[90px]">{EXAM_LABELS[key] || key}:</span>
                <span className="text-xs text-slate-600">{val}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {record.diagnoses?.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-slate-500 uppercase mb-1">Diagnósticos</p>
          <div className="space-y-1">
            {record.diagnoses.map((d, i) => (
              <div key={i} className="flex items-center gap-2">
                {d.code ? (
                  <Badge variant="outline" className={`text-xs font-mono ${d.type === 'primary' ? 'bg-teal-50 text-teal-700 border-teal-200' : ''}`}>{d.code}</Badge>
                ) : (
                  <Badge variant="outline" className={`text-xs italic ${d.type === 'primary' ? 'bg-teal-50 text-teal-700 border-teal-200' : 'bg-slate-100 text-slate-600'}`}>Alterno</Badge>
                )}
                <span className="text-sm text-slate-700">{d.description}</span>
                {d.type === 'primary' && <Badge className="bg-teal-600 text-white text-xs">Principal</Badge>}
              </div>
            ))}
          </div>
        </div>
      )}

      {record.treatment_plan && (
        <div>
          <p className="text-xs font-semibold text-slate-500 uppercase mb-1">Plan de tratamiento</p>
          <p className="text-slate-700 whitespace-pre-wrap">{record.treatment_plan}</p>
        </div>
      )}
      {record.procedures && (
        <div>
          <p className="text-xs font-semibold text-slate-500 uppercase mb-1">Procedimientos</p>
          <p className="text-slate-700 whitespace-pre-wrap">{record.procedures}</p>
        </div>
      )}

      {record.notes && (
        <div>
          <p className="text-xs font-semibold text-slate-500 uppercase mb-1">Notas</p>
          <p className="text-slate-700 whitespace-pre-wrap">{record.notes}</p>
        </div>
      )}
      {record.private_notes && (
        <div className="p-2 bg-amber-50 rounded-md border border-amber-200">
          <p className="text-xs font-semibold text-amber-700 uppercase mb-1">Notas privadas del médico</p>
          <p className="text-slate-700 whitespace-pre-wrap text-xs">{record.private_notes}</p>
        </div>
      )}

      {record.addenda?.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-slate-500 uppercase mb-1">Addendums</p>
          <div className="space-y-2">
            {record.addenda.map((a, i) => (
              <div key={i} className="p-2 bg-blue-50 rounded border border-blue-100">
                <p className="text-xs text-blue-600 mb-0.5">
                  {a.doctor_name} — {new Date(a.created_at).toLocaleString('es-GT', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}
                </p>
                <p className="text-sm text-slate-700">{a.text}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {record.status === 'finalized' && (
        <Button variant="outline" size="sm" className="text-xs" onClick={onAddAddendum} data-testid={`add-addendum-${record.id}`}>
          <MessageSquarePlus className="w-3.5 h-3.5 mr-1" /> Agregar addendum
        </Button>
      )}
    </div>
  );
}
