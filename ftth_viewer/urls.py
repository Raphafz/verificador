"""
URLs do app FTTH Viewer
"""
from django.urls import path
from . import views

app_name = 'ftth_viewer'

urlpatterns = [
    # Página principal
    path('', views.index, name='index'),
    
    # APIs
    path('api/arquivos', views.api_arquivos, name='api_arquivos'),
    path('api/coordenadas', views.api_coordenadas, name='api_coordenadas'),
    path('api/contar-pontos', views.api_contar_pontos, name='api_contar_pontos'),
    path('api/geocode', views.api_geocode, name='api_geocode'),
    path('api/cep', views.api_cep, name='api_cep'),
    path('api/geocode/suggestions', views.api_geocode_suggestions, name='api_geocode_suggestions'),
    path('api/verificar-viabilidade', views.api_verificar_viabilidade, name='api_verificar_viabilidade'),
    path('api/cache/geocoding/stats', views.api_cache_geocoding_stats, name='api_cache_geocoding_stats'),
    path('api/cache/geocoding/clear', views.api_cache_geocoding_clear, name='api_cache_geocoding_clear'),
    path('api/adicionar-cto', views.api_adicionar_cto, name='api_adicionar_cto'),
    path('api/remover-cto', views.api_remover_cto, name='api_remover_cto'),
]

