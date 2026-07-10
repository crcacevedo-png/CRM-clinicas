"""Password policy validator — NIST SP 800-63B aligned (balanced tier).

Rules enforced (all must pass):
  1. Length >= 10 characters.
  2. At least 3 of 4 categories: uppercase, lowercase, digit, symbol.
  3. Does not contain the user's email local-part (case-insensitive).
  4. Does not contain any word from the user's name >= 4 chars (case-insensitive).
  5. Not in the built-in top-1000 common-password blocklist.
  6. Not in the HaveIBeenPwned breach corpus (k-anonymity API — sends only the
     first 5 chars of the SHA-1 hash, never the full password). NETWORK-OPTIONAL:
     if HIBP is down or the request times out the check is skipped (fail-open by
     design so that we never block a legit user because of a 3rd-party outage).

Usage:
    from services.password_policy import validate_password
    validate_password(new_pw, email=user_email, name="Juan Perez")
    # raises HTTPException(400, detail="Password does not meet ...") on fail

The policy is intentionally applied ONLY at password-set time (registration,
invite, reset). Existing users with legacy weak passwords keep working until
they change theirs.
"""
from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)

MIN_LENGTH = 10
MIN_CATEGORIES = 3  # of 4 (upper, lower, digit, symbol)
HIBP_TIMEOUT_SEC = 2.5
HIBP_URL = "https://api.pwnedpasswords.com/range/{prefix}"

# Common-password blocklist loaded lazily from disk.
_COMMON_PASSWORDS: set[str] | None = None
_BLOCKLIST_PATH = Path(__file__).parent / "common_passwords.txt"


def _load_common() -> set[str]:
    global _COMMON_PASSWORDS
    if _COMMON_PASSWORDS is not None:
        return _COMMON_PASSWORDS
    try:
        raw = _BLOCKLIST_PATH.read_text(encoding='utf-8', errors='ignore')
        _COMMON_PASSWORDS = {ln.strip().lower() for ln in raw.splitlines() if ln.strip()}
    except FileNotFoundError:
        logger.warning("common_passwords.txt not found — blocklist check disabled")
        _COMMON_PASSWORDS = set()
    return _COMMON_PASSWORDS


def _category_count(pw: str) -> int:
    cats = 0
    if any(c.isupper() for c in pw): cats += 1
    if any(c.islower() for c in pw): cats += 1
    if any(c.isdigit() for c in pw): cats += 1
    if any(not c.isalnum() for c in pw): cats += 1
    return cats


def _contains_personal(pw: str, email: str | None, name: str | None) -> str | None:
    """Return the personal token found inside the password (case-insensitive), if any."""
    pw_low = pw.lower()
    if email:
        local = email.split('@', 1)[0].lower()
        if len(local) >= 4 and local in pw_low:
            return local
    if name:
        # split by whitespace and punctuation, drop <4 char tokens
        for token in re.split(r"[^\w]+", name.lower()):
            if len(token) >= 4 and token in pw_low:
                return token
    return None


def _hibp_pwned(pw: str) -> bool:
    """Query HIBP k-anonymity API. Returns True if the pw is in a breach.

    Fail-open: any exception (network, timeout, DNS) → returns False. We never
    block a user because HIBP is unavailable.
    """
    try:
        sha1 = hashlib.sha1(pw.encode('utf-8')).hexdigest().upper()
        prefix, suffix = sha1[:5], sha1[5:]
        r = httpx.get(HIBP_URL.format(prefix=prefix), timeout=HIBP_TIMEOUT_SEC,
                      headers={"Add-Padding": "true", "User-Agent": "cortexia-medical/1.0"})
        if r.status_code != 200:
            return False
        for line in r.text.splitlines():
            hash_suffix, _, count = line.partition(':')
            if hash_suffix.strip().upper() == suffix:
                try:
                    return int(count.strip()) > 0
                except ValueError:
                    return True
        return False
    except Exception as e:
        logger.info(f"HIBP check skipped: {e}")
        return False


def validate_password(pw: str, *, email: str | None = None, name: str | None = None,
                      check_hibp: bool = True) -> None:
    """Enforce the password policy. Raises HTTPException(400) on failure."""
    if not isinstance(pw, str):
        raise HTTPException(status_code=400, detail="Contraseña inválida")
    pw = pw.strip()

    if len(pw) < MIN_LENGTH:
        raise HTTPException(status_code=400, detail=f"La contraseña debe tener al menos {MIN_LENGTH} caracteres")

    cats = _category_count(pw)
    if cats < MIN_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail="Debe incluir al menos 3 de: mayúscula, minúscula, número y símbolo",
        )

    token = _contains_personal(pw, email, name)
    if token:
        raise HTTPException(
            status_code=400,
            detail="La contraseña no debe contener su nombre o email",
        )

    common = _load_common()
    if pw.lower() in common:
        raise HTTPException(
            status_code=400,
            detail="Esta contraseña es demasiado común. Elija una menos predecible",
        )

    if check_hibp and _hibp_pwned(pw):
        raise HTTPException(
            status_code=400,
            detail="Esta contraseña apareció en filtraciones públicas conocidas. Elija otra",
        )


def score_password(pw: str) -> dict:
    """Return an informational score for the frontend meter (no side effects).

    - strength: 0..4 (weak..very-strong)
    - checks: dict of individual booleans for UI hinting
    - message: short human-readable status
    """
    checks = {
        "length": len(pw) >= MIN_LENGTH,
        "categories": _category_count(pw) >= MIN_CATEGORIES,
        "not_common": pw.lower() not in _load_common() if pw else False,
    }
    passed = sum(1 for v in checks.values() if v)
    length_bonus = min(2, max(0, (len(pw) - MIN_LENGTH) // 4))
    strength = min(4, passed + length_bonus)
    msg = ["Muy débil", "Débil", "Aceptable", "Fuerte", "Muy fuerte"][strength]
    return {"strength": strength, "checks": checks, "message": msg,
            "min_length": MIN_LENGTH, "min_categories": MIN_CATEGORIES}
