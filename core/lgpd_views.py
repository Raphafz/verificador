"""Views LGPD: consentimento, portabilidade e canal do encarregado."""
from __future__ import annotations

import json

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods

from core.audit_trail import record_security_event
from core.lgpd_constants import LEGAL_DOCUMENT_VERSION, REQUIRED_CONSENT_TYPES
from core.lgpd_export import (
    build_user_data_payload,
    create_signed_zip_export,
    payload_to_csv,
    resolve_export_download,
    sign_export_token,
)
from core.models import ConsentRecord, DataSubjectRequest, LgpdExportDownload, Ticket
from core.ui_helpers import ui_template


def _client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _user_has_all_consents(user) -> bool:
    for doc_type in REQUIRED_CONSENT_TYPES:
        if not ConsentRecord.objects.filter(
            user=user,
            document_type=doc_type,
            document_version=LEGAL_DOCUMENT_VERSION,
        ).exists():
            return False
    return True


@login_required
@require_http_methods(["GET", "POST"])
def consent_required(request):
    tpl = ui_template(request, "core/consent_required.html", "auth/consent_v2.html")
    ctx = {"version": LEGAL_DOCUMENT_VERSION}
    if request.method == "POST":
        if request.POST.get("accept") != "yes":
            messages.error(request, "É necessário aceitar os documentos para continuar.")
            return render(request, tpl, ctx)

        ip = _client_ip(request)
        ua = (request.META.get("HTTP_USER_AGENT") or "")[:512]
        for doc_type in REQUIRED_CONSENT_TYPES:
            ConsentRecord.objects.get_or_create(
                user=request.user,
                document_type=doc_type,
                document_version=LEGAL_DOCUMENT_VERSION,
                defaults={"ip_address": ip, "user_agent": ua},
            )

        messages.success(request, "Preferências registradas com sucesso.")
        return redirect("dashboard")

    return render(request, tpl, ctx)


@login_required
def my_data_portal(request):
    consents = ConsentRecord.objects.filter(user=request.user).order_by("-accepted_at")[:20]
    requests_qs = DataSubjectRequest.objects.filter(user=request.user).order_by("-created_at")[:10]
    exports = LgpdExportDownload.objects.filter(user=request.user).order_by("-created_at")[:5]
    return render(request, "core/my_data_portal.html", {
        "consents": consents,
        "requests": requests_qs,
        "exports": exports,
        "version": LEGAL_DOCUMENT_VERSION,
    })


@login_required
@require_GET
def my_data_export(request):
    user = request.user
    fmt = (request.GET.get("format") or "json").lower()
    payload = build_user_data_payload(user)

    DataSubjectRequest.objects.create(
        user=user,
        request_type="export",
        status="completed",
        details=f"Exportação {fmt.upper()} pelo portal do titular",
        ip_address=_client_ip(request),
        completed_at=timezone.now(),
    )
    record_security_event(
        "lgpd_export_download",
        user=user,
        request=request,
        details={"format": fmt},
    )

    stamp = timezone.now().strftime("%Y%m%d")

    if fmt == "zip":
        artifact = create_signed_zip_export(user, request=request)
        token = sign_export_token(artifact.pk, user.pk)
        url = reverse("my_data_export_download", kwargs={"token": token})
        if request.GET.get("redirect") == "1":
            return redirect(url)
        return JsonResponse({
            "download_url": url,
            "expires_at": artifact.expires_at.isoformat(),
            "max_downloads": artifact.max_downloads,
        })

    if fmt == "csv":
        body = payload_to_csv(payload)
        content_type = "text/csv; charset=utf-8"
        filename = f"meus-dados-{user.id}-{stamp}.csv"
    else:
        body = json.dumps(payload, indent=2, ensure_ascii=False, default=str)
        content_type = "application/json; charset=utf-8"
        filename = f"meus-dados-{user.id}-{stamp}.json"

    response = HttpResponse(body, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
@require_GET
def my_data_export_download(request, token: str):
    path = resolve_export_download(token, request.user)
    if not path:
        raise Http404("Link de download expirado ou inválido.")
    record_security_event(
        "lgpd_export_file_served",
        user=request.user,
        request=request,
        details={"path": path.name},
    )
    return FileResponse(path.open("rb"), as_attachment=True, filename=path.name)


@login_required
@require_http_methods(["POST"])
def my_data_delete_request(request):
    user = request.user
    if user.is_superuser or user.is_rm_admin:
        messages.error(
            request,
            "Contas de administrador RM não podem ser excluídas por este fluxo. "
            "Contacte o encarregado de dados.",
        )
        return redirect("my_data_portal")

    if request.POST.get("confirm") != "DELETE":
        messages.error(request, "Digite DELETE para confirmar.")
        return redirect("my_data_portal")

    DataSubjectRequest.objects.create(
        user=user,
        request_type="delete",
        status="pending",
        details="Solicitação de desativação de conta pelo titular",
        ip_address=_client_ip(request),
    )
    user.is_active = False
    user.save(update_fields=["is_active"])
    record_security_event("lgpd_delete_requested", user=user, request=request)
    logout(request)
    messages.success(
        request,
        "Sua conta foi desativada. Para eliminação completa dos dados, "
        "o encarregado analisará em até 15 dias úteis.",
    )
    return redirect("home_redirect")


def dpo_contact_view(request):
    from django.conf import settings

    return render(request, "core/dpo_contact.html", {
        "dpo_email": getattr(settings, "DPO_EMAIL", "privacidade@rmsys.com.br"),
    })
