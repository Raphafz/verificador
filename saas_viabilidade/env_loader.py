"""Carrega .env compartilhado (dupla) e .env.local opcional (override pessoal)."""
from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv


def load_project_env(base_dir: Path) -> None:
    load_dotenv(base_dir / ".env")
    local_path = base_dir / ".env.local"
    if local_path.is_file():
        load_dotenv(local_path, override=True)
