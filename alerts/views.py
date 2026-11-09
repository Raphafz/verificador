import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from core.models import Company
from core.permissions import company_module_admin_required
from core.bridge_security import log_bridge_api_access, validate_bridge_request

from . import whatsapp_client
from .forms import AlertBridgeConfigForm, WhatsAppLineForm
from .models import AlertBridgeConfig, WhatsAppLine


def _get_or_create_config(company):
    config, _ = AlertBridgeConfig.objects.get_or_create(company=company)
    return config


def _get_line(company, line_id):
    return get_object_or_404(WhatsAppLine, pk=line_id, company=company)


@login_required
@company_module_admin_required("alertas")
def alert_settings(request, company_slug):
    company = get_object_or_404(Company, slug=company_slug)
    config = _get_or_create_config(company)
    lines = list(company.whatsapp_lines.all())

    line_form = WhatsAppLineForm()
    line_rows = [
        {
            "line": line,
            "edit_form": WhatsAppLineForm(instance=line, prefix=f"edit{line.pk}_"),
        }
        for line in lines
    ]

    if request.method == "POST":
        action = request.POST.get("action", "save_config")

        if action == "add_line":
            line_form = WhatsAppLineForm(request.POST)
            if line_form.is_valid():
                from core.quotas import QuotaExceeded, enforce_quota

                try:
                    enforce_quota(company, "whatsapp_chips", user=request.user)
                except QuotaExceeded as exc:
                    messages.error(request, str(exc))
                    return redirect("company:alerts:settings", company_slug=company_slug)
                line = line_form.save(commit=False)
                line.company = company
                line.save()
                messages.success(request, f"Linha «{line.label}» adicionada.")
                return redirect("company:alerts:settings", company_slug=company_slug)
        elif action == "edit_line":
            line_id = request.POST.get("line_id")
            line = _get_line(company, line_id)
            edit_form = WhatsAppLineForm(request.POST, instance=line, prefix=f"edit{line.pk}_")
            if edit_form.is_valid():
                old_mode = line.login_mode
                old_phone = line.normalized_pairing_phone()
                line = edit_form.save()
                new_mode = line.login_mode
                new_phone = line.normalized_pairing_phone()
                changed_creds = old_mode != new_mode or old_phone != new_phone
                reconnect = request.POST.get("reconnect_after_edit") == "1"
                if changed_creds and reconnect and whatsapp_client.worker_online():
                    if new_mode == WhatsAppLine.WHATSAPP_LOGIN_PAIRING and not new_phone:
                        messages.warning(
                            request,
                            "Linha salva. Informe o número e clique em Conectar.",
                        )
                    else:
                        whatsapp_client.start_connect(
                            company_slug,
                            line.pk,
                            line.login_mode,
                            new_phone,
                            label=line.label,
                        )
                        messages.success(
                            request,
                            f"«{line.label}» atualizada. Nova conexão iniciada.",
                        )
                else:
                    messages.success(request, f"«{line.label}» atualizada.")
                return redirect("company:alerts:settings", company_slug=company_slug)
            lines = list(company.whatsapp_lines.all())
            line_rows = [
                {
                    "line": ln,
                    "edit_form": (
                        edit_form
                        if str(ln.pk) == str(line_id)
                        else WhatsAppLineForm(instance=ln, prefix=f"edit{ln.pk}_")
                    ),
                }
                for ln in lines
            ]
            messages.error(request, "Corrija os erros na linha e tente novamente.")
        else:
            form = AlertBridgeConfigForm(request.POST, instance=config)
            if form.is_valid():
                from core.quotas import QuotaExceeded, enforce_quota

                phones = form.cleaned_data.get("whatsapp_alert_phones", "")
                new_count = len(
                    [
                        p
                        for p in phones.split(",")
                        if p.strip()
                    ]
                )
                if new_count:
                    try:
                        enforce_quota(
                            company,
                            "alert_phones",
                            extra=max(0, new_count - len(config.whatsapp_phones_list())),
                            user=request.user,
                        )
                    except QuotaExceeded as exc:
                        messages.error(request, str(exc))
                        return redirect("company:alerts:settings", company_slug=company_slug)
                form.save()
                messages.success(request, "Configuração de alertas salva.")
                return redirect("company:alerts:settings", company_slug=company_slug)
    else:
        form = AlertBridgeConfigForm(instance=config)

    lines_status = []
    if whatsapp_client.worker_online() and lines:
        lines_status = whatsapp_client.list_lines_status(
            company_slug, [line.pk for line in lines]
        )

    status_by_id = {str(s.get("line_id")): s for s in lines_status}

    return render(
        request,
        "alerts/settings.html",
        {
            "company": company,
            "form": form,
            "config": config,
            "lines": lines,
            "line_rows": line_rows,
            "line_form": line_form,
            "status_by_id": status_by_id,
            "worker_online": whatsapp_client.worker_online(),
            "worker_hint": os.getenv(
                "ALERT_BRIDGE_WORKER_CMD",
                "python manage.py runserver",
            ),
        },
    )


@login_required
@company_module_admin_required("alertas")
@require_POST
def whatsapp_line_set_default(request, company_slug, line_id):
    company = get_object_or_404(Company, slug=company_slug)
    line = _get_line(company, line_id)
    line.is_default = True
    line.send_alerts = True
    line.save()
    messages.success(request, f"«{line.label}» marcada para enviar alertas.")
    return redirect("company:alerts:settings", company_slug=company_slug)


@login_required
@company_module_admin_required("alertas")
@require_POST
def whatsapp_line_delete(request, company_slug, line_id):
    company = get_object_or_404(Company, slug=company_slug)
    line = _get_line(company, line_id)
    if whatsapp_client.worker_online():
        whatsapp_client.disconnect(company_slug, line.pk, delete_auth=True)
    label = line.label
    line.delete()
    messages.success(request, f"Linha «{label}» removida.")
    return redirect("company:alerts:settings", company_slug=company_slug)


@login_required
@company_module_admin_required("alertas")
@require_GET
def worker_status(request, company_slug):
    get_object_or_404(Company, slug=company_slug)
    online = whatsapp_client.worker_online()
    return JsonResponse({"online": online})


@login_required
@company_module_admin_required("alertas")
@require_POST
def whatsapp_clear_session(request, company_slug, line_id):
    company = get_object_or_404(Company, slug=company_slug)
    _get_line(company, line_id)
    data = whatsapp_client.clear_local_session(company_slug, line_id)
    return JsonResponse(data)


@login_required
@company_module_admin_required("alertas")
@require_GET
@login_required
@company_module_admin_required("alertas")
@require_GET
def whatsapp_status(request, company_slug, line_id):
    company = get_object_or_404(Company, slug=company_slug)
    _get_line(company, line_id)
    return JsonResponse(whatsapp_client.get_status(company_slug, line_id))


@login_required
@company_module_admin_required("alertas")
@require_GET
def whatsapp_qr(request, company_slug, line_id):
    get_object_or_404(Company, slug=company_slug)
    status, body, content_type = whatsapp_client.fetch_qr_png(company_slug, line_id)
    if status != 200 or not body:
        return HttpResponse(status=404)
    return HttpResponse(body, content_type=content_type or "image/png")


@login_required
@company_module_admin_required("alertas")
@require_POST
def whatsapp_connect(request, company_slug, line_id):
    company = get_object_or_404(Company, slug=company_slug)
    line = _get_line(company, line_id)

    if not whatsapp_client.worker_online():
        return JsonResponse(
            {"error": "Worker MENSAGENS offline. Rode: python manage.py runserver"},
            status=503,
        )

    if line.login_mode == WhatsAppLine.WHATSAPP_LOGIN_PAIRING and not line.normalized_pairing_phone():
        return JsonResponse(
            {"error": "Informe o número desta linha (modo pareamento)."},
            status=400,
        )

    data = whatsapp_client.start_connect(
        company_slug,
        line.pk,
        line.login_mode,
        line.normalized_pairing_phone(),
        label=line.label,
    )
    return JsonResponse(data)


@login_required
@company_module_admin_required("alertas")
@require_POST
def whatsapp_disconnect(request, company_slug, line_id):
    company = get_object_or_404(Company, slug=company_slug)
    _get_line(company, line_id)
    delete_auth = request.POST.get("delete_auth", "1") != "0"
    return JsonResponse(
        whatsapp_client.disconnect(company_slug, line_id, delete_auth=delete_auth)
    )


@require_GET
def worker_configs_api(request):
    err = validate_bridge_request(request)
    if err is not None:
        return err

    configs = (
        AlertBridgeConfig.objects.filter(
            is_active=True,
            company__is_active=True,
            company__module_alertas=True,
        )
        .select_related("company")
        .prefetch_related("company__whatsapp_lines")
    )
    payloads = [
        c.to_worker_payload()
        for c in configs
        if c.telegram_bot_token
    ]
    log_bridge_api_access(request, configs_count=len(payloads))
    return JsonResponse({"configs": payloads, "count": len(payloads)})
