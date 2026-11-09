"""Contexto de branding para e-mails transacionais."""
from __future__ import annotations

import base64
import logging
import mimetypes
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles import finders

logger = logging.getLogger(__name__)

EMAIL_CID_ICON = "rm-email-icon"
EMAIL_CID_LETTREIRO = "rm-email-lettreiro"


def _absolute_url(path_or_url: str, request=None) -> str:
    if not path_or_url:
        return ""
    if path_or_url.startswith(("http://", "https://")):
        return path_or_url

    path = path_or_url if path_or_url.startswith("/") else f"/{path_or_url}"
    if request is not None:
        protocol = "https" if request.is_secure() else "http"
        domain = request.get_host()
    else:
        protocol = "http" if settings.DEBUG else "https"
        domain = getattr(settings, "SITE_DOMAIN", "localhost")
    return f"{protocol}://{domain}{path}"


def _static_relative_path(path_or_url: str) -> str:
    if not path_or_url or path_or_url.startswith(("http://", "https://")):
        return ""
    path = path_or_url.strip()
    if path.startswith("/static/"):
        return path[len("/static/") :]
    if path.startswith("static/"):
        return path[len("static/") :]
    return path.lstrip("/")


def _resolve_static_file(relative_path: str) -> Path | None:
    if not relative_path:
        return None

    found = finders.find(relative_path)
    if found:
        return Path(found)

    candidate = Path(settings.BASE_DIR) / "static" / relative_path
    if candidate.is_file():
        return candidate

    return None


def _embed_static_file(path_or_url: str) -> str:
    relative = _static_relative_path(path_or_url)
    file_path = _resolve_static_file(relative)
    if not file_path:
        logger.warning("Arquivo estático para e-mail não encontrado: %s", path_or_url)
        return ""

    mime, _ = mimetypes.guess_type(str(file_path))
    if not mime:
        mime = "application/octet-stream"

    try:
        encoded = base64.b64encode(file_path.read_bytes()).decode("ascii")
    except OSError:
        logger.exception("Falha ao ler asset de e-mail: %s", file_path)
        return ""

    return f"data:{mime};base64,{encoded}"


def _should_embed_images(request=None) -> bool:
    explicit = getattr(settings, "EMAIL_EMBED_IMAGES", None)
    if explicit is not None:
        return bool(explicit)

    if settings.DEBUG:
        return True

    domain = ""
    if request is not None:
        domain = request.get_host()
    else:
        domain = getattr(settings, "SITE_DOMAIN", "")

    domain_lower = domain.lower()
    return any(token in domain_lower for token in ("127.0.0.1", "localhost", "0.0.0.0"))


def _cid_src(content_id: str) -> str:
    return f"cid:{content_id}"


def _image_src(path_or_url: str, request=None, *, embed: bool) -> str:
    if not path_or_url:
        return ""
    if embed:
        relative = _static_relative_path(path_or_url)
        if _resolve_static_file(relative):
            icon_path = getattr(settings, "EMAIL_ICON_URL", "")
            lettreiro_path = getattr(settings, "EMAIL_LETTREIRO_URL", "")
            if path_or_url == icon_path or relative == _static_relative_path(icon_path):
                return _cid_src(EMAIL_CID_ICON)
            if path_or_url == lettreiro_path or relative == _static_relative_path(
                lettreiro_path
            ):
                return _cid_src(EMAIL_CID_LETTREIRO)
            embedded = _embed_static_file(path_or_url)
            if embedded:
                return embedded
    return _absolute_url(path_or_url, request)


def get_email_inline_attachments() -> list[dict]:
    """Anexos inline (CID) — Gmail não exibe data: URI em <img>."""
    attachments: list[dict] = []
    specs = (
        (
            getattr(settings, "EMAIL_LETTREIRO_URL", ""),
            EMAIL_CID_LETTREIRO,
            "rm-letreiro.png",
        ),
    )
    for path_or_url, content_id, filename in specs:
        relative = _static_relative_path(path_or_url)
        file_path = _resolve_static_file(relative)
        if not file_path:
            logger.warning("Asset inline de e-mail não encontrado: %s", path_or_url)
            continue
        mime, _ = mimetypes.guess_type(str(file_path))
        try:
            raw = file_path.read_bytes()
        except OSError:
            logger.exception("Falha ao ler asset inline de e-mail: %s", file_path)
            continue
        attachments.append(
            {
                "filename": filename,
                "content": list(raw),
                "content_type": mime or "image/png",
                "content_id": content_id,
            }
        )
    return attachments


def get_password_reset_expiry_hours() -> int:
    timeout = getattr(settings, "PASSWORD_RESET_TIMEOUT", 60 * 60 * 24 * 3)
    try:
        return max(1, int(timeout) // 3600)
    except (TypeError, ValueError):
        return 24


def get_email_branding_context(request=None, **extra) -> dict:
    brand_color = getattr(settings, "EMAIL_BRAND_COLOR", "#1D4ED8")
    icon_path = getattr(settings, "EMAIL_ICON_URL", "")
    lettreiro_path = getattr(settings, "EMAIL_LETTREIRO_URL", "")
    logo_path = getattr(settings, "EMAIL_LOGO_URL", "")
    banner_path = getattr(settings, "EMAIL_BANNER_URL", "")
    embed_images = _should_embed_images(request)

    ctx = {
        "brand_name": getattr(settings, "EMAIL_BRAND_NAME", "RM Systems"),
        "product_name": getattr(
            settings, "EMAIL_PRODUCT_NAME", "Verificador de Viabilidade"
        ),
        "support_email": getattr(settings, "EMAIL_SUPPORT_EMAIL", ""),
        "email_icon_src": _image_src(icon_path, request, embed=embed_images),
        "email_lettreiro_src": _image_src(lettreiro_path, request, embed=embed_images),
        "email_logo_url": _absolute_url(logo_path, request),
        "email_banner_url": _absolute_url(banner_path, request),
        "email_logo_src": _image_src(logo_path, request, embed=embed_images),
        "email_banner_src": _image_src(banner_path, request, embed=embed_images),
        "email_images_embedded": embed_images,
        "brand_color": brand_color,
        "brand_color_dark": getattr(settings, "EMAIL_BRAND_COLOR_DARK", "#1e3a8a"),
        "reset_expiry_hours": get_password_reset_expiry_hours(),
    }
    ctx.update(extra)
    return ctx
