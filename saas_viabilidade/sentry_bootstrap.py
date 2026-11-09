"""Inicialização do Sentry (LGPD: sem PII por padrão)."""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def init_sentry(*, debug: bool, environment: str) -> bool:
    """
    Ativa o Sentry se SENTRY_DSN estiver definido e sentry-sdk instalado.
    Retorna True se inicializou.
    """
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
    except ImportError:
        logger.warning(
            "SENTRY_DSN definido, mas sentry-sdk não está instalado. "
            "Execute: pip install sentry-sdk"
        )
        return False

    traces_raw = os.getenv(
        "SENTRY_TRACES_SAMPLE_RATE",
        "0" if debug else "0.1",
    )
    try:
        traces_sample_rate = float(traces_raw)
    except ValueError:
        traces_sample_rate = 0.0

    sentry_logging = LoggingIntegration(
        level=logging.INFO,
        event_level=logging.ERROR,
    )

    sentry_sdk.init(
        dsn=dsn,
        integrations=[DjangoIntegration(), sentry_logging],
        environment=environment,
        traces_sample_rate=traces_sample_rate,
        send_default_pii=False,
        debug=debug and os.getenv("SENTRY_DEBUG", "").lower() in ("1", "true", "yes"),
    )
    logger.info("Sentry ativo (environment=%s, traces=%s)", environment, traces_sample_rate)
    return True
