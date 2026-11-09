"""Sessão segura: rotação, token de acesso e auditoria no login/logout."""
import logging

from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

logger = logging.getLogger("security")


@receiver(user_logged_in)
def handle_user_logged_in(sender, request, user, **kwargs):
    if not request or not hasattr(request, "session"):
        return
    try:
        from core.session_security import on_login_success

        on_login_success(request, user)
    except Exception as exc:
        logger.exception("Falha ao registrar sessão segura no login: %s", exc)

    try:
        from core.audit_trail import record_security_event

        record_security_event(
            "login_success",
            user=user,
            request=request,
            details={"username": user.username},
        )
    except Exception:
        pass


@receiver(user_logged_out)
def handle_user_logged_out(sender, request, user, **kwargs):
    if not user:
        return
    try:
        from core.session_security import on_logout

        if request and hasattr(request, "session"):
            on_logout(request, user)
    except Exception:
        pass
    try:
        from core.audit_trail import record_security_event

        record_security_event("logout", user=user, request=request)
    except Exception:
        pass
