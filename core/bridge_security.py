"""
Autenticação HMAC para API interna alert-bridge (anti-replay, trusted proxy).
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
import time

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse

logger = logging.getLogger("security")
audit_logger = logging.getLogger("audit")

BRIDGE_SIGNATURE_MAX_AGE_SEC = int(os.getenv("BRIDGE_SIGNATURE_MAX_AGE_SEC", "120"))
BRIDGE_NONCE_TTL_SEC = int(os.getenv("BRIDGE_NONCE_TTL_SEC", "300"))


def _env_bool(name: str, default: str = "False") -> bool:
    return os.getenv(name, default).lower() in ("1", "true", "on", "yes")


def bridge_hmac_required() -> bool:
    if _env_bool("BRIDGE_REQUIRE_HMAC", "True" if getattr(settings, "IS_PRODUCTION", False) else "False"):
        return True
    return getattr(settings, "IS_PRODUCTION", False)


def get_bridge_client_ip(request) -> str:
    """IP do cliente; delega para core.request_ip (política unificada)."""
    from core.request_ip import get_client_ip

    return get_client_ip(request)


def bridge_ip_allowed(request) -> bool:
    allow = os.getenv("ALERT_BRIDGE_ALLOWED_IPS", "127.0.0.1,::1").strip()
    allowed = {ip.strip() for ip in allow.split(",") if ip.strip()}
    client = get_bridge_client_ip(request)
    return client in allowed


def _hmac_secret_bytes() -> bytes:
    secret = os.getenv("BRIDGE_HMAC_SECRET", "").strip()
    if not secret and not bridge_hmac_required():
        secret = os.getenv("ALERT_BRIDGE_API_TOKEN", "")
    if not secret:
        return b""
    return secret.encode("utf-8")


def _validate_hmac_policy() -> JsonResponse | None:
    """Produção exige BRIDGE_HMAC_SECRET dedicado (≠ token)."""
    if not getattr(settings, "IS_PRODUCTION", False):
        return None
    hmac_secret = os.getenv("BRIDGE_HMAC_SECRET", "").strip()
    token = os.getenv("ALERT_BRIDGE_API_TOKEN", "").strip()
    if not hmac_secret:
        return JsonResponse(
            {"error": "BRIDGE_HMAC_SECRET obrigatório em produção"},
            status=503,
        )
    if hmac_secret == token:
        return JsonResponse(
            {"error": "BRIDGE_HMAC_SECRET deve ser diferente de ALERT_BRIDGE_API_TOKEN"},
            status=503,
        )
    return None


def build_bridge_signature(timestamp: str, nonce: str, token: str) -> str:
    msg = f"{timestamp}.{nonce}.{token}".encode("utf-8")
    return hmac.new(_hmac_secret_bytes(), msg, hashlib.sha256).hexdigest()


def _nonce_cache_key(nonce: str) -> str:
    return f"bridge_nonce:{nonce}"


def log_bridge_api_access(request, *, configs_count: int, status: str = "ok") -> None:
    audit_logger.info(
        "bridge_configs_fetch",
        extra={
            "status": status,
            "ip": get_bridge_client_ip(request),
            "configs_count": configs_count,
            "request_id": getattr(request, "request_id", None),
        },
    )
    try:
        from alerts.models import AlertBridgeWorkerStatus

        AlertBridgeWorkerStatus.touch(
            ip=get_bridge_client_ip(request),
            configs_count=configs_count,
            version=(request.headers.get("X-Bridge-Version") or "").strip(),
        )
    except Exception:
        logger.exception("Falha ao registrar heartbeat do alert-bridge")


def validate_bridge_request(request) -> JsonResponse | None:
    """
    Retorna JsonResponse de erro ou None se válido.
    Exige: IP allowlist + token + HMAC + timestamp + nonce único (Redis/cache).
    """
    policy_err = _validate_hmac_policy()
    if policy_err is not None:
        return policy_err

    if not bridge_ip_allowed(request):
        logger.warning("Bridge: IP não autorizado", extra={"ip": get_bridge_client_ip(request)})
        return JsonResponse({"error": "Forbidden"}, status=403)

    if request.GET.get("token"):
        return JsonResponse({"error": "Token via query string não é permitido"}, status=400)

    token = (request.headers.get("X-Bridge-Token") or "").strip()
    expected = os.getenv("ALERT_BRIDGE_API_TOKEN", "").strip()
    if not expected or not token or not hmac.compare_digest(token, expected):
        return JsonResponse({"error": "Unauthorized"}, status=401)

    secret = _hmac_secret_bytes()
    if not secret:
        return JsonResponse({"error": "Bridge HMAC não configurado"}, status=503)

    ts_header = request.headers.get("X-Bridge-Timestamp", "").strip()
    nonce = request.headers.get("X-Bridge-Nonce", "").strip()
    sig = request.headers.get("X-Bridge-Signature", "").strip()

    if not ts_header or not nonce or not sig:
        return JsonResponse({"error": "Cabeçalhos de assinatura ausentes"}, status=401)

    try:
        ts_val = int(ts_header)
    except ValueError:
        return JsonResponse({"error": "Timestamp inválido"}, status=401)

    now = int(time.time())
    if abs(now - ts_val) > BRIDGE_SIGNATURE_MAX_AGE_SEC:
        return JsonResponse({"error": "Timestamp expirado"}, status=401)

    if len(nonce) < 16:
        return JsonResponse({"error": "Nonce inválido"}, status=401)

    nkey = _nonce_cache_key(nonce)
    if cache.get(nkey):
        logger.warning("Bridge: replay detectado", extra={"nonce": nonce[:8]})
        return JsonResponse({"error": "Replay detectado"}, status=403)

    expected_sig = build_bridge_signature(ts_header, nonce, token)
    if not hmac.compare_digest(sig, expected_sig):
        return JsonResponse({"error": "Assinatura inválida"}, status=401)

    cache.set(nkey, "1", BRIDGE_NONCE_TTL_SEC)
    return None


def bridge_request_headers_for_client() -> dict[str, str]:
    """Headers para worker Node / urllib."""
    token = os.getenv("ALERT_BRIDGE_API_TOKEN", "").strip()
    ts = str(int(time.time()))
    nonce = secrets.token_urlsafe(24)
    sig = build_bridge_signature(ts, nonce, token)
    return {
        "X-Bridge-Token": token,
        "X-Bridge-Timestamp": ts,
        "X-Bridge-Nonce": nonce,
        "X-Bridge-Signature": sig,
    }


def generate_bridge_credentials() -> tuple[str, str]:
    """Gera par token + HMAC para rotação."""
    return secrets.token_urlsafe(32), secrets.token_urlsafe(48)
