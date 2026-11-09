from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from core.models import Company
from core.permissions import company_access_required, company_module_required

from .forms import CompanyVpnForm, DeleteOnuForm, ListOfflineForm, OltEquipmentForm
from .job_runner import start_delete, start_list_offline
from .models import CompanyVpnConfig, OltEquipment, OnuCleanupJob
from .user_messages import (
    job_status_hint,
    job_status_label,
    parse_job_summary,
    sanitize_vpn_test_log,
    vpn_test_message,
)
from .dispatcher import run_vpn_test_in_container
from .execution import effective_execution_mode

ACTIVE_JOB_STATUSES = ("listing", "running")
POLLING_JOB_STATUSES = ("queued", "listing", "running")


def _job_operation(job: OnuCleanupJob) -> str:
    if job.pending_operation in ("list", "delete"):
        return job.pending_operation
    log = job.log_output or ""
    if "Iniciando exclusão" in log:
        return "delete"
    return "list"


def _create_job(company, user, olt, gpon_port="", serial_numbers=""):
    from core.quotas import QuotaExceeded, enforce_quota

    enforce_quota(company, "olt_jobs_month", user=user)
    return OnuCleanupJob.objects.create(
        company=company,
        olt=olt,
        gpon_port=gpon_port.strip(),
        serial_numbers=serial_numbers,
        created_by=user,
        status="draft",
    )


def _redirect_job_live(request, company_slug, job, op="list"):
    return redirect(
        "company:olt_ops:job_live",
        company_slug=company_slug,
        pk=job.pk,
    )


@login_required
@company_access_required(require_admin=False, allow_user_role=True)
@company_module_required("olt")
def olt_home(request, company_slug):
    company = get_object_or_404(Company, slug=company_slug)
    olts = OltEquipment.objects.filter(company=company, is_active=True)
    jobs = OnuCleanupJob.objects.filter(company=company).select_related("olt")[:8]

    list_form = ListOfflineForm(company=company)
    delete_form = DeleteOnuForm(company=company)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "list_offline":
            list_form = ListOfflineForm(request.POST, company=company)
            if list_form.is_valid():
                olt = list_form.cleaned_data["olt"]
                gpon_port = list_form.cleaned_data["gpon_port"]
                try:
                    job = _create_job(company, request.user, olt, gpon_port=gpon_port)
                except ValidationError as exc:
                    messages.error(request, str(exc))
                else:
                    start_list_offline(job.pk)
                    return _redirect_job_live(request, company_slug, job)
        elif action == "delete_onus":
            delete_form = DeleteOnuForm(request.POST, company=company)
            if delete_form.is_valid():
                if request.POST.get("confirm") != "yes":
                    messages.error(
                        request,
                        "Marque a caixa de confirmação para continuar com a exclusão.",
                    )
                else:
                    olt = delete_form.cleaned_data["olt"]
                    serials = delete_form.cleaned_data["serial_numbers"]
                    try:
                        job = _create_job(
                            company,
                            request.user,
                            olt,
                            serial_numbers=serials,
                        )
                    except ValidationError as exc:
                        messages.error(request, str(exc))
                    else:
                        start_delete(job.pk)
                        return _redirect_job_live(request, company_slug, job)

    vpn_config = None
    try:
        vpn_config = company.vpn_config
    except CompanyVpnConfig.DoesNotExist:
        pass

    return render(
        request,
        "olt_ops/home.html",
        {
            "company": company,
            "olts": olts,
            "jobs": jobs,
            "list_form": list_form,
            "delete_form": delete_form,
            "vpn_config": vpn_config,
        },
    )


@login_required
@company_access_required(require_admin=False, allow_user_role=True)
@company_module_required("olt")
def job_live(request, company_slug, pk):
    company = get_object_or_404(Company, slug=company_slug)
    job = get_object_or_404(OnuCleanupJob, pk=pk, company=company)
    status_url = reverse(
        "company:olt_ops:job_status",
        kwargs={"company_slug": company_slug, "pk": job.pk},
    )
    return render(
        request,
        "olt_ops/job_live.html",
        {
            "company": company,
            "job": job,
            "status_url": status_url,
        },
    )


@login_required
@company_access_required(require_admin=False, allow_user_role=True)
@company_module_required("olt")
@require_GET
def job_status(request, company_slug, pk):
    company = get_object_or_404(Company, slug=company_slug)
    job = get_object_or_404(OnuCleanupJob, pk=pk, company=company)
    running = job.status in ACTIVE_JOB_STATUSES
    queued = job.status == "queued"
    log = job.log_output or ""
    user_summary = parse_job_summary(log) if not running and not queued else ""
    operation = _job_operation(job)
    return JsonResponse(
        {
            "status": job.status,
            "operation": operation,
            "status_label": job.get_status_display(),
            "user_status_label": job_status_label(job.status),
            "user_hint": job_status_hint(job.status, running=running or queued),
            "user_summary": user_summary,
            "log": log,
            "serials": job.serial_numbers or "",
            "serial_count": len(job.serial_list()),
            "running": running,
            "queued": queued,
            "done": job.status not in POLLING_JOB_STATUSES,
        }
    )


@login_required
@company_access_required(require_admin=True)
@company_module_required("olt")
def vpn_settings(request, company_slug):
    company = get_object_or_404(Company, slug=company_slug)
    vpn, _created = CompanyVpnConfig.objects.get_or_create(company=company)
    test_olt = OltEquipment.objects.filter(company=company, is_active=True).first()

    if request.method == "POST":
        form = CompanyVpnForm(request.POST, instance=vpn)
        if form.is_valid():
            form.save()
            messages.success(request, "Configurações de VPN salvas com sucesso.")
            return redirect("company:olt_ops:vpn_settings", company_slug=company_slug)
    else:
        form = CompanyVpnForm(instance=vpn)

    test_log = request.session.pop("olt_vpn_test_log", None)
    vpn_test_ok = request.session.pop("olt_vpn_test_ok", None)
    return render(
        request,
        "olt_ops/vpn_settings.html",
        {
            "company": company,
            "form": form,
            "test_olt": test_olt,
            "vpn_test_log": test_log,
            "vpn_test_ok": vpn_test_ok,
        },
    )


@login_required
@company_access_required(require_admin=True)
@company_module_required("olt")
@require_POST
def vpn_test(request, company_slug):
    company = get_object_or_404(Company, slug=company_slug)
    vpn = get_object_or_404(CompanyVpnConfig, company=company)
    if not vpn.is_configured():
        messages.error(
            request,
            "Preencha todos os campos da VPN e marque “Usar VPN nas operações OLT”.",
        )
        return redirect("company:olt_ops:vpn_settings", company_slug=company_slug)

    olt = OltEquipment.objects.filter(company=company, is_active=True).first()
    if not olt:
        messages.error(request, "Cadastre uma OLT ativa antes de testar a conexão.")
        return redirect("company:olt_ops:vpn_settings", company_slug=company_slug)

    if effective_execution_mode(company) == "container":
        ok, log = run_vpn_test_in_container(company, olt.host, olt.connection_port)
    else:
        from .vpn_manager import test_vpn_to_host

        ok, log = test_vpn_to_host(company, olt.host, olt.connection_port)
    title, detail = vpn_test_message(ok)
    if ok:
        messages.success(request, f"{title}. {detail}")
    else:
        messages.error(request, f"{title}. {detail}")
    request.session["olt_vpn_test_log"] = sanitize_vpn_test_log(log)
    request.session["olt_vpn_test_ok"] = ok
    request.session.modified = True
    return redirect("company:olt_ops:vpn_settings", company_slug=company_slug)


@login_required
@company_access_required(require_admin=True)
@company_module_required("olt")
def olt_list(request, company_slug):
    company = get_object_or_404(Company, slug=company_slug)
    olts = OltEquipment.objects.filter(company=company).order_by("name")
    return render(request, "olt_ops/olt_list.html", {"company": company, "olts": olts})


@login_required
@company_access_required(require_admin=True)
@company_module_required("olt")
def olt_create(request, company_slug):
    company = get_object_or_404(Company, slug=company_slug)
    if request.method == "POST":
        form = OltEquipmentForm(request.POST)
        if form.is_valid():
            from core.quotas import QuotaExceeded, enforce_quota

            try:
                enforce_quota(company, "olts", user=request.user)
            except QuotaExceeded as exc:
                messages.error(request, str(exc))
            else:
                olt = form.save(commit=False)
                olt.company = company
                olt.save()
                messages.success(request, "OLT cadastrada com sucesso.")
                return redirect("company:olt_ops:olt_list", company_slug=company_slug)
    else:
        form = OltEquipmentForm()
    return render(
        request,
        "olt_ops/olt_form.html",
        {"company": company, "form": form, "action": "Cadastrar"},
    )


@login_required
@company_access_required(require_admin=True)
@company_module_required("olt")
def olt_edit(request, company_slug, pk):
    company = get_object_or_404(Company, slug=company_slug)
    olt = get_object_or_404(OltEquipment, pk=pk, company=company)
    if request.method == "POST":
        form = OltEquipmentForm(request.POST, instance=olt)
        if form.is_valid():
            form.save()
            messages.success(request, "Dados da OLT atualizados.")
            return redirect("company:olt_ops:olt_list", company_slug=company_slug)
    else:
        form = OltEquipmentForm(instance=olt)
    return render(
        request,
        "olt_ops/olt_form.html",
        {"company": company, "form": form, "olt": olt, "action": "Editar"},
    )


@login_required
@company_access_required(require_admin=False, allow_user_role=True)
@company_module_required("olt")
def job_detail(request, company_slug, pk):
    company = get_object_or_404(Company, slug=company_slug)
    job = get_object_or_404(OnuCleanupJob, pk=pk, company=company)
    return render(
        request,
        "olt_ops/job_detail.html",
        {"company": company, "job": job},
    )


@login_required
@company_access_required(require_admin=False, allow_user_role=True)
@company_module_required("olt")
@require_POST
def job_list_offline(request, company_slug, pk):
    company = get_object_or_404(Company, slug=company_slug)
    job = get_object_or_404(OnuCleanupJob, pk=pk, company=company)
    if job.status in ACTIVE_JOB_STATUSES:
        messages.warning(request, "Operação já em andamento.")
        return redirect("company:olt_ops:job_live", company_slug=company_slug, pk=job.pk)
    start_list_offline(job.pk)
    return redirect("company:olt_ops:job_live", company_slug=company_slug, pk=job.pk)


@login_required
@company_access_required(require_admin=False, allow_user_role=True)
@company_module_required("olt")
@require_POST
def job_execute_delete(request, company_slug, pk):
    company = get_object_or_404(Company, slug=company_slug)
    job = get_object_or_404(OnuCleanupJob, pk=pk, company=company)
    if job.status in ACTIVE_JOB_STATUSES:
        messages.warning(request, "Operação já em andamento.")
        return redirect("company:olt_ops:job_live", company_slug=company_slug, pk=job.pk)
    if not job.serial_list():
        messages.error(request, "Informe serials antes de excluir.")
        return redirect("company:olt_ops:job_detail", company_slug=company_slug, pk=job.pk)
    if request.POST.get("confirm") != "yes":
        messages.error(request, "Confirme a exclusão irreversível.")
        return redirect("company:olt_ops:job_detail", company_slug=company_slug, pk=job.pk)
    start_delete(job.pk)
    return redirect("company:olt_ops:job_live", company_slug=company_slug, pk=job.pk)
