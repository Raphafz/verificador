"""Exige aceite dos documentos legais na versão vigente."""
from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin

from .lgpd_constants import LEGAL_DOCUMENT_VERSION, REQUIRED_CONSENT_TYPES
from .models import ConsentRecord


class ConsentMiddleware(MiddlewareMixin):
    EXEMPT_PREFIXES = (
        "/ativar-conta/",
        "/consent-required/",
        "/rm/login/",
        "/rm/mfa/",
        "/login/",
        "/logout/",
        "/static/",
        "/media/",
        "/admin/",
        "/termos-uso/",
        "/politica-privacidade/",
        "/politica-cookies/",
        "/lgpd/",
        "/encarregado-dados/",
        "/faq/",
        "/ajuda/",
        "/manual/",
        "/api/internal/",
        "/api/v1/",
        "/health/",
        "/ready/",
        "/change-password-required/",
    )

    def process_request(self, request):
        if not request.user.is_authenticated:
            return None

        path = request.path
        for prefix in self.EXEMPT_PREFIXES:
            if path.startswith(prefix) or "/login/" in path:
                return None

        missing = []
        for doc_type in REQUIRED_CONSENT_TYPES:
            if not ConsentRecord.objects.filter(
                user=request.user,
                document_type=doc_type,
                document_version=LEGAL_DOCUMENT_VERSION,
            ).exists():
                missing.append(doc_type)

        if missing and not path.startswith("/consent-required/"):
            return redirect("consent_required")

        return None
