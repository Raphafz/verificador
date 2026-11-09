"""JWT customizado — claims de tenant, role e MFA."""
from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken, Token


class MfaPendingToken(Token):
    """Token curto só para POST /api/v1/auth/mfa/verify/."""

    token_type = "mfa_pending"
    lifetime = timedelta(minutes=5)


def _apply_user_claims(token: Token, user, *, mfa_verified: bool) -> Token:
    company = user.company if user.company_id else None
    enabled_modules = company.enabled_modules() if company else []
    token["user_id"] = user.pk
    token["username"] = user.username
    token["role"] = getattr(user, "role", "")
    token["is_rm_admin"] = bool(getattr(user, "is_rm_admin", False))
    token["is_company_admin"] = bool(getattr(user, "is_company_admin", False))
    token["company_id"] = user.company_id
    token["company_slug"] = company.slug if company else None
    token["plan_code"] = company.plan_code if company else None
    token["enabled_modules"] = enabled_modules
    token["mfa_verified"] = bool(mfa_verified)
    token["must_change_password"] = bool(getattr(user, "must_change_password", False))
    return token


def issue_token_pair(user, *, mfa_verified: bool) -> dict:
    refresh = RefreshToken.for_user(user)
    _apply_user_claims(refresh, user, mfa_verified=mfa_verified)
    _apply_user_claims(refresh.access_token, user, mfa_verified=mfa_verified)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


def issue_mfa_pending_token(user) -> str:
    token = MfaPendingToken()
    _apply_user_claims(token, user, mfa_verified=False)
    return str(token)


def claim_mfa_verified(token_payload) -> bool:
    if not token_payload:
        return False
    if isinstance(token_payload, dict):
        return bool(token_payload.get("mfa_verified"))
    return bool(getattr(token_payload, "mfa_verified", False))


def get_access_lifetime():
    return getattr(settings, "SIMPLE_JWT", {}).get("ACCESS_TOKEN_LIFETIME", timedelta(minutes=15))


def get_refresh_lifetime():
    return getattr(settings, "SIMPLE_JWT", {}).get("REFRESH_TOKEN_LIFETIME", timedelta(days=7))
