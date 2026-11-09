from datetime import timedelta
from pathlib import Path
import os
from urllib.parse import urlparse

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent
MENSAGENS_DIR = BASE_DIR / "MENSAGENS"
WHATSAPP_BRIDGE_URL = os.getenv("WHATSAPP_BRIDGE_URL", "http://127.0.0.1:3921")

# Load environment: .env (dupla, repo privado) + .env.local opcional (override pessoal)
from saas_viabilidade.env_loader import load_project_env

load_project_env(BASE_DIR)

# Fail-safe enterprise: DEBUG, SECRET_KEY, HTTPS, mídia (saas_viabilidade/security_bootstrap.py)
import sys

from saas_viabilidade.security_bootstrap import SecurityBootstrapError, bootstrap_security

try:
    _SEC = bootstrap_security(base_dir=BASE_DIR, argv=sys.argv)
except SecurityBootstrapError as exc:
    raise RuntimeError(str(exc)) from exc

IS_VPS = _SEC.is_vps
IS_PRODUCTION = _SEC.is_production
IS_LOCAL_DEV = _SEC.is_local_dev
DEBUG = _SEC.debug
SECRET_KEY = _SEC.secret_key
SERVE_PUBLIC_MEDIA = _SEC.serve_public_media
USE_PROTECTED_MEDIA = _SEC.use_protected_media
SITE_DOMAIN = os.getenv("SITE_DOMAIN", "rmsys.app")

ALLOWED_HOSTS_ENV = os.getenv("ALLOWED_HOSTS", "")
if ALLOWED_HOSTS_ENV:
    ALLOWED_HOSTS = [h.strip() for h in ALLOWED_HOSTS_ENV.split(",") if h.strip()]
elif IS_VPS:
    raise ValueError(
        "ALLOWED_HOSTS é obrigatório na VPS. Ex.: rmsys.app,www.rmsys.app"
    )
else:
    ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]

if IS_LOCAL_DEV or DEBUG:
    for tunnel_host in (
        ".trycloudflare.com",
        ".loca.lt",
        ".ngrok-free.app",
        ".ngrok.app",
        ".ngrok.io",
    ):
        if tunnel_host not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(tunnel_host)

if "*" in ALLOWED_HOSTS:
    raise ValueError(
        "Wildcard '*' não é permitido em ALLOWED_HOSTS. "
        "Use domínios específicos."
    )

INSTALLED_APPS = [
    # Primeiro na lista = runserver customizado (sobe MENSAGENS) vence o do staticfiles
    "saas_viabilidade.apps.SaasViabilidadeConfig",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_otp",
    "django_otp.plugins.otp_totp",
    "django_otp.plugins.otp_static",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "core",
    "ftth_viewer",
    "alerts",
    "olt_ops",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "core.middleware_request_id.RequestIdMiddleware",
    "core.middleware_csp.CspNonceMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "core.middleware_dev_tunnel.DevTunnelCsrfMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "core.middleware_crlf.CrlfProtectionMiddleware",
    "core.middleware_http_methods.HttpMethodRestrictionMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "core.middleware_mfa.MfaEnforcementMiddleware",
    "core.middleware_session_idle.SessionIdleTimeoutMiddleware",
    "core.middleware_session_registry.SessionRegistryMiddleware",
    "core.middleware_password_change.PasswordChangeMiddleware",
    "core.middleware_consent.ConsentMiddleware",
    "core.middleware_security.SecureCompanyMiddleware",
    "core.middleware_modules.SaasModuleMiddleware",
    "core.middleware_frontend_spa.FrontendSpaRedirectMiddleware",
    "core.middleware_ui_v2.UiV2PreviewMiddleware",
    "core.middleware_rate_limit_global.GlobalRateLimitMiddleware",
    "core.security_headers.SecurityHeadersMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "saas_viabilidade.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.saas_platform",
                "core.context_processors.company_quotas",
                "core.context_processors.security_context",
                "core.context_processors.ui_context",
            ],
        },
    },
]

WSGI_APPLICATION = "saas_viabilidade.wsgi.application"

DATABASE_URL = os.getenv("DATABASE_URL")
DB_CONN_MAX_AGE = int(os.getenv("DB_CONN_MAX_AGE", "0"))

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL não está configurada. Defina a string de conexão (ex.: Neon) no arquivo .env."
    )

# SSL só para PostgreSQL remoto (SQLite e outros backends não usam sslmode)
_is_postgres = DATABASE_URL.startswith(("postgresql://", "postgres://"))
_db_host = (urlparse(DATABASE_URL).hostname or "").lower()
_is_local_db = _db_host in ("localhost", "127.0.0.1", "::1")
requires_ssl = _is_postgres and not _is_local_db

DATABASES = {
    "default": dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=DB_CONN_MAX_AGE,
        ssl_require=requires_ssl,
    )
}
# Falha rápido se PostgreSQL estiver offline (evita migrate “travado”)
if _is_postgres:
    DATABASES["default"].setdefault("OPTIONS", {})
    DATABASES["default"]["OPTIONS"]["connect_timeout"] = int(
        os.getenv("DB_CONNECT_TIMEOUT", "10")
    )

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 14},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# LGPD — versão dos documentos legais (sincronizar com core/lgpd_constants.py)
LEGAL_DOCUMENT_VERSION = os.getenv("LEGAL_DOCUMENT_VERSION", "2026-05-21")
CACHE_RETENTION_DAYS = int(os.getenv("CACHE_RETENTION_DAYS", "90"))
GEOCODING_CACHE_TTL_HOURS = int(os.getenv("GEOCODING_CACHE_TTL_HOURS", "24"))
GEOCODING_CACHE_SALT = os.getenv("GEOCODING_CACHE_SALT", "")
DPO_EMAIL = os.getenv("DPO_EMAIL", "privacidade@rmsys.com.br")
ACCOUNT_ACTIVATION_EXPIRY_MINUTES = int(os.getenv("ACCOUNT_ACTIVATION_EXPIRY_MINUTES", "30"))

# Segurança enterprise (Fase 2)
# CSP strict-dynamic desliga allowlist de host em script-src; em dev/tunel relaxar por padrao
_default_csp_strict = "False" if IS_LOCAL_DEV else "True"
CSP_STRICT = os.getenv("CSP_STRICT", _default_csp_strict).lower() in ("1", "true", "yes", "on")
HIDE_SERVER_HEADER = os.getenv("HIDE_SERVER_HEADER", "True").lower() in ("1", "true", "yes", "on")
CSP_IMG_EXTRA_HOSTS = os.getenv("CSP_IMG_EXTRA_HOSTS", "")
_extra_http_methods = os.getenv("DISALLOWED_HTTP_METHODS", "")
DISALLOWED_HTTP_METHODS = [m.strip().upper() for m in _extra_http_methods.split(",") if m.strip()]
TRUST_X_FORWARDED_FOR = os.getenv("TRUST_X_FORWARDED_FOR", "False").lower() in (
    "1", "true", "yes", "on",
)
CNPJ_HASH_SALT = os.getenv("CNPJ_HASH_SALT", "")
FIELD_ENCRYPTION_KEY = os.getenv("FIELD_ENCRYPTION_KEY", "")
FTTH_SEARCH_HISTORY_ENABLED = os.getenv("FTTH_SEARCH_HISTORY_ENABLED", "True").lower() in (
    "1", "true", "yes", "on",
)
FTTH_SEARCH_HISTORY_MAX_ITEMS = int(os.getenv("FTTH_SEARCH_HISTORY_MAX_ITEMS", "8"))
FTTH_SEARCH_HISTORY_TTL_MINUTES = int(os.getenv("FTTH_SEARCH_HISTORY_TTL_MINUTES", "30"))
# UI v2 — overhaul visual premium (Fase 2). Ativar: UI_V2=true ou ?v2=1 (cookie 30d)
UI_V2 = os.getenv("UI_V2", "False").lower() in ("1", "true", "yes", "on")
UI_V2_COOKIE = os.getenv("UI_V2_COOKIE", "rm-ui-v2")
UI_V2_PREVIEW_COOKIE = os.getenv("UI_V2_PREVIEW_COOKIE", "True").lower() in ("1", "true", "yes", "on")
# MFA — em DEBUG fica desligado por padrao (dev/tunel local). Producao: MFA_REQUIRED=true no .env
if DEBUG:
    MFA_REQUIRED = False
    MFA_REQUIRED_COMPANY_ADMINS = False
else:
    MFA_REQUIRED = os.getenv("MFA_REQUIRED", "True").lower() in ("1", "true", "yes", "on")
    MFA_REQUIRED_COMPANY_ADMINS = os.getenv("MFA_REQUIRED_COMPANY_ADMINS", "False").lower() in (
        "1", "true", "yes", "on",
    )
MFA_REMEMBER_DAYS = int(os.getenv("MFA_REMEMBER_DAYS", "30"))
SESSION_MAX_CONCURRENT = int(os.getenv("SESSION_MAX_CONCURRENT", "3"))
# Novo login revoga sessões anteriores (outro PC / outro IP) — padrão ativo
SESSION_REVOKE_ON_NEW_LOGIN = os.getenv("SESSION_REVOKE_ON_NEW_LOGIN", "True").lower() in (
    "1",
    "true",
    "yes",
    "on",
)
# Encerra sessão se o IP mudar durante o uso (desligado em dev/túnel por padrão)
_default_bind_ip = "False" if IS_LOCAL_DEV else "True"
SESSION_BIND_IP = os.getenv("SESSION_BIND_IP", _default_bind_ip).lower() in ("1", "true", "yes", "on")
FORCE_RATE_LIMIT = os.getenv("FORCE_RATE_LIMIT", "").lower() in ("1", "true", "yes", "on")
_health_ips = os.getenv("HEALTH_SECURITY_ALLOWED_IPS", "").strip()
HEALTH_SECURITY_ALLOWED_IPS = tuple(
    ip.strip() for ip in _health_ips.split(",") if ip.strip()
)

REDIS_URL = os.getenv("REDIS_URL", "").strip()
USE_REDIS_CACHE = os.getenv(
    "USE_REDIS_CACHE",
    "True" if (IS_PRODUCTION and REDIS_URL) else "False",
).lower() in ("1", "true", "yes", "on")
if REDIS_URL and USE_REDIS_CACHE:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
            "KEY_PREFIX": "saas_viabilidade",
            "TIMEOUT": 300,
        }
    }

# Fase 3 — retenção LGPD, uploads, auditoria
AUDIT_RETENTION_DAYS = int(os.getenv("AUDIT_RETENTION_DAYS", "365"))
ACTIVATION_TOKEN_RETENTION_DAYS = int(os.getenv("ACTIVATION_TOKEN_RETENTION_DAYS", "7"))
CONSENT_RETENTION_DAYS = int(os.getenv("CONSENT_RETENTION_DAYS", "1825"))
DSR_RETENTION_DAYS = int(os.getenv("DSR_RETENTION_DAYS", "1825"))
TICKET_RETENTION_DAYS = int(os.getenv("TICKET_RETENTION_DAYS", "730"))
DSR_PENDING_MAX_DAYS = int(os.getenv("DSR_PENDING_MAX_DAYS", "30"))
DSR_MAX_RETRIES = int(os.getenv("DSR_MAX_RETRIES", "3"))
LGPD_EXPORT_TTL_HOURS = int(os.getenv("LGPD_EXPORT_TTL_HOURS", "24"))
LGPD_EXPORT_MAX_DOWNLOADS = int(os.getenv("LGPD_EXPORT_MAX_DOWNLOADS", "5"))
UPLOAD_QUARANTINE_DIR = os.getenv("UPLOAD_QUARANTINE_DIR", "")
UPLOAD_ANTIVIRUS_ENABLED = os.getenv("UPLOAD_ANTIVIRUS_ENABLED", "False").lower() in (
    "1", "true", "yes", "on",
)
ENV_VALIDATION_STRICT = os.getenv("ENV_VALIDATION_STRICT", "False" if DEBUG else "True").lower() in (
    "1", "true", "yes", "on",
)

FRONTEND_MODE = os.getenv("FRONTEND_MODE", "hybrid")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")

_cors_origins = os.getenv("CORS_ALLOWED_ORIGINS", FRONTEND_URL)
CORS_ALLOWED_ORIGINS = [o.strip() for o in _cors_origins.split(",") if o.strip()]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "x-company-slug",
]

# CSP: origens extras para connect-src (SPA em dev/prod)
_csp_connect = os.getenv("CSP_CONNECT_EXTRA_HOSTS", _cors_origins)
CSP_CONNECT_EXTRA_HOSTS = _csp_connect

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.getenv("JWT_ACCESS_MINUTES", "15"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.getenv("JWT_REFRESH_DAYS", "7"))),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
        "core.api_permissions.RequireMfaVerified",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "core.throttling.AnonBurstThrottle",
        "core.throttling.BurstUserThrottle",
        "core.throttling.SustainedUserThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "burst": os.getenv("DRF_THROTTLE_BURST", "60/min"),
        "sustained": os.getenv("DRF_THROTTLE_SUSTAINED", "2000/hour"),
        "anon_burst": os.getenv("DRF_THROTTLE_ANON", "30/min"),
    },
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "core.drf_exception_handler.safe_drf_exception_handler",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "RM Systems API",
    "DESCRIPTION": "API REST v1 — JWT (SPA) + sessão Django (/admin/).",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}
# Mídia: em produção sempre protegida; dev pode usar SERVE_MEDIA_VIA_DJANGO=true (explícito)
SERVE_MEDIA_VIA_DJANGO = os.getenv("SERVE_MEDIA_VIA_DJANGO", "False").lower() in (
    "1", "true", "on", "yes",
)
MEDIA_SIGNED_URL_MAX_AGE = int(os.getenv("MEDIA_SIGNED_URL_MAX_AGE", "3600"))
MEDIA_SIGNED_ALLOW_ANONYMOUS = os.getenv("MEDIA_SIGNED_ALLOW_ANONYMOUS", "False").lower() in (
    "1", "true", "on", "yes",
)

# OLT — logs operacionais sanitizados
OLT_LOG_MAX_CHARS = int(os.getenv("OLT_LOG_MAX_CHARS", "200000"))
OLT_LOG_RETENTION_DAYS = int(os.getenv("OLT_LOG_RETENTION_DAYS", "7"))

# Bridge — HMAC obrigatório em produção (BRIDGE_REQUIRE_HMAC=true)
BRIDGE_REQUIRE_HMAC = os.getenv(
    "BRIDGE_REQUIRE_HMAC",
    "True" if IS_PRODUCTION else "False",
).lower() in ("1", "true", "on", "yes")

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [
    BASE_DIR / "static",
]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Configurações adicionais para arquivos estáticos
STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
]

# Configuração do WhiteNoise para servir arquivos estáticos
# WhiteNoise permite que o Django sirva arquivos estáticos diretamente
# Usar WhiteNoise sempre, mas com configurações diferentes para dev/prod
# Em dev, storage sem manifest evita 500 em arquivos não coletados
if DEBUG:
    STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"
else:
    STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
WHITENOISE_MAX_AGE = 31536000 if not DEBUG else 0  # Cache de 1 ano em produção, sem cache em dev
WHITENOISE_USE_FINDERS = DEBUG  # Em dev, usar finders para arquivos não coletados
WHITENOISE_AUTOREFRESH = DEBUG  # Em dev, recarregar automaticamente
MEDIA_URL = "/media/"

# Mídia: VPS Hostinger (persistente) ou pasta local em desenvolvimento
VPS_MEDIA_ROOT = os.getenv("VPS_MEDIA_ROOT", "/var/www/saas-viabilidade/media")

if IS_VPS:
    MEDIA_ROOT = Path(VPS_MEDIA_ROOT)
else:
    MEDIA_ROOT = BASE_DIR / "media"
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

LOGIN_REDIRECT_URL = "/dashboard/"  # Usa dashboard_redirect que redireciona corretamente conforme papel do usuário
LOGOUT_REDIRECT_URL = "/rm/login/"
LOGIN_URL = "/rm/login/"

# Custom User Model
AUTH_USER_MODEL = 'core.CustomUser'

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Configurações de email
EMAIL_BACKEND = os.getenv(
    'EMAIL_BACKEND',
    'core.email.resend_backend.ResendEmailBackend'
    if os.getenv('RESEND_API_KEY')
    else (
        'django.core.mail.backends.console.EmailBackend' if DEBUG
        else 'django.core.mail.backends.smtp.EmailBackend'
    ),
)
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() in ('1', 'true', 'on', 'yes')
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'onboarding@resend.dev')
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# Resend (https://resend.com) — e-mail transacional
RESEND_API_KEY = os.getenv('RESEND_API_KEY', '')

# Branding de e-mails transacionais
EMAIL_BRAND_NAME = os.getenv('EMAIL_BRAND_NAME', 'RM Systems')
EMAIL_PRODUCT_NAME = os.getenv('EMAIL_PRODUCT_NAME', 'Verificador de Viabilidade')
EMAIL_BRAND_COLOR = os.getenv('EMAIL_BRAND_COLOR', '#1D4ED8')
EMAIL_BRAND_COLOR_DARK = os.getenv('EMAIL_BRAND_COLOR_DARK', '#1e3a8a')
EMAIL_SUPPORT_EMAIL = os.getenv("EMAIL_SUPPORT_EMAIL", "suporte@rmsys.com.br")
# URLs absolutas ou caminhos /static/... (ex.: /static/email/icon-email.png)
EMAIL_ICON_URL = os.getenv('EMAIL_ICON_URL', '/static/email/icon-email.png')
EMAIL_LETTREIRO_URL = os.getenv('EMAIL_LETTREIRO_URL', '/static/email/letreiro-email.png')
EMAIL_LOGO_URL = os.getenv('EMAIL_LOGO_URL', '')
EMAIL_BANNER_URL = os.getenv('EMAIL_BANNER_URL', '')
# Incorpora logo/banner no HTML (base64) quando localhost/DEBUG — Gmail não abre 127.0.0.1
EMAIL_EMBED_IMAGES = os.getenv('EMAIL_EMBED_IMAGES', '').lower() in ('1', 'true', 'yes', 'on') if os.getenv('EMAIL_EMBED_IMAGES') else None

# Site ID para emails (necessário para password reset)
SITE_ID = 1

# CSRF and cookie security
CSRF_TRUSTED_ORIGINS_ENV = os.getenv("CSRF_TRUSTED_ORIGINS", "")
CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in CSRF_TRUSTED_ORIGINS_ENV.split(",")
    if o.strip()
    and o.strip() != "*"
    and (o.strip().startswith("http://") or o.strip().startswith("https://"))
]

# Adicionar origens CSRF a partir de ALLOWED_HOSTS
for host in ALLOWED_HOSTS:
    if host and host != '*' and not host.startswith('*.'):
        # Adicionar com e sem www
        origin = f"https://{host}"
        if origin not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(origin)
        origin_http = f"http://{host}"
        if origin_http not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(origin_http)
        if not host.startswith('www.'):
            origin_www = f"https://www.{host}"
            if origin_www not in CSRF_TRUSTED_ORIGINS:
                CSRF_TRUSTED_ORIGINS.append(origin_www)

# Se ainda estiver vazio, adicionar padrões de desenvolvimento
if not CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS = [
        "https://127.0.0.1:8000",
        "https://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ]

# Configurações de sessão - Segurança aprimorada (Fase 3)
SESSION_COOKIE_AGE = int(os.getenv("SESSION_COOKIE_AGE", "3600"))
SESSION_IDLE_TIMEOUT = int(os.getenv("SESSION_IDLE_TIMEOUT", "1800"))
SESSION_COOKIE_SECURE = _SEC.session_cookie_secure
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict" if IS_PRODUCTION else "Lax"
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "saas_sessionid")

# CSRF: produção SEMPRE HttpOnly; dev pode usar CSRF_COOKIE_HTTPONLY=true se necessário (JS)
CSRF_COOKIE_SECURE = _SEC.csrf_cookie_secure
CSRF_COOKIE_HTTPONLY = _SEC.csrf_cookie_httponly
CSRF_COOKIE_SAMESITE = "Strict" if IS_PRODUCTION else "Lax"
CSRF_USE_SESSIONS = False
CSRF_FAILURE_VIEW = "core.error_views.custom_403"

# Túnel dev (HTTPS) — browser rejeita cookie sem Secure
if IS_LOCAL_DEV or DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# HTTPS obrigatório em produção (Nginx: X-Forwarded-Proto)
SECURE_SSL_REDIRECT = _SEC.secure_ssl_redirect
if IS_PRODUCTION:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True
    SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = os.getenv("SECURE_HSTS_PRELOAD", "True").lower() in (
        "1", "true", "on", "yes",
    )
else:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if IS_LOCAL_DEV else None
    USE_X_FORWARDED_HOST = IS_LOCAL_DEV or os.getenv("USE_X_FORWARDED_HOST", "False").lower() in (
        "1", "true", "on", "yes",
    )
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin" if IS_PRODUCTION else "same-origin"
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"

# URLs tolerantes à ausência de barra final
APPEND_SLASH = True

# Configurações de tratamento de erros
handler404 = 'core.error_views.custom_404'
handler500 = 'core.error_views.custom_500'
handler403 = 'core.error_views.custom_403'
handler400 = 'core.error_views.custom_400'

# Propagar exceções apenas em modo debug
DEBUG_PROPAGATE_EXCEPTIONS = DEBUG

# Desabilitar debug toolbar e outras ferramentas de debug que podem interferir
INTERNAL_IPS = []

# ===== CONFIGURAÇÕES FTTH VERIFICADOR =====
# Baseado no Verificador-De-Viabilidade-main

# Diretórios de mapas (criados automaticamente se não existirem)
FTTH_MAPAS_ROOT = BASE_DIR / 'Mapas'
FTTH_KML_DIR = FTTH_MAPAS_ROOT / 'kml'
FTTH_KMZ_DIR = FTTH_MAPAS_ROOT / 'kmz'
FTTH_CSV_DIR = FTTH_MAPAS_ROOT / 'csv'
FTTH_XLS_DIR = FTTH_MAPAS_ROOT / 'xls'
FTTH_XLSX_DIR = FTTH_MAPAS_ROOT / 'xlsx'

# Configurações de roteamento
ROUTING_TIMEOUT = int(os.getenv('ROUTING_TIMEOUT', '15'))  # Timeout em segundos
ENABLE_ROUTE_CACHE = True
MAX_CACHE_SIZE = 1000

# Configurações de viabilidade (distâncias em metros)
FTTH_VIABILIDADE_CONFIG = {
    'viavel': int(os.getenv('VIABILIDADE_VIABLE', '300')),      # Até 300m = Viável
    'limitada': int(os.getenv('VIABILIDADE_LIMITADA', '800')),  # 300-800m = Viabilidade Limitada  
    'inviavel': int(os.getenv('VIABILIDADE_INVIAVEL', '800'))   # Acima de 800m = Sem Viabilidade
}

# OpenRouteService API Key (opcional - para melhor qualidade de roteamento)
OPENROUTESERVICE_API_KEY = os.getenv('OPENROUTESERVICE_API_KEY', '')

# OLT / VPN (OpenVPN no servidor Django — caminho opcional do openvpn.exe / binário)
OLT_OPENVPN_BINARY = os.getenv('OLT_OPENVPN_BINARY', '')
OLT_VPN_CONNECT_TIMEOUT = int(os.getenv('OLT_VPN_CONNECT_TIMEOUT', '90'))
# Segundos após L2TP/OpenVPN antes de testar TCP na OLT (rota Windows pode demorar)
OLT_VPN_POST_CONNECT_DELAY = float(os.getenv('OLT_VPN_POST_CONNECT_DELAY', '8'))

# OLT worker — execução isolada em container Docker (multi-tenant VPN)
OLT_EXECUTION_MODE = os.getenv('OLT_EXECUTION_MODE', 'host').strip().lower()
if OLT_EXECUTION_MODE not in ('host', 'container'):
    raise ValueError("OLT_EXECUTION_MODE deve ser 'host' ou 'container'")
OLT_WORKER_IMAGE = os.getenv('OLT_WORKER_IMAGE', 'rmsys/olt-worker:latest')
OLT_DOCKER_BINARY = os.getenv('OLT_DOCKER_BINARY', 'docker')
OLT_MAX_PARALLEL_JOBS = int(os.getenv('OLT_MAX_PARALLEL_JOBS', '5'))
QUOTA_ENFORCEMENT_ENABLED = os.getenv('QUOTA_ENFORCEMENT_ENABLED', 'true').lower() in (
    '1', 'true', 'yes', 'on',
)
# Cobrança recorrente (Asaas)
ASAAS_API_KEY = os.getenv('ASAAS_API_KEY', '').strip()
ASAAS_WEBHOOK_TOKEN = os.getenv('ASAAS_WEBHOOK_TOKEN', '').strip()
# Monitoramento alert-bridge (minutos sem poll = worker offline)
BRIDGE_STALE_MINUTES = int(os.getenv('BRIDGE_STALE_MINUTES', '5'))
OLT_CONTAINER_JOB_TIMEOUT = int(os.getenv('OLT_CONTAINER_JOB_TIMEOUT', '3600'))
OLT_DOCKER_RUN_ARGS = os.getenv('OLT_DOCKER_RUN_ARGS', '')
OLT_WORKER_ENV_KEYS = (
    'DATABASE_URL',
    'DB_CONN_MAX_AGE',
    'DB_CONNECT_TIMEOUT',
    'SECRET_KEY',
    'FIELD_ENCRYPTION_KEY',
    'DJANGO_ENV',
    'DEBUG',
    'OLT_OPENVPN_BINARY',
    'OLT_VPN_CONNECT_TIMEOUT',
    'OLT_VPN_POST_CONNECT_DELAY',
    'OLT_LOG_MAX_CHARS',
    'REDIS_URL',
    'USE_REDIS_CACHE',
)

# Criar diretórios de mapas se não existirem (apenas se não for test)
import sys

if UPLOAD_QUARANTINE_DIR:
    Path(UPLOAD_QUARANTINE_DIR).mkdir(parents=True, exist_ok=True)
else:
    (MEDIA_ROOT / "quarantine").mkdir(parents=True, exist_ok=True)

if "test" not in sys.argv:
    for directory in [FTTH_MAPAS_ROOT, FTTH_KML_DIR, FTTH_KMZ_DIR, FTTH_CSV_DIR, FTTH_XLS_DIR, FTTH_XLSX_DIR]:
        directory.mkdir(parents=True, exist_ok=True)

# Logging estruturado (substitui prints de config sensíveis)
from saas_viabilidade.logging_config import build_logging_config, log_startup_summary

LOGGING = build_logging_config(BASE_DIR, debug=DEBUG)
log_startup_summary(
    debug=DEBUG,
    is_vps=IS_VPS,
    allowed_hosts=ALLOWED_HOSTS,
    csrf_count=len(CSRF_TRUSTED_ORIGINS),
)
if IS_PRODUCTION:
    import logging

    logging.getLogger("security").info(
        "Produção: ssl_redirect=%s csrf_httponly=%s protected_media=%s",
        SECURE_SSL_REDIRECT,
        CSRF_COOKIE_HTTPONLY,
        USE_PROTECTED_MEDIA,
    )

# Validação de ambiente (produção)
from saas_viabilidade.env_validation import apply_environment_validation

if "test" not in sys.argv:
    apply_environment_validation(
        debug=DEBUG,
        is_vps=IS_VPS,
        secret_key=SECRET_KEY,
        strict=ENV_VALIDATION_STRICT or IS_PRODUCTION,
    )

# Sentry (opcional — SENTRY_DSN no .env)
SENTRY_DSN = os.getenv("SENTRY_DSN", "").strip()

if "test" not in sys.argv and SENTRY_DSN:
    from saas_viabilidade.sentry_bootstrap import init_sentry

    _sentry_env = "production" if IS_PRODUCTION else "development"
    init_sentry(debug=DEBUG, environment=_sentry_env)