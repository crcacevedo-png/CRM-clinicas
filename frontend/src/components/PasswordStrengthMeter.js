import { useMemo } from 'react';
import { Check, X, Info } from 'lucide-react';

/**
 * PasswordStrengthMeter — mirror of backend services/password_policy.py.
 *
 * Client-side hint only. Server enforces the real rules at submit time (incl.
 * common-password blocklist and HIBP breach check).
 *
 * Rules mirrored:
 *  - length >= 10
 *  - >= 3 of 4 categories (upper, lower, digit, symbol)
 *  - does NOT contain email local-part (>= 4 chars, case-insensitive)
 *  - does NOT contain any name-token (>= 4 chars, case-insensitive)
 */
const MIN_LENGTH = 10;
const MIN_CATEGORIES = 3;

function categoryCount(pw) {
  let n = 0;
  if (/[A-Z]/.test(pw)) n++;
  if (/[a-z]/.test(pw)) n++;
  if (/\d/.test(pw)) n++;
  if (/[^A-Za-z0-9]/.test(pw)) n++;
  return n;
}

function containsPersonal(pw, email, name) {
  const low = pw.toLowerCase();
  if (email) {
    const local = email.split('@')[0].toLowerCase();
    if (local.length >= 4 && low.includes(local)) return `su email (${local})`;
  }
  if (name) {
    for (const t of name.toLowerCase().split(/[^\w]+/).filter(x => x.length >= 4)) {
      if (low.includes(t)) return `su nombre (${t})`;
    }
  }
  return null;
}

export default function PasswordStrengthMeter({ password, email = '', name = '', showChecks = true }) {
  const analysis = useMemo(() => {
    const pw = password || '';
    const cats = categoryCount(pw);
    const lengthOk = pw.length >= MIN_LENGTH;
    const catsOk = cats >= MIN_CATEGORIES;
    const personalHit = containsPersonal(pw, email, name);
    const personalOk = !personalHit;
    const passed = [lengthOk, catsOk, personalOk].filter(Boolean).length;
    // Length bonus: +1 for every 4 chars over minimum, capped at +2
    const lengthBonus = Math.min(2, Math.max(0, Math.floor((pw.length - MIN_LENGTH) / 4)));
    const strength = pw.length === 0 ? 0 : Math.min(4, passed + lengthBonus);
    const label = ['Muy débil', 'Débil', 'Aceptable', 'Fuerte', 'Muy fuerte'][strength];
    return { pw, cats, lengthOk, catsOk, personalOk, personalHit, strength, label };
  }, [password, email, name]);

  if (!password) return null;

  const barColor = ['bg-rose-500', 'bg-rose-400', 'bg-amber-500', 'bg-teal-500', 'bg-emerald-600'][analysis.strength];
  const textColor = ['text-rose-700', 'text-rose-600', 'text-amber-700', 'text-teal-700', 'text-emerald-700'][analysis.strength];

  return (
    <div className="mt-2 space-y-2" data-testid="password-strength-meter">
      <div className="flex items-center gap-2">
        <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
          <div
            className={`h-full ${barColor} transition-all duration-200`}
            style={{ width: `${(analysis.strength / 4) * 100}%` }}
          />
        </div>
        <span className={`text-xs font-medium ${textColor}`} data-testid="password-strength-label">
          {analysis.label}
        </span>
      </div>
      {showChecks && (
        <ul className="text-xs space-y-1">
          <Rule ok={analysis.lengthOk} text={`Mínimo ${MIN_LENGTH} caracteres`} testid="rule-length" />
          <Rule ok={analysis.catsOk} text={`Incluye al menos ${MIN_CATEGORIES} de: mayúscula, minúscula, número, símbolo`} testid="rule-categories" />
          <Rule
            ok={analysis.personalOk}
            text={analysis.personalHit ? `No debe contener ${analysis.personalHit}` : 'No contiene su email ni nombre'}
            testid="rule-personal"
          />
          <li className="flex items-start gap-1.5 text-slate-500 text-[11px] mt-1">
            <Info className="w-3 h-3 mt-0.5 flex-shrink-0" />
            <span>Al enviar se verificará también contra filtraciones públicas (HIBP) y una lista de contraseñas comunes.</span>
          </li>
        </ul>
      )}
    </div>
  );
}

function Rule({ ok, text, testid }) {
  return (
    <li className="flex items-center gap-1.5" data-testid={testid}>
      {ok
        ? <Check className="w-3 h-3 text-emerald-600 flex-shrink-0" />
        : <X className="w-3 h-3 text-slate-400 flex-shrink-0" />}
      <span className={ok ? 'text-emerald-700' : 'text-slate-500'}>{text}</span>
    </li>
  );
}

/**
 * Boolean helper to disable a submit button when the policy is not met.
 * Doesn't cover HIBP/common-blocklist (that's server-side only).
 */
export function passwordMeetsPolicy(pw, { email, name } = {}) {
  if (!pw || pw.length < MIN_LENGTH) return false;
  if (categoryCount(pw) < MIN_CATEGORIES) return false;
  if (containsPersonal(pw, email, name)) return false;
  return true;
}

export { MIN_LENGTH, MIN_CATEGORIES };
