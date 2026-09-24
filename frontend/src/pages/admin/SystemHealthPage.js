import { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Progress } from '../../components/ui/progress';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui/table';
import { RefreshCw, Play, AlertTriangle, CheckCircle2, Database, HardDrive, Users, Shield, Cpu, Activity, Clock, Archive, Download } from 'lucide-react';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Threshold color helper. green<50, amber 50-80, red>80
const barColor = (pct) => pct < 50 ? 'bg-emerald-500' : pct < 80 ? 'bg-amber-500' : 'bg-rose-500';
const statusColor = (pct) => pct < 50 ? 'text-emerald-600' : pct < 80 ? 'text-amber-600' : 'text-rose-600';
const fmt = (n) => (n ?? 0).toLocaleString('es-GT');
const fmtBytes = (b) => {
  if (b == null) return '-';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let i = 0, n = b;
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(n >= 100 ? 0 : 1)} ${units[i]}`;
};

function StatCard({ title, value, sub, icon: Icon, tone = 'default', testid }) {
  const toneClass = {
    default: 'bg-slate-50 text-slate-900',
    good: 'bg-emerald-50 text-emerald-900',
    warn: 'bg-amber-50 text-amber-900',
    bad: 'bg-rose-50 text-rose-900',
  }[tone] || 'bg-slate-50 text-slate-900';
  return (
    <div className={`rounded-xl border p-4 ${toneClass}`} data-testid={testid}>
      <div className="flex items-center justify-between">
        <span className="text-xs uppercase tracking-wide opacity-70">{title}</span>
        {Icon && <Icon className="w-4 h-4 opacity-60" />}
      </div>
      <div className="mt-2 text-2xl font-bold">{value}</div>
      {sub && <div className="text-xs opacity-60 mt-1">{sub}</div>}
    </div>
  );
}

export default function SystemHealthPage() {
  const { getAuthHeaders } = useAuth();
  const headers = getAuthHeaders();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [archives, setArchives] = useState([]);
  const [cap, setCap] = useState(null);
  const [bench, setBench] = useState(null);
  const [benching, setBenching] = useState(false);
  const [benchConc, setBenchConc] = useState(20);
  const [benchHistory, setBenchHistory] = useState([]);

  const loadBenchHistory = async () => {
    try {
      const res = await axios.get(`${API}/admin/system/capacity/benchmark/history?limit=20`, { headers });
      setBenchHistory(res.data?.runs || []);
    } catch { /* silent */ }
  };

  const load = async () => {
    setLoading(true);
    try {
      const [health, arch, capacity] = await Promise.all([
        axios.get(`${API}/admin/system/health`, { headers }),
        axios.get(`${API}/admin/maintenance/archives`, { headers }).catch(() => ({ data: { archives: [] } })),
        axios.get(`${API}/admin/system/capacity`, { headers }).catch(() => ({ data: null })),
      ]);
      setData(health.data);
      setArchives(arch.data.archives || []);
      setCap(capacity.data);
      loadBenchHistory();
    } catch (err) {
      toast.error('Error al cargar métricas: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  const runBenchmark = async () => {
    setBenching(true);
    setBench(null);
    try {
      const res = await axios.post(`${API}/admin/system/capacity/benchmark?concurrency=${benchConc}`, {}, { headers, timeout: 60000 });
      setBench(res.data);
      const c = await axios.get(`${API}/admin/system/capacity`, { headers }).catch(() => null);
      if (c) setCap(c.data);
      loadBenchHistory();
      toast.success('Prueba de capacidad completada');
    } catch (err) {
      toast.error('Error en la prueba: ' + (err.response?.data?.detail || err.message));
    } finally {
      setBenching(false);
    }
  };

  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);

  const runMaintenance = async () => {
    if (!window.confirm('¿Ejecutar mantenimiento mensual ahora? Puede tardar varios minutos.')) return;
    setRunning(true);
    try {
      const res = await axios.post(`${API}/admin/maintenance/monthly`, {}, { headers, timeout: 300000 });
      const r = res.data;
      const archived = (r.partitions_archived_dropped || []).filter(p => p.dropped).length;
      toast.success(`Mantenimiento completado en ${r.duration_seconds?.toFixed(1)}s — ${r.partitions_created || 0} particiones nuevas, ${archived} archivadas+dropped`);
      load();
    } catch (err) {
      toast.error('Error al ejecutar mantenimiento: ' + (err.response?.data?.detail || err.message));
    } finally {
      setRunning(false);
    }
  };

  if (!data && loading) return <div className="p-6 text-sm text-slate-500">Cargando…</div>;
  if (!data) return <div className="p-6 text-sm text-slate-500">Sin datos</div>;

  const dbPct = data.db_size?.pct_of_pro_limit || 0;
  const storagePct = data.storage?.pct_of_pro_limit || 0;
  const connsPct = ((data.connections?.total || 0) * 100) / (data.connections?.pooler_limit || 200);
  const authFail = data.auth?.failure_ratio_pct || 0;

  return (
    <div className="space-y-6" data-testid="system-health-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <Activity className="w-6 h-6 text-teal-600" />
            Salud del sistema
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Métricas en tiempo real para saber cuándo escalar. Generado en {data.duration_ms} ms.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={load} disabled={loading} data-testid="refresh-btn">
            <RefreshCw className={`w-4 h-4 mr-1 ${loading ? 'animate-spin' : ''}`} />
            Actualizar
          </Button>
          <Button size="sm" onClick={runMaintenance} disabled={running} className="bg-teal-600 hover:bg-teal-700" data-testid="run-maintenance-btn">
            <Play className="w-4 h-4 mr-1" />
            {running ? 'Ejecutando…' : 'Ejecutar mantenimiento'}
          </Button>
        </div>
      </div>

      {/* ===== LIVE CAPACITY ===== */}
      <Card data-testid="capacity-card">
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex items-center gap-2">
            <Cpu className="w-4 h-4 text-teal-600" />Capacidad en vivo
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {cap ? (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <StatCard title="CPU" value={`${cap.cpu?.percent ?? '-'}%`} sub={`${cap.cpu?.count ?? '?'} vCPU · carga ${cap.cpu?.load_avg?.[0] ?? '-'}`} icon={Cpu} tone={(cap.cpu?.percent ?? 0) < 70 ? 'good' : 'warn'} testid="cap-cpu" />
                <StatCard title="Memoria" value={`${cap.memory?.percent ?? '-'}%`} sub={`${fmt(cap.memory?.used_mb)} / ${fmt(cap.memory?.total_mb)} MB`} icon={HardDrive} tone={(cap.memory?.percent ?? 0) < 80 ? 'good' : 'warn'} testid="cap-mem" />
                <StatCard title="Redis" value={cap.redis?.enabled ? `${cap.redis?.ping_ms} ms` : 'Off'} sub={cap.redis?.enabled ? 'Caché compartida activa' : (cap.redis?.note || 'en memoria')} icon={Activity} tone={cap.redis?.enabled ? 'good' : 'warn'} testid="cap-redis" />
                <StatCard title="Latencia BD" value={`${cap.db_api?.ping_ms ?? '-'} ms`} sub="PostgREST (Supabase)" icon={Database} tone={(cap.db_api?.ping_ms ?? 0) < 150 ? 'good' : 'warn'} testid="cap-db" />
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <StatCard title="Threadpool" value={`${cap.threadpool?.in_use ?? 0}/${cap.threadpool?.capacity ?? '-'}`} sub="Hilos en uso / capacidad" icon={Activity} tone="default" testid="cap-threadpool" />
                <StatCard title="Workers" value={String(cap.config?.workers_env ?? '?')} sub="Procesos del backend" icon={Cpu} tone="default" testid="cap-workers" />
                <StatCard title="Conexiones Supabase" value={fmt(cap.config?.supabase_max_connections)} sub="Máx. pool httpx" icon={Database} tone="default" testid="cap-supaconn" />
                <StatCard title="Proceso" value={`${cap.process?.rss_mb ?? '-'} MB`} sub={`PID ${cap.process?.pid ?? '-'} · ${cap.process?.threads ?? '-'} hilos`} icon={HardDrive} tone="default" testid="cap-proc" />
              </div>
            </>
          ) : (
            <div className="text-sm text-slate-500">Sin datos de capacidad.</div>
          )}

          {/* Benchmark */}
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 space-y-3">
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-sm font-medium text-slate-700">Prueba de capacidad (carga interna):</span>
              <select
                value={benchConc}
                onChange={(e) => setBenchConc(Number(e.target.value))}
                className="text-sm border border-slate-300 rounded-md px-2 py-1 bg-white"
                data-testid="bench-concurrency-select"
              >
                {[20, 60, 120, 240, 360].map(v => <option key={v} value={v}>{v} simultáneas</option>)}
              </select>
              <Button size="sm" onClick={runBenchmark} disabled={benching} className="bg-teal-600 hover:bg-teal-700" data-testid="run-benchmark-btn">
                <Play className="w-4 h-4 mr-1" />{benching ? 'Ejecutando…' : 'Ejecutar prueba'}
              </Button>
            </div>
            {bench && (
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3" data-testid="bench-results">
                <StatCard title="Throughput" value={`${bench.throughput_ops_s}/s`} sub={`${bench.total_ops} ops · ${bench.wall_s}s`} tone="good" testid="bench-thrpt" />
                <StatCard title="Latencia p50" value={`${bench.latency_ms?.p50} ms`} sub={`p95 ${bench.latency_ms?.p95} ms`} tone="default" testid="bench-p50" />
                <StatCard title="Errores" value={fmt(bench.errors)} sub={`${bench.ok}/${bench.total_ops} OK`} tone={bench.errors ? 'bad' : 'good'} testid="bench-errors" />
                <StatCard title="Usuarios estimados" value={fmt(bench.estimated_active_users)} sub="activos en pico (aprox.)" tone="default" testid="bench-users" />
                <StatCard title="Concurrencia" value={fmt(bench.concurrency)} sub="peticiones en paralelo" tone="default" testid="bench-conc" />
              </div>
            )}
            {bench && <p className="text-xs text-slate-400">{bench.estimate_note}</p>}
          </div>

          {/* Benchmark history */}
          {benchHistory.length > 0 && (
            <div className="rounded-lg border border-slate-200 p-4" data-testid="bench-history">
              <div className="flex items-center gap-2 mb-2">
                <Clock className="w-4 h-4 text-slate-500" />
                <span className="text-sm font-medium text-slate-700">Historial de pruebas (últimas {benchHistory.length})</span>
              </div>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="text-xs">Fecha</TableHead>
                      <TableHead className="text-xs text-right">Concurrencia</TableHead>
                      <TableHead className="text-xs text-right">Throughput</TableHead>
                      <TableHead className="text-xs text-right">p50 / p95 (ms)</TableHead>
                      <TableHead className="text-xs text-right">Errores</TableHead>
                      <TableHead className="text-xs text-right">Usuarios est.</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {benchHistory.map((r) => (
                      <TableRow key={r.id} data-testid={`bench-history-row-${r.id}`}>
                        <TableCell className="text-xs text-slate-500">{r.created_at ? new Date(r.created_at).toLocaleString('es-GT') : '-'}</TableCell>
                        <TableCell className="text-xs text-right font-mono">{fmt(r.concurrency)}</TableCell>
                        <TableCell className="text-xs text-right font-mono">{r.throughput_ops_s}/s</TableCell>
                        <TableCell className="text-xs text-right font-mono">{r.p50_ms} / {r.p95_ms}</TableCell>
                        <TableCell className={`text-xs text-right font-mono ${(r.errors || 0) > 0 ? 'text-rose-600 font-semibold' : 'text-slate-500'}`}>{fmt(r.errors)}</TableCell>
                        <TableCell className="text-xs text-right font-mono">{fmt(r.estimated_active_users)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Signal cards row */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard title="DAU" value={fmt(data.active_users?.dau)} sub="Usuarios activos 24h" icon={Users} tone="default" testid="stat-dau" />
        <StatCard title="MAU" value={fmt(data.active_users?.mau)} sub="Usuarios activos 30d" icon={Users} tone="default" testid="stat-mau" />
        <StatCard title="Login fallos 24h" value={fmt(data.auth?.failed_24h)} sub={`${authFail}% del total`} icon={Shield} tone={authFail > 30 ? 'warn' : 'default'} testid="stat-failed" />
        <StatCard title="Rate-limits 24h" value={fmt(data.auth?.rate_limited_24h)} sub={`${fmt(data.auth?.unique_ips_24h)} IPs únicas`} icon={AlertTriangle} tone={data.auth?.rate_limited_24h > 20 ? 'warn' : 'default'} testid="stat-rl" />
      </div>

      {/* Capacity: DB, Storage, Connections */}
      <Card>
        <CardHeader><CardTitle className="text-base flex items-center gap-2"><Database className="w-4 h-4" /> Capacidad</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div>
            <div className="flex items-center justify-between mb-1 text-sm">
              <span className="font-medium">Base de datos (Supabase Pro 8 GB)</span>
              <span className={statusColor(dbPct)}>{data.db_size?.total_mb} MB / 8192 MB — {dbPct}%</span>
            </div>
            <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
              <div className={`h-full ${barColor(dbPct)} transition-all`} style={{ width: `${Math.min(100, dbPct)}%` }} />
            </div>
          </div>
          <div>
            <div className="flex items-center justify-between mb-1 text-sm">
              <span className="font-medium">Storage (Pro 100 GB)</span>
              <span className={statusColor(storagePct)}>{data.storage?.attachments_total_gb} GB / 100 GB — {storagePct}%</span>
            </div>
            <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
              <div className={`h-full ${barColor(storagePct)} transition-all`} style={{ width: `${Math.min(100, storagePct)}%` }} />
            </div>
            <p className="text-xs text-slate-500 mt-1">{fmt(data.storage?.attachments_total_files)} archivos totales</p>
          </div>
          <div>
            <div className="flex items-center justify-between mb-1 text-sm">
              <span className="font-medium">Conexiones activas al pooler</span>
              <span className={statusColor(connsPct)}>{data.connections?.total} / {data.connections?.pooler_limit} — {connsPct.toFixed(1)}%</span>
            </div>
            <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
              <div className={`h-full ${barColor(connsPct)} transition-all`} style={{ width: `${Math.min(100, connsPct)}%` }} />
            </div>
            <p className="text-xs text-slate-500 mt-1">{data.connections?.active} activas · {data.connections?.idle} idle</p>
          </div>
        </CardContent>
      </Card>

      {/* Row counts + Top tables */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader><CardTitle className="text-base">Volumen de datos</CardTitle></CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3 text-sm">
              {Object.entries(data.row_counts || {}).map(([k, v]) => (
                <div key={k} className="flex justify-between border-b border-slate-100 py-1">
                  <span className="text-slate-500">{k}</span>
                  <span className="font-mono font-semibold">{fmt(v)}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base flex items-center gap-2"><HardDrive className="w-4 h-4" /> Top tablas por tamaño</CardTitle></CardHeader>
          <CardContent>
            <Table>
              <TableHeader><TableRow><TableHead className="text-xs">Tabla</TableHead><TableHead className="text-xs text-right">Tamaño</TableHead><TableHead className="text-xs text-right">Rows</TableHead></TableRow></TableHeader>
              <TableBody>
                {(data.db_size?.top_tables || []).slice(0, 10).map(t => (
                  <TableRow key={t.name}>
                    <TableCell className="text-xs font-mono">{t.name}</TableCell>
                    <TableCell className="text-xs text-right">{fmtBytes(t.bytes)}</TableCell>
                    <TableCell className="text-xs text-right">{fmt(t.rows)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>

      {/* Jobs & locks */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader><CardTitle className="text-base flex items-center gap-2"><Cpu className="w-4 h-4" /> Export jobs</CardTitle></CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div><div className="text-xs text-slate-500">Encolados</div><div className="text-lg font-bold text-amber-600">{fmt(data.jobs?.queued)}</div></div>
              <div><div className="text-xs text-slate-500">En ejecución</div><div className="text-lg font-bold text-blue-600">{fmt(data.jobs?.running)}</div></div>
              <div><div className="text-xs text-slate-500">Completados (30d)</div><div className="text-lg font-bold text-emerald-600">{fmt(data.jobs?.done_last_30d)}</div></div>
              <div><div className="text-xs text-slate-500">Fallidos (30d)</div><div className={`text-lg font-bold ${(data.jobs?.failed_last_30d || 0) > 0 ? 'text-rose-600' : 'text-slate-500'}`}>{fmt(data.jobs?.failed_last_30d)}</div></div>
            </div>
            <p className="text-xs text-slate-500 mt-3">Duración promedio: {data.jobs?.avg_duration_seconds || 0} s</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base flex items-center gap-2"><Clock className="w-4 h-4" /> Locks distribuidos activos</CardTitle></CardHeader>
          <CardContent>
            {(data.locks?.active_locks || []).length === 0 ? (
              <p className="text-xs text-slate-400 py-4">Sin locks activos</p>
            ) : (
              <Table>
                <TableHeader><TableRow><TableHead className="text-xs">Lock</TableHead><TableHead className="text-xs">Holder</TableHead><TableHead className="text-xs">Estado</TableHead></TableRow></TableHeader>
                <TableBody>
                  {(data.locks?.active_locks || []).map(l => (
                    <TableRow key={l.lock_name}>
                      <TableCell className="text-xs font-mono">{l.lock_name}</TableCell>
                      <TableCell className="text-xs text-slate-500 truncate max-w-[180px]" title={l.holder}>{l.holder}</TableCell>
                      <TableCell>{l.is_stale
                        ? <Badge className="bg-rose-100 text-rose-700 text-[10px]">Stale</Badge>
                        : <Badge className="bg-emerald-100 text-emerald-700 text-[10px]">OK</Badge>}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
            <p className="text-xs text-slate-500 mt-3">
              Último tick reminders: {data.reminders?.last_acquired_at || data.reminders?.last_reminder_sent_at || '—'}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Partitions */}
      <Card>
        <CardHeader><CardTitle className="text-base">Particiones de audit_log</CardTitle></CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-2">
            {(data.partitions?.audit_log_partitions || []).map(p => (
              <div key={p.name} className="border rounded-lg p-2 text-xs">
                <div className="font-mono font-semibold">{p.name.replace('audit_log_', '')}</div>
                <div className="text-slate-500">{fmt(p.rows)} rows · {fmtBytes(p.bytes)}</div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Slow queries (if available) */}
      {data.slow_queries?.available && (data.slow_queries?.rows || []).length > 0 && (
        <Card>
          <CardHeader><CardTitle className="text-base">Queries más lentas (pg_stat_statements)</CardTitle></CardHeader>
          <CardContent>
            <Table>
              <TableHeader><TableRow><TableHead className="text-xs">Query</TableHead><TableHead className="text-xs text-right">Calls</TableHead><TableHead className="text-xs text-right">Mean ms</TableHead><TableHead className="text-xs text-right">Max ms</TableHead></TableRow></TableHeader>
              <TableBody>
                {data.slow_queries.rows.map((r, i) => (
                  <TableRow key={i}>
                    <TableCell className="text-xs font-mono max-w-[500px] truncate" title={r.query}>{r.query}</TableCell>
                    <TableCell className="text-xs text-right">{fmt(r.calls)}</TableCell>
                    <TableCell className={`text-xs text-right ${r.mean_ms > 100 ? 'text-rose-600 font-semibold' : ''}`}>{r.mean_ms}</TableCell>
                    <TableCell className="text-xs text-right">{r.max_ms}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Cold storage archives — audit_log partitions >12 months */}
      <Card data-testid="cold-storage-archives-card">
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Archive className="w-4 h-4 text-slate-600" />
            Archivos históricos (Cold Storage)
          </CardTitle>
        </CardHeader>
        <CardContent>
          {archives.length === 0 ? (
            <p className="text-xs text-slate-400 py-4">
              Aún no hay particiones archivadas. Se generan automáticamente cuando una partición supera los 12 meses.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-xs">Archivo</TableHead>
                  <TableHead className="text-xs">Fecha</TableHead>
                  <TableHead className="text-xs text-right">Tamaño</TableHead>
                  <TableHead className="text-xs text-right">Descarga</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {archives.map(a => (
                  <TableRow key={a.name} data-testid={`archive-row-${a.name}`}>
                    <TableCell className="text-xs font-mono">{a.name}</TableCell>
                    <TableCell className="text-xs text-slate-500">
                      {a.updated_at ? new Date(a.updated_at).toLocaleDateString('es-GT') : '-'}
                    </TableCell>
                    <TableCell className="text-xs text-right font-mono">{fmtBytes(a.size)}</TableCell>
                    <TableCell className="text-xs text-right">
                      {a.signed_url ? (
                        <a
                          href={a.signed_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-teal-600 hover:text-teal-800"
                          data-testid={`download-archive-${a.name}`}
                        >
                          <Download className="w-3 h-3" /> Descargar
                        </a>
                      ) : <span className="text-slate-400">—</span>}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
          <p className="text-xs text-slate-500 mt-3">
            Formato: JSONL comprimido (gzip). URLs firmadas válidas por 24h. Ideal para restauración forense o cumplimiento regulatorio.
          </p>
        </CardContent>
      </Card>

      {/* Growth recommendations */}
      <Card>
        <CardHeader><CardTitle className="text-base flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-emerald-600" /> Recomendaciones de escalado</CardTitle></CardHeader>
        <CardContent>
          <ul className="text-sm space-y-2">
            {dbPct >= 60 && <li className="text-amber-700">⚠️ DB al {dbPct}% del plan Pro. Planifica upgrade a Team ($599/mo) o archivar datos históricos.</li>}
            {storagePct >= 60 && <li className="text-amber-700">⚠️ Storage al {storagePct}%. Considera limpiar PDFs viejos o mover a S3.</li>}
            {connsPct >= 60 && <li className="text-amber-700">⚠️ Conexiones al {connsPct.toFixed(0)}%. Añade PgBouncer transaction-mode.</li>}
            {authFail > 30 && <li className="text-rose-700">🚨 {authFail}% de logins fallando — posible ataque. Revisa audit log filtrando por login_failed.</li>}
            {(data.jobs?.failed_last_30d || 0) > 5 && <li className="text-rose-700">🚨 {data.jobs.failed_last_30d} exports fallidos este mes.</li>}
            {(data.locks?.active_locks || []).some(l => l.is_stale) && <li className="text-rose-700">🚨 Locks stale detectados — un pod probablemente crashó reteniendo el lock.</li>}
            {dbPct < 30 && storagePct < 30 && connsPct < 30 && authFail < 10 && (
              <li className="text-emerald-700">✅ Todos los indicadores en verde. Sistema saludable para seguir creciendo.</li>
            )}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
