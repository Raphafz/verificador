"""Wrappers DRF para APIs FTTH em /api/v1/companies/{slug}/ftth/."""
from __future__ import annotations

from functools import wraps

from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from core.api_permissions import RequireMfaVerified
from core.api_tenant import TenantResolutionError, get_company_for_request
from ftth_viewer.views import (
    api_adicionar_cto,
    api_arquivos,
    api_cache_geocoding_clear,
    api_cache_geocoding_stats,
    api_cep,
    api_contar_pontos,
    api_coordenadas,
    api_geocode,
    api_geocode_suggestions,
    api_remover_cto,
    api_verificar_viabilidade,
)


def ftth_api_view(http_methods):
    def decorator(view_func):
        @api_view(http_methods)
        @authentication_classes([JWTAuthentication])
        @permission_classes([IsAuthenticated, RequireMfaVerified])
        @wraps(view_func)
        def _inner(request, slug, *args, **kwargs):
            try:
                company = get_company_for_request(request, slug)
            except TenantResolutionError:
                return Response({"detail": "Conflito de tenant."}, status=400)
            request.META.setdefault("HTTP_X_COMPANY_SLUG", company.slug)
            return view_func(request, company_slug=company.slug)

        return _inner

    return decorator


api_arquivos_v1 = ftth_api_view(["GET"])(api_arquivos)
api_coordenadas_v1 = ftth_api_view(["GET"])(api_coordenadas)
api_contar_pontos_v1 = ftth_api_view(["GET"])(api_contar_pontos)
api_geocode_v1 = ftth_api_view(["GET", "POST"])(api_geocode)
api_cep_v1 = ftth_api_view(["GET"])(api_cep)
api_geocode_suggestions_v1 = ftth_api_view(["GET"])(api_geocode_suggestions)
api_verificar_viabilidade_v1 = ftth_api_view(["POST"])(api_verificar_viabilidade)
api_cache_geocoding_stats_v1 = ftth_api_view(["GET"])(api_cache_geocoding_stats)
api_cache_geocoding_clear_v1 = ftth_api_view(["POST"])(api_cache_geocoding_clear)
api_adicionar_cto_v1 = ftth_api_view(["POST"])(api_adicionar_cto)
api_remover_cto_v1 = ftth_api_view(["POST"])(api_remover_cto)
