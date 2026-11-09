"""
Mídia protegida — downloads autenticados com verificação multi-tenant.
Em produção, /media/ não é servido publicamente via static().
"""
from __future__ import annotations

import logging
import mimetypes
from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.signing import BadSignature, TimestampSigner
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.urls import reverse
from django.utils.encoding import smart_str
from django.views.decorators.http import require_GET

from core.models import CTOMapFile

logger = logging.getLogger("security.media")

_SIGNER_SALT = "saas-protected-media-v1"


def _media_root() -> Path:
    return Path(settings.MEDIA_ROOT).resolve()


def _safe_media_path(relative_path: str) -> Path | None:
    """Resolve path sob MEDIA_ROOT; bloqueia path traversal."""
    rel = (relative_path or "").replace("\\", "/").lstrip("/")
    if not rel or ".." in rel.split("/"):
        return None
    root = _media_root()
    target = (root / rel).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return None
    if not target.is_file():
        return None
    return target


def user_can_access_media_path(user, relative_path: str) -> bool:
    if not user.is_authenticated:
        return False
    if getattr(user, "is_rm_admin", False) or user.is_superuser:
        return True
    rel = relative_path.replace("\\", "/").lstrip("/")
    if rel.startswith("cto_maps/"):
        if not user.company_id:
            return False
        parts = rel.split("/")
        if len(parts) >= 2 and str(parts[1]).isdigit():
            if int(parts[1]) != user.company_id:
                return False
        return CTOMapFile.objects.filter(company=user.company).filter(file=rel).exists()
    if rel.startswith("quarantine/"):
        return getattr(user, "is_rm_admin", False) or user.is_superuser
    return False


def sign_media_path(relative_path: str) -> str:
    """Token assinado para URL temporária de mídia."""
    signer = TimestampSigner(salt=_SIGNER_SALT)
    return signer.sign(relative_path.replace("\\", "/").lstrip("/"))


def unsign_media_path(token: str, max_age: int | None = None) -> str | None:
    signer = TimestampSigner(salt=_SIGNER_SALT)
    max_age = max_age if max_age is not None else getattr(settings, "MEDIA_SIGNED_URL_MAX_AGE", 3600)
    try:
        return signer.unsign(token, max_age=max_age)
    except BadSignature:
        return None


def build_signed_media_url(relative_path: str) -> str:
    token = sign_media_path(relative_path)
    return reverse("protected_media_signed", kwargs={"token": token})


@login_required
@require_GET
def serve_protected_media(request, path: str):
    """GET /media/<path> — exige login e permissão por empresa."""
    target = _safe_media_path(path)
    if not target:
        raise Http404()
    if not user_can_access_media_path(request.user, path):
        logger.warning(
            "media_forbidden user=%s path=%s",
            request.user.pk,
            path[:120],
        )
        return HttpResponseForbidden("Acesso negado ao arquivo.")
    content_type, _ = mimetypes.guess_type(str(target))
    response = FileResponse(target.open("rb"), content_type=content_type or "application/octet-stream")
    response["Content-Disposition"] = f'inline; filename="{smart_str(target.name)}"'
    response["X-Content-Type-Options"] = "nosniff"
    return response


@require_GET
def serve_protected_media_signed(request, token: str):
    """GET /media-signed/<token>/ — link temporário (opcional para integrações)."""
    rel = unsign_media_path(token)
    if not rel:
        raise Http404()
    target = _safe_media_path(rel)
    if not target:
        raise Http404()
    if request.user.is_authenticated:
        if not user_can_access_media_path(request.user, rel):
            return HttpResponseForbidden("Acesso negado ao arquivo.")
    elif not getattr(settings, "MEDIA_SIGNED_ALLOW_ANONYMOUS", False):
        return HttpResponseForbidden("Autenticação necessária.")
    content_type, _ = mimetypes.guess_type(str(target))
    return FileResponse(target.open("rb"), content_type=content_type or "application/octet-stream")
