import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '../../context/AuthContext';
import { useBranch } from '../../context/BranchContext';
import FeatureGate from '../../components/FeatureGate';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
import { Badge } from '../../components/ui/badge';
import { Switch } from '../../components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../components/ui/dialog';
import { Separator } from '../../components/ui/separator';
import { toast } from 'sonner';
import {
  Package, Search, Plus, Edit, Save, AlertTriangle, AlertCircle, Trash2,
  Truck, ArrowDownUp, Users as UsersIcon, ChevronLeft, ChevronRight, Download, Clock
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const UNITS = ['unidad','caja','frasco','ml','mg','tableta','ampolla','tubo','sobre'];
const ADJUST_REASONS = [
  {v:'physical_count', l:'Conteo físico'}, {v:'damage', l:'Daño'},
  {v:'expiration', l:'Vencimiento'}, {v:'loss', l:'Pérdida'}, {v:'other', l:'Otro'},
];
const MVMT_TYPES = {purchase:'Compra',sale:'Venta',adjustment:'Ajuste',return:'Devolución'};

export default function InventoryPage() {
  const { getAuthHeaders } = useAuth();
  const { branches, activeBranch } = useBranch();
  const h = getAuthHeaders();
  const [tab, setTab] = useState('products');

  return (
    <FeatureGate feature="inventory" planRequired="Professional">
      <div className="p-6 lg:p-8" data-testid="inventory-page">
        <h1 className="text-2xl font-bold text-slate-900 mb-1">Inventario</h1>
        <p className="text-sm text-slate-500 mb-4">Gestión de productos, stock y compras</p>
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="bg-slate-100 mb-4">
            <TabsTrigger value="products" data-testid="inv-tab-products"><Package className="w-3.5 h-3.5 mr-1" />Productos</TabsTrigger>
            <TabsTrigger value="stock" data-testid="inv-tab-stock"><AlertTriangle className="w-3.5 h-3.5 mr-1" />Stock</TabsTrigger>
            <TabsTrigger value="purchases" data-testid="inv-tab-purchases"><Truck className="w-3.5 h-3.5 mr-1" />Compras</TabsTrigger>
            <TabsTrigger value="movements" data-testid="inv-tab-movements"><ArrowDownUp className="w-3.5 h-3.5 mr-1" />Movimientos</TabsTrigger>
            <TabsTrigger value="suppliers" data-testid="inv-tab-suppliers"><UsersIcon className="w-3.5 h-3.5 mr-1" />Proveedores</TabsTrigger>
          </TabsList>
          <TabsContent value="products"><ProductsTab headers={h} branches={branches} /></TabsContent>
          <TabsContent value="stock"><StockTab headers={h} branches={branches} activeBranch={activeBranch} /></TabsContent>
          <TabsContent value="purchases"><PurchasesTab headers={h} branches={branches} activeBranch={activeBranch} /></TabsContent>
          <TabsContent value="movements"><MovementsTab headers={h} branches={branches} activeBranch={activeBranch} /></TabsContent>
          <TabsContent value="suppliers"><SuppliersTab headers={h} /></TabsContent>
        </Tabs>
      </div>
    </FeatureGate>
  );
}

/* ============ PRODUCTS TAB ============ */
function ProductsTab({ headers, branches }) {
  const [products, setProducts] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [search, setSearch] = useState('');
  const [catFilter, setCatFilter] = useState('all');
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editProduct, setEditProduct] = useState(null);
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);
  const [showCatForm, setShowCatForm] = useState(false);
  const [catName, setCatName] = useState('');

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({page:String(page),limit:'15'});
      if (search) params.set('q', search);
      if (catFilter !== 'all') params.set('category_id', catFilter);
      const [pRes, cRes] = await Promise.all([
        axios.get(`${API}/clinic/inventory/products?${params}`, {headers}),
        axios.get(`${API}/clinic/inventory/categories`, {headers}),
      ]);
      setProducts(pRes.data.products||[]);setTotal(pRes.data.total||0);setPages(pRes.data.pages||1);
      setCategories(cRes.data||[]);
    } catch { toast.error('Error al cargar productos'); }
    finally { setLoading(false); }
  }, [page, search, catFilter, headers]);

  useEffect(() => { fetch(); }, [fetch]);
  useEffect(() => { setPage(1); }, [search, catFilter]);

  const openNew = () => {
    setEditProduct(null);
    setForm({name:'',sku:'',barcode:'',description:'',brand:'',presentation:'',category_id:'',medication_id:null,cost_price:0,sale_price:0,tax_rate:12,unit:'unidad',min_stock:0,max_stock:null,requires_prescription:false,has_expiration:false,is_active:true});
    setShowForm(true);
  };

  const openEdit = (p) => {
    setEditProduct(p);
    setForm({...p,category_id:p.category_id||''});
    setShowForm(true);
  };

  const handleSave = async () => {
    if (!form.name) { toast.error('Nombre requerido'); return; }
    setSaving(true);
    try {
      const payload = {...form};
      if (!payload.category_id) delete payload.category_id;
      if (editProduct) {
        await axios.put(`${API}/clinic/inventory/products/${editProduct.id}`, payload, {headers});
        toast.success('Producto actualizado');
      } else {
        await axios.post(`${API}/clinic/inventory/products`, payload, {headers});
        toast.success('Producto creado');
      }
      setShowForm(false); fetch();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error'); }
    finally { setSaving(false); }
  };

  const createCat = async () => {
    if (!catName) return;
    try {
      await axios.post(`${API}/clinic/inventory/categories`, {name:catName}, {headers});
      setCatName(''); setShowCatForm(false); fetch(); toast.success('Categoría creada');
    } catch { toast.error('Error'); }
  };

  const uf = (k,v) => setForm(p => ({...p,[k]:v}));
  const margin = form.sale_price && form.cost_price ? (((form.sale_price - form.cost_price) / form.cost_price) * 100).toFixed(1) : 0;

  return (
    <>
      <div className="flex flex-col sm:flex-row gap-3 mb-4">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <Input className="pl-9 text-sm" placeholder="Buscar producto..." value={search} onChange={e=>setSearch(e.target.value)} data-testid="product-search" />
        </div>
        <Select value={catFilter} onValueChange={setCatFilter}>
          <SelectTrigger className="w-44"><SelectValue placeholder="Categoría" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todas</SelectItem>
            {categories.map(c => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
          </SelectContent>
        </Select>
        <Button variant="outline" size="sm" onClick={()=>setShowCatForm(true)}>+ Categoría</Button>
        <Button className="bg-teal-600 hover:bg-teal-700" onClick={openNew} data-testid="new-product-btn"><Plus className="w-4 h-4 mr-1" />Nuevo producto</Button>
      </div>

      {loading ? <div className="flex justify-center py-16"><div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" /></div> :
      products.length === 0 ? <Card className="border-dashed border-2"><CardContent className="p-12 text-center"><Package className="w-10 h-10 text-slate-300 mx-auto mb-2" /><p className="text-sm text-slate-500">No hay productos</p></CardContent></Card> :
      <Card className="border overflow-hidden">
        <Table>
          <TableHeader><TableRow className="bg-slate-50/80">
            <TableHead className="text-xs font-semibold">SKU</TableHead>
            <TableHead className="text-xs font-semibold">Producto</TableHead>
            <TableHead className="text-xs font-semibold">Categoría</TableHead>
            <TableHead className="text-xs font-semibold">Marca</TableHead>
            <TableHead className="text-xs font-semibold text-right">Precio</TableHead>
            <TableHead className="text-xs font-semibold text-center">Stock</TableHead>
            <TableHead className="text-xs font-semibold text-center">Estado</TableHead>
            <TableHead className="text-xs font-semibold text-right"></TableHead>
          </TableRow></TableHeader>
          <TableBody>
            {products.map(p => (
              <TableRow key={p.id} data-testid={`product-row-${p.id}`}>
                <TableCell className="text-xs font-mono text-slate-500">{p.sku||'—'}</TableCell>
                <TableCell><p className="text-sm font-medium">{p.name}</p>{p.presentation && <p className="text-xs text-slate-400">{p.presentation}</p>}</TableCell>
                <TableCell className="text-xs text-slate-500">{p.category_name||'—'}</TableCell>
                <TableCell className="text-xs text-slate-500">{p.brand||'—'}</TableCell>
                <TableCell className="text-right text-sm font-medium">Q{(p.sale_price||0).toFixed(2)}</TableCell>
                <TableCell className="text-center">
                  <span className={`text-sm font-bold ${p.total_stock <= 0 ? 'text-red-600' : p.total_stock <= (p.min_stock||0) ? 'text-amber-600' : 'text-slate-700'}`}>{p.total_stock}</span>
                </TableCell>
                <TableCell className="text-center">
                  <Badge variant="outline" className={`text-xs ${p.is_active ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-600'}`}>{p.is_active ? 'Activo' : 'Inactivo'}</Badge>
                </TableCell>
                <TableCell className="text-right"><Button variant="ghost" size="sm" className="h-7 text-xs" onClick={()=>openEdit(p)}>Editar</Button></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>}

      {pages > 1 && <div className="flex items-center justify-between mt-4"><p className="text-xs text-slate-500">Pág {page}/{pages}</p><div className="flex gap-1"><Button variant="outline" size="sm" disabled={page<=1} onClick={()=>setPage(p=>p-1)}><ChevronLeft className="w-4 h-4" /></Button><Button variant="outline" size="sm" disabled={page>=pages} onClick={()=>setPage(p=>p+1)}><ChevronRight className="w-4 h-4" /></Button></div></div>}

      {/* Product Form */}
      <Dialog open={showForm} onOpenChange={setShowForm}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto" data-testid="product-form">
          <DialogHeader><DialogTitle>{editProduct ? 'Editar' : 'Nuevo'} producto</DialogTitle></DialogHeader>
          <div className="space-y-3 py-2">
            <p className="text-xs font-bold text-slate-500 uppercase">Información básica</p>
            <div className="grid grid-cols-3 gap-3">
              <div><Label className="text-xs">SKU</Label><Input className="mt-1 text-sm" value={form.sku||''} onChange={e=>uf('sku',e.target.value)} data-testid="product-sku" /></div>
              <div><Label className="text-xs">Código de barras</Label><Input className="mt-1 text-sm" value={form.barcode||''} onChange={e=>uf('barcode',e.target.value)} /></div>
              <div><Label className="text-xs">Categoría</Label>
                <Select value={form.category_id||'none'} onValueChange={v=>uf('category_id',v==='none'?'':v)}>
                  <SelectTrigger className="mt-1 text-sm"><SelectValue placeholder="Sin categoría" /></SelectTrigger>
                  <SelectContent><SelectItem value="none">Sin categoría</SelectItem>{categories.map(c=><SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}</SelectContent>
                </Select>
              </div>
            </div>
            <div><Label className="text-xs">Nombre *</Label><Input className="mt-1 text-sm" value={form.name||''} onChange={e=>uf('name',e.target.value)} data-testid="product-name" /></div>
            <div className="grid grid-cols-3 gap-3">
              <div><Label className="text-xs">Marca</Label><Input className="mt-1 text-sm" value={form.brand||''} onChange={e=>uf('brand',e.target.value)} /></div>
              <div><Label className="text-xs">Presentación</Label><Input className="mt-1 text-sm" value={form.presentation||''} onChange={e=>uf('presentation',e.target.value)} placeholder="Caja x 30 tabletas" /></div>
              <div><Label className="text-xs">Unidad</Label>
                <Select value={form.unit||'unidad'} onValueChange={v=>uf('unit',v)}>
                  <SelectTrigger className="mt-1 text-sm"><SelectValue /></SelectTrigger>
                  <SelectContent>{UNITS.map(u=><SelectItem key={u} value={u}>{u}</SelectItem>)}</SelectContent>
                </Select>
              </div>
            </div>
            <div><Label className="text-xs">Descripción</Label><Textarea className="mt-1 text-sm min-h-[50px]" value={form.description||''} onChange={e=>uf('description',e.target.value)} /></div>
            <Separator /><p className="text-xs font-bold text-slate-500 uppercase">Precios</p>
            <div className="grid grid-cols-4 gap-3">
              <div><Label className="text-xs">Costo (Q)</Label><Input type="number" step="0.01" className="mt-1 text-sm" value={form.cost_price??''} onChange={e=>uf('cost_price',parseFloat(e.target.value)||0)} /></div>
              <div><Label className="text-xs">Venta (Q)</Label><Input type="number" step="0.01" className="mt-1 text-sm" value={form.sale_price??''} onChange={e=>uf('sale_price',parseFloat(e.target.value)||0)} data-testid="product-price" /></div>
              <div><Label className="text-xs">IVA (%)</Label><Input type="number" className="mt-1 text-sm" value={form.tax_rate??12} onChange={e=>uf('tax_rate',parseFloat(e.target.value)||0)} /></div>
              <div><Label className="text-xs">Margen</Label><p className={`mt-1 text-sm font-bold ${margin > 0 ? 'text-emerald-600' : 'text-red-600'}`}>{margin}%</p></div>
            </div>
            <Separator /><p className="text-xs font-bold text-slate-500 uppercase">Inventario</p>
            <div className="grid grid-cols-2 gap-3">
              <div><Label className="text-xs">Stock mínimo</Label><Input type="number" className="mt-1 text-sm" value={form.min_stock??0} onChange={e=>uf('min_stock',parseInt(e.target.value)||0)} /></div>
              <div><Label className="text-xs">Stock máximo</Label><Input type="number" className="mt-1 text-sm" value={form.max_stock??''} onChange={e=>uf('max_stock',parseInt(e.target.value)||null)} /></div>
            </div>
            <div className="flex items-center gap-6">
              <label className="flex items-center gap-2 text-sm"><Switch checked={form.requires_prescription} onCheckedChange={v=>uf('requires_prescription',v)} />Requiere receta</label>
              <label className="flex items-center gap-2 text-sm"><Switch checked={form.has_expiration} onCheckedChange={v=>uf('has_expiration',v)} />Tiene vencimiento</label>
              <label className="flex items-center gap-2 text-sm"><Switch checked={form.is_active} onCheckedChange={v=>uf('is_active',v)} />Activo</label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={()=>setShowForm(false)}>Cancelar</Button>
            <Button className="bg-teal-600 hover:bg-teal-700" onClick={handleSave} disabled={saving} data-testid="save-product-btn"><Save className="w-4 h-4 mr-1" />{saving?'...':'Guardar'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Category Form */}
      <Dialog open={showCatForm} onOpenChange={setShowCatForm}>
        <DialogContent className="max-w-sm">
          <DialogHeader><DialogTitle>Nueva categoría</DialogTitle></DialogHeader>
          <div className="py-2"><Label className="text-xs">Nombre</Label><Input className="mt-1 text-sm" value={catName} onChange={e=>setCatName(e.target.value)} data-testid="category-name" /></div>
          <DialogFooter><Button variant="outline" onClick={()=>setShowCatForm(false)}>Cancelar</Button><Button className="bg-teal-600 hover:bg-teal-700" onClick={createCat}>Crear</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

/* ============ STOCK TAB ============ */
function StockTab({ headers, branches, activeBranch }) {
  const [stocks, setStocks] = useState([]);
  const [alerts, setAlerts] = useState({low_stock:[],expiring:[]});
  const [branchFilter, setBranchFilter] = useState(activeBranch?.id || 'all');
  const [loading, setLoading] = useState(true);
  const [showAdjust, setShowAdjust] = useState(null);
  const [adjForm, setAdjForm] = useState({new_quantity:0,reason:'physical_count',notes:''});

  // Sync filter with global activeBranch
  useEffect(() => {
    if (activeBranch?.id) setBranchFilter(activeBranch.id);
  }, [activeBranch?.id]);

  useEffect(() => {
    const load = async () => {
      try {
        const params = branchFilter!=='all' ? `?branch_id=${branchFilter}` : '';
        const [sRes, aRes] = await Promise.all([
          axios.get(`${API}/clinic/inventory/stock${params}`, {headers}),
          axios.get(`${API}/clinic/inventory/alerts`, {headers}),
        ]);
        setStocks(sRes.data||[]);setAlerts(aRes.data||{low_stock:[],expiring:[]});
      } catch {} finally { setLoading(false); }
    };
    load();
  }, [branchFilter, headers]);

  const handleAdjust = async () => {
    if (!showAdjust) return;
    try {
      await axios.post(`${API}/clinic/inventory/adjust`, {
        product_id:showAdjust.product_id, branch_id:showAdjust.branch_id,
        new_quantity:adjForm.new_quantity, reason:adjForm.reason, notes:adjForm.notes,
      }, {headers});
      toast.success('Stock ajustado');
      setShowAdjust(null);
      setBranchFilter(prev => prev); // trigger re-fetch
      window.location.reload();
    } catch (err) { toast.error(err.response?.data?.detail||'Error'); }
  };

  return (
    <>
      {/* Alerts */}
      {(alerts.low_stock.length>0 || alerts.expiring.length>0) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          {alerts.low_stock.length>0 && (
            <Card className="border-red-200 bg-red-50/50"><CardHeader className="pb-1"><CardTitle className="text-xs font-semibold text-red-700 flex items-center gap-1"><AlertCircle className="w-3.5 h-3.5" />Stock bajo ({alerts.low_stock.length})</CardTitle></CardHeader><CardContent className="pt-1">
              {alerts.low_stock.slice(0,3).map((a,i) => <p key={i} className="text-xs text-red-600">{a.name} ({a.sku}) — {a.quantity} en {a.branch_name}</p>)}
            </CardContent></Card>
          )}
          {alerts.expiring.length>0 && (
            <Card className="border-amber-200 bg-amber-50/50"><CardHeader className="pb-1"><CardTitle className="text-xs font-semibold text-amber-700 flex items-center gap-1"><Clock className="w-3.5 h-3.5" />Próximos a vencer ({alerts.expiring.length})</CardTitle></CardHeader><CardContent className="pt-1">
              {alerts.expiring.slice(0,3).map((a,i) => <p key={i} className="text-xs text-amber-600">{a.product_name} lote {a.batch_number} — vence {a.expiration_date?.substring(0,10)}</p>)}
            </CardContent></Card>
          )}
        </div>
      )}

      <div className="flex gap-3 mb-4">
        <Select value={branchFilter} onValueChange={setBranchFilter}>
          <SelectTrigger className="w-48"><SelectValue placeholder="Sucursal" /></SelectTrigger>
          <SelectContent><SelectItem value="all">Todas</SelectItem>{(branches||[]).map(b=><SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>)}</SelectContent>
        </Select>
      </div>

      {loading ? <div className="flex justify-center py-16"><div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" /></div> :
      <Card className="border overflow-hidden">
        <Table>
          <TableHeader><TableRow className="bg-slate-50/80">
            <TableHead className="text-xs font-semibold">Producto</TableHead>
            <TableHead className="text-xs font-semibold">Sucursal</TableHead>
            <TableHead className="text-xs font-semibold text-center">Disponible</TableHead>
            <TableHead className="text-xs font-semibold text-center">Reservado</TableHead>
            <TableHead className="text-xs font-semibold text-center">Mínimo</TableHead>
            <TableHead className="text-xs font-semibold text-center">Estado</TableHead>
            <TableHead className="text-xs font-semibold text-right"></TableHead>
          </TableRow></TableHeader>
          <TableBody>
            {stocks.map(s => (
              <TableRow key={s.id} className={s.status==='critical'?'bg-red-50/50':s.status==='low'?'bg-amber-50/50':''}>
                <TableCell><p className="text-sm font-medium">{s.product_name}</p><p className="text-xs text-slate-400">{s.sku}</p></TableCell>
                <TableCell className="text-sm">{s.branch_name}</TableCell>
                <TableCell className="text-center text-sm font-bold">{s.quantity||0}</TableCell>
                <TableCell className="text-center text-sm">{s.reserved||0}</TableCell>
                <TableCell className="text-center text-sm">{s.min_stock||0}</TableCell>
                <TableCell className="text-center">
                  <Badge variant="outline" className={`text-xs ${s.status==='critical'?'bg-red-100 text-red-700':s.status==='low'?'bg-amber-100 text-amber-700':'bg-emerald-100 text-emerald-700'}`}>
                    {s.status==='critical'?'Crítico':s.status==='low'?'Bajo':'OK'}
                  </Badge>
                </TableCell>
                <TableCell className="text-right">
                  <Button variant="outline" size="sm" className="h-7 text-xs" onClick={()=>{setShowAdjust(s);setAdjForm({new_quantity:s.quantity||0,reason:'physical_count',notes:''});}}>Ajustar</Button>
                </TableCell>
              </TableRow>
            ))}
            {stocks.length===0 && <TableRow><TableCell colSpan={7} className="text-center py-8 text-slate-400">Sin datos de stock</TableCell></TableRow>}
          </TableBody>
        </Table>
      </Card>}

      <Dialog open={!!showAdjust} onOpenChange={()=>setShowAdjust(null)}>
        <DialogContent className="max-w-sm" data-testid="adjust-dialog">
          <DialogHeader><DialogTitle>Ajustar stock</DialogTitle></DialogHeader>
          <div className="space-y-3 py-2">
            <p className="text-sm">{showAdjust?.product_name} — {showAdjust?.branch_name}</p>
            <p className="text-xs text-slate-500">Cantidad actual: <b>{showAdjust?.quantity||0}</b></p>
            <div><Label className="text-xs">Nueva cantidad</Label><Input type="number" className="mt-1 text-sm" value={adjForm.new_quantity} onChange={e=>setAdjForm(p=>({...p,new_quantity:parseInt(e.target.value)||0}))} data-testid="adjust-qty" /></div>
            <div><Label className="text-xs">Motivo</Label>
              <Select value={adjForm.reason} onValueChange={v=>setAdjForm(p=>({...p,reason:v}))}>
                <SelectTrigger className="mt-1 text-sm"><SelectValue /></SelectTrigger>
                <SelectContent>{ADJUST_REASONS.map(r=><SelectItem key={r.v} value={r.v}>{r.l}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div><Label className="text-xs">Notas</Label><Input className="mt-1 text-sm" value={adjForm.notes} onChange={e=>setAdjForm(p=>({...p,notes:e.target.value}))} /></div>
          </div>
          <DialogFooter><Button variant="outline" onClick={()=>setShowAdjust(null)}>Cancelar</Button><Button className="bg-teal-600 hover:bg-teal-700" onClick={handleAdjust} data-testid="confirm-adjust">Ajustar</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

/* ============ PURCHASES TAB ============ */
function PurchasesTab({ headers, branches, activeBranch }) {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({branch_id:'',supplier_name:'',supplier_id:null,order_number:'',notes:'',items:[{product_id:'',product_name:'',quantity:1,unit_cost:0,subtotal:0,batch_number:'',expiration_date:''}]});
  const [suppliers, setSuppliers] = useState([]);
  const [saving, setSaving] = useState(false);
  const [productSearch, setProductSearch] = useState([]);

  useEffect(() => {
    const load = async () => {
      try {
        const [oRes, sRes] = await Promise.all([
          axios.get(`${API}/clinic/inventory/purchase-orders`, {headers}),
          axios.get(`${API}/clinic/inventory/suppliers`, {headers}),
        ]);
        setOrders(oRes.data.orders||[]); setSuppliers(sRes.data||[]);
      } catch {} finally { setLoading(false); }
    };
    load();
  }, [headers]);

  const openNew = () => {
    setForm({branch_id:activeBranch?.id||'',supplier_name:'',supplier_id:null,order_number:`PO-${new Date().toISOString().slice(0,10)}`,notes:'',tax_rate:12,items:[{product_id:'',product_name:'',quantity:1,unit_cost:0,subtotal:0,batch_number:'',expiration_date:''}]});
    setShowForm(true);
  };

  const searchProducts = async (q, idx) => {
    if (q.length < 2) return;
    try {
      const res = await axios.get(`${API}/clinic/inventory/products/search?q=${encodeURIComponent(q)}`, {headers});
      setProductSearch(res.data||[]);
    } catch {}
  };

  const selectProduct = (p, idx) => {
    const items = [...form.items];
    items[idx] = {...items[idx], product_id:p.id, product_name:p.name, unit_cost:p.cost_price||0, subtotal:(items[idx].quantity||1)*(p.cost_price||0)};
    setForm(f=>({...f,items}));
    setProductSearch([]);
  };

  const updateItem = (idx, field, value) => {
    const items = [...form.items];
    items[idx] = {...items[idx], [field]:value};
    if (field === 'quantity' || field === 'unit_cost') {
      items[idx].subtotal = (items[idx].quantity||0) * (items[idx].unit_cost||0);
    }
    setForm(f=>({...f,items}));
  };

  const addItem = () => setForm(f=>({...f,items:[...f.items,{product_id:'',product_name:'',quantity:1,unit_cost:0,subtotal:0,batch_number:'',expiration_date:''}]}));
  const removeItem = (idx) => { if (form.items.length<=1) return; setForm(f=>({...f,items:f.items.filter((_,i)=>i!==idx)})); };

  const handleSave = async (status) => {
    if (!form.branch_id) { toast.error('Seleccione sucursal'); return; }
    if (!form.supplier_name) { toast.error('Ingrese proveedor'); return; }
    setSaving(true);
    try {
      await axios.post(`${API}/clinic/inventory/purchase-orders`, {...form, status, items:form.items.filter(i=>i.product_id)}, {headers});
      toast.success(status==='received'?'Orden recibida y stock actualizado':'Orden guardada');
      setShowForm(false);
      const res = await axios.get(`${API}/clinic/inventory/purchase-orders`, {headers});
      setOrders(res.data.orders||[]);
    } catch (err) { toast.error(err.response?.data?.detail||'Error'); }
    finally { setSaving(false); }
  };

  const subtotal = form.items.reduce((s,i)=>s+(i.subtotal||0),0);
  const tax = subtotal * ((form.tax_rate||12)/100);

  return (
    <>
      <div className="flex justify-between mb-4">
        <div />
        <Button className="bg-teal-600 hover:bg-teal-700" onClick={openNew} data-testid="new-po-btn"><Plus className="w-4 h-4 mr-1" />Nueva orden</Button>
      </div>
      {loading ? <div className="flex justify-center py-16"><div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" /></div> :
      <Card className="border overflow-hidden">
        <Table>
          <TableHeader><TableRow className="bg-slate-50/80">
            <TableHead className="text-xs font-semibold">Orden</TableHead>
            <TableHead className="text-xs font-semibold">Fecha</TableHead>
            <TableHead className="text-xs font-semibold">Proveedor</TableHead>
            <TableHead className="text-xs font-semibold">Sucursal</TableHead>
            <TableHead className="text-xs font-semibold text-right">Total</TableHead>
            <TableHead className="text-xs font-semibold text-center">Estado</TableHead>
          </TableRow></TableHeader>
          <TableBody>
            {orders.map(o=>(
              <TableRow key={o.id}>
                <TableCell className="text-sm font-mono">{o.order_number}</TableCell>
                <TableCell className="text-sm">{o.created_at?.substring(0,10)}</TableCell>
                <TableCell className="text-sm">{o.supplier_name}</TableCell>
                <TableCell className="text-sm">{o.branch_name}</TableCell>
                <TableCell className="text-right text-sm font-medium">Q{(o.total||0).toFixed(2)}</TableCell>
                <TableCell className="text-center"><Badge variant="outline" className={`text-xs ${o.status==='received'?'bg-emerald-50 text-emerald-700':o.status==='cancelled'?'bg-red-50 text-red-600':'bg-amber-50 text-amber-700'}`}>{o.status==='received'?'Recibida':o.status==='cancelled'?'Cancelada':'Pendiente'}</Badge></TableCell>
              </TableRow>
            ))}
            {orders.length===0 && <TableRow><TableCell colSpan={6} className="text-center py-8 text-slate-400">Sin órdenes de compra</TableCell></TableRow>}
          </TableBody>
        </Table>
      </Card>}

      <Dialog open={showForm} onOpenChange={setShowForm}>
        <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto" data-testid="po-form">
          <DialogHeader><DialogTitle>Nueva orden de compra</DialogTitle></DialogHeader>
          <div className="space-y-3 py-2">
            <div className="grid grid-cols-3 gap-3">
              <div><Label className="text-xs">Sucursal *</Label>
                <Select value={form.branch_id} onValueChange={v=>setForm(f=>({...f,branch_id:v}))}>
                  <SelectTrigger className="mt-1 text-sm"><SelectValue placeholder="Seleccionar" /></SelectTrigger>
                  <SelectContent>{(branches||[]).map(b=><SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div><Label className="text-xs">Proveedor *</Label><Input className="mt-1 text-sm" value={form.supplier_name} onChange={e=>setForm(f=>({...f,supplier_name:e.target.value}))} data-testid="po-supplier" /></div>
              <div><Label className="text-xs">No. orden</Label><Input className="mt-1 text-sm" value={form.order_number} onChange={e=>setForm(f=>({...f,order_number:e.target.value}))} /></div>
            </div>
            <Separator /><p className="text-xs font-bold text-slate-500">Productos</p>
            {form.items.map((item,idx) => (
              <div key={idx} className="p-2 border rounded-lg bg-slate-50/50 space-y-2">
                <div className="flex items-start gap-2">
                  <Badge className="bg-teal-600 text-white mt-1 shrink-0">{idx+1}</Badge>
                  <div className="flex-1 relative">
                    <Input className="text-sm" value={item.product_name} onChange={e=>{updateItem(idx,'product_name',e.target.value);searchProducts(e.target.value,idx);}} placeholder="Buscar producto..." />
                    {productSearch.length>0 && item.product_name.length>=2 && !item.product_id && (
                      <div className="absolute z-50 w-full bg-white border rounded shadow-lg mt-1 max-h-32 overflow-y-auto">
                        {productSearch.map(p=><button key={p.id} type="button" className="w-full px-3 py-1.5 text-left hover:bg-teal-50 text-sm" onMouseDown={()=>selectProduct(p,idx)}>{p.name} ({p.sku})</button>)}
                      </div>
                    )}
                  </div>
                  {form.items.length>1 && <Button variant="ghost" size="sm" className="mt-1" onClick={()=>removeItem(idx)}><Trash2 className="w-3.5 h-3.5 text-red-500" /></Button>}
                </div>
                <div className="grid grid-cols-5 gap-2 ml-8">
                  <div><Label className="text-xs">Cantidad</Label><Input type="number" className="mt-1 text-sm" value={item.quantity} onChange={e=>updateItem(idx,'quantity',parseInt(e.target.value)||0)} /></div>
                  <div><Label className="text-xs">Costo unit.</Label><Input type="number" step="0.01" className="mt-1 text-sm" value={item.unit_cost} onChange={e=>updateItem(idx,'unit_cost',parseFloat(e.target.value)||0)} /></div>
                  <div><Label className="text-xs">Subtotal</Label><p className="mt-1 text-sm font-medium">Q{(item.subtotal||0).toFixed(2)}</p></div>
                  <div><Label className="text-xs">Lote</Label><Input className="mt-1 text-sm" value={item.batch_number} onChange={e=>updateItem(idx,'batch_number',e.target.value)} /></div>
                  <div><Label className="text-xs">Vencimiento</Label><Input type="date" className="mt-1 text-sm" value={item.expiration_date} onChange={e=>updateItem(idx,'expiration_date',e.target.value)} /></div>
                </div>
              </div>
            ))}
            <Button variant="outline" size="sm" onClick={addItem}><Plus className="w-3.5 h-3.5 mr-1" />Agregar producto</Button>
            <Separator />
            <div className="text-right space-y-1">
              <p className="text-sm">Subtotal: <b>Q{subtotal.toFixed(2)}</b></p>
              <p className="text-sm">IVA ({form.tax_rate||12}%): <b>Q{tax.toFixed(2)}</b></p>
              <p className="text-lg font-bold">Total: Q{(subtotal+tax).toFixed(2)}</p>
            </div>
            <div><Label className="text-xs">Notas</Label><Textarea className="mt-1 text-sm min-h-[40px]" value={form.notes} onChange={e=>setForm(f=>({...f,notes:e.target.value}))} /></div>
          </div>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={()=>setShowForm(false)}>Cancelar</Button>
            <Button variant="outline" onClick={()=>handleSave('pending')} disabled={saving}>Guardar pendiente</Button>
            <Button className="bg-teal-600 hover:bg-teal-700" onClick={()=>handleSave('received')} disabled={saving} data-testid="save-receive-btn">Guardar y recibir</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

/* ============ MOVEMENTS TAB ============ */
function MovementsTab({ headers, branches, activeBranch }) {
  const [movements, setMovements] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [typeFilter, setTypeFilter] = useState('all');
  const [branchFilter, setBranchFilter] = useState(activeBranch?.id || 'all');
  const [loading, setLoading] = useState(true);

  // Sync filter with global activeBranch
  useEffect(() => {
    if (activeBranch?.id) setBranchFilter(activeBranch.id);
  }, [activeBranch?.id]);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const params = new URLSearchParams({page:String(page),limit:'20'});
        if (typeFilter!=='all') params.set('movement_type', typeFilter);
        if (branchFilter!=='all') params.set('branch_id', branchFilter);
        const res = await axios.get(`${API}/clinic/inventory/movements?${params}`, {headers});
        setMovements(res.data.movements||[]); setTotal(res.data.total||0); setPages(res.data.pages||1);
      } catch {} finally { setLoading(false); }
    };
    load();
  }, [page, typeFilter, branchFilter, headers]);

  return (
    <>
      <div className="flex gap-3 mb-4">
        <Select value={typeFilter} onValueChange={v=>{setTypeFilter(v);setPage(1);}}>
          <SelectTrigger className="w-36"><SelectValue placeholder="Tipo" /></SelectTrigger>
          <SelectContent><SelectItem value="all">Todos</SelectItem><SelectItem value="purchase">Compras</SelectItem><SelectItem value="sale">Ventas</SelectItem><SelectItem value="adjustment">Ajustes</SelectItem></SelectContent>
        </Select>
        <Select value={branchFilter} onValueChange={v=>{setBranchFilter(v);setPage(1);}}>
          <SelectTrigger className="w-44"><SelectValue placeholder="Sucursal" /></SelectTrigger>
          <SelectContent><SelectItem value="all">Todas</SelectItem>{(branches||[]).map(b=><SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>)}</SelectContent>
        </Select>
      </div>
      {loading ? <div className="flex justify-center py-16"><div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" /></div> :
      <Card className="border overflow-hidden">
        <Table>
          <TableHeader><TableRow className="bg-slate-50/80">
            <TableHead className="text-xs font-semibold">Fecha</TableHead>
            <TableHead className="text-xs font-semibold">Producto</TableHead>
            <TableHead className="text-xs font-semibold">Sucursal</TableHead>
            <TableHead className="text-xs font-semibold text-center">Tipo</TableHead>
            <TableHead className="text-xs font-semibold text-center">Cantidad</TableHead>
            <TableHead className="text-xs font-semibold">Notas</TableHead>
            <TableHead className="text-xs font-semibold">Usuario</TableHead>
          </TableRow></TableHeader>
          <TableBody>
            {movements.map(m=>(
              <TableRow key={m.id}>
                <TableCell className="text-xs">{m.created_at?.substring(0,16).replace('T',' ')}</TableCell>
                <TableCell><p className="text-sm">{m.product_name}</p><p className="text-xs text-slate-400">{m.sku}</p></TableCell>
                <TableCell className="text-sm">{m.branch_name}</TableCell>
                <TableCell className="text-center"><Badge variant="outline" className={`text-xs ${m.movement_type==='purchase'?'bg-blue-50 text-blue-700':m.movement_type==='sale'?'bg-emerald-50 text-emerald-700':'bg-amber-50 text-amber-700'}`}>{MVMT_TYPES[m.movement_type]||m.movement_type}</Badge></TableCell>
                <TableCell className={`text-center text-sm font-bold ${m.quantity>0?'text-emerald-600':'text-red-600'}`}>{m.quantity>0?'+':''}{m.quantity}</TableCell>
                <TableCell className="text-xs text-slate-500 max-w-[150px] truncate">{m.notes||'—'}</TableCell>
                <TableCell className="text-xs text-slate-500">{m.performed_by_name||'—'}</TableCell>
              </TableRow>
            ))}
            {movements.length===0 && <TableRow><TableCell colSpan={7} className="text-center py-8 text-slate-400">Sin movimientos</TableCell></TableRow>}
          </TableBody>
        </Table>
      </Card>}
      {pages>1 && <div className="flex justify-between mt-4"><p className="text-xs text-slate-500">Pág {page}/{pages}</p><div className="flex gap-1"><Button variant="outline" size="sm" disabled={page<=1} onClick={()=>setPage(p=>p-1)}><ChevronLeft className="w-4 h-4" /></Button><Button variant="outline" size="sm" disabled={page>=pages} onClick={()=>setPage(p=>p+1)}><ChevronRight className="w-4 h-4" /></Button></div></div>}
    </>
  );
}

/* ============ SUPPLIERS TAB ============ */
function SuppliersTab({ headers }) {
  const [suppliers, setSuppliers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editSupplier, setEditSupplier] = useState(null);
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);

  const fetch = useCallback(async () => {
    try { const res = await axios.get(`${API}/clinic/inventory/suppliers`, {headers}); setSuppliers(res.data||[]); }
    catch {} finally { setLoading(false); }
  }, [headers]);

  useEffect(() => { fetch(); }, [fetch]);

  const openNew = () => { setEditSupplier(null); setForm({name:'',tax_id:'',contact_person:'',phone:'',email:'',address:'',notes:'',is_active:true}); setShowForm(true); };
  const openEdit = (s) => { setEditSupplier(s); setForm({...s}); setShowForm(true); };

  const handleSave = async () => {
    if (!form.name) { toast.error('Nombre requerido'); return; }
    setSaving(true);
    try {
      if (editSupplier) {
        await axios.put(`${API}/clinic/inventory/suppliers/${editSupplier.id}`, form, {headers});
      } else {
        await axios.post(`${API}/clinic/inventory/suppliers`, form, {headers});
      }
      toast.success(editSupplier?'Proveedor actualizado':'Proveedor creado');
      setShowForm(false); fetch();
    } catch (err) { toast.error(err.response?.data?.detail||'Error'); }
    finally { setSaving(false); }
  };

  const uf = (k,v) => setForm(p=>({...p,[k]:v}));

  return (
    <>
      <div className="flex justify-between mb-4">
        <div />
        <Button className="bg-teal-600 hover:bg-teal-700" onClick={openNew} data-testid="new-supplier-btn"><Plus className="w-4 h-4 mr-1" />Nuevo proveedor</Button>
      </div>
      {loading ? <div className="flex justify-center py-16"><div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" /></div> :
      <Card className="border overflow-hidden">
        <Table>
          <TableHeader><TableRow className="bg-slate-50/80">
            <TableHead className="text-xs font-semibold">Nombre</TableHead>
            <TableHead className="text-xs font-semibold">NIT</TableHead>
            <TableHead className="text-xs font-semibold">Contacto</TableHead>
            <TableHead className="text-xs font-semibold">Teléfono</TableHead>
            <TableHead className="text-xs font-semibold">Email</TableHead>
            <TableHead className="text-xs font-semibold text-center">Estado</TableHead>
            <TableHead className="text-xs font-semibold text-right"></TableHead>
          </TableRow></TableHeader>
          <TableBody>
            {suppliers.map(s=>(
              <TableRow key={s.id}>
                <TableCell className="text-sm font-medium">{s.name}</TableCell>
                <TableCell className="text-sm text-slate-500">{s.tax_id||'—'}</TableCell>
                <TableCell className="text-sm">{s.contact_person||'—'}</TableCell>
                <TableCell className="text-sm">{s.phone||'—'}</TableCell>
                <TableCell className="text-sm text-slate-500">{s.email||'—'}</TableCell>
                <TableCell className="text-center"><Badge variant="outline" className={`text-xs ${s.is_active?'bg-emerald-50 text-emerald-700':'bg-red-50 text-red-600'}`}>{s.is_active?'Activo':'Inactivo'}</Badge></TableCell>
                <TableCell className="text-right"><Button variant="ghost" size="sm" className="h-7 text-xs" onClick={()=>openEdit(s)}>Editar</Button></TableCell>
              </TableRow>
            ))}
            {suppliers.length===0 && <TableRow><TableCell colSpan={7} className="text-center py-8 text-slate-400">Sin proveedores</TableCell></TableRow>}
          </TableBody>
        </Table>
      </Card>}

      <Dialog open={showForm} onOpenChange={setShowForm}>
        <DialogContent className="max-w-md" data-testid="supplier-form">
          <DialogHeader><DialogTitle>{editSupplier?'Editar':'Nuevo'} proveedor</DialogTitle></DialogHeader>
          <div className="space-y-3 py-2">
            <div><Label className="text-xs">Nombre *</Label><Input className="mt-1 text-sm" value={form.name||''} onChange={e=>uf('name',e.target.value)} data-testid="supplier-name" /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label className="text-xs">NIT</Label><Input className="mt-1 text-sm" value={form.tax_id||''} onChange={e=>uf('tax_id',e.target.value)} /></div>
              <div><Label className="text-xs">Contacto</Label><Input className="mt-1 text-sm" value={form.contact_person||''} onChange={e=>uf('contact_person',e.target.value)} /></div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><Label className="text-xs">Teléfono</Label><Input className="mt-1 text-sm" value={form.phone||''} onChange={e=>uf('phone',e.target.value)} /></div>
              <div><Label className="text-xs">Email</Label><Input className="mt-1 text-sm" value={form.email||''} onChange={e=>uf('email',e.target.value)} /></div>
            </div>
            <div><Label className="text-xs">Dirección</Label><Input className="mt-1 text-sm" value={form.address||''} onChange={e=>uf('address',e.target.value)} /></div>
            <div><Label className="text-xs">Notas</Label><Textarea className="mt-1 text-sm min-h-[40px]" value={form.notes||''} onChange={e=>uf('notes',e.target.value)} /></div>
            {editSupplier && <label className="flex items-center gap-2 text-sm"><Switch checked={form.is_active} onCheckedChange={v=>uf('is_active',v)} />Activo</label>}
          </div>
          <DialogFooter><Button variant="outline" onClick={()=>setShowForm(false)}>Cancelar</Button><Button className="bg-teal-600 hover:bg-teal-700" onClick={handleSave} disabled={saving} data-testid="save-supplier-btn">{saving?'...':'Guardar'}</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
