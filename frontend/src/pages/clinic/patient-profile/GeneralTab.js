import { Card, CardContent, CardHeader, CardTitle } from '../../../components/ui/card';
import { Badge } from '../../../components/ui/badge';
import { Separator } from '../../../components/ui/separator';
import {
  Phone, Mail, MapPin, Calendar, Heart, Shield, User, FileText,
  Droplets, AlertTriangle,
} from 'lucide-react';
import { InfoRow } from './cells';
import { formatDate, calcAge, genderLabel } from './utils';

export default function GeneralTab({ patient }) {
  const age = calcAge(patient.date_of_birth);
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <Card className="border border-slate-200">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold text-slate-700 flex items-center gap-2">
            <User className="w-4 h-4 text-teal-500" /> Datos personales
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <InfoRow icon={User} label="Nombre completo" value={`${patient.first_name} ${patient.last_name}`} />
          <InfoRow icon={Calendar} label="Fecha de nacimiento" value={patient.date_of_birth ? `${formatDate(patient.date_of_birth)}${age !== null ? ` (${age} años)` : ''}` : null} />
          <InfoRow icon={User} label="Género" value={genderLabel(patient.gender)} />
          <InfoRow icon={Shield} label="DPI / Identificación" value={patient.national_id} />
          <InfoRow icon={MapPin} label="Nacionalidad" value={patient.nationality} />
        </CardContent>
      </Card>

      <Card className="border border-slate-200">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold text-slate-700 flex items-center gap-2">
            <Phone className="w-4 h-4 text-teal-500" /> Contacto
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <InfoRow icon={Phone} label="Teléfono principal" value={patient.phone} />
          <InfoRow icon={Phone} label="Teléfono secundario" value={patient.phone_secondary} />
          <InfoRow icon={Mail} label="Correo electrónico" value={patient.email} />
          <InfoRow icon={MapPin} label="Dirección" value={[patient.address, patient.city, patient.state, patient.country].filter(Boolean).join(', ') || null} />
        </CardContent>
      </Card>

      <Card className="border border-slate-200">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold text-slate-700 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-orange-500" /> Contacto de emergencia
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <InfoRow icon={User} label="Nombre" value={patient.emergency_contact_name} />
          <InfoRow icon={Heart} label="Relación" value={patient.emergency_contact_relation} />
          <InfoRow icon={Phone} label="Teléfono" value={patient.emergency_contact_phone} />
          {!patient.emergency_contact_name && !patient.emergency_contact_phone && (
            <p className="text-sm text-slate-400 py-2">Sin contacto de emergencia registrado</p>
          )}
        </CardContent>
      </Card>

      <Card className="border border-slate-200">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold text-slate-700 flex items-center gap-2">
            <Heart className="w-4 h-4 text-red-500" /> Información médica
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <InfoRow icon={Droplets} label="Tipo de sangre" value={patient.blood_type} />
          <ListSection label="Alergias" items={patient.allergies} colorClass="bg-red-50 text-red-600 border-red-200" emptyText="Ninguna registrada" />
          <ListSection label="Condiciones crónicas" items={patient.chronic_conditions} colorClass="bg-amber-50 text-amber-700 border-amber-200" emptyText="Ninguna registrada" />
          <ListSection label="Medicamentos actuales" items={patient.current_medications} colorClass="bg-blue-50 text-blue-700 border-blue-200" emptyText="Ninguno registrado" />
          {patient.insurance_provider && (
            <>
              <Separator className="my-2" />
              <InfoRow icon={Shield} label="Aseguradora" value={patient.insurance_provider} />
              <InfoRow icon={FileText} label="Número de póliza" value={patient.insurance_policy_number} />
              <InfoRow icon={Calendar} label="Vencimiento" value={formatDate(patient.insurance_expiry)} />
            </>
          )}
          {patient.notes && (
            <>
              <Separator className="my-2" />
              <div className="py-2">
                <p className="text-xs text-slate-500 mb-1">Notas clínicas</p>
                <p className="text-sm text-slate-700 whitespace-pre-wrap">{patient.notes}</p>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function ListSection({ label, items, colorClass, emptyText }) {
  return (
    <div className="py-2">
      <p className="text-xs text-slate-500 mb-1">{label}</p>
      {items?.length > 0 ? (
        <div className="flex flex-wrap gap-1">
          {items.map((it, i) => (
            <Badge key={i} variant="outline" className={`text-xs ${colorClass}`}>{it}</Badge>
          ))}
        </div>
      ) : <p className="text-sm text-slate-400">{emptyText}</p>}
    </div>
  );
}
