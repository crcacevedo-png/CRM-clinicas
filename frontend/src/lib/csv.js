// Lightweight CSV export helpers — no external dependency.

/** Convert a value to a CSV-safe string (escape quotes, wrap if contains
 *  comma/quote/newline). */
function csvCell(v) {
  if (v === null || v === undefined) return '';
  const s = String(v);
  if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

/** Export an array of objects to a downloadable CSV file.
 *  @param {string} filename - Without extension; ".csv" is appended.
 *  @param {Array<Object>} rows - Array of plain objects.
 *  @param {Array<{key:string,label:string}>} [columns] - Optional column
 *         spec; if omitted, keys are inferred from the first row.
 */
export function exportToCsv(filename, rows, columns) {
  if (!rows || rows.length === 0) return;
  const cols = columns && columns.length
    ? columns
    : Object.keys(rows[0]).map((k) => ({ key: k, label: k }));
  const header = cols.map((c) => csvCell(c.label)).join(',');
  const body = rows
    .map((r) => cols.map((c) => csvCell(r[c.key])).join(','))
    .join('\n');
  const csv = `${header}\n${body}`;
  // BOM so Excel detects UTF-8 (acentos, ñ, etc.)
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${filename}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
