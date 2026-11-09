"""Timeout de inatividade de sessão."""
import time

from django.conf import settings
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin


class SessionIdleTimeoutMiddleware(MiddlewareMixin):
    EXEMPT_PREFIXES = ("/static/", "/media/", "/health/", "/ready/")

    def process_request(self, request):
        if not request.user.is_authenticated:
            return None
        path = request.path or ""
        if any(path.startswith(p) for p in self.EXEMPT_PREFIXES):
            return None

        timeout = int(getattr(settings, "SESSION_IDLE_TIMEOUT", 1800))
        now = time.time()
        last = request.session.get("_last_activity_ts")
        if last and (now - float(last)) > timeout:
            logout(request)
            request.session.flush()
            login_url = getattr(settings, "LOGIN_URL", "/rm/login/")
            return redirect(f"{login_url}?idle=1")
        request.session["_last_activity_ts"] = now
        return None
