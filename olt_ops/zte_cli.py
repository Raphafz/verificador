"""
Sessão CLI ZTE C350 — alinhado a archive/legacy-desktop-tools/deletar_onu.py (_enable_config_zte).
Listagem offline: apenas ``show pon power olt-rx gpon-olt_F/S/P`` (no signal = offline).
"""
from __future__ import annotations

import re
from collections.abc import Callable

from .cli_log import emit_cli_output
import time

from .huawei_delete import _flush_recv, _read_channel, _sync_prompt

_ZTE_CONFIG_IF_RE = re.compile(r"config-if-gpon-olt", re.I)
_ZTE_CONFIG_RE = re.compile(r"\(config\)#", re.I)
# Após show pon power (várias páginas --More--)
ZTE_DISPLAY_PAGE_SPACES = 8


def zte_enter_config(
    chan,
    enable_password: str,
    log_fn: Callable[[str], None] | None = None,
) -> None:
    """enable → (senha enable) → conf t — igual ao legado deletar_onu.py."""
    log = log_fn or (lambda _m: None)
    acc = _sync_prompt(chan, max_total=6.0)
    if _at_zte_config_prompt(acc):
        return

    log(">>> enable")
    out = _send_cmd(chan, "enable", idle_end=0.45, max_total=12.0, log_fn=log_fn)
    if "assword" in out.lower():
        log(">>> [senha enable]")
        _send_cmd(chan, enable_password, idle_end=0.45, max_total=10.0, log_fn=log_fn)

    log(">>> conf t")
    _send_cmd(chan, "conf t", idle_end=0.45, max_total=12.0, log_fn=log_fn)
    _ensure_zte_config(chan, enable_password, log_fn=log)


def _at_zte_config_prompt(text: str) -> bool:
    low = (text or "").lower()
    if _ZTE_CONFIG_IF_RE.search(low):
        return False
    return bool(_ZTE_CONFIG_RE.search(low))


def _at_zte_gpon_olt_prompt(text: str) -> bool:
    return bool(_ZTE_CONFIG_IF_RE.search(text or ""))


def _ensure_zte_config(
    chan,
    password: str,
    log_fn: Callable[[str], None] | None = None,
) -> None:
    log = log_fn or (lambda _m: None)
    acc = _sync_prompt(chan, max_total=5.0)
    for _ in range(8):
        if _at_zte_config_prompt(acc):
            return
        if _at_zte_gpon_olt_prompt(acc):
            log(">>> exit")
            acc = _send_cmd(chan, "exit", idle_end=0.4, max_total=8.0, log_fn=log_fn)
            continue
        if re.search(r">\s*$", acc, re.M) and "(config)" not in acc.lower():
            zte_enter_config(chan, password, log_fn=log)
            return
        acc = _sync_prompt(chan, max_total=4.0)


def _zte_post_more_spaces(chan, n: int = ZTE_DISPLAY_PAGE_SPACES) -> str:
    """Rajada de espaços se ainda houver --More-- após a leitura principal."""
    parts: list[str] = []
    for _ in range(n):
        if getattr(chan, "closed", False):
            break
        chan.send(b" ")
        time.sleep(0.08)
        chunk = _read_channel(chan, idle_end=0.6, max_total=12.0, tail_phase=True)
        if chunk:
            parts.append(chunk)
    tail = _read_channel(chan, idle_end=1.2, max_total=20.0, tail_phase=True)
    if tail:
        parts.append(tail)
    return "".join(parts)


def zte_run_show(
    chan,
    cmd: str,
    *,
    max_total: float = 90.0,
    log_fn: Callable[[str], None] | None = None,
) -> str:
    log = log_fn or (lambda _m: None)
    log(f">>> {cmd}")
    _flush_recv(chan, 0.35)
    chan.send(cmd.encode("utf-8") + b"\n")
    out = _read_channel(chan, idle_end=2.0, max_total=max_total, tail_phase=True)
    if "olt-rx" in cmd.lower():
        log(f"… paginação ZTE: {ZTE_DISPLAY_PAGE_SPACES} espaços")
        out += _zte_post_more_spaces(chan, ZTE_DISPLAY_PAGE_SPACES)
    if log_fn and out.strip():
        log_fn("--- Resposta OLT ---")
        emit_cli_output(log_fn, out, header=None)
    return out


def zte_run_offline_list(
    chan,
    pon_id: str,
    enable_password: str,
    log_fn: Callable[[str], None] | None = None,
    *,
    command: str | None = None,
) -> str:
    """
    ``show pon power olt-rx gpon-olt_<pon>`` — parser extrai gpon-onu_F/S/P:ID com no signal.
    """
    zte_enter_config(chan, enable_password, log_fn=log_fn)
    iface = f"gpon-olt_{pon_id}"
    cmd = (command or "").strip() or f"show pon power olt-rx {iface}"
    return zte_run_show(
        chan,
        cmd,
        max_total=180.0,
        log_fn=log_fn,
    )


def _send_cmd(
    chan,
    cmd: str,
    *,
    idle_end: float,
    max_total: float,
    log_fn: Callable[[str], None] | None = None,
) -> str:
    _flush_recv(chan, 0.35)
    chan.send(cmd.encode("utf-8") + b"\n")
    out = _read_channel(chan, idle_end=idle_end, max_total=max_total, tail_phase=True)
    if log_fn and out.strip():
        emit_cli_output(log_fn, out, header=None)
    return out
