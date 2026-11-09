"""
Respostas JSON seguras — sem vazar exceções ou paths em produção.
"""
from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.http import JsonResponse

logger = logging.getLogger("security")

MSG_SERVER_ERROR = "Erro interno do servidor."
MSG_GENERIC = "Não foi possível concluir a operação."


def client_error_message(exc: BaseException | None, *, fallback: str = MSG_GENERIC) -> str:
    """Mensagem para o cliente: detalhe só em DEBUG."""
    if exc and settings.DEBUG:
        return str(exc)[:500]
    return fallback


def json_error(
    message: str,
    *,
    status: int = 400,
    logger_name: str | None = None,
    exc: BaseException | None = None,
    **extra: Any,
) -> JsonResponse:
    """JsonResponse com mensagem segura (5xx genérico em produção)."""
    if status >= 500:
        if exc:
            log = logging.getLogger(logger_name) if logger_name else logger
            log.exception("API error %s: %s", status, exc)
        if not settings.DEBUG:
            message = MSG_SERVER_ERROR
        elif exc:
            message = str(exc)[:500]
    body: dict[str, Any] = {"erro": message}
    if settings.DEBUG and extra:
        body.update(extra)
    elif settings.DEBUG and exc and status >= 500:
        body["tipo"] = type(exc).__name__
    return JsonResponse(body, status=status)


def json_ok(data: dict[str, Any] | None = None, *, status: int = 200) -> JsonResponse:
    payload = data or {}
    return JsonResponse(payload, status=status)
