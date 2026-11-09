"""Context processors globais."""
from django.conf import settings
from django.core.cache import cache


def _normalize_rm_email(value: str, default_local: str) -> str:
    """Garante domínio @rmsys.com.br (migra legado @rmsys.app)."""
    email = (value or "").strip() or f"{default_local}@rmsys.com.br"
    if email.endswith("@rmsys.app"):
        return email[:-10] + "@rmsys.com.br"
    return email


def saas_platform(request):
    company = getattr(request, "company", None)
    user = getattr(request, "user", None)
    if not company and user and getattr(user, "is_authenticated", False) and getattr(user, "company", None):
        company = user.company
    codes = company.enabled_modules() if company else []
    if (
        user
        and getattr(user, "is_authenticated", False)
        and getattr(user, "role", None) == "COMPANY_USER"
    ):
        codes = [c for c in codes if c != "alertas"]
    return {
        "saas_company": company,
        "saas_modules": codes,
        "saas_module_codes": codes,
        "saas_product_name": getattr(settings, "SAAS_PRODUCT_NAME", "RM Systems"),
        "site_dpo_email": _normalize_rm_email(
            getattr(settings, "DPO_EMAIL", ""),
            "privacidade",
        ),
        "site_support_email": _normalize_rm_email(
            getattr(settings, "EMAIL_SUPPORT_EMAIL", ""),
            "suporte",
        ),
        "site_comercial_email": "comercial@rmsys.com.br",
    }


_QUOTA_CONTEXT_PATH_MARKERS = ("/hub/", "/painel/")


def company_quotas(request):
    """Uso vs limites do plano — só em páginas que exibem quota_usage.html."""
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return {}
    if not (
        getattr(user, "is_company_admin", False)
        or getattr(user, "is_rm_admin", False)
    ):
        return {}

    path = (getattr(request, "path", None) or "").lower()
    if not any(marker in path for marker in _QUOTA_CONTEXT_PATH_MARKERS):
        return {}

    company = getattr(request, "company", None)
    if not company:
        company = getattr(user, "company", None)
    if not company:
        return {}
    try:
        from core.quotas import get_usage_summary

        cache_key = f"quota_summary:v1:{company.pk}"
        summary = cache.get(cache_key)
        if summary is None:
            summary = get_usage_summary(company)
            cache.set(cache_key, summary, 120)
        return {"quota_summary": summary}
    except Exception:
        return {}


def security_context(request):
    return {
        "csp_nonce": getattr(request, "csp_nonce", ""),
        "csp_strict": getattr(settings, "CSP_STRICT", True),
        "ftth_search_history_enabled": getattr(settings, "FTTH_SEARCH_HISTORY_ENABLED", True),
        "ftth_search_history_max_items": getattr(settings, "FTTH_SEARCH_HISTORY_MAX_ITEMS", 8),
        "ftth_search_history_ttl_minutes": getattr(settings, "FTTH_SEARCH_HISTORY_TTL_MINUTES", 30),
    }


def ui_context(request):
    from core.ui_helpers import is_ui_v2

    enabled = is_ui_v2(request)
    return {
        "ui_v2": enabled,
        "ui_shell": "base_app_v2.html" if enabled else "base.html",
        "ui_auth_shell": "base_auth_v2.html" if enabled else None,
    }
