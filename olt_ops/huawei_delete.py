"""
Exclusão Huawei MA5800/MA5680 — baseado em archive/legacy-desktop-tools/deletar_onu.py.
Sessão única: enable/config uma vez; por SN: by-sn → undo → ont delete → quit.
"""
from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass

GEMPORT = 126
BY_SN_PAGE_SPACES = 8

HUAWEI_PAGE_CRK = re.compile(rb"\{\s*<cr>\s*\|\|\s*<K>\s*\}\s*:", re.I)
HUAWEI_SCROLLNUM = re.compile(rb"scrollnum", re.I)
MORE_MARKERS = (
    b"---- More ----",
    b"--- More ---",
    b"  ---- More ----",
    b"---- More (",
    b"press 'q' to break",
    b"--More--",
    b"-- More --",
    b" --More--",
)
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x07")


@dataclass(frozen=True)
class HuaweiOntInfo:
    sn: str
    line_profile_id: int
    frame: int
    slot: int
    port: int
    ont_id: int

    @property
    def fsp(self) -> str:
        return f"{self.frame}/{self.slot}/{self.port}"

    @property
    def fs(self) -> str:
        return f"{self.frame}/{self.slot}"


def _strip_ansi_text(text: str) -> str:
    return _ANSI_RE.sub("", text or "")


def _strip_ansi_bytes(data: bytes) -> bytes:
    return re.sub(rb"\x1b\[[0-9;?]*[a-zA-Z]", b"", data)


def norm_sn(s: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", (s or "").strip()).upper()


def huawei_sn_variants(sn: str) -> list[str]:
    """Formatos alternativos para display ont info by-sn (como no .exe legado)."""
    h = norm_sn(sn)
    seen: set[str] = set()
    out: list[str] = []

    def add(v: str) -> None:
        k = norm_sn(v)
        if k and k not in seen:
            seen.add(k)
            out.append(k)

    add(h)
    if h.startswith("5A544547") and len(h) > 8:
        add(f"ZTEG-{h[8:]}")
    if h.startswith("48575443") and len(h) > 8:
        add(f"HWTC-{h[8:]}")
    if h.startswith("ZTEG") and len(h) > 4:
        tail = h[4:].lstrip("-")
        if tail:
            add("5A544547" + tail)
    if h.startswith("HWTC") and len(h) > 4:
        tail = h[4:].lstrip("-")
        if tail:
            add("48575443" + tail)
    if h.startswith("MONU") and len(h) > 4:
        add(h if "-" in h else f"MONU-{h[4:].lstrip('-')}")
    return out[:8]


def _olt_says_not_exist(text: str) -> bool:
    low = (text or "").lower()
    return "does not exist" in low or "não existe" in low or "not exist" in low


def _sn_in_text(text: str, sn: str) -> bool:
    h = norm_sn(sn)
    if not h:
        return False
    up = text.upper()
    if h in up:
        return True
    tail = h[-8:] if len(h) >= 8 else h
    if tail and tail in up:
        return True
    if h.startswith("5A544547") and f"ZTEG-{h[8:]}" in up.replace("ZTEG", "ZTEG-"):
        return True
    m = re.search(rf"SN\s*[:：]?\s*([0-9A-Fa-f]+)\s*\([^)]*{re.escape(tail)}", up, re.I)
    return bool(m)


def _first_int(patterns: list[str], text: str) -> int | None:
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            return int(m.group(1))
    return None


def parse_by_sn_output(text: str, sn: str) -> HuaweiOntInfo | None:
    """Parser da saída display ont info by-sn (F/S/P, ONT-ID, Line profile ID)."""
    text = _strip_ansi_text(text.replace("\ufeff", "").replace("\u00a0", " "))
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    frame = slot = port = ont_id = None
    sn_norm = norm_sn(sn)

    m_fsp = re.search(
        r"(?:F/S/P|In\s+port|GPON\s+port)\s*[:：]?\s*(\d+)\s*/\s*(\d+)\s*/\s*(\d+)",
        text,
        re.I,
    )
    if m_fsp:
        frame, slot, port = int(m_fsp.group(1)), int(m_fsp.group(2)), int(m_fsp.group(3))

    ont_id = _first_int(
        [
            r"ONT[-\s]*ID\s*[:：]?\s*(\d+)",
            r"ONT\s+No\.?\s*[:：]?\s*(\d+)",
        ],
        text,
    )

    line_id = _first_int(
        [
            r"Line\s+profile\s+ID\s*[:：]?\s*(\d+)",
            r"Line\s+profile\s+index\s*[:：]?\s*(\d+)",
        ],
        text,
    )
    if line_id is None:
        line_id = _first_int([r"Service\s+profile\s+ID\s*[:：]?\s*(\d+)"], text)

    if None in (frame, slot, port, ont_id) or line_id is None:
        return None
    if not _sn_in_text(text, sn):
        return None

    return HuaweiOntInfo(
        sn=sn_norm,
        line_profile_id=line_id,
        frame=frame,
        slot=slot,
        port=port,
        ont_id=ont_id,
    )


def build_delete_commands(info: HuaweiOntInfo) -> list[str]:
    return [
        (
            f"undo service-port vlan {info.line_profile_id} gpon {info.fsp} "
            f"ont {info.ont_id} gemport {GEMPORT}"
        ),
        f"interface gpon {info.fs}",
        f"ont delete {info.port} {info.ont_id}",
        "quit",
    ]


def _buffer_has_more_prompt(buf: bytes) -> bool:
    low = buf.lower()
    if b"--more--" in low or b"---- more" in low:
        return True
    for m in MORE_MARKERS:
        if m in buf:
            return True
    return bool(HUAWEI_PAGE_CRK.search(buf)) or bool(HUAWEI_SCROLLNUM.search(buf))


def _advance_more_pages(buf: bytes, chan, *, crk_first: bool) -> tuple[bytes, bool]:
    """Remove prompts de paginação e envia espaço/Enter para a próxima página."""
    sent = False
    if HUAWEI_SCROLLNUM.search(buf):
        buf = HUAWEI_SCROLLNUM.sub(b"", buf)
        chan.send(b"\x03")
        return buf, True
    if HUAWEI_PAGE_CRK.search(buf):
        buf = HUAWEI_PAGE_CRK.sub(b"", buf)
        chan.send(b"\r\n" if crk_first else b" ")
        return buf, True
    for m in MORE_MARKERS:
        while m in buf:
            buf = buf.replace(m, b"", 1)
            chan.send(b" ")
            sent = True
    if b"--more--" in buf.lower():
        buf = re.sub(rb"-{2,}\s*More\s*-{2,}", b"", buf, flags=re.I)
        chan.send(b" ")
        sent = True
    return buf, sent


def _read_channel(
    chan,
    idle_end: float = 1.0,
    max_total: float = 180.0,
    *,
    tail_phase: bool = True,
) -> str:
    buf = b""
    t0 = time.time()
    last_data = time.time()
    crk_first = True
    while time.time() - t0 < max_total:
        if chan.recv_ready():
            buf += chan.recv(65536)
            last_data = time.time()
            buf, advanced = _advance_more_pages(buf, chan, crk_first=crk_first)
            if advanced:
                crk_first = False
            continue
        if time.time() - last_data >= idle_end:
            if _buffer_has_more_prompt(buf):
                buf, advanced = _advance_more_pages(buf, chan, crk_first=crk_first)
                if advanced:
                    crk_first = False
                    last_data = time.time()
                    continue
            break
        time.sleep(0.05)

    if tail_phase:
        tail_limit = min(time.time() + 6.0, t0 + max_total)
        last_data = time.time()
        while time.time() < tail_limit:
            if chan.recv_ready():
                buf += chan.recv(65536)
                last_data = time.time()
                buf, advanced = _advance_more_pages(buf, chan, crk_first=crk_first)
                if advanced:
                    crk_first = False
                continue
            if time.time() - last_data >= 0.5:
                if _buffer_has_more_prompt(buf):
                    buf, advanced = _advance_more_pages(buf, chan, crk_first=crk_first)
                    if advanced:
                        crk_first = False
                        last_data = time.time()
                        continue
                break
            time.sleep(0.05)

    return _strip_ansi_bytes(buf).decode("utf-8", errors="replace")


def _flush_recv(chan, seconds: float = 0.35) -> None:
    t0 = time.time()
    while chan.recv_ready() and time.time() - t0 < seconds:
        chan.recv(65536)


def _sync_prompt(chan, *, max_total: float = 5.0) -> str:
    chan.send(b"\n")
    return _read_channel(chan, idle_end=0.38, max_total=max_total, tail_phase=False)


def _at_config_prompt(text: str) -> bool:
    """(config)# global — não confundir com interface gpon."""
    low = (text or "").lower()
    if "config-if-gpon" in low:
        return False
    return "(config)#" in low or low.rstrip().endswith("config)#")


def _at_privileged_prompt(text: str) -> bool:
    if _at_config_prompt(text) or "config-if-gpon" in (text or "").lower():
        return False
    lines = [ln.strip() for ln in (text or "").replace("\r", "").split("\n") if ln.strip()]
    if not lines:
        return False
    last = lines[-1]
    return bool(re.search(r"#[^)]*$", last) and "(config)" not in last)


def _read_fast(chan, *, idle_end: float = 0.32, max_total: float = 25.0) -> str:
    return _read_channel(chan, idle_end=idle_end, max_total=max_total, tail_phase=False)


def _read_until_markers(
    chan,
    acc: str,
    markers: tuple[str, ...],
    *,
    idle_end: float = 0.28,
    max_total: float = 90.0,
) -> str:
    t0 = time.time()
    low_markers = tuple(m.lower() for m in markers)
    while time.time() - t0 < max_total:
        if any(m in acc.lower() for m in low_markers):
            return acc
        chunk = _read_fast(chan, idle_end=idle_end, max_total=min(8.0, max_total))
        if chunk:
            acc += chunk
        elif any(m in acc.lower() for m in low_markers):
            return acc
    return acc


def _wait_gpon_interface_prompt(chan, acc: str, timeout: float = 8.0) -> str:
    return _read_until_markers(
        chan, acc, ("config-if-gpon-",), idle_end=0.3, max_total=timeout
    )


def _enable_config_fast(chan, password: str, log_fn: Callable[[str], None] | None) -> None:
    out = _send_cmd(chan, "enable", log_fn, idle_end=0.4, max_total=12.0, tail_phase=False)
    if "assword" in out.lower():
        _send_cmd(chan, password, log_fn, idle_end=0.4, max_total=10.0, tail_phase=False)
    _send_cmd(chan, "config", log_fn, idle_end=0.4, max_total=12.0, tail_phase=False)


def _ensure_config_mode(chan, password: str, log_fn: Callable[[str], None] | None) -> None:
    """
    Garante prompt (config)# antes de display/undo.
    Se estiver em interface gpon, envia quit. Nunca enable/config já em (config)#.
    """
    acc = _sync_prompt(chan)
    for _ in range(8):
        if _at_config_prompt(acc):
            return
        low = acc.lower()
        if "config-if-gpon" in low:
            acc = _send_cmd(chan, "quit", log_fn, idle_end=0.4, max_total=8.0, tail_phase=False)
            acc += _sync_prompt(chan)
            continue
        if "log out" in low and ("(y/n)" in low or "[y/n]" in low):
            if log_fn:
                log_fn(">>> n")
            chan.send(b"n\n")
            acc = _read_fast(chan, idle_end=0.35, max_total=4.0)
            continue
        if "more (" in low or "---- more" in low or "{ lock" in low:
            _send_ctrl_c(chan)
            acc = _sync_prompt(chan)
            continue
        if _at_privileged_prompt(acc):
            acc = _send_cmd(chan, "config", log_fn, idle_end=0.45, max_total=12.0, tail_phase=False)
            if _at_config_prompt(acc):
                return
            acc += _sync_prompt(chan)
            continue
        if re.search(r">\s*$", acc, re.M) and "(config)" not in low:
            _enable_config_fast(chan, password, log_fn)
            acc = _sync_prompt(chan)
            continue
        acc += _sync_prompt(chan)


def _log_olt_block(
    log_fn: Callable[[str], None] | None,
    title: str,
    text: str,
) -> None:
    if not log_fn:
        return
    body = _strip_ansi_text((text or "").strip())
    if not body:
        return
    log_fn(f"--- {title} ---")
    log_fn(body)


def _erro_curto(saida: str) -> str:
    for line in saida.replace("\r", "").split("\n"):
        t = line.strip()
        if not t:
            continue
        low = t.lower()
        if t.startswith("%") or "failure" in low or "unknown command" in low:
            return t[:240]
    if "have been deleted:  0" in saida or "success: 0" in saida.lower():
        return "OLT não confirmou exclusão (0 removidas)"
    return "veja a saída da OLT acima"


def _send_cmd(
    chan,
    cmd: str,
    log_fn: Callable[[str], None] | None,
    *,
    idle_end: float = 1.0,
    max_total: float = 60.0,
    tail_phase: bool = True,
) -> str:
    if cmd.strip() and log_fn:
        log_fn(f">>> {cmd}")
    _flush_recv(chan)
    if cmd.strip():
        chan.send(cmd.encode("utf-8", errors="replace") + b"\n")
    out = _read_channel(chan, idle_end=idle_end, max_total=max_total, tail_phase=tail_phase)
    if cmd.strip():
        _log_olt_block(log_fn, "resposta OLT", out)
    return out


def _needs_confirm_y(text: str) -> bool:
    low = text.lower()
    return "(y/n)" in low or "[y/n]" in low or "are you sure" in low


def _delete_ok(text: str) -> bool:
    low = text.lower()
    if "unknown command" in low or "%" in text:
        if re.search(r"%\s*\w", text):
            return False
    if "success: 1" in low or "success:1" in low:
        return True
    if "have been deleted:  1" in low or "have been deleted: 1" in low:
        return True
    if "failure" in low:
        return False
    return "ont delete" in low and "success" in low


def _send_ctrl_c(chan) -> str:
    try:
        chan.send(b"\x03")
    except Exception:
        return ""
    return _read_channel(chan, idle_end=0.25, max_total=3.0, tail_phase=False)


def _exit_display_pager(chan, text: str) -> None:
    """Sai de ---- More ---- / { lock<K> } antes do próximo comando."""
    low = (text or "").lower()
    if "press 'q' to break" in low or "---- more" in low or "{ lock" in low:
        try:
            chan.send(b"q")
            _read_channel(chan, idle_end=0.35, max_total=4.0, tail_phase=False)
        except Exception:
            pass


def _send_delete_cmd_on_chan(
    chan,
    cmd: str,
    password: str,
    log_fn: Callable[[str], None] | None,
) -> str:
    low = cmd.strip().lower()
    if low.startswith("undo service-port"):
        out = _send_cmd(chan, cmd, log_fn, idle_end=0.5, max_total=90.0, tail_phase=False)
        if _needs_confirm_y(out) and "deleting end" not in out.lower():
            if log_fn:
                log_fn(">>> y")
            chan.send(b"y\n")
            out = _read_until_markers(
                chan,
                out,
                ("deleting end", "have been deleted", "failure", "unknown command"),
                idle_end=0.4,
                max_total=120.0,
            )
            _log_olt_block(log_fn, "resposta confirmação (y)", out)
        return out

    if low.startswith("interface gpon"):
        out = _send_cmd(chan, cmd, log_fn, idle_end=0.45, max_total=15.0, tail_phase=False)
        out = _wait_gpon_interface_prompt(chan, out, timeout=8.0)
        if "config-if-gpon" not in out.lower():
            _ensure_config_mode(chan, password, log_fn)
            out = _send_cmd(chan, cmd, log_fn, idle_end=0.45, max_total=15.0, tail_phase=False)
            out = _wait_gpon_interface_prompt(chan, out, timeout=8.0)
        return out

    if low.startswith("ont delete"):
        time.sleep(0.15)
        out = _send_cmd(chan, cmd, log_fn, idle_end=0.5, max_total=35.0, tail_phase=False)
        return _read_until_markers(
            chan,
            out,
            ("success:", "failure", "unknown command"),
            idle_end=0.35,
            max_total=25.0,
        )

    out = _send_cmd(chan, cmd, log_fn, idle_end=0.35, max_total=10.0, tail_phase=False)
    if low == "quit" and "log out" in out.lower() and _needs_confirm_y(out):
        if log_fn:
            log_fn(">>> n")
        chan.send(b"n\n")
        out += _read_fast(chan, idle_end=0.35, max_total=5.0)
    return _read_until_markers(chan, out, ("(config)#", "config)#"), idle_end=0.3, max_total=8.0)


def _fetch_by_sn(chan, sn: str, log_fn: Callable[[str], None] | None) -> str:
    cmd = f"display ont info by-sn {sn}"
    _flush_recv(chan)
    if log_fn:
        log_fn(f">>> {cmd}")
    chan.send(cmd.encode("utf-8", errors="replace") + b"\n")

    buf = b""
    t_wait = time.time()
    while time.time() - t_wait < 8.0:
        if chan.recv_ready():
            buf += chan.recv(65536)
        if HUAWEI_PAGE_CRK.search(buf):
            break
        if b"F/S/P" in buf or b"In port" in buf:
            break
        if b"Failure" in buf or b"does not exist" in buf.lower():
            break
        if b"% Unknown" in buf or b"parameter error" in buf.lower():
            break
        time.sleep(0.05)

    if HUAWEI_PAGE_CRK.search(buf) or (b"F/S/P" not in buf and b"Failure" not in buf):
        chan.send(b"\r\n")

    rest = _read_channel(chan, idle_end=1.0, max_total=180.0, tail_phase=True)
    text = _strip_ansi_bytes(buf).decode("utf-8", errors="replace") + rest

    lookup_sn_norm = norm_sn(sn)
    for _ in range(BY_SN_PAGE_SPACES):
        if parse_by_sn_output(text, lookup_sn_norm):
            break
        if _olt_says_not_exist(text):
            break
        if "---- More" not in text and "More (" not in text:
            if _sn_in_text(text, lookup_sn_norm) and "F/S/P" in text:
                if re.search(r"Line\s+profile\s+ID", text, re.I):
                    break
        chan.send(b" ")
        text += _read_channel(chan, idle_end=0.45, max_total=18.0, tail_phase=True)

    _log_olt_block(log_fn, "resposta display by-sn", text)
    return text


def lookup_sn(
    chan,
    sn: str,
    password: str,
    log_fn: Callable[[str], None] | None,
) -> tuple[HuaweiOntInfo | None, str]:
    _ensure_config_mode(chan, password, log_fn)
    parts: list[str] = []
    info: HuaweiOntInfo | None = None
    raw = ""
    variants = huawei_sn_variants(sn)
    for variant in variants:
        if len(variants) > 1 and log_fn:
            log_fn(f"--- tentativa SN: {variant} ---")
        raw = _fetch_by_sn(chan, variant, log_fn)
        parts.append(raw)
        info = parse_by_sn_output(raw, sn)
        _exit_display_pager(chan, raw)
        _send_ctrl_c(chan)
        _ensure_config_mode(chan, password, log_fn)
        if info:
            break
        if _olt_says_not_exist(raw):
            break
    return info, "\n".join(parts)


def _delete_one(
    chan,
    info: HuaweiOntInfo,
    password: str,
    log_fn: Callable[[str], None] | None,
) -> tuple[bool, str]:
    _ensure_config_mode(chan, password, log_fn)
    parts: list[str] = []
    try:
        for cmd in build_delete_commands(info):
            parts.append(_send_delete_cmd_on_chan(chan, cmd, password, log_fn))
    except Exception:
        _ensure_config_mode(chan, password, log_fn)
        raise
    texto = "\n".join(parts)
    ok = _delete_ok(texto)
    _ensure_config_mode(chan, password, log_fn)
    return ok, texto


def run_huawei_delete_batch(
    chan,
    password: str,
    serials: list[str],
    log_fn: Callable[[str], None] | None = None,
) -> dict:
    _ensure_config_mode(chan, password, log_fn)
    ok = 0
    fail = 0
    for sn in serials:
        if log_fn:
            log_fn(f"--- SN {sn} ---")
        try:
            info, raw_lookup = lookup_sn(chan, sn, password, log_fn)
            if not info:
                if log_fn:
                    if _olt_says_not_exist(raw_lookup):
                        log_fn(
                            f"SN {sn}: OLT respondeu que não existe "
                            "(já foi removida antes ou SN incorreto)"
                        )
                    else:
                        log_fn(f"SN {sn}: não localizado — faltam dados na resposta")
                        _log_olt_block(log_fn, "saída bruta (não localizado)", raw_lookup)
                fail += 1
                continue
            if log_fn:
                log_fn(
                    f"Localizado: F/S/P {info.fsp} ONT {info.ont_id} "
                    f"vlan/line {info.line_profile_id}"
                )
            deleted, out_del = _delete_one(chan, info, password, log_fn)
            if deleted:
                if log_fn:
                    log_fn(f"SN {sn}: OK")
                ok += 1
            else:
                if log_fn:
                    log_fn(f"SN {sn}: falha na exclusão — {_erro_curto(out_del)}")
                    _log_olt_block(log_fn, "saída bruta exclusão", out_del)
                fail += 1
        except Exception as exc:
            if log_fn:
                log_fn(f"SN {sn}: ERRO {exc}")
            _ensure_config_mode(chan, password, log_fn)
            fail += 1
    return {"ok": ok, "fail": fail, "total": len(serials)}
