"""
Conexão VPN antes de operações na OLT.
Tipos: OpenVPN (.ovpn) ou L2TP/IPsec com chave pré-compartilhada (Windows nativo).
"""
from __future__ import annotations

import base64
import os
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path
from shutil import which

from django.conf import settings

from .models import CompanyVpnConfig


class VpnConnectionError(Exception):
    pass


def _vpn_connect_timeout() -> float:
    return float(
        getattr(settings, "OLT_VPN_CONNECT_TIMEOUT", None)
        or os.getenv("OLT_VPN_CONNECT_TIMEOUT", "90")
    )


def _vpn_post_connect_delay() -> float:
    return float(
        getattr(settings, "OLT_VPN_POST_CONNECT_DELAY", None)
        or os.getenv("OLT_VPN_POST_CONNECT_DELAY", "8")
    )


def _reachability_ports(primary: int) -> list[int]:
    """Testa a porta cadastrada e o par SSH/Telnet (22/23) — cadastro errado é comum."""
    ports = [int(primary)]
    for alt in (22, 23):
        if alt not in ports:
            ports.append(alt)
    return ports


def _ps_escape(value: str) -> str:
    return value.replace("'", "''")


def _run_powershell(script: str, log_fn: Callable[[str], None] | None = None) -> str:
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    popen_kw: dict = {
        "capture_output": True,
        "text": True,
        "timeout": 120,
    }
    if sys.platform == "win32":
        popen_kw["creationflags"] = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
    proc = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-EncodedCommand",
            encoded,
        ],
        **popen_kw,
    )
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    combined = "\n".join(x for x in (out, err) if x)
    if "#< CLIXML" in combined or "<Objs Version" in combined:
        combined = "\n".join(
            ln
            for ln in combined.splitlines()
            if ln.strip()
            and not ln.strip().startswith("<")
            and not ln.strip().startswith("#<")
            and "xmlns" not in ln
            and "<Objs" not in ln
            and "CLIXML" not in ln
        )
    if log_fn and combined:
        for line in combined.splitlines()[-15:]:
            log_fn(line)
    if proc.returncode != 0:
        raise VpnConnectionError(combined or f"PowerShell saiu com código {proc.returncode}")
    return combined


def _l2tp_connection_name(cfg: CompanyVpnConfig) -> str:
    return f"OLT_SaaS_{cfg.company_id}"


def _start_l2tp_windows(
    cfg: CompanyVpnConfig,
    log_fn: Callable[[str], None] | None,
) -> str:
    if log_fn:
        log_fn("Iniciando L2TP/IPsec (VPN nativa do Windows)…")
    name = _l2tp_connection_name(cfg)
    server = _ps_escape(cfg.ipsec_server.strip())
    psk = _ps_escape(cfg.ipsec_psk)
    user = _ps_escape(cfg.vpn_username.strip())
    password = _ps_escape(cfg.vpn_password)
    script = f"""
$ErrorActionPreference = 'Stop'
$name = '{_ps_escape(name)}'
$server = '{server}'
$psk = '{psk}'
$user = '{user}'
$pass = '{password}'
if (Get-VpnConnection -Name $name -ErrorAction SilentlyContinue) {{
    Remove-VpnConnection -Name $name -Force
}}
Add-VpnConnection -Name $name -ServerAddress $server -TunnelType L2tp `
    -EncryptionLevel Required -L2tpPsk $psk -AuthenticationMethod Pap,MSChapv2 `
    -RememberCredential $false -Force | Out-Null
$p = Start-Process -FilePath 'rasdial.exe' -ArgumentList @($name, $user, $pass) -Wait -PassThru -NoNewWindow
if ($p.ExitCode -ne 0) {{
    throw "rasdial falhou (código $($p.ExitCode)). Verifique usuário/senha e se o Django roda como administrador."
}}
Write-Output 'rasdial: conectado'
"""
    _run_powershell(script, log_fn)
    return name


def _stop_l2tp_windows(connection_name: str, log_fn: Callable[[str], None] | None) -> None:
    name = _ps_escape(connection_name)
    script = f"""
$ErrorActionPreference = 'SilentlyContinue'
$name = '{name}'
Start-Process -FilePath 'rasdial.exe' -ArgumentList @($name, '/disconnect') -Wait -NoNewWindow | Out-Null
Remove-VpnConnection -Name $name -Force
"""
    try:
        _run_powershell(script, log_fn)
    except Exception:
        pass


def _start_l2tp_linux(
    cfg: CompanyVpnConfig,
    log_fn: Callable[[str], None] | None,
) -> tuple[subprocess.Popen | None, Path]:
    """Cliente L2TP/IPsec via strongSwan + xl2tpd (VPS Linux)."""
    if not which("ipsec") or not which("xl2tpd"):
        raise VpnConnectionError(
            "L2TP/IPsec no Linux exige strongSwan (ipsec) e xl2tpd no servidor. "
            "Instale os pacotes ou use um VPS com esse suporte; no Windows o teste local funciona nativamente."
        )
    work_dir = Path(tempfile.mkdtemp(prefix=f"olt_vpn_{cfg.company_id}_"))
    server = cfg.ipsec_server.strip()
    psk = cfg.ipsec_psk.replace('"', '\\"')
    user = cfg.vpn_username.strip()
    password = cfg.vpn_password.replace('"', '\\"')

    (work_dir / "ipsec.conf").write_text(
        f"""config setup
    charondebug="ike 1, knl 1, cfg 0"

conn l2tp-olt
    keyexchange=ikev1
    authby=secret
    type=transport
    left=%defaultroute
    leftprotoport=17/1701
    right={server}
    rightprotoport=17/1701
    auto=add
""",
        encoding="utf-8",
    )
    (work_dir / "ipsec.secrets").write_text(
        f'{server} %any : PSK "{psk}"\n',
        encoding="utf-8",
    )
    (work_dir / "xl2tpd.conf").write_text(
        f"""[lac olt]
lns = {server}
ppp debug = yes
pppoptfile = {work_dir / "ppp-options"}
length bit = yes
""",
        encoding="utf-8",
    )
    (work_dir / "ppp-options").write_text(
        f"""noauth
refuse-pap
refuse-eap
refuse-chap
refuse-mschap
refuse-mschapv2
name {user}
password {password}
""",
        encoding="utf-8",
    )

    if log_fn:
        log_fn(f"Subindo IPsec → {server}…")
    subprocess.run(
        ["ipsec", "start", "--config", str(work_dir / "ipsec.conf")],
        cwd=str(work_dir),
        capture_output=True,
        timeout=30,
        check=False,
    )
    subprocess.run(
        ["ipsec", "up", "l2tp-olt"],
        cwd=str(work_dir),
        capture_output=True,
        timeout=30,
        check=False,
    )
    proc = subprocess.Popen(
        ["xl2tpd", "-c", str(work_dir / "xl2tpd.conf"), "-D"],
        cwd=str(work_dir),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1.0)
    control = Path("/var/run/xl2tpd/l2tp-control")
    if control.is_file():
        control.write_text("c olt\n", encoding="ascii")
    else:
        _stop_l2tp_linux(proc, work_dir)
        raise VpnConnectionError(
            "xl2tpd não expôs /var/run/xl2tpd/l2tp-control (rode o Django como root ou ajuste permissões)."
        )
    return proc, work_dir


def _stop_l2tp_linux(proc: subprocess.Popen | None, work_dir: Path | None) -> None:
    control = Path("/var/run/xl2tpd/l2tp-control")
    if control.is_file():
        try:
            control.write_text("d olt\n", encoding="ascii")
        except OSError:
            pass
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
    subprocess.run(["ipsec", "down", "l2tp-olt"], capture_output=True, timeout=15)
    subprocess.run(["ipsec", "stop"], capture_output=True, timeout=15)
    if work_dir and work_dir.exists():
        for f in work_dir.glob("*"):
            try:
                f.unlink()
            except OSError:
                pass
        try:
            work_dir.rmdir()
        except OSError:
            pass


def _openvpn_binary() -> str:
    custom = getattr(settings, "OLT_OPENVPN_BINARY", "") or os.getenv("OLT_OPENVPN_BINARY", "")
    if custom and Path(custom).is_file():
        return custom
    if sys.platform == "win32":
        for candidate in (
            r"C:\Program Files\OpenVPN\bin\openvpn.exe",
            r"C:\Program Files (x86)\OpenVPN\bin\openvpn.exe",
        ):
            if Path(candidate).is_file():
                return candidate
    found = which("openvpn")
    if found:
        return found
    raise VpnConnectionError(
        "OpenVPN não encontrado no servidor. Instale OpenVPN ou defina OLT_OPENVPN_BINARY no .env."
    )


def _prepare_ovpn_files(cfg: CompanyVpnConfig, work_dir: Path) -> Path:
    content = cfg.ovpn_content.strip()
    if not content:
        raise VpnConnectionError("Arquivo .ovpn vazio.")

    auth_path = work_dir / "auth.txt"
    if cfg.vpn_username.strip():
        auth_path.write_text(
            f"{cfg.vpn_username.strip()}\n{cfg.vpn_password}\n",
            encoding="utf-8",
        )

    ovpn_path = work_dir / "client.ovpn"
    lines: list[str] = []
    injected_auth = False
    for line in content.splitlines():
        if line.strip().lower().startswith("auth-user-pass") and cfg.vpn_username.strip():
            lines.append(f"auth-user-pass {auth_path}")
            injected_auth = True
            continue
        lines.append(line)
    if cfg.vpn_username.strip() and not injected_auth:
        lines.append(f"auth-user-pass {auth_path}")
    ovpn_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return ovpn_path


def _start_openvpn(cfg: CompanyVpnConfig, log_fn: Callable[[str], None] | None) -> tuple[subprocess.Popen, Path]:
    binary = _openvpn_binary()
    work_dir = Path(tempfile.mkdtemp(prefix=f"olt_vpn_{cfg.company_id}_"))
    ovpn_path = _prepare_ovpn_files(cfg, work_dir)
    log_file = work_dir / "openvpn.log"

    args = [
        binary,
        "--config",
        str(ovpn_path),
        "--log",
        str(log_file),
        "--verb",
        "3",
        "--daemon",
    ]
    if sys.platform == "win32":
        args.append("olt_saas_vpn")

    popen_kw: dict = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "cwd": str(work_dir),
    }
    if sys.platform == "win32":
        popen_kw["creationflags"] = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]

    if log_fn:
        log_fn(f"Iniciando OpenVPN ({binary})…")
    proc = subprocess.Popen(args, **popen_kw)
    return proc, work_dir


def _wait_target_reachable(
    host: str,
    ports: list[int],
    timeout: float,
    log_fn: Callable[[str], None] | None,
) -> int:
    """Retorna a porta TCP que respondeu."""
    ports = _reachability_ports(ports[0]) if len(ports) == 1 else list(dict.fromkeys(int(p) for p in ports))
    deadline = time.time() + timeout
    last_err = ""
    attempt = 0
    if log_fn:
        port_list = ", ".join(str(p) for p in ports)
        log_fn(f"Testando rota VPN até {host} (portas {port_list})…")
    while time.time() < deadline:
        attempt += 1
        for port in ports:
            try:
                with socket.create_connection((host, port), timeout=4.0):
                    if log_fn:
                        log_fn(f"Rede OK: alcançou {host}:{port} via VPN.")
                    return port
            except OSError as exc:
                last_err = str(exc)
        if log_fn and attempt % 4 == 1:
            left = max(0, int(deadline - time.time()))
            log_fn(f"Ainda sem resposta em {host} ({left}s restantes)…")
        time.sleep(2.0)
    port_list = ", ".join(str(p) for p in ports)
    raise VpnConnectionError(
        f"VPN conectou, mas a OLT não respondeu em {host} (testadas portas {port_list}). "
        f"Confira protocolo SSH/Telnet e a porta no cadastro da OLT. Último erro: {last_err}"
    )


def _stop_openvpn(proc: subprocess.Popen | None, work_dir: Path | None) -> None:
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=12)
        except subprocess.TimeoutExpired:
            proc.kill()
    if work_dir and work_dir.exists():
        for f in work_dir.glob("*"):
            try:
                f.unlink()
            except OSError:
                pass
        try:
            work_dir.rmdir()
        except OSError:
            pass


def _read_openvpn_log(work_dir: Path | None, max_chars: int = 4000) -> str:
    if not work_dir:
        return ""
    log_path = work_dir / "openvpn.log"
    if not log_path.is_file():
        return ""
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
        return text[-max_chars:]
    except OSError:
        return ""


def _vpn_type_label(cfg: CompanyVpnConfig) -> str:
    if cfg.vpn_type == "l2tp_ipsec":
        return "L2TP/IPsec"
    return cfg.name or "OpenVPN"


@contextmanager
def company_vpn_context(
    company,
    *,
    target_host: str = "",
    target_port: int = 22,
    log_fn: Callable[[str], None] | None = None,
) -> Generator[None, None, None]:
    """Se a empresa tiver VPN ativa, conecta antes da operação na OLT."""
    try:
        cfg = company.vpn_config
    except CompanyVpnConfig.DoesNotExist:
        cfg = None

    if not cfg or not cfg.is_configured():
        yield
        return

    timeout = _vpn_connect_timeout()
    proc = None
    work_dir = None
    l2tp_name: str | None = None

    try:
        if log_fn:
            log_fn(f"--- VPN: {_vpn_type_label(cfg)} ({company.name}) ---")

        post_delay = _vpn_post_connect_delay()
        if cfg.vpn_type == "l2tp_ipsec":
            if sys.platform == "win32":
                l2tp_name = _start_l2tp_windows(cfg, log_fn)
            else:
                proc, work_dir = _start_l2tp_linux(cfg, log_fn)
        else:
            proc, work_dir = _start_openvpn(cfg, log_fn)
            if proc.poll() is not None:
                tail = _read_openvpn_log(work_dir)
                raise VpnConnectionError(
                    "OpenVPN encerrou ao iniciar. "
                    f"Verifique .ovpn/usuário/senha. Log: {tail[-800:]}"
                )
        if log_fn and post_delay > 0:
            log_fn(f"Aguardando rota VPN ({int(post_delay)}s)…")
        time.sleep(post_delay)

        if target_host:
            _wait_target_reachable(
                target_host,
                _reachability_ports(target_port),
                timeout,
                log_fn,
            )
        elif log_fn:
            log_fn("VPN ativa (sem teste de host — informe OLT para validar rota).")
        yield
    except VpnConnectionError as exc:
        if log_fn:
            log_fn(f"ERRO VPN: {exc}")
        raise
    except Exception as exc:
        if log_fn:
            log_fn(f"ERRO VPN: {exc}")
        raise VpnConnectionError(str(exc)) from exc
    finally:
        if log_fn:
            log_fn("Encerrando VPN…")
        if l2tp_name:
            _stop_l2tp_windows(l2tp_name, log_fn)
        elif cfg and cfg.vpn_type == "l2tp_ipsec" and sys.platform != "win32":
            _stop_l2tp_linux(proc, work_dir)
        else:
            _stop_openvpn(proc, work_dir)


def test_vpn_to_host(company, host: str, port: int = 22) -> tuple[bool, str]:
    """Teste manual: conecta VPN e tenta TCP até host:port."""
    lines: list[str] = []

    def log(line: str) -> None:
        lines.append(line)

    try:
        with company_vpn_context(
            company,
            target_host=host,
            target_port=port,
            log_fn=log,
        ):
            log("Teste concluído: rede alcançável.")
        return True, "\n".join(lines)
    except Exception as exc:
        log(f"Falha: {exc}")
        return False, "\n".join(lines)
