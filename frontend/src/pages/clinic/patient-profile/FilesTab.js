import { useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../../../components/ui/card';
import { Button } from '../../../components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../../components/ui/table';
import { FileText, Upload, Download, Trash2 } from 'lucide-react';
import { FILE_ICONS } from './constants';
import { formatFileSize, formatDate } from './utils';

export default function FilesTab({ files, uploading, onUpload, onDownload, onDelete }) {
  const fileInputRef = useRef(null);
  return (
    <Card className="border border-slate-200" data-testid="files-section">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-semibold text-slate-700">
            Archivos adjuntos ({files.length})
          </CardTitle>
          <div>
            <input
              type="file"
              ref={fileInputRef}
              onChange={(e) => {
                onUpload(e);
                if (fileInputRef.current) fileInputRef.current.value = '';
              }}
              accept=".pdf,.jpg,.jpeg,.png,.dcm"
              className="hidden"
              data-testid="file-upload-input"
            />
            <Button
              size="sm"
              className="bg-teal-600 hover:bg-teal-700"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              data-testid="upload-file-btn"
            >
              <Upload className="w-3.5 h-3.5 mr-1.5" />
              {uploading ? 'Subiendo...' : 'Subir archivo'}
            </Button>
          </div>
        </div>
        <p className="text-xs text-slate-400 mt-1">Formatos permitidos: PDF, JPG, PNG, DICOM. Máx 10MB</p>
      </CardHeader>
      <CardContent>
        {files.length === 0 ? (
          <div className="text-center py-10 border-2 border-dashed border-slate-200 rounded-lg">
            <FileText className="w-10 h-10 text-slate-300 mx-auto mb-2" />
            <p className="text-sm text-slate-500">No hay archivos adjuntos</p>
            <p className="text-xs text-slate-400 mt-1">Sube documentos, imágenes o estudios del paciente</p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="bg-slate-50/50">
                <TableHead className="text-xs font-semibold">Archivo</TableHead>
                <TableHead className="text-xs font-semibold">Tipo</TableHead>
                <TableHead className="text-xs font-semibold">Tamaño</TableHead>
                <TableHead className="text-xs font-semibold">Fecha</TableHead>
                <TableHead className="text-xs font-semibold text-right">Acciones</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {files.map((f, idx) => {
                const ft = FILE_ICONS[f.content_type] || { icon: FileText, color: 'text-slate-500 bg-slate-50' };
                const FIcon = ft.icon;
                return (
                  <TableRow key={idx} data-testid={`file-row-${idx}`}>
                    <TableCell>
                      <div className="flex items-center gap-2.5">
                        <div className={`w-8 h-8 rounded flex items-center justify-center ${ft.color}`}>
                          <FIcon className="w-4 h-4" />
                        </div>
                        <span className="text-sm font-medium text-slate-700 truncate max-w-[200px]">{f.name}</span>
                      </div>
                    </TableCell>
                    <TableCell className="text-xs text-slate-500">{f.content_type || '—'}</TableCell>
                    <TableCell className="text-xs text-slate-500">{formatFileSize(f.size)}</TableCell>
                    <TableCell className="text-xs text-slate-500">{formatDate(f.created_at)}</TableCell>
                    <TableCell>
                      <div className="flex items-center justify-end gap-1">
                        <Button variant="ghost" size="sm" onClick={() => onDownload(f.name)} className="h-7 w-7 p-0" data-testid={`download-file-${idx}`}>
                          <Download className="w-3.5 h-3.5 text-slate-600" />
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => onDelete(f.name)} className="h-7 w-7 p-0 hover:text-red-600" data-testid={`delete-file-${idx}`}>
                          <Trash2 className="w-3.5 h-3.5" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
