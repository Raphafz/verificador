from django.shortcuts import get_object_or_404
from django.http import Http404, HttpResponseForbidden
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth import logout
from django.urls import reverse
from django.utils import timezone
import logging
from .models import Company

logger = logging.getLogger('security')

class SecureCompanyMiddleware(MiddlewareMixin):
    """
    Middleware seguro para detecção de empresa com validação de autenticação
    """
    
    def process_request(self, request):
        # Inicializar variáveis
        request.company = None
        request.company_slug = None
        request.is_rm_access = False
        
        # Extrair o primeiro segmento da URL
        path = request.path.strip('/')
        segments = path.split('/') if path else []
        
        if not segments:
            request.is_rm_access = True
            return None
            
        first_segment = segments[0].lower()
        
        # Verificar se é acesso de arquivos estáticos ou mídia
        if first_segment in ('static', 'staticfiles', 'media'):
            return None
        
        # Verificar se é acesso RM
        if first_segment == 'rm':
            request.is_rm_access = True
            return None

        # Rotas globais (não são slug de empresa)
        GLOBAL_FIRST_SEGMENTS = {
            'ativar-conta', 'change-password-required', 'consent-required', 'meus-dados', 'encarregado-dados',
            'dashboard', 'verificador', 'admin',
            'termos-uso', 'politica-privacidade', 'politica-cookies', 'lgpd',
            'faq', 'ajuda', 'manual', 'api', 'favicon.ico', 'media', 'media-signed', 'static',
            'health', 'ready', 'sentry-debug', '.well-known',
        }
        if first_segment in GLOBAL_FIRST_SEGMENTS:
            return None
        
        # Verificar se é rota de login da empresa (permitir acesso sem autenticação)
        # O login valida se o usuário pertence à empresa na view company_login_view
        if len(segments) > 1 and segments[1].lower() == 'login':
            # Permitir acesso à página de login (GET e POST) sem autenticação
            # A view company_login_view valida se o usuário pertence à empresa antes de fazer login
            try:
                company = Company.objects.filter(
                    slug__iexact=first_segment,
                    is_active=True
                ).first()
                if company:
                    request.company = company
                    request.company_slug = company.slug
                    # Permitir acesso - a view fará a validação de autenticação e pertencimento à empresa
                    return None
                else:
                    # Empresa não encontrada - deixar passar para retornar 404
                    return None
            except Exception:
                # Em caso de erro, deixar passar
                return None
            
        # Para acesso de empresa (exceto login), exigir autenticação
        if not request.user.is_authenticated:
            # Log tentativa de acesso não autenticado
            logger.warning(
                f"Tentativa de acesso não autenticado para empresa: {first_segment}",
                extra={
                    'ip': request.META.get('REMOTE_ADDR'),
                    'user_agent': request.META.get('HTTP_USER_AGENT'),
                    'path': request.path,
                    'timestamp': timezone.now().isoformat()
                }
            )
            return None
            
        # Verificar se é acesso de empresa via slug
        try:
            company = Company.objects.filter(
                slug__iexact=first_segment,
                is_active=True
            ).first()
            
            if company:
                # VALIDAÇÃO CRÍTICA: Verificar se usuário pertence à empresa
                if not request.user.is_rm_admin and not request.user.is_superuser:
                    if not request.user.company or request.user.company != company:
                        # Log tentativa de acesso não autorizado
                        logger.error(
                            f"Tentativa de acesso não autorizado: usuário {request.user.username} "
                            f"tentou acessar empresa {company.slug}",
                            extra={
                                'user_id': request.user.id,
                                'user_company': request.user.company.slug if request.user.company else None,
                                'target_company': company.slug,
                                'ip': request.META.get('REMOTE_ADDR'),
                                'timestamp': timezone.now().isoformat()
                            }
                        )
                        # Logout forçado por segurança
                        logout(request)
                        # Usar PermissionDenied para acionar a view personalizada de erro 403
                        from django.core.exceptions import PermissionDenied
                        raise PermissionDenied(
                            f"Acesso negado: Você pertence à empresa '{request.user.company.name if request.user.company else 'Nenhuma'}', "
                            f"mas tentou acessar dados da empresa '{company.name}'."
                        )
                
                request.company = company
                request.company_slug = company.slug
                
                # Log acesso autorizado
                logger.info(
                    f"Acesso autorizado: {request.user.username} acessou {company.slug}",
                    extra={
                        'user_id': request.user.id,
                        'company_slug': company.slug,
                        'ip': request.META.get('REMOTE_ADDR'),
                        'timestamp': timezone.now().isoformat()
                    }
                )
                return None
            else:
                # Empresa não encontrada
                logger.warning(
                    f"Tentativa de acesso a empresa inexistente: {first_segment}",
                    extra={
                        'user_id': request.user.id if request.user.is_authenticated else None,
                        'ip': request.META.get('REMOTE_ADDR'),
                        'timestamp': timezone.now().isoformat()
                    }
                )
                return None
                
        except Exception as e:
            logger.error(
                f"Erro no middleware de empresa: {str(e)}",
                extra={
                    'user_id': request.user.id if request.user.is_authenticated else None,
                    'ip': request.META.get('REMOTE_ADDR'),
                    'timestamp': timezone.now().isoformat()
                }
            )
            return None
