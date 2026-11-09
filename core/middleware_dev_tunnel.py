"""Túnel dev (cloudflare/ngrok) — CSRF e origens confiáveis com URL dinâmica."""
from __future__ import annotations

from django.conf import settings
from django.utils.deprecation import MiddlewareMixin

_TUNNEL_SUFFIXES = (
    ".trycloudflare.com",
    ".loca.lt",
    ".ngrok-free.app",
    ".ngrok.app",
    ".ngrok.io",
)


def _dev_tunnel_mode_enabled() -> bool:
    return bool(getattr(settings, "DEBUG", False) or getattr(settings, "IS_LOCAL_DEV", False))


def _request_host(request) -> str:
    forwarded = (request.headers.get("X-Forwarded-Host") or "").split(",")[0].strip()
    host = forwarded or request.get_host()
    return host.split(":")[0].lower()


def _is_tunnel_host(host: str) -> bool:
    return any(host.endswith(suffix) for suffix in _TUNNEL_SUFFIXES)


class DevTunnelCsrfMiddleware(MiddlewareMixin):
    """
    - Adiciona Origin do túnel a CSRF_TRUSTED_ORIGINS.
    - Em dev + host de túnel, não exige CSRF (cookie Secure/Origin instável no quick tunnel).
    """

    def process_request(self, request):
        if not _dev_tunnel_mode_enabled():
            return None
        self._trust_request_origin(request)
        return None

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not _dev_tunnel_mode_enabled():
            return None
        if _is_tunnel_host(_request_host(request)):
            request._dont_enforce_csrf_checks = True
        return None

    @staticmethod
    def _trust_request_origin(request) -> None:
        host = _request_host(request)
        proto = (request.headers.get("X-Forwarded-Proto") or "").split(",")[0].strip()
        if not proto:
            proto = "https" if request.is_secure() else "http"

        for origin in (f"{proto}://{host}", f"https://{host}", f"http://{host}"):
            if origin not in settings.CSRF_TRUSTED_ORIGINS:
                settings.CSRF_TRUSTED_ORIGINS.append(origin)
