import { useState, useRef } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from './ui/dialog';
import { Button } from './ui/button';
import { Upload, FileText, CheckCircle2, AlertCircle, Download } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const CATALOG_LABELS = {
  medications: 'Medicamentos',
  'lab-studies': 'Estudios de Laboratorio',
  icd10: 'Códigos CIE-10',
  patients: 'Pacientes',
};

const ENDPOINT_MAP = {
  medications: { import: '/admin/catalogs/medications/import-csv', template: '/admin/catalogs/medications/csv-template' },
  'lab-studies': { import: '/admin/catalogs/lab-studies/import-csv', template: '/admin/catalogs/lab-studies/csv-template' },
  icd10: { import: '/admin/catalogs/icd10/import-csv', template: '/admin/catalogs/icd10/csv-template' },
  patients: { import: '/clinic/patients-bulk/import', template: '/clinic/patients-bulk/template' },
};

/**
 * Reusable bulk-import dialog (CSV + XLSX).
 * Props:
 *  - open, onOpenChange
 *  - catalog: 'medications' | 'lab-studies' | 'icd10' | 'patients'
 *  - acceptXlsx: boolean (true to also accept .xlsx files; default false → CSV only)
 *  - headers: axios auth headers
 *  - onSuccess?: callback fired after successful commit
 */
export default function CsvImportDialog({ open, onOpenChange, catalog, headers, onSuccess, acceptXlsx = false }) {
  const [file, setFile] = useState(null);
  const [dryRun, setDryRun] = useState(null);
  const [loading, setLoading] = useState(false);
  const [committing, setCommitting] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef(null);
  const endpoints = ENDPOINT_MAP[catalog] || ENDPOINT_MAP.medications;
  const acceptedExtensions = acceptXlsx ? ['.csv', '.xlsx'] : ['.csv'];
  const acceptAttr = acceptXlsx ? '.csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' : '.csv,text/csv';

  const reset = () => {
    setFile(null);
    setDryRun(null);
    setLoading(false);
    setCommitting(false);
  };

  const handleClose = () => {
    if (committing || loading) return;
    reset();
    onOpenChange(false);
  };

  const handleFile = (f) => {
    if (!f) return;
    const ext = '.' + f.name.split('.').pop().toLowerCase();
    if (!acceptedExtensions.includes(ext)) {
      toast.error(`El archivo debe tener extensión ${acceptedExtensions.join(' o ')}`);
      return;
    }
    if (f.size > 5 * 1024 * 1024) {
      toast.error('El archivo no puede superar 5 MB');
      return;
    }
    setFile(f);
    setDryRun(null);
    runDryRun(f);
  };

  const runDryRun = async (f) => {
    setLoading(true);
    try {
      const fd = new FormData();
      fd.append('file', f);
      const res = await axios.post(
        `${API}${endpoints.import}?commit=false`,
        fd,
        { headers: { ...headers, 'Content-Type': 'multipart/form-data' } }
      );
      setDryRun(res.data);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al validar el archivo');
      setFile(null);
    } finally {
      setLoading(false);
    }
  };

  const handleCommit = async () => {
    if (!file) return;
    setCommitting(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await axios.post(
        `${API}${endpoints.import}?commit=true`,
        fd,
        { headers: { ...headers, 'Content-Type': 'multipart/form-data' } }
      );
      const d = res.data;
      if ((d.commit_errors || []).length > 0) {
        toast.error(`Error de inserción en BD: ${d.commit_errors[0].message.slice(0, 80)}`);
        setDryRun(d);
        return;
      }
      toast.success(`Importados ${d.imported} de ${d.total} registros (${d.duplicates_skipped} duplicados omitidos)`);
      onSuccess?.(d);
      reset();
      onOpenChange(false);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error al importar');
    } finally {
      setCommitting(false);
    }
  };

  const downloadTemplate = async (format = 'csv') => {
    try {
      const url = `${API}${endpoints.template}${format === 'xlsx' ? '?format=xlsx' : ''}`;
      const res = await axios.get(url, { headers, responseType: format === 'xlsx' ? 'blob' : 'json' });
      let blob, filename;
      if (format === 'xlsx') {
        blob = res.data;
        filename = `plantilla_${catalog}.xlsx`;
      } else {
        blob = new Blob([res.data.content], { type: 'text/csv;charset=utf-8;' });
        filename = res.data.filename;
      }
      const blobUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(blobUrl);
    } catch {
      toast.error('No se pudo descargar la plantilla');
    }
  };

  const onDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files?.[0];
    handleFile(f);
  };

  const canCommit = dryRun && dryRun.valid_rows > 0 && !committing && !loading;

  return (
    <Dialog open={open} onOpenChange={(v) => v ? onOpenChange(true) : handleClose()}>
      <DialogContent className="max-w-2xl" data-testid="csv-import-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Upload className="w-4 h-4 text-[#2EC4B6]" />
            Importar {CATALOG_LABELS[catalog] || catalog} desde {acceptXlsx ? 'CSV o Excel' : 'CSV'}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {/* Template download */}
          <div className="flex items-center justify-between text-sm bg-slate-50 border border-slate-200 rounded p-3">
            <span className="text-slate-600">¿Necesitas el formato? Descarga la plantilla.</span>
            <div className="flex gap-1.5">
              <Button size="sm" variant="outline" onClick={() => downloadTemplate('csv')} data-testid="csv-template-btn">
                <Download className="w-3.5 h-3.5 mr-1" /> CSV
              </Button>
              {acceptXlsx && (
                <Button size="sm" variant="outline" onClick={() => downloadTemplate('xlsx')} data-testid="xlsx-template-btn">
                  <Download className="w-3.5 h-3.5 mr-1" /> Excel
                </Button>
              )}
            </div>
          </div>

          {/* File drop zone */}
          {!file && (
            <div
              className={`border-2 border-dashed rounded-lg p-10 text-center cursor-pointer transition ${dragOver ? 'border-[#2EC4B6] bg-teal-50/40' : 'border-slate-300 hover:border-slate-400'}`}
              onClick={() => inputRef.current?.click()}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={onDrop}
              data-testid="csv-dropzone"
            >
              <Upload className="w-8 h-8 mx-auto text-slate-400 mb-2" />
              <p className="text-sm text-slate-700 font-medium">
                Suelta tu archivo {acceptXlsx ? 'CSV o Excel' : 'CSV'} aquí o haz clic para seleccionar
              </p>
              <p className="text-xs text-slate-400 mt-1">UTF-8, máximo 5 MB. {acceptXlsx ? 'Acepta .csv y .xlsx.' : 'Acepta delimitador coma o punto y coma.'}</p>
              <input ref={inputRef} type="file" accept={acceptAttr} className="hidden" onChange={(e) => handleFile(e.target.files?.[0])} data-testid="csv-file-input" />
            </div>
          )}

          {/* File selected: show summary */}
          {file && (
            <div className="border border-slate-200 rounded-lg p-3 flex items-center gap-2 bg-slate-50">
              <FileText className="w-4 h-4 text-slate-500" />
              <span className="text-sm font-medium text-slate-700 flex-1 truncate">{file.name}</span>
              <span className="text-xs text-slate-400">{(file.size / 1024).toFixed(1)} KB</span>
              <Button size="sm" variant="ghost" onClick={() => { setFile(null); setDryRun(null); }} data-testid="csv-change-file-btn">
                Cambiar
              </Button>
            </div>
          )}

          {loading && (
            <div className="text-center py-6">
              <div className="w-6 h-6 border-2 border-[#2EC4B6] border-t-transparent rounded-full animate-spin mx-auto" />
              <p className="text-xs text-slate-500 mt-2">Validando archivo…</p>
            </div>
          )}

          {/* Dry-run results */}
          {dryRun && !loading && (
            <div className="space-y-3" data-testid="csv-dryrun-results">
              <div className="grid grid-cols-4 gap-2 text-sm">
                <div className="border border-slate-200 rounded p-2 text-center">
                  <div className="text-xs text-slate-500">Total filas</div>
                  <div className="text-lg font-semibold text-slate-800">{dryRun.total}</div>
                </div>
                <div className="border border-emerald-200 bg-emerald-50/60 rounded p-2 text-center">
                  <div className="text-xs text-emerald-600">Válidas</div>
                  <div className="text-lg font-semibold text-emerald-700">{dryRun.valid_rows}</div>
                </div>
                <div className="border border-amber-200 bg-amber-50/60 rounded p-2 text-center">
                  <div className="text-xs text-amber-600">Duplicadas</div>
                  <div className="text-lg font-semibold text-amber-700">{dryRun.duplicates_skipped}</div>
                </div>
                <div className="border border-red-200 bg-red-50/60 rounded p-2 text-center">
                  <div className="text-xs text-red-600">Errores</div>
                  <div className="text-lg font-semibold text-red-700">{dryRun.error_rows}</div>
                </div>
              </div>

              {/* Errors list */}
              {dryRun.errors?.length > 0 && (
                <div className="border border-red-200 rounded-lg max-h-44 overflow-auto bg-red-50/30">
                  <div className="sticky top-0 bg-red-100 px-3 py-1.5 text-xs font-semibold text-red-800 flex items-center gap-1">
                    <AlertCircle className="w-3.5 h-3.5" /> Errores detectados ({dryRun.errors.length}{dryRun.errors.length === 50 && '+'})
                  </div>
                  <table className="w-full text-xs">
                    <tbody>
                      {dryRun.errors.map((e, i) => (
                        <tr key={i} className="border-t border-red-100">
                          <td className="px-3 py-1 text-slate-500 w-16">Fila {e.row > 0 ? e.row : '—'}</td>
                          <td className="px-3 py-1 text-slate-700"><code className="bg-red-100 px-1 rounded text-red-800">{e.field}</code></td>
                          <td className="px-3 py-1 text-red-700">{e.message}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Preview */}
              {dryRun.preview?.length > 0 && (
                <div className="border border-slate-200 rounded-lg max-h-44 overflow-auto">
                  <div className="sticky top-0 bg-slate-100 px-3 py-1.5 text-xs font-semibold text-slate-700 flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" /> Vista previa (primeras {dryRun.preview.length})
                  </div>
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="bg-slate-50">
                        {Object.keys(dryRun.preview[0]).map((k) => (
                          <th key={k} className="text-left px-3 py-1.5 font-medium text-slate-600">{k}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {dryRun.preview.map((r, i) => (
                        <tr key={i} className="border-t border-slate-100">
                          {Object.values(r).map((v, j) => (
                            <td key={j} className="px-3 py-1 text-slate-700 truncate max-w-[200px]">{Array.isArray(v) ? v.join(', ') : String(v ?? '')}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose} disabled={committing} data-testid="csv-cancel-btn">
            Cancelar
          </Button>
          <Button
            onClick={handleCommit}
            disabled={!canCommit}
            className="bg-[#2EC4B6] hover:bg-[#2EC4B6]/90 disabled:bg-slate-300"
            data-testid="csv-commit-btn"
          >
            {committing ? 'Importando…' : `Importar ${dryRun?.valid_rows ?? ''} registros`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
