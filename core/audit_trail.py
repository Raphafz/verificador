"""Trilha de auditoria persistente (LGPD + segurança)."""
from __future__ import annotations

import logging

from django.utils import timezone

from .log_sanitizer import sanitize_audit_details

audit_logger = logging.getLogger("audit")


def _client_ip(request) -> str | None:
    if not request:
        return None
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def record_security_event(
    event_type: str,
    *,
    user=None,
    request=None,
    details: dict | None = None,
    severity: str = "info",
) -> None:
    """Persiste evento + log estruturado."""
    safe_details = sanitize_audit_details(details or {})
    rid = getattr(request, "request_id", None) if request else None
    cid = getattr(request, "correlation_id", None) if request else None
    ip = _client_ip(request)

    audit_logger.info(
        event_type,
        extra={
            "event_type": event_type,
            "user_id": user.id if user else None,
            "ip": ip,
            "request_id": rid,
            "correlation_id": cid,
            "details": safe_details,
        },
    )

    try:
        from .models import SecurityAuditEvent
        SecurityAuditEvent.objects.create(
            event_type=event_type[:64],
            severity=severity[:16],
            user=user if user and getattr(user, "pk", None) else None,
            ip_address=ip,
            request_id=(rid or "")[:64],
            correlation_id=(cid or "")[:64],
            details=safe_details,
        )
    except Exception as exc:
        audit_logger.debug("Audit DB skip: %s", exc)


def revoke_user_sessions(user) -> int:
    """Remove todas as sessões Django do usuário."""
    from django.contrib.sessions.models import Session
    from django.contrib.auth import SESSION_KEY

    deleted = 0
    for session in Session.objects.iterator():
        try:
            data = session.get_decoded()
            if str(data.get(SESSION_KEY)) == str(user.pk):
                session.delete()
                deleted += 1
        except Exception:
            continue
    record_security_event(
        "sessions_revoked",
        user=user,
        details={"count": deleted},
        severity="warning",
    )
    return deleted
