"""
Redirecionamentos pós-login seguros (anti open redirect).
"""
from __future__ import annotations

from django.conf import settings
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme


def is_safe_redirect_url(request, url: str | None) -> bool:
    if not url or not str(url).strip():
        return False
    url = str(url).strip()
    if url.startswith("//"):
        return False
    allowed_hosts = {request.get_host(), *getattr(settings, "ALLOWED_HOSTS", [])}
    return url_has_allowed_host_and_scheme(
        url=url,
        allowed_hosts=allowed_hosts,
        require_https=request.is_secure(),
    )


def safe_redirect(request, url: str | None, *, fallback_name: str = "dashboard"):
    """Redireciona para url se segura; caso contrário usa fallback_name."""
    if is_safe_redirect_url(request, url):
        return HttpResponseRedirect(url)
    return HttpResponseRedirect(reverse(fallback_name))
