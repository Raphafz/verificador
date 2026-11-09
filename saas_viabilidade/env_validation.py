"""
Validação de variáveis de ambiente em produção/staging.
Chamado no final de settings.py.
"""
from __future__ import annotations

import os
import warnings

from saas_viabilidade.security_bootstrap import (
    validate_field_encryption_key_strength,
    validate_secret_key_strength,
)


REQUIRED_PROD = (
    "SECRET_KEY",
    "DATABASE_URL",
    "ALLOWED_HOSTS",
    "FIELD_ENCRYPTION_KEY",
)

REQUIRED_PROD_BRIDGE = (
    "BRIDGE_HMAC_SECRET",
    "ALERT_BRIDGE_API_TOKEN",
)

RECOMMENDED_PROD = (
    "CNPJ_HASH_SALT",
    "REDIS_URL",
    "GEOCODING_CACHE_SALT",
    "DPO_EMAIL",
    "CSRF_TRUSTED_ORIGINS",
)


def validate_environment(*, debug: bool, is_vps: bool, secret_key: str) -> list[str]:
    issues: list[str] = []
    is_prod = is_vps or os.getenv("DJANGO_ENV", "").strip().lower() == "production"

    if not is_prod and debug and not is_vps:
        return issues

    for name in REQUIRED_PROD:
        val = os.getenv(name, "").strip()
        if not val:
            issues.append(f"Variável obrigatória ausente: {name}")

    for err in validate_secret_key_strength(secret_key):
        issues.append(f"SECRET_KEY: {err}")

    fek = os.getenv("FIELD_ENCRYPTION_KEY", "").strip()
    for err in validate_field_encryption_key_strength(fek):
        issues.append(f"FIELD_ENCRYPTION_KEY: {err}")

    if is_prod:
        for name in REQUIRED_PROD_BRIDGE:
            if not os.getenv(name, "").strip():
                issues.append(f"Variável obrigatória ausente: {name}")
        hmac_s = os.getenv("BRIDGE_HMAC_SECRET", "").strip()
        token_b = os.getenv("ALERT_BRIDGE_API_TOKEN", "").strip()
        if hmac_s and token_b and hmac_s == token_b:
            issues.append("BRIDGE_HMAC_SECRET deve ser diferente de ALERT_BRIDGE_API_TOKEN")

    for name in RECOMMENDED_PROD:
        if not os.getenv(name, "").strip():
            issues.append(f"Recomendado em produção: {name}")

    if is_vps and os.getenv("DEBUG", "").lower() in ("1", "true", "on", "yes"):
        issues.append("DEBUG não deve estar ativo na VPS")

    if os.getenv("SERVE_MEDIA_VIA_DJANGO", "").lower() in ("1", "true", "on", "yes") and is_vps:
        issues.append("SERVE_MEDIA_VIA_DJANGO=true em VPS expõe mídia via Django")

    if is_prod and not os.getenv("SECURE_SSL_REDIRECT", "True").lower() in ("0", "false", "no"):
        pass  # default ok
    elif is_prod and os.getenv("SECURE_SSL_REDIRECT", "").lower() in ("0", "false", "no"):
        issues.append("SECURE_SSL_REDIRECT deve ser True em produção")

    return issues


def apply_environment_validation(*, debug: bool, is_vps: bool, secret_key: str, strict: bool = False) -> None:
    issues = validate_environment(debug=debug, is_vps=is_vps, secret_key=secret_key)
    if not issues:
        return
    msg = "Validação de ambiente:\n- " + "\n- ".join(issues)
    if strict or (is_vps and not debug):
        raise RuntimeError(msg)
    for line in issues:
        warnings.warn(line, stacklevel=2)
