"""Permissões DRF com escopo de tenant e proteção object-level."""
from rest_framework.permissions import BasePermission, SAFE_METHODS

from .mfa_service import is_mfa_verified, mfa_required_for
from .permissions import is_company_admin, is_rm_admin


class MfaVerifiedPermission(BasePermission):
    """
    Exige MFA verificado na sessão quando MFA_REQUIRED se aplica ao usuário.
    Complementa MfaEnforcementMiddleware (inclui /api/v1/).
    """

    message = "Autenticação em dois fatores necessária."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return True
        if not mfa_required_for(user):
            return True
        return is_mfa_verified(request)


class RequireMfaVerified(BasePermission):
    """
    Bloqueia endpoints sensíveis quando MFA é obrigatório e o claim JWT
    `mfa_verified` ainda é false (ou sessão Django sem MFA verificado).
    """

    message = "Autenticação em dois fatores necessária."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return True
        if not mfa_required_for(user):
            return True
        auth = getattr(request, "auth", None)
        if auth is not None:
            from core.jwt_tokens import claim_mfa_verified

            return claim_mfa_verified(auth)
        return is_mfa_verified(request)


# Alias legado (Fase 0 inicial)
JwtMfaVerifiedPermission = RequireMfaVerified


def _user_company_id(user):
    return getattr(user, "company_id", None)


class IsCompanyAdminOrRM(BasePermission):
    """Leitura/escrita administrativa — COMPANY_USER não acessa."""

    message = "Acesso restrito a administradores."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return is_rm_admin(user) or is_company_admin(user)


class TenantScopedPermission(BasePermission):
    """
    RM/superuser: acesso global.
    COMPANY_ADMIN: só objetos da própria empresa.
    COMPANY_USER: leitura na própria empresa (maps); escrita negada nas views.
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if is_rm_admin(user):
            return True
        if request.method in SAFE_METHODS:
            return _user_company_id(user) is not None
        return getattr(user, "is_company_admin", False)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if is_rm_admin(user):
            return True
        user_cid = _user_company_id(user)
        from core.models import Company

        if isinstance(obj, Company):
            return obj.pk == user_cid
        company_id = getattr(obj, "company_id", None)
        if company_id is None and hasattr(obj, "company"):
            company_id = getattr(obj.company, "pk", None)
        if company_id is None:
            return obj.pk == user.pk
        return company_id == user_cid
