# -*- coding: utf-8 -*-
"""Diálogos para cadastro de empresas e OLTs."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

import olt_config as cfg


class _DialogBase(tk.Toplevel):
    def __init__(self, parent: tk.Misc, title: str) -> None:
        super().__init__(parent)
        self.title(title)
        self.transient(parent)
        self.grab_set()
        self.result: bool = False
        self.columnconfigure(0, weight=1)

    def _finish_ok(self) -> None:
        self.result = True
        self.destroy()

    def _finish_cancel(self) -> None:
        self.result = False
        self.destroy()

    def wait(self) -> bool:
        self.wait_window()
        return self.result


class EmpresaDialog(_DialogBase):
    def __init__(self, parent: tk.Misc, *, nome: str = "") -> None:
        super().__init__(parent, "Empresa")
        self.saved_nome = ""
        self._nome_var = tk.StringVar(value=nome)
        frm = ttk.Frame(self, padding=12)
        frm.grid(sticky="nsew")
        ttk.Label(frm, text="Nome da empresa / ISP:").grid(row=0, column=0, sticky=tk.W)
        ent = ttk.Entry(frm, textvariable=self._nome_var, width=42)
        ent.grid(row=1, column=0, sticky="ew", pady=(4, 12))
        ent.focus_set()
        row = ttk.Frame(frm)
        row.grid(row=2, column=0, sticky=tk.E)
        ttk.Button(row, text="Cancelar", command=self._finish_cancel).pack(
            side=tk.RIGHT, padx=(6, 0)
        )
        ttk.Button(row, text="Salvar", command=self._on_save).pack(side=tk.RIGHT)
        self.bind("<Return>", lambda _e: self._on_save())
        self.geometry("+%d+%d" % (parent.winfo_rootx() + 40, parent.winfo_rooty() + 80))

    def nome(self) -> str:
        return (self.saved_nome or self._nome_var.get()).strip()

    def _on_save(self) -> None:
        nome = self._nome_var.get().strip()
        if not nome:
            messagebox.showwarning("Empresa", "Informe o nome da empresa.", parent=self)
            return
        self.saved_nome = nome
        self._finish_ok()


class OltDialog(_DialogBase):
    def __init__(
        self,
        parent: tk.Misc,
        *,
        record: cfg.OltRecord | None = None,
        olt_id: int | None = None,
    ) -> None:
        super().__init__(parent, "OLT")
        rec = record
        self.saved_record: cfg.OltRecord | None = None
        self._olt_id = olt_id if olt_id is not None else (rec.id if rec else 1)

        self._nome = tk.StringVar(value=rec.nome if rec else "")
        self._vendor = tk.StringVar(value=rec.vendor if rec else "huawei")
        self._proto = tk.StringVar(value=rec.proto if rec else "ssh")
        self._host = tk.StringVar(value=rec.host if rec else "")
        self._port = tk.StringVar(value=str(rec.port if rec else 22))
        self._user = tk.StringVar(value=rec.user if rec else "")
        self._password = tk.StringVar(value=rec.password if rec else "")
        self._gemport = tk.StringVar(value=str(rec.gemport if rec else 126))
        self._cmd_listar = tk.StringVar(value=rec.cmd_listar_offline if rec else "")
        self._cmd_localizar = tk.StringVar(value=rec.cmd_localizar_sn if rec else "")
        self._cmd_deletar = tk.StringVar(value=rec.cmd_deletar if rec else "")

        frm = ttk.Frame(self, padding=10)
        frm.grid(sticky="nsew")
        frm.columnconfigure(1, weight=1)

        def row(r: int, label: str, widget: tk.Widget) -> None:
            ttk.Label(frm, text=label).grid(row=r, column=0, sticky=tk.W, pady=2, padx=(0, 8))
            widget.grid(row=r, column=1, sticky="ew", pady=2)

        row(0, "Nome / local:", ttk.Entry(frm, textvariable=self._nome, width=44))
        row(
            1,
            "Fabricante:",
            ttk.Combobox(
                frm,
                textvariable=self._vendor,
                values=("huawei", "zte"),
                state="readonly",
                width=18,
            ),
        )
        row(
            2,
            "Conexão:",
            ttk.Combobox(
                frm,
                textvariable=self._proto,
                values=("ssh", "telnet"),
                state="readonly",
                width=18,
            ),
        )
        row(3, "IP / host:", ttk.Entry(frm, textvariable=self._host, width=44))
        row(4, "Porta:", ttk.Entry(frm, textvariable=self._port, width=10))
        row(5, "Usuário:", ttk.Entry(frm, textvariable=self._user, width=44))
        row(6, "Senha:", ttk.Entry(frm, textvariable=self._password, width=44, show="*"))
        row(7, "Gemport (Huawei):", ttk.Entry(frm, textvariable=self._gemport, width=10))

        adv = ttk.LabelFrame(
            frm,
            text="Comandos personalizados (opcional — vazio = padrão do fabricante)",
        )
        adv.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(10, 4))
        adv.columnconfigure(0, weight=1)

        ttk.Label(
            adv,
            text="Placeholders: {sn} {frame} {slot} {port} {fsp} {fs} {ont_id} {line_profile_id} {gemport} {pon_id} {onu_numero}",
            foreground="#555",
            wraplength=480,
            font=("Segoe UI", 8),
        ).grid(row=0, column=0, sticky=tk.W, padx=6, pady=(4, 2))

        ttk.Label(adv, text="Listar offline:").grid(row=1, column=0, sticky=tk.W, padx=6)
        ttk.Entry(adv, textvariable=self._cmd_listar, width=52).grid(
            row=2, column=0, sticky="ew", padx=6, pady=(0, 4)
        )
        ttk.Label(adv, text="Localizar SN:").grid(row=3, column=0, sticky=tk.W, padx=6)
        ttk.Entry(adv, textvariable=self._cmd_localizar, width=52).grid(
            row=4, column=0, sticky="ew", padx=6, pady=(0, 4)
        )
        ttk.Label(adv, text="Deletar (uma linha por comando):").grid(
            row=5, column=0, sticky=tk.W, padx=6
        )
        txt_del = tk.Text(adv, height=5, width=52, font=("Consolas", 9))
        txt_del.grid(row=6, column=0, sticky="ew", padx=6, pady=(0, 6))
        if rec and rec.cmd_deletar:
            txt_del.insert("1.0", rec.cmd_deletar)
        self._txt_deletar = txt_del

        ttk.Button(adv, text="Preencher padrão do fabricante", command=self._preencher_padrao).grid(
            row=7, column=0, sticky=tk.W, padx=6, pady=(0, 6)
        )

        row_btn = ttk.Frame(frm)
        row_btn.grid(row=9, column=0, columnspan=2, sticky=tk.E, pady=(8, 0))
        ttk.Button(row_btn, text="Cancelar", command=self._finish_cancel).pack(
            side=tk.RIGHT, padx=(6, 0)
        )
        ttk.Button(row_btn, text="Salvar OLT", command=self._on_save).pack(side=tk.RIGHT)

        self.geometry("520x620")
        self.geometry("+%d+%d" % (parent.winfo_rootx() + 30, parent.winfo_rooty() + 20))

    def _preencher_padrao(self) -> None:
        d = cfg.vendor_defaults(self._vendor.get())
        self._cmd_listar.set(d.get("listar_offline", ""))
        self._cmd_localizar.set(d.get("localizar_sn", ""))
        self._txt_deletar.delete("1.0", tk.END)
        self._txt_deletar.insert("1.0", d.get("deletar", ""))

    def record(self) -> cfg.OltRecord:
        try:
            port = int(self._port.get().strip() or "22")
            gemport = int(self._gemport.get().strip() or "126")
        except ValueError:
            raise ValueError("Porta e gemport devem ser números.")
        vendor = self._vendor.get().strip().lower()
        proto = self._proto.get().strip().lower()
        if vendor not in ("huawei", "zte"):
            raise ValueError("Fabricante inválido.")
        if proto not in ("ssh", "telnet"):
            raise ValueError("Conexão inválida.")
        return cfg.OltRecord(
            id=self._olt_id,
            nome=self._nome.get().strip(),
            vendor=vendor,  # type: ignore[arg-type]
            proto=proto,  # type: ignore[arg-type]
            host=self._host.get().strip(),
            port=port,
            user=self._user.get().strip(),
            password=self._password.get(),
            gemport=gemport,
            cmd_listar_offline=self._cmd_listar.get().strip(),
            cmd_localizar_sn=self._cmd_localizar.get().strip(),
            cmd_deletar=self._txt_deletar.get("1.0", tk.END).strip(),
        )

    def _on_save(self) -> None:
        if not self._nome.get().strip():
            messagebox.showwarning("OLT", "Informe o nome da OLT.", parent=self)
            return
        if not self._host.get().strip():
            messagebox.showwarning("OLT", "Informe o IP/host.", parent=self)
            return
        if not self._user.get().strip():
            messagebox.showwarning("OLT", "Informe o usuário.", parent=self)
            return
        try:
            self.saved_record = self.record()
        except ValueError as e:
            messagebox.showwarning("OLT", str(e), parent=self)
            return
        self._finish_ok()
