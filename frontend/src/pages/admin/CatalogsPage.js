import { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../../context/AuthContext';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
import { Switch } from '../../components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';
import { 
  Plus, 
  Pill,
  FlaskConical,
  FileCode,
  Edit2,
  Trash2
} from 'lucide-react';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function CatalogsPage() {
  const [activeTab, setActiveTab] = useState('medications');
  const [medications, setMedications] = useState([]);
  const [labStudies, setLabStudies] = useState([]);
  const [icd10Codes, setIcd10Codes] = useState([]);
  const [loading, setLoading] = useState(true);
  
  const [showModal, setShowModal] = useState(false);
  const [modalType, setModalType] = useState('');
  const [editingItem, setEditingItem] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const [medForm, setMedForm] = useState({ generic_name: '', brand_name: '', presentations: '', category: '' });
  const [labForm, setLabForm] = useState({ name: '', category: '', preparation: '' });
  const [icdForm, setIcdForm] = useState({ code: '', description_es: '', category: '', is_common: false });

  const { getAuthHeaders } = useAuth();

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [medsRes, labsRes, icdRes] = await Promise.all([
        axios.get(`${API}/admin/catalogs/medications`, { headers: getAuthHeaders() }),
        axios.get(`${API}/admin/catalogs/lab-studies`, { headers: getAuthHeaders() }),
        axios.get(`${API}/admin/catalogs/icd10`, { headers: getAuthHeaders() })
      ]);
      setMedications(medsRes.data);
      setLabStudies(labsRes.data);
      setIcd10Codes(icdRes.data);
    } catch (error) {
      console.error('Fetch catalogs error:', error);
      toast.error('Error al cargar catálogos');
    } finally {
      setLoading(false);
    }
  };

  const openAddModal = (type) => {
    setModalType(type);
    setEditingItem(null);
    if (type === 'medication') setMedForm({ generic_name: '', brand_name: '', presentations: '', category: '' });
    if (type === 'lab') setLabForm({ name: '', category: '', preparation: '' });
    if (type === 'icd10') setIcdForm({ code: '', description_es: '', category: '', is_common: false });
    setShowModal(true);
  };

  const openEditModal = (type, item) => {
    setModalType(type);
    setEditingItem(item);
    if (type === 'medication') {
      setMedForm({
        generic_name: item.generic_name || '',
        brand_name: item.brand_name || '',
        presentations: item.presentations?.join(', ') || '',
        category: item.category || ''
      });
    }
    if (type === 'lab') {
      setLabForm({ name: item.name || '', category: item.category || '', preparation: item.preparation || '' });
    }
    if (type === 'icd10') {
      setIcdForm({ code: item.code || '', description_es: item.description_es || '', category: item.category || '', is_common: item.is_common || false });
    }
    setShowModal(true);
  };

  const handleSubmitMedication = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const data = {
        ...medForm,
        presentations: medForm.presentations.split(',').map(p => p.trim()).filter(p => p)
      };
      if (editingItem) {
        await axios.put(`${API}/admin/catalogs/medications/${editingItem.id}`, data, { headers: getAuthHeaders() });
        toast.success('Medicamento actualizado');
      } else {
        await axios.post(`${API}/admin/catalogs/medications`, data, { headers: getAuthHeaders() });
        toast.success('Medicamento creado');
      }
      setShowModal(false);
      fetchData();
    } catch (error) {
      toast.error('Error al guardar');
    } finally {
      setSubmitting(false);
    }
  };

  const handleSubmitLab = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      if (editingItem) {
        await axios.put(`${API}/admin/catalogs/lab-studies/${editingItem.id}`, labForm, { headers: getAuthHeaders() });
        toast.success('Estudio actualizado');
      } else {
        await axios.post(`${API}/admin/catalogs/lab-studies`, labForm, { headers: getAuthHeaders() });
        toast.success('Estudio creado');
      }
      setShowModal(false);
      fetchData();
    } catch (error) {
      toast.error('Error al guardar');
    } finally {
      setSubmitting(false);
    }
  };

  const handleSubmitIcd10 = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      if (editingItem) {
        await axios.put(`${API}/admin/catalogs/icd10/${editingItem.id}`, icdForm, { headers: getAuthHeaders() });
        toast.success('Código actualizado');
      } else {
        await axios.post(`${API}/admin/catalogs/icd10`, icdForm, { headers: getAuthHeaders() });
        toast.success('Código creado');
      }
      setShowModal(false);
      fetchData();
    } catch (error) {
      toast.error('Error al guardar');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeactivateMed = async (id) => {
    if (!window.confirm('¿Desactivar este medicamento?')) return;
    try {
      await axios.delete(`${API}/admin/catalogs/medications/${id}`, { headers: getAuthHeaders() });
      toast.success('Medicamento desactivado');
      fetchData();
    } catch (error) {
      toast.error('Error al desactivar');
    }
  };

  const handleDeactivateLab = async (id) => {
    if (!window.confirm('¿Desactivar este estudio?')) return;
    try {
      await axios.delete(`${API}/admin/catalogs/lab-studies/${id}`, { headers: getAuthHeaders() });
      toast.success('Estudio desactivado');
      fetchData();
    } catch (error) {
      toast.error('Error al desactivar');
    }
  };

  const handleToggleCommon = async (item) => {
    try {
      await axios.put(`${API}/admin/catalogs/icd10/${item.id}/toggle-common`, {}, { headers: getAuthHeaders() });
      fetchData();
    } catch (error) {
      toast.error('Error al cambiar');
    }
  };

  return (
    <div className="p-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-semibold text-zinc-950 tracking-tight">Catálogos</h1>
        <p className="text-sm text-zinc-500 mt-1">Gestiona los catálogos globales de la plataforma</p>
      </div>

      <div className="bg-white border border-zinc-200">
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <div className="border-b border-zinc-200 px-6">
            <TabsList className="bg-transparent border-0 p-0 h-auto">
              <TabsTrigger 
                value="medications" 
                className="data-[state=active]:border-b-2 data-[state=active]:border-violet-600 data-[state=active]:text-violet-600 rounded-none px-4 py-3"
                data-testid="tab-medications"
              >
                <Pill className="w-4 h-4 mr-2" strokeWidth={1.5} />
                Medicamentos ({medications.filter(m => m.is_active !== false).length})
              </TabsTrigger>
              <TabsTrigger 
                value="lab-studies" 
                className="data-[state=active]:border-b-2 data-[state=active]:border-violet-600 data-[state=active]:text-violet-600 rounded-none px-4 py-3"
                data-testid="tab-lab-studies"
              >
                <FlaskConical className="w-4 h-4 mr-2" strokeWidth={1.5} />
                Estudios de Lab ({labStudies.filter(l => l.is_active !== false).length})
              </TabsTrigger>
              <TabsTrigger 
                value="icd10" 
                className="data-[state=active]:border-b-2 data-[state=active]:border-violet-600 data-[state=active]:text-violet-600 rounded-none px-4 py-3"
                data-testid="tab-icd10"
              >
                <FileCode className="w-4 h-4 mr-2" strokeWidth={1.5} />
                Códigos CIE-10 ({icd10Codes.length})
              </TabsTrigger>
            </TabsList>
          </div>

          {/* Medications Tab */}
          <TabsContent value="medications" className="m-0">
            <div className="p-4 border-b border-zinc-200 flex justify-end">
              <Button onClick={() => openAddModal('medication')} className="btn-primary" data-testid="add-medication-btn">
                <Plus className="w-4 h-4 mr-2" strokeWidth={1.5} />
                Agregar medicamento
              </Button>
            </div>
            <div className="overflow-x-auto">
              <table className="data-table" data-testid="medications-table">
                <thead>
                  <tr className="bg-zinc-50">
                    <th>Nombre genérico</th>
                    <th>Marca</th>
                    <th>Presentaciones</th>
                    <th>Categoría</th>
                    <th>Estado</th>
                    <th className="w-24">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr><td colSpan={6} className="text-center py-8 text-zinc-500">Cargando...</td></tr>
                  ) : medications.length > 0 ? (
                    medications.map((med) => (
                      <tr key={med.id} data-testid={`med-row-${med.id}`}>
                        <td className="font-medium text-zinc-900">{med.generic_name}</td>
                        <td>{med.brand_name || '-'}</td>
                        <td className="text-xs">{med.presentations?.join(', ') || '-'}</td>
                        <td>{med.category || '-'}</td>
                        <td>
                          <span className={`badge ${med.is_active !== false ? 'badge-active' : 'badge-inactive'}`}>
                            {med.is_active !== false ? 'Activo' : 'Inactivo'}
                          </span>
                        </td>
                        <td>
                          <div className="flex gap-1">
                            <Button variant="ghost" size="sm" onClick={() => openEditModal('medication', med)} data-testid={`edit-med-${med.id}`}>
                              <Edit2 className="w-4 h-4" strokeWidth={1.5} />
                            </Button>
                            {med.is_active !== false && (
                              <Button variant="ghost" size="sm" onClick={() => handleDeactivateMed(med.id)} className="text-red-600" data-testid={`delete-med-${med.id}`}>
                                <Trash2 className="w-4 h-4" strokeWidth={1.5} />
                              </Button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr><td colSpan={6} className="text-center py-8 text-zinc-500">No hay medicamentos</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </TabsContent>

          {/* Lab Studies Tab */}
          <TabsContent value="lab-studies" className="m-0">
            <div className="p-4 border-b border-zinc-200 flex justify-end">
              <Button onClick={() => openAddModal('lab')} className="btn-primary" data-testid="add-lab-btn">
                <Plus className="w-4 h-4 mr-2" strokeWidth={1.5} />
                Agregar estudio
              </Button>
            </div>
            <div className="overflow-x-auto">
              <table className="data-table" data-testid="lab-studies-table">
                <thead>
                  <tr className="bg-zinc-50">
                    <th>Nombre</th>
                    <th>Categoría</th>
                    <th>Preparación</th>
                    <th>Estado</th>
                    <th className="w-24">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr><td colSpan={5} className="text-center py-8 text-zinc-500">Cargando...</td></tr>
                  ) : labStudies.length > 0 ? (
                    labStudies.map((study) => (
                      <tr key={study.id} data-testid={`lab-row-${study.id}`}>
                        <td className="font-medium text-zinc-900">{study.name}</td>
                        <td>{study.category || '-'}</td>
                        <td className="text-xs max-w-xs truncate">{study.preparation || '-'}</td>
                        <td>
                          <span className={`badge ${study.is_active !== false ? 'badge-active' : 'badge-inactive'}`}>
                            {study.is_active !== false ? 'Activo' : 'Inactivo'}
                          </span>
                        </td>
                        <td>
                          <div className="flex gap-1">
                            <Button variant="ghost" size="sm" onClick={() => openEditModal('lab', study)} data-testid={`edit-lab-${study.id}`}>
                              <Edit2 className="w-4 h-4" strokeWidth={1.5} />
                            </Button>
                            {study.is_active !== false && (
                              <Button variant="ghost" size="sm" onClick={() => handleDeactivateLab(study.id)} className="text-red-600" data-testid={`delete-lab-${study.id}`}>
                                <Trash2 className="w-4 h-4" strokeWidth={1.5} />
                              </Button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr><td colSpan={5} className="text-center py-8 text-zinc-500">No hay estudios</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </TabsContent>

          {/* ICD-10 Tab */}
          <TabsContent value="icd10" className="m-0">
            <div className="p-4 border-b border-zinc-200 flex justify-end">
              <Button onClick={() => openAddModal('icd10')} className="btn-primary" data-testid="add-icd10-btn">
                <Plus className="w-4 h-4 mr-2" strokeWidth={1.5} />
                Agregar código
              </Button>
            </div>
            <div className="overflow-x-auto">
              <table className="data-table" data-testid="icd10-table">
                <thead>
                  <tr className="bg-zinc-50">
                    <th>Código</th>
                    <th>Descripción</th>
                    <th>Categoría</th>
                    <th>Común</th>
                    <th className="w-24">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr><td colSpan={5} className="text-center py-8 text-zinc-500">Cargando...</td></tr>
                  ) : icd10Codes.length > 0 ? (
                    icd10Codes.map((code) => (
                      <tr key={code.id} data-testid={`icd-row-${code.id}`}>
                        <td className="font-mono font-medium text-zinc-900">{code.code}</td>
                        <td>{code.description_es}</td>
                        <td>{code.category || '-'}</td>
                        <td>
                          <Switch 
                            checked={code.is_common} 
                            onCheckedChange={() => handleToggleCommon(code)}
                            data-testid={`toggle-common-${code.id}`}
                          />
                        </td>
                        <td>
                          <Button variant="ghost" size="sm" onClick={() => openEditModal('icd10', code)} data-testid={`edit-icd-${code.id}`}>
                            <Edit2 className="w-4 h-4" strokeWidth={1.5} />
                          </Button>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr><td colSpan={5} className="text-center py-8 text-zinc-500">No hay códigos</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </TabsContent>
        </Tabs>
      </div>

      {/* Modal */}
      <Dialog open={showModal} onOpenChange={setShowModal}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="text-xl font-semibold text-zinc-950">
              {editingItem ? 'Editar' : 'Agregar'} {modalType === 'medication' ? 'Medicamento' : modalType === 'lab' ? 'Estudio' : 'Código CIE-10'}
            </DialogTitle>
          </DialogHeader>

          {modalType === 'medication' && (
            <form onSubmit={handleSubmitMedication} className="mt-4 space-y-4">
              <div>
                <Label className="form-label">Nombre genérico *</Label>
                <Input
                  value={medForm.generic_name}
                  onChange={(e) => setMedForm(prev => ({ ...prev, generic_name: e.target.value }))}
                  className="form-input"
                  required
                  data-testid="med-generic-input"
                />
              </div>
              <div>
                <Label className="form-label">Marca</Label>
                <Input
                  value={medForm.brand_name}
                  onChange={(e) => setMedForm(prev => ({ ...prev, brand_name: e.target.value }))}
                  className="form-input"
                  data-testid="med-brand-input"
                />
              </div>
              <div>
                <Label className="form-label">Presentaciones (separadas por coma)</Label>
                <Input
                  value={medForm.presentations}
                  onChange={(e) => setMedForm(prev => ({ ...prev, presentations: e.target.value }))}
                  className="form-input"
                  placeholder="Ej: 500mg tabletas, 250mg/5ml jarabe"
                  data-testid="med-presentations-input"
                />
              </div>
              <div>
                <Label className="form-label">Categoría</Label>
                <Input
                  value={medForm.category}
                  onChange={(e) => setMedForm(prev => ({ ...prev, category: e.target.value }))}
                  className="form-input"
                  placeholder="Ej: Analgésicos, Antibióticos"
                  data-testid="med-category-input"
                />
              </div>
              <div className="flex justify-end gap-3 pt-4">
                <Button type="button" variant="outline" onClick={() => setShowModal(false)} className="btn-secondary">Cancelar</Button>
                <Button type="submit" className="btn-primary" disabled={submitting} data-testid="submit-med-btn">
                  {submitting ? 'Guardando...' : 'Guardar'}
                </Button>
              </div>
            </form>
          )}

          {modalType === 'lab' && (
            <form onSubmit={handleSubmitLab} className="mt-4 space-y-4">
              <div>
                <Label className="form-label">Nombre *</Label>
                <Input
                  value={labForm.name}
                  onChange={(e) => setLabForm(prev => ({ ...prev, name: e.target.value }))}
                  className="form-input"
                  required
                  data-testid="lab-name-input"
                />
              </div>
              <div>
                <Label className="form-label">Categoría</Label>
                <Input
                  value={labForm.category}
                  onChange={(e) => setLabForm(prev => ({ ...prev, category: e.target.value }))}
                  className="form-input"
                  placeholder="Ej: Hematología, Química sanguínea"
                  data-testid="lab-category-input"
                />
              </div>
              <div>
                <Label className="form-label">Preparación del paciente</Label>
                <Textarea
                  value={labForm.preparation}
                  onChange={(e) => setLabForm(prev => ({ ...prev, preparation: e.target.value }))}
                  className="form-input min-h-[80px]"
                  placeholder="Ej: Ayuno de 8-12 horas"
                  data-testid="lab-preparation-input"
                />
              </div>
              <div className="flex justify-end gap-3 pt-4">
                <Button type="button" variant="outline" onClick={() => setShowModal(false)} className="btn-secondary">Cancelar</Button>
                <Button type="submit" className="btn-primary" disabled={submitting} data-testid="submit-lab-btn">
                  {submitting ? 'Guardando...' : 'Guardar'}
                </Button>
              </div>
            </form>
          )}

          {modalType === 'icd10' && (
            <form onSubmit={handleSubmitIcd10} className="mt-4 space-y-4">
              <div>
                <Label className="form-label">Código *</Label>
                <Input
                  value={icdForm.code}
                  onChange={(e) => setIcdForm(prev => ({ ...prev, code: e.target.value.toUpperCase() }))}
                  className="form-input font-mono"
                  required
                  placeholder="Ej: J00, A09.0"
                  data-testid="icd-code-input"
                />
              </div>
              <div>
                <Label className="form-label">Descripción en español *</Label>
                <Input
                  value={icdForm.description_es}
                  onChange={(e) => setIcdForm(prev => ({ ...prev, description_es: e.target.value }))}
                  className="form-input"
                  required
                  data-testid="icd-description-input"
                />
              </div>
              <div>
                <Label className="form-label">Categoría</Label>
                <Input
                  value={icdForm.category}
                  onChange={(e) => setIcdForm(prev => ({ ...prev, category: e.target.value }))}
                  className="form-input"
                  placeholder="Ej: Enfermedades respiratorias"
                  data-testid="icd-category-input"
                />
              </div>
              <div className="flex items-center gap-2">
                <Switch 
                  checked={icdForm.is_common} 
                  onCheckedChange={(checked) => setIcdForm(prev => ({ ...prev, is_common: checked }))}
                  data-testid="icd-common-switch"
                />
                <Label className="text-sm">Marcar como código común</Label>
              </div>
              <div className="flex justify-end gap-3 pt-4">
                <Button type="button" variant="outline" onClick={() => setShowModal(false)} className="btn-secondary">Cancelar</Button>
                <Button type="submit" className="btn-primary" disabled={submitting} data-testid="submit-icd-btn">
                  {submitting ? 'Guardando...' : 'Guardar'}
                </Button>
              </div>
            </form>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
