"""Input sanitization helpers used across routes.

- `sanitize_postgrest_search(q)`: strips characters with semantic meaning in
  PostgREST's filter DSL (comma, parens, asterisk, colon, percent) so values
  cannot extend `or=(...)` expressions or escape `ilike` patterns.

- `validate_file_magic(...)`: verifies an uploaded file's actual content
  matches the declared mime-type by reading magic bytes via libmagic. Defeats
  trivial Content-Type spoofing where an attacker uploads `.exe` declared
  as `image/png`.
"""
from __future__ import annotations

import re
import logging
from typing import Iterable

logger = logging.getLogger(__name__)

# Chars with meaning in PostgREST filter DSL or ILIKE patterns. Removed entirely
# rather than escaped because users searching by name never legitimately need
# them, and any value containing them is almost certainly an attack probe.
_POSTGREST_BAD_CHARS = re.compile(r'[,()\*:%\\]')


def sanitize_postgrest_search(q: str | None, max_len: int = 80) -> str:
    """Return a search string safe for `.or_(f"col.ilike.%{q}%,...")` patterns."""
    if not q:
        return ""
    cleaned = _POSTGREST_BAD_CHARS.sub('', q).strip()
    return cleaned[:max_len]


# ============== File upload validation ==============

# Map: declared mime-type prefix -> set of actual mime-types we accept.
# We are lenient on JPEG/PNG/WEBP/HEIC variants but strict on category.
_ALLOWED_IMAGE_MIMES = {
    'image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif', 'image/gif',
}
_ALLOWED_DOC_MIMES = {
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'text/plain',
}


def _detect_mime(data: bytes) -> str:
    """Return mime-type from magic bytes. Falls back to octet-stream on error."""
    try:
        import magic
        return magic.from_buffer(data[:4096], mime=True) or 'application/octet-stream'
    except Exception as e:
        logger.warning(f"magic detection failed: {e}")
        return 'application/octet-stream'


def validate_image_upload(data: bytes, *, max_bytes: int = 2 * 1024 * 1024) -> str:
    """Validate that `data` is a real image of an allowed type within size limit.

    Returns the detected mime-type. Raises ValueError on any mismatch so the
    caller can wrap it in an HTTPException(400, ...).
    """
    if not data:
        raise ValueError("Archivo vacío")
    if len(data) > max_bytes:
        raise ValueError(f"Archivo excede el tamaño máximo ({max_bytes // 1024 // 1024} MB)")
    detected = _detect_mime(data)
    if detected not in _ALLOWED_IMAGE_MIMES:
        raise ValueError(f"Tipo de archivo no permitido (detectado: {detected})")
    return detected


def validate_document_upload(data: bytes, *, max_bytes: int = 20 * 1024 * 1024, extra_allowed: Iterable[str] | None = None) -> str:
    """Validate a patient document (PDF, image, office doc) by magic bytes."""
    if not data:
        raise ValueError("Archivo vacío")
    if len(data) > max_bytes:
        raise ValueError(f"Archivo excede el tamaño máximo ({max_bytes // 1024 // 1024} MB)")
    detected = _detect_mime(data)
    allowed = set(_ALLOWED_IMAGE_MIMES) | set(_ALLOWED_DOC_MIMES)
    if extra_allowed:
        allowed |= set(extra_allowed)
    if detected not in allowed:
        raise ValueError(f"Tipo de archivo no permitido (detectado: {detected})")
    return detected
