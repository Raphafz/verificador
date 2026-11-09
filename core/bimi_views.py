"""Endpoints públicos para BIMI (logo no perfil do remetente no Gmail)."""
from __future__ import annotations

from pathlib import Path

from django.contrib.staticfiles import finders
from django.http import HttpResponse, HttpResponseNotFound


def bimi_logo_svg(request):
    """Logo BIMI em /.well-known/bimi/logo.svg (requer HTTPS em produção)."""
    found = finders.find("well-known/bimi/logo.svg")
    if not found:
        return HttpResponseNotFound("BIMI logo not found")
    content = Path(found).read_bytes()
    response = HttpResponse(content, content_type="image/svg+xml; charset=utf-8")
    response["Cache-Control"] = "public, max-age=86400"
    return response
