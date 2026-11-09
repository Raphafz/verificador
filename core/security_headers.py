from django.conf import settings
from django.utils.deprecation import MiddlewareMixin
import logging

logger = logging.getLogger("security")

OSM_IMG = (
    "https://tile.openstreetmap.org "
    "https://a.tile.openstreetmap.org "
    "https://b.tile.openstreetmap.org "
    "https://c.tile.openstreetmap.org "
    "https://*.basemaps.cartocdn.com"
)
OSM_CONNECT = (
    "https://tile.openstreetmap.org "
    "https://a.tile.openstreetmap.org "
    "https://b.tile.openstreetmap.org "
    "https://c.tile.openstreetmap.org "
    "https://*.basemaps.cartocdn.com "
    "https://nominatim.openstreetmap.org"
)
# Google Fonts (opcional — migrar para self-hosted se quiser CSP ainda mais restrita)
STYLE_CDN = "https://fonts.googleapis.com https://fonts.gstatic.com"
FONT_SRC_EXTRA = "https://fonts.gstatic.com https://fonts.googleapis.com"
EXTERNAL_API_CONNECT = (
    "https://router.project-osrm.org https://viacep.com.br https://brasilapi.com.br"
)


def _extra_csp_hosts(setting_name: str) -> str:
    raw = getattr(settings, setting_name, "") or ""
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return " ".join(parts)


def _is_ftth_viewer_request(request) -> bool:
    path = getattr(request, "path", "") or ""
    return "/verificador" in path


def _is_olt_request(request) -> bool:
    path = getattr(request, "path", "") or ""
    return "/olt/" in path


def _allows_inline_style_attr(request) -> bool:
    return _is_ftth_viewer_request(request) or _is_olt_request(request)


def _request_public_origin(request) -> str:
    """Origem pública para CSP — respeita túnel (X-Forwarded-Host/Proto)."""
    forwarded_host = (request.headers.get("X-Forwarded-Host") or "").split(",")[0].strip()
    host = forwarded_host or request.get_host()
    host_without_port = host.split(":")[0]
    proto = (request.headers.get("X-Forwarded-Proto") or "").split(",")[0].strip()
    if not proto:
        proto = "https" if request.is_secure() else "http"
    return f"{proto}://{host_without_port}"


def build_content_security_policy(request) -> str:
    origin = _request_public_origin(request)
    host_without_port = origin.split("://", 1)[-1]
    nonce = getattr(request, "csp_nonce", "") or ""
    strict = getattr(settings, "CSP_STRICT", True)

    img_extra = _extra_csp_hosts("CSP_IMG_EXTRA_HOSTS")
    img_hosts = OSM_IMG
    if img_extra:
        img_hosts = f"{img_hosts} {img_extra}"

    if strict and nonce:
        script_src = f"'self' 'nonce-{nonce}' 'strict-dynamic' {origin}"
        script_src_elem = f"'self' {origin} 'nonce-{nonce}'"
        style_src = f"'self' 'nonce-{nonce}' {origin} {STYLE_CDN}"
        # Leaflet aplica estilos via element.style — exige unsafe-inline no mapa FTTH
        style_src_attr = (
            "'unsafe-inline' 'unsafe-hashes'"
            if _allows_inline_style_attr(request)
            else "'unsafe-hashes'"
        )
        img_src = f"'self' data: blob: {origin} {img_hosts}"
        font_src = f"'self' {origin} {FONT_SRC_EXTRA}"
    elif nonce:
        script_src = f"'self' 'nonce-{nonce}' {origin}"
        script_src_elem = f"'self' {origin} 'nonce-{nonce}'"
        style_src = f"'self' 'nonce-{nonce}' {origin} {STYLE_CDN}"
        style_src_attr = (
            "'unsafe-inline' 'unsafe-hashes'"
            if _allows_inline_style_attr(request)
            else "'unsafe-hashes'"
        )
        img_src = f"'self' data: blob: {origin} {img_hosts}"
        font_src = f"'self' data: blob: {origin} {FONT_SRC_EXTRA}"
    else:
        script_src = f"'self' {origin}"
        script_src_elem = f"'self' {origin}"
        style_src = f"'self' {origin} {STYLE_CDN}"
        style_src_attr = "'unsafe-hashes'"
        img_src = f"'self' data: blob: {origin} {img_hosts}"
        font_src = f"'self' data: blob: {origin} {FONT_SRC_EXTRA}"

    policy = (
        f"default-src 'self' {origin}; "
        f"script-src {script_src}; "
        f"script-src-elem {script_src_elem}; "
        f"style-src {style_src}; "
        f"style-src-attr {style_src_attr}; "
        f"font-src {font_src}; "
        f"img-src {img_src}; "
        f"connect-src 'self' {origin} {_extra_csp_hosts('CSP_CONNECT_EXTRA_HOSTS')} "
        f"{EXTERNAL_API_CONNECT} https://www.gstatic.com {OSM_CONNECT} {FONT_SRC_EXTRA}; "
        f"worker-src 'self' {origin} blob:; "
        f"manifest-src 'self' {origin}; "
        f"frame-ancestors 'none'; "
        f"base-uri 'self'; "
        f"form-action 'self'; "
        f"object-src 'none'; "
        f"media-src 'self' {origin}"
    )
    if request.is_secure() or (request.headers.get("X-Forwarded-Proto") or "").startswith("https"):
        policy += "; upgrade-insecure-requests"
    return policy


class SecurityHeadersMiddleware(MiddlewareMixin):
    """Headers OWASP + CSP nonce."""

    def process_response(self, request, response):
        sw_paths = ["/sw.js", "/service-worker.js", "static/js/sw.js", "staticfiles/js/sw.js"]
        is_service_worker = any(
            request.path.endswith(p) or p in request.path
            or (request.path.startswith("/static/") and "sw.js" in request.path)
            for p in sw_paths
        )

        if is_service_worker:
            response["Content-Type"] = "application/javascript; charset=utf-8"
            response["Service-Worker-Allowed"] = "/"
            response["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response["Pragma"] = "no-cache"
            response["Expires"] = "0"

        if request.path.endswith("/manifest.json"):
            response["Content-Type"] = "application/manifest+json; charset=utf-8"

        response["Content-Security-Policy"] = build_content_security_policy(request)
        response["X-Content-Type-Options"] = "nosniff"
        response["X-Frame-Options"] = "DENY"
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response["X-DNS-Prefetch-Control"] = "off"
        response["Permissions-Policy"] = (
            "accelerometer=(), autoplay=(), camera=(), display-capture=(), "
            "encrypted-media=(), fullscreen=(self), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), midi=(), payment=(), picture-in-picture=(), "
            "publickey-credentials-get=(), screen-wake-lock=(), usb=(), web-share=(), "
            "xr-spatial-tracking=()"
        )
        response["Origin-Agent-Cluster"] = "?1"
        response["Cross-Origin-Opener-Policy"] = "same-origin"
        response["Cross-Origin-Resource-Policy"] = "same-site"
        response["Cross-Origin-Embedder-Policy"] = "credentialless"

        if request.is_secure():
            response["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

        if getattr(settings, "HIDE_SERVER_HEADER", True):
            response.headers.pop("Server", None)

        if request.path.startswith("/admin/") or request.path.startswith("/rm/"):
            response["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response["Pragma"] = "no-cache"
            response["Expires"] = "0"

        return response
