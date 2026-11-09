"""
Views personalizadas para tratamento de erros
"""
from django.shortcuts import render
from django.http import HttpResponseServerError, HttpResponseNotFound, HttpResponseForbidden, HttpResponseBadRequest
import logging

logger = logging.getLogger(__name__)

def custom_404(request, exception=None):
    """View personalizada para erro 404"""
    try:
        # Forçar uso da página personalizada mesmo em DEBUG
        # Usar context vazio para evitar erros de reverse em URLs
        return render(request, 'errors/404.html', {}, status=404)
    except Exception as e:
        logger.error(f"Erro ao renderizar 404: {str(e)}")
        try:
            return render(request, 'errors/generic.html', status=404)
        except Exception as e2:
            logger.error(f"Erro ao renderizar página genérica: {str(e2)}")
            return HttpResponseNotFound("""
            <html>
            <head><title>404 - Página não encontrada</title></head>
            <body style="margin:0;padding:0;height:100vh;display:flex;align-items:center;justify-content:center;background:#f8f9fa;font-family:Arial,sans-serif;">
                <div style="text-align:center;max-width:500px;padding:2rem;">
                    <h1 style="color:#dc3545;font-size:4rem;margin:0;">404</h1>
                    <h2 style="color:#333;margin:1rem 0;">Página não encontrada</h2>
                    <p style="color:#666;margin:1rem 0;">A página que você está procurando não existe.</p>
                    <a href="/" style="display:inline-block;padding:0.75rem 1.5rem;background:#007bff;color:white;text-decoration:none;border-radius:4px;">Voltar ao início</a>
                </div>
            </body>
            </html>
            """)

def force_404(request):
    """Força 404 para qualquer URL não encontrada"""
    return custom_404(request)

def custom_500(request):
    """View personalizada para erro 500"""
    try:
        return render(request, 'errors/500.html', status=500)
    except Exception as e:
        logger.error(f"Erro ao renderizar 500: {str(e)}")
        try:
            return render(request, 'errors/generic.html', status=500)
        except Exception as e2:
            logger.error(f"Erro ao renderizar página genérica: {str(e2)}")
            return HttpResponseServerError("""
            <html>
            <head><title>500 - Erro interno do servidor</title></head>
            <body>
                <h1>500 - Erro interno do servidor</h1>
                <p>Ocorreu um erro inesperado. Tente novamente mais tarde.</p>
                <a href="/">Voltar ao início</a>
            </body>
            </html>
            """)

def custom_403(request, *args, **kwargs):
    """
    View personalizada para erro 403.
    Aceita exception (handler403) ou reason (CSRF_FAILURE_VIEW).
    """
    reason = kwargs.get("reason")
    exception = kwargs.get("exception")

    if args:
        first = args[0]
        if reason is None and isinstance(first, str):
            reason = first
        elif exception is None and not isinstance(first, str):
            exception = first

    logger.error(
        f"Erro 403: path={request.path}, method={request.method}, "
        f"is_csrf_error={bool(reason)}, reason={reason}, exception={exception!r}, "
        f"origin={request.META.get('HTTP_ORIGIN', 'N/A')}, "
        f"referer={request.META.get('HTTP_REFERER', 'N/A')}, "
        f"host={request.get_host()}, "
        f"is_secure={request.is_secure()}"
    )

    if reason:
        error_message = "Verificação de segurança falhou. Atualize a página e tente novamente."
    elif exception:
        error_message = str(exception) or "Você não tem permissão para acessar esta página."
    else:
        error_message = "Acesso negado. Verifique sua sessão e permissões."

    user = getattr(request, "user", None)
    hub_url = None
    home_url = "/"
    login_url = None
    if user and user.is_authenticated:
        company = getattr(user, "company", None)
        if company and getattr(company, "slug", None):
            hub_url = f"/{company.slug}/hub/"
            login_url = f"/{company.slug}/login/"
            home_url = hub_url
        elif getattr(user, "is_rm_admin", False) or getattr(user, "is_superuser", False):
            home_url = "/rm/dashboard/"
            login_url = "/rm/login/"

    try:
        context = {
            "error_message": error_message,
            "is_csrf_error": bool(reason),
            "hub_url": hub_url,
            "home_url": home_url,
            "login_url": login_url,
        }
        return render(request, "errors/403.html", context, status=403)
    except Exception as e:
        logger.error(f"Erro ao renderizar 403: {str(e)}")
        return HttpResponseForbidden(f"""
        <html>
        <head><title>403 - Acesso negado</title></head>
        <body style="margin:0;padding:0;height:100vh;display:flex;align-items:center;justify-content:center;background:#f8f9fa;font-family:Arial,sans-serif;">
            <div style="text-align:center;max-width:500px;padding:2rem;">
                <h1 style="color:#dc3545;font-size:4rem;margin:0;">403</h1>
                <h2 style="color:#333;margin:1rem 0;">Acesso negado</h2>
                <p style="color:#666;margin:1rem 0;">{error_message}</p>
                <a href="/" style="display:inline-block;padding:0.75rem 1.5rem;background:#007bff;color:white;text-decoration:none;border-radius:4px;">Voltar ao início</a>
            </div>
        </body>
        </html>
        """)

def custom_400(request, exception=None):
    """View personalizada para erro 400"""
    try:
        return render(request, 'errors/400.html', status=400)
    except Exception as e:
        logger.error(f"Erro ao renderizar 400: {str(e)}")
        return HttpResponseBadRequest("""
        <html>
        <head><title>400 - Requisição inválida</title></head>
        <body>
            <h1>400 - Requisição inválida</h1>
            <p>A requisição não pôde ser processada.</p>
            <a href="/">Voltar ao início</a>
        </body>
        </html>
        """)
