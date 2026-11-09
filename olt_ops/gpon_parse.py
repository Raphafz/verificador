"""Parsing de saída CLI Huawei/ZTE e porta GPON F/S/P."""
from __future__ import annotations

import re
from dataclasses import dataclass

SN_RE = re.compile(r"\b([0-9A-Fa-f]{12,16})\b")
FSP_RE = re.compile(r"^\s*(\d+)\s*/\s*(\d+)\s*/\s*(\d+)\s*$")
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x07")
# Ruído de paginação Huawei (quebra linha e impede match no início da linha)
_HUAWEI_PAGER_NOISE_RE = re.compile(
    r"----\s*More(?:\s*\([^)]*\))?\s*----|"
    r"Press\s+'Q'\s+to\s+break\s*\)\s*----|"
    r"----\s*More\s*\(|"
    r"\{\s*<cr>\s*\|\|\s*<K>\s*\}\s*:?",
    re.IGNORECASE,
)
# Linha da tabela principal: F/S/P  ONT-ID  SN  active  offline ...
HUAWEI_OFFLINE_ROW_RE = re.compile(
    r"^\s*(\d+)\s*/\s*(\d+)\s*/\s*(\d+)\s+(\d+)\s+([0-9A-Fa-f]{12,16})\s+active\s+offline\b",
    re.IGNORECASE,
)
_HUAWEI_ONT_ROW_RE = re.compile(
    r"(\d+)\s*/\s*(\d+)\s*/\s*(\d+)\s+(\d+)\s+([0-9A-Fa-f]{4,})\s+\S+\s+"
    r"(offline|online)\s+(\S+)",
    re.IGNORECASE,
)


@dataclass
class GponPort:
    frame: int
    slot: int
    port: int

    @classmethod
    def parse(cls, raw: str) -> GponPort:
        text = (raw or "").strip().replace("\\", "/")
        m = FSP_RE.match(text)
        if not m:
            raise ValueError(f"Porta GPON inválida: {raw!r}. Use formato 0/1/14")
        return cls(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    def fsp(self) -> str:
        return f"{self.frame}/{self.slot}/{self.port}"

    def huawei_interface(self) -> str:
        return f"{self.frame}/{self.slot}"

    def zte_pon_id(self) -> str:
        return f"{self.frame}/{self.slot}/{self.port}"


@dataclass
class OnuTarget:
    serial: str
    frame: int
    slot: int
    port: int
    ont_id: int | None = None
    service_port: int | None = None
    pon_id: str | None = None
    onu_number: int | None = None


def unique_serials(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in items:
        sn = "".join(c for c in raw.upper() if c in "0123456789ABCDEF")
        if len(sn) < 12 or sn in seen:
            continue
        seen.add(sn)
        out.append(sn)
    return out


def _strip_terminal_noise(text: str) -> str:
    return _ANSI_ESCAPE_RE.sub("", text or "")


def _clean_huawei_display_text(text: str) -> str:
    """Remove ANSI e prompts ---- More ---- / Press 'Q' que colam na linha da tabela."""
    clean = _strip_terminal_noise(text).replace("\ufeff", "").replace("\u00a0", " ")
    clean = clean.replace("\r\n", "\n").replace("\r", "\n")
    clean = _HUAWEI_PAGER_NOISE_RE.sub("", clean)
    # Linhas com lixo no início mas dados F/S/P no meio
    fixed_lines: list[str] = []
    for line in clean.splitlines():
        line = _HUAWEI_PAGER_NOISE_RE.sub("", line)
        m = _HUAWEI_ONT_ROW_RE.search(line)
        if m and not line.lstrip().startswith(m.group(1)):
            line = line[m.start() :]
        fixed_lines.append(line)
    return "\n".join(fixed_lines)


def _parse_huawei_ont_rows(clean: str) -> dict[tuple[int, int, int, int], tuple[str, str, str]]:
    """Extrai linhas da tabela display ont info (linha inteira ou trecho após paginação)."""
    rows: dict[tuple[int, int, int, int], tuple[str, str, str]] = {}
    row_line_start = re.compile(
        r"^\s*(\d+)\s*/\s*(\d+)\s*/\s*(\d+)\s+(\d+)\s+([0-9A-Fa-f]{4,})\s+\S+\s+"
        r"(offline|online)\s+(\S+)",
        re.I,
    )
    for line in clean.splitlines():
        if not line.strip():
            continue
        m = row_line_start.match(line)
        if not m:
            continue
        f, s, p, oid, sn, run, cfg = m.groups()
        rows[(int(f), int(s), int(p), int(oid))] = (sn.upper(), run.lower(), cfg.lower())

    # Sempre complementa com busca no texto inteiro (linhas quebradas por ---- More ----)
    for m in _HUAWEI_ONT_ROW_RE.finditer(clean):
        f, s, p, oid, sn, run, cfg = m.groups()
        key = (int(f), int(s), int(p), int(oid))
        rows[key] = (sn.upper(), run.lower(), cfg.lower())
    return rows


def parse_huawei_offline_serials(text: str, gpon: GponPort) -> list[str]:
    """
    Parser alinhado a archive/legacy-desktop-tools/listar_ont_offline.py:
    Run State offline + Config State initial na tabela display ont info F/S/P all.
    """
    clean = _clean_huawei_display_text(text)
    rows = _parse_huawei_ont_rows(clean)

    found: list[str] = []
    for key in sorted(rows.keys(), key=lambda k: (k[0], k[1], k[2], k[3])):
        f, s, p, _oid = key
        if f != gpon.frame or s != gpon.slot or p != gpon.port:
            continue
        sn, run, cfg = rows[key]
        if run == "offline" and cfg == "initial":
            found.append(sn)

    return unique_serials(found)


def parse_huawei_by_sn(text: str, serial: str) -> OnuTarget | None:
    """Interpreta display ont info by-sn."""
    sn = serial.upper()
    frame = slot = port = ont_id = None
    service_port = None

    for line in text.splitlines():
        low = line.lower()
        m = re.search(r"(\d+)\s*/\s*(\d+)\s*/\s*(\d+)", line)
        if m and frame is None:
            frame, slot, port = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if "ont id" in low or "ontid" in low:
            om = re.search(r"(\d+)\s*$", line.split(":")[-1])
            if om:
                ont_id = int(om.group(1))
        if "service port" in low or "service-port" in low:
            sm = re.search(r"(\d+)", line.split(":")[-1])
            if sm:
                service_port = int(sm.group(1))
        if sn in line.upper() and ont_id is None:
            nums = re.findall(r"\b(\d+)\b", line)
            if len(nums) >= 2:
                ont_id = int(nums[-1])

    if frame is None or slot is None or port is None:
        return None
    if ont_id is None:
        return None
    return OnuTarget(
        serial=sn,
        frame=frame,
        slot=slot,
        port=port,
        ont_id=ont_id,
        service_port=service_port,
    )


def norm_onu_sn(s: str) -> str:
    """SN Huawei (hex) ou ZTE alfanumérico (ex.: ITBS0D2D01F1, ZTEGCD06BBAB)."""
    return re.sub(r"[^0-9A-Za-z]", "", (s or "").strip()).upper()


def unique_onu_serials(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in items:
        sn = norm_onu_sn(raw)
        if len(sn) < 8 or sn in seen:
            continue
        seen.add(sn)
        out.append(sn)
    return out


_ZTE_ONU_SN_RE = re.compile(
    r"^\s*onu\s+(\d+)\s+type\s+\S+\s+sn\s+(\S+)\s*$",
    re.I,
)
# Ex.: gpon_onu-1/3/1:32 no signal | gpon-onu_1/2/2:4 no signal | gpon-onu_1/2/2:1 -25.228(dbm)
_ZTE_POWER_ONU_RE = re.compile(
    r"gpon[-_\s]*onu[-_](\d+)/(\d+)/(\d+):(\d+)\s+(.+?)(?:\s*$|\s*\()",
    re.I,
)
_ZTE_CLI_NOISE_RE = re.compile(
    r"ZTE-[^\n#]*\(config\)#.*$|"
    r"^Onu\s+Rx\s+power\s*$|"
    r"^-{3,}\s*$|"
    r"-{2,}\s*More\s*-{2,}",
    re.I | re.M,
)


def parse_zte_onu_sn_map(text: str) -> dict[int, str]:
    """Extrai onu N → SN de `show run interface gpon-olt_F/S/P`."""
    clean = _strip_terminal_noise(text)
    out: dict[int, str] = {}
    for line in clean.splitlines():
        m = _ZTE_ONU_SN_RE.match(line.strip())
        if not m:
            continue
        onu_id = int(m.group(1))
        out[onu_id] = norm_onu_sn(m.group(2))
    return out


def _clean_zte_power_text(text: str) -> str:
    clean = _strip_terminal_noise(text).replace("\ufeff", "").replace("\u00a0", " ")
    clean = clean.replace("\r\n", "\n").replace("\r", "\n")
    return _ZTE_CLI_NOISE_RE.sub("", clean)


def _zte_rx_is_offline(rx: str) -> bool:
    rx_low = (rx or "").strip().lower()
    return "no signal" in rx_low or rx_low in ("nosignal", "n/a", "na")


def parse_zte_no_signal_onu_ids(text: str, gpon: GponPort) -> list[int]:
    """ONUs com Rx `no signal` em `show pon power olt-rx gpon-olt_F/S/P`."""
    clean = _clean_zte_power_text(text)
    want = (gpon.frame, gpon.slot, gpon.port)
    ids: set[int] = set()

    for m in _ZTE_POWER_ONU_RE.finditer(clean):
        f, s, p, onu_id, rx = m.groups()
        if (int(f), int(s), int(p)) != want:
            continue
        if _zte_rx_is_offline(rx):
            ids.add(int(onu_id))

    # Fallback linha a linha (eco colado no início da linha)
    for line in clean.splitlines():
        m = _ZTE_POWER_ONU_RE.search(line)
        if not m:
            continue
        f, s, p, onu_id, rx = m.groups()
        if (int(f), int(s), int(p)) != want:
            continue
        if _zte_rx_is_offline(rx):
            ids.add(int(onu_id))

    return sorted(ids)


def parse_zte_offline_onu_ids(power_text: str, gpon: GponPort) -> list[int]:
    """
    Offline ZTE = linhas com Rx ``no signal`` em ``show pon power olt-rx gpon-olt_F/S/P``.
    Retorna IDs ONU (ex.: 32) para ``no onu 32`` na interface gpon-olt.
    """
    return parse_zte_no_signal_onu_ids(power_text, gpon)


def parse_zte_offline_serials(
    run_interface_text: str,
    power_text: str,
    gpon: GponPort,
) -> list[str]:
    """
    Legado: cruzar SN (show run) com no signal. Preferir ``parse_zte_offline_onu_ids``.
    """
    onu_sn = parse_zte_onu_sn_map(run_interface_text)
    offline_ids = parse_zte_no_signal_onu_ids(power_text, gpon)
    found: list[str] = []
    for onu_id in offline_ids:
        sn = onu_sn.get(onu_id)
        if sn:
            found.append(sn)
    return unique_onu_serials(found)


def zte_onu_id_from_job_line(line: str) -> int | None:
    """Linha do job: ID ONU (ZTE) ou legado com prefixo onu:32."""
    raw = (line or "").strip()
    if not raw:
        return None
    m = re.match(r"^(?:onu:)?(\d+)$", raw, re.I)
    if m:
        return int(m.group(1))
    return None


def onu_target_from_zte_job_line(line: str, gpon: GponPort) -> OnuTarget | None:
    """Monta alvo para exclusão ZTE a partir do ID gravado na listagem."""
    onu_num = zte_onu_id_from_job_line(line)
    if onu_num is None:
        return None
    pon = gpon.zte_pon_id()
    return OnuTarget(
        serial=f"ONU-{onu_num}",
        frame=gpon.frame,
        slot=gpon.slot,
        port=gpon.port,
        onu_number=onu_num,
        pon_id=pon,
    )


def _extract_fsp_from_text(text: str) -> tuple[int, int, int] | None:
    """Extrai F/S/P da saída CLI (ex.: gpon-olt_0/1/14 ou 0/1/14)."""
    m = re.search(
        r"gpon[-_]?olt[_\s]*(\d+)\s*/\s*(\d+)\s*/\s*(\d+)",
        text,
        re.I,
    )
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    for line in text.splitlines():
        m = re.search(r"(\d+)\s*/\s*(\d+)\s*/\s*(\d+)", line)
        if m:
            return int(m.group(1)), int(m.group(2)), int(m.group(3))
    return None


def parse_zte_by_sn(
    text: str,
    serial: str,
    gpon: GponPort | None = None,
) -> OnuTarget | None:
    """Interpreta show gpon onu by sn — porta vem da resposta da OLT."""
    sn = serial.upper()
    frame = slot = port = None
    onu_number = None

    if gpon is not None:
        frame, slot, port = gpon.frame, gpon.slot, gpon.port

    for line in text.splitlines():
        up = line.upper()
        if sn not in up:
            continue
        fsp = re.search(r"(\d+)\s*/\s*(\d+)\s*/\s*(\d+)", line)
        if fsp:
            frame, slot, port = (
                int(fsp.group(1)),
                int(fsp.group(2)),
                int(fsp.group(3)),
            )
        nums = re.findall(r"\b(\d+)\b", line)
        if nums and onu_number is None:
            onu_number = int(nums[-1])

    if frame is None:
        found = _extract_fsp_from_text(text)
        if found:
            frame, slot, port = found

    if onu_number is None:
        m = re.search(r"onu\s*[:=]?\s*(\d+)", text, re.I)
        if m:
            onu_number = int(m.group(1))
        else:
            for line in text.splitlines():
                if sn in line.upper():
                    nums = re.findall(r"\b(\d+)\b", line)
                    if len(nums) >= 2:
                        onu_number = int(nums[-1])
                        break

    if frame is None or slot is None or port is None or onu_number is None:
        return None

    pon = f"{frame}/{slot}/{port}"
    return OnuTarget(
        serial=sn,
        frame=frame,
        slot=slot,
        port=port,
        onu_number=onu_number,
        pon_id=pon,
    )
