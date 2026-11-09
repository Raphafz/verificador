"""Resolução de tenant — path slug + header X-Company-Slug (fallback)."""
from __future__ import annotations

from rest_framework.exceptions import NotFound, PermissionDenied

from core.models import Company


class TenantResolutionError(Exception):
    """Slug do path e header X-Company-Slug divergem."""


def resolve_tenant_slug(request, path_slug: str | None = None) -> str | None:
    header = (request.META.get("HTTP_X_COMPANY_SLUG") or "").strip()
    if path_slug and header and header != path_slug:
        raise TenantResolutionError("Conflito entre slug da URL e header X-Company-Slug.")
    return path_slug or header or None


def get_company_for_request(request, path_slug: str | None = None) -> Company:
    """Resolve empresa ativa e valida acesso do usuário autenticado."""
    slug = resolve_tenant_slug(request, path_slug)
    if not slug:
        raise NotFound("Tenant não informado (slug ou X-Company-Slug).")

    try:
        company = Company.objects.get(slug=slug, is_active=True)
    except Company.DoesNotExist as exc:
        raise NotFound("Empresa não encontrada.") from exc

    user = request.user
    if not user.is_authenticated:
        raise PermissionDenied("Autenticação necessária.")

    if user.is_rm_admin or user.is_superuser:
        return company

    if not user.company_id or user.company.slug != company.slug:
        raise PermissionDenied("Sem permissão para esta empresa.")

    return company


def get_company_from_user_context(request) -> Company | None:
    """
    Tenant do contexto JWT/sessão — empresa do usuário ou X-Company-Slug (operador RM).
    Usado por GET /api/v1/companies/me/.
    """
    user = request.user
    if not user.is_authenticated:
        return None

    header_slug = (request.META.get("HTTP_X_COMPANY_SLUG") or "").strip()
    if header_slug and (user.is_rm_admin or user.is_superuser):
        return Company.objects.filter(slug=header_slug, is_active=True).first()

    if user.company_id:
        return user.company

    return None
