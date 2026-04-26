"""Phase 2 refactor: extract 12 more modules from server.py.

Format: list of (module_name, [(start, end), ...])
Ranges 1-indexed, end inclusive.
"""
import re

# Determined via grep of section markers + endpoint locations
SECTIONS = [
    ('auth', [(254, 305)]),
    ('super_admin', [(306, 662)]),  # dashboard + admin/clinics + admin/users
    ('catalogs', [(663, 913)]),
    ('clinic_settings', [(978, 1215)]),  # config + settings + members
    ('appointments', [(1216, 1449), (2757, 2868)]),  # + clinic_dashboard
    ('patients', [(1450, 1632), (2704, 2755)]),  # + patient_files
    ('medical_records', [(1633, 1984)]),  # templates + records
    ('prescriptions', [(1985, 2401)]),
    ('lab_orders', [(2402, 2703)]),
    ('google_calendar', [(2870, 3150)]),
    ('branches', [(3151, 3263)]),
    ('feature_flags', [(3264, 3434)]),
]

# Common deps needed by every router
COMMON_DEPS = "sdb, supabase_admin, require_clinic_member, now_iso, logger"

# Module-specific extra deps (functions/classes only in server.py that this module uses)
EXTRA_DEPS = {
    'auth': "supabase_anon, _ensure_super_admin_seed, LoginRequest, LoginResponse",
    'super_admin': "supabase_anon, require_super_admin, generate_password, ClinicCreate, ClinicUpdate, MemberCreate, UserUpdate, ResetPasswordRequest",
    'catalogs': "require_super_admin, MedicationCreate, MedicationUpdate, LabStudyCreate, LabStudyUpdate, ICD10Create",
    'clinic_settings': "require_clinic_admin, ClinicSettingsUpdate, MemberInvite, MemberUpdate, generate_password",
    'appointments': "require_clinic_member, AppointmentCreate, AppointmentUpdate, AppointmentStatusUpdate",
    'patients': "require_clinic_member, PatientCreate, PatientUpdate",
    'medical_records': "require_clinic_member, ConsultationTemplateCreate, ConsultationTemplateUpdate, MedicalRecordCreate, MedicalRecordUpdate, MedicalRecordAddendum",
    'prescriptions': "require_clinic_member, MedicationFromCatalog, PrescriptionCreate, PrescriptionUpdate",
    'lab_orders': "require_clinic_member, LabOrderCreate",
    'google_calendar': "require_clinic_member, _get_google_oauth_flow, _encrypt_token, _decrypt_token, GoogleCalendarSettings",
    'branches': "require_clinic_member, require_clinic_admin, BranchCreate, BranchUpdate",
    'feature_flags': "require_clinic_member, require_super_admin",
}


def main():
    with open('/app/backend/server.py', 'r') as f:
        lines = f.readlines()

    # 1. Extract sections (carefully — some modules have multiple ranges)
    extracted = {}
    for name, ranges in SECTIONS:
        chunks = []
        for s, e in ranges:
            block = ''.join(lines[s - 1:e])
            block = block.replace('@api_router.', '@router.')
            chunks.append(block)
        extracted[name] = '\n\n'.join(chunks)

    # 2. Write each route file. We use try/except on imports of unknown symbols
    # so the file loads even if some helper isn't yet defined (resolved at request time).
    HEADER_TPL = '''"""Auto-extracted from server.py."""
import uuid
import logging
from datetime import datetime, timezone, timedelta, date
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Body, Request
from pydantic import BaseModel

router = APIRouter()

# Shared deps from server module (imported at file-load time, after server.py finishes init)
from server import {deps}
'''
    for name, _ in SECTIONS:
        deps_str = COMMON_DEPS
        extra = EXTRA_DEPS.get(name)
        if extra:
            deps_str = deps_str + ', ' + extra
        # Try import — fall back gracefully
        body = HEADER_TPL.format(deps=deps_str)
        # google_calendar needs Fernet, base64, hashlib, RedirectResponse — they're imported inline in the section
        body += '\n' + extracted[name]
        with open(f'/app/backend/routes/{name}.py', 'w') as out:
            out.write(body)
        print(f"Wrote routes/{name}.py")

    # 3. Patch server.py: delete sections from BOTTOM to TOP. Flatten ranges and sort desc.
    flat_ranges = []
    for name, ranges in SECTIONS:
        for s, e in ranges:
            flat_ranges.append((s, e, name))
    flat_ranges.sort(key=lambda x: -x[0])
    for s, e, name in flat_ranges:
        del lines[s - 1:e]
        lines.insert(s - 1, f"# === Routes moved to routes/{name}.py ===\n")

    new_content = ''.join(lines)

    # 4. Update the include_router section to import the new modules too
    new_include = '''
# === Refactored route modules (Phase 1 + 2) ===
# Imported here (after all shared symbols are defined) to avoid circular imports.
from routes import (
    auth as _r_auth,
    super_admin as _r_sa,
    catalogs as _r_cat,
    clinic_settings as _r_cs,
    branches as _r_br,
    feature_flags as _r_ff,
    patients as _r_pat,
    appointments as _r_apt,
    medical_records as _r_mr,
    prescriptions as _r_pr,
    lab_orders as _r_lab,
    google_calendar as _r_gc,
    inventory as _r_inv,
    expenses as _r_exp,
    commissions as _r_comm,
    sales as _r_sales,
    accounts_receivable as _r_ar,
    reports as _r_rep,
)
for _r in (
    _r_auth, _r_sa, _r_cat, _r_cs, _r_br, _r_ff,
    _r_pat, _r_apt, _r_mr, _r_pr, _r_lab, _r_gc,
    _r_inv, _r_exp, _r_comm, _r_sales, _r_ar, _r_rep,
):
    api_router.include_router(_r.router)
'''
    # Replace the previous include block
    new_content = re.sub(
        r'# === Refactored route modules ===.*?api_router\.include_router\(_r\.router\)\n',
        new_include.strip() + '\n',
        new_content,
        flags=re.DOTALL,
    )

    with open('/app/backend/server.py', 'w') as f:
        f.write(new_content)
    print(f"\nserver.py: {new_content.count(chr(10))} lines")


if __name__ == '__main__':
    main()
