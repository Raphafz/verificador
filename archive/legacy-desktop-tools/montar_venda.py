# -*- coding: utf-8 -*-
"""Monta a pasta Venda\\ com somente os arquivos do pacote comercial."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
USAR = ROOT.parent / "USAR"
VENDA = ROOT.parent / "Venda"

# Arquivos obrigatórios (copiados de USAR se existirem, ou gerados)
OBRIGATORIOS = (
    "deletar_onu_gui.exe",
    "empresas.json",
    "onu_deletar.txt",
    "LEIA-ME.txt",
    "INICIAR.vbs",
    "EXECUTAR.bat",
)

# Opcionais — entram na Venda se existirem em USAR
OPCIONAIS = ("putty.exe", "plink.exe")

EMPRESAS_VAZIO = '{\n  "version": 1,\n  "empresas": []\n}\n'

ONU_TEMPLATE = (
    "# ONU — um SN ou MAC por linha\n"
    "# Huawei: SN hexadecimal\n"
    "# ZTE:    SN alfanumerico\n#\n"
)

PUTTY_AVISO = (
    "Coloque o arquivo putty.exe nesta pasta antes de enviar ao cliente.\n"
    "Download: https://www.putty.org/\n"
)


def montar_venda(*, origem: Path = USAR, destino: Path = VENDA) -> list[str]:
    avisos: list[str] = []
    if destino.exists():
        shutil.rmtree(destino)
    destino.mkdir(parents=True)
    (destino / "log").mkdir()

    manual_src = ROOT / "MANUAL_USUARIO.txt"
    if manual_src.is_file():
        shutil.copy2(manual_src, destino / "LEIA-ME.txt")
    elif (origem / "LEIA-ME.txt").is_file():
        shutil.copy2(origem / "LEIA-ME.txt", destino / "LEIA-ME.txt")

    (destino / "log" / "LEIA-ME.txt").write_text(
        "Relatórios de execução (.txt) são gravados aqui automaticamente.\n",
        encoding="utf-8",
    )

    for nome in OBRIGATORIOS:
        if nome in ("LEIA-ME.txt", "empresas.json", "onu_deletar.txt"):
            continue
        src = origem / nome
        if src.is_file():
            shutil.copy2(src, destino / nome)
        elif nome == "deletar_onu_gui.exe":
            avisos.append("Falta deletar_onu_gui.exe — rode: python compilar.py")

    if not (destino / "empresas.json").exists():
        (destino / "empresas.json").write_text(EMPRESAS_VAZIO, encoding="utf-8")

    if not (destino / "onu_deletar.txt").exists():
        txt = origem / "onu_deletar.txt"
        if txt.is_file():
            shutil.copy2(txt, destino / "onu_deletar.txt")
        else:
            (destino / "onu_deletar.txt").write_text(ONU_TEMPLATE, encoding="utf-8")

    for nome in ("INICIAR.vbs", "EXECUTAR.bat"):
        src = origem / nome
        if src.is_file() and not (destino / nome).exists():
            shutil.copy2(src, destino / nome)

    for nome in OPCIONAIS:
        src = origem / nome
        if src.is_file():
            shutil.copy2(src, destino / nome)

    if not (destino / "putty.exe").is_file():
        (destino / "COLOQUE_putty.exe_AQUI.txt").write_text(PUTTY_AVISO, encoding="utf-8")
        avisos.append("putty.exe não encontrado — inclua antes de enviar o ZIP ao cliente.")

    (destino / "COMO_ABRIR.txt").write_text(
        "Como abrir o programa\n"
        "=====================\n\n"
        "  Recomendado:  duplo clique em INICIAR.vbs\n"
        "                (abre sem janela preta do Windows)\n\n"
        "  Alternativa:  duplo clique em EXECUTAR.bat\n"
        "                (pode aparecer uma janela de comando por um instante)\n\n"
        "  Os dois iniciam deletar_onu_gui.exe\n",
        encoding="utf-8",
    )

    return avisos


def main() -> int:
    avisos = montar_venda()
    print(f"Pasta de venda: {VENDA.resolve()}\n")
    for p in sorted(VENDA.rglob("*")):
        if p.is_file():
            print(f"  {p.relative_to(VENDA)}")
    if avisos:
        print("\nAvisos:")
        for a in avisos:
            print(f"  ! {a}")
        return 1
    print("\nPronto para ZIP e envio ao cliente.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
