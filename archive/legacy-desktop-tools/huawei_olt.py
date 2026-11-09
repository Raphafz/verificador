# -*- coding: utf-8 -*-
"""Conexão SSH/Telnet/Plink com OLTs cadastradas em empresas.json."""

from __future__ import annotations

import errno
import inspect
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

warnings.filterwarnings("ignore", message=".*telnetlib.*", category=DeprecationWarning)

try:
    import paramiko
    from paramiko.ssh_exception import (
        AuthenticationException,
        IncompatiblePeer,
        SSHException,
    )
except ImportError:
    paramiko = None  # type: ignore
    AuthenticationException = Exception  # type: ignore
    IncompatiblePeer = Exception  # type: ignore
    SSHException = Exception  # type: ignore

try:
    from telnetlib import Telnet
except ImportError:
    Telnet = None  # type: ignore

Vendor = Literal["huawei", "zte"]
Proto = Literal["ssh", "telnet"]

from olt_config import (  # noqa: E402
    OltProfile,
    list_redes,
    norm_empresa as norm_rede,
    olts_dict,
    rede_titulo,
)

# Compatibilidade CLI legado (sem OLTs embutidas)
OLTS: dict[int, OltProfile] = {}


MORE_MARKERS = (
    b"---- More ----",
    b"--- More ---",
    b"  ---- More ----",
)

# Paginação estilo MA5800 após "display ..." (Enter na 1.ª vez, depois espaço).
HUAWEI_PAGE_CRK = re.compile(rb"\{\s*<cr>\s*\|\|\s*<K>\s*\}\s*:", re.I)

# Após `display ont info … all`, enviar N espaços para "---- More ----" (sem screen-length).
HUAWEI_DISPLAY_PAGE_SPACES = 7


def _strip_huawei_crk_prompts(buf: bytes) -> bytes:
    return HUAWEI_PAGE_CRK.sub(b"", buf)


def _strip_ansi(data: bytes) -> bytes:
    return re.sub(rb"\x1b\[[0-9;?]*[a-zA-Z]", b"", data)


def _read_channel_shell(
    chan: paramiko.Channel,
    idle_end: float = 1.2,
    max_total: float = 600.0,
    *,
    tail_phase: bool = True,
    tail_window: float = 5.0,
) -> str:
    buf = b""
    t0 = time.time()
    last_data = time.time()
    huawei_crk_first = True
    while time.time() - t0 < max_total:
        if chan.recv_ready():
            chunk = chan.recv(65536)
            buf += chunk
            last_data = time.time()
            if HUAWEI_PAGE_CRK.search(buf):
                buf = _strip_huawei_crk_prompts(buf)
                chan.send(b"\r\n" if huawei_crk_first else b" ")
                huawei_crk_first = False
                continue
            for m in MORE_MARKERS:
                if m in buf:
                    buf = buf.replace(m, b"")
                    chan.send(b" ")
                    last_data = time.time()
                    break
            continue
        if time.time() - last_data >= idle_end:
            break
        time.sleep(0)

    if not tail_phase:
        return _strip_ansi(buf).decode("utf-8", errors="replace")

    # Segunda fase curta: apanhar blocos lentos sem esperar ~12 s por defeito.
    last_data = time.time()
    tail_limit = min(time.time() + tail_window, t0 + max_total)
    tail_idle = 0.4
    while time.time() < tail_limit and time.time() - t0 < max_total:
        if chan.recv_ready():
            buf += chan.recv(65536)
            last_data = time.time()
            if HUAWEI_PAGE_CRK.search(buf):
                buf = _strip_huawei_crk_prompts(buf)
                chan.send(b"\r\n" if huawei_crk_first else b" ")
                huawei_crk_first = False
                continue
            for m in MORE_MARKERS:
                if m in buf:
                    buf = buf.replace(m, b"")
                    chan.send(b" ")
                    last_data = time.time()
                    break
            continue
        if time.time() - last_data >= tail_idle:
            break
        time.sleep(0)

    return _strip_ansi(buf).decode("utf-8", errors="replace")


def _huawei_post_display_paging(chan: paramiko.Channel, n: int = HUAWEI_DISPLAY_PAGE_SPACES) -> str:
    """
    Após o display: envia N espaços seguidos (paginação "More") e uma leitura curta.
    """
    for _ in range(n):
        if chan.closed:
            break
        chan.send(b" ")
    return _read_channel_shell(
        chan, idle_end=0.85, max_total=45.0, tail_phase=True, tail_window=3.0
    )


def _huawei_cleanup_session(chan: paramiko.Channel) -> None:
    """
    Após o display: quit (sai do config), quit (sai do #), y (confirma se a OLT perguntar).
    Evita deixar a sessão presa em (config)# ou prompts de confirmação.
    """
    try:
        if getattr(chan, "closed", False):
            return
    except Exception:
        return
    for cmd in ("quit", "quit", "y"):
        try:
            chan.send(cmd.encode("utf-8") + b"\n")
            _read_channel_shell(chan, idle_end=0.35, max_total=8.0, tail_phase=False)
        except Exception:
            break


def _huawei_cli_suffix_lines() -> list[str]:
    """Linhas finais do script Plink/PuTTY -m (sair da OLT de forma limpa)."""
    return ["quit", "quit", "y"]


def _send_and_read_shell(
    chan: paramiko.Channel,
    cmd: str,
    pre_wait: float = 0.0,
    idle_end: float = 1.2,
    max_total: float = 600.0,
    *,
    tail_window: float | None = None,
    tail_phase: bool | None = None,
) -> str:
    if pre_wait > 0:
        time.sleep(pre_wait)
    # Esvaziar eco/prompt pendente sem misturar com a resposta do próximo comando.
    t0 = time.time()
    while chan.recv_ready() and time.time() - t0 < 0.35:
        chan.recv(65536)
    chan.send(cmd.encode("utf-8") + b"\n")
    kw: dict[str, Any] = {}
    if tail_window is not None:
        kw["tail_window"] = tail_window
    if tail_phase is not None:
        kw["tail_phase"] = tail_phase
    return _read_channel_shell(chan, idle_end=idle_end, max_total=max_total, **kw)


def _huawei_enable_config_shell(chan: paramiko.Channel, login_password: str) -> None:
    """enable → (senha se pedir) → config → Enter para (config)# antes do display."""
    out = _send_and_read_shell(
        chan, "enable", pre_wait=0.0, idle_end=2.2, max_total=45.0, tail_window=3.0
    )
    if "assword" in out.lower():
        _send_and_read_shell(
            chan, login_password, pre_wait=0.0, idle_end=2.2, max_total=35.0, tail_window=2.5
        )
    _send_and_read_shell(
        chan, "config", pre_wait=0.0, idle_end=2.2, max_total=45.0, tail_window=3.0
    )
    chan.send(b"\n")
    _read_channel_shell(chan, idle_end=0.55, max_total=8.0, tail_phase=False)


def _huawei_cli_prefix_lines() -> list[str]:
    """
    Script Plink/PuTTY -m: enable, Enter (senha enable), config, Enter, depois display + espaços.
    """
    return ["enable", "", "config", ""]


def _zte_cli_prefix_lines() -> list[str]:
    """Plink/PuTTY: enable → conf t."""
    return ["enable", "", "conf t", ""]


def _ssh_apply_legacy_algorithms(transport: paramiko.Transport) -> None:
    """ZTE C350: prioriza ssh-rsa e KEX compatíveis (Paramiko 3.3.x)."""
    sec = transport.get_security_options()
    if "ssh-rsa" in transport._key_info:
        sec.key_types = ("ssh-rsa", "rsa-sha2-256", "rsa-sha2-512")
    prefer_kex = (
        "diffie-hellman-group-exchange-sha256",
        "diffie-hellman-group14-sha256",
        "diffie-hellman-group16-sha512",
        "ecdh-sha2-nistp256",
    )
    allowed = set(sec.kex)
    sec.kex = tuple(k for k in prefer_kex if k in allowed) or sec.kex


def _new_ssh_transport(sock: socket.socket, *, legacy: bool = False) -> paramiko.Transport:
    """Cria Transport compatível com Paramiko 3.3 (ZTE) e 3.4+ (Huawei)."""
    disabled = None
    if legacy:
        disabled = {
            "pubkeys": [
                "rsa-sha2-512",
                "rsa-sha2-256",
                "ssh-ed25519",
                "ecdsa-sha2-nistp256",
                "ecdsa-sha2-nistp384",
                "ecdsa-sha2-nistp521",
            ],
        }
    kw: dict = {}
    params = inspect.signature(paramiko.Transport.__init__).parameters
    if "strict_kex" in params:
        kw["strict_kex"] = False
    if disabled is not None and "disabled_algorithms" in params:
        kw["disabled_algorithms"] = disabled
    return paramiko.Transport(sock, **kw)


def _ssh_open_transport(host: str, port: int, *, legacy: bool = False) -> paramiko.Transport:
    """Conexão SSH. legacy=True para OLT ZTE (host key ssh-rsa)."""
    sock = socket.create_connection((host, port), timeout=30)
    transport = _new_ssh_transport(sock, legacy=legacy)
    if legacy:
        _ssh_apply_legacy_algorithms(transport)
    transport.banner_timeout = 60
    transport.handshake_timeout = 60
    transport.auth_timeout = 90
    transport.start_client(timeout=60)
    if not transport.is_active():
        err = transport.get_exception()
        transport.close()
        raise SSHException(err or "Handshake SSH falhou com a OLT.")
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


def _ssh_connect_olt(
    host: str, port: int, username: str, password: str, *, legacy: bool = False
) -> paramiko.Transport:
    """
    strict_kex=False + timeouts maiores (Huawei / Paramiko 5).
    legacy=True: algoritmos antigos (ZTE C350 SSH).
    Tenta password; na mesma sessão tenta keyboard-interactive; se o TCP cair,
    abre nova sessão só com keyboard-interactive (comportamento comum em MA5800).
    """
    transport = _ssh_open_transport(host, port, legacy=legacy)
    try:
        if _ssh_try_password(transport, username, password):
            return transport
        if transport.is_active() and _ssh_try_kbd(transport, username, password):
            return transport
    except Exception:
        transport.close()
        raise

    if transport.is_authenticated():
        return transport

    try:
        transport.close()
    except Exception:
        pass

    transport2 = _ssh_open_transport(host, port, legacy=legacy)
    try:
        if _ssh_try_kbd(transport2, username, password):
            return transport2
    except Exception:
        transport2.close()
        raise

    transport2.close()
    raise AuthenticationException(
        "Login SSH recusado pela OLT (confirme no PuTTY: usuário, senha e se pede só teclado interativo)."
    )


def _script_dir() -> Path:
    """Pasta do script (ou da .exe), onde você colocou putty.exe / plink.exe."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _find_plink() -> str | None:
    """
    Plink = SSH em modo automático (mesmo projeto do PuTTY).
    Procure primeiro na pasta do sistema (putty.exe / plink.exe ao lado do .py).
    """
    app = _script_dir()
    for p in (
        app / "plink.exe",
        app / "PLINK.EXE",
        shutil.which("plink"),
        r"C:\plink.exe",
        r"C:\Program Files\PuTTY\plink.exe",
        r"C:\Program Files (x86)\PuTTY\plink.exe",
    ):
        if not p:
            continue
        path = Path(p)
        if path.is_file():
            return str(path)
    return None


def _find_putty() -> str | None:
    """putty.exe na pasta do programa (Olts Fibramar usa C:\\putty.exe)."""
    app = _script_dir()
    for p in (
        app / "putty.exe",
        app / "PUTTY.EXE",
        shutil.which("putty"),
        r"C:\putty.exe",
        r"C:\Program Files\PuTTY\putty.exe",
        r"C:\Program Files (x86)\PuTTY\putty.exe",
    ):
        if not p:
            continue
        path = Path(p)
        if path.is_file():
            return str(path)
    return None


def _plink_install_hint() -> str:
    app = _script_dir()
    tem_putty = (app / "putty.exe").is_file() or (app / "PUTTY.EXE").is_file()
    msg = (
        "Coloque `plink.exe` na mesma pasta (vem no ZIP oficial do PuTTY, junto com putty.exe) "
        "ou use o `putty.exe` atualizado na pasta — o script tenta o putty com -m se não achar o plink.\n"
        "Download: https://www.chiark.greenend.org.uk/~sgtatham/putty/latest.html"
    )
    if tem_putty:
        msg += f"\nPasta atual: {app}"
    return msg


def _conn_reset_like(exc: BaseException) -> bool:
    if isinstance(exc, (ConnectionResetError, BrokenPipeError)):
        return True
    if isinstance(exc, OSError):
        if getattr(exc, "winerror", None) == 10054:
            return True
        if getattr(exc, "errno", None) in (
            errno.ECONNRESET,
            errno.ECONNABORTED,
        ):
            return True
    msg = str(exc).lower()
    if "10054" in msg or "forcibly closed" in msg or "forçado o cancelamento" in msg:
        return True
    if "connection reset" in msg or "broken pipe" in msg or "socket exception" in msg:
        return True
    return False


def _should_fallback_plink(exc: BaseException) -> bool:
    """
    Sempre tentar Plink/PuTTY quando o Paramiko falha na OLT: MA5800 costuma
    aceitar o mesmo login no PuTTY e recusar no Paramiko (método/cipher).
    """
    if isinstance(exc, IncompatiblePeer):
        return True
    if isinstance(exc, AuthenticationException):
        return True
    if isinstance(exc, ValueError) and "unknown cipher" in str(exc).lower():
        return True
    return _conn_reset_like(exc)


def _run_ssh_paramiko(
    host: str,
    port: int,
    username: str,
    password: str,
    extra_commands: list[str],
    display_cmd: str,
) -> str:
    transport = _ssh_connect_olt(host, port, username, password)
    try:
        chan = transport.open_session()
        # Largura maior evita quebra de linha no meio da tabela (regex deixa de bater).
        chan.get_pty("vt100", 320, 56, 0, 0)
        chan.invoke_shell()
        chan.settimeout(0.0)
        _read_channel_shell(chan, idle_end=0.85, max_total=18.0, tail_window=2.5)

        _huawei_enable_config_shell(chan, password)

        for line in extra_commands:
            line = line.strip()
            if not line:
                continue
            _send_and_read_shell(chan, line)

        main = _send_and_read_shell(
            chan,
            display_cmd,
            pre_wait=0.0,
            idle_end=6.5,
            max_total=600.0,
            tail_window=10.0,
        )
        out = main + _huawei_post_display_paging(chan, HUAWEI_DISPLAY_PAGE_SPACES)
        _huawei_cleanup_session(chan)
        return out
    finally:
        transport.close()


def _run_ssh_putty_cl(
    host: str,
    port: int,
    username: str,
    password: str,
    extra_commands: list[str],
    display_cmd: str,
    exe: str,
    *,
    use_batch: bool,
) -> str:
    """Plink ou PuTTY: -ssh user@host -pw … -m arquivo (PuTTY envia saída ao stdout se redirecionado)."""
    lines: list[str] = []
    lines.extend(_huawei_cli_prefix_lines())
    for line in extra_commands:
        line = line.strip()
        if line:
            lines.append(line)
    lines.append(display_cmd)
    for _ in range(HUAWEI_DISPLAY_PAGE_SPACES):
        lines.append(" ")
    lines.extend(_huawei_cli_suffix_lines())

    with tempfile.NamedTemporaryFile(
        "w",
        suffix=".txt",
        delete=False,
        encoding="utf-8",
        newline="\n",
    ) as tf:
        tf.write("\n".join(lines) + "\n")
        script_path = tf.name

    try:
        cmd: list[str] = [
            exe,
            "-ssh",
            f"{username}@{host}",
            "-P",
            str(port),
            "-pw",
            password,
        ]
        if use_batch:
            cmd.append("-batch")
        cmd.extend(["-m", script_path])

        run_kw: dict = {
            "capture_output": True,
            "timeout": 600,
            "encoding": "utf-8",
            "errors": "replace",
        }
        if sys.platform == "win32" and hasattr(subprocess, "CREATE_NO_WINDOW"):
            run_kw["creationflags"] = subprocess.CREATE_NO_WINDOW

        proc = subprocess.run(cmd, check=False, **run_kw)
        out = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode != 0 and not out.strip():
            raise RuntimeError(
                f"Processo saiu com código {proc.returncode}. "
                "Abra o PuTTY nesta OLT uma vez (grava a chave do host) e tente de novo."
            )
        return out
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass


def _run_ssh_plink(
    host: str,
    port: int,
    username: str,
    password: str,
    extra_commands: list[str],
    display_cmd: str,
    plink_exe: str,
) -> str:
    return _run_ssh_putty_cl(
        host,
        port,
        username,
        password,
        extra_commands,
        display_cmd,
        plink_exe,
        use_batch=True,
    )


def _run_ssh_putty_exe(
    host: str,
    port: int,
    username: str,
    password: str,
    extra_commands: list[str],
    display_cmd: str,
    putty_exe: str,
) -> str:
    """putty.exe costuma não aceitar -batch; chave do host deve estar em cache."""
    return _run_ssh_putty_cl(
        host,
        port,
        username,
        password,
        extra_commands,
        display_cmd,
        putty_exe,
        use_batch=False,
    )


def run_ssh(
    host: str,
    port: int,
    username: str,
    password: str,
    extra_commands: list[str],
    display_cmd: str,
) -> str:
    try:
        return _run_ssh_paramiko(
            host, port, username, password, extra_commands, display_cmd
        )
    except Exception as e:
        if not _should_fallback_plink(e):
            raise
        if isinstance(e, AuthenticationException):
            print(
                "\nAviso: Paramiko não autenticou nesta OLT (comum em Huawei MA5800); "
                "tentando Plink/PuTTY com o mesmo login do menu…\n",
                file=sys.stderr,
            )
        else:
            print(
                "\nAviso: Paramiko não manteve a sessão SSH; tentando Plink/PuTTY…\n",
                file=sys.stderr,
            )
        plink_exe = _find_plink()
        putty_exe = _find_putty()
        if plink_exe:
            print(
                "Usando Plink…\n",
                file=sys.stderr,
            )
            try:
                return _run_ssh_plink(
                    host,
                    port,
                    username,
                    password,
                    extra_commands,
                    display_cmd,
                    plink_exe,
                )
            except Exception as e2:
                if putty_exe:
                    print(
                        "\nPlink falhou; tentando putty.exe na mesma pasta (-m)…\n",
                        file=sys.stderr,
                    )
                    try:
                        return _run_ssh_putty_exe(
                            host,
                            port,
                            username,
                            password,
                            extra_commands,
                            display_cmd,
                            putty_exe,
                        )
                    except Exception as e3:
                        raise RuntimeError(
                            f"Plink e putty.exe falharam ({e3!r}; plink: {e2!r}). "
                            "Abra o PuTTY nesta OLT uma vez (chave do host) ou atualize o PuTTY.\n"
                            f"Causa original Paramiko: {e!r}"
                        ) from e3
                raise RuntimeError(
                    f"Plink também falhou ({e2!r}). Causa original: {e!r}"
                ) from e2

        if putty_exe:
            print(
                "Usando putty.exe desta pasta (-m)…\n",
                file=sys.stderr,
            )
            try:
                return _run_ssh_putty_exe(
                    host,
                    port,
                    username,
                    password,
                    extra_commands,
                    display_cmd,
                    putty_exe,
                )
            except Exception as e2:
                raise RuntimeError(
                    f"putty.exe -m também falhou ({e2!r}). Instale/copie também o `plink.exe` "
                    f"para a pasta ou abra o PuTTY nesta OLT uma vez e tente de novo.\n"
                    f"Causa original: {e!r}"
                ) from e2

        raise RuntimeError(
            "A OLT encerrou a conexão SSH (erro 10054 / reset). O Paramiko nem sempre combina com MA5800.\n"
            "Coloque `putty.exe` ou `plink.exe` na pasta do programa.\n" + _plink_install_hint()
        ) from e


def _telnet_drain(
    tn: Telnet,
    total_timeout: float = 60.0,
    idle_end: float = 1.0,
    crk_first_ref: list[bool] | None = None,
) -> bytes:
    buf = b""
    deadline = time.time() + total_timeout
    last = time.time()
    while time.time() < deadline:
        try:
            chunk = tn.read_very_eager()
        except EOFError:
            break
        if chunk:
            buf += chunk
            last = time.time()
            if crk_first_ref is not None and HUAWEI_PAGE_CRK.search(buf):
                buf = _strip_huawei_crk_prompts(buf)
                tn.write(b"\r\n" if crk_first_ref[0] else b" ")
                crk_first_ref[0] = False
                continue
            for m in MORE_MARKERS:
                if m in buf:
                    buf = buf.replace(m, b"")
                    tn.write(b" ")
                    last = time.time()
                    break
        else:
            if buf and time.time() - last >= idle_end:
                break
            time.sleep(0)
    return _strip_ansi(buf)


def run_telnet(
    host: str,
    port: int,
    username: str,
    password: str,
    extra_commands: list[str],
    display_cmd: str,
) -> str:
    if Telnet is None:
        raise RuntimeError(
            "Telnet indisponível: em Python 3.13+ instale standard-telnetlib (requirements.txt) ou use uma OLT SSH."
        )
    tn = Telnet()
    tn.open(host, port, timeout=30)

    def wait_prompt(timeout: float = 45.0) -> bytes:
        return _telnet_drain(tn, total_timeout=timeout, idle_end=0.8)

    try:
        acc = wait_prompt(25.0)
        low = acc.lower()
        if b"ogin:" in low or b"username:" in low:
            tn.write(username.encode("utf-8", errors="replace") + b"\n")
            acc += wait_prompt(25.0)
            low = acc.lower()
        if b"assword:" in low:
            tn.write(password.encode("utf-8", errors="replace") + b"\n")
            acc += wait_prompt(45.0)

        for line in extra_commands:
            line = line.strip()
            if not line:
                continue
            tn.write(line.encode("utf-8", errors="replace") + b"\n")
            acc += wait_prompt(90.0)

        tn.write(b"enable\n")
        acc += wait_prompt(25.0)
        tail = acc[-1200:].lower() if len(acc) > 1200 else acc.lower()
        if b"assword" in tail:
            tn.write(password.encode("utf-8", errors="replace") + b"\n")
            acc += wait_prompt(35.0)
        tn.write(b"config\n")
        acc += wait_prompt(45.0)

        tn.write(display_cmd.encode("utf-8", errors="replace") + b"\n")
        acc += _telnet_drain(
            tn, total_timeout=600.0, idle_end=1.1, crk_first_ref=[True]
        )
        for _ in range(HUAWEI_DISPLAY_PAGE_SPACES):
            tn.write(b" ")
        acc += _telnet_drain(tn, total_timeout=40.0, idle_end=0.65, crk_first_ref=None)
        for end_cmd in (b"quit\n", b"quit\n", b"y\n"):
            tn.write(end_cmd)
            acc += _telnet_drain(tn, total_timeout=10.0, idle_end=0.4, crk_first_ref=None)
        return _strip_ansi(acc).decode("utf-8", errors="replace")
    finally:
        try:
            tn.close()
        except Exception:
            pass


def _strip_ansi_str(s: str) -> str:
    """Remove sequências de cor/cursor (PuTTY) que quebram o ^ dos regex."""
    s = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", s)
    s = re.sub(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)", "", s)
    return s


