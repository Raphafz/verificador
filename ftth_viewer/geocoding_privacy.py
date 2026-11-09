"""
Cache de geocoding com minimização LGPD: chave SHA-256 com salt, sem endereço reversível.
"""
from __future__ import annotations

import hashlib
import re
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

COORD_CACHE_KEY_RE = re.compile(r"^-?\d+\.\d+,-?\d+\.\d+$")


def get_cache_salt() -> str:
    explicit = getattr(settings, "GEOCODING_CACHE_SALT", "") or ""
    if explicit.strip():
        return explicit.strip()
    return getattr(settings, "SECRET_KEY", "dev-geocoding-salt-change-me")


def get_ttl_hours() -> int:
    return int(getattr(settings, "GEOCODING_CACHE_TTL_HOURS", 24))


def get_retention_days() -> int:
    return int(getattr(settings, "CACHE_RETENTION_DAYS", 90))


def compute_expires_at(from_dt=None):
    base = from_dt or timezone.now()
    return base + timedelta(hours=get_ttl_hours())


def is_coord_cache_key(value: str) -> bool:
    return bool(value and COORD_CACHE_KEY_RE.match(str(value).strip()))


def hash_cache_key(raw_query: str, *, query_type: str | None = None) -> str:
    """
    Gera SHA-256(salt + tipo + consulta normalizada). Irreversível.
    """
    raw = (raw_query or "").strip()
    if not raw:
        raise ValueError("Consulta de cache vazia")

    qtype = query_type
    if qtype is None:
        qtype = "reverse" if is_coord_cache_key(raw) else "address"

    if qtype == "reverse":
        parts = raw.split(",")
        lat = round(float(parts[0]), 6)
        lon = round(float(parts[1]), 6)
        normalized = f"{lat:.6f},{lon:.6f}"
    else:
        from .utils import normalize_address

        normalized = normalize_address(raw)

    payload = f"{get_cache_salt()}|{qtype}|{normalized}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def anonymize_display_name(full_address: str) -> str:
    """
    Mantém apenas região aproximada (cidade/UF/país) — sem logradouro/número.
    """
    if not full_address:
        return ""

    parts = [p.strip() for p in full_address.split(",") if p.strip()]
    if not parts:
        return ""

    if len(parts) <= 2:
        return ", ".join(parts)

    region = parts[-3:]
    lowered = " ".join(region).lower()
    if "brasil" not in lowered and "brazil" not in lowered:
        region.append("Brasil")

    return ", ".join(region[:4])


def cache_key_for_query(query: str) -> tuple[str, str]:
    """Retorna (cache_key_hash, query_type)."""
    qtype = "reverse" if is_coord_cache_key(query) else "address"
    return hash_cache_key(query, query_type=qtype), qtype
