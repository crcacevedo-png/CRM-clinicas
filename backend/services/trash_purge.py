"""Daily job that permanently purges items older than 30 days from the Papelera.

Scoped tables: `clinics` and `clinic_members`. For clinics we call the same
`_delete_clinic_data` helper used by the manual purge endpoint so every
clinic-scoped row is cleaned. For members we also try to remove their auth
account when they have no remaining memberships.

Idempotent and defensive: any single-row failure is logged and skipped.
"""
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

RETENTION_DAYS = 30


def purge_expired_trash() -> dict:
    """Purge clinics and users whose deleted_at is older than 30 days.

    Returns counters for observability.
    """
    from core import sdb, supabase_admin
    from routes.super_admin import _delete_clinic_data

    cutoff = (datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)).isoformat()
    stats = {"clinics_purged": 0, "members_purged": 0, "auth_users_deleted": 0, "errors": 0}

    # -- Clinics --
    try:
        rows = (
            sdb.table('clinics')
            .select('id,name')
            .not_.is_('deleted_at', 'null')
            .lte('deleted_at', cutoff)
            .execute()
            .data or []
        )
    except Exception as e:
        logger.warning(f"trash purge: could not list clinics: {e}")
        rows = []

    for c in rows:
        cid = c.get('id')
        try:
            members = sdb.table('clinic_members').select('user_id').eq('clinic_id', cid).execute().data or []
            uids = [m.get('user_id') for m in members if m.get('user_id')]
            _delete_clinic_data(cid)
            try:
                sdb.table('clinic_members').delete().eq('clinic_id', cid).execute()
            except Exception:
                pass
            for uid in uids:
                try:
                    other = sdb.table('clinic_members').select('id', count='exact').eq('user_id', uid).execute()
                    if (other.count or 0) > 0:
                        continue
                    supabase_admin.auth.admin.delete_user(uid)
                    stats["auth_users_deleted"] += 1
                except Exception as e:
                    logger.warning(f"trash purge: auth delete failed uid={uid}: {e}")
            sdb.table('clinics').delete().eq('id', cid).execute()
            stats["clinics_purged"] += 1
            logger.info(f"trash purge: clinic '{c.get('name')}' ({cid}) permanently deleted")
        except Exception as e:
            stats["errors"] += 1
            logger.warning(f"trash purge: clinic {cid} failed: {e}")

    # -- Orphan members (their clinic is still alive but member was soft-deleted > 30d ago) --
    try:
        rows = (
            sdb.table('clinic_members')
            .select('id,user_id')
            .not_.is_('deleted_at', 'null')
            .lte('deleted_at', cutoff)
            .execute()
            .data or []
        )
    except Exception as e:
        logger.warning(f"trash purge: could not list members: {e}")
        rows = []

    for m in rows:
        mid = m.get('id')
        try:
            sdb.table('clinic_members').delete().eq('id', mid).execute()
            uid = m.get('user_id')
            if uid:
                try:
                    other = sdb.table('clinic_members').select('id', count='exact').eq('user_id', uid).execute()
                    if (other.count or 0) == 0:
                        supabase_admin.auth.admin.delete_user(uid)
                        stats["auth_users_deleted"] += 1
                except Exception as e:
                    logger.warning(f"trash purge member auth uid={uid}: {e}")
            stats["members_purged"] += 1
        except Exception as e:
            stats["errors"] += 1
            logger.warning(f"trash purge: member {mid} failed: {e}")

    logger.info(f"trash purge cycle done: {stats}")
    return stats
