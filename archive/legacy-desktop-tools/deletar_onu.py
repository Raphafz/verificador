# -*- coding: utf-8 -*-
"""
Apaga ONUs Huawei ou ZTE a partir de onu_deletar.txt (um SN/MAC por linha).

Por ONU (localiza → apaga → próxima):
  Huawei: display ont info by-sn → undo service-port → ont delete
  ZTE:    show gpon onu by sn → interface gpon-olt_ → no onu → exit

Cadastro de OLTs em empresas.json. CastroX © 2026
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Union

import huawei_olt as lo
from app_info import WATERMARK

TXT_ONU = "onu_deletar.txt"
GEMPORT = 126
BY_SN_PAGE_SPACES = 8  # máximo; para antes se já parseou o SN (Line profile pode vir no fim)

_cancel_event = threading.Event()


def clear_cancel() -> None:
    _cancel_event.clear()


def request_cancel() -> None:
    _cancel_event.set()


def cancel_requested() -> bool:
    return _cancel_event.is_set()


def _raise_if_cancelled() -> None:
    if _cancel_event.is_set():
        raise KeyboardInterrupt("cancelado pelo usuário")


@dataclass(frozen=True)
class OntBySn:
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


@dataclass(frozen=True)
class OntZteBySn:
    sn: str
    pon_id: str  # ex.: 1/3/1
    onu_numero: int

    @property
    def gpon_olt_if(self) -> str:
        return f"gpon-olt_{self.pon_id}"


OnuFound = Union[OntBySn, OntZteBySn]


@dataclass
class RunAllResult:
    vendor: str = "huawei"
    entries: list[tuple[str, str]] = field(default_factory=list)
    found: dict[str, OnuFound] = field(default_factory=dict)
    lookup_raw: dict[str, str] = field(default_factory=dict)
    delete_raw: dict[str, str] = field(default_factory=dict)
    not_found: dict[str, str] = field(default_factory=dict)


def app_dir() -> Path:
    """Pasta do .exe (portátil) ou USAR\\ em desenvolvimento."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    here = Path(__file__).resolve().parent
    usar = here.parent / "USAR"
    if usar.is_dir():
        return usar
    return here


TXT_ONU_TEMPLATE = """\
# Deletar ONU — um SN ou MAC por linha
# Huawei: SN hexadecimal (ex. 5A544547C8F0ED10)
# ZTE:    SN alfanumerico (ex. ITBS0D2D01F1 ou ZTEGCDAADE83)
#
"""


def ensure_portable_setup() -> Path:
    """Cria log\\, onu_deletar.txt e empresas.json na pasta do programa."""
    base = app_dir()
    (base / "log").mkdir(parents=True, exist_ok=True)
    txt = base / TXT_ONU
    if not txt.is_file():
        txt.write_text(TXT_ONU_TEMPLATE, encoding="utf-8")
    import olt_config as _ocfg

    _ocfg.load_config()
    return txt


def txt_onu_path() -> Path:
    """Sempre na mesma pasta do .exe — copie a pasta para qualquer PC."""
    return ensure_portable_setup()


def norm_onu_sn(s: str) -> str:
    """SN Huawei (hex) ou ZTE (ex.: ITBS0D2D01F1)."""
    return re.sub(r"[^0-9A-Za-z]", "", (s or "").strip()).upper()


def norm_sn(s: str) -> str:
    return norm_onu_sn(s)


# Prefixo no adesivo vs prefixo que a MA5800 grava (hex ASCII do fabricante).
_HUAWEI_SN_PREFIX_ALT: dict[str, tuple[str, ...]] = {
    "FHTC": ("HWTC", "48575443"),
    "FHTT": ("HWTC", "48575443"),
    "HWTC": ("FHTC", "46485454"),
    "TPLG": ("HWTC", "48575443"),
    "ZTEG": ("HWTC", "48575443"),
}


def _vendor_sn_hex_forms(prefix: str, tail: str) -> list[str]:
    """Gera SN em hex estilo OLT: 48575443… ou 46485454… + sufixo."""
    forms: list[str] = []
    pre_h = prefix.encode("ascii").hex().upper()
    forms.append(pre_h + tail)
    if tail.isdigit():
        forms.append(pre_h + tail.encode("ascii").hex().upper())
    return forms


def huawei_sn_variants(sn: str) -> list[str]:
    """
    Tentativas para display ont info by-sn:
    - SN do TXT (FHTC…, HWTC…, hex puro)
    - MONU-xxxxxxxx
    - Prefixo alternativo (FHTC→HWTC) e forma hex (48575443…)
    """
    h = norm_onu_sn(sn)
    seen: set[str] = set()
    out: list[str] = []

    def add(v: str) -> None:
        k = norm_onu_sn(v)
        if k and k not in seen:
            seen.add(k)
            out.append(k)

    add(h)

    if h.startswith("4D4F4E55") and len(h) >= 16:
        tail = h[8:]
        if len(tail) >= 8:
            add(f"MONU-{tail[-8:]}")
    if h.startswith("MONU"):
        add(h if "-" in h else f"MONU-{h[4:].lstrip('-')}")

    # SN alfanumérico com prefixo de 4 letras (FiberHome, TP-Link, etc.)
    if re.fullmatch(r"[A-Z]{4}[A-Z0-9]{4,}", h) and not re.fullmatch(r"[0-9A-F]{16,}", h):
        pre, tail = h[:4], h[4:]
        for hx in _vendor_sn_hex_forms(pre, tail):
            add(hx)
        for alt in _HUAWEI_SN_PREFIX_ALT.get(pre, ()):
            if re.fullmatch(r"[0-9A-F]{8}", alt):
                add(alt + tail)
            else:
                add(alt + tail)
                for hx in _vendor_sn_hex_forms(alt, tail):
                    add(hx)

    return out[:14]


def _sn_for_cmd(sn: str) -> str:
    s = (sn or "").strip().upper()
    if s.startswith("MONU-"):
        return s
    return norm_onu_sn(sn)


def build_by_sn_cmd(sn: str, profile: lo.OltProfile | None = None) -> str:
    if profile and profile.cmd_localizar_sn.strip():
        return profile.cmd_localizar_sn.replace("{sn}", _sn_for_cmd(sn)).replace(
            "{SN}", _sn_for_cmd(sn)
        )
    s = _sn_for_cmd(sn)
    if profile and profile.vendor == "zte":
        return build_zte_by_sn_cmd(sn, profile)
    return f"display ont info by-sn {s}"


def build_zte_by_sn_cmd(sn: str, profile: lo.OltProfile | None = None) -> str:
    if profile and profile.cmd_localizar_sn.strip():
        return profile.cmd_localizar_sn.replace("{sn}", _sn_for_cmd(sn)).replace(
            "{SN}", _sn_for_cmd(sn)
        )
    return f"show gpon onu by sn {norm_onu_sn(sn)}"


def _expand_cmd_lines(template: str, mapping: dict[str, str]) -> list[str]:
    lines: list[str] = []
    for line in template.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        for key, val in mapping.items():
            line = line.replace(key, val)
        lines.append(line)
    return lines


def ler_sns_txt(path: Path) -> list[str]:
    if not path.is_file():
        raise FileNotFoundError(f"Coloque a lista em:\n{path}")
    out: list[str] = []
    seen: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "\t" in line:
            line = line.split("\t", 1)[0].strip()
        key = norm_sn(line)
        if len(key) < 8:
            continue
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out


def _first_int(patterns: list[str], text: str) -> int | None:
    for pat in patterns:
        m = re.search(pat, text, re.I | re.M)
        if m:
            return int(m.group(1))
    return None


def _sn_in_olt_text(text: str, sn: str) -> bool:
    """True se o SN pedido aparece na saída (hex, parênteses ou sufixo comum)."""
    sn_norm = norm_sn(sn)
    if not sn_norm:
        return False
    compact = re.sub(r"[^0-9A-Z]", "", text.upper())
    if sn_norm in compact:
        return True
    tail = sn_norm[-8:] if len(sn_norm) >= 8 else sn_norm
    if tail and tail in compact:
        return True
    for m in re.finditer(
        r"SN\s*[:：]\s*([0-9A-F]{8,})(?:\s*\(([A-Za-z0-9-]+)\))?",
        text,
        re.I,
    ):
        hex_part = norm_sn(m.group(1))
        paren = norm_sn(m.group(2) or "")
        for cand in (hex_part, paren):
            if not cand:
                continue
            if cand == sn_norm or cand.endswith(tail) or sn_norm.endswith(
                cand[-8:] if len(cand) >= 8 else cand
            ):
                return True
            if len(sn_norm) >= 8 and len(cand) >= 8 and sn_norm[4:] == cand[4:]:
                return True
    return False


def _extract_line_profile_id(text: str) -> int | None:
    line_id = _first_int(
        [
            r"Line\s+profile\s+ID\s*[:：]?\s*(\d+)",
            r"Line\s+profile\s+index\s*[:：]?\s*(\d+)",
            r"Line\s+profile\s+no\.?\s*[:：]?\s*(\d+)",
        ],
        text,
    )
    if line_id is not None:
        return line_id
    line_id = _first_int(
        [
            r"Service\s+profile\s+ID\s*[:：]?\s*(\d+)",
            r"ONT\s+line\s+profile\s+ID\s*[:：]?\s*(\d+)",
        ],
        text,
    )
    if line_id is not None:
        return line_id
    m_vlan = re.search(
        r"(?:VLAN|vlan)\s*(?:ID)?\s*[:：]?\s*(\d+).*?Line\s+profile",
        text,
        re.I | re.S,
    )
    if m_vlan:
        return int(m_vlan.group(1))
    m_map = re.search(
        r"Mapping\s+VLAN[^\n]*\n(?:.*\n){0,12}?\s*\d+\s+(\d+)\s",
        text,
        re.I,
    )
    if m_map:
        return int(m_map.group(1))
    return None


def parse_by_sn_output(text: str, sn: str) -> OntBySn | None:
    """Extrai Line profile ID, F/S/P e ONT-ID da saída do display ont info by-sn."""
    text = lo._strip_ansi_str(text.replace("\ufeff", "").replace("\u00a0", " "))
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    frame = slot = port = ont_id = None
    sn_norm = norm_sn(sn)
    sn_tail = sn_norm[-8:] if len(sn_norm) >= 8 else sn_norm

    m_alt = re.search(
        r"(\d+)\s*/\s*(\d+)\s*/\s*(\d+)\s+(\d+)\s+([0-9A-Fa-f]{4,})",
        text,
        re.I,
    )
    if m_alt and sn_tail and sn_tail not in m_alt.group(5).upper():
        if not _sn_in_olt_text(text, sn):
            m_alt = None
    m_fsp = re.search(
        r"(?:F/S/P|In\s+port|GPON\s+port)\s*[:：]?\s*(\d+)\s*/\s*(\d+)\s*/\s*(\d+)",
        text,
        re.I,
    )
    if m_fsp:
        frame, slot, port = int(m_fsp.group(1)), int(m_fsp.group(2)), int(m_fsp.group(3))
    elif m_alt:
        frame, slot, port = int(m_alt.group(1)), int(m_alt.group(2)), int(m_alt.group(3))

    ont_id = _first_int(
        [
            r"ONT[-\s]*ID\s*[:：]?\s*(\d+)",
            r"ONT\s+No\.?\s*[:：]?\s*(\d+)",
            r"ONT\s+number\s*[:：]?\s*(\d+)",
        ],
        text,
    )
    if ont_id is None and m_alt:
        ont_id = int(m_alt.group(4))

    line_id = _extract_line_profile_id(text)

    if frame is None and _sn_in_olt_text(text, sn):
        m_fsp2 = re.search(
            r"(?:F/S/P|In\s+port|GPON\s+port)\s*[:：]?\s*(\d+)\s*/\s*(\d+)\s*/\s*(\d+)",
            text,
            re.I,
        )
        if m_fsp2:
            frame, slot, port = (
                int(m_fsp2.group(1)),
                int(m_fsp2.group(2)),
                int(m_fsp2.group(3)),
            )
        if ont_id is None:
            ont_id = _first_int(
                [r"ONT[-\s]*ID\s*[:：]?\s*(\d+)", r"ONT\s+No\.?\s*[:：]?\s*(\d+)"],
                text,
            )
        if line_id is None:
            line_id = _first_int(
                [r"Line\s+profile\s+ID\s*[:：]?\s*(\d+)"],
                text,
            )

    if None in (frame, slot, port, ont_id):
        return None
    if line_id is None:
        return None
    if not _sn_in_olt_text(text, sn):
        return None
    return OntBySn(
        sn=norm_sn(sn),
        line_profile_id=line_id,
        frame=frame,
        slot=slot,
        port=port,
        ont_id=ont_id,
    )


def build_delete_cmds_for_one(
    info: OntBySn, profile: lo.OltProfile | None = None
) -> list[str]:
    """Por ONU: undo → interface gpon → ont delete → quit (volta ao config#)."""
    gem = profile.gemport if profile else GEMPORT
    if profile and profile.cmd_deletar.strip():
        custom = _expand_cmd_lines(
            profile.cmd_deletar,
            {
                "{sn}": info.sn,
                "{vlan}": str(info.line_profile_id),
                "{line_profile_id}": str(info.line_profile_id),
                "{frame}": str(info.frame),
                "{slot}": str(info.slot),
                "{port}": str(info.port),
                "{fsp}": info.fsp,
                "{fs}": info.fs,
                "{ont_id}": str(info.ont_id),
                "{gemport}": str(gem),
            },
        )
        if custom:
            return custom
    return [
        f"undo service-port vlan {info.line_profile_id} gpon {info.fsp} ont {info.ont_id} gemport {gem}",
        f"interface gpon {info.fs}",
        f"ont delete {info.port} {info.ont_id}",
        "quit",
    ]


def build_delete_cmds_batch(
    infos: list[OntBySn], profile: lo.OltProfile | None = None
) -> list[str]:
    """Uma sequência por ONU; quit após cada delete (próxima pode ser outra porta)."""
    lines: list[str] = []
    for info in infos:
        lines.extend(build_delete_cmds_for_one(info, profile))
    return lines


def parse_zte_by_sn_output(text: str, sn: str) -> OntZteBySn | None:
    """Extrai pon_id e onu_numero (C350/C610/C320: gpon-onu_ ou gpon_onu-)."""
    text = lo._strip_ansi_str(text.replace("\ufeff", "").replace("\u00a0", " "))
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    patterns = (
        r"gpon[-_]onu[-_](\d+/\d+/\d+)\s*:\s*(\d+)",
        r"gpon_onu-(\d+/\d+/\d+)\s*:\s*(\d+)",
        r"gpon-onu_(\d+/\d+/\d+)\s*:\s*(\d+)",
    )
    m = None
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            break
    if not m:
        return None
    return OntZteBySn(sn=norm_onu_sn(sn), pon_id=m.group(1), onu_numero=int(m.group(2)))


def build_zte_delete_cmds_for_one(
    info: OntZteBySn, profile: lo.OltProfile | None = None
) -> list[str]:
    if profile and profile.cmd_deletar.strip():
        custom = _expand_cmd_lines(
            profile.cmd_deletar,
            {
                "{sn}": info.sn,
                "{pon_id}": info.pon_id,
                "{onu_numero}": str(info.onu_numero),
            },
        )
        if custom:
            return custom
    return [
        f"interface gpon-olt_{info.pon_id}",
        f"no onu {info.onu_numero}",
        "exit",
    ]


def _delete_ok_zte(saida: str) -> bool:
    low = saida.lower()
    if "unknown command" in low or re.search(r"%\s*error", saida, re.I):
        return False
    if "invalid input" in low or "bad command" in low:
        return False
    if re.search(r"%\s*\w", saida) and "no onu" not in low:
        return False
    return "no onu" in low


def _format_found_line(info: OnuFound) -> str:
    if isinstance(info, OntZteBySn):
        return f"gpon-olt_{info.pon_id} onu {info.onu_numero}"
    return f"{info.fsp} ont {info.ont_id}"


def _out_needs_confirm_y(text: str) -> bool:
    low = text.lower()
    return (
        "(y/n)" in low
        or "[y/n]" in low
        or "yes or no" in low
        or "are you sure" in low
        or "release service virtual port" in low
    )


def _drain_chan(chan) -> None:
    t0 = time.time()
    try:
        while chan.recv_ready() and time.time() - t0 < 0.25:
            chan.recv(65536)
    except Exception:
        pass


def _read_fast(chan, *, idle_end: float = 0.32, max_total: float = 25.0) -> str:
    """Leitura curta sem fase tail longa (comandos rápidos)."""
    return lo._read_channel_shell(
        chan, idle_end=idle_end, max_total=max_total, tail_phase=False
    )


def _read_until_markers(
    chan,
    acc: str,
    markers: tuple[str, ...],
    *,
    idle_end: float = 0.28,
    max_total: float = 90.0,
) -> str:
    """Lê até aparecer algum marcador na saída ou timeout."""
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


def _at_config_prompt(text: str) -> bool:
    low = text.lower()
    if "config-if-gpon" in low:
        return False
    return "(config)#" in low or low.rstrip().endswith("config)#")


def _at_privileged_prompt(text: str) -> bool:
    """Prompt hostname# (fora de config e de interface gpon)."""
    if _at_config_prompt(text) or "config-if-gpon" in text.lower():
        return False
    lines = [ln.strip() for ln in text.replace("\r", "").split("\n") if ln.strip()]
    if not lines:
        return False
    last = lines[-1]
    return bool(re.search(r"#[^)]*$", last) and "(config)" not in last)


def _sync_prompt(chan, *, max_total: float = 5.0) -> str:
    chan.send(b"\n")
    return _read_fast(chan, idle_end=0.38, max_total=max_total)


def _ensure_config_mode(chan, login_password: str | None = None) -> None:
    """
    Garante (config)# antes de undo/interface.
    Nunca envia quit a partir de (config)# — isso cai para # e os comandos perdem espaços/falham.
    """
    acc = _sync_prompt(chan)
    for _ in range(8):
        if _at_config_prompt(acc):
            return
        low = acc.lower()
        if "config-if-gpon" in low:
            acc = lo._send_and_read_shell(
                chan, "quit", pre_wait=0.05, idle_end=0.4, max_total=8.0, tail_phase=False
            )
            acc += _sync_prompt(chan)
            continue
        if "log out" in low and ("(y/n)" in low or "[y/n]" in low):
            chan.send(b"n\n")
            acc = _read_fast(chan, idle_end=0.35, max_total=4.0)
            continue
        if "more (" in low or "---- more" in low:
            acc = _send_ctrl_c(chan) + _sync_prompt(chan)
            continue
        if _at_privileged_prompt(acc):
            acc = lo._send_and_read_shell(
                chan, "config", pre_wait=0.05, idle_end=0.45, max_total=12.0, tail_phase=False
            )
            if _at_config_prompt(acc):
                return
            acc += _sync_prompt(chan)
            continue
        if re.search(r">\s*$", acc, re.M) and "(config)" not in low:
            if login_password:
                _enable_config_fast(chan, login_password)
            else:
                lo._send_and_read_shell(
                    chan, "enable", pre_wait=0.05, idle_end=0.4, max_total=12.0, tail_phase=False
                )
                lo._send_and_read_shell(
                    chan, "config", pre_wait=0.05, idle_end=0.4, max_total=12.0, tail_phase=False
                )
            acc = _sync_prompt(chan)
            continue
        acc += _sync_prompt(chan)


def _send_delete_cmd_on_chan(chan, cmd: str) -> str:
    """Envia exclusão; confirma y/n; leituras curtas até prompt/marcador."""
    low = cmd.strip().lower()
    is_undo = low.startswith("undo service-port")
    is_iface = low.startswith("interface gpon")
    is_ont_del = low.startswith("ont delete")
    is_quit = low == "quit"

    if is_undo:
        out = lo._send_and_read_shell(
            chan, cmd, pre_wait=0.05, idle_end=0.5, max_total=30.0, tail_phase=False
        )
        if _out_needs_confirm_y(out) and "deleting end" not in out.lower():
            chan.send(b"y\n")
            out = _read_until_markers(
                chan,
                out,
                ("deleting end", "have been deleted", "failure", "unknown command"),
                idle_end=0.4,
                max_total=180.0,
            )
        return out

    if is_iface:
        out = lo._send_and_read_shell(
            chan, cmd, pre_wait=0.1, idle_end=0.45, max_total=15.0, tail_phase=False
        )
        out = _wait_gpon_interface_prompt(chan, out, timeout=8.0)
        if "config-if-gpon" not in out.lower():
            _ensure_config_mode(chan)
            out = lo._send_and_read_shell(
                chan, cmd, pre_wait=0.1, idle_end=0.45, max_total=15.0, tail_phase=False
            )
            out = _wait_gpon_interface_prompt(chan, out, timeout=8.0)
        return out

    if is_ont_del:
        time.sleep(0.2)
        out = lo._send_and_read_shell(
            chan, cmd, pre_wait=0.1, idle_end=0.5, max_total=35.0, tail_phase=False
        )
        return _read_until_markers(
            chan,
            out,
            ("success:", "failure", "unknown command"),
            idle_end=0.35,
            max_total=25.0,
        )

    out = lo._send_and_read_shell(
        chan, cmd, pre_wait=0.05, idle_end=0.35, max_total=10.0, tail_phase=False
    )
    if is_quit and "log out" in out.lower() and _out_needs_confirm_y(out):
        chan.send(b"n\n")
        out += _read_fast(chan, idle_end=0.35, max_total=5.0)
    return _read_until_markers(chan, out, ("(config)#", "config)#"), idle_end=0.3, max_total=8.0)


def _erro_curto(saida: str) -> str:
    """Uma linha curta de erro a partir da saída da OLT."""
    for line in saida.replace("\r", "").split("\n"):
        t = line.strip()
        if not t:
            continue
        if t.startswith("%") or "failure" in t.lower() or "unknown command" in t.lower():
            return t[:120]
    if "have been deleted:  0" in saida or "success: 0" in saida.lower():
        return "OLT não confirmou exclusão"
    return "falha na OLT"


def _delete_ok(saida: str) -> bool:
    low = saida.lower()
    if "unknown command" in low or re.search(r"%\s*\w", saida):
        return False
    if "success: 1" in low or "success:1" in low:
        return True
    if "have been deleted:  1" in saida or "have been deleted: 1" in low:
        return True
    if "failure" in low:
        return False
    return "ont delete" in low and "success" in low


def _delete_one_onu(
    chan,
    info: OntBySn,
    login_password: str | None = None,
    profile: lo.OltProfile | None = None,
) -> tuple[bool, str, str]:
    """Retorna (ok, mensagem_erro, saída_bruta_OLT)."""
    _ensure_config_mode(chan, login_password)
    saida: list[str] = []
    try:
        for cmd in build_delete_cmds_for_one(info, profile):
            part = _send_delete_cmd_on_chan(chan, cmd)
            saida.append(f">>> {cmd}\n{part}")
    except KeyboardInterrupt:
        raise
    except Exception as e:
        _ensure_config_mode(chan, login_password)
        return False, str(e)[:80], ""
    texto = "\n".join(saida)
    if _delete_ok(texto):
        _ensure_config_mode(chan, login_password)
        return True, "", texto
    _ensure_config_mode(chan, login_password)
    return False, _erro_curto(texto), texto


def _at_zte_config_prompt(text: str) -> bool:
    low = text.lower()
    if "config-if-gpon-olt" in low:
        return False
    return "(config)#" in low or low.rstrip().endswith("config)#")


def _at_zte_gpon_olt_prompt(text: str) -> bool:
    return "config-if-gpon-olt" in text.lower()


def _enable_config_zte(chan, password: str) -> None:
    out = lo._send_and_read_shell(
        chan, "enable", pre_wait=0, idle_end=0.45, max_total=12.0, tail_phase=False
    )
    if "assword" in out.lower():
        lo._send_and_read_shell(
            chan, password, pre_wait=0, idle_end=0.45, max_total=10.0, tail_phase=False
        )
    lo._send_and_read_shell(
        chan, "conf t", pre_wait=0, idle_end=0.45, max_total=12.0, tail_phase=False
    )


def _ensure_config_mode_zte(chan, login_password: str | None = None) -> None:
    acc = _sync_prompt(chan)
    for _ in range(8):
        if _at_zte_config_prompt(acc):
            return
        low = acc.lower()
        if _at_zte_gpon_olt_prompt(acc):
            acc = lo._send_and_read_shell(
                chan, "exit", pre_wait=0.05, idle_end=0.4, max_total=8.0, tail_phase=False
            )
            acc += _sync_prompt(chan)
            continue
        if "more" in low and "(" in low:
            acc = _send_ctrl_c(chan) + _sync_prompt(chan)
            continue
        if _at_privileged_prompt(acc):
            lo._send_and_read_shell(
                chan, "conf t", pre_wait=0.05, idle_end=0.45, max_total=12.0, tail_phase=False
            )
            acc = _sync_prompt(chan)
            continue
        if re.search(r">\s*$", acc, re.M) and "(config)" not in low:
            if login_password:
                _enable_config_zte(chan, login_password)
            acc = _sync_prompt(chan)
            continue
        acc += _sync_prompt(chan)


def _send_delete_cmd_zte_on_chan(chan, cmd: str) -> str:
    low = cmd.strip().lower()
    is_iface = low.startswith("interface gpon-olt")
    is_no_onu = low.startswith("no onu")
    is_exit = low == "exit"

    if is_iface:
        out = lo._send_and_read_shell(
            chan, cmd, pre_wait=0.08, idle_end=0.45, max_total=15.0, tail_phase=False
        )
        return _read_until_markers(
            chan, out, ("config-if-gpon-olt", "unknown command", "%error"),
            idle_end=0.35,
            max_total=12.0,
        )

    if is_no_onu:
        return lo._send_and_read_shell(
            chan, cmd, pre_wait=0.08, idle_end=0.5, max_total=25.0, tail_phase=False
        )

    out = lo._send_and_read_shell(
        chan, cmd, pre_wait=0.05, idle_end=0.35, max_total=10.0, tail_phase=False
    )
    if is_exit:
        return _read_until_markers(chan, out, ("(config)#", "config)#"), idle_end=0.3, max_total=8.0)
    return out


def lookup_sn_zte_on_chan(
    chan,
    sn: str,
    login_password: str | None = None,
    profile: lo.OltProfile | None = None,
) -> tuple[OntZteBySn | None, str]:
    cmd = build_zte_by_sn_cmd(sn, profile)
    _ensure_config_mode_zte(chan, login_password)
    out = lo._send_and_read_shell(
        chan, cmd, pre_wait=0, idle_end=0.5, max_total=25.0, tail_phase=False
    )
    out_b = out.encode("utf-8", errors="replace")
    for m in MORE_MARKERS_ZTE:
        if m in out_b:
            chan.send(b" ")
            out += _read_fast(chan, idle_end=0.3, max_total=6.0)
            out_b = out.encode("utf-8", errors="replace")
    _ensure_config_mode_zte(chan, login_password)
    info = parse_zte_by_sn_output(out, sn)
    return info, out


MORE_MARKERS_ZTE = (b"--More--", b"---- More ----")


def _delete_one_onu_zte(
    chan,
    info: OntZteBySn,
    login_password: str | None = None,
    profile: lo.OltProfile | None = None,
) -> tuple[bool, str, str]:
    _ensure_config_mode_zte(chan, login_password)
    saida: list[str] = []
    try:
        for cmd in build_zte_delete_cmds_for_one(info, profile):
            part = _send_delete_cmd_zte_on_chan(chan, cmd)
            saida.append(f">>> {cmd}\n{part}")
    except KeyboardInterrupt:
        raise
    except Exception as e:
        _ensure_config_mode_zte(chan, login_password)
        return False, str(e)[:80], ""
    texto = "\n".join(saida)
    if _delete_ok_zte(texto):
        _ensure_config_mode_zte(chan, login_password)
        return True, "", texto
    _ensure_config_mode_zte(chan, login_password)
    return False, _erro_curto(texto), texto


def _zte_cleanup_session(chan) -> None:
    for cmd in ("exit", "exit"):
        try:
            chan.send(cmd.encode("utf-8") + b"\n")
            _read_fast(chan, idle_end=0.35, max_total=6.0)
        except Exception:
            break


def _plink_body_with_confirm_y(cmds: list[str]) -> list[str]:
    """Script Plink: após undo service-port envia y (confirmação da OLT)."""
    out: list[str] = []
    for cmd in cmds:
        out.append(cmd)
        if cmd.strip().lower().startswith("undo service-port"):
            out.append("y")
    return out


def _send_ctrl_c(chan) -> str:
    try:
        chan.send(b"\x03")
    except Exception:
        return ""
    return _read_fast(chan, idle_end=0.22, max_total=3.0)


def _huawei_fetch_by_sn(chan, cmd: str, sn: str) -> str:
    """
    MA5800: display ont info by-sn → { <cr>||<K> } → Enter → dados (+ More com espaço).
    """
    t0 = time.time()
    while chan.recv_ready() and time.time() - t0 < 0.35:
        chan.recv(65536)
    chan.send(cmd.encode("utf-8", errors="replace") + b"\n")

    buf = b""
    t_wait = time.time()
    while time.time() - t_wait < 6.0:
        if chan.recv_ready():
            buf += chan.recv(65536)
        if lo.HUAWEI_PAGE_CRK.search(buf):
            break
        if b"F/S/P" in buf or b"In port" in buf:
            break
        if b"Failure" in buf or b"does not exist" in buf.lower():
            break
        if b"% Unknown" in buf or b"parameter error" in buf.lower():
            break
        time.sleep(0.04)

    if lo.HUAWEI_PAGE_CRK.search(buf) or (
        b"F/S/P" not in buf
        and b"Failure" not in buf
        and b"does not exist" not in buf.lower()
    ):
        chan.send(b"\r\n")

    rest = lo._read_channel_shell(
        chan, idle_end=1.0, max_total=180.0, tail_phase=True, tail_window=4.0
    )
    return lo._strip_ansi_str(buf.decode("utf-8", errors="replace") + rest)


def _page_by_sn(chan, sn: str) -> str:
    """Pagina até reconhecer F/S/P + Line profile ou esgotar tentativas."""
    parts: list[str] = []
    for _ in range(BY_SN_PAGE_SPACES):
        try:
            chan.send(b" ")
        except Exception:
            break
        parts.append(_read_fast(chan, idle_end=0.45, max_total=18.0))
        merged = "".join(parts)
        if parse_by_sn_output(merged, sn):
            break
        if "---- More ----" not in merged and "More (" not in merged:
            if _sn_in_olt_text(merged, sn) and "F/S/P" in merged:
                break
    return "".join(parts)


def _enable_config_fast(chan, password: str) -> None:
    out = lo._send_and_read_shell(
        chan, "enable", pre_wait=0, idle_end=0.4, max_total=12.0, tail_phase=False
    )
    if "assword" in out.lower():
        lo._send_and_read_shell(
            chan, password, pre_wait=0, idle_end=0.4, max_total=10.0, tail_phase=False
        )
    lo._send_and_read_shell(
        chan, "config", pre_wait=0, idle_end=0.4, max_total=12.0, tail_phase=False
    )


def lookup_sn_on_chan(
    chan,
    sn: str,
    login_password: str | None = None,
    profile: lo.OltProfile | None = None,
) -> tuple[OntBySn | None, str]:
    _ensure_config_mode(chan, login_password)
    parts: list[str] = []
    info: OntBySn | None = None
    for variant in huawei_sn_variants(sn):
        cmd = build_by_sn_cmd(variant, profile)
        out = _huawei_fetch_by_sn(chan, cmd, sn)
        if parse_by_sn_output(out, sn) is None:
            out += _page_by_sn(chan, sn)
        out += _send_ctrl_c(chan)
        parts.append(f"=== tentativa: {variant} ===\n{out}")
        info = parse_by_sn_output(out, sn)
        if info:
            break
        _ensure_config_mode(chan, login_password)
    return info, "\n".join(parts)


def _plink_putty_dirs() -> list[Path]:
    return [app_dir(), lo._script_dir()]


def _find_plink_local() -> str | None:
    for base in _plink_putty_dirs():
        for name in ("plink.exe", "PLINK.EXE"):
            p = base / name
            if p.is_file():
                return str(p)
    return lo._find_plink()


def _find_putty_local() -> str | None:
    for base in _plink_putty_dirs():
        for name in ("putty.exe", "PUTTY.EXE"):
            p = base / name
            if p.is_file():
                return str(p)
    return lo._find_putty()


def _find_ssh_cli_exe() -> tuple[str | None, bool]:
    """Retorna (caminho, use_plink_batch). Preferência: plink.exe, depois putty.exe."""
    plink = _find_plink_local()
    if plink:
        return plink, True
    putty = _find_putty_local()
    if putty:
        return putty, False
    return None, False


def _erro_ssh_com_causa(exc: BaseException) -> str:
    causa = str(exc).strip() or exc.__class__.__name__
    dica = (
        "\n\nVerifique: VPN/rede ate a OLT, IP correto, firewall.\n"
        "Na mesma pasta do programa coloque plink.exe ou putty.exe "
        "(ZIP do PuTTY: https://www.chiark.greenend.org.uk/~sgtatham/putty/latest.html)."
    )
    return f"Conexao SSH falhou: {causa}{dica}"


def _run_paramiko_work(
    host: str,
    port: int,
    username: str,
    password: str,
    work: Callable,
    *,
    vendor: str = "huawei",
) -> object:
    transport = lo._ssh_connect_olt(
        host, port, username, password, legacy=(vendor == "zte")
    )
    try:
        chan = transport.open_session()
        chan.get_pty("vt100", 320, 56, 0, 0)
        chan.invoke_shell()
        chan.settimeout(0.0)
        lo._read_channel_shell(chan, idle_end=0.5, max_total=10.0, tail_phase=False)
        if vendor == "zte":
            _enable_config_zte(chan, password)
        else:
            _enable_config_fast(chan, password)
        result = work(chan)
        if vendor == "zte":
            _zte_cleanup_session(chan)
        else:
            lo._huawei_cleanup_session(chan)
        return result
    finally:
        transport.close()


def _run_plink_lines(
    host: str,
    port: int,
    username: str,
    password: str,
    body_lines: list[str],
    exe: str,
    *,
    use_batch: bool,
    vendor: str = "huawei",
) -> str:
    lines: list[str] = []
    if vendor == "zte":
        lines.extend(lo._zte_cli_prefix_lines())
    else:
        lines.extend(lo._huawei_cli_prefix_lines())
    lines.extend(body_lines)
    if vendor == "zte":
        lines.extend(["exit", "exit"])
    else:
        lines.extend(lo._huawei_cli_suffix_lines())

    with tempfile.NamedTemporaryFile(
        "w", suffix=".txt", delete=False, encoding="utf-8", newline="\n"
    ) as tf:
        tf.write("\n".join(lines) + "\n")
        script_path = tf.name

    try:
        import os
        import subprocess

        cmd = [
            exe,
            "-ssh",
            f"{username}@{host}",
            "-P",
            str(port),
            "-pw",
            password,
        ]
        if use_batch:
            cmd.append("-batch")
        cmd.extend(["-m", script_path])
        run_kw: dict = {
            "capture_output": True,
            "timeout": 1800,
            "encoding": "utf-8",
            "errors": "replace",
        }
        if sys.platform == "win32" and hasattr(subprocess, "CREATE_NO_WINDOW"):
            run_kw["creationflags"] = subprocess.CREATE_NO_WINDOW
        proc = subprocess.run(cmd, check=False, **run_kw)
        return (proc.stdout or "") + (proc.stderr or "")
    finally:
        try:
            import os

            os.unlink(script_path)
        except OSError:
            pass


def _run_telnet_lines(
    host: str,
    port: int,
    username: str,
    password: str,
    body_lines: list[str],
) -> str:
    if lo.Telnet is None:
        raise RuntimeError("Telnet indisponível.")
    tn = lo.Telnet()
    tn.open(host, port, timeout=30)
    acc = b""

    def wait_prompt(timeout: float = 45.0) -> None:
        nonlocal acc
        acc += lo._telnet_drain(tn, total_timeout=timeout, idle_end=0.8)

    try:
        wait_prompt(25.0)
        low = acc.lower()
        if b"ogin:" in low or b"username:" in low:
            tn.write(username.encode("utf-8", errors="replace") + b"\n")
            wait_prompt(25.0)
            low = acc.lower()
        if b"assword:" in low:
            tn.write(password.encode("utf-8", errors="replace") + b"\n")
            wait_prompt(45.0)

        tn.write(b"enable\n")
        wait_prompt(25.0)
        tail = acc[-1200:].lower() if len(acc) > 1200 else acc.lower()
        if b"assword" in tail:
            tn.write(password.encode("utf-8", errors="replace") + b"\n")
            wait_prompt(35.0)
        tn.write(b"config\n")
        wait_prompt(45.0)

        for line in body_lines:
            line = line.strip()
            if not line:
                continue
            if line == "\x03" or line.upper() == "CTRL+C":
                tn.write(b"\x03")
                acc += lo._telnet_drain(tn, total_timeout=8.0, idle_end=0.4, crk_first_ref=None)
                continue
            tn.write(line.encode("utf-8", errors="replace") + b"\n")
            if line.startswith("display ont info by-sn"):
                acc += lo._telnet_drain(
                    tn, total_timeout=120.0, idle_end=1.0, crk_first_ref=[True]
                )
                for _ in range(BY_SN_PAGE_SPACES):
                    tn.write(b" ")
                acc += lo._telnet_drain(
                    tn, total_timeout=25.0, idle_end=0.6, crk_first_ref=None
                )
                tn.write(b"\x03")
                acc += lo._telnet_drain(tn, total_timeout=8.0, idle_end=0.4, crk_first_ref=None)
            elif line.lower().startswith("undo service-port"):
                acc += lo._telnet_drain(tn, total_timeout=120.0, idle_end=2.0, crk_first_ref=None)
                if b"(y/n)" in acc.lower() or b"are you sure" in acc.lower():
                    tn.write(b"y\n")
                    acc += lo._telnet_drain(tn, total_timeout=300.0, idle_end=3.0, crk_first_ref=None)
            elif line.lower().startswith("interface gpon"):
                acc += lo._telnet_drain(tn, total_timeout=30.0, idle_end=1.2, crk_first_ref=None)
            elif line.lower().startswith("ont delete"):
                time.sleep(0.5)
                acc += lo._telnet_drain(tn, total_timeout=90.0, idle_end=1.2, crk_first_ref=None)
            else:
                acc += lo._telnet_drain(tn, total_timeout=90.0, idle_end=0.9, crk_first_ref=None)

        for end_cmd in (b"quit\n", b"quit\n", b"y\n"):
            tn.write(end_cmd)
            acc += lo._telnet_drain(tn, total_timeout=10.0, idle_end=0.4, crk_first_ref=None)

        return lo._strip_ansi(acc).decode("utf-8", errors="replace")
    finally:
        try:
            tn.close()
        except Exception:
            pass


def _expand_body_for_plink(
    sns: list[str],
    delete_infos: list[OntBySn] | None,
    profile: lo.OltProfile | None = None,
) -> list[str]:
    """Linhas para script Plink: by-sn + espaços + ctrl+c por SN; depois deletes."""
    lines: list[str] = []
    for sn in sns:
        for variant in huawei_sn_variants(sn):
            lines.append(build_by_sn_cmd(variant, profile))
            lines.append("")  # Enter no { <cr>||<K> }
            for _ in range(BY_SN_PAGE_SPACES):
                lines.append(" ")
            lines.append("\x03")
    if delete_infos:
        lines.extend(
            _plink_body_with_confirm_y(build_delete_cmds_batch(delete_infos, profile))
        )
    return lines


def _expand_body_for_plink_zte(
    sns: list[str],
    delete_infos: list[OntZteBySn] | None,
    profile: lo.OltProfile | None = None,
) -> list[str]:
    lines: list[str] = []
    for sn in sns:
        lines.append(build_zte_by_sn_cmd(sn, profile))
        lines.append("")
    if delete_infos:
        for info in delete_infos:
            lines.extend(build_zte_delete_cmds_for_one(info, profile))
    return lines


def _run_all_paramiko(profile: lo.OltProfile, sns: list[str]) -> RunAllResult:
    """Uma sessão SSH: por SN — localiza e apaga antes da próxima."""
    if profile.vendor == "zte":
        return _run_all_paramiko_zte(profile, sns)
    out = RunAllResult(vendor="huawei")

    def work(chan) -> None:
        pwd = profile.password
        for sn in sns:
            _raise_if_cancelled()
            print(f"  {sn}… ", end="", flush=True)
            info, raw = lookup_sn_on_chan(chan, sn, pwd, profile)
            out.lookup_raw[sn] = raw
            if not info:
                out.not_found[sn] = raw
                out.entries.append((sn, "Erro: não localizado na OLT"))
                print("não encontrado")
                continue
            out.found[sn] = info
            print(f"OK {_format_found_line(info)} — ", end="", flush=True)
            raw_del = ""
            try:
                ok_del, err, raw_del = _delete_one_onu(chan, info, pwd, profile)
            except KeyboardInterrupt:
                out.delete_raw[sn] = raw_del
                out.entries.append((sn, "Erro: interrompido"))
                print("interrompido")
                raise
            except Exception as e:
                ok_del, err, raw_del = False, str(e)[:80], ""
            out.delete_raw[sn] = raw_del
            if ok_del:
                out.entries.append((sn, "Delet"))
                print("Delet")
            else:
                out.entries.append((sn, f"Erro: {err}"))
                print(f"Erro: {err}")

    try:
        _run_paramiko_work(
            profile.host,
            profile.port,
            profile.user,
            profile.password,
            work,
            vendor="huawei",
        )
    except KeyboardInterrupt:
        print("\nInterrompido pelo utilizador.")
        for sn in sns:
            if not any(r[0] == sn for r in out.entries):
                out.entries.append((sn, "Erro: interrompido"))
        raise
    return out


def _run_all_paramiko_zte(profile: lo.OltProfile, sns: list[str]) -> RunAllResult:
    out = RunAllResult(vendor="zte")

    def work(chan) -> None:
        pwd = profile.password
        for sn in sns:
            _raise_if_cancelled()
            print(f"  {sn}… ", end="", flush=True)
            info, raw = lookup_sn_zte_on_chan(chan, sn, pwd, profile)
            out.lookup_raw[sn] = raw
            if not info:
                out.not_found[sn] = raw
                out.entries.append((sn, "Erro: não localizado na OLT"))
                print("não encontrado")
                continue
            out.found[sn] = info
            print(f"OK {_format_found_line(info)} — ", end="", flush=True)
            raw_del = ""
            try:
                ok_del, err, raw_del = _delete_one_onu_zte(chan, info, pwd, profile)
            except KeyboardInterrupt:
                out.delete_raw[sn] = raw_del
                out.entries.append((sn, "Erro: interrompido"))
                print("interrompido")
                raise
            except Exception as e:
                ok_del, err, raw_del = False, str(e)[:80], ""
            out.delete_raw[sn] = raw_del
            if ok_del:
                out.entries.append((sn, "Delet"))
                print("Delet")
            else:
                out.entries.append((sn, f"Erro: {err}"))
                print(f"Erro: {err}")

    try:
        _run_paramiko_work(
            profile.host,
            profile.port,
            profile.user,
            profile.password,
            work,
            vendor="zte",
        )
    except KeyboardInterrupt:
        print("\nInterrompido pelo utilizador.")
        for sn in sns:
            if not any(r[0] == sn for r in out.entries):
                out.entries.append((sn, "Erro: interrompido"))
        raise
    return out


def _run_all_telnet(profile: lo.OltProfile, sns: list[str]) -> RunAllResult:
    """Telnet: uma conexão — por SN localiza e apaga."""
    if profile.vendor == "zte":
        return _run_all_telnet_zte(profile, sns)
    if lo.Telnet is None:
        raise RuntimeError("Telnet indisponível.")
    tn = lo.Telnet()
    tn.open(profile.host, profile.port, timeout=30)
    acc = b""
    out = RunAllResult(vendor="huawei")

    def wait_prompt(timeout: float = 20.0, idle: float = 0.45) -> None:
        nonlocal acc
        acc += lo._telnet_drain(tn, total_timeout=timeout, idle_end=idle)

    def telnet_ensure_config() -> None:
        tn.write(b"\n")
        wait_prompt(3.0, 0.32)
        tail = acc[-2500:].lower()
        if b"(config)#" in tail and b"config-if-gpon" not in tail:
            return
        if b"config-if-gpon" in tail:
            tn.write(b"quit\n")
            wait_prompt(4.0, 0.32)
        if b"log out" in acc[-1200:].lower() and b"(y/n)" in acc[-1200:].lower():
            tn.write(b"n\n")
            wait_prompt(3.0, 0.3)
        if b"(config)#" not in acc[-2500:]:
            tn.write(b"config\n")
            wait_prompt(6.0, 0.35)

    try:
        wait_prompt(25.0)
        low = acc.lower()
        if b"ogin:" in low or b"username:" in low:
            tn.write(profile.user.encode("utf-8", errors="replace") + b"\n")
            wait_prompt(25.0)
        if b"assword:" in acc.lower():
            tn.write(profile.password.encode("utf-8", errors="replace") + b"\n")
            wait_prompt(45.0)
        tn.write(b"enable\n")
        wait_prompt(25.0)
        if b"assword" in acc[-1200:].lower():
            tn.write(profile.password.encode("utf-8", errors="replace") + b"\n")
            wait_prompt(35.0)
        tn.write(b"config\n")
        wait_prompt(45.0)

        for sn in sns:
            _raise_if_cancelled()
            print(f"  {sn}… ", end="", flush=True)
            mark = len(acc)
            chunk = ""
            info = None
            for variant in huawei_sn_variants(sn):
                tn.write(
                    build_by_sn_cmd(variant, profile).encode("utf-8", errors="replace") + b"\n"
                )
                wait_prompt(8.0, 0.4)
                chunk = lo._strip_ansi(acc[mark:]).decode("utf-8", errors="replace")
                if b"F/S/P" not in acc[mark:] and b"Failure" not in acc[mark:]:
                    tn.write(b"\n")
                    wait_prompt(35.0, 0.5)
                    chunk = lo._strip_ansi(acc[mark:]).decode("utf-8", errors="replace")
                if parse_by_sn_output(chunk, sn) is None:
                    for _ in range(BY_SN_PAGE_SPACES):
                        tn.write(b" ")
                        wait_prompt(10.0, 0.45)
                        chunk = lo._strip_ansi(acc[mark:]).decode("utf-8", errors="replace")
                        if parse_by_sn_output(chunk, sn):
                            break
                info = parse_by_sn_output(chunk, sn)
                if info:
                    break
                tn.write(b"\x03")
                wait_prompt(3.0, 0.3)
                telnet_ensure_config()
            tn.write(b"\x03")
            wait_prompt(3.0, 0.3)
            telnet_ensure_config()
            chunk = lo._strip_ansi(acc[mark:]).decode("utf-8", errors="replace")
            if info is None:
                info = parse_by_sn_output(chunk, sn)
            out.lookup_raw[sn] = chunk
            if not info:
                out.not_found[sn] = chunk
                out.entries.append((sn, "Erro: não localizado na OLT"))
                print("não encontrado")
                continue
            out.found[sn] = info
            print(f"OK {_format_found_line(info)} — ", end="", flush=True)
            telnet_ensure_config()
            mark = len(acc)
            cmd_log: list[str] = []
            for cmd in build_delete_cmds_for_one(info, profile):
                cmd_log.append(f">>> {cmd}")
                tn.write(cmd.encode("utf-8", errors="replace") + b"\n")
                low = cmd.lower()
                if low.startswith("undo service-port"):
                    wait_prompt(90.0, 0.5)
                    if b"(y/n)" in acc.lower() or b"are you sure" in acc.lower():
                        tn.write(b"y\n")
                    wait_prompt(120.0, 0.55)
                elif low.startswith("interface gpon"):
                    wait_prompt(8.0, 0.4)
                elif low.startswith("ont delete"):
                    wait_prompt(15.0, 0.4)
                elif low.strip() == "quit":
                    wait_prompt(5.0, 0.35)
                    if b"log out" in acc[-1500:].lower() and (
                        b"(y/n)" in acc[-1500:].lower() or b"[y/n]" in acc[-1500:].lower()
                    ):
                        tn.write(b"n\n")
                        wait_prompt(3.0, 0.3)
            chunk = lo._strip_ansi(acc[mark:]).decode("utf-8", errors="replace")
            out.delete_raw[sn] = "\n".join(cmd_log) + "\n" + chunk
            if _delete_ok(chunk):
                out.entries.append((sn, "Delet"))
                print("Delet")
            else:
                err = _erro_curto(chunk)
                out.entries.append((sn, f"Erro: {err}"))
                print(f"Erro: {err}")

        for end_cmd in (b"quit\n", b"quit\n", b"y\n"):
            tn.write(end_cmd)
            wait_prompt(8.0)

        return out
    finally:
        try:
            tn.close()
        except Exception:
            pass


def _run_all_telnet_zte(profile: lo.OltProfile, sns: list[str]) -> RunAllResult:
    if lo.Telnet is None:
        raise RuntimeError("Telnet indisponível.")
    tn = lo.Telnet()
    tn.open(profile.host, profile.port, timeout=30)
    acc = b""
    out = RunAllResult(vendor="zte")

    def wait_prompt(timeout: float = 20.0, idle: float = 0.45) -> None:
        nonlocal acc
        acc += lo._telnet_drain(tn, total_timeout=timeout, idle_end=idle)

    def telnet_ensure_config_zte() -> None:
        tn.write(b"\n")
        wait_prompt(3.0, 0.32)
        tail = acc[-2500:].lower()
        if b"(config)#" in tail and b"config-if-gpon-olt" not in tail:
            return
        if b"config-if-gpon-olt" in tail:
            tn.write(b"exit\n")
            wait_prompt(4.0, 0.32)
        if b"(config)#" not in acc[-2500:]:
            tn.write(b"conf t\n")
            wait_prompt(6.0, 0.35)

    try:
        wait_prompt(25.0)
        low = acc.lower()
        if b"ogin:" in low or b"username:" in low:
            tn.write(profile.user.encode("utf-8", errors="replace") + b"\n")
            wait_prompt(25.0)
        if b"assword:" in acc.lower():
            tn.write(profile.password.encode("utf-8", errors="replace") + b"\n")
            wait_prompt(45.0)
        tn.write(b"enable\n")
        wait_prompt(25.0)
        if b"assword" in acc[-1200:].lower():
            tn.write(profile.password.encode("utf-8", errors="replace") + b"\n")
            wait_prompt(35.0)
        tn.write(b"conf t\n")
        wait_prompt(45.0)

        for sn in sns:
            _raise_if_cancelled()
            print(f"  {sn}… ", end="", flush=True)
            mark = len(acc)
            tn.write(
                build_zte_by_sn_cmd(sn, profile).encode("utf-8", errors="replace") + b"\n"
            )
            wait_prompt(15.0, 0.4)
            telnet_ensure_config_zte()
            chunk = lo._strip_ansi(acc[mark:]).decode("utf-8", errors="replace")
            info = parse_zte_by_sn_output(chunk, sn)
            out.lookup_raw[sn] = chunk
            if not info:
                out.not_found[sn] = chunk
                out.entries.append((sn, "Erro: não localizado na OLT"))
                print("não encontrado")
                continue
            out.found[sn] = info
            print(f"OK {_format_found_line(info)} — ", end="", flush=True)
            telnet_ensure_config_zte()
            mark = len(acc)
            cmd_log: list[str] = []
            for cmd in build_zte_delete_cmds_for_one(info, profile):
                cmd_log.append(f">>> {cmd}")
                tn.write(cmd.encode("utf-8", errors="replace") + b"\n")
                low_cmd = cmd.lower()
                if low_cmd.startswith("interface gpon-olt"):
                    wait_prompt(10.0, 0.4)
                elif low_cmd.startswith("no onu"):
                    wait_prompt(15.0, 0.4)
                else:
                    wait_prompt(5.0, 0.35)
            chunk = lo._strip_ansi(acc[mark:]).decode("utf-8", errors="replace")
            out.delete_raw[sn] = "\n".join(cmd_log) + "\n" + chunk
            if _delete_ok_zte(chunk):
                out.entries.append((sn, "Delet"))
                print("Delet")
            else:
                err = _erro_curto(chunk)
                out.entries.append((sn, f"Erro: {err}"))
                print(f"Erro: {err}")

        for end_cmd in (b"exit\n", b"exit\n"):
            tn.write(end_cmd)
            wait_prompt(6.0)
        return out
    finally:
        try:
            tn.close()
        except Exception:
            pass


def _run_all_plink_zte_per_onu(
    profile: lo.OltProfile, sns: list[str], exe: str, *, use_batch: bool
) -> RunAllResult:
    """ZTE via SSH: Plink/PuTTY (Paramiko 3.14 não aceita host key ssh-rsa da C350)."""
    out = RunAllResult(vendor="zte")
    for sn in sns:
        _raise_if_cancelled()
        print(f"  {sn}… ", end="", flush=True)
        lookup_lines = [
            *lo._zte_cli_prefix_lines(),
            build_zte_by_sn_cmd(sn, profile),
            "",
        ]
        raw = _run_plink_lines(
            profile.host,
            profile.port,
            profile.user,
            profile.password,
            lookup_lines,
            exe,
            use_batch=use_batch,
            vendor="zte",
        )
        out.lookup_raw[sn] = raw
        info = parse_zte_by_sn_output(raw, sn)
        if not info:
            out.not_found[sn] = raw
            out.entries.append((sn, "Erro: não localizado na OLT"))
            print("não encontrado")
            continue
        out.found[sn] = info
        print(f"OK {_format_found_line(info)} — ", end="", flush=True)
        del_lines = [
            *lo._zte_cli_prefix_lines(),
            *build_zte_delete_cmds_for_one(info, profile),
        ]
        del_raw = _run_plink_lines(
            profile.host,
            profile.port,
            profile.user,
            profile.password,
            del_lines,
            exe,
            use_batch=use_batch,
            vendor="zte",
        )
        out.delete_raw[sn] = del_raw
        if _delete_ok_zte(del_raw):
            out.entries.append((sn, "Delet"))
            print("Delet")
        else:
            err = _erro_curto(del_raw)
            out.entries.append((sn, f"Erro: {err}"))
            print(f"Erro: {err}")
    return out


def _run_all_zte_ssh(profile: lo.OltProfile, sns: list[str]) -> RunAllResult:
    """ZTE SSH: igual Huawei — Paramiko em segundo plano (sem abrir PuTTY)."""
    try:
        return _run_all_paramiko(profile, sns)
    except Exception as e:
        if not lo._should_fallback_plink(e):
            raise
        exe, batch = _find_ssh_cli_exe()
        if not exe:
            raise RuntimeError(_erro_ssh_com_causa(e)) from e
        print(f"\nAviso: Paramiko falhou; usando {Path(exe).name}…\n", file=sys.stderr)
        return _run_all_plink_zte_per_onu(profile, sns, exe, use_batch=batch)


def run_all(profile: lo.OltProfile, sns: list[str]) -> RunAllResult:
    """Localiza + apaga."""
    if profile.proto == "telnet":
        return _run_all_telnet(profile, sns)

    if profile.vendor == "zte":
        return _run_all_zte_ssh(profile, sns)

    is_zte = False
    try:
        return _run_all_paramiko(profile, sns)
    except Exception as e:
        if not lo._should_fallback_plink(e):
            raise
        print(f"\nAviso: Paramiko falhou ({e}); tentando PuTTY/Plink…\n", file=sys.stderr)
        exe, use_batch = _find_ssh_cli_exe()
        if not exe:
            raise RuntimeError(_erro_ssh_com_causa(e)) from e
        vend = "zte" if is_zte else "huawei"
        lines = (
            _expand_body_for_plink_zte(sns, None, profile)
            if is_zte
            else _expand_body_for_plink(sns, None, profile)
        )
        raw = _run_plink_lines(
            profile.host,
            profile.port,
            profile.user,
            profile.password,
            lines,
            exe,
            use_batch=use_batch,
            vendor=vend,
        )
        out = RunAllResult(vendor=vend)
        for sn in sns:
            _raise_if_cancelled()
            out.lookup_raw[sn] = raw
            if is_zte:
                info = parse_zte_by_sn_output(raw, sn)
            else:
                info = parse_by_sn_output(raw, sn)
            if info:
                out.found[sn] = info
            else:
                out.not_found[sn] = raw
        if not out.found:
            out.entries = [(sn, "Erro: não localizado na OLT") for sn in sns]
            return out
        if is_zte:
            zte_infos = [v for v in out.found.values() if isinstance(v, OntZteBySn)]
            del_lines = _expand_body_for_plink_zte(sns, zte_infos, profile)
        else:
            hw_infos = [v for v in out.found.values() if isinstance(v, OntBySn)]
            del_lines = _plink_body_with_confirm_y(
                build_delete_cmds_batch(hw_infos, profile)
            )
        del_out = _run_plink_lines(
            profile.host,
            profile.port,
            profile.user,
            profile.password,
            del_lines,
            exe,
            use_batch=use_batch,
            vendor=vend,
        )
        ok_fn = _delete_ok_zte if is_zte else _delete_ok
        for sn in sns:
            _raise_if_cancelled()
            if sn not in out.found:
                out.entries.append((sn, "Erro: não localizado na OLT"))
            else:
                out.delete_raw[sn] = del_out
                if ok_fn(del_out):
                    out.entries.append((sn, "Delet"))
                else:
                    out.entries.append((sn, f"Erro: {_erro_curto(del_out)}"))
        return out


def gravar_log(olt_key: int, result: RunAllResult, rede: str) -> Path:
    """Log completo: resumo + comandos + saída OLT."""
    log_dir = app_dir() / "log"
    log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    tag = "zte" if result.vendor == "zte" else "huawei"
    rede_slug = lo.norm_rede(rede)
    path = log_dir / f"delet_{rede_slug}_olt{olt_key}_{tag}_bysn_{ts}.txt"
    titulo_rede = lo.rede_titulo(rede)
    profile = lo.olts_dict(rede).get(olt_key)
    lines = [
        f"{titulo_rede} OLT {olt_key} | {tag} | by-sn | EXECUTADO | {WATERMARK}",
        "",
    ]

    lines.append("--- Resumo ---")
    for sn, msg in result.entries:
        lines.append(f"{sn} - {msg}")
    n_ok = sum(1 for _, m in result.entries if m == "Delet")
    lines.append(f"Total: {n_ok}/{len(result.entries)} deletada(s)")
    lines.append("")

    for sn, info in result.found.items():
        if isinstance(info, OntZteBySn):
            lines.append(
                f"SN={info.sn}\tPON={info.pon_id}\tONU={info.onu_numero}"
            )
            cmds = build_zte_delete_cmds_for_one(info, profile)
            lookup_label = "--- show gpon onu by sn (trecho) ---"
        else:
            lines.append(
                f"SN={info.sn}\tLineProfileID={info.line_profile_id}\t"
                f"F/S/P={info.fsp}\tONT-ID={info.ont_id}"
            )
            cmds = build_delete_cmds_for_one(info, profile)
            lookup_label = "--- display by-sn (trecho) ---"
        for c in cmds:
            lines.append(f"  {c}")
        lines.append("")
        lines.append(lookup_label)
        lines.append(result.lookup_raw.get(sn, "")[:4000])
        lines.append("")
        lines.append("--- saída delete ---")
        lines.append(result.delete_raw.get(sn, "(sem saída)"))
        lines.append("")

    if result.not_found:
        lines.append("--- SN não localizado ---")
        for sn, raw in result.not_found.items():
            lines.append(sn)
            dbg = log_dir / f"bysn_raw_{sn}_{ts}.txt"
            dbg.write_text(raw or "", encoding="utf-8")
            lines.append(f"  bruto: {dbg.name}")
        lines.append("")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


MENU_LARGURA = 70


def print_menu_rede() -> None:
    barra = "=" * MENU_LARGURA
    print()
    print(barra)
    print("ESCOLHA A EMPRESA".center(MENU_LARGURA))
    print(barra)
    redes = lo.list_redes()
    if not redes:
        print("\t (nenhuma — cadastre em empresas.json ou na GUI)")
    for i, rid in enumerate(redes, start=1):
        print(f"\t {i}:{lo.rede_titulo(rid)}")
    print("\t 0:SAIR")
    print(barra)


def print_menu(rede: str) -> None:
    olts = lo.olts_dict(rede)
    titulo = lo.rede_titulo(rede)
    barra = "=" * MENU_LARGURA
    print()
    print(barra)
    print(f"DELETAR ONU — {titulo}".center(MENU_LARGURA))
    print(WATERMARK.center(MENU_LARGURA))
    print(barra)
    for k in sorted(olts):
        nome = olts[k].nome.upper()
        print(f"\t{k:2d}:{nome}")
    print("\t 0:SAIR")
    print(barra)
    print(f"\nLista de SN:\n  {txt_onu_path()}\n")


def fluxo(olt_key: int, rede: str) -> int:
    rede = lo.norm_rede(rede)
    if not rede:
        print(
            "Nenhuma empresa cadastrada. Use a GUI: Nova empresa / Adicionar OLT.",
            file=sys.stderr,
        )
        return 2
    olts = lo.olts_dict(rede)
    if olt_key not in olts:
        print(f"OLT inválida para {lo.rede_titulo(rede)}.", file=sys.stderr)
        return 2
    profile = olts[olt_key]

    txt_path = txt_onu_path()
    try:
        sns = ler_sns_txt(txt_path)
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 2
    if not sns:
        print(f"Nenhum SN em {txt_path}", file=sys.stderr)
        return 2

    fab = "ZTE" if profile.vendor == "zte" else "Huawei"
    print(f"\n{lo.rede_titulo(rede)} | OLT: {profile.nome}  |  {fab}  |  {len(sns)} SN no TXT")
    print("Modo automático: por ONU (localiza → apaga → próxima).\n")

    clear_cancel()
    result = RunAllResult()
    try:
        result = run_all(profile, sns)
    except KeyboardInterrupt:
        print("\nInterrompido (log gravado se houver resultados).", file=sys.stderr)
        if result.entries or result.found:
            gravar_log(olt_key, result, rede)
        return 130
    except Exception as e:
        print(f"\nErro: {e}", file=sys.stderr)
        return 1

    if not result.entries:
        result.entries = [(sn, "Erro: execução sem resultado") for sn in sns]

    log = gravar_log(olt_key, result, rede)
    print("\n--- Resumo ---")
    for sn, msg in result.entries:
        print(f"  {sn} - {msg}")
    n_ok = sum(1 for _, m in result.entries if m == "Delet")
    print(f"\nConcluído: {n_ok}/{len(result.entries)} deletada(s).")
    print(f"Log: {log.resolve()}")
    return 0 if n_ok > 0 else 2


def _pausar_antes_fechar() -> None:
    """Duplo clique no .exe: mantém a janela aberta para ler o resultado."""
    try:
        input("\nPressione Enter para fechar...")
    except (EOFError, KeyboardInterrupt):
        pass


def _deve_pausar_ao_fechar() -> bool:
    """EXE compilado ou menu interativo sem .bat."""
    return bool(getattr(sys, "frozen", False))


def main() -> int:
    ensure_portable_setup()
    if lo.paramiko is None:
        print(
            "Instale: pip install -r requirements.txt  (na pasta delet)",
            file=sys.stderr,
        )
        return 1
    p = argparse.ArgumentParser(description="Apaga ONUs Huawei/ZTE (onu_deletar.txt).")
    p.add_argument("--olt", type=int, help="Número da OLT no menu da empresa")
    p.add_argument(
        "--empresa",
        "--rede",
        dest="empresa",
        help="ID da empresa (como em empresas.json)",
    )
    args = p.parse_args()

    redes = lo.list_redes()
    if not redes:
        print(
            "Nenhuma empresa cadastrada. Use a GUI: Nova empresa / Adicionar OLT.",
            file=sys.stderr,
        )
        return 2

    empresa = args.empresa
    if args.olt is not None:
        if not empresa:
            empresa = redes[0]
        return fluxo(args.olt, empresa)

    print_menu_rede()
    op_rede = input("Digite o número da empresa.......").strip()
    if op_rede == "0":
        return 0
    try:
        idx = int(op_rede)
        if idx < 1 or idx > len(redes):
            raise ValueError
        rede = redes[idx - 1]
    except ValueError:
        print("Empresa inválida.", file=sys.stderr)
        return 2

    print_menu(rede)
    op = input("Digite a opcao.......").strip()
    if op == "0":
        return 0
    try:
        olt_key = int(op)
    except ValueError:
        print("Opção inválida.", file=sys.stderr)
        return 2
    return fluxo(olt_key, rede)


if __name__ == "__main__":
    _code = 1
    try:
        _code = main()
    except Exception as _e:
        print(f"\nErro fatal: {_e}", file=sys.stderr)
        _code = 1
    finally:
        if _deve_pausar_ao_fechar():
            _pausar_antes_fechar()
    sys.exit(_code)
