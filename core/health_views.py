"""Healthcheck e readiness para load balancers / monitoramento."""
import os

from django.conf import settings
from django.db import connection
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.views.decorators.http import require_GET

from core.request_ip import get_client_ip


@require_GET
def health_live(request):
    """Liveness — processo responde."""
    return JsonResponse({"status": "ok", "service": "saas-viabilidade"})


@require_GET
def health_ready(request):
    """Readiness — DB e config mínima."""
    checks = {"database": False, "secret_key": False, "debug_safe": True}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["database"] = True
    except Exception:
        body = {"status": "degraded", "checks": checks}
        if settings.DEBUG:
            import traceback

            body["error"] = traceback.format_exc()[-500:]
        else:
            body["error"] = "database_unavailable"
        return JsonResponse(body, status=503)

    sk = getattr(settings, "SECRET_KEY", "")
    from saas_viabilidade.security_bootstrap import validate_secret_key_strength

    checks["secret_key"] = bool(sk) and not validate_secret_key_strength(sk)
    checks["debug_safe"] = not (getattr(settings, "IS_VPS", False) and settings.DEBUG)

    ok = checks["database"] and (checks["secret_key"] or settings.DEBUG)
    return JsonResponse(
        {"status": "ok" if ok else "degraded", "checks": checks},
        status=200 if ok else 503,
    )


def _health_security_allowed(request) -> bool:
    allowed = getattr(settings, "HEALTH_SECURITY_ALLOWED_IPS", ())
    if not allowed:
        return True
    return get_client_ip(request) in allowed


@require_GET
def health_security(request):
    """Auditoria rápida de flags de segurança (sem dados sensíveis)."""
    if not _health_security_allowed(request):
        return HttpResponseForbidden("Forbidden")
    return JsonResponse({
        "csp_strict": getattr(settings, "CSP_STRICT", False),
        "mfa_required": getattr(settings, "MFA_REQUIRED", False),
        "session_secure": getattr(settings, "SESSION_COOKIE_SECURE", False),
        "force_rate_limit": getattr(settings, "FORCE_RATE_LIMIT", False),
        "field_encryption_configured": bool(os.getenv("FIELD_ENCRYPTION_KEY", "").strip()),
        "upload_antivirus": getattr(settings, "UPLOAD_ANTIVIRUS_ENABLED", False),
    })


@require_GET
def sentry_debug(request):
    """
    Dispara erro de teste para validar Sentry.
    Só disponível com DEBUG=True e SENTRY_DSN configurado.
    """
    if not settings.DEBUG:
        raise Http404
    if not getattr(settings, "SENTRY_DSN", "").strip():
        return JsonResponse(
            {"error": "SENTRY_DSN não configurado no .env"},
            status=503,
        )
    _ = 1 / 0
