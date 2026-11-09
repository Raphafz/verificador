"""
Upload seguro — quarentena, nomes aleatórios, hook antivirus opcional.
"""
from __future__ import annotations

import logging
import os
import secrets
import shutil
import subprocess
from pathlib import Path

from django.conf import settings

logger = logging.getLogger("security")


def quarantine_root() -> Path:
    root = Path(getattr(settings, "UPLOAD_QUARANTINE_DIR", settings.MEDIA_ROOT / "quarantine"))
    root.mkdir(parents=True, exist_ok=True)
    return root


def secure_upload_filename(original_name: str) -> str:
    """Nome de armazenamento aleatório preservando extensão permitida."""
    ext = Path(original_name).suffix.lower()[:10]
    if ext not in {".xlsx", ".xls", ".csv", ".kml", ".kmz"}:
        ext = ".bin"
    return f"{secrets.token_hex(16)}{ext}"


def secure_cto_upload_path(instance, filename: str) -> str:
    company_id = getattr(instance, "company_id", None) or "unknown"
    safe = secure_upload_filename(filename)
    return f"cto_maps/{company_id}/{safe}"


def scan_file_with_clamav(file_path: Path) -> tuple[bool, str]:
    """
    Hook antivirus opcional (ClamAV).
    Retorna (ok, mensagem). Se clamscan ausente, retorna (True, 'skipped').
    """
    if not getattr(settings, "UPLOAD_ANTIVIRUS_ENABLED", False):
        return True, "antivirus_disabled"
    clam = os.getenv("CLAMSCAN_PATH", "clamscan")
    try:
        result = subprocess.run(
            [clam, "--no-summary", str(file_path)],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if result.returncode == 0:
            return True, "clean"
        if result.returncode == 1:
            return False, "infected"
        return False, result.stderr or "scan_error"
    except FileNotFoundError:
        logger.warning("clamscan não encontrado — upload sem varredura AV")
        return True, "clamscan_missing"
    except subprocess.TimeoutExpired:
        return False, "scan_timeout"


def quarantine_file(source_path: Path, reason: str) -> Path:
    dest = quarantine_root() / f"{secrets.token_hex(8)}_{source_path.name}"
    shutil.move(str(source_path), str(dest))
    logger.warning("Arquivo em quarentena: %s motivo=%s", dest.name, reason)
    return dest


def strip_file_metadata(path: Path) -> None:
    """
    Remove metadados opcionais (EXIF em JPEG embutido, docProps em Office Open XML).
    Falha silenciosa — não bloqueia upload.
    """
    suffix = path.suffix.lower()
    try:
        if suffix in (".xlsx", ".xlsm", ".docx"):
            import zipfile
            import tempfile

            with zipfile.ZipFile(path, "r") as zin:
                names = [n for n in zin.namelist() if not n.startswith("docProps/")]
                if len(names) == len(zin.namelist()):
                    return
                tmp = path.with_suffix(path.suffix + ".tmp")
                with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
                    for name in names:
                        zout.writestr(name, zin.read(name))
            tmp.replace(path)
    except Exception as exc:
        logger.debug("strip_file_metadata ignorado: %s", exc)


def process_uploaded_file(file_field, *, original_name: str) -> None:
    """
    Pós-validação: AV opcional. Em infecção, move para quarentena e apaga referência.
    """
    if not file_field or not getattr(file_field, "path", None):
        return
    path = Path(file_field.path)
    if not path.is_file():
        return
    ok, msg = scan_file_with_clamav(path)
    if ok:
        strip_file_metadata(path)
        return
    quarantine_file(path, msg)
    file_field.delete(save=False)
    from django.core.exceptions import ValidationError
    raise ValidationError("Arquivo reprovado na verificação de segurança.")
