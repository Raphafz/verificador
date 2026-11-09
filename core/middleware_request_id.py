"""Request-ID e Correlation-ID para rastreio distribuído."""
from __future__ import annotations

import secrets
import threading
from contextvars import ContextVar

from django.utils.deprecation import MiddlewareMixin

_local = threading.local()
_correlation_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def get_current_request_ids() -> tuple[str | None, str | None]:
    rid = getattr(_local, "request_id", None)
    cid = _correlation_var.get() or getattr(_local, "correlation_id", None)
    return rid, cid


class RequestIdMiddleware(MiddlewareMixin):
    HEADER_REQUEST = "HTTP_X_REQUEST_ID"
    HEADER_CORRELATION = "HTTP_X_CORRELATION_ID"
    RESPONSE_HEADER = "X-Request-ID"

    def process_request(self, request):
        incoming_rid = (request.META.get(self.HEADER_REQUEST) or "").strip()
        request.request_id = incoming_rid or secrets.token_hex(16)
        incoming_cid = (request.META.get(self.HEADER_CORRELATION) or "").strip()
        request.correlation_id = incoming_cid or request.request_id
        _local.request_id = request.request_id
        _local.correlation_id = request.correlation_id
        _correlation_var.set(request.correlation_id)

    def process_response(self, request, response):
        rid = getattr(request, "request_id", None)
        if rid:
            response[self.RESPONSE_HEADER] = rid
            response["X-Correlation-ID"] = getattr(request, "correlation_id", rid)
        _local.request_id = None
        _local.correlation_id = None
        return response
