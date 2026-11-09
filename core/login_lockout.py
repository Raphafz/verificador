"""
Lockout progressivo após falhas de login (brute force).
"""
from __future__ import annotations

import logging
import os

from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.utils import timezone

logger = logging.getLogger("security")

LOCKOUT_THRESHOLDS = (5, 10, 15)
LOCKOUT_DURATIONS_SEC = (300, 900, 3600)


def _enabled() -> bool:
    from django.conf import settings
    force = os.getenv("FORCE_RATE_LIMIT", "").lower() in ("1", "true", "yes", "on")
    if force:
        return True
    return not getattr(settings, "DEBUG", True)


def _ip(request) -> str:
    from core.request_ip import get_client_ip

    return get_client_ip(request)


def _key(username: str, ip: str) -> str:
    user = (username or "").strip().lower()[:128]
    return f"login_fail:{ip}:{user}"


def is_locked(request, username: str) -> tuple[bool, int]:
    """Retorna (bloqueado, segundos_restantes)."""
    if not _enabled():
        return False, 0
    data = cache.get(_key(username, _ip(request)), {})
    if not data:
        return False, 0
    until = data.get("locked_until", 0)
    now = timezone.now().timestamp()
    if until and now < until:
        return True, int(until - now)
    return False, 0


def record_failure(request, username: str) -> int:
    """Registra falha; retorna segundos de lockout se aplicável."""
    if not _enabled():
        return 0
    key = _key(username, _ip(request))
    data = cache.get(key, {"count": 0, "locked_until": 0})
    data["count"] = int(data.get("count", 0)) + 1
    count = data["count"]
    lock_sec = 0
    for threshold, duration in zip(LOCKOUT_THRESHOLDS, LOCKOUT_DURATIONS_SEC):
        if count >= threshold:
            lock_sec = duration
    if lock_sec:
        data["locked_until"] = timezone.now().timestamp() + lock_sec
        logger.warning(
            "Login lockout ativo",
            extra={"username": username[:32], "ip": _ip(request), "failures": count, "lock_sec": lock_sec},
        )
    cache.set(key, data, max(lock_sec, 3600))
    return lock_sec if data.get("locked_until") else 0


def clear_failures(request, username: str) -> None:
    if not _enabled():
        return
    cache.delete(_key(username, _ip(request)))


def lockout_response(request, retry_after: int):
    msg = f"Muitas tentativas. Aguarde {retry_after // 60 + 1} minuto(s)."
    if request.headers.get("Accept") == "application/json":
        return JsonResponse({"error": msg, "retry_after": retry_after}, status=429)
    return HttpResponse(msg, status=429)
