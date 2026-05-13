"""Global Announcements / Communication (Super Admin → Clinics).

- Super admin endpoints: list, create, update, delete announcements.
- Clinic endpoints: list announcements matching their segmentation (plan,
  country) and not yet dismissed by the current user; dismiss an announcement.

Segmentation matching:
- If `segment_plans` is null/empty → all plans match
- If `segment_countries` is null/empty → all countries match
- If `segment_clinic_ids` is null/empty → match by plan+country; if non-empty
  the clinic must be explicitly in the list
- Plus an active/time window: `is_active=true` AND now in [starts_at, ends_at]
  (null bounds are treated as -infinity / +infinity)
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException

from core import (
    sdb, logger, now_iso,
    require_super_admin, require_clinic_member,
)

router = APIRouter()

# ============== MODELS ==============

class AnnouncementCreate(BaseModel):
    title: str
    body: str
    severity: str = "info"  # info | success | warning | critical
    cta_label: Optional[str] = None
    cta_url: Optional[str] = None
    segment_plans: Optional[List[str]] = None
    segment_countries: Optional[List[str]] = None
    segment_clinic_ids: Optional[List[str]] = None
    is_active: bool = True
    starts_at: Optional[str] = None
    ends_at: Optional[str] = None


class AnnouncementUpdate(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    severity: Optional[str] = None
    cta_label: Optional[str] = None
    cta_url: Optional[str] = None
    segment_plans: Optional[List[str]] = None
    segment_countries: Optional[List[str]] = None
    segment_clinic_ids: Optional[List[str]] = None
    is_active: Optional[bool] = None
    starts_at: Optional[str] = None
    ends_at: Optional[str] = None


_VALID_SEVERITIES = {"info", "success", "warning", "critical"}


# ============== SUPER ADMIN ENDPOINTS ==============

@router.get("/admin/announcements")
async def list_announcements(user=Depends(require_super_admin)):
    try:
        res = sdb.table('super_announcements').select('*').order('created_at', desc=True).execute()
        rows = res.data or []
        # Add dismissal counts for analytics
        ids = [r['id'] for r in rows]
        counts = {}
        if ids:
            d = sdb.table('announcement_dismissals').select('announcement_id').in_('announcement_id', ids).execute()
            for x in (d.data or []):
                counts[x['announcement_id']] = counts.get(x['announcement_id'], 0) + 1
        for r in rows:
            r['dismissals_count'] = counts.get(r['id'], 0)
        return rows
    except Exception as e:
        logger.error(f"list_announcements: {e}")
        raise HTTPException(status_code=500, detail="Error al listar anuncios")


@router.post("/admin/announcements")
async def create_announcement(data: AnnouncementCreate, user=Depends(require_super_admin)):
    if data.severity not in _VALID_SEVERITIES:
        raise HTTPException(status_code=400, detail="Severidad inválida")
    if not data.title.strip() or not data.body.strip():
        raise HTTPException(status_code=400, detail="Título y cuerpo son requeridos")
    try:
        doc = {
            "id": str(uuid.uuid4()),
            "title": data.title.strip(),
            "body": data.body.strip(),
            "severity": data.severity,
            "cta_label": (data.cta_label or "").strip() or None,
            "cta_url": (data.cta_url or "").strip() or None,
            "segment_plans": data.segment_plans or None,
            "segment_countries": data.segment_countries or None,
            "segment_clinic_ids": data.segment_clinic_ids or None,
            "is_active": data.is_active,
            "starts_at": data.starts_at,
            "ends_at": data.ends_at,
            "created_by": getattr(user, "id", None),
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        sdb.table('super_announcements').insert(doc).execute()
        return {"id": doc["id"], "message": "Anuncio creado"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_announcement: {e}")
        raise HTTPException(status_code=500, detail="Error al crear anuncio")


@router.put("/admin/announcements/{announcement_id}")
async def update_announcement(announcement_id: str, data: AnnouncementUpdate, user=Depends(require_super_admin)):
    if data.severity is not None and data.severity not in _VALID_SEVERITIES:
        raise HTTPException(status_code=400, detail="Severidad inválida")
    try:
        update = data.model_dump(exclude_unset=True)
        # Normalize blanks
        for k in ("title", "body", "cta_label", "cta_url"):
            if k in update and isinstance(update[k], str):
                update[k] = update[k].strip() or (None if k != "title" and k != "body" else update[k])
        update["updated_at"] = now_iso()
        res = sdb.table('super_announcements').update(update).eq('id', announcement_id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Anuncio no encontrado")
        return {"message": "Anuncio actualizado"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"update_announcement: {e}")
        raise HTTPException(status_code=500, detail="Error al actualizar anuncio")


@router.delete("/admin/announcements/{announcement_id}")
async def delete_announcement(announcement_id: str, user=Depends(require_super_admin)):
    try:
        sdb.table('super_announcements').delete().eq('id', announcement_id).execute()
        return {"message": "Anuncio eliminado"}
    except Exception as e:
        logger.error(f"delete_announcement: {e}")
        raise HTTPException(status_code=500, detail="Error al eliminar anuncio")


# ============== CLINIC-FACING ENDPOINTS ==============

def _matches_segment(ann: dict, clinic: dict) -> bool:
    """Check if a clinic is targeted by an announcement's segmentation."""
    # Explicit allow-list takes priority: if set & non-empty, only listed clinics see it
    explicit = ann.get("segment_clinic_ids")
    if explicit:
        return clinic["id"] in explicit
    # Plan filter
    plans = ann.get("segment_plans")
    if plans:
        if (clinic.get("plan") or "free") not in plans:
            return False
    # Country filter (case-insensitive compare)
    countries = ann.get("segment_countries")
    if countries:
        c_country = (clinic.get("country") or "").strip().lower()
        if c_country not in [x.strip().lower() for x in countries]:
            return False
    return True


def _is_within_window(ann: dict, now_ts: datetime) -> bool:
    starts = ann.get("starts_at")
    ends = ann.get("ends_at")
    if starts:
        try:
            s = datetime.fromisoformat(starts.replace('Z', '+00:00'))
            if now_ts < s:
                return False
        except Exception:
            pass
    if ends:
        try:
            e = datetime.fromisoformat(ends.replace('Z', '+00:00'))
            if now_ts > e:
                return False
        except Exception:
            pass
    return True


@router.get("/clinic/announcements")
async def get_clinic_announcements(ctx=Depends(require_clinic_member)):
    """Return active announcements visible to the current member's clinic."""
    clinic_id = ctx["member"]["clinic_id"]
    user_id = getattr(ctx.get("auth_user"), "id", None)
    try:
        clinic = sdb.table('clinics').select('id,plan,country').eq('id', clinic_id).single().execute().data or {}
        anns_res = sdb.table('super_announcements').select('*').eq('is_active', True).order('created_at', desc=True).execute()
        anns = anns_res.data or []
        # Filter by time window + segmentation
        now_ts = datetime.now(timezone.utc)
        eligible = [a for a in anns if _is_within_window(a, now_ts) and _matches_segment(a, clinic)]
        # Subtract dismissed by this user
        dismissed_ids = set()
        if user_id and eligible:
            d_res = sdb.table('announcement_dismissals').select('announcement_id').eq('user_id', user_id).in_('announcement_id', [a['id'] for a in eligible]).execute()
            dismissed_ids = {x['announcement_id'] for x in (d_res.data or [])}
        return [
            {
                "id": a['id'],
                "title": a['title'],
                "body": a['body'],
                "severity": a.get('severity') or 'info',
                "cta_label": a.get('cta_label'),
                "cta_url": a.get('cta_url'),
                "created_at": a.get('created_at'),
            }
            for a in eligible if a['id'] not in dismissed_ids
        ]
    except Exception as e:
        logger.error(f"get_clinic_announcements: {e}")
        # Don't break the dashboard if announcements query fails
        return []


@router.post("/clinic/announcements/{announcement_id}/dismiss")
async def dismiss_announcement(announcement_id: str, ctx=Depends(require_clinic_member)):
    """Mark an announcement as dismissed for the current user (won't show again)."""
    clinic_id = ctx["member"]["clinic_id"]
    user_id = getattr(ctx.get("auth_user"), "id", None)
    if not user_id:
        raise HTTPException(status_code=400, detail="Sesión inválida")
    try:
        # Verify announcement exists
        ann = sdb.table('super_announcements').select('id').eq('id', announcement_id).maybe_single().execute()
        if not getattr(ann, 'data', None):
            raise HTTPException(status_code=404, detail="Anuncio no encontrado")
        # Upsert dismissal (PK: announcement_id+user_id)
        sdb.table('announcement_dismissals').upsert({
            "announcement_id": announcement_id,
            "clinic_id": clinic_id,
            "user_id": user_id,
            "dismissed_at": now_iso(),
        }).execute()
        return {"message": "Anuncio descartado"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"dismiss_announcement: {e}")
        raise HTTPException(status_code=500, detail="Error al descartar anuncio")
