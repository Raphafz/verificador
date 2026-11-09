"""Views MFA — setup TOTP, verificação, backup codes, dispositivos confiáveis."""
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .mfa_lockout import clear_mfa_failures, is_mfa_locked, record_mfa_failure
from .mfa_service import (
    REMEMBER_COOKIE,
    REMEMBER_DAYS,
    create_totp_device,
    generate_backup_codes,
    has_mfa_enabled,
    list_trusted_devices,
    mark_mfa_verified,
    mfa_required_for,
    provisioning_uri,
    qr_png_base64,
    revoke_all_trusted_devices,
    revoke_trusted_device,
    set_remember_device,
    verify_backup_code,
    verify_token,
)
from .permissions import rm_admin_required
from .ui_helpers import ui_template


def _client_ip(request) -> str:
    from core.request_ip import get_client_ip

    return get_client_ip(request)


@login_required
@rm_admin_required
@require_http_methods(["GET", "POST"])
def mfa_setup(request):
    if not mfa_required_for(request.user):
        return redirect("dashboard")
    device = create_totp_device(request.user)
    uri = provisioning_uri(device)
    backup_codes = None
    tpl = ui_template(request, "core/mfa_setup.html", "auth/mfa_setup_v2.html")
    ctx_base = {
        "provisioning_uri": uri,
        "qr_base64": qr_png_base64(uri),
    }
    if request.method == "POST":
        code = (request.POST.get("token") or "").strip()
        if verify_token(request.user, code):
            backup_codes = generate_backup_codes(request.user)
            mark_mfa_verified(request)
            messages.success(request, "Autenticação em dois fatores ativada. Guarde os códigos de backup.")
            return render(
                request,
                tpl,
                {**ctx_base, "backup_codes": backup_codes, "done": True},
            )
        messages.error(request, "Código inválido. Escaneie o QR e tente novamente.")
    return render(
        request,
        tpl,
        {**ctx_base, "backup_codes": backup_codes, "done": False},
    )


@login_required
@require_http_methods(["GET", "POST"])
def mfa_verify(request):
    if not mfa_required_for(request.user):
        return redirect("dashboard")
    tpl = ui_template(request, "core/mfa_verify.html", "auth/mfa_verify_v2.html")
    ctx = {"next": request.GET.get("next", "")}
    if has_mfa_enabled(request.user) is False and request.method == "GET":
        return redirect(reverse("rm:mfa_setup"))
    ip = _client_ip(request)
    locked, retry = is_mfa_locked(request.user.pk, ip)
    if locked:
        messages.error(request, f"Muitas tentativas. Aguarde {retry // 60 + 1} minuto(s).")
        return render(request, tpl, ctx)

    if request.method == "POST":
        code = (request.POST.get("token") or "").strip()
        backup = (request.POST.get("backup_code") or "").strip()
        ok = False
        if backup:
            ok = verify_backup_code(request.user, backup)
        elif code:
            ok = verify_token(request.user, code)
        if ok:
            clear_mfa_failures(request.user.pk, ip)
            mark_mfa_verified(request)
            from core.safe_redirect import safe_redirect

            next_url = request.GET.get("next") or request.POST.get("next")
            response = safe_redirect(request, next_url, fallback_name="dashboard")
            if request.POST.get("remember") == "1":
                raw = set_remember_device(request, request.user)
                response.set_cookie(
                    REMEMBER_COOKIE,
                    raw,
                    max_age=REMEMBER_DAYS * 86400,
                    httponly=True,
                    secure=getattr(settings, "SESSION_COOKIE_SECURE", False),
                    samesite=getattr(settings, "SESSION_COOKIE_SAMESITE", "Lax"),
                )
            return response
        record_mfa_failure(request.user.pk, ip)
        messages.error(request, "Código inválido.")
    return render(request, tpl, ctx)


@login_required
@rm_admin_required
def mfa_recovery(request):
    if request.method == "POST":
        code = (request.POST.get("token") or "").strip()
        if verify_token(request.user, code):
            codes = generate_backup_codes(request.user)
            return render(request, "core/mfa_recovery.html", {"backup_codes": codes, "done": True})
        messages.error(request, "Informe o código do aplicativo autenticador.")
    return render(request, "core/mfa_recovery.html", {"done": False})


@login_required
@rm_admin_required
def mfa_trusted_devices(request):
    devices = list_trusted_devices(request.user)
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "revoke_all":
            n = revoke_all_trusted_devices(request.user)
            messages.success(request, f"{n} dispositivo(s) revogado(s).")
        else:
            did = request.POST.get("device_id")
            if did and revoke_trusted_device(request.user, int(did)):
                messages.success(request, "Dispositivo revogado.")
        return redirect("rm:mfa_trusted_devices")
    return render(request, "core/mfa_trusted_devices.html", {"devices": devices})
