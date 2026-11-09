from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from functools import wraps
import logging
import threading

logger = logging.getLogger('security')

# Lock para sincronização de operações de cache
_cache_lock = threading.Lock()

class RateLimiter:
    """
    Sistema de rate limiting para proteção contra ataques
    """
    
    def __init__(self, requests=100, window=3600, key_prefix='rate_limit'):
        self.requests = requests
        self.window = window
        self.key_prefix = key_prefix
    
    def get_client_ip(self, request):
        """Obter IP real do cliente (política unificada em core.request_ip)."""
        from core.request_ip import get_client_ip as resolve_client_ip

        return resolve_client_ip(request) or "0.0.0.0"
    
    def get_cache_key(self, request, action=''):
        """Gerar chave de cache para rate limiting"""
        ip = self.get_client_ip(request)
        user_id = request.user.id if request.user.is_authenticated else 'anonymous'
        # Adicionar empresa ao cache key para multi-tenant
        company_slug = getattr(request, 'company_slug', 'global')
        return f"{self.key_prefix}:{company_slug}:{ip}:{user_id}:{action}"
    
    def is_allowed(self, request, action=''):
        """Verificar se a requisição é permitida (thread-safe)"""
        cache_key = self.get_cache_key(request, action)
        current_time = timezone.now().timestamp()
        
        # Usar lock para evitar race conditions
        with _cache_lock:
            # Obter requisições atuais
            requests_data = cache.get(cache_key, [])
            
            # Remover requisições antigas (fora da janela)
            cutoff_time = current_time - self.window
            requests_data = [req_time for req_time in requests_data if req_time > cutoff_time]
            
            # Verificar limite ANTES de adicionar nova requisição
            if len(requests_data) >= self.requests:
                # Salvar estado limpo no cache para próxima verificação
                cache.set(cache_key, requests_data, self.window)
                logger.warning(
                    f"Rate limit excedido para {self.get_client_ip(request)}",
                    extra={
                        'ip': self.get_client_ip(request),
                        'user_id': request.user.id if request.user.is_authenticated else None,
                        'action': action,
                        'requests_count': len(requests_data),
                        'limit': self.requests,
                        'timestamp': timezone.now().isoformat()
                    }
                )
                return False
            
            # Adicionar requisição atual
            requests_data.append(current_time)
            # Cache com timeout = window + margem de segurança (10%)
            cache.set(cache_key, requests_data, int(self.window * 1.1))
        
        return True
    
    def get_remaining_requests(self, request, action=''):
        """Obter número de requisições restantes (com limpeza do cache)"""
        cache_key = self.get_cache_key(request, action)
        current_time = timezone.now().timestamp()
        cutoff_time = current_time - self.window
        
        with _cache_lock:
            # Obter requisições atuais
            requests_data = cache.get(cache_key, [])
            
            # Remover requisições antigas (fora da janela)
            valid_requests = [req_time for req_time in requests_data if req_time > cutoff_time]
            
            # Salvar estado limpo no cache
            if len(valid_requests) != len(requests_data):
                cache.set(cache_key, valid_requests, int(self.window * 1.1))
            
            remaining = max(0, self.requests - len(valid_requests))
        
        return remaining

# Instâncias de rate limiter para diferentes ações
login_limiter = RateLimiter(requests=20, window=900)  # 20 tentativas em 15 minutos (mais permissivo)
activation_limiter = RateLimiter(requests=10, window=1800)  # 10 tentativas / 30 min (ativação de conta)
upload_limiter = RateLimiter(requests=50, window=3600)  # 50 uploads por hora
api_limiter = RateLimiter(requests=500, window=3600)  # 500 requisições por hora
general_limiter = RateLimiter(requests=1000, window=3600)  # 1000 requisições por hora

def rate_limit(limiter, action=''):
    """
    Decorator para aplicar rate limiting
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            from django.conf import settings
            import os
            force = os.getenv("FORCE_RATE_LIMIT", "").lower() in ("1", "true", "yes", "on")
            if settings.DEBUG and not force:
                return view_func(request, *args, **kwargs)
            
            if not limiter.is_allowed(request, action):
                if request.headers.get('Accept') == 'application/json':
                    return JsonResponse({
                        'error': 'Rate limit excedido',
                        'retry_after': limiter.window
                    }, status=429)
                else:
                    return HttpResponse(
                        f"Rate limit excedido. Tente novamente em {limiter.window} segundos.",
                        status=429
                    )
            
            # Calcular requisições restantes ANTES de processar a view
            remaining = limiter.get_remaining_requests(request, action)
            
            # Processar a view
            response = view_func(request, *args, **kwargs)
            
            # Adicionar headers informativos na resposta
            if hasattr(response, '__setitem__'):
                # Para HttpResponse/JsonResponse (dict-like)
                response['X-RateLimit-Limit'] = str(limiter.requests)
                response['X-RateLimit-Remaining'] = str(remaining)
                response['X-RateLimit-Reset'] = str(int(timezone.now().timestamp() + limiter.window))
            elif hasattr(response, 'headers'):
                # Para outras respostas com headers (Django HttpResponse)
                response.headers['X-RateLimit-Limit'] = str(limiter.requests)
                response.headers['X-RateLimit-Remaining'] = str(remaining)
                response.headers['X-RateLimit-Reset'] = str(int(timezone.now().timestamp() + limiter.window))
            
            return response
        return _wrapped
    return decorator

# Decorators específicos
def login_rate_limit(view_func):
    """Rate limiting para login"""
    return rate_limit(login_limiter, 'login')(view_func)


def activation_rate_limit(view_func):
    """Rate limiting para ativação de conta / definição de senha"""
    return rate_limit(activation_limiter, 'account_activate')(view_func)

def upload_rate_limit(view_func):
    """Rate limiting para upload"""
    return rate_limit(upload_limiter, 'upload')(view_func)

def api_rate_limit(view_func):
    """Rate limiting para API"""
    return rate_limit(api_limiter, 'api')(view_func)

def general_rate_limit(view_func):
    """Rate limiting geral"""
    return rate_limit(general_limiter, 'general')(view_func)

def clear_rate_limit(request, action=''):
    """Limpar rate limit para um IP/usuário específico"""
    limiter = RateLimiter()
    cache_key = limiter.get_cache_key(request, action)
    cache.delete(cache_key)
    return True

def clear_all_rate_limits():
    """Limpar todos os rate limits (usar com cuidado)"""
    cache.clear()
    return True

