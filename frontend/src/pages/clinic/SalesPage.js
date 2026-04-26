import { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { useBranch } from '../../context/BranchContext';
import { useFeatures } from '../../context/FeatureContext';
import FeatureGate from '../../components/FeatureGate';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { ShoppingCart, Calendar, Stethoscope, Lock } from 'lucide-react';
import POSTab from './sales/POSTab';
import DailySalesTab from './sales/DailySalesTab';
import ServicesTab from './sales/ServicesTab';
import SessionsTab from './sales/SessionsTab';

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
          <TabsContent value="day"><DailySalesTab headers={headers} branches={branches} activeBranch={activeBranch} /></TabsContent>
          <TabsContent value="services"><ServicesTab headers={headers} /></TabsContent>
          <TabsContent value="sessions"><SessionsTab headers={headers} branches={branches} activeBranch={activeBranch} /></TabsContent>
        </Tabs>
      </div>
    </FeatureGate>
  );
}
