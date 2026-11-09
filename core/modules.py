"""Helpers para módulos do SaaS unificado (Verificador, Alertas, OLT)."""

MODULE_META = {
    "verificador": {
        "label": "Verificador FTTH",
        "icon": "fa-search",
        "description": "Mapas CTO e viabilidade de instalação",
        "color": "#1D4ED8",
    },
    "alertas": {
        "label": "Alertas",
        "icon": "fa-bell",
        "description": "Telegram → WhatsApp (monitoramento de rede)",
        "color": "#059669",
    },
    "olt": {
        "label": "OLT / ONU",
        "icon": "fa-server",
        "description": "Listar offline e remover ONTs em OLT GPON",
        "color": "#D97706",
    },
}


def _module_entry(company, user, code):
    """Metadados + URL resolvida no Python (evita erro de template/namespace)."""
    from django.urls import NoReverseMatch, reverse

    meta = MODULE_META.get(code, {})
    slug = company.slug
    try:
        if code == "verificador":
            url = reverse("company:ftth_viewer:index", kwargs={"company_slug": slug})
        elif code == "alertas":
            if not (getattr(user, "is_company_admin", False) or getattr(user, "is_rm_admin", False)):
                return None
            url = reverse("company:alerts:settings", kwargs={"company_slug": slug})
        elif code == "olt":
            url = reverse("company:olt_ops:home", kwargs={"company_slug": slug})
        else:
            return None
    except NoReverseMatch:
        return None

    return {
        "code": code,
        "label": meta.get("label", code),
        "icon": meta.get("icon", "fa-cube"),
        "description": meta.get("description", ""),
        "color": meta.get("color", "#64748B"),
        "url": url,
    }


def get_company_modules(company, user=None):
    """Retorna metadados dos módulos habilitados para templates e hub."""
    if not company:
        return []
    result = []
    for code in company.enabled_modules():
        if user is not None:
            entry = _module_entry(company, user, code)
            if entry:
                result.append(entry)
        else:
            meta = MODULE_META.get(code, {})
            result.append({
                "code": code,
                "label": meta.get("label", code),
                "icon": meta.get("icon", "fa-cube"),
                "description": meta.get("description", ""),
                "color": meta.get("color", "#64748B"),
            })
    return result


def post_login_redirect_url(user):
    """Destino após login conforme módulos habilitados."""
    from django.urls import reverse

    if not user.company:
        return reverse("rm:admin_dashboard")

    slug = user.company.slug
    modules = user.company.enabled_modules()

    if len(modules) != 1:
        return reverse("company:hub", kwargs={"company_slug": slug})

    only = modules[0]
    if only == "verificador":
        return reverse("company:ftth_viewer:index", kwargs={"company_slug": slug})
    if only == "alertas":
        if getattr(user, "is_company_admin", False) or getattr(user, "is_rm_admin", False):
            return reverse("company:alerts:settings", kwargs={"company_slug": slug})
        if "verificador" in modules:
            return reverse("company:ftth_viewer:index", kwargs={"company_slug": slug})
        return reverse("company:hub", kwargs={"company_slug": slug})
    if only == "olt":
        return reverse("company:olt_ops:home", kwargs={"company_slug": slug})
    return reverse("company:hub", kwargs={"company_slug": slug})


def resolve_company_for_request(request):
    """Empresa do tenant atual (middleware, usuário ou slug na URL)."""
    company = getattr(request, "company", None)
    if company:
        return company
    user = getattr(request, "user", None)
    if user and user.is_authenticated and getattr(user, "company", None):
        return user.company
    slug = None
    if hasattr(request, "resolver_match") and request.resolver_match:
        slug = request.resolver_match.kwargs.get("company_slug")
    if slug:
        from core.models import Company
        try:
            return Company.objects.get(slug=slug)
        except Company.DoesNotExist:
            return None
    return None
