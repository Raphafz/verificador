"""
Configuração centralizada de logging — sem exposição de secrets.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from core.log_sanitizer import sanitize_log_message


class SanitizingFilter(logging.Filter):
    """Remove PII e valores sensíveis das mensagens de log."""

    SENSITIVE_KEYS = frozenset({
        "password", "secret", "token", "authorization", "cookie",
        "csrf", "api_key", "database_url", "field_encryption_key",
    })

    def filter(self, record: logging.LogRecord) -> bool:
        if record.msg:
            record.msg = sanitize_log_message(str(record.msg))
        if record.args:
            record.args = tuple(
                sanitize_log_message(str(a)) if isinstance(a, str) else a
                for a in record.args
            )
        return True


def _safe_host_list(hosts: list) -> str:
    return f"{len(hosts)} host(s)" if len(hosts) > 3 else ", ".join(hosts)


def log_startup_summary(*, debug: bool, is_vps: bool, allowed_hosts: list, csrf_count: int) -> None:
    """Log estruturado de bootstrap — nunca lista origens CSRF completas em produção."""
    logger = logging.getLogger("saas.startup")
    logger.info(
        "Aplicação iniciada",
        extra={
            "debug": debug,
            "is_vps": is_vps,
            "allowed_hosts": _safe_host_list(allowed_hosts),
            "csrf_trusted_origins_count": csrf_count,
        },
    )
    if debug:
        logger.debug("ALLOWED_HOSTS: %s", _safe_host_list(allowed_hosts))


def build_logging_config(base_dir: Path, *, debug: bool) -> dict:
    logs_dir = base_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    level = os.getenv("LOG_LEVEL", "DEBUG" if debug else "INFO").upper()
    use_json = os.getenv("LOG_FORMAT", "").lower() == "json"
    console_formatter = "json" if use_json else "verbose"

    # Windows + runserver: RotatingFileHandler falha ao renomear app.log (WinError 32).
    import sys

    file_handler_class = (
        "logging.FileHandler"
        if debug and sys.platform == "win32"
        else "logging.handlers.RotatingFileHandler"
    )
    file_handler_extra = (
        {}
        if file_handler_class == "logging.FileHandler"
        else {"maxBytes": 10 * 1024 * 1024, "backupCount": 5}
    )
    audit_handler_extra = (
        {}
        if file_handler_class == "logging.FileHandler"
        else {"maxBytes": 20 * 1024 * 1024, "backupCount": 10}
    )
    olt_handler_extra = (
        {}
        if file_handler_class == "logging.FileHandler"
        else {"maxBytes": 15 * 1024 * 1024, "backupCount": 3}
    )
    security_handler_extra = (
        {}
        if file_handler_class == "logging.FileHandler"
        else {"maxBytes": 10 * 1024 * 1024, "backupCount": 5}
    )

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "sanitize": {"()": "saas_viabilidade.logging_config.SanitizingFilter"},
            "request_id": {"()": "saas_viabilidade.logging_config.RequestIdLogFilter"},
        },
        "formatters": {
            "verbose": {
                "format": "%(asctime)s [%(levelname)s] %(name)s %(request_id)s %(message)s",
                "defaults": {"request_id": "-"},
            },
            "json": {
                "()": "saas_viabilidade.logging_config.JsonFormatter",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "filters": ["sanitize", "request_id"],
                "formatter": console_formatter,
                "level": level,
            },
            "olt_operations_file": {
                "class": file_handler_class,
                "filename": str(logs_dir / "olt_operations.log"),
                **olt_handler_extra,
                "filters": ["sanitize", "request_id"],
                "formatter": console_formatter,
                "level": "INFO",
            },
            "file": {
                "class": file_handler_class,
                "filename": str(logs_dir / "app.log"),
                **file_handler_extra,
                "filters": ["sanitize"],
                "formatter": "verbose",
                "level": "INFO",
            },
            "audit_file": {
                "class": file_handler_class,
                "filename": str(logs_dir / "audit.log"),
                **audit_handler_extra,
                "filters": ["sanitize"],
                "formatter": "verbose",
                "level": "INFO",
            },
            "security_file": {
                "class": file_handler_class,
                "filename": str(logs_dir / "security.log"),
                **security_handler_extra,
                "filters": ["sanitize"],
                "formatter": "verbose",
                "level": "WARNING",
            },
        },
        "loggers": {
            "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
            "django.request": {"handlers": ["console", "file"], "level": "WARNING", "propagate": False},
            "saas.startup": {"handlers": ["console"], "level": "INFO", "propagate": False},
            "audit": {"handlers": ["audit_file", "console"], "level": "INFO", "propagate": False},
            "security": {"handlers": ["security_file", "console"], "level": "INFO", "propagate": False},
            "olt_ops.operations": {
                "handlers": ["olt_operations_file"],
                "level": "INFO",
                "propagate": False,
            },
        },
        "root": {"handlers": ["console", "file"], "level": level},
    }


class JsonFormatter(logging.Formatter):
    """Formatter JSON-lite para integração com agregadores."""

    def format(self, record: logging.LogRecord) -> str:
        import json
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": sanitize_log_message(record.getMessage()),
            "time": self.formatTime(record),
        }
        rid = getattr(record, "request_id", None)
        if rid:
            payload["request_id"] = rid
        cid = getattr(record, "correlation_id", None)
        if cid:
            payload["correlation_id"] = cid
        return json.dumps(payload, ensure_ascii=False)


class RequestIdLogFilter(logging.Filter):
    """Injeta request_id do thread-local / contexto."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            from core.middleware_request_id import get_current_request_ids
            rid, cid = get_current_request_ids()
            record.request_id = rid or "-"
            record.correlation_id = cid or "-"
        except Exception:
            record.request_id = "-"
            record.correlation_id = "-"
        return True
