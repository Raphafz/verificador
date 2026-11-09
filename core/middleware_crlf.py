"""Bloqueia injeção CRLF em path e query string."""
from urllib.parse import unquote

from django.http import HttpResponseBadRequest

def _contains_crlf(value: str) -> bool:
    if not value:
        return False
    decoded = unquote(value)
    if "\r" in decoded or "\n" in decoded:
        return True
    lower = value.lower()
    return "%0d" in lower or "%0a" in lower


class CrlfProtectionMiddleware:
    """Rejeita requisições com CR/LF na URL (response splitting / header injection)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path or ""
        query = request.META.get("QUERY_STRING", "")
        if _contains_crlf(path) or _contains_crlf(query):
            return HttpResponseBadRequest("Requisição inválida.")
        return self.get_response(request)
