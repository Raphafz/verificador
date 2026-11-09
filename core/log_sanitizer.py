"""Mascaramento de PII e dados operacionais em logs e auditoria."""
import re

from core.operational_sanitizer import sanitize_operational_text

_CNPJ_RE = re.compile(r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}")
_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")


def mask_cnpj(value: str | None) -> str:
    if not value:
        return ""
    digits = re.sub(r"\D", "", value)
    if len(digits) < 4:
        return "***"
    return f"**{digits[-4:]}"


def mask_email(value: str | None) -> str:
    if not value or "@" not in value:
        return value or ""
    local, _, domain = value.partition("@")
    if len(local) <= 2:
        return f"**@{domain}"
    return f"{local[0]}***{local[-1]}@{domain}"


def sanitize_log_message(text: str) -> str:
    if not text:
        return text
    text = sanitize_operational_text(text, classification="app")
    text = _EMAIL_RE.sub(lambda m: mask_email(m.group(0)), text)
    text = _CNPJ_RE.sub(lambda m: mask_cnpj(m.group(0)), text)
    return text


def sanitize_audit_details(details: dict | None) -> dict:
    if not details:
        return {}
    out = {}
    for key, val in details.items():
        k = str(key).lower()
        if "cnpj" in k:
            out[key] = mask_cnpj(str(val))
        elif "email" in k:
            out[key] = mask_email(str(val))
        elif "password" in k or "token" in k or "secret" in k:
            out[key] = "[REDACTED]"
        else:
            out[key] = val
    return out
