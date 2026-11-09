from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponseForbidden, HttpResponse, Http404, JsonResponse
from django.core.exceptions import ValidationError, PermissionDenied
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import cache_page
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.core.paginator import Paginator
from django.urls import reverse
from django.utils import timezone
import logging
import os
import csv
from django.views.decorators.csrf import ensure_csrf_cookie
from datetime import timedelta

from .forms import CTOMapFileForm, CompanyForm, CustomUserForm, CustomUserChangeForm
from .models import CTOMapFile, Company, CustomUser
from .utils import send_user_credentials_email
from .ticket_views import (
    company_ticket_create, company_ticket_list, company_ticket_detail,
    rm_ticket_list, rm_ticket_detail,
    get_new_messages, rm_get_new_messages
)
from .notification_views import (
    get_notifications, mark_notification_read, mark_all_notifications_read, get_unread_count
)
from .permissions import (
    is_rm_admin, is_company_admin, can_manage_users,
    rm_admin_required, user_management_required, company_access_required, company_access_required_json
)
from .reports import ReportGenerator, ExportManager
from .audit_logger import log_user_action, log_data_access
from .rate_limiting import login_rate_limit, upload_rate_limit, general_rate_limit
from .ui_helpers import ui_template
from .verificador_service import VerificadorService, VerificadorIntegrationManager
from ftth_viewer.models import ViabilidadeCache

logger = logging.getLogger(__name__)


# ===== PÁGINAS LEGAIS E DOCUMENTAÇÃO =====

def termos_uso_view(request):
    """Página de Termos de Uso"""
    return render(request, 'legal/termos_uso.html')


def politica_privacidade_view(request):
    """Página de Política de Privacidade"""
    return render(request, 'legal/politica_privacidade.html')


def politica_cookies_view(request):
    """Página de Política de Cookies"""
    return render(request, 'legal/politica_cookies.html')


def lgpd_view(request):
    """Página de Compliance LGPD"""
    return render(request, 'legal/lgpd.html')


def faq_view(request):
    """Página de Perguntas Frequentes (FAQ)"""
    return render(request, 'docs/faq.html')


def ajuda_view(request):
    """Página de Ajuda/Suporte"""
    return render(request, 'docs/ajuda.html')


def manual_usuario_view(request):
    """Página do Manual do Usuário"""
    return render(request, 'docs/manual_usuario.html')


@ensure_csrf_cookie
def login_view(request):
    return render(request, ui_template(request, "login.html", "auth/login_v2.html"))


@login_required
def logout_view(request):
    logout(request)
    return redirect('rm:login')


@login_required
def company_logout_view(request, company_slug):
    logout(request)
    return redirect('company:login', company_slug=company_slug)


def home_redirect(request):
    return redirect('/rm/login/')


@ensure_csrf_cookie
@login_rate_limit
def rm_login_view(request):
    """
    View de login RM - acessível para todos, incluindo superusuários.
    Não requer autenticação prévia para acessar a página.
    """
    from core.login_session_messages import flash_session_end_reason

    flash_session_end_reason(request)

    # Log para debug de CSRF
    logger.debug(f"rm_login_view: method={request.method}, path={request.path}, host={request.get_host()}, user={request.user.username if request.user.is_authenticated else 'anon'}, is_superuser={request.user.is_superuser if request.user.is_authenticated else False}")
    logger.debug(f"rm_login_view: is_secure={request.is_secure()}, META.get('HTTP_ORIGIN')={request.META.get('HTTP_ORIGIN', 'N/A')}")
    logger.debug(f"rm_login_view: CSRF cookie presente={request.META.get('CSRF_COOKIE', 'N/A')}")
    
    if request.method == 'POST':
        from .login_lockout import clear_failures, is_locked, lockout_response, record_failure

        logger.info(f"rm_login_view POST: origin={request.META.get('HTTP_ORIGIN', 'N/A')}, referer={request.META.get('HTTP_REFERER', 'N/A')}")
        logger.info(f"rm_login_view POST: CSRF token presente={bool(request.POST.get('csrfmiddlewaretoken'))}")

        input_id = (request.POST.get('username', '') or '').strip()
        locked, retry = is_locked(request, input_id)
        if locked:
            return lockout_response(request, retry)

        from .login_auth import (
            INVALID_LOGIN_MESSAGE,
            apply_login_failure_delay,
            resolve_login_username,
        )
        from .safe_redirect import safe_redirect

        password = (request.POST.get('password', '') or '').strip()
        username = resolve_login_username(input_id)
        user = authenticate(request, username=username, password=password)
        if user is not None:
            # Verificar se o usuário está ativo
            if not user.is_active:
                logger.warning(f"Tentativa de login com conta desativada: {user.username}")
                messages.error(request, 'Sua conta está desativada. Contate o administrador.')
            # Verificar se é admin RM ou superuser
            elif user.is_rm_admin or user.is_superuser:
                clear_failures(request, input_id)
                login(request, user)
                # Log detalhado para debug
                logger.info(f"Login bem-sucedido: {user.username} (role: {user.role}, is_superuser: {user.is_superuser}, is_rm_admin: {user.is_rm_admin})")
                logger.info(f"Sessão criada: session_key={request.session.session_key}, user_id={user.id}")
                # Verificar novamente após login
                if not request.user.is_authenticated:
                    logger.error(f"ERRO: Usuário não autenticado após login() - {user.username}")
                if not (request.user.is_rm_admin or request.user.is_superuser):
                    logger.error(f"ERRO: Usuário não tem permissão RM após login - {request.user.username} (role: {request.user.role})")
                
                # Verificar se usuário precisa mudar senha (middleware fará o redirecionamento)
                if hasattr(user, 'must_change_password') and user.must_change_password:
                    return redirect('dashboard')
                
                next_url = request.GET.get('next') or request.POST.get('next')
                if next_url and str(next_url).strip():
                    logger.info("Redirecionamento pós-login RM (next validado)")
                    return safe_redirect(request, next_url, fallback_name="dashboard")
                return redirect('dashboard')
            else:
                # Usuário autenticado mas não é admin RM - pode tentar login da empresa
                logger.warning(f"Tentativa de login RM sem permissão: {user.username} (role: {user.role}, is_rm_admin: {user.is_rm_admin}, is_superuser: {user.is_superuser})")
                messages.error(request, 'Você não tem permissão para acessar esta área. Tente fazer login através da página da sua empresa.')
        else:
            record_failure(request, input_id)
            apply_login_failure_delay()
            logger.warning("Tentativa de login RM com credenciais inválidas")
            messages.error(request, INVALID_LOGIN_MESSAGE)
    return render(request, ui_template(request, "login.html", "auth/login_v2.html"))


@login_required
@rm_admin_required
def company_list(request):
    from django.core.paginator import Paginator
    
    # Otimizar query com only() para campos necessários
    from .cnpj_utils import cnpj_digits, hash_cnpj

    qs = Company.objects.all().only(
        'id', 'name', 'slug', 'cnpj', 'cnpj_hash', 'email', 'is_active',
    ).order_by('name')
    q = request.GET.get('q', '').strip()
    if q:
        filters = Q(name__icontains=q) | Q(email__icontains=q)
        digits = cnpj_digits(q)
        if len(digits) == 14:
            filters |= Q(cnpj_hash=hash_cnpj(digits))
        qs = qs.filter(filters)
    paginator = Paginator(qs, 12)
    page_number = request.GET.get('page')
    companies = paginator.get_page(page_number)
    return render(request, 'core/rm_companies.html', {'companies': companies, 'q': q})


@login_required
@rm_admin_required
def rm_admin_dashboard(request):
    """Dashboard administrativo RM"""
    logger.info(f"rm_admin_dashboard acessado por: {request.user.username} (role: {request.user.role}, is_superuser: {request.user.is_superuser}, is_rm_admin: {request.user.is_rm_admin})")
    from django.utils import timezone
    
    # Usar cache para estatísticas que não mudam frequentemente
    cache_key = f'rm_dashboard_stats_{request.user.id}'
    cached_stats = cache.get(cache_key)
    
    if cached_stats is None:
        # Buscar dados do banco com otimizações
        companies = Company.objects.all().only('id', 'name', 'slug', 'is_active')
        active_companies = companies.filter(is_active=True).count()
        total_users = CustomUser.objects.only('id').count()
        total_maps = CTOMapFile.objects.only('id').count()
        
        # Atividades recentes (últimos uploads e criações) - usar select_related
        # Note: file_name é uma propriedade (@property), não um campo do banco, então não pode estar no .only()
        recent_maps = CTOMapFile.objects.select_related('company', 'uploaded_by').only(
            'file', 'uploaded_at', 'company__name', 'uploaded_by__first_name', 
            'uploaded_by__last_name', 'uploaded_by__username'
        ).order_by('-uploaded_at')[:5]
        
        recent_activities = []
        for map_file in recent_maps:
            recent_activities.append({
                'icon': 'map',
                'description': f"Mapa '{map_file.file_name}' enviado por {map_file.uploaded_by.get_full_name() or map_file.uploaded_by.username}",
                'timestamp': map_file.uploaded_at,
                'company': map_file.company.name if map_file.company else 'N/A'
            })
        
        cached_stats = {
            'total_companies': companies.count(),
            'active_companies': active_companies,
            'total_users': total_users,
            'total_maps': total_maps,
            'recent_activities': recent_activities,
        }
        # Cache por 5 minutos
        cache.set(cache_key, cached_stats, 300)
    
    activation_email_users = (
        CustomUser.objects.filter(email__isnull=False)
        .exclude(email="")
        .only("id", "username", "email", "first_name", "last_name")
        .order_by("username")
    )

    context = {
        'companies': Company.objects.all().only('id', 'name', 'slug', 'is_active'),
        'total_companies': cached_stats['total_companies'],
        'active_companies': cached_stats['active_companies'],
        'total_users': cached_stats['total_users'],
        'total_maps': cached_stats['total_maps'],
        'today': timezone.now(),
        'recent_activities': cached_stats['recent_activities'],
        'activation_email_users': activation_email_users,
    }
    try:
        from alerts.models import AlertBridgeWorkerStatus

        context["bridge_status"] = AlertBridgeWorkerStatus.get_status()
    except Exception:
        context["bridge_status"] = {"healthy": None, "message": "Status indisponível."}
    
    return render(request, 'core/rm_dashboard.html', context)


@login_required
@rm_admin_required
def rm_tenant_usage(request):
    """Painel RM: uso e quotas por tenant."""
    from core.quotas import get_usage, get_usage_summary

    q = request.GET.get("q", "").strip()
    plan = request.GET.get("plan", "").strip()
    companies = Company.objects.all().order_by("name")
    if q:
        companies = companies.filter(name__icontains=q)
    if plan in ("P", "M", "G", "XL"):
        companies = companies.filter(plan_code=plan)

    rows = []
    for company in companies:
        usage = get_usage(company)
        summary = get_usage_summary(company)
        rows.append(
            {
                "company": company,
                "usage": usage,
                "summary": summary,
                "at_limit_count": sum(1 for item in summary["items"] if item["at_limit"]),
                "near_limit_count": sum(1 for item in summary["items"] if item["near_limit"]),
            }
        )

    return render(
        request,
        "core/rm_tenant_usage.html",
        {
            "rows": rows,
            "q": q,
            "plan": plan,
            "plan_choices": Company._meta.get_field("plan_code").choices,
        },
    )


@login_required
@rm_admin_required
def rm_company_portal(request, company_slug):
    company = get_object_or_404(Company, slug=company_slug)
    users_qs = CustomUser.objects.filter(company=company)
    maps_qs = CTOMapFile.objects.filter(company=company)
    context = {
        'company': company,
        'total_users': users_qs.count(),
        'active_users': users_qs.filter(is_active=True).count(),
        'total_maps': maps_qs.count(),
        'recent_maps': maps_qs.order_by('-uploaded_at')[:5],
    }
    return render(request, 'core/rm_company_portal.html', context)


@login_required
@rm_admin_required
def rm_company_login_check(request, company_slug):
    if request.user.is_authenticated and request.user.is_rm_admin:
        return redirect('rm:company_portal', company_slug=company_slug)
    return redirect('rm:login')


@login_required
@rm_admin_required
def rm_user_list(request):
    q = request.GET.get('q', '').strip()
    users = CustomUser.objects.select_related('company').only(
        'id', 'username', 'email', 'first_name', 'last_name', 'role', 
        'is_active', 'company__name', 'company__slug'
    ).order_by('username')
    if q:
        users = users.filter(Q(username__icontains=q) | Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q))
    return render(request, 'rm/users/list.html', {'users': users, 'q': q})


@login_required
@rm_admin_required
def rm_user_create(request):
    """Cria um novo usuário no painel RM"""
    logger.debug(f"rm_user_create: method={request.method}, user={request.user.username}")
    
    if request.method == 'POST':
        logger.debug(f"rm_user_create POST: dados recebidos - {request.POST.dict()}")
        form = CustomUserForm(request.POST, current_user=request.user)
        
        logger.debug(f"rm_user_create: formulário criado, is_valid={form.is_valid()}")
        if not form.is_valid():
            logger.warning(f"Formulário inválido:")
            logger.warning(f"  Erros de campos: {form.errors.as_json()}")
            if form.non_field_errors():
                logger.warning(f"  Erros gerais: {list(form.non_field_errors())}")
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    logger.debug(f"Salvando usuário...")
                    user = form.save()
                    
                    if getattr(form, '_send_welcome_email', False):
                        temp_password = getattr(form, '_generated_password', None)
                        email_sent = send_user_credentials_email(
                            user, plain_password=temp_password, request=request
                        )
                        if email_sent:
                            messages.success(
                                request,
                                f'Usuário {user.username} criado. Enviamos um e-mail de boas-vindas '
                                f'com a senha temporária para {user.email}. No primeiro acesso será '
                                f'necessário definir uma nova senha.',
                            )
                        else:
                            messages.warning(
                                request,
                                f'Usuário {user.username} criado, mas o e-mail de boas-vindas não foi enviado. '
                                f'Informe a senha temporária manualmente ou redefina a senha.',
                            )
                    else:
                        messages.success(request, f'Usuário {user.username} criado com sucesso!')
                    
                    logger.info(f"Usuário criado com sucesso: {user.username} (role: {user.role}, company: {user.company.name if user.company else 'N/A'})")
                    return redirect('rm:user_list')
            except ValidationError as e:
                # Erros de validação são tratados no formulário
                # Quando ValidationError é lançado no save(), o formulário adiciona os erros aos campos
                # Mas o formulário ainda está marcado como válido, então precisamos marcar como inválido
                logger.warning(f"Erro de validação ao criar usuário: {str(e)}")
                logger.warning(f"Erros no formulário após ValidationError: {form.errors}")
                # Não recriar o formulário - manter os erros já adicionados
                # A view continuará e exibirá o formulário com erros
            except Exception as e:
                logger.error(f"Erro ao criar usuário: {str(e)}", exc_info=True)
                import traceback
                logger.error(f"Traceback completo: {traceback.format_exc()}")
                # Adicionar erro ao formulário se possível
                if hasattr(form, 'add_error'):
                    form.add_error(None, f'Erro ao criar usuário: {str(e)}')
                messages.error(request, f'Erro ao criar usuário: {str(e)}')
        
        # Logar erros do formulário se houver
        if not form.is_valid() or form.errors:
            logger.warning(f"Formulário tem erros:")
            for field, errors in form.errors.items():
                logger.warning(f"  Campo '{field}': {list(errors)}")
            if form.non_field_errors():
                logger.warning(f"  Erros gerais: {list(form.non_field_errors())}")
    else:
        form = CustomUserForm(current_user=request.user)
    
    # Adicionar action para o template
    context = {
        'form': form,
        'action': 'Criar'
    }
    return render(request, 'rm/users/form.html', context)


@login_required
@rm_admin_required
def rm_user_delete(request, user_id):
    if request.method == 'POST':
        try:
            user = get_object_or_404(CustomUser, id=user_id)
            
            # Não permitir deletar superusuários
            if user.is_superuser:
                return JsonResponse({
                    'success': False,
                    'message': 'Não é possível deletar superusuários.'
                }, status=400)
            
            # Não permitir deletar o próprio usuário
            if user == request.user:
                return JsonResponse({
                    'success': False,
                    'message': 'Não é possível deletar seu próprio usuário.'
                }, status=400)
            
            username = user.username
            user.delete()
            
            return JsonResponse({
                'success': True,
                'message': f'Usuário {username} deletado com sucesso!'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Erro ao deletar usuário: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'message': 'Método não permitido.'
    }, status=405)


@login_required
@rm_admin_required
@require_http_methods(["POST"])
def rm_user_send_email(request, user_id):
    """Envia e-mail transacional (template escolhido) para o usuário."""
    from .rm_transactional_email import (
        get_template,
        get_templates_for_user,
        send_rm_user_email,
        success_message,
    )

    user_obj = get_object_or_404(CustomUser, id=user_id)

    if not (user_obj.email or "").strip():
        return JsonResponse(
            {
                "success": False,
                "message": "Este usuário não possui e-mail cadastrado.",
            },
            status=400,
        )

    template_id = (request.POST.get("template") or "activation").strip()
    if not get_template(template_id):
        return JsonResponse(
            {"success": False, "message": "Template de e-mail inválido."},
            status=400,
        )

    available_ids = {t["id"] for t in get_templates_for_user(user_obj)}
    if template_id not in available_ids:
        return JsonResponse(
            {
                "success": False,
                "message": "Este template não está disponível para este usuário.",
            },
            status=400,
        )

    ticket_id_raw = (request.POST.get("ticket_id") or "").strip()
    ticket_id = int(ticket_id_raw) if ticket_id_raw.isdigit() else None

    try:
        sent = send_rm_user_email(
            template_id,
            user_obj,
            request=request,
            ticket_id=ticket_id,
        )
    except ValueError as exc:
        return JsonResponse({"success": False, "message": str(exc)}, status=400)
    except Exception as exc:
        logger.exception(
            "Falha ao enviar e-mail transacional (RM)",
            extra={
                "target_user_id": user_obj.id,
                "admin_id": request.user.id,
                "template": template_id,
            },
        )
        return JsonResponse(
            {"success": False, "message": f"Erro ao enviar e-mail: {exc}"},
            status=500,
        )

    if sent:
        log_user_action(
            request.user,
            "rm_send_user_email",
            details={
                "target_user_id": user_obj.id,
                "target_username": user_obj.username,
                "template": template_id,
            },
            ip_address=request.META.get("REMOTE_ADDR"),
        )
        return JsonResponse(
            {
                "success": True,
                "message": success_message(template_id, user_obj),
                "email": user_obj.email,
                "template": template_id,
            }
        )

    return JsonResponse(
        {
            "success": False,
            "message": "Não foi possível enviar o e-mail. Verifique a configuração de e-mail.",
        },
        status=500,
    )


rm_user_send_activation_email = rm_user_send_email


@login_required
@rm_admin_required
def rm_user_details(request, user_id):
    """Retorna detalhes completos do usuário em JSON"""
    user_obj = get_object_or_404(CustomUser, id=user_id)
    
    return JsonResponse({
        'id': user_obj.id,
        'username': user_obj.username,
        'email': user_obj.email,
        'first_name': user_obj.first_name or '',
        'last_name': user_obj.last_name or '',
        'full_name': user_obj.get_full_name() or user_obj.username,
        'phone': user_obj.phone or '-',
        'role': user_obj.get_role_display(),
        'role_code': user_obj.role,
        'company': user_obj.company.name if user_obj.company else '-',
        'is_active': user_obj.is_active,
        'is_staff': user_obj.is_staff,
        'is_superuser': user_obj.is_superuser,
        'last_login': user_obj.last_login.strftime('%d/%m/%Y %H:%M') if user_obj.last_login else 'Nunca',
        'date_joined': user_obj.date_joined.strftime('%d/%m/%Y %H:%M') if user_obj.date_joined else None,
        'created_at': user_obj.created_at.strftime('%d/%m/%Y %H:%M') if hasattr(user_obj, 'created_at') and user_obj.created_at else None,
        'updated_at': user_obj.updated_at.strftime('%d/%m/%Y %H:%M') if hasattr(user_obj, 'updated_at') and user_obj.updated_at else None,
    })

@login_required
@rm_admin_required
def rm_user_edit(request, user_id):
    user_obj = get_object_or_404(CustomUser, id=user_id)
    if request.method == 'POST':
        form = CustomUserChangeForm(request.POST, instance=user_obj)
        if form.is_valid():
            with transaction.atomic():
                form.save()
                messages.success(request, 'Usuário atualizado com sucesso!')
                return redirect('rm:user_list')
    else:
        form = CustomUserChangeForm(instance=user_obj)
    return render(request, 'rm/users/form.html', {
        'form': form,
        'user_obj': user_obj,
        'action': 'Editar',
    })


@ensure_csrf_cookie
@login_rate_limit
def company_login_view(request, company_slug):
    from core.login_session_messages import flash_session_end_reason

    flash_session_end_reason(request)
    context = {'company_slug': company_slug}
    if request.method == 'POST':
        from .login_lockout import clear_failures, is_locked, lockout_response, record_failure

        input_id = (request.POST.get('username', '') or '').strip()
        locked, retry = is_locked(request, input_id)
        if locked:
            return lockout_response(request, retry)

        from .login_auth import (
            INVALID_LOGIN_COMPANY_MESSAGE,
            apply_login_failure_delay,
            resolve_login_username,
        )

        password = (request.POST.get('password', '') or '').strip()
        username = resolve_login_username(input_id)
        user = authenticate(request, username=username, password=password)
        
        # Debug logging (apenas em nível DEBUG para não expor informações sensíveis)
        logger.debug(f"Login attempt for company: {company_slug}")
        if user:
            logger.debug(f"User authentication successful for company: {company_slug}")
            if not user.company:
                logger.warning("User without company associated attempted login")
        else:
            logger.debug("Authentication failed - invalid credentials")
        
        if user is not None and user.company and user.company.slug == company_slug:
            clear_failures(request, input_id)
            login(request, user)
            logger.info(f"Successful login for company: {company_slug}")
            
            # Verificar se usuário precisa mudar senha (middleware fará o redirecionamento)
            if hasattr(user, 'must_change_password') and user.must_change_password:
                return redirect('dashboard')
            
            from core.modules import post_login_redirect_url
            return redirect(post_login_redirect_url(user))
        else:
            record_failure(request, input_id)
            apply_login_failure_delay()
            logger.warning(
                "Falha de login empresa",
                extra={"company_slug": company_slug},
            )
            messages.error(request, INVALID_LOGIN_COMPANY_MESSAGE)
    return render(request, ui_template(request, "company/login.html", "auth/login_v2.html"), context)


@login_required
@company_access_required(require_admin=False, allow_user_role=True)
def company_hub(request, company_slug):
    """Hub unificado — escolha de módulos (Verificador, Alertas, OLT)."""
    from core.modules import get_company_modules

    company = get_object_or_404(Company, slug=company_slug)
    modules = get_company_modules(company, user=request.user)

    users_qs = CustomUser.objects.filter(company=company)
    maps_qs = CTOMapFile.objects.filter(company=company)
    context = {
        'company': company,
        'saas_modules': modules,
        'total_users': users_qs.count(),
        'total_maps': maps_qs.count(),
    }
    return render(request, 'core/company_hub.html', context)


@login_required
@company_access_required(require_admin=False, allow_user_role=True)
def company_dashboard(request, company_slug):
    """Dashboard administrativo — apenas quando verificador está ativo."""
    company = get_object_or_404(Company, slug=company_slug)

    if not company.has_module('verificador'):
        return redirect('company:hub', company_slug=company_slug)

    logger.debug(f"Dashboard access - company: {company_slug}, user_id: {request.user.id}, role: {request.user.role}")

    users_qs = CustomUser.objects.filter(company=company)
    maps_qs = CTOMapFile.objects.filter(company=company)

    recent_maps = (
        maps_qs.select_related('uploaded_by')
        .only(
            'file',
            'uploaded_at',
            'uploaded_by__first_name',
            'uploaded_by__last_name',
            'uploaded_by__username',
            'is_processed',
        )
        .order_by('-uploaded_at')[:8]
    )
    recent_activities = []
    for map_file in recent_maps:
        status = 'processado' if map_file.is_processed else 'pendente'
        recent_activities.append({
            'icon': 'cloud-upload-alt',
            'description': (
                f"Mapa «{map_file.file_name}» enviado por "
                f"{map_file.uploaded_by.get_full_name() or map_file.uploaded_by.username} "
                f"({status})"
            ),
            'timestamp': map_file.uploaded_at,
        })

    context = {
        'company': company,
        'total_users': users_qs.count(),
        'active_users': users_qs.filter(is_active=True).count(),
        'total_maps': maps_qs.count(),
        'maps_processed': maps_qs.filter(is_processed=True).count(),
        'recent_activities': recent_activities,
    }
    return render(request, 'core/company_dashboard.html', context)


@login_required
@company_access_required(require_admin=False, allow_user_role=True)
def company_verificador(request, company_slug):
    """Verificador - acessível para todos os usuários da empresa"""
    from ftth_viewer.views import index as ftth_index
    return ftth_index(request, company_slug=company_slug)


@login_required
@company_access_required(require_admin=False, allow_user_role=True)
def company_map_upload_page(request, company_slug):
    """Página de upload de mapas CTO"""
    import os
    company = get_object_or_404(Company, slug=company_slug)
    maps_qs = CTOMapFile.objects.filter(company=company)
    maps_total = maps_qs.count()
    maps_processed = maps_qs.filter(is_processed=True).count()
    maps_pending = maps_total - maps_processed
    maps = maps_qs.order_by('-uploaded_at')[:50]

    # Adicionar informações de tamanho de arquivo com tratamento de erro
    for map in maps:
        try:
            if map.file and map.file.name:
                map.file_size_bytes = os.path.getsize(map.file.path) if os.path.exists(map.file.path) else None
                map.original_filename = os.path.basename(map.file.name)
            else:
                map.file_size_bytes = None
                map.original_filename = getattr(map, 'description', 'N/A')
        except (FileNotFoundError, ValueError, OSError):
            map.file_size_bytes = None
            map.original_filename = getattr(map, 'description', 'N/A')
    
    context = {
        'company': company,
        'maps': maps,
        'maps_total': maps_total,
        'maps_processed': maps_processed,
        'maps_pending': maps_pending,
    }
    return render(request, 'core/upload_page.html', context)


@login_required
@company_access_required(require_admin=False)
@upload_rate_limit
def company_map_upload(request, company_slug):
    """Upload de mapa CTO via AJAX com verificação Flask"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método não permitido'}, status=405)
    
    company = get_object_or_404(Company, slug=company_slug)
    
    try:
        # Verificar se o usuário pode fazer upload (RM/Superuser/Company Admin sempre podem)
        if not (
            getattr(request.user, 'is_rm_admin', False)
            or getattr(request.user, 'is_superuser', False)
            or getattr(request.user, 'is_company_admin', False)
            or getattr(request.user, 'can_upload_maps', False)
        ):
            return JsonResponse({'success': False, 'message': 'Sem permissão para upload'}, status=403)
        
        # Verificar se o usuário pertence à empresa (liberar RM/Superuser)
        if not (getattr(request.user, 'is_rm_admin', False) or getattr(request.user, 'is_superuser', False)) and request.user.company != company:
            return JsonResponse({'success': False, 'message': 'Acesso negado à empresa'}, status=403)
        
        # Verificar se há arquivo no request
        if 'file' not in request.FILES:
            return JsonResponse({'success': False, 'message': 'Nenhum arquivo enviado'}, status=400)
        
        uploaded_file = request.FILES['file']

        from core.quotas import QuotaExceeded, enforce_quota

        try:
            enforce_quota(company, "maps", user=request.user)
        except QuotaExceeded as exc:
            return JsonResponse({'success': False, 'message': str(exc)}, status=403)
        
        # Processar arquivo usando o verificador Flask
        result = VerificadorIntegrationManager.processar_upload_arquivo(
            uploaded_file=uploaded_file,
            company=company,
            user=request.user
        )
        
        if result['success']:
            # Log do upload bem-sucedido
            try:
                from .audit_logger import log_map_upload
                map_file = CTOMapFile.objects.get(id=result['cto_file_id'])
                log_map_upload(request.user, map_file, company)
                
                # Invalidar cache de arquivos após upload - para TODOS os usuários da empresa
                # Buscar todos os usuários da empresa para invalidar seus caches
                from core.models import CustomUser
                company_users = CustomUser.objects.filter(company=company).values_list('id', flat=True)
                
                # Invalidar cache para todos os usuários da empresa
                cache_keys_to_delete = [f'rm_dashboard_stats_{request.user.id}']
                for user_id in company_users:
                    cache_keys_to_delete.extend([
                        f'api_arquivos_{user_id}_{company.slug}',
                        f'api_arquivos_{user_id}_none',
                    ])
                
                # Invalidar também para RM admins (que podem ver todas as empresas)
                if request.user.is_rm_admin or request.user.is_superuser:
                    cache_keys_to_delete.extend([
                        f'api_arquivos_{request.user.id}_{company.slug}',
                        f'api_arquivos_{request.user.id}_none',
                    ])
                
                # Invalidar cache de CTOs também
                cache_keys_to_delete.append(f'get_all_ctos_{company.id}')
                
                # Deletar todos os caches relacionados
                if cache_keys_to_delete:
                    cache.delete_many(cache_keys_to_delete)
            except Exception as log_error:
                logger.warning(f"Erro no log de upload: {str(log_error)}")
            
            # Preparar resposta com dados do Flask
            flask_result = result.get('flask_result', {})
            flask_data = flask_result.get('results', {})
            
            response_data = {
                'success': True,
                'message': 'Arquivo analisado com sucesso!',
                'file_id': result['cto_file_id'],
                'file_name': os.path.basename(uploaded_file.name),
                'analysis': {
                    'viability_score': flask_data.get('viability_score', 'N/A'),
                    'issues': flask_data.get('issues', []),
                    'recommendations': flask_data.get('recommendations', []),
                    'processing_time': flask_data.get('processing_time', 0),
                    'coordinates_count': flask_data.get('coordinates_count', 0)
                },
                'flask_status': result.get('flask_status', {})
            }
            
            return JsonResponse(response_data)
        else:
            # Upload falhou
            error_message = result.get('error', 'Erro desconhecido na análise')
            
            # Se o Flask estiver offline, ainda salvar o arquivo
            if result.get('flask_status', {}).get('status') != 'online':
                # Criar arquivo sem análise
                map_file = CTOMapFile(
                    file=uploaded_file,
                    description=request.POST.get('description', f'Arquivo enviado - Análise pendente'),
                    company=company,
                    uploaded_by=request.user,
                    processing_status='pending'
                )
                map_file.save()
                
                return JsonResponse({
                    'success': True,
                    'message': 'Arquivo salvo. Análise será realizada quando o serviço estiver disponível.',
                    'file_id': map_file.id,
                    'file_name': os.path.basename(uploaded_file.name),
                    'analysis_pending': True,
                    'flask_status': result.get('flask_status', {})
                })
            else:
                return JsonResponse({
                    'success': False, 
                    'message': error_message,
                    'flask_status': result.get('flask_status', {})
                }, status=400)
        
    except ValidationError as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)
    except Exception as e:
        logger.error(f"Erro no upload: {str(e)}")
        return JsonResponse({'success': False, 'message': 'Erro interno do servidor'}, status=500)


@login_required
@company_access_required(require_admin=False)
def company_verificar_coordenadas(request, company_slug):
    """Verifica viabilidade de coordenadas específicas"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método não permitido'}, status=405)
    
    company = get_object_or_404(Company, slug=company_slug)
    
    try:
        # Verificar se o usuário pode fazer verificações
        if not request.user.can_upload_maps:
            return JsonResponse({'success': False, 'message': 'Sem permissão para verificação'}, status=403)
        
        # Obter coordenadas do request
        lat = request.POST.get('lat')
        lon = request.POST.get('lon')
        
        if not lat or not lon:
            return JsonResponse({'success': False, 'message': 'Coordenadas não fornecidas'}, status=400)
        
        try:
            lat = float(lat)
            lon = float(lon)
        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'message': 'Coordenadas inválidas'}, status=400)
        
        # Verificar viabilidade usando Verificador Django
        result = VerificadorService.verificar_coordenadas(
            lat=lat,
            lon=lon,
            company=company,
            user=request.user
        )
        
        if result.get('success'):
            return JsonResponse({
                'success': True,
                'message': 'Verificação concluída',
                'analysis': result
            })
        else:
            return JsonResponse({
                'success': False,
                'message': result.get('error', 'Erro na verificação'),
                'analysis': result
            }, status=400)
        
    except Exception as e:
        logger.error(f"Erro na verificação de coordenadas: {str(e)}")
        return JsonResponse({'success': False, 'message': 'Erro interno do servidor'}, status=500)


@login_required
@company_access_required(require_admin=False)
def company_user_list(request, company_slug):
    from django.core.paginator import Paginator
    
    company = get_object_or_404(Company, slug=company_slug)
    users_qs = CustomUser.objects.filter(company=company).select_related('company').order_by('username')
    
    # Paginação
    paginator = Paginator(users_qs, 25)  # 25 usuários por página
    page_number = request.GET.get('page')
    users = paginator.get_page(page_number)
    
    return render(request, 'company/users/list.html', {'users': users, 'company': company})


@login_required
@company_access_required(require_admin=True)
def company_map_list(request, company_slug):
    """Lista de mapas da empresa (painel admin)"""
    from django.core.paginator import Paginator
    
    if not (request.user.is_company_admin or request.user.is_rm_admin or request.user.is_superuser):
        return HttpResponseForbidden()
    company = get_object_or_404(Company, slug=company_slug)
    if not (request.user.is_rm_admin or request.user.is_superuser) and request.user.company != company:
        return HttpResponseForbidden()

    # Otimizar query com select_related
    maps_qs = CTOMapFile.objects.filter(company=company).select_related(
        'company', 'uploaded_by'
    ).order_by('-uploaded_at')
    
    # Paginação
    paginator = Paginator(maps_qs, 20)  # 20 mapas por página
    page_number = request.GET.get('page')
    maps = paginator.get_page(page_number)
    
    return render(request, 'company/maps/list.html', {'maps': maps, 'company': company})






@login_required
@company_access_required(require_admin=False)
def company_map_download(request, company_slug, pk):
    """Download de mapa da empresa"""
    company = get_object_or_404(Company, slug=company_slug)
    
    # Verificar permissões
    if not request.user.is_rm_admin and not request.user.is_superuser:
        if not request.user.company or request.user.company != company:
            return HttpResponseForbidden("Acesso negado")

    map_file = get_object_or_404(CTOMapFile, pk=pk, company=company)

    # Verificar se o arquivo existe fisicamente
    if not map_file.file:
        messages.error(request, f'O arquivo "{map_file.file_name}" não foi encontrado no servidor.')
        return redirect('company:map_list', company_slug=company_slug)
    
    # Verificar se tem atributo path
    if not hasattr(map_file.file, 'path'):
        messages.error(request, f'O arquivo "{map_file.file_name}" não pode ser acessado.')
        return redirect('company:map_list', company_slug=company_slug)
    
    file_path = map_file.file.path
    
    # Verificar se o arquivo existe fisicamente
    if not os.path.exists(file_path):
        messages.error(
            request,
            f'O arquivo "{map_file.file_name}" não foi encontrado no servidor. '
            f'Envie o mapa novamente pela interface web.',
        )
        return redirect('company:map_list', company_slug=company_slug)
    
    # Tentar fazer o download
    try:
        # Determinar content-type baseado na extensão
        file_ext = os.path.splitext(map_file.file_name)[1].lower()
        content_types = {
            '.kml': 'application/vnd.google-earth.kml+xml',
            '.kmz': 'application/vnd.google-earth.kmz',
            '.csv': 'text/csv',
            '.xls': 'application/vnd.ms-excel',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        }
        content_type = content_types.get(file_ext, 'application/octet-stream')
        
        # Ler e servir o arquivo
        with open(file_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type=content_type)
            # Usar nome seguro para o arquivo
            safe_filename = map_file.file_name.encode('utf-8', 'replace').decode('utf-8')
            response['Content-Disposition'] = f'attachment; filename="{safe_filename}"'
            response['Content-Length'] = os.path.getsize(file_path)
            return response
    except IOError as e:
        logger.error(f"Erro ao ler arquivo {file_path}: {str(e)}")
        messages.error(request, f'Erro ao ler o arquivo "{map_file.file_name}". Tente novamente.')
        return redirect('company:map_list', company_slug=company_slug)
    except Exception as e:
        logger.error(f"Erro inesperado ao fazer download do arquivo {pk}: {str(e)}")
        messages.error(request, f'Erro ao fazer download do arquivo. Tente novamente.')
        return redirect('company:map_list', company_slug=company_slug)


@login_required
@company_access_required(require_admin=True)
@require_http_methods(["POST"])
def company_map_delete(request, company_slug, pk):
    """Deletar mapa da empresa"""
    if not (request.user.is_company_admin or request.user.is_rm_admin or request.user.is_superuser):
        messages.error(request, 'Sem permissão para excluir arquivos')
        return redirect('company:upload', company_slug=company_slug)

    company = get_object_or_404(Company, slug=company_slug)
    map_file = get_object_or_404(CTOMapFile, pk=pk, company=company)
    
    try:
        # Remover arquivo físico se existir
        if map_file.file and os.path.exists(map_file.file.path):
            os.remove(map_file.file.path)
        
        # Deletar registro do banco
        map_file.delete()
        
        messages.success(request, 'Arquivo excluído com sucesso!')
        
    except Exception as e:
        logger.error(f"Erro ao excluir arquivo {pk}: {str(e)}")
        messages.error(request, 'Erro ao excluir arquivo. Tente novamente.')
    
    return redirect('company:upload', company_slug=company_slug)


@login_required
@company_access_required(require_admin=False, allow_user_role=False)
def company_map_history(request, company_slug):
    company = get_object_or_404(Company, slug=company_slug)
    maps = CTOMapFile.objects.filter(company=company).order_by('-uploaded_at')
    return render(request, 'company/maps/history.html', {'maps': maps, 'company': company})


@login_required
@rm_admin_required
def rm_user_quick_search(request):
    q = request.GET.get('q', '').strip()
    if not q:
        messages.warning(request, 'Digite e-mail, nome ou usuário para buscar.')
        return redirect('rm:user_list')
    # Preferir correspondências exatas de e-mail ou username
    exact_qs = CustomUser.objects.filter(Q(email__iexact=q) | Q(username__iexact=q))
    if exact_qs.count() == 1:
        return redirect('rm:user_edit', user_id=exact_qs.first().pk)
    # Fallback para busca parcial em nome, username ou e-mail
    qs = CustomUser.objects.filter(
        Q(email__icontains=q) |
        Q(username__icontains=q) |
        Q(first_name__icontains=q) |
        Q(last_name__icontains=q)
    ).order_by('username')
    if qs.count() == 1:
        return redirect('rm:user_edit', user_id=qs.first().pk)
    if qs.exists():
        messages.info(request, f'{qs.count()} usuários encontrados para "{q}". Refine a busca.')
        return redirect(f"{reverse('rm:user_list')}?q={q}")
    messages.warning(request, f'Nenhum usuário encontrado para "{q}".')
    return redirect(f"{reverse('rm:user_list')}?q={q}")


@login_required
@rm_admin_required
def rm_maps_by_company(request):
    """Visão RM: Mapas agrupados por empresa, com ações e gráficos"""
    companies = Company.objects.all().order_by('name')
    company_stats = []
    for c in companies:
        maps_qs = CTOMapFile.objects.filter(company=c)
        stats = {
            'company': c,
            'maps': maps_qs.select_related('company', 'uploaded_by'),
            'total_maps': maps_qs.count(),
            'processed_maps': maps_qs.filter(is_processed=True).count(),
            'pending_maps': maps_qs.filter(is_processed=False).count(),
        }
        company_stats.append(stats)

    # Dados agregados para gráficos gerais (total de mapas por empresa)
    labels = [s['company'].name for s in company_stats]
    totals = [s['total_maps'] for s in company_stats]
    processed = [s['processed_maps'] for s in company_stats]
    pending = [s['pending_maps'] for s in company_stats]

    context = {
        'companies': companies,
        'company_stats': company_stats,
        'chart_labels': labels,
        'chart_totals': totals,
        'chart_processed': processed,
        'chart_pending': pending,
    }
    return render(request, 'rm/maps/by_company.html', context)


@login_required
@company_access_required(require_admin=True)
def company_map_admin(request, company_slug):
    """Tela de administração avançada de mapas para empresa"""
    if not (request.user.is_company_admin or request.user.is_rm_admin or request.user.is_superuser):
        return HttpResponseForbidden()

    company = get_object_or_404(Company, slug=company_slug)
    if not (request.user.is_rm_admin or request.user.is_superuser) and request.user.company != company:
        return HttpResponseForbidden()

    # Buscar todos os mapas da empresa
    maps = CTOMapFile.objects.filter(company=company).select_related('uploaded_by').order_by('-uploaded_at')

    # Calcular estatísticas
    total_maps = maps.count()
    processed_maps = maps.filter(is_processed=True).count()
    pending_maps = maps.filter(is_processed=False).count()

    # Calcular tamanho total dos arquivos
    total_size = sum(map_file.file.size for map_file in maps if map_file.file)
    total_size_mb = round(total_size / (1024 * 1024), 2)

    context = {
        'company': company,
        'maps': maps,
        'total_maps': total_maps,
        'processed_maps': processed_maps,
        'pending_maps': pending_maps,
        'total_size_mb': total_size_mb,
    }

    return render(request, 'company/maps/admin.html', context)


@login_required
@company_access_required(require_admin=True, allow_user_role=False)
def company_reports(request, company_slug):
    """Relatórios completos para administradores da empresa"""
    company = get_object_or_404(Company, slug=company_slug)

    maps_qs = CTOMapFile.objects.filter(company=company)

    total_maps = maps_qs.count()
    processed_maps = maps_qs.filter(is_processed=True).count()
    pending_maps = total_maps - processed_maps
    maps_last_30_days = maps_qs.filter(uploaded_at__gte=timezone.now() - timedelta(days=30)).count()

    viability_agg = maps_qs.aggregate(
        viavel=Count('id', filter=Q(viability_score__gte=80)),
        limitada=Count('id', filter=Q(viability_score__gte=60, viability_score__lt=80)),
        inviavel=Count('id', filter=Q(viability_score__lt=60, viability_score__isnull=False)),
        nao_analisado=Count('id', filter=Q(viability_score__isnull=True))
    )

    viability_counts = {
        'viavel': viability_agg.get('viavel', 0) or 0,
        'limitada': viability_agg.get('limitada', 0) or 0,
        'inviavel': viability_agg.get('inviavel', 0) or 0,
        'nao_analisado': viability_agg.get('nao_analisado', 0) or 0,
    }

    verifications_qs = ViabilidadeCache.objects.filter(company=company)
    total_verifications = verifications_qs.count()
    verifications_viavel = verifications_qs.filter(resultado__viabilidade__status__iexact='Viável').count()
    verifications_limitada = verifications_qs.filter(resultado__viabilidade__status__iexact='Viabilidade Limitada').count()
    verifications_inviavel = verifications_qs.filter(resultado__viabilidade__status__iexact='Sem viabilidade').count()
    verifications_outros = max(total_verifications - (verifications_viavel + verifications_limitada + verifications_inviavel), 0)

    monthly_uploads = maps_qs.filter(uploaded_at__isnull=False).annotate(
        month=TruncMonth('uploaded_at')
    ).values('month').order_by('month').annotate(total=Count('id'))

    def format_month(value):
        if not value:
            return 'N/A'
        if timezone.is_naive(value):
            return value.strftime('%b/%Y')
        return timezone.localtime(value).strftime('%b/%Y')

    monthly_upload_labels = [format_month(entry['month']) for entry in monthly_uploads]
    monthly_upload_values = [entry['total'] for entry in monthly_uploads]

    monthly_verifications = verifications_qs.annotate(
        month=TruncMonth('created_at')
    ).values('month').order_by('month').annotate(total=Count('id')) if hasattr(ViabilidadeCache, 'created_at') else []

    monthly_verification_labels = [format_month(entry['month']) for entry in monthly_verifications]
    monthly_verification_values = [entry['total'] for entry in monthly_verifications]

    top_uploaders_qs = maps_qs.values(
        'uploaded_by__first_name',
        'uploaded_by__last_name',
        'uploaded_by__username'
    ).annotate(total=Count('id')).order_by('-total')[:5]

    top_uploaders = []
    for item in top_uploaders_qs:
        first = item.get('uploaded_by__first_name') or ''
        last = item.get('uploaded_by__last_name') or ''
        username = item.get('uploaded_by__username') or ''
        full_name = f"{first} {last}".strip()
        display_name = full_name if full_name else username
        top_uploaders.append({
            'name': display_name,
            'username': username,
            'total': item['total']
        })

    recent_maps = maps_qs.select_related('uploaded_by').order_by('-uploaded_at')[:5]

    context = {
        'company': company,
        'map_stats': {
            'total': total_maps,
            'processed': processed_maps,
            'pending': pending_maps,
            'last_30_days': maps_last_30_days,
        },
        'viability_counts': viability_counts,
        'viability_labels': ['Viável', 'Viabilidade Limitada', 'Sem Viabilidade', 'Não analisado'],
        'viability_values': [
            viability_counts['viavel'],
            viability_counts['limitada'],
            viability_counts['inviavel'],
            viability_counts['nao_analisado'],
        ],
        'verification_stats': {
            'total': total_verifications,
            'viavel': verifications_viavel,
            'limitada': verifications_limitada,
            'inviavel': verifications_inviavel,
            'outros': verifications_outros,
        },
        'verification_labels': ['Viável', 'Viabilidade Limitada', 'Sem Viabilidade', 'Outros'],
        'verification_values': [
            verifications_viavel,
            verifications_limitada,
            verifications_inviavel,
            verifications_outros,
        ],
        'monthly_upload_labels': monthly_upload_labels,
        'monthly_upload_values': monthly_upload_values,
        'monthly_verification_labels': monthly_verification_labels,
        'monthly_verification_values': monthly_verification_values,
        'top_uploaders': top_uploaders,
        'recent_maps': recent_maps,
    }

    return render(request, 'company/reports.html', context)


# --- Novas views RM para relatórios e lista/ações de mapas ---
@login_required
@rm_admin_required
def rm_map_list(request):
    """Lista de todos os mapas (visão RM), agrupados por empresa"""
    from django.db.models import Count, Prefetch
    from django.core.paginator import Paginator
    
    # Buscar todas as empresas com seus mapas, ordenadas por nome
    # Otimizar com select_related e prefetch_related
    companies_qs = Company.objects.annotate(
        map_count=Count('cto_maps')
    ).filter(map_count__gt=0).select_related().order_by('name')
    
    # Paginação de empresas
    paginator = Paginator(companies_qs, 15)  # 15 empresas por página
    page_number = request.GET.get('page')
    companies_page = paginator.get_page(page_number)
    
    # Agrupar mapas por empresa (apenas para empresas da página atual)
    companies_with_maps = []
    for company in companies_page:
        # Limitar a 10 mapas mais recentes por empresa para performance
        maps = CTOMapFile.objects.filter(company=company).select_related(
            'uploaded_by', 'company'
        ).order_by('-uploaded_at')[:10]
        companies_with_maps.append({
            'company': company,
            'maps': maps,
            'count': company.map_count  # Usar o count do annotation
        })
    
    # Empresas sem mapas (opcional, pode ser removido se não for usado)
    companies_without_maps = Company.objects.annotate(
        map_count=Count('cto_maps')
    ).filter(map_count=0).order_by('name')[:10]  # Limitar a 10
    
    context = {
        'companies_with_maps': companies_with_maps,
        'companies_without_maps': companies_without_maps,
        'total_companies': paginator.count,
        'companies_page': companies_page,  # Para paginação no template
    }
    
    return render(request, 'rm/maps/list.html', context)


@login_required
@rm_admin_required
def rm_map_download(request, pk):
    map_file = get_object_or_404(CTOMapFile, pk=pk)
    if os.path.exists(map_file.file.path):
        with open(map_file.file.path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/octet-stream')
            response['Content-Disposition'] = f'attachment; filename="{map_file.file_name}"'
            return response
    raise Http404('Arquivo não encontrado')


@login_required
@rm_admin_required
@require_http_methods(["POST"])
def rm_map_delete(request, pk):
    map_file = get_object_or_404(CTOMapFile, pk=pk)
    company_slug = map_file.company.slug if map_file.company else None
    try:
        if map_file.file and os.path.exists(map_file.file.path):
            os.remove(map_file.file.path)
        map_file.delete()
        
        # Invalidar cache de arquivos - para TODOS os usuários da empresa
        if map_file.company:
            from core.models import CustomUser
            company_users = CustomUser.objects.filter(company=map_file.company).values_list('id', flat=True)
            
            cache_keys_to_delete = []
            for user_id in company_users:
                cache_keys_to_delete.extend([
                    f'api_arquivos_{user_id}_{company_slug}',
                    f'api_arquivos_{user_id}_none',
                    f'api_coordenadas_{map_file.id}_{company_slug}',
                    f'api_coordenadas_{map_file.file_name}_{company_slug}',
                ])
            
            # Invalidar também para RM admins
            if request.user.is_rm_admin or request.user.is_superuser:
                cache_keys_to_delete.extend([
                    f'api_arquivos_{request.user.id}_{company_slug}',
                    f'api_arquivos_{request.user.id}_none',
                    f'api_coordenadas_{map_file.id}_{company_slug}',
                    f'api_coordenadas_{map_file.file_name}_{company_slug}',
                ])
            
            if cache_keys_to_delete:
                cache.delete_many(cache_keys_to_delete)
        return JsonResponse({'success': True})
    except Exception:
        return JsonResponse({'success': False, 'message': 'Falha ao excluir'}, status=500)


@login_required
@rm_admin_required
def rm_reports(request):
    companies = Company.objects.all().order_by('name')
    users = CustomUser.objects.all()

    # Estatísticas por empresa para gráficos
    company_stats = []
    for c in companies:
        maps_qs = CTOMapFile.objects.filter(company=c)
        company_stats.append({
            'company': c,
            'total_maps': maps_qs.count(),
            'processed_maps': maps_qs.filter(is_processed=True).count(),
            'pending_maps': maps_qs.filter(is_processed=False).count(),
        })

    labels = [s['company'].name for s in company_stats]
    totals = [s['total_maps'] for s in company_stats]
    processed = [s['processed_maps'] for s in company_stats]
    pending = [s['pending_maps'] for s in company_stats]

    # Totais gerais para o gráfico de status e cards
    overall_processed = CTOMapFile.objects.filter(is_processed=True).count()
    overall_pending = CTOMapFile.objects.filter(is_processed=False).count()
    companies_with_maps = sum(1 for stat in company_stats if stat['total_maps'] > 0)

    context = {
        'total_companies': companies.count(),
        'active_companies': companies.filter(is_active=True).count(),
        'total_users': users.count(),
        'active_users': users.filter(is_active=True).count(),
        'total_maps': CTOMapFile.objects.count(),
        'companies_with_maps': companies_with_maps,
        'overall_processed': overall_processed,
        'overall_pending': overall_pending,
        'chart_labels': labels,
        'chart_totals': totals,
        'chart_processed': processed,
        'chart_pending': pending,
    }
    return render(request, 'rm/reports.html', context)


@login_required
@rm_admin_required
def rm_reports_export_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="relatorios_rm.csv"'
    writer = csv.writer(response)
    writer.writerow(['Métrica', 'Valor'])
    writer.writerow(['Empresas (ativas)', Company.objects.filter(is_active=True).count()])
    writer.writerow(['Empresas (total)', Company.objects.count()])
    writer.writerow(['Usuários (ativos)', CustomUser.objects.filter(is_active=True).count()])
    writer.writerow(['Usuários (total)', CustomUser.objects.count()])
    writer.writerow(['Mapas CTO (total)', CTOMapFile.objects.count()])
    return response


# Redireciona para o dashboard correto conforme o papel do usuário

@login_required
def change_password_required(request):
    """
    View para mudança obrigatória de senha no primeiro acesso
    """
    user = request.user
    
    # Verificar se usuário realmente precisa mudar a senha
    if not hasattr(user, 'must_change_password') or not user.must_change_password:
        # Não precisa mudar senha, redirecionar para dashboard
        return redirect('dashboard')
    
    if request.method == 'POST':
        new_password = request.POST.get('new_password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()
        
        if not new_password or not confirm_password:
            messages.error(request, 'Preencha a nova senha e a confirmação.')
            return render(request, 'core/change_password_required.html')
        
        # Verificar se as novas senhas coincidem
        if new_password != confirm_password:
            messages.error(request, 'As senhas não coincidem.')
            return render(request, 'core/change_password_required.html')
        
        # Verificar se a nova senha é diferente da atual
        if user.check_password(new_password):
            messages.error(request, 'A nova senha deve ser diferente da senha provisória.')
            return render(request, 'core/change_password_required.html')
        
        # Validar tamanho mínimo (8 caracteres)
        if len(new_password) < 8:
            messages.error(request, 'A senha deve ter no mínimo 8 caracteres.')
            return render(request, 'core/change_password_required.html')
        
        # Atualizar senha
        user.set_password(new_password)
        user.must_change_password = False
        user.save()
        
        # Atualizar sessão para não precisar logar novamente
        from django.contrib.auth import update_session_auth_hash
        update_session_auth_hash(request, user)
        
        messages.success(request, 'Senha alterada com sucesso!')
        logger.info(f"Usuário {user.username} alterou senha obrigatória com sucesso")
        
        from core.modules import post_login_redirect_url
        return redirect(post_login_redirect_url(user))
    
    return render(request, 'core/change_password_required.html')


def dashboard_redirect(request):
    if not request.user.is_authenticated:
        return redirect('rm:login')

    user = request.user
    
    # Verificar se usuário precisa mudar senha
    if hasattr(user, 'must_change_password') and user.must_change_password:
        return redirect('change_password_required')
    
    if user.is_rm_admin or user.is_superuser:
        return redirect('rm:admin_dashboard')

    if user.company:
        from core.modules import post_login_redirect_url
        return redirect(post_login_redirect_url(user))

    # Fallback: se não houver empresa associada, enviar para RM dashboard
    return redirect('rm:admin_dashboard')


@login_required
@rm_admin_required
def rm_company_create(request):
    if request.method == 'POST':
        form = CompanyForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Empresa criada com sucesso!')
            return redirect('rm:company_list')
    else:
        form = CompanyForm()
    return render(request, 'rm/companies/form.html', {'form': form, 'company': None})


@login_required
@rm_admin_required
def rm_company_edit(request, company_id):
    company = get_object_or_404(Company, id=company_id)
    if request.method == 'POST':
        form = CompanyForm(request.POST, instance=company)
        if form.is_valid():
            form.save()
            messages.success(request, 'Empresa atualizada com sucesso!')
            return redirect('rm:company_list')
    else:
        form = CompanyForm(instance=company)
    return render(request, 'rm/companies/form.html', {
        'form': form,
        'company': company,
    })


@login_required
@company_access_required(require_admin=True)
def company_user_create(request, company_slug):
    """Cria um novo usuário no painel da empresa"""
    logger.debug(f"company_user_create: method={request.method}, company_slug={company_slug}, user={request.user.username}")
    
    company = get_object_or_404(Company, slug=company_slug)
    
    # Verificar se o usuário tem permissão para criar usuários nesta empresa
    if not request.user.is_company_admin:
        messages.error(request, 'Você não tem permissão para criar usuários.')
        return redirect('company:user_list', company_slug=company_slug)
    
    if request.method == 'POST':
        logger.debug(f"company_user_create POST: dados recebidos - {request.POST.dict()}")
        form = CustomUserForm(request.POST, current_user=request.user)
        
        logger.debug(f"company_user_create: formulário criado, is_valid={form.is_valid()}")
        if not form.is_valid():
            logger.warning(f"Formulário inválido:")
            logger.warning(f"  Erros de campos: {form.errors.as_json()}")
            if form.non_field_errors():
                logger.warning(f"  Erros gerais: {list(form.non_field_errors())}")
        
        if form.is_valid():
            from core.quotas import QuotaExceeded, enforce_quota

            try:
                enforce_quota(company, "users", user=request.user)
                with transaction.atomic():
                    logger.debug(f"Salvando usuário...")
                    user = form.save(commit=False)
                    # Forçar empresa para garantir que o usuário seja da empresa correta
                    user.company = company
                    # Papel padrão para criação pela empresa (se não definido)
                    if not getattr(user, 'role', None) or user.role == 'RM':
                        user.role = 'COMPANY_USER'
                    
                    # Validar que não está tentando criar RM
                    if user.role == 'RM':
                        messages.error(request, 'Não é possível criar usuário RM pela empresa.')
                        form.add_error('role', 'Não é possível criar usuário RM pela empresa.')
                    else:
                        # Salvar o usuário
                        user.save()
                        
                        if getattr(form, '_send_welcome_email', False):
                            temp_password = getattr(form, '_generated_password', None)
                            email_sent = send_user_credentials_email(
                                user, plain_password=temp_password, request=request
                            )
                            if email_sent:
                                messages.success(
                                    request,
                                    f'Usuário {user.username} criado. Enviamos um e-mail de boas-vindas '
                                    f'com a senha temporária para {user.email}. No primeiro acesso será '
                                    f'necessário definir uma nova senha.',
                                )
                            else:
                                messages.warning(
                                    request,
                                    f'Usuário {user.username} criado, mas o e-mail de boas-vindas não foi enviado. '
                                    f'Informe a senha temporária manualmente ou redefina a senha.',
                                )
                        else:
                            messages.success(request, f'Usuário {user.username} criado com sucesso!')
                        
                        logger.info(f"Usuário criado com sucesso: {user.username} (role: {user.role}, company: {user.company.name if user.company else 'N/A'})")
                        return redirect('company:user_list', company_slug=company_slug)
            except ValidationError as e:
                # Erros de validação são tratados no formulário
                logger.warning(f"Erro de validação ao criar usuário: {str(e)}")
                logger.warning(f"Erros no formulário após ValidationError: {dict(form.errors)}")
                if isinstance(e, QuotaExceeded):
                    messages.error(request, str(e))
                pass  # Continuar para exibir o formulário com erros
            except Exception as e:
                logger.error(f"Erro ao criar usuário: {str(e)}", exc_info=True)
                import traceback
                logger.error(f"Traceback completo: {traceback.format_exc()}")
                messages.error(request, f'Erro ao criar usuário: {str(e)}')
        
        # Logar erros do formulário se houver
        if not form.is_valid() or form.errors:
            logger.warning(f"Formulário tem erros:")
            for field, errors in form.errors.items():
                logger.warning(f"  Campo '{field}': {list(errors)}")
            if form.non_field_errors():
                logger.warning(f"  Erros gerais: {list(form.non_field_errors())}")
    else:
        form = CustomUserForm(current_user=request.user)
    
    # Adicionar title para o template
    context = {
        'form': form,
        'company': company,
        'title': 'Criar Usuário'
    }
    return render(request, 'company/users/form.html', context)


@login_required
@company_access_required(require_admin=True)
def company_user_edit(request, company_slug, user_id):
    company = get_object_or_404(Company, slug=company_slug)
    user_obj = get_object_or_404(CustomUser, id=user_id, company=company)
    
    if request.method == 'POST':
        form = CustomUserChangeForm(request.POST, instance=user_obj, current_user=request.user)
        if form.is_valid():
            with transaction.atomic():
                user = form.save(commit=False)
                user.company = company  # força permanência na empresa
                if user.role == 'RM':
                    messages.error(request, 'Não é possível definir papel RM para usuário da empresa.')
                else:
                    user.save()
                    messages.success(request, 'Usuário atualizado com sucesso!')
                    return redirect('company:user_list', company_slug=company_slug)
    else:
        form = CustomUserChangeForm(instance=user_obj, current_user=request.user)
    
    context = {
        'form': form,
        'company': company,
        'user_obj': user_obj,
        'title': 'Editar Usuário'
    }
    return render(request, 'company/users/form.html', context)


@login_required
@company_access_required(require_admin=True)
@require_http_methods(["POST"])
def company_user_delete(request, company_slug, user_id):
    """Deleta um usuário da empresa"""
    company = get_object_or_404(Company, slug=company_slug)
    
    try:
        user_obj = get_object_or_404(CustomUser, id=user_id, company=company)
        
        # Não permitir deletar superusuários ou RM admins
        if user_obj.is_superuser or user_obj.is_rm_admin:
            messages.error(request, 'Não é possível deletar este tipo de usuário.')
            return redirect('company:user_list', company_slug=company_slug)
        
        # Não permitir deletar o próprio usuário
        if user_obj.id == request.user.id:
            messages.error(request, 'Não é possível deletar seu próprio usuário.')
            return redirect('company:user_list', company_slug=company_slug)
        
        # Verificar se o usuário pertence à empresa
        if user_obj.company != company:
            messages.error(request, 'Usuário não pertence a esta empresa.')
            return redirect('company:user_list', company_slug=company_slug)
        
        username = user_obj.get_full_name() or user_obj.username
        user_obj.delete()
        
        messages.success(request, f'Usuário "{username}" removido com sucesso!')
        return redirect('company:user_list', company_slug=company_slug)
        
    except CustomUser.DoesNotExist:
        messages.error(request, 'Usuário não encontrado.')
        return redirect('company:user_list', company_slug=company_slug)
    except Exception as e:
        logger.error(f"Erro ao deletar usuário: {str(e)}", exc_info=True)
        messages.error(request, f'Erro ao remover usuário: {str(e)}')
        return redirect('company:user_list', company_slug=company_slug)


@login_required
@company_access_required_json(require_admin=True)
@require_http_methods(["POST"])
def company_user_toggle(request, company_slug, user_id):
    try:
        target = get_object_or_404(CustomUser, id=user_id)
        # Bloquear operações perigosas
        if getattr(target, 'is_superuser', False) or getattr(target, 'is_rm_admin', False):
            return JsonResponse({'success': False, 'message': 'Operação não permitida para este usuário.'}, status=403)
        # Verificar pertencimento à mesma empresa
        if not target.company or target.company.slug != company_slug:
            return JsonResponse({'success': False, 'message': 'Usuário não pertence a esta empresa.'}, status=403)
        # Evitar auto-desativação
        if target.id == request.user.id:
            return JsonResponse({'success': False, 'message': 'Você não pode alterar seu próprio status.'}, status=400)
        target.is_active = not target.is_active
        target.save(update_fields=['is_active'])
        return JsonResponse({'success': True, 'active': target.is_active})
    except Exception as e:
        return JsonResponse({'success': False, 'message': 'Falha ao alterar status.'}, status=500)


@login_required
@rm_admin_required
@require_http_methods(["POST"])
def rm_company_delete(request, company_id):
    """
    Exclui uma empresa com validações de segurança e dependências
    
    Validações:
    - Verifica se empresa existe
    - Conta dependências (usuários, mapas)
    - Requer confirmação explícita
    - Faz backup/log da ação
    - Remove em transação para garantir integridade
    """
    company = get_object_or_404(Company, id=company_id)
    
    # Verificar confirmação
    confirmed = request.POST.get('confirmed', 'false').lower() == 'true'
    if not confirmed:
        # Retornar informações sobre dependências para confirmação
        user_count = company.users.count()
        map_count = company.cto_maps.count()
        
        return JsonResponse({
            'success': False,
            'requires_confirmation': True,
            'message': 'Confirmação necessária para excluir empresa',
            'dependencies': {
                'users': user_count,
                'maps': map_count,
                'company_name': company.name
            },
            'warning': f'A exclusão desta empresa também excluirá {user_count} usuário(s) e {map_count} mapa(s) associado(s).'
        }, status=400)
    
    # Validar dependências
    user_count = company.users.count()
    map_count = company.cto_maps.count()
    
    # Log da tentativa de exclusão
    logger.warning(
        f"Tentativa de exclusão de empresa: {company.name} (ID: {company.id})",
        extra={
            'user_id': request.user.id,
            'company_id': company.id,
            'company_name': company.name,
            'user_count': user_count,
            'map_count': map_count,
            'timestamp': timezone.now().isoformat()
        }
    )
    
    # Executar exclusão em transação
    try:
        with transaction.atomic():
            # Coletar informações antes da exclusão para log
            from .log_sanitizer import mask_cnpj, mask_email
            company_info = {
                'name': company.name,
                'cnpj': mask_cnpj(company.cnpj),
                'email': mask_email(company.email),
                'slug': company.slug,
                'user_count': user_count,
                'map_count': map_count
            }
            
            # Remover arquivos físicos dos mapas antes de excluir
            for map_file in company.cto_maps.all():
                try:
                    if map_file.file and os.path.exists(map_file.file.path):
                        os.remove(map_file.file.path)
                        logger.debug(f"Arquivo de mapa removido: {map_file.file.path}")
                except Exception as file_error:
                    logger.warning(f"Erro ao remover arquivo de mapa {map_file.id}: {file_error}")
            
            # Excluir empresa (cascata excluirá usuários e mapas do banco)
            company.delete()
            
            # Log da exclusão bem-sucedida
            logger.info(
                f"Empresa excluída com sucesso: {company_info['name']}",
                extra={
                    'user_id': request.user.id,
                    'deleted_company': company_info,
                    'timestamp': timezone.now().isoformat()
                }
            )
            
            # Registrar no audit log
            try:
                from .audit_logger import log_user_action
                log_user_action(
                    user=request.user,
                    action='company_deleted',
                    details={
                        'company_name': company_info['name'],
                        'company_cnpj': company_info['cnpj'],
                        'users_deleted': user_count,
                        'maps_deleted': map_count
                    }
                )
            except Exception as audit_error:
                logger.warning(f"Erro ao registrar no audit log: {audit_error}")
            
            return JsonResponse({
                'success': True,
                'message': f'Empresa "{company_info["name"]}" excluída com sucesso',
                'deleted': {
                    'company': company_info['name'],
                    'users': user_count,
                    'maps': map_count
                }
            })
            
    except Exception as e:
        logger.error(
            f"Erro ao excluir empresa {company.id}: {str(e)}",
            extra={
                'user_id': request.user.id,
                'company_id': company.id,
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            },
            exc_info=True
        )
        
        from django.conf import settings as django_settings

        message = (
            f'Erro ao excluir empresa: {str(e)}'
            if django_settings.DEBUG
            else 'Erro ao excluir empresa. Tente novamente ou contate o suporte.'
        )
        return JsonResponse({'success': False, 'message': message}, status=500)


# === RELATÓRIOS E EXPORTAÇÃO ===

@login_required
@rm_admin_required
def rm_reports_dashboard(request):
    """Dashboard de relatórios para RM"""
    metrics = ReportGenerator.get_system_wide_metrics()
    
    context = {
        'metrics': metrics,
        'title': 'Relatórios do Sistema'
    }
    return render(request, 'rm/reports/dashboard.html', context)

@login_required
@company_access_required
def company_reports_dashboard(request, company_slug):
    """Dashboard de relatórios da empresa"""
    company = get_object_or_404(Company, slug=company_slug)
    metrics = ReportGenerator.get_company_metrics(company)
    
    context = {
        'company': company,
        'metrics': metrics,
        'title': 'Relatórios da Empresa'
    }
    return render(request, 'company/reports/dashboard.html', context)

@login_required
@rm_admin_required
def export_system_report(request, format='csv'):
    """Exportar relatório do sistema"""
    metrics = ReportGenerator.get_system_wide_metrics()
    
    # Preparar dados para exportação
    export_data = []
    
    # Dados de empresas
    for company_data in metrics['company_rankings']:
        export_data.append({
            'Tipo': 'Empresa',
            'Nome': company_data.name,
            'Usuários': company_data.user_count,
            'Mapas': company_data.map_count,
            'Criada em': company_data.created_at
        })
    
    # Dados de uso
    for usage_data in metrics['usage_statistics']['maps_by_company']:
        export_data.append({
            'Tipo': 'Uso de Mapas',
            'Empresa': usage_data.name,
            'Total de Mapas': usage_data.map_count,
            'Data': timezone.now().strftime('%Y-%m-%d')
        })
    
    filename = f'relatorio_sistema_{timezone.now().strftime("%Y%m%d")}.{format}'
    
    if format == 'csv':
        return ExportManager.export_to_csv(export_data, filename)
    else:
        return ExportManager.export_to_json(export_data, filename)

@login_required
@company_access_required
def export_company_report(request, company_slug, format='csv'):
    """Exportar relatório da empresa"""
    company = get_object_or_404(Company, slug=company_slug)
    metrics = ReportGenerator.get_company_metrics(company)
    
    # Preparar dados para exportação
    export_data = []
    
    # Informações da empresa
    export_data.append({
        'Tipo': 'Informações da Empresa',
        'Nome': company.name,
        'Email': company.email,
        'Telefone': company.phone,
        'Total de Usuários': metrics['company_info']['total_users'],
        'Usuários Ativos': metrics['company_info']['active_users'],
        'Total de Mapas': metrics['map_statistics']['total_maps']
    })
    
    # Estatísticas de mapas
    for file_type in metrics['map_statistics']['by_file_type']:
        export_data.append({
            'Tipo': 'Estatísticas de Mapas',
            'Tipo de Arquivo': file_type['file_type'],
            'Quantidade': file_type['count'],
            'Empresa': company.name
        })
    
    filename = f'relatorio_{company.slug}_{timezone.now().strftime("%Y%m%d")}.{format}'
    
    if format == 'csv':
        return ExportManager.export_to_csv(export_data, filename)
    else:
        return ExportManager.export_to_json(export_data, filename)

@login_required
@company_access_required
def export_user_list(request, company_slug, format='csv'):
    """Exportar lista de usuários da empresa"""
    company = get_object_or_404(Company, slug=company_slug)
    users = CustomUser.objects.filter(company=company)
    
    export_data = []
    for user in users:
        export_data.append({
            'Username': user.username,
            'Email': user.email,
            'Nome Completo': f"{user.first_name} {user.last_name}".strip(),
            'Telefone': user.phone or '',
            'Role': user.get_role_display(),
            'Ativo': 'Sim' if user.is_active else 'Não',
            'Último Login': user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else 'Nunca',
            'Data de Criação': user.date_joined.strftime('%Y-%m-%d %H:%M')
        })
    
    filename = f'usuarios_{company.slug}_{timezone.now().strftime("%Y%m%d")}.{format}'
    
    if format == 'csv':
        return ExportManager.export_to_csv(export_data, filename)
    else:
        return ExportManager.export_to_json(export_data, filename)

@login_required
@company_access_required
def export_map_list(request, company_slug, format='csv'):
    """Exportar lista de mapas da empresa"""
    company = get_object_or_404(Company, slug=company_slug)
    maps = CTOMapFile.objects.filter(company=company)
    
    export_data = []
    for map_file in maps:
        export_data.append({
            'Nome do Arquivo': map_file.original_filename,
            'Tipo': map_file.file_type,
            'Tamanho (MB)': round(map_file.file_size / (1024 * 1024), 2) if map_file.file_size else 0,
            'Status': map_file.status,
            'Uploadado por': map_file.uploaded_by.get_full_name() if map_file.uploaded_by else 'Sistema',
            'Data de Upload': map_file.uploaded_at.strftime('%Y-%m-%d %H:%M')
        })
    
    filename = f'mapas_{company.slug}_{timezone.now().strftime("%Y%m%d")}.{format}'
    
    if format == 'csv':
        return ExportManager.export_to_csv(export_data, filename)
    else:
        return ExportManager.export_to_json(export_data, filename)
