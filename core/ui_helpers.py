"""Helpers UI v2 — feature flag e seleção de templates."""
from django.conf import settings


def is_ui_v2(request) -> bool:
    if getattr(settings, "UI_V2", False):
        return True
    if not request:
        return False
    if request.COOKIES.get(getattr(settings, "UI_V2_COOKIE", "rm-ui-v2")) == "1":
        return True
    if request.GET.get("v2") == "1":
        return True
    return False


def ui_template(request, legacy: str, v2: str) -> str:
    return v2 if is_ui_v2(request) else legacy
