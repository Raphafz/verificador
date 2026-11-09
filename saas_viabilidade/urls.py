from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from django.contrib.auth import views as auth_views
from django.http import FileResponse, Http404
from core import views as core_views
from core.views import home_redirect, dashboard_redirect
from core.admin import rm_admin_site
from core.error_views import custom_404, force_404
from alerts.views import worker_configs_api
from core.billing.asaas_webhook import asaas_webhook
from core import lgpd_views
from core.activation_views import account_activate
from core import health_views
from core import bimi_views
from core.media_protected import serve_protected_media, serve_protected_media_signed

urlpatterns = [
    path("health/", health_views.health_live, name="health_live"),
    path("health/security/", health_views.health_security, name="health_security"),
    path("ready/", health_views.health_ready, name="health_ready"),
    path("api/v1/", include("core.api_urls")),
    path("api/internal/alert-bridge/configs/", worker_configs_api, name="alert_bridge_configs"),
    path("api/webhooks/asaas/", asaas_webhook, name="asaas_webhook"),
    path("ativar-conta/<str:token>/", account_activate, name="account_activate"),
    path("consent-required/", lgpd_views.consent_required, name="consent_required"),
    path("meus-dados/", lgpd_views.my_data_portal, name="my_data_portal"),
    path("meus-dados/exportar/", lgpd_views.my_data_export, name="my_data_export"),
    path(
        "meus-dados/download/<str:token>/",
        lgpd_views.my_data_export_download,
        name="my_data_export_download",
    ),
    path("meus-dados/excluir/", lgpd_views.my_data_delete_request, name="my_data_delete_request"),
    path("encarregado-dados/", lgpd_views.dpo_contact_view, name="dpo_contact"),
    path("admin/", rm_admin_site.urls),
    # Rota genérica de dashboard que redireciona conforme papel do usuário
    path("dashboard/", dashboard_redirect, name="dashboard"),
    
    # Mudança obrigatória de senha no primeiro acesso
    path("change-password-required/", core_views.change_password_required, name="change_password_required"),
    
    # Service Worker - rota própria para header Service-Worker-Allowed: /
    path("sw.js", lambda req: FileResponse(
        open(settings.BASE_DIR / "static" / "js" / "sw.js", "rb"),
        content_type="application/javascript; charset=utf-8",
        headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"},
    )),
    
    # Favicon - redireciona para o arquivo estático
    path("favicon.ico", RedirectView.as_view(url=settings.STATIC_URL + "favicon.ico", permanent=True), name="favicon"),
    path(".well-known/bimi/logo.svg", bimi_views.bimi_logo_svg, name="bimi_logo"),
    
    # URLs RM Systems
    path("rm/", include(("core.urls_rm", "rm"), namespace="rm")),
    
    # URLs do verificador (novo app FTTH Viewer)
    path("verificador/", include(("ftth_viewer.urls", "ftth_viewer"), namespace="verificador")),
    
    # URLs de documentação e páginas legais (acessíveis a todos, sem autenticação)
    path("termos-uso/", core_views.termos_uso_view, name="termos_uso"),
    path("politica-privacidade/", core_views.politica_privacidade_view, name="politica_privacidade"),
    path("politica-cookies/", core_views.politica_cookies_view, name="politica_cookies"),
    path("lgpd/", core_views.lgpd_view, name="lgpd"),
    path("faq/", core_views.faq_view, name="faq"),
    path("ajuda/", core_views.ajuda_view, name="ajuda"),
    path("manual/", core_views.manual_usuario_view, name="manual_usuario"),
    
    # URLs específicas por empresa
    re_path(r'^(?P<company_slug>[\w-]+)/', include(("core.urls_company", "company"), namespace="company")),
    
    # Redirect da raiz para RM
    path("", home_redirect, name="home_redirect"),
]

if settings.DEBUG and getattr(settings, "SENTRY_DSN", "").strip():
    urlpatterns.insert(
        3,
        path("sentry-debug/", health_views.sentry_debug, name="sentry_debug"),
    )

# Mídia: dev explícito (DEBUG + SERVE_MEDIA_VIA_DJANGO) OU rotas autenticadas (antes do catch-all)
_media_urlpatterns = []
if getattr(settings, "SERVE_PUBLIC_MEDIA", False):
    _media_urlpatterns = static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
elif getattr(settings, "USE_PROTECTED_MEDIA", True):
    media_prefix = settings.MEDIA_URL.strip("/")
    _media_urlpatterns = [
        path(
            f"{media_prefix}/<path:path>",
            serve_protected_media,
            name="protected_media",
        ),
        path(
            "media-signed/<str:token>/",
            serve_protected_media_signed,
            name="protected_media_signed",
        ),
    ]

urlpatterns = _media_urlpatterns + urlpatterns + [
    re_path(r"^.*$", force_404, name="catch_all_404"),
]
