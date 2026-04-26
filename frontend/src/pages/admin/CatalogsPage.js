import { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../../context/AuthContext';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
import { Switch } from '../../components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import CsvImportDialog from '../../components/CsvImportDialog';
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
  Trash2,
  Upload,
  FileUp,
  CheckCircle,
  AlertCircle,
  Search
} from 'lucide-react';
import { toast } from 'sonner';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function CatalogsPage() {
  const [activeTab, setActiveTab] = useState('medications');
  const [medications, setMedications] = useState([]);
  const [labStudies, setLabStudies] = useState([]);
  const [icd10Codes, setIcd10Codes] = useState([]);
  const [loading, setLoading] = useState(true);
  
  const [showModal, setShowModal] = useState(false);
  const [showBulkModal, setShowBulkModal] = useState(false);
  const [csvCatalog, setCsvCatalog] = useState(null);
  const [modalType, setModalType] = useState('');
  const [editingItem, setEditingItem] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [bulkResult, setBulkResult] = useState(null);

  const [medForm, setMedForm] = useState({ generic_name: '', brand_name: '', presentations: '', category: '' });
  const [labForm, setLabForm] = useState({ name: '', category: '', preparation: '' });
  const [icdForm, setIcdForm] = useState({ code: '', description_es: '', category: '', is_common: false });
  const [bulkText, setBulkText] = useState('');

  // Search/filter states
  const [medSearch, setMedSearch] = useState('');
  const [medCategoryFilter, setMedCategoryFilter] = useState('all');
  const [labSearch, setLabSearch] = useState('');
  const [labCategoryFilter, setLabCategoryFilter] = useState('all');
  const [icdSearch, setIcdSearch] = useState('');
  const [icdCategoryFilter, setIcdCategoryFilter] = useState('all');
  const [icdCommonFilter, setIcdCommonFilter] = useState('all');

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

  // Filtered data
  const filteredMeds = medications.filter(m => {
    const search = medSearch.toLowerCase();
    const matchesSearch = !search || 
      (m.generic_name || '').toLowerCase().includes(search) || 
      (m.brand_name || '').toLowerCase().includes(search) ||
      (m.category || '').toLowerCase().includes(search);
    const matchesCat = medCategoryFilter === 'all' || m.category === medCategoryFilter;
    return matchesSearch && matchesCat;
  });

  const filteredLabs = labStudies.filter(s => {
    const search = labSearch.toLowerCase();
    const matchesSearch = !search || 
      (s.name || '').toLowerCase().includes(search) ||
      (s.category || '').toLowerCase().includes(search) ||
      (s.preparation || '').toLowerCase().includes(search);
    const matchesCat = labCategoryFilter === 'all' || s.category === labCategoryFilter;
    return matchesSearch && matchesCat;
  });

  const filteredIcd = icd10Codes.filter(c => {
    const search = icdSearch.toLowerCase();
    const matchesSearch = !search || 
      (c.code || '').toLowerCase().includes(search) || 
      (c.description_es || '').toLowerCase().includes(search) ||
      (c.category || '').toLowerCase().includes(search);
    const matchesCat = icdCategoryFilter === 'all' || c.category === icdCategoryFilter;
    const matchesCommon = icdCommonFilter === 'all' || (icdCommonFilter === 'yes' ? c.is_common : !c.is_common);
    return matchesSearch && matchesCat && matchesCommon;
  });

  const medCategories = [...new Set(medications.map(m => m.category).filter(Boolean))].sort();
  const labCategories = [...new Set(labStudies.map(s => s.category).filter(Boolean))].sort();
  const icdCategories = [...new Set(icd10Codes.map(c => c.category).filter(Boolean))].sort();

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

  const openBulkModal = (type) => {
    setModalType(type);
    setBulkText('');
    setBulkResult(null);
    setShowBulkModal(true);
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

  const handleBulkImport = async () => {
    setSubmitting(true);
    setBulkResult(null);
    
    try {
      let data;
      let endpoint;
      
      // Parse the bulk text based on type
      const lines = bulkText.trim().split('\n').filter(line => line.trim());
      
      if (modalType === 'medication') {
        // Format: generic_name | brand_name | presentations | category
        const medications = lines.map(line => {
          const parts = line.split('|').map(p => p.trim());
          return {
            generic_name: parts[0] || '',
            brand_name: parts[1] || null,
            presentations: parts[2] ? parts[2].split(',').map(p => p.trim()) : [],
            category: parts[3] || null
          };
        }).filter(m => m.generic_name);
        
        data = { medications };
        endpoint = `${API}/admin/catalogs/medications/bulk`;
      } else if (modalType === 'lab') {
        // Format: name | category | preparation
        const studies = lines.map(line => {
          const parts = line.split('|').map(p => p.trim());
          return {
            name: parts[0] || '',
            category: parts[1] || null,
            preparation: parts[2] || null
          };
        }).filter(s => s.name);
        
        data = { studies };
        endpoint = `${API}/admin/catalogs/lab-studies/bulk`;
      } else if (modalType === 'icd10') {
        // Format: code | description_es | category | is_common (1/0)
        const codes = lines.map(line => {
          const parts = line.split('|').map(p => p.trim());
          return {
            code: parts[0] || '',
            description_es: parts[1] || '',
            category: parts[2] || null,
            is_common: parts[3] === '1' || parts[3]?.toLowerCase() === 'true'
          };
        }).filter(c => c.code && c.description_es);
        
        data = { codes };
        endpoint = `${API}/admin/catalogs/icd10/bulk`;
      }
      
      const response = await axios.post(endpoint, data, { headers: getAuthHeaders() });
      setBulkResult(response.data);
      
      if (response.data.imported > 0) {
        toast.success(`${response.data.imported} registros importados`);
        fetchData();
      }
    } catch (error) {
      toast.error('Error en la importación');
      setBulkResult({ imported: 0, errors: [error.message], total: 0 });
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

  const getBulkPlaceholder = () => {
    if (modalType === 'medication') {
      return `Formato: nombre_genérico | marca | presentaciones | categoría
Ejemplo:
Paracetamol | Tylenol | 500mg tabletas, 120mg/5ml jarabe | Analgésicos
Ibuprofeno | Advil | 400mg tabletas, 200mg cápsulas | Antiinflamatorios
Amoxicilina | Amoxil | 500mg cápsulas, 250mg/5ml suspensión | Antibióticos`;
    } else if (modalType === 'lab') {
      return `Formato: nombre | categoría | preparación
Ejemplo:
Hemograma completo | Hematología | Ayuno no requerido
Glucosa en ayunas | Química sanguínea | Ayuno de 8-12 horas
Perfil lipídico | Química sanguínea | Ayuno de 12 horas
TSH | Hormonas | Sin preparación especial`;
    } else if (modalType === 'icd10') {
      return `Formato: código | descripción | categoría | común (1/0)
Ejemplo:
J00 | Rinofaringitis aguda (resfriado común) | Respiratorias | 1
A09 | Diarrea y gastroenteritis de presunto origen infeccioso | Digestivas | 1
I10 | Hipertensión esencial (primaria) | Cardiovasculares | 1
E11 | Diabetes mellitus tipo 2 | Endocrinas | 1
M54.5 | Lumbago no especificado | Musculoesqueléticas | 1`;
    }
    return '';
  };

  const getBulkTitle = () => {
    if (modalType === 'medication') return 'Importar Medicamentos';
    if (modalType === 'lab') return 'Importar Estudios de Laboratorio';
    if (modalType === 'icd10') return 'Importar Códigos CIE-10';
    return 'Importar';
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
                className="data-[state=active]:border-b-2 data-[state=active]:border-[#2EC4B6] data-[state=active]:text-[#2EC4B6] rounded-none px-4 py-3"
                data-testid="tab-medications"
              >
                <Pill className="w-4 h-4 mr-2" strokeWidth={1.5} />
                Medicamentos ({medications.filter(m => m.is_active !== false).length})
              </TabsTrigger>
              <TabsTrigger 
                value="lab-studies" 
                className="data-[state=active]:border-b-2 data-[state=active]:border-[#2EC4B6] data-[state=active]:text-[#2EC4B6] rounded-none px-4 py-3"
                data-testid="tab-lab-studies"
              >
                <FlaskConical className="w-4 h-4 mr-2" strokeWidth={1.5} />
                Estudios de Lab ({labStudies.filter(l => l.is_active !== false).length})
              </TabsTrigger>
              <TabsTrigger 
                value="icd10" 
                className="data-[state=active]:border-b-2 data-[state=active]:border-[#2EC4B6] data-[state=active]:text-[#2EC4B6] rounded-none px-4 py-3"
                data-testid="tab-icd10"
              >
                <FileCode className="w-4 h-4 mr-2" strokeWidth={1.5} />
                Códigos CIE-10 ({icd10Codes.length})
              </TabsTrigger>
            </TabsList>
          </div>

          {/* Medications Tab */}
          <TabsContent value="medications" className="m-0">
            <div className="p-4 border-b border-zinc-200 flex items-center gap-3">
              <div className="relative flex-1 max-w-sm">
                <Search className="w-4 h-4 absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-400" />
                <Input className="pl-8 h-9 text-sm" placeholder="Buscar por nombre, marca..." value={medSearch} onChange={e => setMedSearch(e.target.value)} data-testid="med-search" />
              </div>
              <Select value={medCategoryFilter} onValueChange={setMedCategoryFilter}>
                <SelectTrigger className="w-[180px] h-9 text-sm" data-testid="med-category-filter">
                  <SelectValue placeholder="Categoría" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todas las categorías</SelectItem>
                  {medCategories.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                </SelectContent>
              </Select>
              {(medSearch || medCategoryFilter !== 'all') && (
                <span className="text-xs text-zinc-500">{filteredMeds.length} de {medications.filter(m => m.is_active !== false).length}</span>
              )}
              <div className="ml-auto flex gap-2">
                <Button onClick={() => setCsvCatalog('medications')} variant="outline" className="border-[#2EC4B6] text-[#2EC4B6] hover:bg-[#2EC4B6]/10" data-testid="csv-import-medications-btn">
                  <Upload className="w-4 h-4 mr-2" strokeWidth={1.5} />
                  CSV
                </Button>
                <Button onClick={() => openBulkModal('medication')} variant="outline" className="border-[#2EC4B6] text-[#2EC4B6] hover:bg-[#2EC4B6]/10" data-testid="bulk-import-medications-btn">
                  <Upload className="w-4 h-4 mr-2" strokeWidth={1.5} />
                  Importar
                </Button>
                <Button onClick={() => openAddModal('medication')} className="bg-[#0A2540] hover:bg-[#0A2540]/90" data-testid="add-medication-btn">
                  <Plus className="w-4 h-4 mr-2" strokeWidth={1.5} />
                  Agregar
                </Button>
              </div>
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
                  ) : filteredMeds.length > 0 ? (
                    filteredMeds.map((med) => (
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
            <div className="p-4 border-b border-zinc-200 flex items-center gap-3">
              <div className="relative flex-1 max-w-sm">
                <Search className="w-4 h-4 absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-400" />
                <Input className="pl-8 h-9 text-sm" placeholder="Buscar por nombre, preparación..." value={labSearch} onChange={e => setLabSearch(e.target.value)} data-testid="lab-search" />
              </div>
              <Select value={labCategoryFilter} onValueChange={setLabCategoryFilter}>
                <SelectTrigger className="w-[180px] h-9 text-sm" data-testid="lab-category-filter">
                  <SelectValue placeholder="Categoría" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todas las categorías</SelectItem>
                  {labCategories.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                </SelectContent>
              </Select>
              {(labSearch || labCategoryFilter !== 'all') && (
                <span className="text-xs text-zinc-500">{filteredLabs.length} de {labStudies.filter(s => s.is_active !== false).length}</span>
              )}
              <div className="ml-auto flex gap-2">
                <Button onClick={() => setCsvCatalog('lab-studies')} variant="outline" className="border-[#2EC4B6] text-[#2EC4B6] hover:bg-[#2EC4B6]/10" data-testid="csv-import-lab-btn">
                  <Upload className="w-4 h-4 mr-2" strokeWidth={1.5} />
                  CSV
                </Button>
                <Button onClick={() => openBulkModal('lab')} variant="outline" className="border-[#2EC4B6] text-[#2EC4B6] hover:bg-[#2EC4B6]/10" data-testid="bulk-import-lab-btn">
                  <Upload className="w-4 h-4 mr-2" strokeWidth={1.5} />
                  Importar
                </Button>
                <Button onClick={() => openAddModal('lab')} className="bg-[#0A2540] hover:bg-[#0A2540]/90" data-testid="add-lab-btn">
                  <Plus className="w-4 h-4 mr-2" strokeWidth={1.5} />
                  Agregar
                </Button>
              </div>
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
                  ) : filteredLabs.length > 0 ? (
                    filteredLabs.map((study) => (
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
            <div className="p-4 border-b border-zinc-200 flex items-center gap-3">
              <div className="relative flex-1 max-w-sm">
                <Search className="w-4 h-4 absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-400" />
                <Input className="pl-8 h-9 text-sm" placeholder="Buscar por código o descripción..." value={icdSearch} onChange={e => setIcdSearch(e.target.value)} data-testid="icd-search" />
              </div>
              <Select value={icdCategoryFilter} onValueChange={setIcdCategoryFilter}>
                <SelectTrigger className="w-[180px] h-9 text-sm" data-testid="icd-category-filter">
                  <SelectValue placeholder="Categoría" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todas las categorías</SelectItem>
                  {icdCategories.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                </SelectContent>
              </Select>
              <Select value={icdCommonFilter} onValueChange={setIcdCommonFilter}>
                <SelectTrigger className="w-[140px] h-9 text-sm" data-testid="icd-common-filter">
                  <SelectValue placeholder="Común" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todos</SelectItem>
                  <SelectItem value="yes">Solo comunes</SelectItem>
                  <SelectItem value="no">No comunes</SelectItem>
                </SelectContent>
              </Select>
              {(icdSearch || icdCategoryFilter !== 'all' || icdCommonFilter !== 'all') && (
                <span className="text-xs text-zinc-500">{filteredIcd.length} de {icd10Codes.length}</span>
              )}
              <div className="ml-auto flex gap-2">
                <Button onClick={() => setCsvCatalog('icd10')} variant="outline" className="border-[#2EC4B6] text-[#2EC4B6] hover:bg-[#2EC4B6]/10" data-testid="csv-import-icd10-btn">
                  <Upload className="w-4 h-4 mr-2" strokeWidth={1.5} />
                  CSV
                </Button>
                <Button onClick={() => openBulkModal('icd10')} variant="outline" className="border-[#2EC4B6] text-[#2EC4B6] hover:bg-[#2EC4B6]/10" data-testid="bulk-import-icd10-btn">
                  <Upload className="w-4 h-4 mr-2" strokeWidth={1.5} />
                  Importar
                </Button>
                <Button onClick={() => openAddModal('icd10')} className="bg-[#0A2540] hover:bg-[#0A2540]/90" data-testid="add-icd10-btn">
                  <Plus className="w-4 h-4 mr-2" strokeWidth={1.5} />
                  Agregar
                </Button>
              </div>
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
                  ) : filteredIcd.length > 0 ? (
                    filteredIcd.map((code) => (
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

      {/* Single Item Modal */}
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
                <Button type="button" variant="outline" onClick={() => setShowModal(false)}>Cancelar</Button>
                <Button type="submit" className="bg-[#0A2540] hover:bg-[#0A2540]/90" disabled={submitting} data-testid="submit-med-btn">
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
                <Button type="button" variant="outline" onClick={() => setShowModal(false)}>Cancelar</Button>
                <Button type="submit" className="bg-[#0A2540] hover:bg-[#0A2540]/90" disabled={submitting} data-testid="submit-lab-btn">
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
                <Button type="button" variant="outline" onClick={() => setShowModal(false)}>Cancelar</Button>
                <Button type="submit" className="bg-[#0A2540] hover:bg-[#0A2540]/90" disabled={submitting} data-testid="submit-icd-btn">
                  {submitting ? 'Guardando...' : 'Guardar'}
                </Button>
              </div>
            </form>
          )}
        </DialogContent>
      </Dialog>

      {/* Bulk Import Modal */}
      <Dialog open={showBulkModal} onOpenChange={setShowBulkModal}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="text-xl font-semibold text-zinc-950 flex items-center gap-2">
              <FileUp className="w-5 h-5 text-[#2EC4B6]" strokeWidth={1.5} />
              {getBulkTitle()}
            </DialogTitle>
          </DialogHeader>

          <div className="mt-4 space-y-4">
            <div>
              <Label className="form-label">Pega los datos (un registro por línea)</Label>
              <Textarea
                value={bulkText}
                onChange={(e) => setBulkText(e.target.value)}
                className="form-input min-h-[200px] font-mono text-sm"
                placeholder={getBulkPlaceholder()}
                data-testid="bulk-textarea"
              />
              <p className="text-xs text-zinc-500 mt-2">
                Separa los campos con el caracter <code className="bg-zinc-100 px-1 rounded">|</code> (pipe)
              </p>
            </div>

            {bulkResult && (
              <div className={`p-4 rounded-lg ${bulkResult.imported > 0 ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'}`}>
                <div className="flex items-start gap-3">
                  {bulkResult.imported > 0 ? (
                    <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" strokeWidth={1.5} />
                  ) : (
                    <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" strokeWidth={1.5} />
                  )}
                  <div>
                    <p className={`font-medium ${bulkResult.imported > 0 ? 'text-green-800' : 'text-red-800'}`}>
                      {bulkResult.imported} de {bulkResult.total} registros importados
                    </p>
                    {bulkResult.errors && bulkResult.errors.length > 0 && (
                      <ul className="mt-2 text-sm text-red-700 list-disc list-inside">
                        {bulkResult.errors.slice(0, 5).map((err, i) => (
                          <li key={i}>{err}</li>
                        ))}
                        {bulkResult.errors.length > 5 && (
                          <li>...y {bulkResult.errors.length - 5} errores más</li>
                        )}
                      </ul>
                    )}
                  </div>
                </div>
              </div>
            )}

            <div className="flex justify-end gap-3 pt-4">
              <Button type="button" variant="outline" onClick={() => setShowBulkModal(false)}>
                Cerrar
              </Button>
              <Button 
                onClick={handleBulkImport} 
                className="bg-[#2EC4B6] hover:bg-[#2EC4B6]/90" 
                disabled={submitting || !bulkText.trim()}
                data-testid="submit-bulk-btn"
              >
                {submitting ? 'Importando...' : 'Importar'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* CSV Import Dialog */}
      <CsvImportDialog
        open={!!csvCatalog}
        onOpenChange={(v) => { if (!v) setCsvCatalog(null); }}
        catalog={csvCatalog}
        headers={getAuthHeaders()}
        onSuccess={() => fetchCatalogs()}
      />
    </div>
  );
}
