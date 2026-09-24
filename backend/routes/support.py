"""In-app support tickets.

Any authenticated user (super admin or active clinic member) can open a ticket
and exchange messages. The super admin sees every ticket, replies, and sets the
status (open / answered / closed). Replies also trigger an email notification
inviting the user to read the answer inside the platform.
"""
import os
import json
import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Request, UploadFile, File
from pydantic import BaseModel

from core import sdb, supabase_admin, run_sql, get_current_user, require_super_admin, logger

router = APIRouter()

VALID_STATUSES = ("open", "answered", "closed")
MAX_ATTACH_BYTES = 5 * 1024 * 1024


def _iso(v):
    return v.isoformat() if isinstance(v, datetime) else v


def _row(r: dict) -> dict:
    d = dict(r)
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
        elif v is not None and not isinstance(v, (str, int, float, bool, list, dict)):
            d[k] = str(v)
    return d


def _identity(user) -> dict:
    """Resolve who the authenticated caller is (super admin or clinic member)."""
    sa = sdb.table('super_admins').select('first_name,last_name,email').eq('user_id', user.id).maybe_single().execute()
    if getattr(sa, 'data', None):
        d = sa.data
        return {"user_type": "super_admin",
                "name": f"{d.get('first_name','')} {d.get('last_name','')}".strip() or "Super Admin",
                "clinic_id": None, "clinic_name": None, "email": user.email or d.get('email')}
    cm = sdb.table('clinic_members').select('clinic_id,first_name,last_name').eq('user_id', user.id).eq('is_active', True).maybe_single().execute()
    if getattr(cm, 'data', None):
        d = cm.data
        cname = None
        try:
            cl = sdb.table('clinics').select('name').eq('id', d['clinic_id']).maybe_single().execute()
            if getattr(cl, 'data', None):
                cname = cl.data.get('name')
        except Exception:
            pass
        return {"user_type": "clinic_member",
                "name": f"{d.get('first_name','')} {d.get('last_name','')}".strip() or "Usuario",
                "clinic_id": d['clinic_id'], "clinic_name": cname, "email": user.email}
    raise HTTPException(status_code=403, detail="Usuario sin acceso")


def _messages(ticket_id: str) -> list:
    rows = run_sql(
        "SELECT id, author_user_id, author_type, author_name, body, attachments, created_at "
        "FROM public.support_messages WHERE ticket_id = %s ORDER BY created_at ASC",
        (ticket_id,), fetch=True,
    ) or []
    return [_row(r) for r in rows]


def _clean_attachments(attachments) -> list:
    """Keep only well-formed {name, url} entries (max 5)."""
    out = []
    for a in (attachments or [])[:5]:
        if isinstance(a, dict) and a.get("url"):
            out.append({"name": str(a.get("name") or "adjunto"), "url": str(a["url"])})
    return out


# ============== ATTACHMENT UPLOAD ==============

@router.post("/support/upload")
async def upload_attachment(file: UploadFile = File(...), user=Depends(get_current_user)):
    """Upload a support screenshot to Supabase Storage. Returns {name, url}."""
    contents = await file.read()
    try:
        from services.input_sanitizer import validate_image_upload
        detected_mime = validate_image_upload(contents, max_bytes=MAX_ATTACH_BYTES)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    ext_map = {'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp', 'image/heic': 'heic', 'image/heif': 'heif', 'image/gif': 'gif'}
    ext = ext_map.get(detected_mime, 'png')
    path = f"_support/{user.id}/{uuid.uuid4().hex}.{ext}"
    try:
        supabase_admin.storage.from_('patient-files').upload(path, contents, {"content-type": detected_mime, "upsert": "true"})
        signed = supabase_admin.storage.from_('patient-files').create_signed_url(path, 31536000)
        url = signed.get('signedURL') or signed.get('signedUrl', '')
    except Exception as e:
        logger.error(f"support upload error: {e}")
        raise HTTPException(status_code=500, detail="Error al subir el archivo")
    return {"name": (file.filename or f"captura.{ext}")[:120], "url": url}


# ============== USER-FACING ==============

class TicketCreate(BaseModel):
    subject: str
    body: str
    attachments: list | None = None


class MessageCreate(BaseModel):
    body: str
    attachments: list | None = None


@router.post("/support/tickets")
async def create_ticket(payload: TicketCreate, request: Request, user=Depends(get_current_user)):
    subject = (payload.subject or "").strip()
    body = (payload.body or "").strip()
    if not subject or not body:
        raise HTTPException(status_code=400, detail="Asunto y mensaje son obligatorios")
    idn = _identity(user)
    attach = _clean_attachments(payload.attachments)
    rows = run_sql(
        "INSERT INTO public.support_tickets "
        "(user_id, user_email, user_name, user_type, clinic_id, clinic_name, subject, status, last_message_at) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,'open',NOW()) RETURNING id",
        (user.id, idn["email"], idn["name"], idn["user_type"], idn["clinic_id"], idn["clinic_name"], subject),
        fetch=True,
    )
    ticket_id = rows[0]["id"]
    run_sql(
        "INSERT INTO public.support_messages (ticket_id, author_user_id, author_type, author_name, body, attachments) "
        "VALUES (%s,%s,'user',%s,%s,%s::jsonb)",
        (ticket_id, user.id, idn["name"], body, json.dumps(attach)),
    )
    return {"ok": True, "ticket_id": str(ticket_id)}


@router.get("/support/unread-count")
async def support_unread_count(user=Depends(get_current_user)):
    """Number of the user's own tickets with an unread super-admin reply."""
    rows = run_sql(
        "SELECT count(*) AS n FROM public.support_tickets WHERE user_id = %s AND user_unread = true",
        (user.id,), fetch=True,
    ) or [{"n": 0}]
    return {"unread": rows[0]["n"]}


@router.get("/support/tickets")
async def my_tickets(user=Depends(get_current_user)):
    rows = run_sql(
        "SELECT id, subject, status, user_unread, created_at, updated_at, last_message_at "
        "FROM public.support_tickets WHERE user_id = %s ORDER BY last_message_at DESC",
        (user.id,), fetch=True,
    ) or []
    return {"tickets": [_row(r) for r in rows]}


@router.get("/support/tickets/{ticket_id}")
async def get_ticket(ticket_id: str, user=Depends(get_current_user)):
    rows = run_sql(
        "SELECT * FROM public.support_tickets WHERE id = %s AND user_id = %s",
        (ticket_id, user.id), fetch=True,
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado")
    # Opening the ticket marks any super-admin reply as read
    run_sql("UPDATE public.support_tickets SET user_unread = false WHERE id = %s AND user_id = %s", (ticket_id, user.id))
    return {"ticket": _row(rows[0]), "messages": _messages(ticket_id)}


@router.post("/support/tickets/{ticket_id}/messages")
async def add_message(ticket_id: str, payload: MessageCreate, user=Depends(get_current_user)):
    body = (payload.body or "").strip()
    if not body:
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacío")
    rows = run_sql(
        "SELECT id, user_name FROM public.support_tickets WHERE id = %s AND user_id = %s",
        (ticket_id, user.id), fetch=True,
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado")
    idn = _identity(user)
    attach = _clean_attachments(payload.attachments)
    run_sql(
        "INSERT INTO public.support_messages (ticket_id, author_user_id, author_type, author_name, body, attachments) "
        "VALUES (%s,%s,'user',%s,%s,%s::jsonb)",
        (ticket_id, user.id, idn["name"], body, json.dumps(attach)),
    )
    run_sql(
        "UPDATE public.support_tickets SET status='open', last_message_at=NOW(), updated_at=NOW() WHERE id = %s",
        (ticket_id,),
    )
    return {"ok": True}


# ============== SUPER ADMIN ==============

class ReplyCreate(BaseModel):
    body: str
    status: str | None = None
    attachments: list | None = None


class StatusUpdate(BaseModel):
    status: str


@router.get("/admin/support/summary")
async def admin_support_summary(user=Depends(require_super_admin)):
    """Lightweight counts for the sidebar badge (open tickets)."""
    counts = run_sql(
        "SELECT status, count(*) AS n FROM public.support_tickets GROUP BY status",
        None, fetch=True,
    ) or []
    summary = {c["status"]: c["n"] for c in counts}
    summary["total"] = sum(summary.values())
    summary.setdefault("open", 0)
    return summary


@router.get("/admin/support/tickets")
async def admin_list_tickets(status: str | None = None, user=Depends(require_super_admin)):
    if status and status in VALID_STATUSES:
        rows = run_sql(
            "SELECT * FROM public.support_tickets WHERE status = %s ORDER BY last_message_at DESC",
            (status,), fetch=True,
        )
    else:
        rows = run_sql(
            "SELECT * FROM public.support_tickets ORDER BY last_message_at DESC",
            None, fetch=True,
        )
    rows = rows or []
    counts = run_sql(
        "SELECT status, count(*) AS n FROM public.support_tickets GROUP BY status",
        None, fetch=True,
    ) or []
    summary = {c["status"]: c["n"] for c in counts}
    summary["total"] = sum(summary.values())
    return {"tickets": [_row(r) for r in rows], "summary": summary}


@router.get("/admin/support/tickets/{ticket_id}")
async def admin_get_ticket(ticket_id: str, user=Depends(require_super_admin)):
    rows = run_sql("SELECT * FROM public.support_tickets WHERE id = %s", (ticket_id,), fetch=True)
    if not rows:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado")
    return {"ticket": _row(rows[0]), "messages": _messages(ticket_id)}


@router.post("/admin/support/tickets/{ticket_id}/reply")
async def admin_reply(ticket_id: str, payload: ReplyCreate, request: Request, user=Depends(require_super_admin)):
    body = (payload.body or "").strip()
    if not body:
        raise HTTPException(status_code=400, detail="La respuesta no puede estar vacía")
    rows = run_sql("SELECT * FROM public.support_tickets WHERE id = %s", (ticket_id,), fetch=True)
    if not rows:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado")
    ticket = rows[0]
    idn = _identity(user)
    new_status = payload.status if payload.status in VALID_STATUSES else "answered"
    attach = _clean_attachments(payload.attachments)
    run_sql(
        "INSERT INTO public.support_messages (ticket_id, author_user_id, author_type, author_name, body, attachments) "
        "VALUES (%s,%s,'super_admin',%s,%s,%s::jsonb)",
        (ticket_id, user.id, idn["name"], body, json.dumps(attach)),
    )
    run_sql(
        "UPDATE public.support_tickets SET status=%s, user_unread=true, last_message_at=NOW(), updated_at=NOW() WHERE id = %s",
        (new_status, ticket_id),
    )
    # Email notification (best-effort)
    try:
        from services.email_service import send_email
        from services.email_templates import support_reply_notice
        to_email = ticket.get("user_email")
        if to_email:
            tpl = support_reply_notice(
                user_name=ticket.get("user_name") or "Usuario",
                subject=ticket.get("subject") or "tu mensaje",
                login_url=f"{os.environ.get('FRONTEND_URL', '')}/login",
            )
            await send_email(to=to_email, subject=tpl["subject"], html=tpl["html"], text=tpl["text"])
    except Exception as e:
        logger.warning(f"support reply email failed: {e}")
    return {"ok": True, "status": new_status}


@router.post("/admin/support/tickets/{ticket_id}/status")
async def admin_set_status(ticket_id: str, payload: StatusUpdate, user=Depends(require_super_admin)):
    if payload.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="Estado inválido")
    rows = run_sql("SELECT id FROM public.support_tickets WHERE id = %s", (ticket_id,), fetch=True)
    if not rows:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado")
    run_sql(
        "UPDATE public.support_tickets SET status=%s, updated_at=NOW() WHERE id = %s",
        (payload.status, ticket_id),
    )
    return {"ok": True, "status": payload.status}
