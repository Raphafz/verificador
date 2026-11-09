"""
Inicia o worker Node (MENSAGENS) integrado ao Django em desenvolvimento.
"""
from __future__ import annotations

import atexit
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from django.conf import settings


def _env_flag(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "on", "yes")


def should_run_alert_bridge() -> bool:
    if not getattr(settings, "DEBUG", False):
        return False
    return _env_flag("RUN_ALERT_BRIDGE", default=True)


def mensagens_dir() -> Path:
    return Path(getattr(settings, "MENSAGENS_DIR", settings.BASE_DIR / "MENSAGENS"))


def _loopback_host(host: str) -> str:
    """0.0.0.0/:: são válidos para bind do servidor, mas inválidos como cliente HTTP (Windows)."""
    h = (host or "").strip()
    if h in ("0.0.0.0", "::", ""):
        return "127.0.0.1"
    if h.startswith("::ffff:"):
        return h
    return h


def bridge_api_url(host: str, port: int | str) -> str:
    explicit = os.getenv("ALERT_BRIDGE_API_URL", "").strip()
    if explicit:
        return explicit
    return f"http://{_loopback_host(host)}:{port}/api/internal/alert-bridge/configs/"


class AlertBridgeRunner:
    """Processo Node (npm run start:saas) apontando para a API Django."""

    def __init__(self, host: str = "127.0.0.1", port: int | str = 8000):
        self.host = _loopback_host(host)
        self.port = int(port)
        self.process: subprocess.Popen | None = None
        self._log_thread: threading.Thread | None = None
        self._stopped = False
        self._owns_process = False
        self._recent_logs: list[str] = []

    def start_when_server_ready(self, timeout: float = 90.0) -> None:
        if self.process or self._stopped:
            return

        mensagens = mensagens_dir()
        if not mensagens.is_dir():
            print(f"[alert-bridge] Pasta MENSAGENS não encontrada: {mensagens}")
            return

        if not shutil.which("npm"):
            print("[alert-bridge] npm não encontrado no PATH — instale Node.js 18+")
            return

        token = os.getenv("ALERT_BRIDGE_API_TOKEN", "").strip()
        if not token:
            print(
                "[alert-bridge] Defina ALERT_BRIDGE_API_TOKEN no .env "
                "(mesmo valor no Django e no worker)."
            )
            return

        if not (mensagens / "node_modules").is_dir():
            print("[alert-bridge] Instalando dependências (npm install)…")
            subprocess.run(
                ["npm", "install"],
                cwd=mensagens,
                check=False,
                shell=(os.name == "nt"),
            )

        api_url = bridge_api_url(self.host, self.port)
        if not self._wait_for_django(api_url, timeout=timeout):
            print("[alert-bridge] Django não respondeu a tempo — worker não iniciado.")
            return

        bridge_port = os.getenv("WHATSAPP_BRIDGE_PORT", "3921")
        if self._bridge_ping_ok(bridge_port):
            print(
                f"[alert-bridge] API WhatsApp já ativa em http://127.0.0.1:{bridge_port}/ping "
                "— não inicia outro Node (evita EADDRINUSE)."
            )
            print(
                "[alert-bridge] Se algo falhar no painel, feche o runserver, mate o processo "
                f"na porta {bridge_port} e suba de novo."
            )
            return

        env = os.environ.copy()
        env["ALERT_BRIDGE_API_URL"] = api_url
        env["ALERT_BRIDGE_API_TOKEN"] = token
        hmac_secret = os.getenv("BRIDGE_HMAC_SECRET", "").strip() or token
        env["BRIDGE_HMAC_SECRET"] = hmac_secret
        env.setdefault("WHATSAPP_BRIDGE_PORT", bridge_port)
        env.setdefault("PYTHONUNBUFFERED", "1")

        npm = "npm.cmd" if os.name == "nt" else "npm"
        cmd = [npm, "run", "start:saas"]

        print(f"[alert-bridge] Iniciando MENSAGENS (SaaS) → {api_url}")

        self.process = subprocess.Popen(
            cmd,
            cwd=mensagens,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            shell=False,
        )

        self._log_thread = threading.Thread(
            target=self._pipe_logs,
            name="alert-bridge-logs",
            daemon=True,
        )
        self._log_thread.start()
        self._owns_process = True
        atexit.register(self.stop)
        threading.Thread(
            target=self._wait_for_bridge_api,
            name="alert-bridge-health",
            daemon=True,
        ).start()

    def _bridge_ping_ok(self, port: str | int) -> bool:
        ping_url = f"http://127.0.0.1:{port}/ping"
        token = os.getenv("ALERT_BRIDGE_API_TOKEN", "")
        try:
            req = urllib.request.Request(
                ping_url,
                headers={"X-Bridge-Token": token},
            )
            with urllib.request.urlopen(req, timeout=2) as resp:
                return resp.status == 200
        except Exception:
            return False

    def _wait_for_bridge_api(self) -> None:
        port = os.getenv("WHATSAPP_BRIDGE_PORT", "3921")
        ping_url = f"http://127.0.0.1:{port}/ping"
        deadline = time.time() + 45
        while time.time() < deadline:
            if self.process and self.process.poll() is not None:
                print(
                    f"[alert-bridge] Worker encerrou (código {self.process.returncode}). "
                    "Veja erros acima (ex.: EADDRINUSE, SyntaxError)."
                )
                if "EADDRINUSE" in (self._last_log_snippet() or ""):
                    print(
                        f"[alert-bridge] Porta {port} ocupada — encerre o Node antigo "
                        "ou reinicie o PC/terminal."
                    )
                return
            if self._bridge_ping_ok(port):
                print(f"[alert-bridge] API WhatsApp OK em {ping_url}")
                return
            time.sleep(1)
        print(
            f"[alert-bridge] API WhatsApp não respondeu em {ping_url} — "
            "o painel ficará em «worker parado» até o Node subir."
        )

    def _wait_for_django(self, api_url: str, timeout: float) -> bool:
        from core.bridge_security import bridge_request_headers_for_client

        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                req = urllib.request.Request(
                    api_url,
                    headers=bridge_request_headers_for_client(),
                )
                with urllib.request.urlopen(req, timeout=2) as resp:
                    if resp.status in (200, 401):
                        return True
            except urllib.error.HTTPError as exc:
                if exc.code in (200, 401):
                    return True
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                pass
            time.sleep(0.5)
        return False

    def _pipe_logs(self) -> None:
        if not self.process or not self.process.stdout:
            return
        for line in self.process.stdout:
            if self._stopped:
                break
            text = line.rstrip()
            if text:
                self._recent_logs.append(text)
                if len(self._recent_logs) > 30:
                    self._recent_logs.pop(0)
                print(f"[alert-bridge] {text}")

    def _last_log_snippet(self) -> str:
        return "\n".join(getattr(self, "_recent_logs", [])[-8:])

    def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        proc = self.process
        self.process = None
        if not proc or not self._owns_process:
            return
        print("[alert-bridge] Encerrando worker MENSAGENS…")
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
