"""MFA TOTP — setup, verificação, backup codes, remember device."""
from __future__ import annotations

import base64
import hashlib
import io
import secrets
from typing import Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone

User = get_user_model()

REMEMBER_COOKIE = "mfa_trust"
REMEMBER_DAYS = int(getattr(settings, "MFA_REMEMBER_DAYS", 30))


def mfa_required_for(user) -> bool:
    if not getattr(settings, "MFA_REQUIRED", False):
        return False
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or getattr(user, "is_rm_admin", False) or user.is_staff:
        return True
    if getattr(user, "role", None) == "RM":
        return True
    if getattr(settings, "MFA_REQUIRED_COMPANY_ADMINS", False):
        return getattr(user, "role", None) in ("COMPANY_ADMIN", "COMPANY_USER")
    return False


def _digest_token(raw: str) -> str:
    import hashlib
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _device_label(request) -> str:
    ua = (request.META.get("HTTP_USER_AGENT") or "")[:120]
    return ua or "Dispositivo desconhecido"


def get_totp_device(user):
    from django_otp.plugins.otp_totp.models import TOTPDevice

    return TOTPDevice.objects.filter(user=user, confirmed=True).first()


def has_mfa_enabled(user) -> bool:
    return get_totp_device(user) is not None


def create_totp_device(user, name: str = "default"):
    from django_otp.plugins.otp_totp.models import TOTPDevice

    TOTPDevice.objects.filter(user=user, confirmed=False).delete()
    return TOTPDevice.objects.create(user=user, name=name, confirmed=False)


def provisioning_uri(device) -> str:
    return device.config_url


def qr_png_base64(uri: str) -> str:
    try:
        import qrcode
        buf = io.BytesIO()
        qrcode.make(uri).save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except ImportError:
        return ""


def verify_token(user, token: str) -> bool:
    device = get_totp_device(user)
    if not device:
        unconfirmed = None
        from django_otp.plugins.otp_totp.models import TOTPDevice
        unconfirmed = TOTPDevice.objects.filter(user=user, confirmed=False).first()
        if unconfirmed and unconfirmed.verify_token(token.strip()):
            unconfirmed.confirmed = True
            unconfirmed.save(update_fields=["confirmed"])
            return True
        return False
    return device.verify_token(token.strip())


def generate_backup_codes(user, count: int = 10) -> list[str]:
    from django_otp.plugins.otp_static.models import StaticDevice, StaticToken

    StaticDevice.objects.filter(user=user, name="backup").delete()
    device = StaticDevice.objects.create(user=user, name="backup")
    codes = []
    for _ in range(count):
        code = secrets.token_hex(4).upper()
        StaticToken.objects.create(device=device, token=code)
        codes.append(code)
    return codes


def verify_backup_code(user, code: str) -> bool:
    from django_otp.plugins.otp_static.models import StaticDevice

    device = StaticDevice.objects.filter(user=user, name="backup").first()
    if not device:
        return False
    normalized = code.strip().replace("-", "").upper()
    return device.verify_token(normalized)


def set_remember_device(request, user) -> str:
    from datetime import timedelta

    from core.models import TrustedDevice

    raw = secrets.token_urlsafe(32)
    digest = _digest_token(raw)
    expires = timezone.now() + timedelta(days=REMEMBER_DAYS)
    from core.request_ip import get_client_ip

    ip = get_client_ip(request)
    TrustedDevice.objects.create(
        user=user,
        token_digest=digest,
        device_label=_device_label(request),
        ip_address=ip or None,
        expires_at=expires,
    )
    cache.set(f"mfa_remember:{user.id}:{digest}", "1", REMEMBER_DAYS * 86400)
    request.session["mfa_remember_digest"] = digest
    secure = getattr(settings, "SESSION_COOKIE_SECURE", False)
    return raw


def is_device_remembered(request, user) -> bool:
    from core.models import TrustedDevice

    raw = request.COOKIES.get(REMEMBER_COOKIE) or request.session.get("mfa_remember_digest")
    if not raw:
        return False
    digest = _digest_token(raw) if len(raw) != 64 else raw
    dev = (
        TrustedDevice.objects.filter(
            user=user,
            token_digest=digest,
            revoked_at__isnull=True,
            expires_at__gte=timezone.now(),
        )
        .first()
    )
    if dev:
        dev.last_used_at = timezone.now()
        dev.save(update_fields=["last_used_at"])
        return True
    return bool(cache.get(f"mfa_remember:{user.id}:{digest}"))


def list_trusted_devices(user):
    from core.models import TrustedDevice

    return TrustedDevice.objects.filter(user=user, revoked_at__isnull=True).order_by("-last_used_at")


def revoke_trusted_device(user, device_id: int) -> bool:
    from core.models import TrustedDevice

    updated = TrustedDevice.objects.filter(user=user, pk=device_id, revoked_at__isnull=True).update(
        revoked_at=timezone.now()
    )
    return updated > 0


def revoke_all_trusted_devices(user) -> int:
    from core.models import TrustedDevice

    return TrustedDevice.objects.filter(user=user, revoked_at__isnull=True).update(
        revoked_at=timezone.now()
    )


def mark_mfa_verified(request) -> None:
    request.session["mfa_verified_at"] = timezone.now().isoformat()


def is_mfa_verified(request) -> bool:
    if not request.user.is_authenticated:
        return False
    if is_device_remembered(request, request.user):
        return True
    try:
        from django_otp import user_has_device
        if not user_has_device(request.user):
            return not mfa_required_for(request.user)
    except Exception:
        pass
    if getattr(request.user, "is_verified", lambda: False)():
        return True
    return bool(request.session.get("mfa_verified_at"))
