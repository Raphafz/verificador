"""Sessão SSH/Telnet com OLT Huawei/ZTE."""
from __future__ import annotations

import inspect
import re
import socket
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

# Paginação Huawei/ZTE (-- More --, ---- More ----, etc.)
_MORE_PROMPT_RE = re.compile(
    r"(----\s*more|--+more--|press\s+['\"]?(q|any)['\"]?\s+to\s+(break|continue))",
    re.I,
)
# Rajadas de espaço ao ver ---- More ---- (equivalente a Enter + ~6 espaços no PuTTY)
_BURST_SPACES = 8
_MAX_PAGER_BURSTS = 24

if TYPE_CHECKING:
    from .models import OltEquipment

try:
    import paramiko
    from paramiko import RSAKey
    from paramiko.ssh_exception import (
        AuthenticationException,
        IncompatiblePeer,
        SSHException,
    )
except ImportError:
    paramiko = None
    RSAKey = None  # type: ignore[misc, assignment]
    IncompatiblePeer = Exception  # type: ignore[misc, assignment]
    AuthenticationException = SSHException = Exception  # type: ignore[misc, assignment]

_PARAMIKO_SSH_RSA_PATCHED = False


def _ensure_paramiko_ssh_rsa_support() -> None:
    """
    Paramiko 5 removeu ssh-rsa de Transport._key_info; OLTs Huawei/ZTE anunciam
    apenas essa chave de host (erro: no acceptable host key).
    """
    global _PARAMIKO_SSH_RSA_PATCHED
    if _PARAMIKO_SSH_RSA_PATCHED or paramiko is None or RSAKey is None:
        return
    key_info = paramiko.Transport._key_info
    if "ssh-rsa" not in key_info:
        paramiko.Transport._key_info = {"ssh-rsa": RSAKey, **key_info}
    _PARAMIKO_SSH_RSA_PATCHED = True


_ensure_paramiko_ssh_rsa_support()


def _apply_legacy_olt_ssh_algorithms(transport) -> None:
    """
    Huawei MA5800 / ZTE: priorizar rsa-sha2-* (Paramiko 5 falha ao verificar assinatura
    ssh-rsa legada SHA-1). Mantém ssh-rsa só como fallback.
    """
    sec = transport.get_security_options()
    _ensure_paramiko_ssh_rsa_support()
    available = set(transport._key_info.keys())
    host_keys = tuple(
        k
        for k in ("rsa-sha2-512", "rsa-sha2-256", "ssh-rsa")
        if k in available
    )
    if host_keys:
        sec.key_types = host_keys
    prefer_kex = (
        "diffie-hellman-group-exchange-sha256",
        "diffie-hellman-group14-sha256",
        "diffie-hellman-group16-sha512",
        "diffie-hellman-group14-sha1",
        "diffie-hellman-group-exchange-sha1",
        "diffie-hellman-group1-sha1",
        "ecdh-sha2-nistp256",
    )
    allowed_kex = set(sec.kex)
    kex = tuple(k for k in prefer_kex if k in allowed_kex)
    if kex:
        sec.kex = kex


def _olt_transport_factory(sock: socket.socket, *, disabled_algorithms=None):
    """Transport compatível com OLT legada (ssh-rsa + KEX antigos)."""
    kw: dict = {}
    params = inspect.signature(paramiko.Transport.__init__).parameters
    if "strict_kex" in params:
        kw["strict_kex"] = False
    transport = paramiko.Transport(sock, disabled_algorithms=disabled_algorithms, **kw)
    _apply_legacy_olt_ssh_algorithms(transport)
    return transport


def _ssh_try_password(transport: paramiko.Transport, username: str, password: str) -> bool:
    try:
        transport.auth_password(username, password)
        return transport.is_authenticated()
    except (AuthenticationException, SSHException, EOFError):
        return False


def _ssh_try_kbd(transport: paramiko.Transport, username: str, password: str) -> bool:
    def handler(title: str, instructions: str, prompts: list) -> list[str]:
        if not prompts:
            return [password]
        return [password for _ in prompts]

    try:
        transport.auth_interactive(username, handler)
        return transport.is_authenticated()
    except (AuthenticationException, SSHException, EOFError):
        return False


class OltConnectionError(Exception):
    pass


class OltSession:
    def __init__(
        self,
        olt: OltEquipment,
        timeout: float = 25.0,
        log_sink: Callable[[str], None] | None = None,
    ):
        self.olt = olt
        self.timeout = timeout
        self.log: list[str] = []
        self._log_sink = log_sink
        self._client = None
        self._channel = None
        self._telnet_sock = None
        self._telnet_buf = ""

    def _log(self, msg: str) -> None:
        self.log.append(msg)
        if self._log_sink and msg:
            self._log_sink(msg)

    def _tail_has_more_prompt(self, text: str) -> bool:
        if not text:
            return False
        tail = text[-1200:].lower()
        if "the total of onts are" in tail or "total of onts are:" in tail:
            return False
        return bool(_MORE_PROMPT_RE.search(tail))

    def _send_pager_quit(self) -> None:
        """Encerra ---- More ---- (tecla Q na Huawei)."""
        if self._channel:
            self._channel.send("q")
        elif self._telnet_sock:
            self._telnet_sock.sendall(b"q")

    def _send_pager_burst(self) -> None:
        """
        SSH não envia clique de mouse; na prática no PuTTY o operador usa
        Enter + vários espaços para passar o ---- More ---- até o fim.
        """
        payload = "\r\n" + (" " * _BURST_SPACES)
        if self._channel:
            self._channel.send(payload)
        elif self._telnet_sock:
            self._telnet_sock.sendall(payload.encode("utf-8"))

    def connect(self) -> None:
        if self.olt.protocol == "telnet":
            self._connect_telnet()
        else:
            self._connect_ssh()

    def close(self) -> None:
        try:
            if self._channel:
                self._channel.close()
        except Exception:
            pass
        try:
            if self._client and hasattr(self._client, "close"):
                self._client.close()
        except Exception:
            pass
        try:
            if self._telnet_sock:
                self._telnet_sock.close()
        except Exception:
            pass

    def _connect_ssh(self) -> None:
        if paramiko is None:
            raise OltConnectionError("Instale paramiko: pip install paramiko")

        password = (self.olt.password or "").strip()
        if not password:
            raise OltConnectionError(
                "Senha da OLT vazia ou não descriptografada. "
                "Abra OLT / ONU → editar equipamento, informe a senha novamente e salve."
            )

        host = self.olt.host
        port = self.olt.port or 22
        self._log(f"[SSH] Conectando {host}:{port}…")

        try:
            sock = socket.create_connection((host, port), timeout=self.timeout)
        except OSError as exc:
            raise OltConnectionError(f"Falha ao abrir TCP {host}:{port}: {exc}") from exc

        transport = _olt_transport_factory(sock)
        transport.banner_timeout = self.timeout
        transport.handshake_timeout = self.timeout
        transport.auth_timeout = self.timeout

        try:
            transport.start_client(timeout=self.timeout)
            if not transport.is_active():
                err = transport.get_exception()
                raise OltConnectionError(err or "Handshake SSH falhou com a OLT.")
            if not _ssh_try_password(transport, self.olt.username, password):
                if not _ssh_try_kbd(transport, self.olt.username, password):
                    raise OltConnectionError(
                        "Autenticação SSH recusada (usuário/senha). "
                        "Confira credenciais no cadastro da OLT."
                    )
        except IncompatiblePeer as exc:
            raise OltConnectionError(
                "SSH incompatível com esta OLT (algoritmos de chave legados). "
                "Tente protocolo Telnet no cadastro da OLT."
            ) from exc
        except SSHException as exc:
            transport.close()
            msg = str(exc).lower()
            if "signature verification" in msg:
                raise OltConnectionError(
                    "Falha na verificação da chave SSH da OLT (ssh-rsa legado). "
                    "Reinicie o runserver após atualizar o sistema, ou use Telnet (porta 23)."
                ) from exc
            raise OltConnectionError(f"Falha SSH: {exc}") from exc
        except OltConnectionError:
            transport.close()
            raise
        except Exception as exc:
            transport.close()
            raise OltConnectionError(f"Falha SSH: {exc}") from exc

        channel = transport.open_session()
        if self.olt.vendor in ("huawei", "zte"):
            channel.get_pty(term="vt100", width=320, height=56)
        else:
            channel.get_pty(width=200, height=40)
        channel.invoke_shell()
        self._client = transport
        self._channel = channel
        time.sleep(0.8)
        self._drain_ssh()
        self._log("[SSH] Conectado.")

    def _drain_ssh(self) -> str:
        if not self._channel:
            return ""
        chunks: list[str] = []
        deadline = time.time() + 1.2
        while time.time() < deadline:
            if self._channel.recv_ready():
                data = self._channel.recv(65535).decode("utf-8", errors="replace")
                chunks.append(data)
            else:
                time.sleep(0.1)
        return "".join(chunks)

    def _connect_telnet(self) -> None:
        port = self.olt.connection_port
        self._log(f"[Telnet] Conectando {self.olt.host}:{port}…")
        password = (self.olt.password or "").strip()
        if not password:
            raise OltConnectionError(
                "Senha da OLT vazia ou não descriptografada. "
                "Edite a OLT, informe a senha novamente e salve."
            )
        try:
            sock = socket.create_connection(
                (self.olt.host, port),
                timeout=self.timeout,
            )
        except Exception as exc:
            raise OltConnectionError(f"Falha Telnet: {exc}") from exc
        self._telnet_sock = sock
        self._telnet_sock.settimeout(2.0)
        acc = self._read_telnet(6.0)
        if acc.strip():
            from .cli_log import emit_cli_output

            self._log("[Telnet] Banner / prompt inicial:")
            emit_cli_output(self._log, acc, header=None)
        low = acc.lower()
        if "login:" in low or "username:" in low:
            self._telnet_write(self.olt.username)
            acc += self._read_telnet(8.0)
        if "password:" in acc.lower():
            self._telnet_write(self.olt.password, hide=True)
            acc += self._read_telnet(10.0)
        elif not ("#" in acc or ">" in acc):
            self._telnet_write(self.olt.username)
            self._telnet_write(self.olt.password, hide=True)
            acc += self._read_telnet(10.0)
        if "login failed" in acc.lower() or "access denied" in acc.lower():
            raise OltConnectionError("Telnet: usuário ou senha recusados.")
        self._log("[Telnet] Autenticado.")

    def _read_telnet(self, wait: float = 2.0) -> str:
        if not self._telnet_sock:
            return ""
        end = time.time() + wait
        parts: list[bytes] = []
        while time.time() < end:
            try:
                chunk = self._telnet_sock.recv(65535)
                if chunk:
                    parts.append(chunk)
                else:
                    break
            except socket.timeout:
                if parts:
                    break
        raw = b"".join(parts)
        text = raw.decode("utf-8", errors="replace")
        self._telnet_buf += text
        return text

    def _telnet_write(self, text: str, hide: bool = False) -> None:
        if not self._telnet_sock:
            return
        if not hide:
            self._log(f">>> {text}")
        data = (text.strip() + "\n").encode("utf-8")
        self._telnet_sock.sendall(data)

    def run_zte_offline_list(self, pon_id: str, *, command: str | None = None) -> str:
        """Listagem ZTE: show pon power olt-rx gpon-olt_<pon>."""
        from .huawei_cli import TelnetChannelAdapter
        from .zte_cli import zte_run_offline_list

        if self._channel:
            chan = self._channel
        elif self._telnet_sock:
            chan = TelnetChannelAdapter(self._telnet_sock)
        else:
            raise OltConnectionError("Sessão não aberta")
        return zte_run_offline_list(
            chan,
            pon_id,
            self.olt.zte_enable_secret(),
            log_fn=self._log,
            command=command,
        )

    def run_huawei_offline_list(self, display_cmd: str, *, max_total: float = 600.0) -> str:
        """Listagem Huawei com paginação { <cr>||<K> } e ---- More ---- (scripts desenvolvimento)."""
        from .huawei_cli import TelnetChannelAdapter, huawei_run_display_list

        if self._channel:
            chan = self._channel
        elif self._telnet_sock:
            chan = TelnetChannelAdapter(self._telnet_sock)
        else:
            raise OltConnectionError("Sessão não aberta")
        return huawei_run_display_list(
            chan,
            display_cmd,
            self.olt.password,
            log_fn=self._log,
            max_total=max_total,
        )

    def run_commands(
        self,
        commands: list[str],
        pause: float = 0.6,
        idle_wait: float | None = None,
    ) -> str:
        if self.olt.protocol == "telnet":
            return self._run_telnet(commands, pause, idle_wait)
        return self._run_ssh(commands, pause, idle_wait)

    def _idle_seconds(self, pause: float, idle_wait: float | None) -> float:
        if idle_wait is not None:
            return idle_wait
        return max(8.0, pause * 12)

    def _run_ssh(
        self,
        commands: list[str],
        pause: float,
        idle_wait: float | None,
    ) -> str:
        if not self._channel:
            raise OltConnectionError("Sessão SSH não aberta")
        wait = self._idle_seconds(pause, idle_wait)
        out_parts: list[str] = []
        for cmd in commands:
            cmd = cmd.strip()
            if not cmd:
                continue
            self._log(f">>> {cmd}")
            self._channel.send(cmd + "\n")
            time.sleep(pause)
            chunk = self._read_ssh_paged(wait)
            if chunk:
                self._log(chunk)
            out_parts.append(chunk)
        return "\n".join(out_parts)

    def _read_ssh_paged(self, max_wait: float) -> str:
        if not self._channel:
            return ""
        chunks: list[str] = []
        idle_since = None
        deadline = time.time() + max_wait
        bursts = 0
        while time.time() < deadline:
            got_data = False
            while self._channel.recv_ready():
                data = self._channel.recv(65535).decode("utf-8", errors="replace")
                chunks.append(data)
                got_data = True
                idle_since = None

            full = "".join(chunks)
            if self._tail_has_more_prompt(full) and bursts < _MAX_PAGER_BURSTS:
                self._send_pager_burst()
                bursts += 1
                time.sleep(0.22)
                continue

            if got_data:
                continue

            if chunks:
                if idle_since is None:
                    idle_since = time.time()
                elif time.time() - idle_since > 0.55:
                    full = "".join(chunks)
                    if "the total of onts are" in full.lower():
                        self._send_pager_quit()
                        time.sleep(0.2)
                        self._drain_ssh_extra()
                        break
                    if self._tail_has_more_prompt(full) and bursts < _MAX_PAGER_BURSTS:
                        self._send_pager_burst()
                        bursts += 1
                        idle_since = None
                        time.sleep(0.22)
                        continue
                    break
            time.sleep(0.1)
        return "".join(chunks)

    def _drain_ssh_extra(self) -> None:
        if not self._channel:
            return
        deadline = time.time() + 1.0
        while time.time() < deadline:
            if self._channel.recv_ready():
                self._channel.recv(65535)
            else:
                time.sleep(0.08)

    def _run_telnet(
        self,
        commands: list[str],
        pause: float,
        idle_wait: float | None,
    ) -> str:
        if not self._telnet_sock:
            raise OltConnectionError("Sessão Telnet não aberta")
        read_wait = self._idle_seconds(pause, idle_wait)
        parts: list[str] = []
        for cmd in commands:
            cmd = cmd.strip()
            if not cmd:
                continue
            self._telnet_write(cmd)
            time.sleep(pause)
            chunk = self._read_telnet_paged(read_wait)
            if chunk:
                self._log(chunk)
            parts.append(chunk)
        return "\n".join(parts)

    def _read_telnet_paged(self, max_wait: float) -> str:
        if not self._telnet_sock:
            return ""
        chunks: list[str] = []
        deadline = time.time() + max_wait
        bursts = 0
        idle_since = None
        while time.time() < deadline:
            try:
                part = self._read_telnet(1.2)
            except Exception:
                part = ""
            if part:
                chunks.append(part)
                idle_since = None
                full = "".join(chunks)
                if self._tail_has_more_prompt(full) and bursts < _MAX_PAGER_BURSTS:
                    self._send_pager_burst()
                    bursts += 1
                    time.sleep(0.22)
                    continue
                continue

            if chunks:
                if idle_since is None:
                    idle_since = time.time()
                elif time.time() - idle_since > 0.55:
                    full = "".join(chunks)
                    if self._tail_has_more_prompt(full) and bursts < _MAX_PAGER_BURSTS:
                        self._send_pager_burst()
                        bursts += 1
                        idle_since = None
                        time.sleep(0.22)
                        continue
                    break
            time.sleep(0.1)
        return "".join(chunks)

    def run_script(self, script: str) -> str:
        lines = [ln.strip() for ln in script.splitlines() if ln.strip()]
        return self.run_commands(lines)
