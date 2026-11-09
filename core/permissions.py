from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseForbidden, JsonResponse
from functools import wraps
import logging

from rest_framework.permissions import BasePermission

logger = logging.getLogger(__name__)


def is_rm_admin(user):
    """Verifica se o usuário é administrador RM ou superusuário"""
    # Superusuários sempre têm acesso, mesmo sem autenticação explícita
    if hasattr(user, 'is_superuser') and user.is_superuser:
        return True
    return user.is_authenticated and getattr(user, 'is_rm_admin', False)


def is_company_admin(user):
    """Verifica se o usuário é administrador da empresa"""
    return user.is_authenticated and user.is_company_admin


def is_company_user(user):
    """Verifica se o usuário é usuário da empresa"""
    return user.is_authenticated and user.is_company_user


def can_manage_users(user):
    """Verifica se o usuário pode gerenciar outros usuários"""
    return user.is_authenticated and user.can_manage_users


def can_upload_maps(user):
    """Verifica se o usuário pode fazer upload de mapas"""
    return user.is_authenticated and user.can_upload_maps


def belongs_to_same_company(user, target_user):
    """Verifica se dois usuários pertencem à mesma empresa"""
    if user.is_rm_admin:
        return True  # RM admins podem acessar qualquer empresa

    if not user.company or not target_user.company:
        return False

    return user.company == target_user.company

# Função de teste com logs para debug
def _rm_admin_test(user):
    """Testa se o usuário é RM admin ou superuser, com logs para debug"""
    # Superusuários sempre têm acesso, mesmo sem autenticação explícita
    if hasattr(user, 'is_superuser') and user.is_superuser:
        logger.debug(f"rm_admin_required: Acesso permitido para superusuário {user.username}")
        return True
    
    if not user.is_authenticated:
        logger.warning(f"rm_admin_required: Usuário não autenticado")
        return False
    
    is_admin = is_rm_admin(user)
    if not is_admin:
        logger.warning(
            f"rm_admin_required: Acesso negado para {user.username} "
            f"(role: {getattr(user, 'role', 'N/A')}, "
            f"is_superuser: {user.is_superuser}, "
            f"is_rm_admin: {getattr(user, 'is_rm_admin', False)})"
        )
    else:
        logger.debug(
            f"rm_admin_required: Acesso permitido para {user.username} "
            f"(role: {getattr(user, 'role', 'N/A')}, is_superuser: {user.is_superuser})"
        )
    return is_admin

class IsRMAdmin(BasePermission):
    """DRF — apenas administradores RM ou superuser."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and is_rm_admin(user))


class IsCompanyAdmin(BasePermission):
    """DRF — admin da empresa ou RM."""

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return is_rm_admin(user) or is_company_admin(user)


# Decorators para views usando user_passes_test
rm_admin_required = user_passes_test(_rm_admin_test, login_url='/rm/login/')
company_admin_required = user_passes_test(
    lambda u: is_rm_admin(u) or is_company_admin(u) or u.is_superuser,
    login_url='/rm/login/'
)

user_management_required = user_passes_test(lambda u: can_manage_users(u) or u.is_superuser, login_url='/rm/login/')
# map_upload_required removido - funcionalidade de upload foi consolidada


def company_access_required(require_admin=False, allow_user_role=True):
    """
    Decorator que garante acesso multi-tenant por slug de empresa.
    - RM admins e superusers sempre têm acesso.
    - Caso contrário, o usuário deve pertencer à empresa do slug.
    - Se require_admin=True, o usuário também deve ser COMPANY_ADMIN.
    - Se allow_user_role=False, COMPANY_USER não pode acessar (exceto verificador).
    Respostas padrão: 403 HTML.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            user = request.user
            
            # Log para debug
            logger.debug(
                f"company_access_required: Verificando acesso para {user.username if user.is_authenticated else 'anonymous'} "
                f"(slug: {kwargs.get('company_slug')}, require_admin: {require_admin})"
            )
            
            # Acesso amplo para RM/superuser
            if user.is_authenticated and (getattr(user, 'is_rm_admin', False) or getattr(user, 'is_superuser', False)):
                logger.debug(f"company_access_required: Acesso permitido para RM/superuser {user.username}")
                return view_func(request, *args, **kwargs)
            
            # Buscar empresa pelo slug
            company_slug = kwargs.get('company_slug')
            if not user.is_authenticated:
                logger.warning(f"company_access_required: Usuário não autenticado para slug {company_slug}")
                raise PermissionDenied("Você precisa estar autenticado para acessar esta página.")
            
            if not company_slug:
                logger.warning(f"company_access_required: Slug de empresa não fornecido")
                raise PermissionDenied("Slug de empresa não fornecido.")
            
            # Import lazy para evitar ciclos
            from .models import Company
            try:
                company = Company.objects.get(slug=company_slug)
            except Company.DoesNotExist:
                logger.error(f"company_access_required: Empresa com slug '{company_slug}' não encontrada")
                raise PermissionDenied(f"Empresa '{company_slug}' não encontrada.")
            
            # Verificação de pertencimento
            if not user.company:
                logger.warning(
                    f"company_access_required: Usuário {user.username} não tem empresa associada "
                    f"(tentando acessar {company_slug})"
                )
                raise PermissionDenied("Você não tem autorização para acessar esta página. Usuário sem empresa associada.")
            
            if user.company != company:
                logger.warning(
                    f"company_access_required: Usuário {user.username} pertence à empresa {user.company.slug} "
                    f"mas tentou acessar {company_slug}"
                )
                raise PermissionDenied(
                    f"Você não tem autorização para acessar esta página. Você pertence à empresa '{user.company.name}', "
                    f"mas está tentando acessar dados da empresa '{company.name}'."
                )
            
            # COMPANY_USER só pode acessar verificador e upload
            if user.role == 'COMPANY_USER' and not allow_user_role:
                logger.info(
                    f"company_access_required: COMPANY_USER {user.username} tentou acessar página restrita, "
                    f"redirecionando para verificador"
                )
                # Redirecionar para verificador se tentar acessar outras páginas
                from django.shortcuts import redirect
                return redirect('company:ftth_viewer:index', company_slug=company_slug)
            
            # Se requer admin, validar
            if require_admin:
                is_company_admin = getattr(user, 'is_company_admin', False)
                if not is_company_admin:
                    logger.warning(
                        f"company_access_required: Usuário {user.username} (role: {user.role}) "
                        f"tentou acessar página que requer COMPANY_ADMIN"
                    )
                    raise PermissionDenied(
                        "Você não tem autorização para acessar esta página. "
                        "Apenas administradores da empresa podem acessar esta funcionalidade."
                    )
            
            logger.debug(f"company_access_required: Acesso permitido para {user.username} a {company_slug}")
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


def company_module_admin_required(module_code):
    """
    Módulo habilitado na empresa + apenas COMPANY_ADMIN (ou RM/superuser).
    Uso: alertas, configurações sensíveis.
    """
    def decorator(view_func):
        @company_access_required(require_admin=True)
        @company_module_required(module_code)
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


def company_module_required(module_code):
    """
    Exige que a empresa do slug tenha o módulo habilitado.
    RM/superuser passam; demais usuários precisam pertencer à empresa.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            user = request.user
            company_slug = kwargs.get("company_slug")
            from .models import Company

            if user.is_authenticated and (
                getattr(user, "is_rm_admin", False) or getattr(user, "is_superuser", False)
            ):
                if company_slug:
                    company = Company.objects.filter(slug=company_slug).first()
                    if company and not company.has_module(module_code):
                        raise PermissionDenied(
                            f"O módulo '{module_code}' não está habilitado para esta empresa."
                        )
                return view_func(request, *args, **kwargs)

            if not user.is_authenticated or not company_slug:
                raise PermissionDenied("Acesso negado.")

            try:
                company = Company.objects.get(slug=company_slug)
            except Company.DoesNotExist:
                raise PermissionDenied("Empresa não encontrada.")

            if not user.company or user.company_id != company.id:
                raise PermissionDenied("Você não tem autorização para acessar esta empresa.")

            if not company.has_module(module_code):
                raise PermissionDenied(
                    "Este módulo não está contratado para sua empresa. "
                    "Entre em contato com o suporte RM Systems."
                )
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


def rm_admin_required_json(view_func):
    """JSON/AJAX — apenas RM ou superuser."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        user = request.user
        if user.is_authenticated and (
            getattr(user, "is_rm_admin", False) or getattr(user, "is_superuser", False)
        ):
            return view_func(request, *args, **kwargs)
        return JsonResponse({"error": "Sem permissão"}, status=403)

    return _wrapped


def company_access_required_json(require_admin=False):
    """
    Variante para endpoints JSON/AJAX.
    - Responde com JsonResponse(status=403) quando sem permissão.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            user = request.user
            # Acesso amplo para RM/superuser
            if user.is_authenticated and (getattr(user, 'is_rm_admin', False) or getattr(user, 'is_superuser', False)):
                return view_func(request, *args, **kwargs)
            company_slug = kwargs.get('company_slug')
            if not user.is_authenticated or not company_slug:
                return JsonResponse({'error': 'Sem permissão'}, status=403)
            from .models import Company
            try:
                company = Company.objects.get(slug=company_slug)
            except Company.DoesNotExist:
                return JsonResponse({'error': 'Sem permissão'}, status=403)
            if not user.company or user.company != company:
                return JsonResponse({'error': 'Sem permissão'}, status=403)
            if require_admin and not getattr(user, 'is_company_admin', False):
                return JsonResponse({'error': 'Sem permissão'}, status=403)
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


def same_company_required(view_func):
    """Mantido por compatibilidade; use company_access_required(False)."""
    return company_access_required(require_admin=False)(view_func)


class SameCompanyRequiredMixin:
    """Mixin que verifica se o usuário pode acessar dados da empresa"""
    def dispatch(self, request, *args, **kwargs):
        # Para uso futuro com CBVs
        return super().dispatch(request, *args, **kwargs)

# Mixins para Class-Based Views
class RMAdminRequiredMixin:
    """Mixin que exige que o usuário seja administrador RM ou superusuário"""

    def dispatch(self, request, *args, **kwargs):
        # Superusuários sempre têm acesso
        if hasattr(request.user, 'is_superuser') and request.user.is_superuser:
            return super().dispatch(request, *args, **kwargs)
        if not is_rm_admin(request.user):
            raise PermissionDenied("Acesso restrito a administradores RM.")
        return super().dispatch(request, *args, **kwargs)

class CompanyAdminRequiredMixin:
    """Mixin que exige que o usuário seja administrador da empresa ou superusuário"""

    def dispatch(self, request, *args, **kwargs):
        # Superusuários sempre têm acesso
        if hasattr(request.user, 'is_superuser') and request.user.is_superuser:
            return super().dispatch(request, *args, **kwargs)
        if not (is_rm_admin(request.user) or is_company_admin(request.user)):
            raise PermissionDenied("Acesso restrito a administradores.")
        return super().dispatch(request, *args, **kwargs)

class UserManagementRequiredMixin:
    """Mixin que exige permissão para gerenciar usuários ou ser superusuário"""

    def dispatch(self, request, *args, **kwargs):
        # Superusuários sempre têm acesso
        if hasattr(request.user, 'is_superuser') and request.user.is_superuser:
            return super().dispatch(request, *args, **kwargs)
        if not can_manage_users(request.user):
            raise PermissionDenied("Você não tem permissão para gerenciar usuários.")
        return super().dispatch(request, *args, **kwargs)

class MapUploadRequiredMixin:
    """Mixin que exige permissão para upload de mapas ou ser superusuário"""

    def dispatch(self, request, *args, **kwargs):
        # Superusuários sempre têm acesso
        if hasattr(request.user, 'is_superuser') and request.user.is_superuser:
            return super().dispatch(request, *args, **kwargs)
        if not can_upload_maps(request.user):
            raise PermissionDenied("Você não tem permissão para fazer upload de mapas.")
        return super().dispatch(request, *args, **kwargs)

class SameCompanyRequiredMixin:
    """Mixin que verifica se o usuário pode acessar dados da empresa"""

    def dispatch(self, request, *args, **kwargs):
        # Implementação específica deve ser feita nas views que herdam este mixin
        return super().dispatch(request, *args, **kwargs)