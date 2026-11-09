"""
Helpers de autenticação — anti-enumeração e respostas uniformes.
"""
from __future__ import annotations

import logging
import random
import time

from django.contrib.auth import get_user_model

logger = logging.getLogger("security")

INVALID_LOGIN_MESSAGE = "Credenciais inválidas."
INVALID_LOGIN_COMPANY_MESSAGE = "Credenciais inválidas para esta empresa."

_FAILURE_DELAY_MIN = 0.12
_FAILURE_DELAY_MAX = 0.28


def _failure_delay_enabled() -> bool:
    import os

    from django.conf import settings

    force = os.getenv("FORCE_RATE_LIMIT", "").lower() in ("1", "true", "yes", "on")
    if force:
        return True
    return not getattr(settings, "DEBUG", True)


def apply_login_failure_delay() -> None:
    """Atraso leve em falha de login para reduzir enumeração por timing."""
    if not _failure_delay_enabled():
        return
    time.sleep(random.uniform(_FAILURE_DELAY_MIN, _FAILURE_DELAY_MAX))


def resolve_login_username(input_id: str) -> str:
    """
    Resolve e-mail para username sem lançar exceção (mesmo caminho para existente/inexistente).
    """
    input_id = (input_id or "").strip()
    if not input_id:
        return ""
    if "@" not in input_id:
        return input_id
    User = get_user_model()
    row = User.objects.filter(email__iexact=input_id).only("username").first()
    return row.username if row else input_id
