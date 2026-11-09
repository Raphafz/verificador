"""
Rotas DRF — API REST v1 (JWT + sessão admin).
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .api import CompanyViewSet, CTOMapFileViewSet, UserViewSet
from .api_auth_account import ActivateAPIView, PasswordResetConfirmAPIView, PasswordResetRequestAPIView
from .api_auth_mfa import MfaRecoveryAPIView, MfaSetupAPIView, MfaVerifyAPIView
from .api_auth_sessions import SessionsAPIView, TrustedDevicesAPIView
from .api_auth_views import (
    ChangePasswordAPIView,
    CompaniesMeAPIView,
    CompanyMeAPIView,
    LoginAPIView,
    LogoutAPIView,
    MeAPIView,
)
from .api_billing_views import BillingStubAPIView
from .api_schema_views import RestrictedSpectacularAPIView, RestrictedSpectacularSwaggerView

router = DefaultRouter()
router.register(r"companies", CompanyViewSet, basename="api-company")
router.register(r"maps", CTOMapFileViewSet, basename="api-map")
router.register(r"users", UserViewSet, basename="api-user")

urlpatterns = [
    # Auth
    path("auth/login/", LoginAPIView.as_view(), name="api-auth-login"),
    path("auth/mfa/verify/", MfaVerifyAPIView.as_view(), name="api-auth-mfa-verify"),
    path("auth/mfa/setup/", MfaSetupAPIView.as_view(), name="api-auth-mfa-setup"),
    path("auth/mfa/recovery/", MfaRecoveryAPIView.as_view(), name="api-auth-mfa-recovery"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="api-auth-token-refresh"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="api-auth-refresh-legacy"),
    path("auth/logout/", LogoutAPIView.as_view(), name="api-auth-logout"),
    path("auth/change-password/", ChangePasswordAPIView.as_view(), name="api-auth-change-password"),
    path("auth/activate/", ActivateAPIView.as_view(), name="api-auth-activate"),
    path("auth/password-reset/", PasswordResetRequestAPIView.as_view(), name="api-auth-password-reset"),
    path(
        "auth/password-reset/confirm/",
        PasswordResetConfirmAPIView.as_view(),
        name="api-auth-password-reset-confirm",
    ),
    path("auth/trusted-devices/", TrustedDevicesAPIView.as_view(), name="api-auth-trusted-devices"),
    path("auth/sessions/", SessionsAPIView.as_view(), name="api-auth-sessions"),
    # Contexto
    path("me/", MeAPIView.as_view(), name="api-me"),
    path("companies/me/", CompaniesMeAPIView.as_view(), name="api-companies-me"),
    path("companies/<slug:slug>/", CompanyMeAPIView.as_view(), name="api-company-context"),
    path("companies/<slug:slug>/ftth/", include("ftth_viewer.api_v1_urls")),
    # Stub billing (fora do escopo real)
    path("billing/", BillingStubAPIView.as_view(), name="api-billing"),
    # Admin API legada
    path("schema/", RestrictedSpectacularAPIView.as_view(), name="api-schema"),
    path("docs/", RestrictedSpectacularSwaggerView.as_view(url_name="api-schema"), name="api-docs"),
    path("", include(router.urls)),
]
