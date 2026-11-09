"""
Ativação de conta por link único — token opaco, hash SHA-256 em repouso, uso único, 30 min.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from .log_sanitizer import mask_email
from .models import AccountActivationToken, CustomUser

logger = logging.getLogger("security")

ACTIVATION_TOKEN_BYTES = 48
ACTIVATION_EXPIRY_MINUTES = int(getattr(settings, "ACCOUNT_ACTIVATION_EXPIRY_MINUTES", 30))


class AccountActivationTokenGenerator(PasswordResetTokenGenerator):
    """Gerador auxiliar (padrão Django) — invalida se a senha mudar após emissão."""

    timeout = ACTIVATION_EXPIRY_MINUTES * 60


activation_token_generator = AccountActivationTokenGenerator()


def _digest(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _client_ip(request) -> str | None:
    if request is None:
        return None
    from core.request_ip import get_client_ip

    return get_client_ip(request)


@transaction.atomic
def create_activation_token(user: CustomUser, request=None) -> str:
    """
    Gera token opaco. Invalida tokens ativos anteriores do mesmo usuário.
    """
    AccountActivationToken.objects.filter(user=user, used_at__isnull=True).update(
        used_at=timezone.now()
    )

    raw_token = secrets.token_urlsafe(ACTIVATION_TOKEN_BYTES)
    digest = _digest(raw_token)
    expires_at = timezone.now() + timedelta(minutes=ACTIVATION_EXPIRY_MINUTES)

    AccountActivationToken.objects.create(
        user=user,
        token_digest=digest,
        django_token=activation_token_generator.make_token(user),
        expires_at=expires_at,
        created_ip=_client_ip(request),
    )

    logger.info(
        "Token de ativação criado",
        extra={
            "user_id": user.id,
            "expires_at": expires_at.isoformat(),
            "email_masked": mask_email(user.email),
        },
    )
    return raw_token


def build_activation_url(request, raw_token: str) -> str:
    path = reverse("account_activate", kwargs={"token": raw_token})
    if request:
        protocol = "https" if request.is_secure() else "http"
        return f"{protocol}://{request.get_host()}{path}"
    domain = getattr(settings, "SITE_DOMAIN", "rmsys.app")
    return f"https://{domain}{path}"


def get_user_for_activation_token(raw_token: str) -> tuple[CustomUser | None, AccountActivationToken | None]:
    """Valida token sem consumir."""
    if not raw_token or len(raw_token) < 32:
        return None, None

    digest = _digest(raw_token)
    try:
        record = AccountActivationToken.objects.select_related("user").get(
            token_digest=digest,
            used_at__isnull=True,
        )
    except AccountActivationToken.DoesNotExist:
        logger.warning("Ativação: token inexistente ou já utilizado")
        return None, None

    if record.is_expired:
        logger.warning(
            "Ativação: token expirado",
            extra={"user_id": record.user_id, "token_id": record.pk},
        )
        return None, record

    user = record.user
    if not user.is_active:
        return None, record

    if record.django_token and not activation_token_generator.check_token(
        user, record.django_token
    ):
        logger.warning(
            "Ativação: token Django inválido (senha alterada ou expirado)",
            extra={"user_id": user.id},
        )
        return None, record

    return user, record


@transaction.atomic
def consume_activation_token(raw_token: str, request=None) -> CustomUser | None:
    """Marca token como usado após senha definida."""
    user, record = get_user_for_activation_token(raw_token)
    if not user or not record:
        return None

    updated = AccountActivationToken.objects.filter(
        pk=record.pk,
        used_at__isnull=True,
        expires_at__gt=timezone.now(),
    ).update(used_at=timezone.now(), used_ip=_client_ip(request))

    if not updated:
        return None

    logger.info(
        "Conta ativada via token",
        extra={"user_id": user.id, "email_masked": mask_email(user.email)},
    )
    return user


def purge_expired_activation_tokens() -> int:
    """Remove tokens expirados ou usados há mais de 7 dias."""
    cutoff = timezone.now() - timedelta(days=7)
    deleted, _ = AccountActivationToken.objects.filter(
        Q(used_at__isnull=False, used_at__lt=cutoff) | Q(expires_at__lt=cutoff)
    ).delete()
    return deleted
