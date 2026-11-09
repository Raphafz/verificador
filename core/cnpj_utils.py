"""CNPJ — hash indexável, mascaramento e criptografia em repouso."""
from __future__ import annotations

import hashlib
import re

from django.conf import settings

_DIGITS_RE = re.compile(r"\D")


def cnpj_digits(value: str | None) -> str:
    if not value:
        return ""
    return _DIGITS_RE.sub("", str(value))


def format_cnpj(digits: str) -> str:
    d = cnpj_digits(digits)
    if len(d) != 14:
        return digits
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"


def hash_cnpj(value: str | None) -> str:
    """SHA-256(salt + dígitos) — busca sem expor CNPJ."""
    digits = cnpj_digits(value)
    if len(digits) != 14:
        return ""
    salt = getattr(settings, "CNPJ_HASH_SALT", "") or getattr(settings, "SECRET_KEY", "")
    payload = f"{salt}|cnpj|{digits}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def mask_cnpj_display(value: str | None) -> str:
    """Exibição: **.***.**/****-XX (últimos 2 dígitos)."""
    d = cnpj_digits(value)
    if len(d) < 4:
        return "***"
    return f"**.***.***/****-{d[-2:]}"
