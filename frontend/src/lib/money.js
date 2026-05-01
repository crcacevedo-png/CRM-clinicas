/**
 * Central money formatting utilities.
 * The system works with 2 decimals everywhere (currency: Q).
 */

// Round to exactly 2 decimals using Number.EPSILON to avoid IEEE-754 artefacts.
export function round2(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return 0;
  return Math.round((n + Number.EPSILON) * 100) / 100;
}

// Format as "Q1,234.56" (for display).
export function formatMoney(value, { withSymbol = true, locale = 'es-GT' } = {}) {
  const n = round2(value);
  const formatted = n.toLocaleString(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return withSymbol ? `Q${formatted}` : formatted;
}

// Parse user input (string) to a safe 2-decimal number.
export function parseMoney(input) {
  if (input == null || input === '') return 0;
  const s = String(input).replace(/,/g, '');
  return round2(parseFloat(s));
}

// Format a number into a plain 2-decimal string (useful for <input type="number"> defaults).
export function toFixed2(value) {
  return round2(value).toFixed(2);
}
