"""Valida token de sessão, expiração, IP e registro ativo; atualiza last_seen."""
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin

from core.session_security import (
    login_redirect_url,
    on_login_success,
    register_session,
    touch_session,
    validate_active_session,
    _session_expires_at,
)


class SessionRegistryMiddleware(MiddlewareMixin):
    EXEMPT_PREFIXES = ("/static/", "/media/", "/health/", "/ready/")

    def process_request(self, request):
        if not request.user.is_authenticated:
            return None
        path = request.path or ""
        if any(path.startswith(p) for p in self.EXEMPT_PREFIXES):
            return None

        invalid, reason = validate_active_session(request, request.user)
        if invalid:
            redirect_url = login_redirect_url(request, reason)
            logout(request)
            try:
                request.session.flush()
            except Exception:
                pass
            return redirect(redirect_url)

        if not request.session.get("_session_registered"):
            token = request.session.get("_access_token")
            if token:
                exp_raw = request.session.get("_session_expires_at")
                expires_at = _session_expires_at()
                if exp_raw:
                    try:
                        from datetime import datetime

                        expires_at = datetime.fromisoformat(exp_raw)
                        if timezone.is_naive(expires_at):
                            from django.utils import timezone as tz

                            expires_at = tz.make_aware(expires_at, tz.get_current_timezone())
                    except (TypeError, ValueError):
                        expires_at = _session_expires_at()
                register_session(
                    request,
                    request.user,
                    access_token=token,
                    expires_at=expires_at,
                )
                request.session["_session_registered"] = True
            else:
                on_login_success(request, request.user)
        else:
            touch_session(request, request.user)
        return None
