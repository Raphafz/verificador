"""
Criptografia de campos sensíveis em repouso (Fernet).
Configure FIELD_ENCRYPTION_KEY no .env (chave Fernet — 44 caracteres url-safe).
Gere com: python manage.py setup_p1_security --write-key
"""
import base64
import hashlib
import logging
import os

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

ENCRYPTED_PREFIX = "enc:v1:"
_warned_decrypt_failure = False


class FieldEncryptionNotConfiguredError(RuntimeError):
    """FIELD_ENCRYPTION_KEY ausente ou inválida; boot/setup necessário."""


def _derive_key_from_secret(secret: str) -> bytes:
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _read_env_encryption_key() -> str:
    raw = os.getenv("FIELD_ENCRYPTION_KEY", "").strip()
    if raw:
        return raw
    try:
        from django.conf import settings

        return (getattr(settings, "FIELD_ENCRYPTION_KEY", None) or "").strip()
    except Exception:
        return ""


def normalize_fernet_key(raw_key: str) -> str:
    """Ajusta padding base64 url-safe (Fernet exige 44 caracteres com '=' final)."""
    key = (raw_key or "").strip()
    if not key:
        return key
    pad = (-len(key)) % 4
    if pad:
        key = key + ("=" * pad)
    return key


def _try_fernet(raw_key: str) -> Fernet | None:
    if not raw_key:
        return None
    seen = set()
    for candidate in (raw_key.strip(), normalize_fernet_key(raw_key)):
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        try:
            return Fernet(candidate.encode("utf-8"))
        except Exception:
            continue
    return None


def _allow_secret_key_derivation() -> bool:
    """
    Derivação de SECRET_KEY só em testes automatizados ou dev com opt-in explícito.
    Nunca em produção.
    """
    from saas_viabilidade.security_bootstrap import is_test_run

    if is_test_run():
        return True
    if os.getenv("ALLOW_FIELD_ENCRYPTION_SECRET_FALLBACK", "").lower() not in (
        "1",
        "true",
        "on",
        "yes",
    ):
        return False
    try:
        from django.conf import settings

        if getattr(settings, "IS_PRODUCTION", False):
            return False
        return bool(getattr(settings, "DEBUG", False))
    except Exception:
        return False


def _fernet_from_secret_key() -> Fernet:
    from django.conf import settings

    secret = getattr(settings, "SECRET_KEY", None)
    if not secret:
        raise FieldEncryptionNotConfiguredError("SECRET_KEY não configurada")
    return Fernet(_derive_key_from_secret(secret))


def get_fernet() -> Fernet:
    """Fernet para criptografar — exige FIELD_ENCRYPTION_KEY (sem fallback silencioso)."""
    f = _try_fernet(_read_env_encryption_key())
    if f is not None:
        return f
    if _allow_secret_key_derivation():
        logger.debug(
            "FIELD_ENCRYPTION_KEY ausente — usando derivação de SECRET_KEY (teste ou fallback dev)"
        )
        return _fernet_from_secret_key()
    raise FieldEncryptionNotConfiguredError(
        "FIELD_ENCRYPTION_KEY ausente ou inválida. "
        "Gere com: python manage.py setup_p1_security --write-key"
    )


def _decrypt_candidates() -> list[Fernet]:
    """Ordem: chave do .env; legado derivado só em teste ou fallback dev explícito."""
    candidates: list[Fernet] = []
    env_fernet = _try_fernet(_read_env_encryption_key())
    if env_fernet is not None:
        candidates.append(env_fernet)
    if _allow_secret_key_derivation():
        derived = _fernet_from_secret_key()
        if derived not in candidates:
            candidates.append(derived)
    return candidates


def is_encrypted(value: str | None) -> bool:
    return bool(value) and str(value).startswith(ENCRYPTED_PREFIX)


def encrypt_value(plain: str | None) -> str:
    if plain is None or plain == "":
        return ""
    if is_encrypted(plain):
        return plain
    token = get_fernet().encrypt(plain.encode("utf-8")).decode("utf-8")
    return f"{ENCRYPTED_PREFIX}{token}"


def decrypt_value(stored: str | None) -> str:
    global _warned_decrypt_failure
    if stored is None or stored == "":
        return ""
    if not is_encrypted(stored):
        return stored
    payload = stored[len(ENCRYPTED_PREFIX) :]
    candidates = _decrypt_candidates()
    if not candidates:
        raise FieldEncryptionNotConfiguredError(
            "Não há chave para descriptografar. Configure FIELD_ENCRYPTION_KEY."
        )
    last_error: InvalidToken | None = None
    for fernet in candidates:
        try:
            return fernet.decrypt(payload.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            last_error = exc
            continue
    if not _warned_decrypt_failure:
        _warned_decrypt_failure = True
        logger.error(
            "Falha ao descriptografar campo (chave trocada ou dado legado). "
            "Execute: python manage.py setup_p1_security --write-key "
            "e re-salve o token Telegram / senhas OLT no painel."
        )
    if last_error:
        logger.debug("decrypt_value: InvalidToken após %s candidato(s)", len(candidates))
    return ""
