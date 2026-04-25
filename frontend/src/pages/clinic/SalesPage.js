import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../context/AuthContext';
import { useBranch } from '../../context/BranchContext';
import { useFeatures } from '../../context/FeatureContext';
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
  ShoppingCart, Search, Plus, Trash2, X, Calculator, Banknote, CreditCard,
  Wallet, ArrowRight, Lock, Unlock, Calendar, Printer, Eye, Ban, Receipt, Stethoscope
} from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const PAY_LABEL = { cash: 'Efectivo', credit_card: 'Tarjeta crédito', debit_card: 'Tarjeta débito', transfer: 'Transferencia', credit: 'Crédito', check: 'Cheque', other: 'Otro' };
const STATUS_LABEL = { paid: 'Pagada', partial: 'Parcial', pending: 'Pendiente', cancelled: 'Anulada' };

export default function SalesPage() {
  const { getAuthHeaders } = useAuth();
  const { branches, activeBranch } = useBranch();
  const { hasFeature } = useFeatures();
  const headers = getAuthHeaders();
  const [tab, setTab] = useState('pos');

  return (
    <FeatureGate feature="sales" planRequired="Professional">
      <div className="p-6 lg:p-8" data-testid="sales-page">
        <h1 className="text-2xl font-bold text-slate-900 mb-1">Ventas y Caja</h1>
        <p className="text-sm text-slate-500 mb-4">Punto de venta, sesiones de caja y servicios</p>
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="bg-slate-100 mb-4">
            <TabsTrigger value="pos" data-testid="sales-tab-pos"><ShoppingCart className="w-3.5 h-3.5 mr-1" />Punto de venta</TabsTrigger>
            <TabsTrigger value="day" data-testid="sales-tab-day"><Calendar className="w-3.5 h-3.5 mr-1" />Ventas del día</TabsTrigger>
            <TabsTrigger value="services" data-testid="sales-tab-services"><Stethoscope className="w-3.5 h-3.5 mr-1" />Servicios</TabsTrigger>
            <TabsTrigger value="sessions" data-testid="sales-tab-sessions"><Lock className="w-3.5 h-3.5 mr-1" />Sesiones de caja</TabsTrigger>
          </TabsList>
          <TabsContent value="pos"><POSTab headers={headers} branches={branches} activeBranch={activeBranch} hasInventory={hasFeature('inventory')} /></TabsContent>
          <TabsContent value="day"><DailySalesTab headers={headers} branches={branches} /></TabsContent>
          <TabsContent value="services"><ServicesTab headers={headers} /></TabsContent>
          <TabsContent value="sessions"><SessionsTab headers={headers} branches={branches} /></TabsContent>
        </Tabs>
      </div>
    </FeatureGate>
  );
}

/* ============ POS TAB ============ */
function POSTab({ headers, branches, activeBranch, hasInventory }) {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showOpenDlg, setShowOpenDlg] = useState(false);
  const [showCloseDlg, setShowCloseDlg] = useState(false);
  const [registers, setRegisters] = useState([]);
  const [openForm, setOpenForm] = useState({ cash_register_id: '', opening_amount: 0 });
  const [opening, setOpening] = useState(false);

  // Catalog
  const [catalogTab, setCatalogTab] = useState('services');
  const [services, setServices] = useState([]);
  const [products, setProducts] = useState([]);
  const [productSearch, setProductSearch] = useState('');

  // Cart
  const [cart, setCart] = useState([]);
  const [customer, setCustomer] = useState({ name: '', id: '', email: '', address: '', patient_id: null });
  const [patientSearch, setPatientSearch] = useState('');
  const [patientResults, setPatientResults] = useState([]);
  const [discount, setDiscount] = useState(0);
  const [docType, setDocType] = useState('receipt');
  const [showCharge, setShowCharge] = useState(false);
  const [showSuccess, setShowSuccess] = useState(null);

  const loadSession = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/clinic/sales/cash-session/current`, { headers });
      setSession(res.data.session);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [headers]);

  useEffect(() => { loadSession(); }, [loadSession]);

  useEffect(() => {
    if (!session) return;
    (async () => {
      try {
        const [s, p] = await Promise.all([
          axios.get(`${API}/clinic/sales/services?active_only=true`, { headers }),
          hasInventory ? axios.get(`${API}/clinic/inventory/products?limit=50`, { headers }) : Promise.resolve({ data: { products: [] } }),
        ]);
        setServices(s.data || []);
        setProducts(p.data.products || []);
      } catch { /* ignore */ }
    })();
  }, [session, headers, hasInventory]);

  useEffect(() => {
    if (!session || !showOpenDlg) return;
  }, [session, showOpenDlg]);

  const loadRegistersForOpen = async () => {
    try {
      const branchId = activeBranch?.id || '';
      const url = branchId ? `${API}/clinic/sales/cash-registers?branch_id=${branchId}` : `${API}/clinic/sales/cash-registers`;
      const r = await axios.get(url, { headers });
      setRegisters(r.data || []);
      if ((r.data || []).length === 1) setOpenForm(f => ({ ...f, cash_register_id: r.data[0].id }));
    } catch { toast.error('Error al cargar cajas'); }
  };

  const handleOpenClick = () => { loadRegistersForOpen(); setShowOpenDlg(true); };

  const handleOpenSession = async () => {
    if (!openForm.cash_register_id) { toast.error('Seleccione una caja'); return; }
    setOpening(true);
    try {
      await axios.post(`${API}/clinic/sales/cash-session/open`, openForm, { headers });
      toast.success('Caja abierta');
      setShowOpenDlg(false);
      setOpenForm({ cash_register_id: '', opening_amount: 0 });
      loadSession();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error'); }
    finally { setOpening(false); }
  };

  const addToCart = (item, type) => {
    if (type === 'product' && (item.total_stock || 0) <= 0) {
      toast.error('Producto sin stock'); return;
    }
    const id = type === 'product' ? `p-${item.id}` : `s-${item.id}`;
    const existing = cart.find(c => c.id === id);
    if (existing) {
      setCart(c => c.map(x => x.id === id ? { ...x, quantity: x.quantity + 1 } : x));
    } else {
      setCart(c => [...c, {
        id, type,
        product_id: type === 'product' ? item.id : null,
        service_id: type === 'service' ? item.id : null,
        description: item.name,
        quantity: 1,
        unit_price: type === 'product' ? (item.sale_price || 0) : (item.price || 0),
        tax_rate: item.tax_rate ?? 12,
        discount_pct: 0,
        stock: type === 'product' ? item.total_stock : null,
      }]);
    }
  };

  const updateCartItem = (id, field, value) => {
    setCart(c => c.map(x => x.id === id ? { ...x, [field]: value } : x));
  };
  const removeCartItem = (id) => setCart(c => c.filter(x => x.id !== id));

  const searchPatients = async (q) => {
    setPatientSearch(q);
    if (q.length < 2) { setPatientResults([]); return; }
    try {
      const r = await axios.get(`${API}/clinic/patients/search?q=${encodeURIComponent(q)}`, { headers });
      setPatientResults(r.data || []);
    } catch { /* ignore */ }
  };
  const selectPatient = (p) => {
    setCustomer({ name: `${p.first_name} ${p.last_name}`, id: p.national_id || '', email: '', address: '', patient_id: p.id });
    setPatientSearch(`${p.first_name} ${p.last_name}`);
    setPatientResults([]);
  };

  const subtotal = cart.reduce((s, i) => s + i.quantity * i.unit_price * (1 - (i.discount_pct || 0) / 100), 0);
  const subAfterDisc = Math.max(0, subtotal - (discount || 0));
  const taxTotal = cart.reduce((s, i) => {
    const lineSub = i.quantity * i.unit_price * (1 - (i.discount_pct || 0) / 100);
    return s + lineSub * ((i.tax_rate || 0) / 100);
  }, 0);
  const total = +(subAfterDisc + taxTotal).toFixed(2);

  const filteredProducts = products.filter(p => !productSearch || p.name.toLowerCase().includes(productSearch.toLowerCase()) || (p.sku || '').toLowerCase().includes(productSearch.toLowerCase()));

  const resetSale = () => {
    setCart([]); setCustomer({ name: '', id: '', email: '', address: '', patient_id: null });
    setPatientSearch(''); setDiscount(0); setDocType('receipt');
  };

  if (loading) return <div className="flex justify-center py-16"><div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" /></div>;

  // No session: show open-cashier screen
  if (!session) {
    return (
      <>
        <Card className="border-dashed border-2 max-w-md mx-auto">
          <CardContent className="p-10 text-center">
            <Lock className="w-12 h-12 text-slate-300 mx-auto mb-3" />
            <h3 className="text-lg font-semibold text-slate-700 mb-1">No hay sesión de caja abierta</h3>
            <p className="text-sm text-slate-500 mb-5">Para registrar ventas, abra una sesión de caja.</p>
            <Button className="bg-teal-600 hover:bg-teal-700" onClick={handleOpenClick} data-testid="open-cash-session-btn">
              <Unlock className="w-4 h-4 mr-1" />Abrir caja
            </Button>
          </CardContent>
        </Card>
        <Dialog open={showOpenDlg} onOpenChange={setShowOpenDlg}>
          <DialogContent className="max-w-sm" data-testid="open-cash-dialog">
            <DialogHeader><DialogTitle>Abrir caja</DialogTitle></DialogHeader>
            <div className="space-y-3 py-2">
              <div>
                <Label className="text-xs">Caja</Label>
                <Select value={openForm.cash_register_id} onValueChange={v => setOpenForm(f => ({ ...f, cash_register_id: v }))}>
                  <SelectTrigger className="mt-1 text-sm" data-testid="cash-register-select"><SelectValue placeholder="Seleccionar" /></SelectTrigger>
                  <SelectContent>
                    {registers.map(r => <SelectItem key={r.id} value={r.id}>{r.name} — {r.branch_name}</SelectItem>)}
                    {registers.length === 0 && <div className="px-3 py-2 text-xs text-slate-400">No hay cajas. Cree una en Configuración.</div>}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs">Monto de apertura (Q)</Label>
                <Input type="number" step="0.01" className="mt-1 text-sm" value={openForm.opening_amount} onChange={e => setOpenForm(f => ({ ...f, opening_amount: parseFloat(e.target.value) || 0 }))} data-testid="opening-amount-input" />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowOpenDlg(false)}>Cancelar</Button>
              <Button className="bg-teal-600 hover:bg-teal-700" onClick={handleOpenSession} disabled={opening} data-testid="confirm-open-btn">
                {opening ? '...' : 'Abrir caja'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </>
    );
  }

  // Active session: show POS
  return (
    <>
      <div className="flex items-center justify-between bg-emerald-50 border border-emerald-200 rounded-lg px-4 py-2 mb-4">
        <div className="flex items-center gap-2 text-sm">
          <Unlock className="w-4 h-4 text-emerald-600" />
          <span className="font-medium text-emerald-800">Caja abierta:</span>
          <span className="text-emerald-700">{session.cash_register_name} — {session.branch_name}</span>
          <span className="text-emerald-600 text-xs">| Apertura: Q{(session.opening_amount || 0).toFixed(2)}</span>
        </div>
        <Button variant="outline" size="sm" onClick={() => setShowCloseDlg(true)} data-testid="close-cash-session-btn">
          <Lock className="w-3.5 h-3.5 mr-1" />Cerrar caja
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        {/* Catalog */}
        <div className="lg:col-span-3">
          <Card>
            <CardHeader className="pb-2">
              <Tabs value={catalogTab} onValueChange={setCatalogTab}>
                <TabsList className="bg-slate-100">
                  <TabsTrigger value="services" data-testid="cat-tab-services">Servicios</TabsTrigger>
                  <TabsTrigger value="products" data-testid="cat-tab-products">Productos</TabsTrigger>
                </TabsList>
              </Tabs>
            </CardHeader>
            <CardContent>
              {catalogTab === 'services' ? (
                <div className="grid grid-cols-2 md:grid-cols-3 gap-2 max-h-[500px] overflow-y-auto">
                  {services.map(s => (
                    <button key={s.id} type="button" onClick={() => addToCart(s, 'service')} className="text-left p-3 border border-slate-200 rounded-lg hover:border-teal-400 hover:bg-teal-50 transition" data-testid={`service-card-${s.id}`}>
                      <p className="text-sm font-medium text-slate-800 truncate">{s.name}</p>
                      <p className="text-xs text-slate-500">{s.category || '—'}</p>
                      <p className="text-base font-bold text-teal-600 mt-1">Q{(s.price || 0).toFixed(2)}</p>
                    </button>
                  ))}
                  {services.length === 0 && <div className="col-span-full text-center py-8 text-sm text-slate-400">No hay servicios. Cree uno en la pestaña "Servicios".</div>}
                </div>
              ) : (
                <>
                  <div className="relative mb-2">
                    <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                    <Input className="pl-9 text-sm" placeholder="Buscar producto..." value={productSearch} onChange={e => setProductSearch(e.target.value)} data-testid="pos-product-search" />
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-2 max-h-[450px] overflow-y-auto">
                    {filteredProducts.map(p => (
                      <button key={p.id} type="button" onClick={() => addToCart(p, 'product')} disabled={p.total_stock <= 0} className={`text-left p-3 border rounded-lg transition ${p.total_stock <= 0 ? 'opacity-50 cursor-not-allowed border-slate-200' : 'border-slate-200 hover:border-teal-400 hover:bg-teal-50'}`}>
                        <p className="text-sm font-medium text-slate-800 truncate">{p.name}</p>
                        <p className="text-xs text-slate-500">Stock: <span className={p.total_stock <= 0 ? 'text-red-600' : ''}>{p.total_stock}</span></p>
                        <p className="text-base font-bold text-teal-600 mt-1">Q{(p.sale_price || 0).toFixed(2)}</p>
                      </button>
                    ))}
                    {filteredProducts.length === 0 && <div className="col-span-full text-center py-8 text-sm text-slate-400">{hasInventory ? 'Sin productos' : 'Active el módulo Inventario'}</div>}
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Cart */}
        <div className="lg:col-span-2">
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm font-semibold">Carrito y cobro</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {/* Customer */}
              <div className="space-y-2 pb-3 border-b">
                <Label className="text-xs">Cliente / Paciente</Label>
                <div className="relative">
                  <Input className="text-sm" placeholder="Buscar paciente..." value={patientSearch} onChange={e => searchPatients(e.target.value)} data-testid="pos-patient-search" />
                  {patientResults.length > 0 && (
                    <div className="absolute z-50 w-full bg-white border rounded shadow-lg mt-1 max-h-32 overflow-y-auto">
                      {patientResults.map(p => (
                        <button key={p.id} type="button" className="w-full px-3 py-1.5 text-left hover:bg-teal-50 text-sm" onMouseDown={() => selectPatient(p)}>
                          {p.first_name} {p.last_name} {p.national_id ? `— ${p.national_id}` : ''}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <Input className="text-xs" placeholder="Nombre" value={customer.name} onChange={e => setCustomer(c => ({ ...c, name: e.target.value }))} data-testid="customer-name-input" />
                  <Input className="text-xs" placeholder="NIT/DPI" value={customer.id} onChange={e => setCustomer(c => ({ ...c, id: e.target.value }))} data-testid="customer-id-input" />
                </div>
              </div>

              {/* Cart items */}
              <div className="max-h-[260px] overflow-y-auto space-y-2">
                {cart.length === 0 && <p className="text-xs text-slate-400 text-center py-6">Agregue items del catálogo</p>}
                {cart.map(item => {
                  const lineSub = item.quantity * item.unit_price * (1 - (item.discount_pct || 0) / 100);
                  return (
                    <div key={item.id} className="flex items-start gap-2 p-2 border rounded bg-slate-50/40">
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-medium truncate">{item.description}</p>
                        {item.stock != null && <p className="text-[10px] text-slate-400">Stock: {item.stock}</p>}
                        <div className="flex items-center gap-1 mt-1">
                          <Input type="number" className="h-7 text-xs w-16" value={item.quantity} min={1} onChange={e => updateCartItem(item.id, 'quantity', parseFloat(e.target.value) || 1)} data-testid={`cart-qty-${item.id}`} />
                          <span className="text-xs text-slate-400">×</span>
                          <Input type="number" step="0.01" className="h-7 text-xs w-20" value={item.unit_price} onChange={e => updateCartItem(item.id, 'unit_price', parseFloat(e.target.value) || 0)} />
                          <span className="ml-auto text-xs font-bold">Q{lineSub.toFixed(2)}</span>
                        </div>
                      </div>
                      <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => removeCartItem(item.id)} data-testid={`cart-remove-${item.id}`}>
                        <X className="w-3.5 h-3.5 text-red-500" />
                      </Button>
                    </div>
                  );
                })}
              </div>

              <Separator />
              {/* Totals */}
              <div className="space-y-1 text-xs">
                <div className="flex justify-between"><span className="text-slate-500">Subtotal</span><span>Q{subtotal.toFixed(2)}</span></div>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-slate-500">Descuento</span>
                  <Input type="number" step="0.01" className="h-7 text-xs w-24 text-right" value={discount} onChange={e => setDiscount(parseFloat(e.target.value) || 0)} data-testid="discount-input" />
                </div>
                <div className="flex justify-between"><span className="text-slate-500">IVA</span><span>Q{taxTotal.toFixed(2)}</span></div>
                <div className="flex justify-between items-center pt-2 border-t">
                  <span className="text-sm font-bold">TOTAL</span>
                  <span className="text-2xl font-bold text-teal-600" data-testid="cart-total">Q{total.toFixed(2)}</span>
                </div>
              </div>

              <div className="flex gap-2">
                <Select value={docType} onValueChange={setDocType}>
                  <SelectTrigger className="text-xs h-9 flex-1"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="receipt">Recibo</SelectItem>
                    <SelectItem value="invoice">Factura</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <Button className="w-full bg-teal-600 hover:bg-teal-700 h-12 text-base" onClick={() => {
                if (cart.length === 0) { toast.error('Carrito vacío'); return; }
                if (docType === 'invoice' && !customer.id) { toast.error('NIT del cliente requerido para factura'); return; }
                setShowCharge(true);
              }} data-testid="charge-btn">
                <Calculator className="w-5 h-5 mr-2" />COBRAR Q{total.toFixed(2)}
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Charge Modal */}
      <ChargeModal open={showCharge} onClose={() => setShowCharge(false)} total={total} onConfirm={async (payments) => {
        try {
          const payload = {
            branch_id: session.branch_id || activeBranch?.id,
            cash_session_id: session.id,
            patient_id: customer.patient_id,
            customer_name: customer.name,
            customer_id: customer.id,
            customer_email: customer.email,
            customer_address: customer.address,
            document_type: docType,
            discount_amount: discount,
            items: cart.map(c => ({
              product_id: c.product_id, service_id: c.service_id,
              description: c.description, quantity: c.quantity,
              unit_price: c.unit_price, discount_pct: c.discount_pct || 0,
              tax_rate: c.tax_rate || 0,
            })),
            payments,
          };
          const r = await axios.post(`${API}/clinic/sales`, payload, { headers });
          toast.success(`Venta ${r.data.sale_number} registrada`);
          setShowCharge(false);
          setShowSuccess(r.data);
          resetSale();
        } catch (err) { toast.error(err.response?.data?.detail || 'Error al registrar venta'); }
      }} />

      {/* Success Modal */}
      <Dialog open={!!showSuccess} onOpenChange={() => setShowSuccess(null)}>
        <DialogContent className="max-w-sm" data-testid="sale-success-dialog">
          <DialogHeader><DialogTitle className="text-emerald-600">¡Venta registrada!</DialogTitle></DialogHeader>
          <div className="text-center py-2">
            <p className="text-sm text-slate-500 mb-1">No.</p>
            <p className="text-xl font-bold">{showSuccess?.sale_number}</p>
            <p className="text-3xl font-bold text-teal-600 mt-2">Q{(showSuccess?.total || 0).toFixed(2)}</p>
            <Badge variant="outline" className="mt-2">{STATUS_LABEL[showSuccess?.payment_status]}</Badge>
          </div>
          <DialogFooter className="flex-col sm:flex-col gap-2">
            <Button variant="outline" className="w-full" onClick={async () => {
              try {
                const r = await axios.get(`${API}/clinic/sales/${showSuccess.id}/pdf-url`, { headers });
                if (r.data.url) window.open(r.data.url, '_blank');
                else toast.error('PDF no disponible');
              } catch { toast.error('Error al obtener PDF'); }
            }} data-testid="print-receipt-btn"><Printer className="w-4 h-4 mr-1" />Imprimir comprobante</Button>
            <Button className="w-full bg-teal-600 hover:bg-teal-700" onClick={() => setShowSuccess(null)} data-testid="new-sale-btn">Nueva venta</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Close Session Modal */}
      <CloseSessionDialog open={showCloseDlg} onClose={() => setShowCloseDlg(false)} session={session} headers={headers} onClosed={() => { setShowCloseDlg(false); loadSession(); }} />
    </>
  );
}

/* ============ CHARGE MODAL ============ */
function ChargeModal({ open, onClose, total, onConfirm }) {
  const [payments, setPayments] = useState([{ payment_method: 'cash', amount: 0, reference: '' }]);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => { if (open) setPayments([{ payment_method: 'cash', amount: total, reference: '' }]); }, [open, total]);

  const addPay = () => setPayments(p => [...p, { payment_method: 'credit_card', amount: 0, reference: '' }]);
  const removePay = (i) => setPayments(p => p.filter((_, idx) => idx !== i));
  const updPay = (i, field, value) => setPayments(p => p.map((x, idx) => idx === i ? { ...x, [field]: value } : x));

  const totalPaid = payments.reduce((s, p) => s + (parseFloat(p.amount) || 0), 0);
  const cashGiven = payments.filter(p => p.payment_method === 'cash').reduce((s, p) => s + (parseFloat(p.amount) || 0), 0);
  const change = cashGiven > 0 && totalPaid > total ? totalPaid - total : 0;
  const due = Math.max(0, total - totalPaid);

  const handleConfirm = async () => {
    if (totalPaid <= 0) { toast.error('Ingrese al menos un pago'); return; }
    // Truncate any over-payment from cash to exact total (so amount_paid <= total)
    const adjusted = payments.filter(p => (parseFloat(p.amount) || 0) > 0).map(p => {
      let amt = parseFloat(p.amount) || 0;
      if (p.payment_method === 'cash' && totalPaid > total) {
        // reduce by change to record only effective collected = total
        amt = Math.max(0, amt - change);
      }
      return { ...p, amount: amt };
    }).filter(p => p.amount > 0);
    setSubmitting(true);
    try { await onConfirm(adjusted); }
    finally { setSubmitting(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-md" data-testid="charge-dialog">
        <DialogHeader><DialogTitle>Cobrar</DialogTitle></DialogHeader>
        <div className="space-y-3 py-2">
          <div className="text-center bg-teal-50 border border-teal-200 rounded-lg py-3">
            <p className="text-xs text-teal-700">Total a pagar</p>
            <p className="text-3xl font-bold text-teal-600">Q{total.toFixed(2)}</p>
          </div>
          {payments.map((p, i) => (
            <div key={i} className="flex items-end gap-2 p-2 border rounded">
              <div className="flex-1">
                <Label className="text-xs">Método</Label>
                <Select value={p.payment_method} onValueChange={v => updPay(i, 'payment_method', v)}>
                  <SelectTrigger className="mt-1 text-sm h-8" data-testid={`pay-method-${i}`}><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="cash"><Banknote className="w-3 h-3 inline mr-1" />Efectivo</SelectItem>
                    <SelectItem value="credit_card"><CreditCard className="w-3 h-3 inline mr-1" />Tarjeta crédito</SelectItem>
                    <SelectItem value="debit_card"><CreditCard className="w-3 h-3 inline mr-1" />Tarjeta débito</SelectItem>
                    <SelectItem value="transfer"><ArrowRight className="w-3 h-3 inline mr-1" />Transferencia</SelectItem>
                    <SelectItem value="credit"><Wallet className="w-3 h-3 inline mr-1" />Crédito</SelectItem>
                    <SelectItem value="check">Cheque</SelectItem>
                    <SelectItem value="other">Otro</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="w-24">
                <Label className="text-xs">Monto</Label>
                <Input type="number" step="0.01" className="mt-1 text-sm h-8" value={p.amount} onChange={e => updPay(i, 'amount', e.target.value)} data-testid={`pay-amount-${i}`} />
              </div>
              {(p.payment_method === 'credit_card' || p.payment_method === 'debit_card' || p.payment_method === 'transfer' || p.payment_method === 'check') && (
                <div className="w-24">
                  <Label className="text-xs">Ref.</Label>
                  <Input className="mt-1 text-sm h-8" value={p.reference || ''} onChange={e => updPay(i, 'reference', e.target.value)} placeholder="Auth" />
                </div>
              )}
              {payments.length > 1 && <Button variant="ghost" size="sm" className="h-8 w-8 p-0" onClick={() => removePay(i)}><X className="w-3.5 h-3.5 text-red-500" /></Button>}
            </div>
          ))}
          <Button variant="outline" size="sm" onClick={addPay}><Plus className="w-3.5 h-3.5 mr-1" />Agregar método</Button>
          <div className="bg-slate-50 rounded p-2 text-xs space-y-1">
            <div className="flex justify-between"><span>Pagado:</span><span className="font-bold">Q{totalPaid.toFixed(2)}</span></div>
            {change > 0 && <div className="flex justify-between text-emerald-700"><span>Cambio:</span><span className="font-bold">Q{change.toFixed(2)}</span></div>}
            {due > 0 && <div className="flex justify-between text-amber-700"><span>Saldo pendiente:</span><span className="font-bold">Q{due.toFixed(2)}</span></div>}
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancelar</Button>
          <Button className="bg-teal-600 hover:bg-teal-700" onClick={handleConfirm} disabled={submitting} data-testid="confirm-payment-btn">{submitting ? '...' : 'Confirmar pago'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/* ============ CLOSE SESSION MODAL ============ */
function CloseSessionDialog({ open, onClose, session, headers, onClosed }) {
  const [summary, setSummary] = useState(null);
  const [actual, setActual] = useState(0);
  const [closing, setClosing] = useState(false);

  useEffect(() => {
    if (!open || !session) return;
    (async () => {
      try {
        const r = await axios.get(`${API}/clinic/sales/cash-session/${session.id}/summary`, { headers });
        setSummary(r.data);
        setActual(r.data.expected || 0);
      } catch { /* ignore */ }
    })();
  }, [open, session, headers]);

  const handleClose = async () => {
    setClosing(true);
    try {
      await axios.post(`${API}/clinic/sales/cash-session/${session.id}/close`, { actual_amount: actual }, { headers });
      toast.success('Caja cerrada');
      onClosed();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error'); }
    finally { setClosing(false); }
  };

  if (!summary) return null;
  const diff = (parseFloat(actual) || 0) - (summary.expected || 0);

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-sm" data-testid="close-cash-dialog">
        <DialogHeader><DialogTitle>Cerrar caja</DialogTitle></DialogHeader>
        <div className="space-y-2 py-2 text-sm">
          <div className="flex justify-between"><span className="text-slate-500">Apertura:</span><span className="font-medium">Q{(summary.opening || 0).toFixed(2)}</span></div>
          <div className="flex justify-between"><span className="text-slate-500">Ventas en efectivo:</span><span className="font-medium">Q{(summary.totals?.cash || 0).toFixed(2)}</span></div>
          <div className="flex justify-between"><span className="text-slate-500">Ventas en tarjeta:</span><span className="font-medium">Q{((summary.totals?.credit_card || 0) + (summary.totals?.debit_card || 0)).toFixed(2)}</span></div>
          <div className="flex justify-between"><span className="text-slate-500">Transferencias:</span><span className="font-medium">Q{(summary.totals?.transfer || 0).toFixed(2)}</span></div>
          <Separator />
          <div className="flex justify-between text-base"><span className="font-bold">Total esperado en caja:</span><span className="font-bold text-teal-600">Q{(summary.expected || 0).toFixed(2)}</span></div>
          <div>
            <Label className="text-xs">Monto físico contado</Label>
            <Input type="number" step="0.01" className="mt-1" value={actual} onChange={e => setActual(parseFloat(e.target.value) || 0)} data-testid="actual-amount-input" />
          </div>
          <div className={`flex justify-between p-2 rounded ${Math.abs(diff) < 0.01 ? 'bg-emerald-50 text-emerald-700' : diff > 0 ? 'bg-blue-50 text-blue-700' : 'bg-red-50 text-red-700'}`}>
            <span className="font-bold">{diff > 0 ? 'Sobrante' : diff < 0 ? 'Faltante' : 'Cuadrado'}:</span>
            <span className="font-bold">Q{Math.abs(diff).toFixed(2)}</span>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Cancelar</Button>
          <Button className="bg-teal-600 hover:bg-teal-700" onClick={handleClose} disabled={closing} data-testid="confirm-close-btn">{closing ? '...' : 'Confirmar cierre'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/* ============ DAILY SALES TAB ============ */
function DailySalesTab({ headers, branches }) {
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [summary, setSummary] = useState(null);
  const [sales, setSales] = useState([]);
  const [branchFilter, setBranchFilter] = useState('all');
  const [methodFilter, setMethodFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ date, date_from: date, date_to: date });
      if (branchFilter !== 'all') params.set('branch_id', branchFilter);
      if (methodFilter !== 'all') params.set('payment_method', methodFilter);
      const [s, l] = await Promise.all([
        axios.get(`${API}/clinic/sales/daily-summary?${branchFilter !== 'all' ? `branch_id=${branchFilter}&` : ''}date=${date}`, { headers }),
        axios.get(`${API}/clinic/sales?${params}&limit=50`, { headers }),
      ]);
      setSummary(s.data); setSales(l.data.sales || []);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [date, branchFilter, methodFilter, headers]);

  useEffect(() => { load(); }, [load]);

  const openDetail = async (id) => {
    try {
      const r = await axios.get(`${API}/clinic/sales/${id}`, { headers });
      setDetail(r.data);
    } catch { toast.error('Error'); }
  };

  const handleCancel = async (id) => {
    const reason = prompt('Motivo de la anulación:');
    if (!reason) return;
    try { await axios.post(`${API}/clinic/sales/${id}/cancel`, { reason }, { headers }); toast.success('Venta anulada'); load(); setDetail(null); }
    catch (err) { toast.error(err.response?.data?.detail || 'Error'); }
  };

  const printReceipt = async (id) => {
    try {
      const r = await axios.get(`${API}/clinic/sales/${id}/pdf-url`, { headers });
      if (r.data.url) window.open(r.data.url, '_blank');
      else toast.error('PDF no disponible');
    } catch { toast.error('Error al obtener PDF'); }
  };

  return (
    <>
      <div className="flex flex-wrap gap-3 mb-4">
        <Input type="date" className="w-44" value={date} onChange={e => setDate(e.target.value)} data-testid="date-filter" />
        <Select value={branchFilter} onValueChange={setBranchFilter}>
          <SelectTrigger className="w-44"><SelectValue placeholder="Sucursal" /></SelectTrigger>
          <SelectContent><SelectItem value="all">Todas</SelectItem>{(branches || []).map(b => <SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>)}</SelectContent>
        </Select>
        <Select value={methodFilter} onValueChange={setMethodFilter}>
          <SelectTrigger className="w-44"><SelectValue placeholder="Método de pago" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todos</SelectItem>
            <SelectItem value="cash">Efectivo</SelectItem>
            <SelectItem value="credit_card">Tarjeta crédito</SelectItem>
            <SelectItem value="debit_card">Tarjeta débito</SelectItem>
            <SelectItem value="transfer">Transferencia</SelectItem>
            <SelectItem value="credit">Crédito</SelectItem>
            <SelectItem value="check">Cheque</SelectItem>
            <SelectItem value="other">Otro</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <SummaryCard label="Total ventas" value={summary?.total} count={summary?.count} color="teal" />
        <SummaryCard label="Efectivo" value={summary?.cash} color="emerald" icon={Banknote} />
        <SummaryCard label="Tarjeta" value={summary?.card} color="blue" icon={CreditCard} />
        <SummaryCard label="Pendiente cobro" value={summary?.pending_due} color="amber" icon={Wallet} />
      </div>

      {loading ? <div className="flex justify-center py-16"><div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" /></div> :
        <Card className="border overflow-hidden">
          <Table>
            <TableHeader><TableRow className="bg-slate-50/80">
              <TableHead className="text-xs font-semibold">Hora</TableHead>
              <TableHead className="text-xs font-semibold">No.</TableHead>
              <TableHead className="text-xs font-semibold">Cliente</TableHead>
              <TableHead className="text-xs font-semibold">Items</TableHead>
              <TableHead className="text-xs font-semibold text-right">Total</TableHead>
              <TableHead className="text-xs font-semibold text-center">Pago</TableHead>
              <TableHead className="text-xs font-semibold text-center">Estado</TableHead>
              <TableHead className="text-xs font-semibold">Cajero</TableHead>
              <TableHead className="text-xs font-semibold text-right"></TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {sales.map(s => (
                <TableRow key={s.id} data-testid={`sale-row-${s.id}`}>
                  <TableCell className="text-xs">{s.created_at?.substring(11, 16)}</TableCell>
                  <TableCell className="text-xs font-mono">{s.sale_number}</TableCell>
                  <TableCell className="text-sm">{s.customer_name || '—'}</TableCell>
                  <TableCell className="text-xs text-slate-500 max-w-[180px] truncate">{s.items_summary}</TableCell>
                  <TableCell className="text-right text-sm font-bold">Q{(s.total || 0).toFixed(2)}</TableCell>
                  <TableCell className="text-center text-xs">{(s.payment_methods || []).map(m => PAY_LABEL[m] || m).join(', ') || '—'}</TableCell>
                  <TableCell className="text-center"><Badge variant="outline" className={`text-xs ${s.status === 'cancelled' ? 'bg-red-50 text-red-700' : s.payment_status === 'paid' ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>{s.status === 'cancelled' ? 'Anulada' : STATUS_LABEL[s.payment_status] || s.payment_status}</Badge></TableCell>
                  <TableCell className="text-xs text-slate-500">{s.cashier_name}</TableCell>
                  <TableCell className="text-right">
                    <Button variant="ghost" size="sm" className="h-7 w-7 p-0" onClick={() => openDetail(s.id)} data-testid={`view-sale-${s.id}`}><Eye className="w-3.5 h-3.5" /></Button>
                  </TableCell>
                </TableRow>
              ))}
              {sales.length === 0 && <TableRow><TableCell colSpan={9} className="text-center py-8 text-slate-400">Sin ventas en esta fecha</TableCell></TableRow>}
            </TableBody>
          </Table>
        </Card>}

      <Dialog open={!!detail} onOpenChange={() => setDetail(null)}>
        <DialogContent className="max-w-lg" data-testid="sale-detail-dialog">
          <DialogHeader><DialogTitle>Venta {detail?.sale_number}</DialogTitle></DialogHeader>
          {detail && (
            <div className="space-y-3 text-sm">
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div><span className="text-slate-500">Cliente:</span> <span className="font-medium">{detail.customer_name || '—'}</span></div>
                <div><span className="text-slate-500">NIT/DPI:</span> <span className="font-medium">{detail.customer_id || '—'}</span></div>
                <div><span className="text-slate-500">Cajero:</span> <span className="font-medium">{detail.cashier_name}</span></div>
                <div><span className="text-slate-500">Estado:</span> <Badge variant="outline" className="text-xs">{detail.status === 'cancelled' ? 'Anulada' : STATUS_LABEL[detail.payment_status]}</Badge></div>
              </div>
              <Separator />
              <p className="text-xs font-bold text-slate-500">Items</p>
              {(detail.items || []).map(it => (
                <div key={it.id} className="flex justify-between text-xs">
                  <span>{it.quantity} × {it.description}</span>
                  <span className="font-medium">Q{(it.total || 0).toFixed(2)}</span>
                </div>
              ))}
              <Separator />
              <div className="text-right text-sm">
                <p>Subtotal: <b>Q{(detail.subtotal || 0).toFixed(2)}</b></p>
                {(detail.discount_amount || 0) > 0 && <p>Descuento: <b>-Q{(detail.discount_amount).toFixed(2)}</b></p>}
                <p>IVA: <b>Q{(detail.tax_amount || 0).toFixed(2)}</b></p>
                <p className="text-lg font-bold text-teal-600">TOTAL: Q{(detail.total || 0).toFixed(2)}</p>
              </div>
              <Separator />
              <p className="text-xs font-bold text-slate-500">Pagos</p>
              {(detail.payments || []).map(p => (
                <div key={p.id} className="flex justify-between text-xs">
                  <span>{PAY_LABEL[p.payment_method] || p.payment_method} {p.reference ? `— ${p.reference}` : ''}</span>
                  <span className="font-medium">Q{(p.amount || 0).toFixed(2)}</span>
                </div>
              ))}
              {detail.cancellation_reason && <p className="text-xs text-red-600">Motivo anulación: {detail.cancellation_reason}</p>}
            </div>
          )}
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => printReceipt(detail.id)}><Printer className="w-3.5 h-3.5 mr-1" />Imprimir</Button>
            {detail?.status !== 'cancelled' && <Button variant="outline" className="text-red-600" onClick={() => handleCancel(detail.id)} data-testid="cancel-sale-btn"><Ban className="w-3.5 h-3.5 mr-1" />Anular</Button>}
            <Button onClick={() => setDetail(null)}>Cerrar</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function SummaryCard({ label, value, count, color = 'slate', icon: Icon }) {
  const colorMap = { teal: 'text-teal-600', emerald: 'text-emerald-600', blue: 'text-blue-600', amber: 'text-amber-600', slate: 'text-slate-600' };
  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
          <p className="text-xs text-slate-500 font-medium">{label}</p>
          {Icon && <Icon className={`w-4 h-4 ${colorMap[color]}`} />}
        </div>
        <p className={`text-2xl font-bold mt-1 ${colorMap[color]}`}>Q{(value || 0).toFixed(2)}</p>
        {count != null && <p className="text-xs text-slate-400">{count} ventas</p>}
      </CardContent>
    </Card>
  );
}

/* ============ SERVICES TAB ============ */
function ServicesTab({ headers }) {
  const [items, setItems] = useState([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [edit, setEdit] = useState(null);
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/clinic/sales/services?q=${encodeURIComponent(search)}`, { headers });
      setItems(r.data || []);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [search, headers]);

  useEffect(() => { load(); }, [load]);

  const openNew = () => { setEdit(null); setForm({ code: '', name: '', description: '', category: '', price: 0, tax_rate: 12, duration_minutes: 30, is_active: true }); setShowForm(true); };
  const openEdit = (s) => { setEdit(s); setForm({ ...s }); setShowForm(true); };

  const handleSave = async () => {
    if (!form.name) { toast.error('Nombre requerido'); return; }
    setSaving(true);
    try {
      if (edit) await axios.put(`${API}/clinic/sales/services/${edit.id}`, form, { headers });
      else await axios.post(`${API}/clinic/sales/services`, form, { headers });
      toast.success(edit ? 'Servicio actualizado' : 'Servicio creado');
      setShowForm(false); load();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error'); }
    finally { setSaving(false); }
  };

  const uf = (k, v) => setForm(p => ({ ...p, [k]: v }));

  return (
    <>
      <div className="flex gap-3 mb-4">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <Input className="pl-9 text-sm" placeholder="Buscar servicio..." value={search} onChange={e => setSearch(e.target.value)} data-testid="service-search" />
        </div>
        <Button className="bg-teal-600 hover:bg-teal-700" onClick={openNew} data-testid="new-service-btn"><Plus className="w-4 h-4 mr-1" />Nuevo servicio</Button>
      </div>

      {loading ? <div className="flex justify-center py-16"><div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" /></div> :
        <Card className="border overflow-hidden">
          <Table>
            <TableHeader><TableRow className="bg-slate-50/80">
              <TableHead className="text-xs font-semibold">Código</TableHead>
              <TableHead className="text-xs font-semibold">Nombre</TableHead>
              <TableHead className="text-xs font-semibold">Categoría</TableHead>
              <TableHead className="text-xs font-semibold text-right">Precio</TableHead>
              <TableHead className="text-xs font-semibold text-center">Duración</TableHead>
              <TableHead className="text-xs font-semibold text-center">Estado</TableHead>
              <TableHead className="text-xs font-semibold text-right"></TableHead>
            </TableRow></TableHeader>
            <TableBody>
              {items.map(s => (
                <TableRow key={s.id} data-testid={`service-row-${s.id}`}>
                  <TableCell className="text-xs font-mono text-slate-500">{s.code || '—'}</TableCell>
                  <TableCell><p className="text-sm font-medium">{s.name}</p>{s.description && <p className="text-xs text-slate-400 truncate max-w-[280px]">{s.description}</p>}</TableCell>
                  <TableCell className="text-xs text-slate-500">{s.category || '—'}</TableCell>
                  <TableCell className="text-right text-sm font-medium">Q{(s.price || 0).toFixed(2)}</TableCell>
                  <TableCell className="text-center text-xs">{s.duration_minutes ? `${s.duration_minutes} min` : '—'}</TableCell>
                  <TableCell className="text-center"><Badge variant="outline" className={`text-xs ${s.is_active ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-600'}`}>{s.is_active ? 'Activo' : 'Inactivo'}</Badge></TableCell>
                  <TableCell className="text-right"><Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => openEdit(s)}>Editar</Button></TableCell>
                </TableRow>
              ))}
              {items.length === 0 && <TableRow><TableCell colSpan={7} className="text-center py-8 text-slate-400"><Receipt className="w-10 h-10 mx-auto mb-2 text-slate-300" />Sin servicios</TableCell></TableRow>}
            </TableBody>
          </Table>
        </Card>}

      <Dialog open={showForm} onOpenChange={setShowForm}>
        <DialogContent className="max-w-md" data-testid="service-form-dialog">
          <DialogHeader><DialogTitle>{edit ? 'Editar' : 'Nuevo'} servicio</DialogTitle></DialogHeader>
          <div className="space-y-3 py-2">
            <div className="grid grid-cols-2 gap-3">
              <div><Label className="text-xs">Código</Label><Input className="mt-1 text-sm" value={form.code || ''} onChange={e => uf('code', e.target.value)} /></div>
              <div><Label className="text-xs">Categoría</Label><Input className="mt-1 text-sm" value={form.category || ''} onChange={e => uf('category', e.target.value)} placeholder="Consultas" /></div>
            </div>
            <div><Label className="text-xs">Nombre *</Label><Input className="mt-1 text-sm" value={form.name || ''} onChange={e => uf('name', e.target.value)} data-testid="service-name-input" /></div>
            <div><Label className="text-xs">Descripción</Label><Textarea className="mt-1 text-sm min-h-[50px]" value={form.description || ''} onChange={e => uf('description', e.target.value)} /></div>
            <div className="grid grid-cols-3 gap-3">
              <div><Label className="text-xs">Precio (Q)</Label><Input type="number" step="0.01" className="mt-1 text-sm" value={form.price ?? ''} onChange={e => uf('price', parseFloat(e.target.value) || 0)} data-testid="service-price-input" /></div>
              <div><Label className="text-xs">IVA (%)</Label><Input type="number" className="mt-1 text-sm" value={form.tax_rate ?? 12} onChange={e => uf('tax_rate', parseFloat(e.target.value) || 0)} /></div>
              <div><Label className="text-xs">Duración (min)</Label><Input type="number" className="mt-1 text-sm" value={form.duration_minutes ?? ''} onChange={e => uf('duration_minutes', parseInt(e.target.value) || null)} /></div>
            </div>
            <label className="flex items-center gap-2 text-sm"><Switch checked={form.is_active} onCheckedChange={v => uf('is_active', v)} />Activo</label>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowForm(false)}>Cancelar</Button>
            <Button className="bg-teal-600 hover:bg-teal-700" onClick={handleSave} disabled={saving} data-testid="save-service-btn">{saving ? '...' : 'Guardar'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

/* ============ SESSIONS TAB ============ */
function SessionsTab({ headers, branches }) {
  const [sessions, setSessions] = useState([]);
  const [registers, setRegisters] = useState([]);
  const [showCRForm, setShowCRForm] = useState(false);
  const [crForm, setCrForm] = useState({ name: '', branch_id: '' });
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [s, r] = await Promise.all([
        axios.get(`${API}/clinic/sales/cash-sessions?limit=30`, { headers }),
        axios.get(`${API}/clinic/sales/cash-registers`, { headers }),
      ]);
      setSessions(s.data.sessions || []);
      setRegisters(r.data || []);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [headers]);

  useEffect(() => { load(); }, [load]);

  const handleCreateCR = async () => {
    if (!crForm.name || !crForm.branch_id) { toast.error('Nombre y sucursal'); return; }
    try {
      await axios.post(`${API}/clinic/sales/cash-registers`, crForm, { headers });
      toast.success('Caja creada');
      setShowCRForm(false); setCrForm({ name: '', branch_id: '' }); load();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error'); }
  };

  return (
    <>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
        <Card className="md:col-span-2">
          <CardHeader className="pb-2"><CardTitle className="text-sm font-semibold flex items-center justify-between">Cajas registradoras
            <Button size="sm" variant="outline" onClick={() => setShowCRForm(true)} data-testid="new-cash-register-btn"><Plus className="w-3.5 h-3.5 mr-1" />Nueva caja</Button>
          </CardTitle></CardHeader>
          <CardContent>
            {registers.length === 0 ? <p className="text-xs text-slate-400">No hay cajas registradas</p> :
              <div className="space-y-1.5">
                {registers.map(r => (
                  <div key={r.id} className="flex items-center justify-between p-2 border rounded text-sm">
                    <div><p className="font-medium">{r.name}</p><p className="text-xs text-slate-500">{r.branch_name}</p></div>
                    <Badge variant="outline" className="text-xs bg-emerald-50 text-emerald-700">Activa</Badge>
                  </div>
                ))}
              </div>}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="pb-2"><CardTitle className="text-sm font-semibold">Historial de sesiones</CardTitle></CardHeader>
        <CardContent>
          {loading ? <div className="flex justify-center py-8"><div className="w-6 h-6 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" /></div> :
            <Table>
              <TableHeader><TableRow className="bg-slate-50/80">
                <TableHead className="text-xs font-semibold">Apertura</TableHead>
                <TableHead className="text-xs font-semibold">Caja / Sucursal</TableHead>
                <TableHead className="text-xs font-semibold">Cajero</TableHead>
                <TableHead className="text-xs font-semibold text-right">Apertura</TableHead>
                <TableHead className="text-xs font-semibold text-right">Esperado</TableHead>
                <TableHead className="text-xs font-semibold text-right">Real</TableHead>
                <TableHead className="text-xs font-semibold text-right">Diferencia</TableHead>
                <TableHead className="text-xs font-semibold text-center">Estado</TableHead>
              </TableRow></TableHeader>
              <TableBody>
                {sessions.map(s => (
                  <TableRow key={s.id} data-testid={`session-row-${s.id}`}>
                    <TableCell className="text-xs">{s.opened_at?.substring(0, 16).replace('T', ' ')}</TableCell>
                    <TableCell className="text-sm"><p>{s.cash_register_name}</p><p className="text-xs text-slate-400">{s.branch_name}</p></TableCell>
                    <TableCell className="text-xs">{s.opened_by_name}</TableCell>
                    <TableCell className="text-right text-sm">Q{(s.opening_amount || 0).toFixed(2)}</TableCell>
                    <TableCell className="text-right text-sm">{s.expected_amount != null ? `Q${(+s.expected_amount).toFixed(2)}` : '—'}</TableCell>
                    <TableCell className="text-right text-sm">{s.actual_amount != null ? `Q${(+s.actual_amount).toFixed(2)}` : '—'}</TableCell>
                    <TableCell className={`text-right text-sm font-medium ${s.difference > 0 ? 'text-blue-600' : s.difference < 0 ? 'text-red-600' : 'text-slate-700'}`}>{s.difference != null ? `Q${(+s.difference).toFixed(2)}` : '—'}</TableCell>
                    <TableCell className="text-center"><Badge variant="outline" className={`text-xs ${s.status === 'open' ? 'bg-amber-50 text-amber-700' : 'bg-slate-50 text-slate-600'}`}>{s.status === 'open' ? 'Abierta' : 'Cerrada'}</Badge></TableCell>
                  </TableRow>
                ))}
                {sessions.length === 0 && <TableRow><TableCell colSpan={8} className="text-center py-8 text-slate-400">Sin sesiones</TableCell></TableRow>}
              </TableBody>
            </Table>}
        </CardContent>
      </Card>

      <Dialog open={showCRForm} onOpenChange={setShowCRForm}>
        <DialogContent className="max-w-sm" data-testid="cash-register-form-dialog">
          <DialogHeader><DialogTitle>Nueva caja</DialogTitle></DialogHeader>
          <div className="space-y-3 py-2">
            <div><Label className="text-xs">Nombre</Label><Input className="mt-1 text-sm" value={crForm.name} onChange={e => setCrForm(f => ({ ...f, name: e.target.value }))} placeholder="Caja Principal" data-testid="cr-name-input" /></div>
            <div>
              <Label className="text-xs">Sucursal</Label>
              <Select value={crForm.branch_id} onValueChange={v => setCrForm(f => ({ ...f, branch_id: v }))}>
                <SelectTrigger className="mt-1 text-sm" data-testid="cr-branch-select"><SelectValue placeholder="Seleccionar" /></SelectTrigger>
                <SelectContent>{(branches || []).map(b => <SelectItem key={b.id} value={b.id}>{b.name}</SelectItem>)}</SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCRForm(false)}>Cancelar</Button>
            <Button className="bg-teal-600 hover:bg-teal-700" onClick={handleCreateCR} data-testid="save-cr-btn">Guardar</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
