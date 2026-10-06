"""Tests for Smart Retries (Stripe) — webhook attempts logging + grace window."""
import os
import time
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import requests

API_URL = os.environ.get("REACT_APP_BACKEND_URL") or (
    open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].strip().split("\n")[0]
)
BASE = f"{API_URL}/api"

SA_EMAIL = "info@cortexiagt.com"
SA_PASSWORD = "Armagedon1980$"
CM_EMAIL = "prueba3@gmail.com"
CM_PASSWORD = "Test123456!"
CLINIC_ID = "c0321ed8-97da-47a1-b601-3b94bffabdd7"


def _login(email, password):
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": password}, timeout=10)
    r.raise_for_status()
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def sa_headers():
    return {"Authorization": f"Bearer {_login(SA_EMAIL, SA_PASSWORD)}"}


@pytest.fixture(scope="module")
def cm_headers():
    return {"Authorization": f"Bearer {_login(CM_EMAIL, CM_PASSWORD)}"}


@pytest.fixture(scope="module")
def sdb():
    import sys
    sys.path.insert(0, "/app/backend")
    from core import sdb as _sdb
    return _sdb


@pytest.fixture
def restore_clinic(sdb):
    """Reset the test clinic to normal state before AND after each test."""
    def _restore():
        sdb.table('clinics').update({
            "stripe_subscription_status": None,
            "payment_grace_until": None,
            "is_payment_blocked": False,
            "payment_blocked_at": None,
            "is_courtesy": False,
            "stripe_subscription_id": None,
        }).eq('id', CLINIC_ID).execute()
        sdb.table('payment_attempts').delete().eq('clinic_id', CLINIC_ID).execute()
    _restore()
    yield _restore
    _restore()


# =============================================================================
# payment_attempts table
# =============================================================================

class TestPaymentAttemptsTable:
    def test_table_exists_with_required_columns(self, sdb):
        """payment_attempts must exist with all required columns."""
        # Any select should return (an empty list) without raising
        res = sdb.table('payment_attempts').select(
            'id,clinic_id,stripe_invoice_id,stripe_subscription_id,attempt_count,'
            'status,failure_code,failure_message,amount_due,currency,next_attempt_at,'
            'attempted_at,created_at'
        ).limit(1).execute()
        assert isinstance(res.data, list)


# =============================================================================
# webhook: invoice.payment_failed → logs attempt + extends grace
# =============================================================================

class TestWebhookPaymentFailure:
    def test_payment_failed_logs_attempt_and_sets_grace(self, sdb, restore_clinic):
        """Simulate Stripe invoice.payment_failed → attempt row inserted + grace set."""
        from routes.billing import _apply_payment_failure
        sub_id = f"sub_test_{uuid.uuid4().hex[:8]}"
        sdb.table('clinics').update({
            "stripe_subscription_id": sub_id,
            "is_courtesy": False,
        }).eq('id', CLINIC_ID).execute()

        next_at = int((datetime.now(timezone.utc) + timedelta(days=5)).timestamp())
        invoice = {
            "id": f"in_test_{uuid.uuid4().hex[:8]}",
            "subscription": sub_id,
            "attempt_count": 2,
            "next_payment_attempt": next_at,
            "amount_due": 29900,
            "currency": "usd",
            "last_payment_error": {"code": "card_declined", "message": "Your card was declined."},
        }
        _apply_payment_failure(invoice)

        # Attempt was logged
        attempts = sdb.table('payment_attempts').select('*').eq('clinic_id', CLINIC_ID).execute().data
        assert len(attempts) == 1, f"expected 1 attempt, got {len(attempts)}"
        a = attempts[0]
        assert a['status'] == 'failed'
        assert a['attempt_count'] == 2
        assert a['failure_code'] == 'card_declined'
        assert a['failure_message'] == 'Your card was declined.'
        assert float(a['amount_due']) == 299.0
        assert a['currency'] == 'USD'
        assert a['next_attempt_at'] is not None

        # Grace was set past the next retry
        c = sdb.table('clinics').select('stripe_subscription_status,payment_grace_until').eq('id', CLINIC_ID).single().execute().data
        assert c['stripe_subscription_status'] == 'past_due'
        grace = datetime.fromisoformat(c['payment_grace_until'].replace('Z', '+00:00'))
        expected_min = datetime.fromtimestamp(next_at, tz=timezone.utc)
        assert grace >= expected_min, f"grace {grace} must be >= stripe next_attempt {expected_min}"

    def test_payment_failed_courtesy_logs_but_no_block(self, sdb, restore_clinic):
        """Courtesy clinics: attempt is logged (audit) but no grace/past_due set."""
        from routes.billing import _apply_payment_failure
        sub_id = f"sub_courtesy_{uuid.uuid4().hex[:8]}"
        sdb.table('clinics').update({
            "stripe_subscription_id": sub_id,
            "is_courtesy": True,
        }).eq('id', CLINIC_ID).execute()

        invoice = {
            "id": f"in_test_{uuid.uuid4().hex[:8]}",
            "subscription": sub_id,
            "attempt_count": 1,
            "next_payment_attempt": None,
            "amount_due": 0,
            "currency": "usd",
            "last_payment_error": None,
        }
        _apply_payment_failure(invoice)

        attempts = sdb.table('payment_attempts').select('*').eq('clinic_id', CLINIC_ID).execute().data
        assert len(attempts) == 1  # Logged for audit

        c = sdb.table('clinics').select('stripe_subscription_status,payment_grace_until,is_payment_blocked').eq('id', CLINIC_ID).single().execute().data
        assert c['stripe_subscription_status'] != 'past_due'
        assert c['payment_grace_until'] is None
        assert c['is_payment_blocked'] is False

    def test_payment_failed_no_next_attempt_fallback_grace(self, sdb, restore_clinic):
        """When Stripe exhausted retries (no next_payment_attempt), fall back to 3-day grace."""
        from routes.billing import _apply_payment_failure
        sub_id = f"sub_exhausted_{uuid.uuid4().hex[:8]}"
        sdb.table('clinics').update({
            "stripe_subscription_id": sub_id,
            "is_courtesy": False,
        }).eq('id', CLINIC_ID).execute()

        invoice = {
            "id": f"in_test_{uuid.uuid4().hex[:8]}",
            "subscription": sub_id,
            "attempt_count": 4,
            "next_payment_attempt": None,
            "amount_due": 9900,
            "currency": "usd",
            "last_payment_error": {"code": "insufficient_funds", "message": "Insufficient funds."},
        }
        _apply_payment_failure(invoice)

        c = sdb.table('clinics').select('payment_grace_until').eq('id', CLINIC_ID).single().execute().data
        grace = datetime.fromisoformat(c['payment_grace_until'].replace('Z', '+00:00'))
        delta = (grace - datetime.now(timezone.utc)).total_seconds() / 86400
        assert 2.5 <= delta <= 3.5, f"grace delta={delta} days, expected ~3"

    def test_payment_failed_grace_never_shrinks(self, sdb, restore_clinic):
        """A second failed attempt must not pull grace backwards."""
        from routes.billing import _apply_payment_failure
        sub_id = f"sub_grace_{uuid.uuid4().hex[:8]}"
        far = (datetime.now(timezone.utc) + timedelta(days=15)).isoformat()
        sdb.table('clinics').update({
            "stripe_subscription_id": sub_id,
            "is_courtesy": False,
            "payment_grace_until": far,
            "stripe_subscription_status": "past_due",
        }).eq('id', CLINIC_ID).execute()

        # New failure with much sooner next_attempt
        near_ts = int((datetime.now(timezone.utc) + timedelta(days=1)).timestamp())
        invoice = {
            "id": f"in_test_{uuid.uuid4().hex[:8]}",
            "subscription": sub_id,
            "attempt_count": 3,
            "next_payment_attempt": near_ts,
            "amount_due": 9900,
            "currency": "usd",
        }
        _apply_payment_failure(invoice)

        c = sdb.table('clinics').select('payment_grace_until').eq('id', CLINIC_ID).single().execute().data
        new_grace = datetime.fromisoformat(c['payment_grace_until'].replace('Z', '+00:00'))
        old_grace = datetime.fromisoformat(far.replace('+00:00', '+00:00'))
        assert new_grace >= old_grace, "grace must never shrink"


# =============================================================================
# webhook: invoice.payment_succeeded → logs success + clears block
# =============================================================================

class TestWebhookPaymentSuccess:
    def test_payment_success_logs_and_clears(self, sdb, restore_clinic):
        from routes.billing import _apply_payment_failure, _apply_payment_success
        sub_id = f"sub_ok_{uuid.uuid4().hex[:8]}"
        sdb.table('clinics').update({
            "stripe_subscription_id": sub_id,
            "is_courtesy": False,
            "is_payment_blocked": True,
            "stripe_subscription_status": "past_due",
            "payment_grace_until": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        }).eq('id', CLINIC_ID).execute()

        # First a failure, then a success
        _apply_payment_failure({
            "id": f"in_f_{uuid.uuid4().hex[:8]}", "subscription": sub_id,
            "attempt_count": 1, "amount_due": 9900, "currency": "usd",
            "next_payment_attempt": int((datetime.now(timezone.utc) + timedelta(days=2)).timestamp()),
        })
        _apply_payment_success({
            "id": f"in_s_{uuid.uuid4().hex[:8]}", "subscription": sub_id,
            "amount_due": 0, "currency": "usd", "attempt_count": 1,
        })

        attempts = sdb.table('payment_attempts').select('status').eq('clinic_id', CLINIC_ID).execute().data
        statuses = sorted([a['status'] for a in attempts])
        assert statuses == ['failed', 'succeeded']

        c = sdb.table('clinics').select('stripe_subscription_status,is_payment_blocked,payment_grace_until').eq('id', CLINIC_ID).single().execute().data
        assert c['stripe_subscription_status'] == 'active'
        assert c['is_payment_blocked'] is False
        assert c['payment_grace_until'] is None


# =============================================================================
# API endpoints
# =============================================================================

class TestEndpoints:
    def test_payment_status_enriched_with_retry_info(self, sdb, cm_headers, restore_clinic):
        """GET /api/billing/payment-status includes last_attempt_count, failure_message, next_retry_at."""
        from routes.billing import _apply_payment_failure
        sub_id = f"sub_status_{uuid.uuid4().hex[:8]}"
        sdb.table('clinics').update({
            "stripe_subscription_id": sub_id,
            "is_courtesy": False,
        }).eq('id', CLINIC_ID).execute()
        _apply_payment_failure({
            "id": f"in_{uuid.uuid4().hex[:8]}", "subscription": sub_id,
            "attempt_count": 3,
            "next_payment_attempt": int((datetime.now(timezone.utc) + timedelta(days=4)).timestamp()),
            "amount_due": 29900, "currency": "usd",
            "last_payment_error": {"code": "card_declined", "message": "Your card was declined."},
        })

        r = requests.get(f"{BASE}/billing/payment-status", headers=cm_headers, timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d['last_attempt_count'] == 3
        assert d['last_failure_message'] == 'Your card was declined.'
        assert d['next_retry_at'] is not None

    def test_my_payment_attempts(self, sdb, cm_headers, restore_clinic):
        """GET /api/billing/payment-attempts returns the clinic's history."""
        from routes.billing import _apply_payment_failure, _apply_payment_success
        sub_id = f"sub_hist_{uuid.uuid4().hex[:8]}"
        sdb.table('clinics').update({"stripe_subscription_id": sub_id, "is_courtesy": False}).eq('id', CLINIC_ID).execute()
        _apply_payment_failure({
            "id": f"in_h1_{uuid.uuid4().hex[:8]}", "subscription": sub_id,
            "attempt_count": 1, "amount_due": 9900, "currency": "usd",
            "next_payment_attempt": int((datetime.now(timezone.utc) + timedelta(days=3)).timestamp()),
        })
        _apply_payment_success({
            "id": f"in_h2_{uuid.uuid4().hex[:8]}", "subscription": sub_id,
            "amount_due": 0, "currency": "usd", "attempt_count": 1,
        })

        r = requests.get(f"{BASE}/billing/payment-attempts", headers=cm_headers, timeout=10)
        assert r.status_code == 200
        attempts = r.json()['attempts']
        assert len(attempts) == 2
        # Most recent first
        assert attempts[0]['status'] in ('failed', 'succeeded')

    def test_admin_retry_dashboard(self, sdb, sa_headers, restore_clinic):
        """GET /api/admin/billing/retry-dashboard surfaces clinics in dunning."""
        from routes.billing import _apply_payment_failure
        sub_id = f"sub_dash_{uuid.uuid4().hex[:8]}"
        sdb.table('clinics').update({"stripe_subscription_id": sub_id, "is_courtesy": False}).eq('id', CLINIC_ID).execute()
        _apply_payment_failure({
            "id": f"in_d_{uuid.uuid4().hex[:8]}", "subscription": sub_id,
            "attempt_count": 2, "amount_due": 29900, "currency": "usd",
            "next_payment_attempt": int((datetime.now(timezone.utc) + timedelta(days=4)).timestamp()),
            "last_payment_error": {"code": "card_declined", "message": "Declined"},
        })

        r = requests.get(f"{BASE}/admin/billing/retry-dashboard", headers=sa_headers, timeout=10)
        assert r.status_code == 200
        d = r.json()
        clinic_rows = [c for c in d['clinics'] if c['clinic_id'] == CLINIC_ID]
        assert len(clinic_rows) == 1
        row = clinic_rows[0]
        assert row['stripe_status'] == 'past_due'
        assert row['last_attempt_count'] == 2
        assert row['last_failure_message'] == 'Declined'
        assert row['next_retry_at'] is not None
        assert d['summary']['clinics_in_retry'] >= 1

    def test_admin_payment_attempts_list(self, sdb, sa_headers, restore_clinic):
        """GET /api/admin/billing/payment-attempts filtered by clinic + status."""
        from routes.billing import _apply_payment_failure
        sub_id = f"sub_adm_{uuid.uuid4().hex[:8]}"
        sdb.table('clinics').update({"stripe_subscription_id": sub_id, "is_courtesy": False}).eq('id', CLINIC_ID).execute()
        _apply_payment_failure({
            "id": f"in_a_{uuid.uuid4().hex[:8]}", "subscription": sub_id,
            "attempt_count": 1, "amount_due": 9900, "currency": "usd",
            "next_payment_attempt": int((datetime.now(timezone.utc) + timedelta(days=5)).timestamp()),
        })

        r = requests.get(f"{BASE}/admin/billing/payment-attempts?clinic_id={CLINIC_ID}&status=failed", headers=sa_headers, timeout=10)
        assert r.status_code == 200
        attempts = r.json()['attempts']
        assert len(attempts) >= 1
        assert all(a['status'] == 'failed' for a in attempts)
        assert attempts[0]['clinic_name'] == 'Clinica la salud'
