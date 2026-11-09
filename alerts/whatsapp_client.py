"""Cliente HTTP para o worker MENSAGENS (API WhatsApp multi-linha)."""
from __future__ import annotations

import json
import os
import shutil
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings


def bridge_base_url() -> str:
    return os.getenv(
        "WHATSAPP_BRIDGE_URL",
        getattr(settings, "WHATSAPP_BRIDGE_URL", "http://127.0.0.1:3921"),
    ).rstrip("/")


def bridge_token() -> str:
    return os.getenv("ALERT_BRIDGE_API_TOKEN", "")


def _mensagens_dir() -> Path:
    return Path(getattr(settings, "MENSAGENS_DIR", settings.BASE_DIR / "MENSAGENS"))


def _line_data_dir(company_slug: str, line_id: int | str) -> Path:
    safe_slug = "".join(c for c in company_slug if c.isalnum() or c in "-_")
    safe_id = str(line_id).replace("/", "")
    return _mensagens_dir() / "data" / "whatsapp" / safe_slug / safe_id


def _status_file(company_slug: str, line_id: int | str) -> Path:
    return _line_data_dir(company_slug, line_id) / "status.json"


def _session_path(company_slug: str, line_id: int | str) -> str:
    return f"/whatsapp/{company_slug}/{line_id}"


def _request(method: str, path: str, body: dict | None = None, timeout: float = 15.0):
    url = f"{bridge_base_url()}{path}"
    data = None
    headers = {
        "X-Bridge-Token": bridge_token(),
        "Accept": "application/json",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            if resp.headers.get("Content-Type", "").startswith("image/"):
                return resp.status, raw, resp.headers.get("Content-Type")
            return resp.status, json.loads(raw.decode("utf-8")), "application/json"
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8"))
        except Exception:
            payload = {"error": exc.reason or str(exc)}
        return exc.code, payload, "application/json"
    except urllib.error.URLError as exc:
        return 0, {"error": f"Worker MENSAGENS offline: {exc.reason}", "status": "worker_offline"}, "application/json"


def worker_online() -> bool:
    status, _, _ = _request("GET", "/ping", timeout=2)
    return status == 200


def _read_local_status(company_slug: str, line_id: int | str) -> dict | None:
    path = _status_file(company_slug, line_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        data["worker_reachable"] = False
        data["status_from_cache"] = True
        return data
    except (OSError, json.JSONDecodeError):
        return None


def _write_local_status(company_slug: str, line_id: int | str, patch: dict) -> dict:
    path = _status_file(company_slug, line_id)
    current = _read_local_status(company_slug, line_id) or {
        "session_key": f"{company_slug}/{line_id}",
        "company_slug": company_slug,
        "line_id": str(line_id),
        "status": "disconnected",
        "message": "Desconectado",
    }
    current.update(patch)
    current["updated_at"] = datetime.now(timezone.utc).isoformat()
    for key in ("worker_reachable", "status_from_cache", "has_stale_auth"):
        current.pop(key, None)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")
    return current


def has_local_auth(company_slug: str, line_id: int | str) -> bool:
    auth_dir = _line_data_dir(company_slug, line_id) / "auth_info"
    if not auth_dir.is_dir():
        return False
    try:
        return any(auth_dir.iterdir())
    except OSError:
        return False


def clear_local_session(company_slug: str, line_id: int | str) -> dict:
    """Remove credenciais e QR locais (funciona sem worker Node)."""
    return _disconnect_local(company_slug, line_id, delete_auth=True)


def _disconnect_local(company_slug: str, line_id: int | str, delete_auth: bool = False) -> dict:
    base = _line_data_dir(company_slug, line_id)
    auth_dir = base / "auth_info"
    if delete_auth and auth_dir.is_dir():
        shutil.rmtree(auth_dir, ignore_errors=True)
    for name in ("whatsapp-qr.png", "whatsapp-pairing-code.txt"):
        f = base / name
        if f.is_file():
            f.unlink(missing_ok=True)
    status = _write_local_status(
        company_slug,
        line_id,
        {
            "status": "disconnected",
            "pairing_code": None,
            "message": "Desconectado (worker offline — sessão local limpa)",
        },
    )
    status["ok"] = True
    status["local_disconnect"] = True
    return status


def get_status(company_slug: str, line_id: int | str) -> dict:
    status, data, _ = _request("GET", f"{_session_path(company_slug, line_id)}/", timeout=3)
    if status == 200:
        data["worker_reachable"] = True
        return data
    cached = _read_local_status(company_slug, line_id)
    if cached:
        if cached.get("status") == "qr" and not _qr_png_path(company_slug, line_id).is_file():
            cached = {
                **cached,
                "status": "qr",
                "message": "Gerando QR Code… (inicie o worker com runserver)",
            }
        if has_local_auth(company_slug, line_id) and cached.get("status") == "disconnected":
            cached["has_stale_auth"] = True
            cached["message"] = (
                "Credenciais antigas no disco. Use «Limpar sessão» e depois «Conectar»."
            )
        return cached
    if status == 0:
        data.setdefault("status", "disconnected")
        data.setdefault("message", "Worker MENSAGENS offline")
    data["worker_reachable"] = False
    return data


def list_lines_status(company_slug: str, line_ids: list) -> list:
    out = []
    for lid in line_ids:
        st = get_status(company_slug, lid)
        st["line_id"] = str(lid)
        out.append(st)
    return out


def start_connect(
    company_slug: str,
    line_id: int | str,
    mode: str,
    phone: str = "",
    *,
    label: str = "",
    fresh: bool = True,
) -> dict:
    body = {"mode": mode, "phone": phone, "fresh": fresh}
    if label:
        body["label"] = label
    _, data, _ = _request(
        "POST",
        f"{_session_path(company_slug, line_id)}/connect",
        body,
    )
    return data


def disconnect(company_slug: str, line_id: int | str, delete_auth: bool = False) -> dict:
    status, data, _ = _request(
        "POST",
        f"{_session_path(company_slug, line_id)}/disconnect",
        {"delete_auth": delete_auth},
        timeout=10,
    )
    if status == 200:
        return data
    return _disconnect_local(company_slug, line_id, delete_auth=delete_auth)


def _qr_png_path(company_slug: str, line_id: int | str) -> Path:
    return _line_data_dir(company_slug, line_id) / "whatsapp-qr.png"


def fetch_qr_png(company_slug: str, line_id: int | str):
    status, body, content_type = _request(
        "GET",
        f"{_session_path(company_slug, line_id)}/qr.png",
        timeout=10,
    )
    if status == 200 and body:
        return status, body, content_type
    local = _qr_png_path(company_slug, line_id)
    if local.is_file():
        return 200, local.read_bytes(), "image/png"
    return status or 404, b"", content_type or "image/png"
