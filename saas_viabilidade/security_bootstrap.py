"""
Fail-safe de boot para produção: DEBUG, SECRET_KEY, flags HTTPS e mídia.
Chamado no início de settings.py antes de qualquer config sensível.
"""
from __future__ import annotations

import logging
import os
import secrets
import sys
from dataclasses import dataclass
from pathlib import Path

from django.core.management.utils import get_random_secret_key

logger = logging.getLogger("security.bootstrap")

INSECURE_SECRET_KEYS = frozenset({
    "dev-secret-key-change-me",
    "django-insecure-dev-key-change-in-production-12345678901234567890",
    "change-me",
    "secret",
    "test",
})

MIN_SECRET_KEY_LENGTH = 50
MIN_SECRET_UNIQUE_CHARS = 5
MIN_FIELD_ENCRYPTION_KEY_LENGTH = 44


class SecurityBootstrapError(RuntimeError):
    """Impede boot do Django em configuração insegura."""


def _env_bool(name: str, default: str = "False") -> bool:
    return os.getenv(name, default).lower() in ("1", "true", "on", "yes")


def is_vps_environment() -> bool:
    vps_env = os.getenv("VPS_ENVIRONMENT", "").strip().lower()
    if vps_env in ("1", "true", "on", "yes"):
        return True
    if vps_env in ("0", "false", "off", "no"):
        return False
    return os.path.exists("/etc/nginx")


def is_test_run(argv: list[str] | None = None) -> bool:
    argv = argv or sys.argv
    return any("test" in arg for arg in argv)


def validate_secret_key_strength(key: str) -> list[str]:
    issues: list[str] = []
    if not key:
        issues.append("SECRET_KEY ausente")
        return issues
    if key in INSECURE_SECRET_KEYS:
        issues.append("SECRET_KEY é um valor conhecido/inseguro")
    if len(key) < MIN_SECRET_KEY_LENGTH:
        issues.append(f"SECRET_KEY deve ter pelo menos {MIN_SECRET_KEY_LENGTH} caracteres")
    if len(set(key)) < MIN_SECRET_UNIQUE_CHARS:
        issues.append(f"SECRET_KEY deve ter pelo menos {MIN_SECRET_UNIQUE_CHARS} caracteres distintos")
    if key.startswith("django-insecure-"):
        issues.append("SECRET_KEY com prefixo django-insecure- não é permitido em produção")
    return issues


def generate_secret_key() -> str:
    """Gera SECRET_KEY compatível com Django (≥50 chars, alta entropia)."""
    return get_random_secret_key()


def _normalize_fernet_key(raw_key: str) -> str:
    key = (raw_key or "").strip()
    if not key:
        return key
    pad = (-len(key)) % 4
    if pad:
        key = key + ("=" * pad)
    return key


def _fernet_key_usable(raw_key: str) -> bool:
    """True se a string for uma chave Fernet válida."""
    from cryptography.fernet import Fernet

    if not raw_key:
        return False
    seen: set[str] = set()
    for candidate in (raw_key.strip(), _normalize_fernet_key(raw_key)):
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        try:
            Fernet(candidate.encode("utf-8"))
            return True
        except Exception:
            continue
    return False


def validate_field_encryption_key_strength(key: str) -> list[str]:
    issues: list[str] = []
    if not (key or "").strip():
        issues.append("FIELD_ENCRYPTION_KEY ausente")
        return issues
    raw = key.strip()
    if len(raw) < MIN_FIELD_ENCRYPTION_KEY_LENGTH:
        issues.append(
            f"FIELD_ENCRYPTION_KEY deve ter pelo menos {MIN_FIELD_ENCRYPTION_KEY_LENGTH} caracteres "
            "(chave Fernet url-safe)"
        )
    if not _fernet_key_usable(raw):
        issues.append(
            "FIELD_ENCRYPTION_KEY inválida (use Fernet.generate_key ou "
            "python manage.py setup_p1_security --write-key)"
        )
    return issues


def resolve_field_encryption_key(*, is_production: bool, is_test: bool) -> None:
    """
    Exige FIELD_ENCRYPTION_KEY válida fora de testes.
    Dev sem chave: falha no boot (opt-in explícito para fallback legado).
    """
    raw = os.getenv("FIELD_ENCRYPTION_KEY", "").strip()
    allow_fallback = _env_bool("ALLOW_FIELD_ENCRYPTION_SECRET_FALLBACK")

    if is_test and not raw:
        return

    if is_production:
        issues = validate_field_encryption_key_strength(raw)
        if issues:
            raise SecurityBootstrapError(
                "FIELD_ENCRYPTION_KEY inválida para produção:\n- "
                + "\n- ".join(issues)
                + "\n\nGere: python manage.py setup_p1_security --write-key"
            )
        return

    if raw:
        issues = validate_field_encryption_key_strength(raw)
        if issues:
            raise SecurityBootstrapError(
                "FIELD_ENCRYPTION_KEY inválida:\n- "
                + "\n- ".join(issues)
                + "\n\nGere: python manage.py setup_p1_security --write-key"
            )
        return

    if allow_fallback:
        logger.warning(
            "FIELD_ENCRYPTION_KEY ausente — ALLOW_FIELD_ENCRYPTION_SECRET_FALLBACK=true "
            "(derivação de SECRET_KEY; apenas desenvolvimento local)"
        )
        return

    raise SecurityBootstrapError(
        "FIELD_ENCRYPTION_KEY não definida no .env.\n"
        "Gere e grave: python manage.py setup_p1_security --write-key\n"
        "Ou, só em dev local legado: ALLOW_FIELD_ENCRYPTION_SECRET_FALLBACK=true"
    )


def resolve_secret_key(*, is_production: bool, is_test: bool) -> str:
    raw = os.getenv("SECRET_KEY", "").strip()
    if is_test and not raw:
        return get_random_secret_key()
    if is_production:
        issues = validate_secret_key_strength(raw)
        if issues:
            raise SecurityBootstrapError(
                "SECRET_KEY inválida para produção:\n- "
                + "\n- ".join(issues)
                + "\n\nGere uma chave: python manage.py check_security --generate-secret-key"
            )
        return raw
    if not raw:
        raise SecurityBootstrapError(
            "SECRET_KEY não definida no .env.\n"
            "Gere uma chave: python manage.py check_security --generate-secret-key\n"
            "e adicione ao arquivo .env"
        )
    issues = validate_secret_key_strength(raw)
    if issues:
        logger.warning(
            "SECRET_KEY fraca para desenvolvimento (produção bloquearia): %s",
            "; ".join(issues),
        )
    return raw


@dataclass(frozen=True)
class SecurityBootConfig:
    is_vps: bool
    is_production: bool
    is_local_dev: bool
    is_test: bool
    debug: bool
    secret_key: str
    serve_public_media: bool
    use_protected_media: bool
    secure_ssl_redirect: bool
    csrf_cookie_httponly: bool
    session_cookie_secure: bool
    csrf_cookie_secure: bool


def bootstrap_security(*, base_dir: Path, argv: list[str] | None = None) -> SecurityBootConfig:
    argv = argv or sys.argv
    is_vps = is_vps_environment()
    is_test = is_test_run(argv)
    is_local_dev = _env_bool("IS_LOCAL_DEV")
    django_env = os.getenv("DJANGO_ENV", "").strip().lower()
    is_production = is_vps or django_env == "production" or _env_bool("PRODUCTION")

    debug_default = "False" if is_production else "True"
    debug_env_set = os.getenv("DEBUG")
    debug = _env_bool("DEBUG", debug_default) if debug_env_set is not None else _env_bool("DEBUG", debug_default)

    if is_production:
        debug = False
        if debug_env_set and _env_bool("DEBUG"):
            raise SecurityBootstrapError(
                "FALHA DE SEGURANÇA: DEBUG=True não é permitido em produção "
                "(DJANGO_ENV=production, VPS_ENVIRONMENT ou PRODUCTION=true). "
                "Defina DEBUG=False no .env"
            )

    if debug and is_vps and not is_local_dev:
        raise SecurityBootstrapError(
            "FALHA DE SEGURANÇA: DEBUG=True detectado na VPS. "
            "Defina DEBUG=False e IS_LOCAL_DEV não deve contornar produção."
        )

    secret_key = resolve_secret_key(is_production=is_production, is_test=is_test)
    resolve_field_encryption_key(is_production=is_production, is_test=is_test)

    serve_media_flag = _env_bool("SERVE_MEDIA_VIA_DJANGO")
    if is_production and serve_media_flag:
        raise SecurityBootstrapError(
            "SERVE_MEDIA_VIA_DJANGO=true é proibido em produção. "
            "Sirva /media/ apenas via Nginx com auth ou use rotas protegidas do Django."
        )

    serve_public_media = (not is_production) and debug and serve_media_flag
    use_protected_media = not serve_public_media

    secure_ssl_default = "True" if is_production else "False"
    secure_ssl_redirect = is_production and _env_bool("SECURE_SSL_REDIRECT", secure_ssl_default)

    if is_production:
        csrf_cookie_httponly = True
    else:
        csrf_cookie_httponly = _env_bool("CSRF_COOKIE_HTTPONLY", "False")

    session_secure = is_production or _env_bool("SESSION_COOKIE_SECURE", "False" if debug else "True")
    csrf_secure = is_production or _env_bool("CSRF_COOKIE_SECURE", "False" if debug else "True")

    cfg = SecurityBootConfig(
        is_vps=is_vps,
        is_production=is_production,
        is_local_dev=is_local_dev,
        is_test=is_test,
        debug=debug,
        secret_key=secret_key,
        serve_public_media=serve_public_media,
        use_protected_media=use_protected_media,
        secure_ssl_redirect=secure_ssl_redirect,
        csrf_cookie_httponly=csrf_cookie_httponly,
        session_cookie_secure=session_secure,
        csrf_cookie_secure=csrf_secure,
    )

    if not is_test:
        level = logging.INFO if is_production else logging.DEBUG
        logger.log(
            level,
            "Security bootstrap: production=%s debug=%s vps=%s protected_media=%s ssl_redirect=%s",
            is_production,
            debug,
            is_vps,
            use_protected_media,
            secure_ssl_redirect,
        )

    return cfg
