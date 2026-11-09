"""Throttling global leve (APIs e rotas sensíveis)."""
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

from .rate_limiting import general_limiter


class GlobalRateLimitMiddleware(MiddlewareMixin):
    """Aplica general_limiter em paths não estáticos."""

    SKIP_PREFIXES = (
        "/static/",
        "/media/",
        "/favicon.ico",
        "/.well-known/",
        "/sw.js",
    )

    def process_view(self, request, view_func, view_args, view_kwargs):
        path = request.path or ""
        if any(path.startswith(p) for p in self.SKIP_PREFIXES):
            return None
        from django.conf import settings
        import os
        force = os.getenv("FORCE_RATE_LIMIT", "").lower() in ("1", "true", "yes", "on")
        if settings.DEBUG and not force:
            return None
        if not general_limiter.is_allowed(request, "global"):
            if request.headers.get("Accept") == "application/json":
                return JsonResponse(
                    {"error": "Rate limit excedido", "retry_after": general_limiter.window},
                    status=429,
                )
            from django.http import HttpResponse
            return HttpResponse("Rate limit excedido.", status=429)
        return None
