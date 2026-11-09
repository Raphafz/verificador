"""
Middleware para forçar mudança de senha no primeiro acesso
"""
from django.shortcuts import redirect
from django.urls import reverse, resolve
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth import logout
import logging

logger = logging.getLogger(__name__)

class PasswordChangeMiddleware(MiddlewareMixin):
    """
    Middleware que força a mudança de senha no primeiro acesso
    """
    
    # URLs que não requerem mudança de senha
    EXEMPT_PATHS = [
        '/ativar-conta/',
        '/change-password-required/',
        '/consent-required/',
        '/encarregado-dados/',
        '/rm/login/',
        '/login/',
        '/logout/',
        '/static/',
        '/media/',
        '/admin/logout/',
        '/admin/jsi18n/',
        '/termos-uso/',
        '/politica-privacidade/',
        '/politica-cookies/',
        '/lgpd/',
        '/faq/',
        '/ajuda/',
        '/manual/',
        '/meus-dados/',
        '/health/',
        '/ready/',
        '/api/v1/',
    ]
    
    def process_request(self, request):
        # Apenas verificar se usuário está autenticado
        if not request.user.is_authenticated:
            return None
        
        # Verificar se o caminho atual está na lista de exceções
        path = request.path
        for exempt_path in self.EXEMPT_PATHS:
            if path.startswith(exempt_path):
                return None
        
        # Verificar se usuário precisa mudar a senha
        if hasattr(request.user, 'must_change_password') and request.user.must_change_password:
            # Verificar se já está na página de mudança de senha
            if path == '/change-password-required/' or path.startswith('/change-password-required'):
                return None
            
            # Redirecionar para página de mudança obrigatória de senha
            logger.info(f"Redirecionando usuário {request.user.username} para mudança obrigatória de senha")
            return redirect('change_password_required')
        
        return None

