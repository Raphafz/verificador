"""OpenAPI / Swagger — acesso restrito a RM."""
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.permissions import IsAuthenticated

from core.permissions import IsRMAdmin


class RestrictedSpectacularAPIView(SpectacularAPIView):
    permission_classes = [IsAuthenticated, IsRMAdmin]


class RestrictedSpectacularSwaggerView(SpectacularSwaggerView):
    permission_classes = [IsAuthenticated, IsRMAdmin]
