import { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Checkbox } from '../../components/ui/checkbox';
import { Badge } from '../../components/ui/badge';
import { Separator } from '../../components/ui/separator';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../components/ui/dialog';
import { toast } from 'sonner';
import { CreditCard, Save, Settings, Check } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function PlansPage() {
  const { getAuthHeaders } = useAuth();
  const headers = getAuthHeaders();
  const [plans, setPlans] = useState([]);
  const [features, setFeatures] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editPlan, setEditPlan] = useState(null);
  const [editForm, setEditForm] = useState({});
  const [planFeatureIds, setPlanFeatureIds] = useState([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        const [plansRes, featuresRes] = await Promise.all([
          axios.get(`${API}/admin/plans`, { headers }),
          axios.get(`${API}/admin/features`, { headers }),
        ]);
        setPlans(plansRes.data || []);
        setFeatures(featuresRes.data || []);
      } catch { toast.error('Error al cargar datos'); }
      finally { setLoading(false); }
    };
    load();
  }, []);

  const openEditPlan = async (plan) => {
    setEditPlan(plan);
    setEditForm({
      name: plan.name, description: plan.description || '',
      price_monthly: plan.price_monthly, price_yearly: plan.price_yearly,
      max_users: plan.max_users, max_patients: plan.max_patients,
      max_storage_mb: plan.max_storage_mb, max_branches: plan.max_branches,
    });
    try {
      const res = await axios.get(`${API}/admin/plans/${plan.id}/features`, { headers });
      setPlanFeatureIds(res.data || []);
    } catch { setPlanFeatureIds([]); }
  };

  const toggleFeature = (featureId) => {
    setPlanFeatureIds(prev =>
      prev.includes(featureId) ? prev.filter(id => id !== featureId) : [...prev, featureId]
    );
  };

  const savePlan = async () => {
    if (!editPlan) return;
    setSaving(true);
    try {
      await Promise.all([
        axios.put(`${API}/admin/plans/${editPlan.id}`, editForm, { headers }),
        axios.put(`${API}/admin/plans/${editPlan.id}/features`, { feature_ids: planFeatureIds }, { headers }),
      ]);
      toast.success('Plan actualizado');
      setEditPlan(null);
      const res = await axios.get(`${API}/admin/plans`, { headers });
      setPlans(res.data || []);
    } catch { toast.error('Error al guardar'); }
    finally { setSaving(false); }
  };

  const uf = (field, value) => setEditForm(prev => ({ ...prev, [field]: value }));

  const grouped = {};
  features.forEach(f => {
    const cat = f.category || 'other';
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(f);
  });
  const CAT_LABELS = { clinical: 'Clínico', administrative: 'Administrativo', reports: 'Reportes' };

  if (loading) return <div className="flex justify-center items-center h-96"><div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" /></div>;

  return (
    <div className="p-6 lg:p-8" data-testid="plans-page">
      <h1 className="text-2xl font-bold text-slate-900 mb-1">Planes</h1>
      <p className="text-sm text-slate-500 mb-6">Gestión de planes y módulos del sistema</p>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        {plans.map(plan => (
          <Card key={plan.id} className="border border-slate-200 hover:shadow-md transition-shadow" data-testid={`plan-card-${plan.code}`}>
            <CardContent className="p-5">
              <div className="flex items-center justify-between mb-3">
                <Badge className={`text-sm ${plan.code === 'enterprise' ? 'bg-violet-600' : plan.code === 'professional' ? 'bg-teal-600' : 'bg-slate-600'} text-white`}>{plan.name}</Badge>
              </div>
              <p className="text-xs text-slate-500 mb-3">{plan.description}</p>
              <div className="flex items-baseline gap-1 mb-3">
                <span className="text-2xl font-bold text-slate-900">${plan.price_monthly}</span>
                <span className="text-xs text-slate-400">/mes</span>
                <span className="text-xs text-slate-300 ml-2">${plan.price_yearly}/año</span>
              </div>
              <div className="space-y-1 text-xs text-slate-600 mb-4">
                <p>{plan.max_users} usuarios</p>
                <p>{plan.max_patients?.toLocaleString()} pacientes</p>
                <p>{(plan.max_storage_mb / 1024).toFixed(0)} GB almacenamiento</p>
                <p>{plan.max_branches} sucursal{plan.max_branches > 1 ? 'es' : ''}</p>
              </div>
              <Button variant="outline" size="sm" className="w-full text-xs" onClick={() => openEditPlan(plan)} data-testid={`edit-plan-${plan.code}`}>
                <Settings className="w-3.5 h-3.5 mr-1" /> Editar plan
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Edit Plan Dialog */}
      <Dialog open={!!editPlan} onOpenChange={() => setEditPlan(null)}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto" data-testid="edit-plan-dialog">
          <DialogHeader>
            <DialogTitle>Editar plan: {editPlan?.name}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="grid grid-cols-2 gap-3">
              <div><Label className="text-xs">Nombre</Label><Input className="mt-1 text-sm" value={editForm.name || ''} onChange={e => uf('name', e.target.value)} /></div>
              <div><Label className="text-xs">Descripción</Label><Input className="mt-1 text-sm" value={editForm.description || ''} onChange={e => uf('description', e.target.value)} /></div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label className="text-xs">Precio mensual ($)</Label><Input type="number" step="0.01" className="mt-1 text-sm" value={editForm.price_monthly ?? ''} onChange={e => uf('price_monthly', parseFloat(e.target.value))} /></div>
              <div><Label className="text-xs">Precio anual ($)</Label><Input type="number" step="0.01" className="mt-1 text-sm" value={editForm.price_yearly ?? ''} onChange={e => uf('price_yearly', parseFloat(e.target.value))} /></div>
            </div>
            <div className="grid grid-cols-4 gap-3">
              <div><Label className="text-xs">Máx usuarios</Label><Input type="number" className="mt-1 text-sm" value={editForm.max_users ?? ''} onChange={e => uf('max_users', parseInt(e.target.value))} /></div>
              <div><Label className="text-xs">Máx pacientes</Label><Input type="number" className="mt-1 text-sm" value={editForm.max_patients ?? ''} onChange={e => uf('max_patients', parseInt(e.target.value))} /></div>
              <div><Label className="text-xs">Almacenamiento (MB)</Label><Input type="number" className="mt-1 text-sm" value={editForm.max_storage_mb ?? ''} onChange={e => uf('max_storage_mb', parseInt(e.target.value))} /></div>
              <div><Label className="text-xs">Máx sucursales</Label><Input type="number" className="mt-1 text-sm" value={editForm.max_branches ?? ''} onChange={e => uf('max_branches', parseInt(e.target.value))} /></div>
            </div>
            <Separator />
            <p className="text-sm font-semibold text-slate-700">Módulos incluidos</p>
            <div className="grid grid-cols-2 gap-x-6 gap-y-1">
              {Object.entries(grouped).map(([cat, catFeatures]) => (
                <div key={cat} className="space-y-1 mb-3">
                  <p className="text-xs font-bold text-slate-500 uppercase">{CAT_LABELS[cat] || cat}</p>
                  {catFeatures.map(f => (
                    <label key={f.id} className="flex items-center gap-2 cursor-pointer py-0.5">
                      <Checkbox checked={planFeatureIds.includes(f.id)} onCheckedChange={() => toggleFeature(f.id)} />
                      <span className="text-sm text-slate-700">{f.name}</span>
                    </label>
                  ))}
                </div>
              ))}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditPlan(null)}>Cancelar</Button>
            <Button className="bg-teal-600 hover:bg-teal-700" onClick={savePlan} disabled={saving} data-testid="save-plan-btn">
              <Save className="w-4 h-4 mr-1" /> {saving ? 'Guardando...' : 'Guardar'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
