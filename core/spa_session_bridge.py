"""Ponte de sessão Django para modo hybrid (login JWT + painéis SSR)."""
from __future__ import annotations

from django.conf import settings


def should_bridge_django_session() -> bool:
    return getattr(settings, "FRONTEND_MODE", "hybrid") != "ssr"


def establish_django_session(request, user) -> None:
    """Cria cookie de sessão após login JWT para módulos SSR (OLT, FTTH, alertas)."""
    if not should_bridge_django_session():
        return
    if not user or not getattr(user, "is_active", False):
        return
    if (
        request.session.session_key
        and request.session.get("auth_user_id") == user.pk
        and getattr(request, "user", None)
        and request.user.is_authenticated
        and request.user.pk == user.pk
    ):
        return
    from django.contrib.auth import login as django_login

    django_login(request, user, backend="django.contrib.auth.backends.ModelBackend")


def clear_django_session(request) -> None:
    if not should_bridge_django_session():
        return
    from django.contrib.auth import logout as django_logout

    django_logout(request)
