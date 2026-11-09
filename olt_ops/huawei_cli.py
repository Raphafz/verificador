"""

Sessão CLI Huawei MA5800 — alinhado a archive/legacy-desktop-tools/huawei_olt.py e listar_ont_offline.py.

Paginação: 7 espaços após o display (sem screen-length / scroll).

"""

from __future__ import annotations



import select

import socket

import time

from collections.abc import Callable



from .cli_log import emit_cli_output

from .huawei_delete import _flush_recv, _read_channel



# Após display ont info … all — igual archive/legacy-desktop-tools/huawei_olt.py

HUAWEI_DISPLAY_PAGE_SPACES = 7



HUAWEI_DISPLAY_END_MARKERS = (

    "the total of onts are",

    "total of onts are:",

    "total of onts is",

)





class TelnetChannelAdapter:

    """Adapta socket Telnet para a API usada por _read_channel (recv_ready/recv/send)."""



    def __init__(self, sock: socket.socket):

        self._sock = sock

        self.closed = False



    def recv_ready(self) -> bool:

        try:

            readable, _, _ = select.select([self._sock], [], [], 0)

            return bool(readable)

        except OSError:

            return False



    def recv(self, nbytes: int) -> bytes:

        return self._sock.recv(nbytes)



    def send(self, data: bytes) -> None:

        self._sock.sendall(data)





def _huawei_clear_stale_prompt(

    chan,

    log_fn: Callable[[str], None] | None = None,

) -> None:

    """Ctrl+C + Enter se ficou preso em prompt interativo (ex.: scroll)."""

    chan.send(b"\x03")

    time.sleep(0.12)

    out = _read_channel(chan, idle_end=0.45, max_total=6.0, tail_phase=False)

    if log_fn and out.strip():

        emit_cli_output(log_fn, out, header=None)

    chan.send(b"\n")

    _read_channel(chan, idle_end=0.4, max_total=5.0, tail_phase=False)





def _huawei_post_display_spaces(chan, n: int = HUAWEI_DISPLAY_PAGE_SPACES) -> str:

    """Envia N espaços (um por vez) para passar ---- More ---- até o fim da lista."""

    parts: list[str] = []

    for _ in range(n):

        if getattr(chan, "closed", False):

            break

        chan.send(b" ")

        time.sleep(0.08)

        chunk = _read_channel(chan, idle_end=0.45, max_total=10.0, tail_phase=True)

        if chunk:

            parts.append(chunk)

    tail = _read_channel(chan, idle_end=1.0, max_total=18.0, tail_phase=True)

    if tail:

        parts.append(tail)

    return "".join(parts)





def huawei_enter_config(chan, password: str, log_fn: Callable[[str], None] | None = None) -> None:

    """enable → (senha se pedir) → config → Enter em (config)#."""

    log = log_fn or (lambda _m: None)

    log(">>> enable")

    out = _send_cmd(chan, "enable", idle_end=2.2, max_total=45.0, log_fn=log_fn)

    if "assword" in out.lower():

        log(">>> [senha enable]")

        _send_cmd(chan, password, idle_end=2.2, max_total=35.0, log_fn=log_fn)

    log(">>> config")

    _send_cmd(chan, "config", idle_end=2.2, max_total=45.0, log_fn=log_fn)

    chan.send(b"\n")

    _read_channel(chan, idle_end=0.55, max_total=8.0, tail_phase=False)





def huawei_run_display_list(

    chan,

    display_cmd: str,

    password: str,

    log_fn: Callable[[str], None] | None = None,

    *,

    max_total: float = 600.0,

) -> str:

    """

    display ont info F S P all + 7 espaços para paginação (como PuTTY manual).

    """

    log = log_fn or (lambda _m: None)

    huawei_enter_config(chan, password, log_fn=log)

    _huawei_clear_stale_prompt(chan, log_fn)

    _flush_recv(chan, 0.35)



    log(f">>> {display_cmd}")

    if log_fn:

        log_fn("--- Resposta OLT (display ont info) ---")

    _flush_recv(chan, 0.35)

    chan.send(display_cmd.encode("utf-8") + b"\n")

    main = _read_channel(chan, idle_end=6.5, max_total=max_total, tail_phase=True)

    if log_fn and main.strip():

        emit_cli_output(log_fn, main, header=None)



    log(f"… paginação: {HUAWEI_DISPLAY_PAGE_SPACES} espaços")

    extra = _huawei_post_display_spaces(chan, HUAWEI_DISPLAY_PAGE_SPACES)

    if log_fn and extra.strip():

        emit_cli_output(log_fn, extra, header=None)

    return main + extra





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


