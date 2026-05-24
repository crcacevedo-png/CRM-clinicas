"""Email service powered by Resend.

Provides a single async helper `send_email()` that the rest of the backend
should use. Templates live in `email_templates.py`. Calls run in a worker
thread to keep the FastAPI event loop non-blocking; failures never raise to
the caller (transactional emails are best-effort by design — auth, RX, etc.
must keep working even if SMTP burps).

To enable: set RESEND_API_KEY, SENDER_EMAIL (and optionally SENDER_NAME) in
backend/.env. If RESEND_API_KEY is missing, every send is logged as DRY-RUN
and the app keeps working.
"""
import os
import asyncio
import base64
import logging
from pathlib import Path
from typing import Iterable, Optional

# Defensive: load env in case this module is imported before core.py
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / '.env')
except Exception:
    pass

import resend

logger = logging.getLogger(__name__)

_API_KEY = os.environ.get("RESEND_API_KEY")
_SENDER_EMAIL = os.environ.get("SENDER_EMAIL") or "onboarding@resend.dev"
_SENDER_NAME = os.environ.get("SENDER_NAME") or "Cortexia Medical"

if _API_KEY:
    resend.api_key = _API_KEY


def _from_header() -> str:
    return f"{_SENDER_NAME} <{_SENDER_EMAIL}>"


def _normalize_to(to) -> list[str]:
    if isinstance(to, str):
        return [to]
    return list(to or [])


async def send_email(
    *,
    to,
    subject: str,
    html: str,
    text: Optional[str] = None,
    attachments: Optional[Iterable[dict]] = None,
    reply_to: Optional[str] = None,
    cc: Optional[Iterable[str]] = None,
    bcc: Optional[Iterable[str]] = None,
) -> dict:
    """Send a transactional email via Resend (non-blocking).

    Args:
      to: recipient email (str) or list of emails.
      subject: subject line.
      html: HTML body.
      text: optional plain-text fallback.
      attachments: iterable of dicts with keys:
        - filename (str): name shown in the email client (e.g. "receta.pdf").
        - content (bytes | str): raw bytes OR a remote URL string.
      reply_to: optional Reply-To header.
      cc/bcc: optional copy lists.

    Returns:
      dict with keys: ok (bool), id (Resend message id or None), error (str|None).
      Never raises — caller can ignore or log.
    """
    if not _API_KEY:
        logger.warning(f"[DRY-RUN email] to={to} subject={subject!r}")
        return {"ok": False, "id": None, "error": "RESEND_API_KEY not set"}

    recipients = _normalize_to(to)
    if not recipients:
        return {"ok": False, "id": None, "error": "no recipients"}

    params: dict = {
        "from": _from_header(),
        "to": recipients,
        "subject": subject,
        "html": html,
    }
    if text:
        params["text"] = text
    if reply_to:
        params["reply_to"] = reply_to
    if cc:
        params["cc"] = list(cc)
    if bcc:
        params["bcc"] = list(bcc)
    if attachments:
        attach_list = []
        for a in attachments:
            content = a.get("content")
            if isinstance(content, (bytes, bytearray)):
                content = base64.b64encode(bytes(content)).decode("ascii")
                attach_list.append({"filename": a.get("filename") or "file", "content": content})
            elif isinstance(content, str):
                # treat as URL or already-base64 string; Resend accepts both via "path" or pre-encoded "content".
                if content.startswith(("http://", "https://")):
                    attach_list.append({"filename": a.get("filename") or "file", "path": content})
                else:
                    attach_list.append({"filename": a.get("filename") or "file", "content": content})
        if attach_list:
            params["attachments"] = attach_list

    try:
        result = await asyncio.to_thread(resend.Emails.send, params)
        msg_id = (result or {}).get("id") if isinstance(result, dict) else getattr(result, "id", None)
        logger.info(f"Email sent id={msg_id} to={recipients} subject={subject!r}")
        return {"ok": True, "id": msg_id, "error": None}
    except Exception as e:
        logger.error(f"Email send failed to={recipients} subject={subject!r}: {e}")
        return {"ok": False, "id": None, "error": str(e)[:300]}
