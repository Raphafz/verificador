"""Lockout progressivo para tentativas MFA (brute force TOTP)."""
from __future__ import annotations

import logging
import os

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger("security")

MFA_LOCKOUT_THRESHOLDS = (5, 8, 12)
MFA_LOCKOUT_DURATIONS_SEC = (300, 900, 1800)


def _enabled() -> bool:
    from django.conf import settings

    force = os.getenv("FORCE_RATE_LIMIT", "").lower() in ("1", "true", "yes", "on")
    if force:
        return True
    return not getattr(settings, "DEBUG", True)


def _key(user_id: int, ip: str) -> str:
    return f"mfa_fail:{user_id}:{ip}"


def is_mfa_locked(user_id: int, ip: str) -> tuple[bool, int]:
    if not _enabled():
        return False, 0
    data = cache.get(_key(user_id, ip), {})
    until = float(data.get("locked_until", 0) or 0)
    now = timezone.now().timestamp()
    if until and now < until:
        return True, int(until - now)
    return False, 0


def record_mfa_failure(user_id: int, ip: str) -> int:
    if not _enabled():
        return 0
    key = _key(user_id, ip)
    data = cache.get(key, {"count": 0, "locked_until": 0})
    data["count"] = int(data.get("count", 0)) + 1
    lock_sec = 0
    for threshold, duration in zip(MFA_LOCKOUT_THRESHOLDS, MFA_LOCKOUT_DURATIONS_SEC):
        if data["count"] >= threshold:
            lock_sec = duration
    if lock_sec:
        data["locked_until"] = timezone.now().timestamp() + lock_sec
        logger.warning(
            "MFA lockout",
            extra={"user_id": user_id, "ip": ip, "failures": data["count"], "lock_sec": lock_sec},
        )
    cache.set(key, data, max(lock_sec, 3600))
    return lock_sec


def clear_mfa_failures(user_id: int, ip: str) -> None:
    if not _enabled():
        return
    cache.delete(_key(user_id, ip))
