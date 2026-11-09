"""
Pipeline de log operacional OLT: sanitização, truncamento, classificação e arquivo separado.
"""
from __future__ import annotations

import logging
import os

from django.conf import settings

from core.operational_sanitizer import (
    classify_log_line,
    mask_host_for_log,
    sanitize_operational_text,
)

_olt_logger = logging.getLogger("olt_ops.operations")

OLT_LOG_MAX_CHARS = int(os.getenv("OLT_LOG_MAX_CHARS", "200000"))
OLT_LOG_RETENTION_DAYS = int(os.getenv("OLT_LOG_RETENTION_DAYS", "7"))


def sanitize_chunk(text: str) -> str:
    return sanitize_operational_text(text or "", classification="olt_cli")


def format_olt_reference(name: str, host: str, *, extra: str = "") -> str:
    host_m = mask_host_for_log(host)
    base = f"OLT: {name} ({host_m})"
    return f"{base} · {extra}" if extra else base


def append_to_job_log(current: str, chunk: str, *, classify: bool = True) -> str:
    """Sanitiza, classifica linhas novas e trunca o log acumulado."""
    if not chunk:
        return current or ""
    clean = sanitize_chunk(chunk)
    if classify:
        clean = "\n".join(
            classify_log_line(ln) if ln.strip() else ln
            for ln in clean.split("\n")
        )
    combined = (current or "") + (clean if clean.endswith("\n") else clean + "\n")
    max_chars = int(getattr(settings, "OLT_LOG_MAX_CHARS", OLT_LOG_MAX_CHARS))
    if len(combined) > max_chars:
        tail = "\n[WARN] Log truncado (limite de segurança).\n"
        keep = max_chars - len(tail) - 80
        combined = combined[: max(0, keep)] + tail
    return combined


def log_to_operations_file(job_id: int, chunk: str) -> None:
    """Cópia sanitizada em logs/olt_operations.log (separado do app.log)."""
    if not chunk.strip():
        return
    preview = sanitize_chunk(chunk)
    if len(preview) > 4000:
        preview = preview[:4000] + "\n…"
    _olt_logger.info("job_id=%s\n%s", job_id, preview)
