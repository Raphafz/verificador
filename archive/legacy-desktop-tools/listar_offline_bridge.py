# -*- coding: utf-8 -*-
"""Ponte para listar_ont_offline.py usando perfis cadastrados em empresas.json."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import huawei_olt as lo

_dev = Path(__file__).resolve().parent
if str(_dev) not in sys.path:
    sys.path.insert(0, str(_dev))

import listar_ont_offline as _listar  # noqa: E402 — empacotado no .exe com PyInstaller


class ListarOfflineError(Exception):
    pass


def build_listar_cmd(fsp: str, profile: lo.OltProfile) -> str:
    if profile.cmd_listar_offline.strip():
        norm = _listar.parse_fsp(fsp)
        m = re.fullmatch(r"(\d+)/(\d+)/(\d+)", norm)
        if not m:
            raise ListarOfflineError("F/S/P inválido.")
        frame, slot, port = m.groups()
        cmd = profile.cmd_listar_offline
        return (
            cmd.replace("{frame}", frame)
            .replace("{slot}", slot)
            .replace("{port}", port)
            .replace("{fsp}", norm)
        )
    if profile.vendor != "huawei":
        raise ListarOfflineError(
            "Listagem automática só em OLT Huawei.\n"
            "Use «Gerar TXT do clipboard» ou cadastre comando em Listar offline."
        )
    return _listar.build_display_command(fsp)


def listar_porta_offline(rede: str, olt_key: int, fsp: str) -> tuple[str, str]:
    """
    Conecta na OLT Huawei e executa display ont info F S P all.
    Retorna (texto_filtrado_sns, saida_bruta).
    """
    olts = lo.olts_dict(rede)
    if olt_key not in olts:
        raise ListarOfflineError(f"OLT {olt_key} inválida para {lo.rede_titulo(rede)}.")
    profile = olts[olt_key]
    if profile.vendor == "zte":
        raise ListarOfflineError(
            "Listagem offline só funciona em OLT Huawei.\n"
            "Escolha uma OLT com tipo HW na lista."
        )
    try:
        cmd = build_listar_cmd(fsp, profile)
    except ValueError as e:
        raise ListarOfflineError(str(e)) from e

    try:
        if profile.proto == "telnet":
            raw = lo.run_telnet(
                profile.host, profile.port, profile.user, profile.password, [], cmd
            )
        else:
            raw = lo.run_ssh(
                profile.host, profile.port, profile.user, profile.password, [], cmd
            )
    except Exception as e:
        raise ListarOfflineError(f"Erro na conexão: {e}") from e

    filtered = _listar.filter_offline_block(raw)
    return filtered, raw


def listar_do_clipboard() -> str:
    """Gera lista de SN a partir do texto copiado (PuTTY / display ont info … all)."""
    try:
        raw = _listar.read_clipboard_text()
    except Exception as e:
        raise ListarOfflineError(f"Não foi possível ler a área de transferência: {e}") from e
    if not raw.strip():
        raise ListarOfflineError("Área de transferência vazia. Copie a saída da OLT (Ctrl+C).")
    return _listar.filter_offline_block(raw)


def contar_sns(texto: str) -> int:
    return len([ln for ln in texto.splitlines() if ln.strip() and not ln.strip().startswith("#")])
