"""
IP do cliente — X-Forwarded-For só quando REMOTE_ADDR é proxy confiável.
Evita spoofing de IP em lockout, sessão, MFA e rate limit.
"""
from __future__ import annotations

import os


def get_trusted_proxy_ips() -> set[str]:
    raw = (
        os.getenv("TRUSTED_PROXY_IPS", "").strip()
        or os.getenv("ALERT_BRIDGE_TRUSTED_PROXIES", "127.0.0.1,::1").strip()
    )
    return {ip.strip() for ip in raw.split(",") if ip.strip()}


def get_client_ip(request) -> str:
    """
    Retorna IP do cliente final.
    Usa o primeiro valor de X-Forwarded-For apenas se REMOTE_ADDR for proxy confiável.
    """
    remote = (request.META.get("REMOTE_ADDR") or "").strip()
    if not remote:
        return "127.0.0.1"
    if remote not in get_trusted_proxy_ips():
        return remote
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        client = xff.split(",")[0].strip()
        if client:
            return client
    return remote
