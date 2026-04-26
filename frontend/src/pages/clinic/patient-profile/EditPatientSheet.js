import { Sheet, SheetContent, SheetHeader, SheetTitle } from '../../../components/ui/sheet';
import { Button } from '../../../components/ui/button';
import { Input } from '../../../components/ui/input';
import { Label } from '../../../components/ui/label';
import { Textarea } from '../../../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../../components/ui/select';
import { Separator } from '../../../components/ui/separator';

export default function EditPatientSheet({ open, onClose, form, updateField, onSave, saving }) {
  return (
    <Sheet open={open} onOpenChange={onClose}>
      <SheetContent className="sm:max-w-xl overflow-y-auto" data-testid="edit-patient-sheet">
        <SheetHeader className="mb-4">
          <SheetTitle>Editar paciente</SheetTitle>
        </SheetHeader>
        <div className="space-y-3">
          <p className="text-xs font-semibold text-slate-500 uppercase">Datos personales</p>
          <div className="grid grid-cols-2 gap-3">
            <div><Label className="text-xs">Nombre *</Label><Input className="mt-1 text-sm" value={form.first_name || ''} onChange={e => updateField('first_name', e.target.value)} data-testid="edit-first-name" /></div>
            <div><Label className="text-xs">Apellido *</Label><Input className="mt-1 text-sm" value={form.last_name || ''} onChange={e => updateField('last_name', e.target.value)} data-testid="edit-last-name" /></div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div><Label className="text-xs">Fecha de nacimiento</Label><Input type="date" className="mt-1 text-sm" value={form.date_of_birth || ''} onChange={e => updateField('date_of_birth', e.target.value)} /></div>
            <div>
              <Label className="text-xs">Género</Label>
              <Select value={form.gender || ''} onValueChange={v => updateField('gender', v)}>
                <SelectTrigger className="mt-1 text-sm"><SelectValue placeholder="Seleccionar" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="male">Masculino</SelectItem>
                  <SelectItem value="female">Femenino</SelectItem>
                  <SelectItem value="other">Otro</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div><Label className="text-xs">DPI</Label><Input className="mt-1 text-sm" value={form.national_id || ''} onChange={e => updateField('national_id', e.target.value)} /></div>
            <div><Label className="text-xs">Nacionalidad</Label><Input className="mt-1 text-sm" value={form.nationality || ''} onChange={e => updateField('nationality', e.target.value)} /></div>
          </div>

          <Separator />
          <p className="text-xs font-semibold text-slate-500 uppercase">Contacto</p>
          <div className="grid grid-cols-2 gap-3">
            <div><Label className="text-xs">Teléfono</Label><Input className="mt-1 text-sm" value={form.phone || ''} onChange={e => updateField('phone', e.target.value)} data-testid="edit-phone" /></div>
            <div><Label className="text-xs">Teléfono secundario</Label><Input className="mt-1 text-sm" value={form.phone_secondary || ''} onChange={e => updateField('phone_secondary', e.target.value)} /></div>
          </div>
          <div><Label className="text-xs">Email</Label><Input type="email" className="mt-1 text-sm" value={form.email || ''} onChange={e => updateField('email', e.target.value)} /></div>
          <div><Label className="text-xs">Dirección</Label><Input className="mt-1 text-sm" value={form.address || ''} onChange={e => updateField('address', e.target.value)} /></div>
          <div className="grid grid-cols-3 gap-3">
            <div><Label className="text-xs">Ciudad</Label><Input className="mt-1 text-sm" value={form.city || ''} onChange={e => updateField('city', e.target.value)} /></div>
            <div><Label className="text-xs">Departamento</Label><Input className="mt-1 text-sm" value={form.state || ''} onChange={e => updateField('state', e.target.value)} /></div>
            <div><Label className="text-xs">País</Label><Input className="mt-1 text-sm" value={form.country || ''} onChange={e => updateField('country', e.target.value)} /></div>
          </div>

          <Separator />
          <p className="text-xs font-semibold text-slate-500 uppercase">Contacto de emergencia</p>
          <div className="grid grid-cols-3 gap-3">
            <div><Label className="text-xs">Nombre</Label><Input className="mt-1 text-sm" value={form.emergency_contact_name || ''} onChange={e => updateField('emergency_contact_name', e.target.value)} /></div>
            <div><Label className="text-xs">Relación</Label><Input className="mt-1 text-sm" value={form.emergency_contact_relation || ''} onChange={e => updateField('emergency_contact_relation', e.target.value)} /></div>
            <div><Label className="text-xs">Teléfono</Label><Input className="mt-1 text-sm" value={form.emergency_contact_phone || ''} onChange={e => updateField('emergency_contact_phone', e.target.value)} /></div>
          </div>

          <Separator />
          <p className="text-xs font-semibold text-slate-500 uppercase">Información médica</p>
          <div>
            <Label className="text-xs">Tipo de sangre</Label>
            <Select value={form.blood_type || ''} onValueChange={v => updateField('blood_type', v)}>
              <SelectTrigger className="mt-1 text-sm"><SelectValue placeholder="Seleccionar" /></SelectTrigger>
              <SelectContent>
                {['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'].map(bt => <SelectItem key={bt} value={bt}>{bt}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div><Label className="text-xs">Alergias (separadas por coma)</Label><Input className="mt-1 text-sm" value={form.allergies || ''} onChange={e => updateField('allergies', e.target.value)} /></div>
          <div><Label className="text-xs">Condiciones crónicas (separadas por coma)</Label><Input className="mt-1 text-sm" value={form.chronic_conditions || ''} onChange={e => updateField('chronic_conditions', e.target.value)} /></div>
          <div><Label className="text-xs">Medicamentos actuales (separados por coma)</Label><Input className="mt-1 text-sm" value={form.current_medications || ''} onChange={e => updateField('current_medications', e.target.value)} /></div>

          <Separator />
          <p className="text-xs font-semibold text-slate-500 uppercase">Seguro médico</p>
          <div><Label className="text-xs">Proveedor de seguro</Label><Input className="mt-1 text-sm" value={form.insurance_provider || ''} onChange={e => updateField('insurance_provider', e.target.value)} /></div>
          <div className="grid grid-cols-2 gap-3">
            <div><Label className="text-xs">Número de póliza</Label><Input className="mt-1 text-sm" value={form.insurance_policy_number || ''} onChange={e => updateField('insurance_policy_number', e.target.value)} /></div>
            <div><Label className="text-xs">Vencimiento</Label><Input type="date" className="mt-1 text-sm" value={form.insurance_expiry || ''} onChange={e => updateField('insurance_expiry', e.target.value)} /></div>
          </div>
          <div><Label className="text-xs">Notas clínicas</Label><Textarea className="mt-1 text-sm min-h-[60px]" value={form.notes || ''} onChange={e => updateField('notes', e.target.value)} /></div>
        </div>

        <div className="flex justify-end gap-3 mt-6 pt-4 border-t">
          <Button variant="outline" onClick={onClose}>Cancelar</Button>
          <Button className="bg-teal-600 hover:bg-teal-700" onClick={onSave} disabled={saving} data-testid="save-edit-btn">
            {saving ? 'Guardando...' : 'Guardar cambios'}
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
