"""Middleware — preview UI v2 via query ?v2=1 ou ?v2=0."""
from django.conf import settings


class UiV2PreviewMiddleware:
    """Persiste opt-in/opt-out de UI v2 em cookie (30 dias)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not getattr(settings, "UI_V2_PREVIEW_COOKIE", True):
            return response
        cookie_name = getattr(settings, "UI_V2_COOKIE", "rm-ui-v2")
        v2_param = request.GET.get("v2")
        if v2_param == "1":
            response.set_cookie(cookie_name, "1", max_age=86400 * 30, samesite="Lax")
        elif v2_param == "0":
            response.delete_cookie(cookie_name)
        return response
