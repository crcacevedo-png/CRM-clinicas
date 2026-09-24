"""Capacity watchdog: emails the super admin when CPU or DB connections
cross a threshold (default 80%). Runs on the shared APScheduler tick.

Multi-pod safe (distributed lock) and rate-limited via the shared cache so
the same alert is not re-sent within CAPACITY_ALERT_COOLDOWN_MIN minutes.
"""
import os
import socket
import logging
from datetime import datetime, timezone

logger = logging.getLogger("clinic_crm")

ALERT_EMAIL = os.environ.get("CAPACITY_ALERT_EMAIL", "info@cortexiagt.com")
THRESHOLD = float(os.environ.get("CAPACITY_ALERT_THRESHOLD", "80"))
COOLDOWN_MIN = int(os.environ.get("CAPACITY_ALERT_COOLDOWN_MIN", "60"))
ENABLED = os.environ.get("CAPACITY_ALERTS_ENABLED", "true").lower() != "false"
POOLER_LIMIT = int(os.environ.get("SUPABASE_MAX_CONNECTIONS", "200"))


def _measure() -> dict:
    """Return current cpu_pct and connections_pct (blocking — call in a thread)."""
    from core import run_sql
    out = {"cpu_pct": None, "conn_pct": None, "conn_total": None}
    try:
        import psutil
        out["cpu_pct"] = round(psutil.cpu_percent(interval=0.3), 1)
    except Exception as e:
        logger.debug(f"capacity_alerts cpu read failed: {e}")
    try:
        rows = run_sql(
            "SELECT count(*) AS total FROM pg_stat_activity WHERE datname = current_database()",
            None,
            fetch=True,
        )
        total = (rows[0]["total"] if rows else 0) or 0
        out["conn_total"] = total
        out["conn_pct"] = round(total * 100.0 / POOLER_LIMIT, 1) if POOLER_LIMIT else None
    except Exception as e:
        logger.debug(f"capacity_alerts conn read failed: {e}")
    return out


async def check_capacity_and_alert() -> dict:
    """One watchdog tick. Returns a small status dict for observability."""
    if not ENABLED:
        return {"skipped": "disabled"}

    from starlette.concurrency import run_in_threadpool
    from services.cache import cache_get, cache_set

    m = await run_in_threadpool(_measure)
    breaches = []
    if m["cpu_pct"] is not None and m["cpu_pct"] >= THRESHOLD:
        breaches.append(("cpu", f"CPU al {m['cpu_pct']}%"))
    if m["conn_pct"] is not None and m["conn_pct"] >= THRESHOLD:
        breaches.append(("conn", f"Conexiones a la BD al {m['conn_pct']}% ({m['conn_total']}/{POOLER_LIMIT})"))

    if not breaches:
        return {"ok": True, **m, "alerted": False}

    # Cooldown: don't re-send the same metric within the window.
    to_send = []
    for key, label in breaches:
        ck = f"capacity_alert:{key}"
        if cache_get(ck) is None:
            to_send.append(label)
            cache_set(ck, {"at": datetime.now(timezone.utc).isoformat()}, COOLDOWN_MIN * 60)

    if not to_send:
        return {"ok": True, **m, "alerted": False, "note": "cooldown active"}

    from services.email_service import send_email
    host = socket.gethostname()
    now_str = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    items_html = "".join(f"<li style='margin:4px 0'>{x}</li>" for x in to_send)
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;margin:auto">
      <h2 style="color:#B91C1C">🚨 Alerta de capacidad — Cortexia Medical</h2>
      <p>El sistema superó el umbral del <strong>{THRESHOLD:.0f}%</strong>:</p>
      <ul style="color:#0A2540">{items_html}</ul>
      <p style="color:#64748B;font-size:13px">
        Host: {host}<br/>CPU: {m['cpu_pct']}% · Conexiones: {m['conn_pct']}%<br/>
        Generado: {now_str}
      </p>
      <p style="color:#64748B;font-size:13px">
        Revisa el panel <strong>Salud del sistema</strong> (/admin/salud) para más detalle.
        No se reenviará esta alerta durante {COOLDOWN_MIN} min.
      </p>
    </div>
    """
    text = "Alerta de capacidad Cortexia — " + "; ".join(to_send)
    res = await send_email(
        to=ALERT_EMAIL,
        subject="🚨 Alerta de capacidad — Cortexia Medical",
        html=html,
        text=text,
    )
    logger.info(f"Capacity alert sent to {ALERT_EMAIL}: {to_send} (ok={res.get('ok')})")
    return {"ok": True, **m, "alerted": True, "sent": to_send, "email_ok": res.get("ok")}
