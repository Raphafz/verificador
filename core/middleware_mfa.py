"""Exige MFA verificado para admins/RM quando MFA_REQUIRED=true."""
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin

from .mfa_service import has_mfa_enabled, is_mfa_verified, mfa_required_for


class MfaEnforcementMiddleware(MiddlewareMixin):
    EXEMPT_PREFIXES = (
        "/rm/login/",
        "/rm/logout/",
        "/rm/mfa/",
        "/rm/sessoes/",
        "/ativar-conta/",
        "/static/",
        "/media/",
        "/admin/login/",
        "/consent-required/",
        "/health/",
        "/ready/",
        "/api/v1/auth/",
    )

    def process_request(self, request):
        user = request.user
        if not user.is_authenticated:
            return None
        if not mfa_required_for(user):
            return None
        path = request.path or ""
        if any(path.startswith(p) for p in self.EXEMPT_PREFIXES):
            return None
        if not has_mfa_enabled(user) and not path.startswith("/rm/mfa/setup"):
            return redirect(reverse("rm:mfa_setup"))
        if is_mfa_verified(request):
            return None
        return redirect(reverse("rm:mfa_verify"))
