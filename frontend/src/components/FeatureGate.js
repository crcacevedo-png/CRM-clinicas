import { useFeature, useFeatures } from '../context/FeatureContext';
import { Card, CardContent } from './ui/card';
import { Badge } from './ui/badge';
import { Lock } from 'lucide-react';

const PLAN_NAMES = { basic: 'Basic', professional: 'Professional', enterprise: 'Enterprise' };

export default function FeatureGate({ feature, children, planRequired }) {
  const hasAccess = useFeature(feature);
  const { plan } = useFeatures();

  if (hasAccess) return children;

  const suggestedPlan = planRequired || 'Professional';

  return (
    <div className="p-6 lg:p-8 flex items-center justify-center min-h-[60vh]" data-testid={`feature-gate-${feature}`}>
      <Card className="border border-slate-200 max-w-md w-full">
        <CardContent className="p-8 text-center">
          <div className="w-14 h-14 rounded-full bg-slate-100 flex items-center justify-center mx-auto mb-4">
            <Lock className="w-6 h-6 text-slate-400" />
          </div>
          <h2 className="text-lg font-bold text-slate-900 mb-2">Funcionalidad no disponible</h2>
          <p className="text-sm text-slate-500 mb-4">
            Esta funcionalidad está disponible en el plan{' '}
            <Badge className="bg-teal-600 text-white">{suggestedPlan}</Badge>.
          </p>
          <p className="text-xs text-slate-400">
            Plan actual: <span className="font-medium">{PLAN_NAMES[plan] || plan}</span>.
            Contacta a tu administrador para actualizar.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
