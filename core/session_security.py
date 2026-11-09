"""
Gestão de sessões enterprise: token de acesso, expiração, revogação e login em outro IP/dispositivo.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.sessions.models import Session
from django.utils import timezone

from core.audit_trail import record_security_event

logger = logging.getLogger("security")


def _client_ip(request) -> str:
    from core.request_ip import get_client_ip

    return _normalize_client_ip(get_client_ip(request))


def _normalize_client_ip(ip: str) -> str:
    """Evita falha no registro de sessão quando o IP não é detectável (proxy/túnel)."""
    import ipaddress

    candidate = (ip or "").strip() or "127.0.0.1"
    if candidate == "unknown":
        candidate = "127.0.0.1"
    try:
        ipaddress.ip_address(candidate)
        return candidate
    except ValueError:
        return "127.0.0.1"


def _user_agent(request) -> str:
    return (request.META.get("HTTP_USER_AGENT") or "")[:512]


def _session_cookie_age() -> int:
    return int(getattr(settings, "SESSION_COOKIE_AGE", 3600))


def _revoke_on_new_login() -> bool:
    return bool(getattr(settings, "SESSION_REVOKE_ON_NEW_LOGIN", True))


def _bind_ip() -> bool:
    return bool(getattr(settings, "SESSION_BIND_IP", True))


def _max_concurrent_sessions() -> int:
    if _revoke_on_new_login():
        return 1
    return int(getattr(settings, "SESSION_MAX_CONCURRENT", 3))


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _session_expires_at():
    return timezone.now() + timedelta(seconds=_session_cookie_age())


def login_redirect_url(request, reason: str) -> str:
    """URL de login com motivo de encerramento da sessão."""
    slug = request.session.get("_session_company_slug")
    if slug:
        return f"/{slug}/login/?session={reason}"
    base = getattr(settings, "LOGIN_URL", "/rm/login/")
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}session={reason}"


def issue_access_token() -> tuple[str, str, timezone.datetime]:
    """Retorna (token em claro para a sessão, digest para BD, expires_at)."""
    token = secrets.token_urlsafe(32)
    return token, _token_digest(token), _session_expires_at()


def register_session(request, user, *, access_token: str, expires_at) -> None:
    """Registra sessão ativa com token e aplica limite de concorrência."""
    from core.models import UserSessionRecord

    if not request.session.session_key:
        request.session.save()
    sk = request.session.session_key
    ip = _client_ip(request)
    ua = _user_agent(request)

    UserSessionRecord.objects.filter(user=user, session_key=sk).delete()
    UserSessionRecord.objects.create(
        user=user,
        session_key=sk,
        access_token_digest=_token_digest(access_token),
        ip_address=ip or None,
        user_agent=ua,
        is_current=True,
        expires_at=expires_at,
    )

    active = UserSessionRecord.objects.filter(user=user, revoked_at__isnull=True).order_by(
        "-last_seen_at"
    )
    excess = active.count() - _max_concurrent_sessions()
    if excess > 0:
        to_revoke = list(active.order_by("last_seen_at")[:excess])
        for old in to_revoke:
            if old.session_key != sk:
                revoke_session_record(old)


def touch_session(request, user) -> None:
    from core.models import UserSessionRecord

    sk = request.session.session_key
    if not sk:
        return
    UserSessionRecord.objects.filter(user=user, session_key=sk, revoked_at__isnull=True).update(
        last_seen_at=timezone.now()
    )


def rotate_session(request) -> None:
    """Rotaciona session key após login (mitiga session fixation)."""
    if request.session.session_key:
        request.session.cycle_key()


def revoke_session_record(record) -> None:
    try:
        Session.objects.filter(session_key=record.session_key).delete()
    except Exception:
        pass
    record.revoked_at = timezone.now()
    record.is_current = False
    record.save(update_fields=["revoked_at", "is_current"])


def revoke_all_sessions(user, *, except_session_key: str | None = None) -> int:
    from core.models import UserSessionRecord

    qs = UserSessionRecord.objects.filter(user=user, revoked_at__isnull=True)
    if except_session_key:
        qs = qs.exclude(session_key=except_session_key)
    count = 0
    for rec in qs:
        revoke_session_record(rec)
        count += 1
    return count


def check_suspicious_login(request, user) -> bool:
    """
    Detecta IP/UA diferentes do último login bem-sucedido.
    Retorna True se suspeito.
    """
    from core.models import UserSessionRecord

    ip = _client_ip(request)
    ua = _user_agent(request)
    last = (
        UserSessionRecord.objects.filter(user=user, revoked_at__isnull=True)
        .exclude(session_key=request.session.session_key or "")
        .order_by("-last_seen_at")
        .first()
    )
    if not last:
        return False
    suspicious = False
    if last.ip_address and ip and last.ip_address != ip:
        suspicious = True
    if last.user_agent and ua and last.user_agent[:80] != ua[:80]:
        suspicious = True
    if suspicious:
        request.session["login_suspicious"] = True
        record_security_event(
            "suspicious_login",
            user=user,
            request=request,
            details={"ip": ip, "previous_ip": last.ip_address},
            severity="warning",
        )
    return suspicious


def validate_active_session(request, user) -> tuple[bool, str]:
    """
    Valida token de acesso, expiração, revogação e IP vinculado.
    Retorna (invalido, motivo) — motivo: replaced | expired | invalid | ip_changed
    """
    from core.models import UserSessionRecord

    sk = request.session.session_key
    if not sk:
        return True, "invalid"

    now = timezone.now()
    exp_raw = request.session.get("_session_expires_at")
    if exp_raw:
        try:
            exp_dt = datetime.fromisoformat(exp_raw)
            if timezone.is_naive(exp_dt):
                exp_dt = timezone.make_aware(exp_dt, timezone.get_current_timezone())
            if now > exp_dt:
                return True, "expired"
        except (TypeError, ValueError):
            return True, "invalid"

    rec = (
        UserSessionRecord.objects.filter(
            user=user,
            session_key=sk,
            revoked_at__isnull=True,
        )
        .first()
    )
    if not rec:
        return True, "replaced"

    if rec.expires_at and now > rec.expires_at:
        revoke_session_record(rec)
        return True, "expired"

    token = request.session.get("_access_token") or ""
    if not token or not rec.access_token_digest:
        return True, "invalid"
    if rec.access_token_digest != _token_digest(token):
        return True, "invalid"

    if _bind_ip():
        current_ip = _client_ip(request)
        bound_ip = request.session.get("_session_ip") or rec.ip_address
        if bound_ip and current_ip and bound_ip != current_ip:
            revoke_session_record(rec)
            record_security_event(
                "session_ip_mismatch",
                user=user,
                request=request,
                details={"bound_ip": bound_ip, "current_ip": current_ip},
                severity="warning",
            )
            return True, "ip_changed"

    return False, ""


def on_login_success(request, user) -> None:
    """Chamar após login() bem-sucedido (via signal user_logged_in)."""
    rotate_session(request)

    revoked_count = 0
    if _revoke_on_new_login():
        revoked_count = revoke_all_sessions(user)
        if revoked_count:
            record_security_event(
                "sessions_revoked_on_login",
                user=user,
                request=request,
                details={
                    "revoked_count": revoked_count,
                    "ip": _client_ip(request),
                    "reason": "new_login_other_device_or_ip",
                },
                severity="info",
            )

    check_suspicious_login(request, user)

    access_token, _digest, expires_at = issue_access_token()
    register_session(request, user, access_token=access_token, expires_at=expires_at)

    request.session["_access_token"] = access_token
    request.session["_session_ip"] = _client_ip(request)
    request.session["_session_expires_at"] = expires_at.isoformat()
    request.session["_session_registered"] = True
    request.session["_last_activity_ts"] = __import__("time").time()
    request.session["auth_user_id"] = user.pk
    if getattr(user, "company", None) and user.company_id:
        request.session["_session_company_slug"] = user.company.slug


def on_logout(request, user) -> None:
    """Revoga registro da sessão atual ao sair."""
    from core.models import UserSessionRecord

    sk = request.session.session_key
    if not sk:
        return
    rec = UserSessionRecord.objects.filter(
        user=user,
        session_key=sk,
        revoked_at__isnull=True,
    ).first()
    if rec:
        revoke_session_record(rec)
