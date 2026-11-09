"""
Sanitização operacional (OLT/VPN/bridge) — LGPD + anti-vazamento.
Usado em log_output de jobs, handlers de arquivo e mensagens Python.
"""
from __future__ import annotations

import re
from functools import lru_cache

_REDACT = "[REDACTED]"

# key=value sensíveis
_KV_SECRET = re.compile(
    r"(?i)\b(password|passwd|senha|secret|enable[-_]?password|community|"
    r"token|api[_-]?key|psk|private[-_]?key|authorization)\s*[:=]\s*\S+"
)

# "enable secret VALUE" / "snmp-server community NAME"
_INLINE_SECRET = re.compile(
    r"(?i)\b(enable\s+secret|secret|community)\s+(\S+)"
)

# SNMP / community strings
_SNMP_COMMUNITY = re.compile(
    r"(?i)(snmp-server\s+community|(?:ro|rw)\s+community|community)\s+(\S+)"
)

_BEARER = re.compile(r"(?i)\b(bearer|authorization)\s+[A-Za-z0-9._\-+/=]{8,}")

_TELEGRAM_TOKEN = re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{20,}\b")

_PRIVATE_IPV4 = re.compile(
    r"\b("
    r"10(?:\.\d{1,3}){3}|"
    r"172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2}|"
    r"192\.168(?:\.\d{1,3}){2}"
    r")\b"
)

# VPN / OpenVPN inline secrets
_OVPN_SECRET = re.compile(r"(?i)^(auth-user-pass|secret|key|tls-auth)\s+.+$", re.M)

_SAFE_CLI_PREFIXES = (
    "show", "display", "interface", "config", "conf t", "conf", "undo", "quit",
    "exit", "enable", "cd ", "dir", "ping", "no ", "delete", "ont", "gpon",
    "scroll", "screen", "return", "reboot", "save", "write", "list", "get",
    "set", "debug", "terminal", "idle", "sysname", "[", "olt:", "erro:",
    "iniciando", "conectando", "vpn", "l2tp", "openvpn", "---", "…", "...",
)

_LOG_CLASS_PREFIX = re.compile(r"^\[(INFO|WARN|ERROR|DEBUG|OLT|VPN|SEC)\]\s*", re.I)


def mask_private_ipv4(text: str) -> str:
    def _repl(match: re.Match) -> str:
        parts = match.group(1).split(".")
        return f"{parts[0]}.{parts[1]}.*.*"

    return _PRIVATE_IPV4.sub(_repl, text)


def mask_host_for_log(host: str | None) -> str:
    if not host:
        return "-"
    host = str(host).strip()
    if _PRIVATE_IPV4.search(host):
        return mask_private_ipv4(host)
    # Hostname público: mantém domínio, mascara subpartes numéricas longas
    if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", host):
        parts = host.split(".")
        return f"{parts[0]}.{parts[1]}.*.*"
    return host


def _sanitize_cli_command_line(line: str) -> str:
    stripped = line.strip()
    if not stripped.startswith(">>>"):
        return line
    cmd = stripped[3:].strip()
    if not cmd or cmd.startswith("[senha") or cmd == "[REDACTED]":
        return line
    lower = cmd.lower()
    if any(lower.startswith(p) for p in _SAFE_CLI_PREFIXES):
        return mask_private_ipv4(line)
    # Comando curto sem espaço — frequentemente senha digitada após enable
    if len(cmd) < 80 and " " not in cmd and not cmd.startswith("/"):
        return ">>> [REDACTED]"
    return mask_private_ipv4(line)


@lru_cache(maxsize=1)
def _compiled_line_rules() -> tuple[re.Pattern, ...]:
    return (
        _KV_SECRET,
        _SNMP_COMMUNITY,
        _BEARER,
        _TELEGRAM_TOKEN,
    )


def sanitize_operational_text(text: str, *, classification: str = "olt_cli") -> str:
    """Remove/mascara dados sensíveis de saída OLT/VPN/operacional."""
    if not text:
        return text
    out = text.replace("\r\n", "\n").replace("\r", "\n")
    out = _INLINE_SECRET.sub(lambda m: f"{m.group(1)} {_REDACT}", out)
    for pat in _compiled_line_rules():
        if pat is _SNMP_COMMUNITY:
            out = pat.sub(r"\1 " + _REDACT, out)
        elif pat is _KV_SECRET:
            out = pat.sub(lambda m: f"{m.group(1)}={_REDACT}", out)
        else:
            out = pat.sub(_REDACT, out)
    out = _OVPN_SECRET.sub(lambda m: f"{m.group(0).split()[0]} {_REDACT}", out)
    lines = []
    for line in out.split("\n"):
        line = mask_private_ipv4(line)
        line = _sanitize_cli_command_line(line)
        if re.search(r"(?i)password\s*[:：]?\s*\S+", line):
            line = re.sub(r"(?i)password\s*[:：]?\s*\S+", f"password: {_REDACT}", line)
        lines.append(line)
    return "\n".join(lines)


def classify_log_line(line: str, default: str = "OLT") -> str:
    """Prefixo de classificação para leitura humana."""
    if _LOG_CLASS_PREFIX.match(line):
        return line
    lower = line.lower()
    if "vpn" in lower or "l2tp" in lower or "openvpn" in lower:
        return f"[VPN] {line}"
    if lower.startswith("erro") or "error" in lower:
        return f"[ERROR] {line}"
    if line.strip().startswith(">>>"):
        return f"[OLT] {line}"
    return f"[{default}] {line}"
