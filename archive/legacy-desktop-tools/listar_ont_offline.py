# -*- coding: utf-8 -*-
"""
Parser da saída Huawei `display ont info F S P all` → SN offline + config initial.
Conexão SSH/Telnet: use huawei_olt.run_ssh / run_telnet (via listar_offline_bridge).
"""

from __future__ import annotations

import ctypes
import re
import subprocess
import sys
from typing import TypeAlias

OntKey: TypeAlias = tuple[int, int, int, int]


def _strip_ansi_str(s: str) -> str:
    s = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", s)
    s = re.sub(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)", "", s)
    return s


def parse_fsp(s: str) -> str:
    s = s.strip()
    if re.fullmatch(r"\d+/\d+/\d+", s):
        return s
    parts = re.split(r"[\s,;/]+", s)
    parts = [p for p in parts if p]
    if len(parts) == 3 and all(p.isdigit() for p in parts):
        return f"{parts[0]}/{parts[1]}/{parts[2]}"
    raise ValueError("Use três números: frame slot porta (ex.: 0 1 14 ou 0/1/14).")


def build_display_command(fsp: str) -> str:
    norm = parse_fsp(fsp)
    m = re.fullmatch(r"(\d+)/(\d+)/(\d+)", norm)
    if not m:
        raise ValueError("F/S/P inválido.")
    frame, slot, port = m.groups()
    return f"display ont info {frame} {slot} {port} all"


def _parse_huawei_ont_display(
    text: str,
) -> tuple[dict[OntKey, tuple[str, str, str]], dict[OntKey, str]]:
    text = _strip_ansi_str(text.replace("\ufeff", "").replace("\u00a0", " "))
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    row_ont = re.compile(
        r"^\s*(\d+)\s*/\s*(\d+)\s*/\s*(\d+)\s+(\d+)\s+([0-9A-Fa-f]{4,})\s+\S+\s+(offline|online)\s+(\S+)",
        re.I,
    )
    row_desc = re.compile(r"^\s*(\d+)\s*/\s*(\d+)\s*/\s*(\d+)\s+(\d+)\s+(.+)$")
    row_loose = re.compile(
        r"(\d+)\s*/\s*(\d+)\s*/\s*(\d+)\s+(\d+)\s+([0-9A-Fa-f]{4,})\s+\S+\s+(offline|online)\s+(\S+)",
        re.I,
    )

    rows: dict[OntKey, tuple[str, str, str]] = {}
    for line in text.splitlines():
        m = row_ont.match(line)
        if not m:
            continue
        f, s, p, oid, sn, run, cfg = m.groups()
        rows[(int(f), int(s), int(p), int(oid))] = (sn.upper(), run.lower(), cfg.lower())

    if not rows:
        for m in row_loose.finditer(text):
            f, s, p, oid, sn, run, cfg = m.groups()
            rows[(int(f), int(s), int(p), int(oid))] = (sn.upper(), run.lower(), cfg.lower())

    desc_map: dict[OntKey, str] = {}
    lines = text.splitlines()
    hdr = -1
    for i, line in enumerate(lines):
        lo_line = line.lower()
        if re.search(r"\bont\s*[- ]?\s*id\b", lo_line, re.I) and "description" in lo_line:
            hdr = i
            break
    if hdr >= 0:
        j = hdr + 1
        while j < len(lines):
            raw = lines[j]
            st = raw.strip()
            if st.startswith("In port"):
                break
            if st.startswith("---") or not st:
                j += 1
                continue
            if row_ont.match(raw):
                j += 1
                continue
            m2 = row_desc.match(raw)
            if m2:
                f, s, p, oid, desc = m2.groups()
                desc_map[(int(f), int(s), int(p), int(oid))] = desc.strip()
            j += 1

    return rows, desc_map


def format_offline_sn_report(text: str) -> str:
    """SN das ONTs Run offline + Config initial, uma por linha."""
    rows, _desc = _parse_huawei_ont_display(text)
    sns: list[str] = []
    for key in sorted(rows.keys(), key=lambda k: (k[0], k[1], k[2], k[3])):
        sn, run, cfg = rows[key]
        if run == "offline" and cfg == "initial":
            sns.append(sn)
    return "\n".join(sns) + ("\n" if sns else "")


def filter_offline_block(text: str) -> str:
    return format_offline_sn_report(text)


def _clipboard_win32() -> str | None:
    if sys.platform != "win32":
        return None
    CF_UNICODETEXT = 13
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    if not user32.OpenClipboard(None):
        return None
    try:
        h = user32.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return None
        p = kernel32.GlobalLock(h)
        if not p:
            return None
        try:
            return ctypes.wstring_at(p)
        finally:
            kernel32.GlobalUnlock(h)
    finally:
        user32.CloseClipboard()


def read_clipboard_text() -> str:
    if sys.platform == "win32":
        try:
            t = _clipboard_win32()
            if t and t.strip():
                return t
        except Exception:
            pass
        try:
            r = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "Get-Clipboard -Raw",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if r.stdout and r.stdout.strip():
                return r.stdout
        except Exception:
            pass
    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        try:
            return root.clipboard_get()
        finally:
            root.destroy()
    except Exception as e:
        raise RuntimeError(f"Não foi possível ler o clipboard: {e}") from e
