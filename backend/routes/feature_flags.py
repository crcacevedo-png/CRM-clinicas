"""Auto-extracted from server.py."""
import uuid
import logging
from datetime import datetime, timezone, timedelta, date
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Body, Request
from pydantic import BaseModel

router = APIRouter()

from core import (
    sdb, supabase_admin, supabase_user, logger, now_iso,
    generate_password, generate_slug, enrich_member, get_auth_users_map,
    get_plan_limits, parse_presentations,
    require_clinic_member, require_super_admin, get_current_user,
    LoginRequest, LoginResponse, ClinicCreate, ClinicUpdate, ClinicMemberCreate, UserUpdate,
    MedicationCreate, MedicationBulkImport, LabStudyCreate, LabStudyBulkImport,
    ICD10CodeCreate, ICD10BulkImport,
    AppointmentCreate, AppointmentUpdate, AppointmentStatusUpdate,
    PatientQuickCreate, PatientFullCreate,
)

# ============== FEATURE FLAGS ROUTES ==============

@router.get("/clinic/features")
async def get_clinic_features(ctx=Depends(require_clinic_member)):
    """Get all active features for the current clinic (plan + overrides)"""
    clinic_id = ctx["member"]["clinic_id"]
    try:
        clinic = sdb.table('clinics').select('plan').eq('id', clinic_id).single().execute()
        plan_code = clinic.data.get('plan', 'basic')

        plan = sdb.table('plans').select('id').eq('code', plan_code).maybe_single().execute()
        plan_features = []
        if plan.data:
            pf = sdb.table('plan_features').select('feature_id').eq('plan_id', plan.data['id']).execute()
            plan_feature_ids = [r['feature_id'] for r in (pf.data or [])]
            if plan_feature_ids:
                feats = sdb.table('features').select('code').in_('id', plan_feature_ids).eq('is_active', True).execute()
                plan_features = [f['code'] for f in (feats.data or [])]

        overrides = sdb.table('clinic_feature_overrides').select('feature_id,is_enabled').eq('clinic_id', clinic_id).execute()
        override_map = {}
        if overrides.data:
            feat_ids = [o['feature_id'] for o in overrides.data]
            if feat_ids:
                feats = sdb.table('features').select('id,code').in_('id', feat_ids).execute()
                id_to_code = {f['id']: f['code'] for f in (feats.data or [])}
                for o in overrides.data:
                    code = id_to_code.get(o['feature_id'])
                    if code:
                        override_map[code] = o['is_enabled']

        all_features = set(plan_features)
        for code, enabled in override_map.items():
            if enabled:
                all_features.add(code)
            else:
                all_features.discard(code)

        return {"features": sorted(all_features), "plan": plan_code}
    except Exception as e:
        logger.error(f"Get clinic features error: {e}")
        raise HTTPException(status_code=500, detail="Error al obtener features")

# --- ADMIN: Plans management ---

@router.get("/admin/plans")
async def admin_list_plans(user=Depends(require_super_admin)):
    try:
        plans = sdb.table('plans').select('*').order('sort_order').execute()
        return plans.data or []
    except Exception as e:
        logger.error(f"List plans error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@router.put("/admin/plans/{plan_id}")
async def admin_update_plan(plan_id: str, data: dict, user=Depends(require_super_admin)):
    try:
        allowed = ['name', 'description', 'price_monthly', 'price_yearly', 'max_users', 'max_patients', 'max_storage_mb', 'max_branches']
        update = {k: v for k, v in data.items() if k in allowed and v is not None}
        update['updated_at'] = now_iso()
        sdb.table('plans').update(update).eq('id', plan_id).execute()
        return {"message": "Plan actualizado"}
    except Exception as e:
        logger.error(f"Update plan error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@router.get("/admin/features")
async def admin_list_features(user=Depends(require_super_admin)):
    try:
        features = sdb.table('features').select('*').order('category').order('sort_order').execute()
        return features.data or []
    except Exception as e:
        logger.error(f"List features error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@router.get("/admin/plans/{plan_id}/features")
async def admin_get_plan_features(plan_id: str, user=Depends(require_super_admin)):
    try:
        pf = sdb.table('plan_features').select('feature_id').eq('plan_id', plan_id).execute()
        return [r['feature_id'] for r in (pf.data or [])]
    except Exception as e:
        logger.error(f"Get plan features error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@router.put("/admin/plans/{plan_id}/features")
async def admin_set_plan_features(plan_id: str, data: dict, user=Depends(require_super_admin)):
    """Set features for a plan (replaces all)"""
    try:
        feature_ids = data.get('feature_ids', [])
        sdb.table('plan_features').delete().eq('plan_id', plan_id).execute()
        for fid in feature_ids:
            sdb.table('plan_features').insert({"plan_id": plan_id, "feature_id": fid}).execute()
        return {"message": "Features actualizados"}
    except Exception as e:
        logger.error(f"Set plan features error: {e}")
        raise HTTPException(status_code=500, detail="Error")

# --- ADMIN: Clinic feature overrides ---

@router.get("/admin/clinics/{clinic_id}/features")
async def admin_get_clinic_features(clinic_id: str, user=Depends(require_super_admin)):
    try:
        clinic = sdb.table('clinics').select('plan').eq('id', clinic_id).single().execute()
        plan_code = clinic.data.get('plan', 'basic')
        plan = sdb.table('plans').select('id').eq('code', plan_code).maybe_single().execute()

        plan_feature_ids = []
        if plan.data:
            pf = sdb.table('plan_features').select('feature_id').eq('plan_id', plan.data['id']).execute()
            plan_feature_ids = [r['feature_id'] for r in (pf.data or [])]

        all_features = sdb.table('features').select('*').order('category').order('sort_order').execute()
        overrides = sdb.table('clinic_feature_overrides').select('feature_id,is_enabled').eq('clinic_id', clinic_id).execute()
        override_map = {o['feature_id']: o['is_enabled'] for o in (overrides.data or [])}

        result = []
        for f in (all_features.data or []):
            result.append({
                **f,
                "in_plan": f['id'] in plan_feature_ids,
                "override": override_map.get(f['id']),
            })
        return {"features": result, "plan": plan_code, "plan_feature_ids": plan_feature_ids}
    except Exception as e:
        logger.error(f"Get clinic features admin error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@router.put("/admin/clinics/{clinic_id}/features/{feature_id}")
async def admin_toggle_clinic_feature(clinic_id: str, feature_id: str, data: dict, user=Depends(require_super_admin)):
    """Toggle a feature override for a clinic"""
    try:
        is_enabled = data.get('is_enabled')
        if is_enabled is None:
            sdb.table('clinic_feature_overrides').delete().eq('clinic_id', clinic_id).eq('feature_id', feature_id).execute()
            return {"message": "Override eliminado"}
        existing = sdb.table('clinic_feature_overrides').select('id').eq('clinic_id', clinic_id).eq('feature_id', feature_id).maybe_single().execute()
        if existing and existing.data:
            sdb.table('clinic_feature_overrides').update({"is_enabled": is_enabled}).eq('id', existing.data['id']).execute()
        else:
            sdb.table('clinic_feature_overrides').insert({
                "clinic_id": clinic_id, "feature_id": feature_id, "is_enabled": is_enabled,
            }).execute()
        return {"message": "Override actualizado"}
    except Exception as e:
        logger.error(f"Toggle clinic feature error: {e}")
        raise HTTPException(status_code=500, detail="Error")

@router.put("/admin/clinics/{clinic_id}/plan")
async def admin_change_clinic_plan(clinic_id: str, data: dict, user=Depends(require_super_admin)):
    """Change a clinic's plan"""
    try:
        plan_code = data.get('plan')
        if not plan_code:
            raise HTTPException(status_code=400, detail="Plan requerido")
        plan = sdb.table('plans').select('id,max_users,max_patients,max_storage_mb,max_branches').eq('code', plan_code).maybe_single().execute()
        if not plan.data:
            raise HTTPException(status_code=404, detail="Plan no encontrado")
        sdb.table('clinics').update({
            "plan": plan_code,
            "max_users": plan.data['max_users'],
            "max_patients": plan.data['max_patients'],
            "max_storage_mb": plan.data['max_storage_mb'],
            "updated_at": now_iso(),
        }).eq('id', clinic_id).execute()
        return {"message": "Plan actualizado"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Change clinic plan error: {e}")
        raise HTTPException(status_code=500, detail="Error")

