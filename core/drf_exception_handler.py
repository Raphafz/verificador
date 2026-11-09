"""Handler DRF — respostas 500 sem vazar stacktrace em produção."""
from __future__ import annotations

import logging

from django.conf import settings
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger("security")


def safe_drf_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        return response
    logger.exception("Unhandled API exception", exc_info=exc)
    if settings.DEBUG:
        return Response(
            {"detail": str(exc), "tipo": type(exc).__name__},
            status=500,
        )
    return Response({"detail": "Erro interno do servidor."}, status=500)
