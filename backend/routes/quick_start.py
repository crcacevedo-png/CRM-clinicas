"""Quick-start onboarding checklist (clinic-level, clinic_admin only).

State lives in `clinics.quick_start` JSONB: {completed: [step_key], dismissed: bool}.
Shared across all admins of a clinic. The visible step catalog + feature gating
is computed on the frontend; the backend just persists completed/dismissed.
"""
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

router = APIRouter()

from core import sdb, logger, require_clinic_admin


class QuickStartUpdate(BaseModel):
    completed: Optional[List[str]] = None
    dismissed: Optional[bool] = None


def _get_state(clinic_id: str) -> dict:
    try:
        row = sdb.table('clinics').select('quick_start').eq('id', clinic_id).maybe_single().execute()
        data = getattr(row, 'data', None) or {}
        qs = data.get('quick_start') or {}
    except Exception as e:
        logger.warning(f"quick_start read failed: {e}")
        qs = {}
    return {
        "completed": qs.get("completed") or [],
        "dismissed": bool(qs.get("dismissed", False)),
    }


@router.get("/clinic/quick-start")
async def get_quick_start(ctx=Depends(require_clinic_admin)):
    return _get_state(ctx["member"]["clinic_id"])


@router.put("/clinic/quick-start")
async def update_quick_start(data: QuickStartUpdate, ctx=Depends(require_clinic_admin)):
    clinic_id = ctx["member"]["clinic_id"]
    state = _get_state(clinic_id)
    if data.completed is not None:
        state["completed"] = list(dict.fromkeys([s for s in data.completed if isinstance(s, str)]))
    if data.dismissed is not None:
        state["dismissed"] = bool(data.dismissed)
    try:
        sdb.table('clinics').update({"quick_start": state}).eq('id', clinic_id).execute()
    except Exception as e:
        logger.error(f"quick_start update failed: {e}")
        raise HTTPException(status_code=500, detail="Error al guardar el inicio rápido")
    return state
