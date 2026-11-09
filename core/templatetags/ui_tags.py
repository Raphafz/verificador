"""
Tags de UI — breadcrumbs e helpers visuais (sem lógica de negócio).
"""
from django import template
from django.template.loader import render_to_string
from django.urls import NoReverseMatch, reverse
from django.utils.safestring import mark_safe

register = template.Library()

# (namespace, url_name) -> (label, parent_url_name ou None)
# parent resolve no mesmo namespace salvo indicação
_RM_CRUMBS = {
    ("rm", "admin_dashboard"): ("Dashboard", None),
    ("rm", "company_list"): ("Empresas", "admin_dashboard"),
    ("rm", "company_create"): ("Nova empresa", "company_list"),
    ("rm", "company_edit"): ("Editar empresa", "company_list"),
    ("rm", "user_list"): ("Usuários RM", "admin_dashboard"),
    ("rm", "user_create"): ("Novo usuário", "user_list"),
    ("rm", "user_edit"): ("Editar usuário", "user_list"),
    ("rm", "map_list"): ("Mapas", "admin_dashboard"),
    ("rm", "map_by_company"): ("Upload de mapa", "map_list"),
    ("rm", "ticket_list"): ("Tickets", "admin_dashboard"),
    ("rm", "ticket_detail"): ("Detalhe do ticket", "ticket_list"),
    ("rm", "reports"): ("Relatórios", "admin_dashboard"),
    ("company", "dashboard"): ("Dashboard", "hub"),
    ("company", "hub"): ("Hub", None),
    ("company", "user_list"): ("Usuários", "hub"),
    ("company", "user_create"): ("Novo usuário", "user_list"),
    ("company", "user_edit"): ("Editar usuário", "user_list"),
    ("company", "upload"): ("Upload", "hub"),
    ("company", "map_history"): ("Histórico", "hub"),
    ("company", "map_list"): ("Mapas", "hub"),
    ("company", "reports"): ("Relatórios", "hub"),
    ("company", "ticket_list"): ("Tickets", "hub"),
    ("company", "ticket_create"): ("Novo ticket", "ticket_list"),
    ("company", "ticket_detail"): ("Ticket", "ticket_list"),
    ("company", "ftth_viewer:index"): ("Verificador", "hub"),
    ("company", "alerts:settings"): ("Alertas", "hub"),
    ("company", "olt_ops:home"): ("OLT / ONU", "hub"),
    ("company", "olt_ops:olt_list"): ("OLTs", "olt_ops:home"),
    ("company", "olt_ops:job_detail"): ("Job OLT", "olt_ops:home"),
    ("company", "olt_ops:vpn_settings"): ("VPN OLT", "olt_ops:home"),
}

# url_names que precisam de company_slug nos kwargs
_COMPANY_SLUG_URLS = {
    "dashboard",
    "hub",
    "user_list",
    "user_create",
    "user_edit",
    "upload",
    "map_history",
    "map_list",
    "reports",
    "ticket_list",
    "ticket_create",
    "ticket_detail",
}


def _safe_reverse(view_name, namespace=None, user=None, company_slug=None):
    name = f"{namespace}:{view_name}" if namespace else view_name
    kwargs = {}
    if namespace == "company" and company_slug:
        kwargs["company_slug"] = company_slug
    try:
        return reverse(name, kwargs=kwargs)
    except NoReverseMatch:
        return None


def _build_trail(namespace, url_name, user, company_slug=None, extra_items=None):
    if (namespace, url_name) not in _RM_CRUMBS:
        if extra_items:
            return list(extra_items)
        return []

    chain = []
    current = url_name
    visited = set()
    while current and (namespace, current) not in visited:
        visited.add((namespace, current))
        label, parent = _RM_CRUMBS[(namespace, current)]
        chain.insert(0, (current, label))
        current = parent

    trail = []
    home_label = "RM Systems"
    home_url = None
    if user and getattr(user, "is_authenticated", False):
        if getattr(user, "is_rm_admin", False):
            home_url = _safe_reverse("admin_dashboard", "rm")
        elif company_slug:
            home_url = _safe_reverse("hub", "company", user=user, company_slug=company_slug)
            home_label = "Início"
    trail.append({"label": home_label, "url": home_url})

    for view_name, lbl in chain[:-1]:
        trail.append({
            "label": lbl,
            "url": _safe_reverse(view_name, namespace, user=user, company_slug=company_slug),
        })

    if extra_items:
        for item in extra_items:
            trail.append(item)

    _view_last, last_label = chain[-1]
    trail.append({"label": last_label, "url": None})

    return trail


@register.simple_tag(takes_context=True)
def rm_breadcrumbs(context, extra=None):
    """Renderiza breadcrumbs sem inclusion_tag (compatível Python 3.14 + Django 4.2)."""
    request = context.get("request")
    user = context.get("user")
    if not request or not user or not getattr(user, "is_authenticated", False):
        return mark_safe("")

    match = getattr(request, "resolver_match", None)
    if not match:
        return mark_safe("")

    namespace = (match.namespace or "").strip()
    url_name = match.url_name or ""
    company_slug = match.kwargs.get("company_slug") if match.kwargs else None
    if not company_slug and getattr(user, "company", None):
        company_slug = getattr(user.company, "slug", None)

    extra_items = context.get("breadcrumb_extra") or extra
    crumbs = _build_trail(namespace, url_name, user, company_slug=company_slug, extra_items=extra_items)
    show = len(crumbs) > 1
    return mark_safe(
        render_to_string(
            "includes/rm_breadcrumbs.html",
            {"crumbs": crumbs, "show": show},
            request=request,
        )
    )
