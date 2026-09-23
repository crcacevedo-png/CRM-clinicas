import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../../components/ui/card';
import { Button } from '../../../components/ui/button';
import { Input } from '../../../components/ui/input';
import { Label } from '../../../components/ui/label';
import { Badge } from '../../../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../../components/ui/select';
import { Tabs, TabsList, TabsTrigger } from '../../../components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../../components/ui/dialog';
import { Separator } from '../../../components/ui/separator';
import { toast } from 'sonner';
import { Search, Plus, X, Calculator, Lock, Unlock, Printer, AlertTriangle, MessageCircle } from 'lucide-react';
import { API, STATUS_LABEL } from './constants';
import { shareViaWhatsApp } from '../../../lib/whatsappShare';
import ChargeModal from './ChargeModal';
import CloseSessionDialog from './CloseSessionDialog';

export default function POSTab({ headers, branches, activeBranch, hasInventory }) {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showOpenDlg, setShowOpenDlg] = useState(false);
  const [showCloseDlg, setShowCloseDlg] = useState(false);
  const [registers, setRegisters] = useState([]);
  const [openForm, setOpenForm] = useState({ cash_register_id: '', opening_amount: 0 });
  const [opening, setOpening] = useState(false);

  const [catalogTab, setCatalogTab] = useState('services');
  const [services, setServices] = useState([]);
  const [products, setProducts] = useState([]);
  const [productSearch, setProductSearch] = useState('');

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

  const branchMismatch = activeBranch?.id && session.branch_id && activeBranch.id !== session.branch_id;
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

      {branchMismatch && (
        <div className="flex items-start gap-2 bg-amber-50 border border-amber-300 rounded-lg px-4 py-3 mb-4" data-testid="branch-mismatch-banner">
          <AlertTriangle className="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" />
          <div className="text-sm text-amber-900">
            <p className="font-semibold">Atención: tu sucursal activa no coincide con la caja abierta.</p>
            <p className="mt-1">
              Estás vendiendo en <strong>{session.branch_name}</strong> (la caja está abierta allí), pero tu selector de sucursal muestra <strong>{activeBranch?.name}</strong>.
              Para vender en <strong>{activeBranch?.name}</strong>, primero <button type="button" className="underline font-medium hover:text-amber-700" onClick={() => setShowCloseDlg(true)}>cierra la caja actual</button> y abre una nueva en esa sucursal.
            </p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
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

        <div className="lg:col-span-2">
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm font-semibold">Carrito y cobro</CardTitle></CardHeader>
            <CardContent className="space-y-3">
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

      <ChargeModal
        open={showCharge}
        onClose={() => setShowCharge(false)}
        total={total}
        hasPatient={!!customer.patient_id}
        patientName={customer.name}
        onConfirm={async (payments, arOpts = {}) => {
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
              ...arOpts,
            };
            const r = await axios.post(`${API}/clinic/sales`, payload, { headers });
            toast.success(`Venta ${r.data.sale_number} registrada`);
            setShowCharge(false);
            setShowSuccess(r.data);
            resetSale();
          } catch (err) { toast.error(err.response?.data?.detail || 'Error al registrar venta'); }
        }}
      />

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
            <Button variant="outline" className="w-full text-green-600 border-green-200 hover:bg-green-50" onClick={() => shareViaWhatsApp('sale', showSuccess.id, headers)} data-testid="whatsapp-receipt-btn"><MessageCircle className="w-4 h-4 mr-1" />Enviar por WhatsApp</Button>
            <Button className="w-full bg-teal-600 hover:bg-teal-700" onClick={() => setShowSuccess(null)} data-testid="new-sale-btn">Nueva venta</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <CloseSessionDialog open={showCloseDlg} onClose={() => setShowCloseDlg(false)} session={session} headers={headers} onClosed={() => { setShowCloseDlg(false); loadSession(); }} />
    </>
  );
}
