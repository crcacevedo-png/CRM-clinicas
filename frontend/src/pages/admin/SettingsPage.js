import { Settings } from 'lucide-react';

export default function SettingsPage() {
  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-3xl font-semibold text-zinc-950 tracking-tight">Configuración</h1>
        <p className="text-sm text-zinc-500 mt-1">Ajustes generales del sistema</p>
      </div>

      <div className="bg-white border border-zinc-200 p-12 text-center">
        <Settings className="w-12 h-12 text-zinc-300 mx-auto mb-4" strokeWidth={1.5} />
        <h2 className="text-lg font-medium text-zinc-700 mb-2">Próximamente</h2>
        <p className="text-sm text-zinc-500">
          La configuración del sistema estará disponible en una próxima actualización.
        </p>
      </div>
    </div>
  );
}
