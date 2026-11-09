"""
Redireciona rotas HTML migradas para o SPA quando FRONTEND_MODE=spa.
"""
from __future__ import annotations

import re

from django.conf import settings
from django.http import HttpResponsePermanentRedirect


# (regex pattern, spa path template — use {slug} para captura)
_SPA_REDIRECTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^/rm/login/?$"), "/rm/login"),
    (re.compile(r"^/rm/admin/?$"), "/rm/dashboard"),
    (re.compile(r"^/rm/empresas/?$"), "/rm/empresas"),
    (re.compile(r"^/rm/usuarios/?$"), "/rm/usuarios"),
    (re.compile(r"^/rm/mapas/?$"), "/rm/mapas"),
    (re.compile(r"^/rm/mfa/verify/?$"), "/mfa"),
    (re.compile(r"^/rm/mfa/setup/?$"), "/mfa/setup"),
    (re.compile(r"^/rm/password-reset/?$"), "/rm/password-reset"),
    (re.compile(r"^/ativar-conta/[^/]+/?$"), None),  # handled dynamically
    (re.compile(r"^/(?P<slug>[a-z0-9-]+)/login/?$"), "/{slug}/login"),
    (re.compile(r"^/(?P<slug>[a-z0-9-]+)/hub/?$"), "/{slug}/hub"),
    (re.compile(r"^/(?P<slug>[a-z0-9-]+)/painel/?$"), "/{slug}/dashboard"),
    (re.compile(r"^/(?P<slug>[a-z0-9-]+)/usuarios/?$"), "/{slug}/usuarios"),
    (re.compile(r"^/(?P<slug>[a-z0-9-]+)/mapas/?$"), "/{slug}/mapas"),
    (re.compile(r"^/(?P<slug>[a-z0-9-]+)/password-reset/?$"), "/{slug}/password-reset"),
]


class FrontendSpaRedirectMiddleware:
    """Em modo spa, envia rotas migradas para FRONTEND_URL."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(settings, "FRONTEND_MODE", "hybrid") != "spa":
            return self.get_response(request)

        if request.path.startswith("/api/") or request.path.startswith("/admin/"):
            return self.get_response(request)

        accept = request.headers.get("Accept", "")
        if "application/json" in accept and "text/html" not in accept:
            return self.get_response(request)

        base = getattr(settings, "FRONTEND_URL", "").rstrip("/")
        if not base:
            return self.get_response(request)

        path = request.path

        if path.startswith("/ativar-conta/"):
            token = path.rstrip("/").split("/")[-1]
            target = f"{base}/ativar-conta/{token}"
            return HttpResponsePermanentRedirect(target)

        for pattern, template in _SPA_REDIRECTS:
            if template is None:
                continue
            match = pattern.match(path)
            if match:
                spa_path = template.format(**match.groupdict()) if match.groupdict() else template
                return HttpResponsePermanentRedirect(f"{base}{spa_path}")

        return self.get_response(request)
