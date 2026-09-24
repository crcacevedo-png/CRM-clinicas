# Escalado a 200 clínicas y 100–150 usuarios simultáneos

## Estado actual (lo que YA se optimizó en el código)
Todo esto ya está implementado y medido en el backend:

1. **Dashboard sin bloqueo** — `GET /clinic/dashboard` pasó de `async def` a `def`, así FastAPI lo corre en su threadpool y no serializa las peticiones.
2. **Caché compatible con Redis** (`services/cache.py`) para `get_clinic_features` y `get_role_modules` (TTL 45 s), con invalidación al cambiar roles/plan/features. Usa **Redis si existe `REDIS_URL`**, si no cae a caché en memoria.
3. **Reintento global de PostgREST** en todas las consultas (evita los 500 intermitentes por conexiones Supabase cerradas).
4. **Pool httpx ampliado** hacia Supabase (`max_connections=200`, keepalive 50, expiry 10 s).
5. **Threadpool AnyIO ampliado** a 128 (variable `THREADPOOL_TOKENS`).

### Medido en preview (1 solo worker)
| Escenario | Antes | Ahora |
|---|---|---|
| Dashboard 15 conc. | 27 s | ~4 s |
| Dashboard 30 conc. | ~54 s | 3.6 s |
| Ligero 100 conc. | — | 12.5 s, 100% OK |
| Dashboard 60 conc. | inusable | 60/60 OK pero ~68 s (satura 1 worker) |

**Conclusión:** un solo worker rinde bien hasta ~30 acciones pesadas simultáneas. Para 100–150 usuarios simultáneos hace falta escalar horizontalmente (varios workers) + Redis + más CPU. Eso es INFRA y se activa en Emergent.

## Lo que DEBES activar en Emergent (infra) para 100–150 simultáneos

### 1. Más CPU/RAM (procesador)
- Recomendado: **4–8 vCPU y 8–16 GB RAM** para el backend.
- Regla práctica: **1 worker por vCPU** (o `2×vCPU` si la carga es I/O como aquí).

### 2. Varios workers de Uvicorn/Gunicorn (lo más importante)
El preview corre `--workers 1 --reload` (config de desarrollo, archivo readonly). En **producción** el backend debe arrancar con varios workers, por ejemplo:

```
gunicorn server:app \
  -k uvicorn.workers.UvicornWorker \
  --workers 8 \
  --timeout 120 \
  --bind 0.0.0.0:8001
```
(o `uvicorn server:app --workers 8 --host 0.0.0.0 --port 8001` sin `--reload`)

Con 8 workers × ~20 concurrentes cómodos ≈ **~160 usuarios simultáneos**.

### 3. Redis (caché compartida entre workers) — YA soportado por el código
- Provisiona un Redis y define la variable de entorno **`REDIS_URL`** (ej: `redis://default:password@host:6379/0`).
- Al detectarlo, el backend lo usa automáticamente (lo verás en logs: "Cache backend: Redis").
- Sin Redis, cada worker mantiene su propia caché en memoria (funciona, pero multiplica las consultas a Supabase por la cantidad de workers).

### 4. Supabase (base de datos) — el nuevo cuello de botella al escalar workers
Con muchos workers, todas las consultas van a Supabase. Verificar/activar:
- **Connection Pooler de Supabase** (PgBouncer, modo *transaction*) — usar el puerto `6543`/pooler para las conexiones. Evita agotar las conexiones de Postgres.
- Subir el plan de Supabase si el proyecto está en Free (límite bajo de conexiones/CPU).
- Variables opcionales ya soportadas: `SUPABASE_MAX_CONNECTIONS` (def. 200), `SUPABASE_MAX_KEEPALIVE` (def. 50), `THREADPOOL_TOKENS` (def. 128).

## Siguientes optimizaciones de código (opcionales, si se requiere aún más)
- Convertir a `def` (o cachear) otros endpoints pesados: **Reportes**, listados grandes.
- Cachear el Dashboard por usuario con TTL corto (10–15 s) para recortar sus ~10-12 consultas.
- Reducir el número de consultas del Dashboard combinándolas en una función RPC de Postgres.

## Resumen
- Código: **listo** para escalar (Redis-ready, sin bloqueo del loop, pool y threadpool ampliados, reintentos).
- Infra en Emergent: **subir procesador**, **8 workers**, **provisionar Redis (`REDIS_URL`)**, y **usar el pooler de Supabase**. Con eso, la meta de 200 clínicas / 100–150 usuarios simultáneos es alcanzable.
