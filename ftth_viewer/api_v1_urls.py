"""Rotas FTTH v1 — /api/v1/companies/<slug>/ftth/..."""
from django.urls import path

from . import api_v1_wrappers as v1

urlpatterns = [
    path("arquivos", v1.api_arquivos_v1, name="ftth-v1-arquivos"),
    path("coordenadas", v1.api_coordenadas_v1, name="ftth-v1-coordenadas"),
    path("contar-pontos", v1.api_contar_pontos_v1, name="ftth-v1-contar-pontos"),
    path("geocode", v1.api_geocode_v1, name="ftth-v1-geocode"),
    path("cep", v1.api_cep_v1, name="ftth-v1-cep"),
    path("geocode/suggestions", v1.api_geocode_suggestions_v1, name="ftth-v1-geocode-suggestions"),
    path("verificar-viabilidade", v1.api_verificar_viabilidade_v1, name="ftth-v1-verificar-viabilidade"),
    path("cache/geocoding/stats", v1.api_cache_geocoding_stats_v1, name="ftth-v1-cache-stats"),
    path("cache/geocoding/clear", v1.api_cache_geocoding_clear_v1, name="ftth-v1-cache-clear"),
    path("adicionar-cto", v1.api_adicionar_cto_v1, name="ftth-v1-adicionar-cto"),
    path("remover-cto", v1.api_remover_cto_v1, name="ftth-v1-remover-cto"),
]
