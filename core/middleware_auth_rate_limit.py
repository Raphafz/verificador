"""Rate limit em rotas de autenticação (sempre ativo, inclusive em DEBUG)."""
from django.http import HttpResponse, JsonResponse
from django.utils.deprecation import MiddlewareMixin

from .rate_limiting import login_limiter

_AUTH_PATH_MARKERS = (
    "/login/",
    "/signin/",
    "/password-reset/",
    "/account/activate/",
    "/account_activate/",
    "/change-password/",
)


class AuthRateLimitMiddleware(MiddlewareMixin):
    """Limita tentativas em login e fluxos de senha (mitiga password_policy / brute-force)."""

    def process_view(self, request, view_func, view_args, view_kwargs):
        path = (request.path or "").lower()
        if not any(marker in path for marker in _AUTH_PATH_MARKERS):
            return None
        if not login_limiter.is_allowed(request, "auth"):
            if "application/json" in (request.headers.get("Accept") or ""):
                return JsonResponse(
                    {"error": "Muitas tentativas. Aguarde e tente novamente."},
                    status=429,
                )
            return HttpResponse(
                "Muitas tentativas. Aguarde alguns minutos e tente novamente.",
                status=429,
            )
        return None
