# -*- coding: utf-8 -*-
"""Recompila deletar_onu_gui.exe e monta a pasta USAR\\. CastroX © 2026"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
USAR = ROOT.parent / "USAR"
def _run(cmd: list[str]) -> None:
    print(">", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def _montar_usar() -> None:
    USAR.mkdir(parents=True, exist_ok=True)
    (USAR / "log").mkdir(exist_ok=True)

    putty_src = None
    for cand in (
        ROOT / "putty.exe",
        USAR / "putty.exe",
        Path(r"C:\Program Files\PuTTY\putty.exe"),
        Path(r"C:\putty.exe"),
    ):
        if cand.is_file():
            putty_src = cand
            break
    if putty_src:
        shutil.copy2(putty_src, USAR / "putty.exe")

    for plink in (
        Path(r"C:\Program Files\PuTTY\plink.exe"),
        Path(r"C:\Program Files (x86)\PuTTY\plink.exe"),
        Path(r"C:\plink.exe"),
    ):
        if plink.is_file():
            shutil.copy2(plink, USAR / "plink.exe")
            break

    txt = USAR / "onu_deletar.txt"
    if not txt.is_file() or txt.stat().st_size == 0:
        txt.write_text(
            "# ONU — um SN ou MAC por linha\n"
            "# Huawei: SN hexadecimal\n"
            "# ZTE:    SN alfanumerico\n#\n",
            encoding="utf-8",
        )

    (USAR / "EXECUTAR.bat").write_text(
        "@echo off\r\n"
        "chcp 65001 >nul\r\n"
        'cd /d "%~dp0"\r\n'
        'if exist "%~dp0deletar_onu_gui.exe" (\r\n'
        '  start "" "%~dp0deletar_onu_gui.exe" %*\r\n'
        "  exit /b 0\r\n"
        ")\r\n"
        "echo Falta deletar_onu_gui.exe\r\n"
        "pause\r\n"
        "exit /b 1\r\n",
        encoding="utf-8",
    )

    (USAR / "INICIAR.vbs").write_text(
        'Set fso = CreateObject("Scripting.FileSystemObject")\n'
        "pasta = fso.GetParentFolderName(WScript.ScriptFullName)\n"
        'exe = pasta & "\\deletar_onu_gui.exe"\n'
        "If Not fso.FileExists(exe) Then\n"
        '  MsgBox "Falta deletar_onu_gui.exe nesta pasta.", vbCritical, "OLT ONU"\n'
        "  WScript.Quit 1\n"
        "End If\n"
        'CreateObject("WScript.Shell").Run """" & exe & """", 1, False\n',
        encoding="utf-8",
    )

    emp_json = USAR / "empresas.json"
    if not emp_json.is_file():
        emp_json.write_text(
            '{\n  "version": 1,\n  "empresas": []\n}\n',
            encoding="utf-8",
        )

    manual_src = ROOT / "MANUAL_USUARIO.txt"
    manual_dst = USAR / "LEIA-ME.txt"
    if manual_src.is_file():
        shutil.copy2(manual_src, manual_dst)
    else:
        manual_dst.write_text(
            "Manual não encontrado. Suporte: https://t.me/castrox23\n",
            encoding="utf-8",
        )

    (USAR / "log" / "LEIA-ME.txt").write_text(
        "Relatórios de execução (.txt) são gravados aqui automaticamente.\n",
        encoding="utf-8",
    )


def main() -> int:
    _run([sys.executable, "-m", "pip", "install", "-q", "-r", "requirements.txt"])
    _run([sys.executable, "-m", "pip", "install", "-q", "pyinstaller"])

    for old in USAR.glob("deletar_onu.exe"):
        old.unlink()

    _run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--onefile",
            "--windowed",
            "--name",
            "deletar_onu_gui",
            "--paths",
            ".",
            "--hidden-import",
            "huawei_olt",
            "--hidden-import",
            "app_info",
            "--hidden-import",
            "olt_config",
            "--hidden-import",
            "olt_config_ui",
            "--hidden-import",
            "deletar_onu",
            "--hidden-import",
            "listar_offline_bridge",
            "--hidden-import",
            "listar_ont_offline",
            "--hidden-import",
            "bcrypt",
            "--hidden-import",
            "nacl",
            "--hidden-import",
            "nacl.bindings",
            "--collect-submodules",
            "paramiko",
            "--collect-all",
            "tkinter",
            "--copy-metadata",
            "cryptography",
            "--distpath",
            str(USAR),
            "--workpath",
            "build",
            "--specpath",
            ".",
            "deletar_onu_gui.py",
        ]
    )

    _montar_usar()

    from montar_venda import montar_venda

    print("\nMontando pasta Venda\\ ...")
    avisos = montar_venda()
    for a in avisos:
        print(f"  ! {a}")

    print(f"\nPronto: {USAR.resolve()}")
    print(f"Venda:  {(USAR.parent / 'Venda').resolve()}")
    for p in sorted(USAR.iterdir()):
        if p.is_file():
            print(f"  {p.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
