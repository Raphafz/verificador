"""Nonce CSP por requisição."""
import secrets

from django.utils.deprecation import MiddlewareMixin


class CspNonceMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request.csp_nonce = secrets.token_urlsafe(16)
