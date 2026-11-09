"""Envio da saída OLT para log ao vivo — sempre sanitizada antes de persistir."""
from __future__ import annotations

from collections.abc import Callable

from olt_ops.operational_log import sanitize_chunk

# Linhas por bloco (menos gravações no banco, ainda atualiza o polling)
_LINES_PER_BLOCK = 60


def emit_cli_output(
    log_fn: Callable[[str], None] | None,
    text: str,
    *,
    header: str | None = "--- Resposta OLT ---",
) -> None:
    """
    Grava saída do terminal no log (sanitizada: sem senhas, tokens, IPs privados completos).
    """
    if not log_fn:
        return
    body = sanitize_chunk((text or "").replace("\r\n", "\n").replace("\r", "\n"))
    if not body.strip():
        return
    if header:
        log_fn(header)
    lines = body.split("\n")
    batch: list[str] = []
    for line in lines:
        batch.append(line)
        if len(batch) >= _LINES_PER_BLOCK:
            log_fn("\n".join(batch))
            batch = []
    if batch:
        log_fn("\n".join(batch))
