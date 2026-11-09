"""Ponto de entrada para despacho de jobs OLT (host ou container)."""
from __future__ import annotations

from .dispatcher import start_delete, start_list_offline

__all__ = ["start_delete", "start_list_offline"]
