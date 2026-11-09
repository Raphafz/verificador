# -*- coding: utf-8 -*-
"""GUI unificada: listar ONT offline → onu_deletar.txt → excluir. CastroX © 2026"""

from __future__ import annotations

import os
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import huawei_olt as lo
import olt_config as ocfg
from olt_config_ui import EmpresaDialog, OltDialog

import deletar_onu as core
import listar_offline_bridge as listar
from app_info import APP_NAME, APP_VERSION, SUPPORT_TELEGRAM_URL, SUPPORT_TELEGRAM_USER, WATERMARK


class QueueWriter:
    def __init__(self, q: queue.Queue[str]) -> None:
        self._q = q
        self._buf = ""

    def write(self, s: str) -> None:
        if not s:
            return
        self._buf += s
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            self._q.put(line + "\n")
        if self._buf and not s.endswith("\n"):
            self._q.put(self._buf)
            self._buf = ""

    def flush(self) -> None:
        if self._buf:
            self._q.put(self._buf + "\n")
            self._buf = ""


class OnuManagerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME} — {WATERMARK}")
        self.geometry("940x820")
        self.minsize(860, 760)
        self._log_q: queue.Queue[str] = queue.Queue()
        self._worker: threading.Thread | None = None
        self._running = False
        self._cfg = ocfg.load_config()
        self._empresa_atual_id = ""
        self._empresa_var = tk.StringVar()
        self._ultimo_preview_sns = 0
        self._ultimo_log_path: Path | None = None
        self._resumo_var = tk.StringVar(value="Pronto. A saída detalhada aparece abaixo.")

        self._build_ui()
        self._refresh_sn_info()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        pad = {"padx": 8, "pady": 4}

        self._paned = ttk.Panedwindow(self, orient=tk.VERTICAL)
        self._paned.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        pane_top = ttk.Frame(self._paned)
        pane_bottom = ttk.Frame(self._paned)
        self._paned.add(pane_top, weight=4)
        self._paned.add(pane_bottom, weight=3)

        hdr = ttk.Frame(pane_top)
        hdr.pack(fill=tk.X, **pad)
        ttk.Label(
            hdr,
            text="OLT ONU — Listar offline e deletar",
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor=tk.W)
        row_meta = ttk.Frame(hdr)
        row_meta.pack(fill=tk.X)
        ttk.Label(row_meta, text=WATERMARK, foreground="#555").pack(side=tk.LEFT)
        ttk.Button(
            row_meta,
            text="Manual / Suporte",
            style="Compact.TButton",
            command=self._abrir_manual,
        ).pack(side=tk.RIGHT)

        frm_emp = ttk.LabelFrame(pane_top, text="Empresa e OLTs")
        frm_emp.pack(fill=tk.X, **pad)

        st = ttk.Style()
        st.configure("Emp.TButton", padding=(8, 4), font=("Segoe UI", 9))
        st.configure("EmpOn.TButton", padding=(8, 4), font=("Segoe UI", 9, "bold"))
        st.configure("Action.TButton", padding=(14, 10), font=("Segoe UI", 9))
        st.map("Action.TButton", padding=[("active", (14, 10)), ("pressed", (14, 10))])
        st.configure("Compact.TButton", padding=(6, 3), font=("Segoe UI", 9))

        row_emp = ttk.Frame(frm_emp)
        row_emp.pack(fill=tk.X, padx=8, pady=(6, 4))
        ttk.Label(row_emp, text="Empresa:").pack(side=tk.LEFT, padx=(0, 6))
        self._combo_empresa = ttk.Combobox(
            row_emp,
            textvariable=self._empresa_var,
            state="readonly",
            width=28,
        )
        self._combo_empresa.pack(side=tk.LEFT, padx=(0, 8))
        self._combo_empresa.bind("<<ComboboxSelected>>", self._on_empresa_combo)

        row_emp_btn = ttk.Frame(frm_emp)
        row_emp_btn.pack(fill=tk.X, padx=8, pady=(0, 6))
        ttk.Button(
            row_emp_btn,
            text="Nova empresa",
            style="Compact.TButton",
            command=self._nova_empresa,
        ).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(
            row_emp_btn,
            text="Editar empresa",
            style="Compact.TButton",
            command=self._editar_empresa,
        ).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(
            row_emp_btn,
            text="Excluir empresa",
            style="Compact.TButton",
            command=self._excluir_empresa,
        ).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Button(
            row_emp_btn,
            text="+ OLT",
            style="Compact.TButton",
            command=self._nova_olt,
        ).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(
            row_emp_btn,
            text="Editar OLT",
            style="Compact.TButton",
            command=self._editar_olt,
        ).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(
            row_emp_btn,
            text="Excluir OLT",
            style="Compact.TButton",
            command=self._excluir_olt,
        ).pack(side=tk.LEFT)

        frm_olt = ttk.LabelFrame(pane_top, text="OLT (compartilhada nas duas etapas)")
        frm_olt.pack(fill=tk.X, **pad)

        row_filtro = ttk.Frame(frm_olt)
        row_filtro.pack(fill=tk.X, padx=8, pady=(6, 4))
        ttk.Label(row_filtro, text="Buscar:").pack(side=tk.LEFT, padx=(0, 6))
        self._olt_filtro = tk.StringVar()
        self._olt_filtro.trace_add("write", lambda *_: self._refresh_olt_list())
        self._entry_filtro = ttk.Entry(row_filtro, textvariable=self._olt_filtro, width=40)
        self._entry_filtro.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row_filtro, text="Limpar", width=7, command=self._limpar_filtro_olt).pack(
            side=tk.LEFT, padx=(6, 0)
        )

        tree_wrap = ttk.Frame(frm_olt)
        tree_wrap.pack(fill=tk.X, padx=8, pady=(0, 4))

        self._tree_olt = ttk.Treeview(
            tree_wrap,
            columns=("num", "tipo", "nome"),
            show="headings",
            height=3,
            selectmode="browse",
        )
        self._tree_olt.heading("num", text="#")
        self._tree_olt.heading("tipo", text="Tipo")
        self._tree_olt.heading("nome", text="OLT / Local")
        self._tree_olt.column("num", width=40, anchor=tk.CENTER, stretch=False)
        self._tree_olt.column("tipo", width=48, anchor=tk.CENTER, stretch=False)
        self._tree_olt.column("nome", width=560, anchor=tk.W)

        scroll_olt = ttk.Scrollbar(tree_wrap, orient=tk.VERTICAL, command=self._tree_olt.yview)
        self._tree_olt.configure(yscrollcommand=scroll_olt.set)
        self._tree_olt.pack(side=tk.LEFT, fill=tk.X, expand=True)
        scroll_olt.pack(side=tk.RIGHT, fill=tk.Y)

        self._tree_olt.tag_configure("zte", foreground="#1565c0")
        self._tree_olt.tag_configure("huawei", foreground="#37474f")
        self._tree_olt.bind("<Double-1>", self._on_olt_double_click)

        self._lbl_olt_sel = ttk.Label(frm_olt, text="", foreground="#555")
        self._lbl_olt_sel.pack(anchor=tk.W, padx=8, pady=(0, 6))

        frm_tabs = ttk.Frame(pane_top)
        frm_tabs.pack(fill=tk.BOTH, expand=True, **pad)

        self._notebook = ttk.Notebook(frm_tabs)
        self._notebook.pack(fill=tk.BOTH, expand=True)

        tab_listar = ttk.Frame(self._notebook, padding=10)
        tab_deletar = ttk.Frame(self._notebook, padding=10)
        self._notebook.add(tab_listar, text="  1. Listar offline  ")
        self._notebook.add(tab_deletar, text="  2. Deletar ONU  ")

        self._build_tab_listar(tab_listar)
        self._build_tab_deletar(tab_deletar)

        frm_log = ttk.LabelFrame(pane_bottom, text="Saída e resumo")
        frm_log.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 4))

        frm_resumo = ttk.Frame(frm_log)
        frm_resumo.pack(fill=tk.X, padx=6, pady=(6, 2))
        ttk.Label(frm_resumo, text="Resumo:", font=("Segoe UI", 9, "bold")).pack(
            anchor=tk.W
        )
        self._lbl_resumo = ttk.Label(
            frm_resumo,
            textvariable=self._resumo_var,
            wraplength=860,
            justify=tk.LEFT,
            foreground="#1a237e",
        )
        self._lbl_resumo.pack(fill=tk.X, anchor=tk.W, pady=(2, 0))

        row_log_btn = ttk.Frame(frm_log)
        row_log_btn.pack(fill=tk.X, padx=6, pady=(4, 2))
        ttk.Button(
            row_log_btn,
            text="Limpar saída",
            style="Action.TButton",
            command=self._clear_log,
        ).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(
            row_log_btn,
            text="Copiar tudo",
            style="Action.TButton",
            command=self._copiar_saida,
        ).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(
            row_log_btn,
            text="Abrir último log",
            style="Action.TButton",
            command=self._open_ultimo_log,
        ).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(
            row_log_btn,
            text="Pasta log",
            style="Action.TButton",
            command=self._open_log_dir,
        ).pack(side=tk.LEFT)

        log_wrap = ttk.Frame(frm_log)
        log_wrap.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))
        log_wrap.rowconfigure(0, weight=1)
        log_wrap.columnconfigure(0, weight=1)

        self._log = tk.Text(
            log_wrap,
            height=14,
            font=("Consolas", 10),
            state=tk.DISABLED,
            wrap=tk.NONE,
            undo=False,
        )
        scroll_y = ttk.Scrollbar(log_wrap, orient=tk.VERTICAL, command=self._log.yview)
        scroll_x = ttk.Scrollbar(log_wrap, orient=tk.HORIZONTAL, command=self._log.xview)
        self._log.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        self._log.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")

        self._status = tk.StringVar(value="Pronto.")
        status_frm = ttk.Frame(self)
        status_frm.pack(fill=tk.X, side=tk.BOTTOM)
        ttk.Label(
            status_frm,
            textvariable=self._status,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(6, 4),
        ).pack(fill=tk.X)

        self.bind("<Configure>", self._on_resize, add="+")
        self._tree_olt.bind("<<TreeviewSelect>>", lambda _e: self._atualizar_lbl_olt_sel())
        self._reload_config(select_first=True)
        self.after(150, self._ajustar_paned)
        self.after(300, self._primeira_empresa_se_vazio)

    def _build_tab_listar(self, parent: ttk.Frame) -> None:
        ttk.Label(
            parent,
            text=(
                "Comando Huawei: display ont info <frame> <slot> <porta> all\n"
                "Gera onu_deletar.txt com SN das ONTs Run offline + Config initial."
            ),
            foreground="#444",
            wraplength=700,
        ).pack(anchor=tk.W, pady=(0, 8))

        row_fsp = ttk.Frame(parent)
        row_fsp.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(row_fsp, text="Porta GPON (F/S/P):").pack(side=tk.LEFT, padx=(0, 8))
        self._fsp_var = tk.StringVar(value="0/1/14")
        ttk.Entry(row_fsp, textvariable=self._fsp_var, width=18).pack(side=tk.LEFT)
        ttk.Label(row_fsp, text="  ex.: 0/1/14 ou 0 1 14", foreground="#666").pack(
            side=tk.LEFT, padx=(8, 0)
        )

        row_btn = ttk.Frame(parent)
        row_btn.pack(fill=tk.X, pady=(4, 10))
        row_btn.columnconfigure(0, weight=1)
        row_btn.columnconfigure(1, weight=1)

        self._btn_listar = ttk.Button(
            row_btn,
            text="Listar na OLT → gravar onu_deletar.txt",
            style="Action.TButton",
            command=self._start_listar,
        )
        self._btn_listar.grid(
            row=0, column=0, columnspan=2, sticky="nsew", ipady=8, padx=4, pady=(0, 8)
        )

        self._btn_clipboard = ttk.Button(
            row_btn,
            text="Gerar TXT do clipboard (Ctrl+C)",
            style="Action.TButton",
            command=self._start_clipboard,
        )
        self._btn_clipboard.grid(row=1, column=0, sticky="nsew", ipady=6, padx=(4, 3), pady=2)

        ttk.Button(
            row_btn,
            text="Ir para deletar →",
            style="Action.TButton",
            command=self._ir_para_deletar,
        ).grid(row=1, column=1, sticky="nsew", ipady=6, padx=(3, 4), pady=2)

        self._lbl_listar_preview = ttk.Label(
            parent,
            text="Nenhuma listagem nesta sessão.",
            wraplength=680,
            foreground="#333",
        )
        self._lbl_listar_preview.pack(anchor=tk.W, pady=(4, 0))

    def _build_tab_deletar(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)

        frm_txt = ttk.LabelFrame(parent, text="Lista de SN (onu_deletar.txt)")
        frm_txt.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        frm_txt.columnconfigure(0, weight=1)

        try:
            _info_bg = ttk.Style().lookup("TLabelframe", "background") or "#f0f0f0"
        except tk.TclError:
            _info_bg = "#f0f0f0"
        self._txt_info = tk.Text(
            frm_txt,
            height=4,
            wrap=tk.WORD,
            font=("Segoe UI", 9),
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=0,
            state=tk.DISABLED,
            background=_info_bg,
        )
        self._txt_info.grid(row=0, column=0, sticky="ew", padx=8, pady=8)

        row_btn = ttk.Frame(parent)
        row_btn.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        for col in range(4):
            row_btn.columnconfigure(col, weight=1)
        ttk.Button(
            row_btn,
            text="Abrir / editar TXT",
            style="Compact.TButton",
            command=self._open_txt,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(
            row_btn,
            text="Recarregar lista",
            style="Compact.TButton",
            command=self._refresh_sn_info,
        ).grid(row=0, column=1, sticky="ew", padx=4)
        self._btn_run = ttk.Button(
            row_btn,
            text="Executar exclusão",
            style="Compact.TButton",
            command=self._start_run,
        )
        self._btn_run.grid(row=0, column=2, sticky="ew", padx=4)
        self._btn_parar = ttk.Button(
            row_btn,
            text="Parar processos",
            style="Compact.TButton",
            command=self._parar_processos,
            state=tk.DISABLED,
        )
        self._btn_parar.grid(row=0, column=3, sticky="ew", padx=(4, 0))

    def _ajustar_paned(self) -> None:
        try:
            h = max(self.winfo_height(), 760)
            self._paned.sashpos(0, int(h * 0.48))
        except tk.TclError:
            pass

    def _on_resize(self, event: tk.Event) -> None:
        if event.widget is not self:
            return
        w = max(320, event.width - 48)
        if hasattr(self, "_lbl_resumo"):
            self._lbl_resumo.configure(wraplength=w)

    def _on_olt_double_click(self, _event: tk.Event) -> None:
        if self._notebook.index(self._notebook.select()) == 0:
            self._start_listar()
        else:
            self._start_run()

    def _ir_para_deletar(self) -> None:
        self._notebook.select(1)
        self._refresh_sn_info()

    def _rede_atual(self) -> str:
        return self._empresa_atual_id

    def _on_empresa_combo(self, _event: tk.Event | None = None) -> None:
        if self._running:
            return
        nome = self._empresa_var.get().strip()
        eid = getattr(self, "_empresa_ids_por_nome", {}).get(nome, "")
        if eid:
            self._empresa_atual_id = eid
            self._olt_filtro.set("")
            self._refresh_olt_list()
            if hasattr(self, "_status"):
                self._status.set(f"Empresa: {lo.rede_titulo(eid)}")

    def _reload_config(self, *, select_first: bool = False) -> None:
        self._cfg = ocfg.load_config()
        nomes: list[str] = []
        self._empresa_ids_por_nome = {}
        for emp in self._cfg.empresas:
            label = emp.nome
            nomes.append(label)
            self._empresa_ids_por_nome[label] = emp.id
        self._combo_empresa["values"] = nomes
        if nomes:
            if select_first or self._empresa_atual_id not in lo.list_redes(self._cfg):
                self._empresa_var.set(nomes[0])
                self._empresa_atual_id = self._cfg.empresas[0].id
            else:
                for label, eid in self._empresa_ids_por_nome.items():
                    if eid == self._empresa_atual_id:
                        self._empresa_var.set(label)
                        break
            self._on_empresa_combo()
        else:
            self._empresa_atual_id = ""
            self._empresa_var.set("")
            self._refresh_olt_list()
            if hasattr(self, "_status"):
                self._status.set("Cadastre uma empresa (Nova empresa).")

    def _primeira_empresa_se_vazio(self) -> None:
        if self._cfg.empresas:
            return
        if messagebox.askyesno(
            "Cadastro",
            "Nenhuma empresa cadastrada.\n\nDeseja criar a primeira empresa agora?",
        ):
            self._nova_empresa()

    def _empresa_selecionada(self) -> ocfg.EmpresaRecord | None:
        if not self._empresa_atual_id:
            return None
        return ocfg.empresa_por_id(self._empresa_atual_id, self._cfg)

    def _nova_empresa(self) -> None:
        if self._running:
            return
        dlg = EmpresaDialog(self)
        if not dlg.wait():
            return
        emp = ocfg.adicionar_empresa(dlg.nome())
        self._reload_config()
        self._empresa_var.set(emp.nome)
        self._empresa_atual_id = emp.id
        self._on_empresa_combo()
        messagebox.showinfo("Empresa", "Empresa criada. Agora use «+ OLT» para cadastrar equipamentos.")

    def _editar_empresa(self) -> None:
        emp = self._empresa_selecionada()
        if not emp:
            messagebox.showwarning("Empresa", "Selecione ou crie uma empresa.")
            return
        dlg = EmpresaDialog(self, nome=emp.nome)
        if not dlg.wait():
            return
        ocfg.atualizar_empresa(emp.id, dlg.nome())
        self._reload_config()

    def _excluir_empresa(self) -> None:
        emp = self._empresa_selecionada()
        if not emp:
            messagebox.showwarning("Empresa", "Nenhuma empresa selecionada.")
            return
        if not messagebox.askyesno(
            "Excluir empresa",
            f"Excluir «{emp.nome}» e todas as {len(emp.olts)} OLT(s)?",
        ):
            return
        ocfg.remover_empresa(emp.id)
        self._reload_config(select_first=True)

    def _nova_olt(self) -> None:
        emp = self._empresa_selecionada()
        if not emp:
            messagebox.showwarning("OLT", "Crie uma empresa antes de adicionar OLT.")
            return
        dlg = OltDialog(self, olt_id=ocfg.proximo_olt_id(emp))
        if not dlg.wait():
            return
        if dlg.saved_record is None:
            return
        ocfg.salvar_olt(emp.id, dlg.saved_record)
        self._reload_config()
        messagebox.showinfo("OLT", "OLT cadastrada.")

    def _editar_olt(self) -> None:
        emp = self._empresa_selecionada()
        if not emp:
            return
        try:
            key = self._olt_key()
        except ValueError:
            messagebox.showwarning("OLT", "Selecione uma OLT na lista.")
            return
        rec = next((o for o in emp.olts if o.id == key), None)
        if not rec:
            return
        dlg = OltDialog(self, record=rec, olt_id=key)
        if not dlg.wait():
            return
        if dlg.saved_record is None:
            return
        ocfg.salvar_olt(emp.id, dlg.saved_record)
        self._reload_config()

    def _excluir_olt(self) -> None:
        emp = self._empresa_selecionada()
        if not emp:
            return
        try:
            key = self._olt_key()
        except ValueError:
            messagebox.showwarning("OLT", "Selecione uma OLT na lista.")
            return
        rec = next((o for o in emp.olts if o.id == key), None)
        if not rec:
            return
        if not messagebox.askyesno("Excluir OLT", f"Excluir OLT {key} — {rec.nome}?"):
            return
        ocfg.remover_olt(emp.id, key)
        self._reload_config()

    def _limpar_filtro_olt(self) -> None:
        self._olt_filtro.set("")

    def _refresh_olt_list(self) -> None:
        if not hasattr(self, "_tree_olt"):
            return
        for item in self._tree_olt.get_children():
            self._tree_olt.delete(item)
        if not self._empresa_atual_id:
            self._atualizar_lbl_olt_sel()
            return
        olts = lo.olts_dict(self._rede_atual())
        filtro = self._olt_filtro.get().strip().lower()
        for k in sorted(olts):
            p = olts[k]
            texto = p.nome.lower()
            if filtro and filtro not in texto and filtro not in str(k):
                continue
            tipo = "ZTE" if p.vendor == "zte" else "HW"
            self._tree_olt.insert(
                "",
                tk.END,
                iid=str(k),
                values=(f"{k:2d}", tipo, p.nome.upper()),
                tags=(p.vendor,),
            )
        filhos = self._tree_olt.get_children()
        if filhos:
            self._tree_olt.selection_set(filhos[0])
            self._tree_olt.focus(filhos[0])
            self._tree_olt.see(filhos[0])
        self._atualizar_lbl_olt_sel()

    def _atualizar_lbl_olt_sel(self) -> None:
        try:
            key = self._olt_key()
            p = lo.olts_dict(self._rede_atual())[key]
            fab = "ZTE" if p.vendor == "zte" else "Huawei"
            extra = ""
            if p.vendor == "zte":
                extra = " — listagem offline só em Huawei"
            self._lbl_olt_sel.configure(
                text=f"Selecionada: OLT {key} — {p.nome}  ({fab}){extra}"
            )
        except (ValueError, KeyError):
            if not self._empresa_atual_id:
                self._lbl_olt_sel.configure(
                    text="Cadastre uma empresa e use «+ OLT» para adicionar equipamentos."
                )
            else:
                self._lbl_olt_sel.configure(
                    text="Nenhuma OLT nesta empresa (use «+ OLT» ou ajuste o filtro)."
                )

    def _olt_key(self) -> int:
        sel = self._tree_olt.selection()
        if not sel:
            raise ValueError("sem seleção")
        return int(sel[0])

    def _append_log(self, text: str) -> None:
        self._log.configure(state=tk.NORMAL)
        self._log.insert(tk.END, text)
        self._log.see(tk.END)
        self._log.configure(state=tk.DISABLED)
        self._extrair_resumo_da_linha(text)

    def _extrair_resumo_da_linha(self, text: str) -> None:
        for line in text.splitlines():
            s = line.strip()
            if not s:
                continue
            m_log = re.search(r"Log:\s*(.+)$", s, re.I)
            if m_log:
                p = Path(m_log.group(1).strip())
                if p.suffix.lower() == ".txt":
                    self._ultimo_log_path = p
            if s.startswith("Concluído:") or s.startswith("--- Resumo"):
                self._resumo_var.set(s)
            elif re.match(r"^\d+/\d+ deletada", s):
                self._resumo_var.set(f"Concluído: {s}")
            elif " - Delet" in s or " - Erro:" in s or "não encontrado" in s.lower():
                atual = self._resumo_var.get()
                if len(atual) < 120 or "Pronto." in atual or "Aguardando" in atual:
                    self._resumo_var.set(s)
                else:
                    self._resumo_var.set(f"{atual}\n{s}")

    def _texto_saida(self) -> str:
        return self._log.get("1.0", tk.END)

    def _clear_log(self) -> None:
        self._log.configure(state=tk.NORMAL)
        self._log.delete("1.0", tk.END)
        self._log.configure(state=tk.DISABLED)
        self._resumo_var.set("Saída limpa.")

    def _copiar_saida(self) -> None:
        txt = self._texto_saida().strip()
        if not txt:
            messagebox.showinfo("Copiar", "Nada para copiar.")
            return
        self.clipboard_clear()
        self.clipboard_append(txt)
        self._status.set("Saída copiada para a área de transferência.")

    def _open_ultimo_log(self) -> None:
        if self._ultimo_log_path and self._ultimo_log_path.is_file():
            try:
                os.startfile(str(self._ultimo_log_path))  # type: ignore[attr-defined]
            except OSError:
                subprocess.Popen(["notepad.exe", str(self._ultimo_log_path)])
            return
        log_dir = core.app_dir() / "log"
        logs = sorted(log_dir.glob("delet_*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
        if logs:
            try:
                os.startfile(str(logs[0]))  # type: ignore[attr-defined]
            except OSError:
                subprocess.Popen(["notepad.exe", str(logs[0])])
            self._ultimo_log_path = logs[0]
            self._resumo_var.set(f"Log: {logs[0]}")
            return
        messagebox.showinfo("Log", f"Nenhum log em:\n{log_dir}")

    def _parar_processos(self) -> None:
        if not self._running:
            return
        core.request_cancel()
        self._log_q.put("\n>>> Parada solicitada — finalizando operação atual...\n")
        self._status.set("Parando…")
        self._resumo_var.set("Parada solicitada — aguardando fim da operação atual…")

    def _set_busy(self, busy: bool) -> None:
        self._running = busy
        for w in (self._btn_run, self._btn_listar, self._btn_clipboard):
            w.configure(state=tk.DISABLED if busy else tk.NORMAL)
        if hasattr(self, "_btn_parar"):
            self._btn_parar.configure(state=tk.NORMAL if busy else tk.DISABLED)
        if busy:
            self._tree_olt.state(["disabled"])
            self._entry_filtro.state(["disabled"])
            self._notebook.state(["disabled"])
        else:
            self._tree_olt.state(["!disabled"])
            self._entry_filtro.state(["!disabled"])
            self._notebook.state(["!disabled"])
        if hasattr(self, "_combo_empresa"):
            self._combo_empresa.configure(state="disabled" if busy else "readonly")

    def _gravar_onu_deletar(self, conteudo: str) -> int:
        path = core.txt_onu_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        texto = conteudo.strip()
        if texto and not texto.endswith("\n"):
            texto += "\n"
        path.write_text(texto, encoding="utf-8")
        return listar.contar_sns(texto)

    def _refresh_sn_info(self) -> None:
        path = core.txt_onu_path()
        linhas: list[str] = []
        try:
            sns = core.ler_sns_txt(path)
            linhas.append(str(path))
            linhas.append(f"{len(sns)} SN/MAC na lista.")
            if sns:
                prev = ", ".join(sns[:4]) + ("…" if len(sns) > 4 else "")
                linhas.append(f"Primeiros: {prev}")
        except FileNotFoundError:
            linhas = [f"Arquivo não encontrado:", str(path)]
        except Exception as e:
            linhas = [f"Erro ao ler TXT: {e}"]
        if hasattr(self, "_txt_info"):
            self._txt_info.configure(state=tk.NORMAL)
            self._txt_info.delete("1.0", tk.END)
            self._txt_info.insert("1.0", "\n".join(linhas))
            self._txt_info.configure(state=tk.DISABLED)

    def _open_txt(self) -> None:
        path = core.txt_onu_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.is_file():
            path.write_text(core.TXT_ONU_TEMPLATE, encoding="utf-8")
        try:
            os.startfile(str(path))  # type: ignore[attr-defined]
        except OSError:
            subprocess.Popen(["notepad.exe", str(path)])

    def _open_log_dir(self) -> None:
        log_dir = core.app_dir() / "log"
        log_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(log_dir))  # type: ignore[attr-defined]
        except OSError:
            messagebox.showinfo("Log", str(log_dir.resolve()))

    def _poll_log(self) -> None:
        try:
            while True:
                self._append_log(self._log_q.get_nowait())
        except queue.Empty:
            pass
        if self._running:
            self.after(80, self._poll_log)

    def _start_listar(self) -> None:
        if self._running:
            return
        if not self._empresa_atual_id:
            messagebox.showwarning("Empresa", "Cadastre uma empresa e pelo menos uma OLT.")
            return
        if lo.paramiko is None:
            messagebox.showerror(
                "Dependência",
                "Paramiko não instalado.\nExecute: pip install -r requirements.txt",
            )
            return
        try:
            olt_key = self._olt_key()
        except (ValueError, IndexError):
            messagebox.showerror("OLT", "Selecione uma OLT válida.")
            return
        rede = self._rede_atual()
        olts = lo.olts_dict(rede)
        profile = olts.get(olt_key)
        if not profile:
            messagebox.showerror("OLT", f"OLT inválida para {lo.rede_titulo(rede)}.")
            return
        if profile.vendor == "zte":
            messagebox.showwarning(
                "OLT ZTE",
                "A listagem offline usa comando Huawei (display ont info … all).\n"
                "Selecione uma OLT Huawei (tipo HW).",
            )
            return
        fsp = self._fsp_var.get().strip()
        if not fsp:
            messagebox.showwarning("Porta", "Informe frame/slot/porta (ex.: 0/1/14).")
            return

        self._clear_log()
        core.clear_cancel()
        self._set_busy(True)
        self._status.set(f"Listando offline — {lo.rede_titulo(rede)} OLT {olt_key}…")
        self._log_q.put(f"\n=== Listar offline — OLT {olt_key}: {profile.nome} ===\n")
        self._log_q.put(f"Porta: {fsp}\nConectando…\n")
        self.after(80, self._poll_log)

        def worker() -> None:
            ok = False
            n = 0
            try:
                filtered, _raw = listar.listar_porta_offline(rede, olt_key, fsp)
                if core.cancel_requested():
                    self._log_q.put("\n>>> Operação cancelada (resultado descartado).\n")
                    self.after(0, lambda: self._listar_finished(False, 0, cancelled=True))
                    return
                n = self._gravar_onu_deletar(filtered)
                ok = True
                self._log_q.put(f"\n{n} SN gravado(s) em:\n  {core.txt_onu_path()}\n")
                if n == 0:
                    self._log_q.put(
                        "\nAviso: nenhuma ONT offline+initial encontrada nesta porta.\n"
                    )
            except listar.ListarOfflineError as e:
                self._log_q.put(f"\nErro: {e}\n")
            except Exception as e:
                self._log_q.put(f"\nErro fatal: {e}\n")
            self.after(0, lambda: self._listar_finished(ok, n))

        self._worker = threading.Thread(target=worker, daemon=True)
        self._worker.start()

    def _start_clipboard(self) -> None:
        if self._running:
            return
        self._clear_log()
        core.clear_cancel()
        self._set_busy(True)
        self._status.set("Gerando TXT do clipboard…")
        self._log_q.put("\n=== Gerar a partir do clipboard ===\n")
        self.after(80, self._poll_log)

        def worker() -> None:
            ok = False
            n = 0
            try:
                filtered = listar.listar_do_clipboard()
                if core.cancel_requested():
                    self._log_q.put("\n>>> Operação cancelada (resultado descartado).\n")
                    self.after(0, lambda: self._listar_finished(False, 0, cancelled=True))
                    return
                n = self._gravar_onu_deletar(filtered)
                ok = True
                self._log_q.put(f"\n{n} SN gravado(s) em:\n  {core.txt_onu_path()}\n")
            except listar.ListarOfflineError as e:
                self._log_q.put(f"\nErro: {e}\n")
            except Exception as e:
                self._log_q.put(f"\nErro fatal: {e}\n")
            self.after(0, lambda: self._listar_finished(ok, n))

        self._worker = threading.Thread(target=worker, daemon=True)
        self._worker.start()

    def _listar_finished(self, ok: bool, n: int, *, cancelled: bool = False) -> None:
        self._running = False
        core.clear_cancel()
        self._poll_log()
        self._set_busy(False)
        self._ultimo_preview_sns = n
        path = core.txt_onu_path()
        if cancelled:
            self._status.set("Operação cancelada.")
            self._resumo_var.set("Listagem cancelada pelo usuário.")
            return
        if ok:
            self._refresh_sn_info()
            self._lbl_listar_preview.configure(
                text=f"Última listagem: {n} SN → {path}"
            )
            self._status.set(f"Listagem concluída — {n} SN em onu_deletar.txt")
            if n > 0:
                if messagebox.askyesno(
                    "Listagem concluída",
                    f"{n} SN gravado(s) em onu_deletar.txt.\n\nIr para a aba Deletar agora?",
                ):
                    self._ir_para_deletar()
            else:
                messagebox.showinfo(
                    "Listagem",
                    "Nenhuma ONT offline+initial nesta porta.\n"
                    "Confira F/S/P ou use o clipboard se já copiou a saída da OLT.",
                )
        else:
            self._status.set("Listagem com erro.")
            messagebox.showerror("Erro", "Falha na listagem. Veja a saída abaixo.")

    def _start_run(self) -> None:
        if self._running:
            return
        if not self._empresa_atual_id:
            messagebox.showwarning("Empresa", "Cadastre uma empresa e pelo menos uma OLT.")
            return
        if lo.paramiko is None:
            messagebox.showerror(
                "Dependência",
                "Paramiko não instalado.\nExecute: pip install -r requirements.txt",
            )
            return
        try:
            olt_key = self._olt_key()
        except (ValueError, IndexError):
            messagebox.showerror("OLT", "Selecione uma OLT válida.")
            return
        rede = self._rede_atual()
        olts = lo.olts_dict(rede)
        if olt_key not in olts:
            messagebox.showerror("OLT", f"OLT inválida para {lo.rede_titulo(rede)}.")
            return
        try:
            sns = core.ler_sns_txt(core.txt_onu_path())
        except FileNotFoundError as e:
            messagebox.showerror("TXT", str(e))
            return
        if not sns:
            messagebox.showwarning(
                "TXT",
                "Nenhum SN em onu_deletar.txt.\n\n"
                "Use a aba «Listar offline» primeiro ou edite o arquivo.",
            )
            return

        if not messagebox.askyesno(
            "Confirmar",
            f"{lo.rede_titulo(rede)} — OLT {olt_key}: {olts[olt_key].nome}\n\n"
            f"Apagar {len(sns)} ONU(s)?\n\nEsta ação não pode ser desfeita.",
        ):
            return

        self._clear_log()
        core.clear_cancel()
        self._resumo_var.set(
            f"Executando exclusão — {lo.rede_titulo(rede)} OLT {olt_key} ({len(sns)} SN)…"
        )
        self._set_busy(True)
        self._status.set(f"Executando {lo.rede_titulo(rede)} — OLT {olt_key}…")
        self.after(80, self._poll_log)

        def worker() -> None:
            code = 1
            try:
                old_out, old_err = sys.stdout, sys.stderr
                writer = QueueWriter(self._log_q)
                sys.stdout = writer  # type: ignore[assignment]
                sys.stderr = writer  # type: ignore[assignment]
                try:
                    code = core.fluxo(olt_key, rede)
                finally:
                    writer.flush()
                    sys.stdout, sys.stderr = old_out, old_err
            except Exception as e:
                self._log_q.put(f"\nErro fatal: {e}\n")
            self.after(0, lambda: self._run_finished(code))

        self._worker = threading.Thread(target=worker, daemon=True)
        self._worker.start()

    def _extrair_resultado_execucao(self, saida: str, code: int) -> tuple[str, str]:
        """Resumo curto + nome do arquivo de log (sem repetir caminho completo)."""
        n_ok: int | None = None
        n_total: int | None = None
        for line in saida.splitlines():
            s = line.strip()
            m = re.search(r"Concluído:\s*(\d+)/(\d+)", s, re.I)
            if m:
                n_ok, n_total = int(m.group(1)), int(m.group(2))
            m_total = re.search(r"Total:\s*(\d+)/(\d+)", s, re.I)
            if m_total:
                n_ok, n_total = int(m_total.group(1)), int(m_total.group(2))
            m_log = re.search(r"Log:\s*(.+)$", s, re.I)
            if m_log:
                self._ultimo_log_path = Path(m_log.group(1).strip())

        if n_ok is not None and n_total is not None:
            resumo = f"Concluído: {n_ok}/{n_total} deletada(s)."
        elif code == 130:
            resumo = "Exclusão interrompida."
        elif code == 0:
            resumo = "Concluído com sucesso."
        else:
            resumo = "Finalizado — veja detalhes na saída abaixo."

        log_nome = self._ultimo_log_path.name if self._ultimo_log_path else ""
        return resumo, log_nome

    def _run_finished(self, code: int) -> None:
        self._running = False
        core.clear_cancel()
        self._poll_log()
        self._set_busy(False)
        self._refresh_sn_info()

        resumo, log_nome = self._extrair_resultado_execucao(self._texto_saida(), code)
        if log_nome:
            self._resumo_var.set(f"{resumo}\nRelatório: {log_nome}")
        else:
            self._resumo_var.set(resumo)

        self._append_log("\n" + "=" * 72 + "\n")
        if self._ultimo_log_path:
            self._append_log(f"Relatório salvo: {self._ultimo_log_path.name}\n")
        self._log.see(tk.END)

        msg_popup = resumo
        if log_nome:
            msg_popup += f"\n\nRelatório: {log_nome}\n(Use «Abrir último log» na área de saída.)"

        if code == 0:
            self._status.set(resumo)
            messagebox.showinfo("Concluído", msg_popup)
        elif code == 130:
            self._status.set("Interrompido.")
            extra = f"\n\nRelatório: {log_nome}" if log_nome else ""
            messagebox.showinfo(
                "Interrompido",
                "Exclusão interrompida.\n\n"
                "ONUs já processadas constam no relatório; as restantes não foram apagadas."
                + extra,
            )
        else:
            self._status.set(resumo)
            messagebox.showwarning(
                "Atenção",
                msg_popup + "\n\nUse «Abrir último log» ou role a saída abaixo.",
            )

    def _abrir_manual(self) -> None:
        manual = core.app_dir() / "LEIA-ME.txt"
        if manual.is_file():
            try:
                os.startfile(str(manual))  # type: ignore[attr-defined]
                return
            except OSError:
                subprocess.Popen(["notepad.exe", str(manual)])
                return
        messagebox.showinfo(
            "Manual / Suporte",
            f"{APP_NAME}\nVersão {APP_VERSION}\n\n"
            f"Arquivo LEIA-ME.txt não encontrado nesta pasta.\n\n"
            f"Suporte Telegram:\n{SUPPORT_TELEGRAM_URL}\n{SUPPORT_TELEGRAM_USER}",
        )

    def _on_close(self) -> None:
        if self._running:
            if not messagebox.askyesno(
                "Sair",
                "Operação em andamento.\nFechar mesmo assim?",
            ):
                return
        self.destroy()


def main() -> None:
    core.ensure_portable_setup()
    if lo.paramiko is None:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Dependência",
            "Paramiko não encontrado.\nInstale: pip install -r requirements.txt",
        )
        sys.exit(1)
    app = OnuManagerApp()
    if len(sys.argv) > 1 and sys.argv[1].lower() in ("--listar", "-l", "listar"):
        app.after(80, lambda: app._notebook.select(0))
    app.mainloop()


# Compatibilidade com imports antigos
DeletarOnuApp = OnuManagerApp

if __name__ == "__main__":
    main()
