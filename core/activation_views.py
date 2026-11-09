"""
Views públicas de ativação de conta (definição de senha via link único).
"""
import logging

from django.db import transaction
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from .account_activation import (
    ACTIVATION_EXPIRY_MINUTES,
    consume_activation_token,
    get_user_for_activation_token,
)
from .rate_limiting import activation_rate_limit
from .ui_helpers import ui_template

logger = logging.getLogger("security")

_ACTIVATE_TPL = ("core/account_activate.html", "auth/account_activate_v2.html")


def _activate_template(request):
    return ui_template(request, *_ACTIVATE_TPL)


@never_cache
@csrf_protect
@require_http_methods(["GET", "POST"])
@activation_rate_limit
def account_activate(request, token):
    user, record = get_user_for_activation_token(token)

    if request.method == "GET":
        if not user:
            return render(
                request,
                _activate_template(request),
                {
                    "valid": False,
                    "expiry_minutes": ACTIVATION_EXPIRY_MINUTES,
                },
                status=400 if record and record.is_expired else 403,
            )
        return render(
            request,
            _activate_template(request),
            {
                "valid": True,
                "token": token,
                "user": user,
                "expiry_minutes": ACTIVATION_EXPIRY_MINUTES,
                "login_hint": _login_url_for_user(user, request),
            },
        )

    if not user:
        messages.error(
            request,
            "Link inválido ou expirado. Solicite um novo convite ao administrador.",
        )
        return render(
            request,
            _activate_template(request),
            {"valid": False, "expiry_minutes": ACTIVATION_EXPIRY_MINUTES},
            status=403,
        )

    return _handle_activation_post(request, user, token)


@transaction.atomic
def _handle_activation_post(request, user, token):
    password1 = (request.POST.get("password1") or "").strip()
    password2 = (request.POST.get("password2") or "").strip()

    if not password1 or not password2:
        messages.error(request, "Preencha e confirme a nova senha.")
        return _render_form(request, user, token)

    if password1 != password2:
        messages.error(request, "As senhas não coincidem.")
        return _render_form(request, user, token)

    try:
        validate_password(password1, user=user)
    except ValidationError as exc:
        for err in exc.messages:
            messages.error(request, err)
        return _render_form(request, user, token)

    activated = consume_activation_token(token, request)
    if not activated:
        messages.error(request, "Não foi possível concluir a ativação. Solicite um novo link.")
        return render(
            request,
            _activate_template(request),
            {"valid": False, "expiry_minutes": ACTIVATION_EXPIRY_MINUTES},
            status=403,
        )

    user.set_password(password1)
    user.must_change_password = False
    user.save(update_fields=["password", "must_change_password"])

    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    messages.success(
        request,
        "Conta ativada com sucesso! Você já está conectado.",
    )
    logger.info(
        "Senha definida na ativação",
        extra={"user_id": user.id},
    )
    return redirect("dashboard")


def _render_form(request, user, token):
    return render(
        request,
        _activate_template(request),
        {
            "valid": True,
            "token": token,
            "user": user,
            "expiry_minutes": ACTIVATION_EXPIRY_MINUTES,
            "login_hint": _login_url_for_user(user, request),
        },
    )


def _login_url_for_user(user, request):
    if user.role == "RM" or not user.company_id:
        return "/rm/login/"
    return f"/{user.company.slug}/login/"
