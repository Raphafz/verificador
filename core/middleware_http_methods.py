"""Restringe métodos HTTP perigosos ou desnecessários fora da API REST."""
from django.conf import settings
from django.http import HttpResponseNotAllowed

DISALLOWED_HTTP_METHODS = frozenset({"TRACE", "CONNECT"})

# Métodos de escrita só em /api/
WRITE_METHODS = frozenset({"PUT", "DELETE", "PATCH"})
API_PREFIXES = ("/api/",)


class HttpMethodRestrictionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        extra = getattr(settings, "DISALLOWED_HTTP_METHODS", None) or ()
        self._blocked = DISALLOWED_HTTP_METHODS | frozenset(m.upper() for m in extra)

    def __call__(self, request):
        method = request.method.upper()
        if method in self._blocked:
            return HttpResponseNotAllowed(
                ["GET", "POST", "HEAD", "OPTIONS", "PATCH", "PUT", "DELETE"]
            )
        path = request.path or ""
        if method in WRITE_METHODS and not any(path.startswith(p) for p in API_PREFIXES):
            return HttpResponseNotAllowed(["GET", "POST", "HEAD", "OPTIONS"])
        return self.get_response(request)
