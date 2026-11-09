# -*- coding: utf-8 -*-
"""Cadastro de empresas e OLTs (JSON portátil). CastroX © 2026"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

Vendor = Literal["huawei", "zte"]
Proto = Literal["ssh", "telnet"]

CONFIG_FILENAME = "empresas.json"
CONFIG_VERSION = 1

VENDOR_CMD_HELP = {
    "huawei": {
        "listar_offline": "display ont info {frame} {slot} {port} all",
        "localizar_sn": "display ont info by-sn {sn}",
        "deletar": (
            "undo service-port vlan {line_profile_id} gpon {fsp} ont {ont_id} gemport {gemport}\n"
            "interface gpon {fs}\n"
            "ont delete {port} {ont_id}\n"
            "quit"
        ),
    },
    "zte": {
        "listar_offline": "(ZTE: use clipboard ou comando manual na OLT)",
        "localizar_sn": "show gpon onu by sn {sn}",
        "deletar": (
            "interface gpon-olt_{pon_id}\n"
            "no onu {onu_numero}\n"
            "exit"
        ),
    },
}


def _app_dir() -> Path:
    import sys

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    here = Path(__file__).resolve().parent
    usar = here.parent / "USAR"
    if usar.is_dir():
        return usar
    return here


def config_path() -> Path:
    return _app_dir() / CONFIG_FILENAME


def _migrar_config_legado() -> None:
    """Se existir empresas.json só em desenvolvimento\\, copia para USAR\\."""
    dest = config_path()
    legado = Path(__file__).resolve().parent / CONFIG_FILENAME
    if legado.resolve() == dest.resolve():
        return
    if not legado.is_file():
        return
    try:
        legado_vazio = len(legado.read_text(encoding="utf-8").strip()) < 25
    except OSError:
        legado_vazio = True
    if legado_vazio:
        return
    if not dest.is_file() or dest.stat().st_size < 25:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(legado.read_text(encoding="utf-8"), encoding="utf-8")


def slugify(nome: str) -> str:
    s = unicodedata.normalize("NFKD", nome.strip().lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s or "empresa"


@dataclass
class OltRecord:
    id: int
    nome: str
    vendor: Vendor
    proto: Proto
    host: str
    port: int
    user: str
    password: str
    gemport: int = 126
    cmd_listar_offline: str = ""
    cmd_localizar_sn: str = ""
    cmd_deletar: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> OltRecord:
        return cls(
            id=int(d["id"]),
            nome=str(d.get("nome", "")).strip(),
            vendor=str(d.get("vendor", "huawei")).lower(),  # type: ignore[arg-type]
            proto=str(d.get("proto", "ssh")).lower(),  # type: ignore[arg-type]
            host=str(d.get("host", "")).strip(),
            port=int(d.get("port", 22)),
            user=str(d.get("user", "")).strip(),
            password=str(d.get("password", "")),
            gemport=int(d.get("gemport", 126)),
            cmd_listar_offline=str(d.get("cmd_listar_offline", "")).strip(),
            cmd_localizar_sn=str(d.get("cmd_localizar_sn", "")).strip(),
            cmd_deletar=str(d.get("cmd_deletar", "")).strip(),
        )


@dataclass(frozen=True)
class OltProfile:
    """Perfil usado na conexão (compatível com huawei_olt legado)."""

    key: int
    nome: str
    vendor: Vendor
    proto: Proto
    host: str
    port: int
    user: str
    password: str
    empresa_id: str
    gemport: int = 126
    cmd_listar_offline: str = ""
    cmd_localizar_sn: str = ""
    cmd_deletar: str = ""

    @classmethod
    def from_record(cls, empresa_id: str, rec: OltRecord) -> OltProfile:
        return cls(
            key=rec.id,
            nome=rec.nome,
            vendor=rec.vendor,
            proto=rec.proto,
            host=rec.host,
            port=rec.port,
            user=rec.user,
            password=rec.password,
            empresa_id=empresa_id,
            gemport=rec.gemport,
            cmd_listar_offline=rec.cmd_listar_offline,
            cmd_localizar_sn=rec.cmd_localizar_sn,
            cmd_deletar=rec.cmd_deletar,
        )


@dataclass
class EmpresaRecord:
    id: str
    nome: str
    olts: list[OltRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "nome": self.nome,
            "olts": [o.to_dict() for o in self.olts],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> EmpresaRecord:
        olts = [OltRecord.from_dict(x) for x in d.get("olts", [])]
        return cls(
            id=str(d.get("id", "")).strip(),
            nome=str(d.get("nome", "")).strip(),
            olts=olts,
        )


@dataclass
class AppConfig:
    version: int = CONFIG_VERSION
    empresas: list[EmpresaRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "empresas": [e.to_dict() for e in self.empresas],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AppConfig:
        empresas = [EmpresaRecord.from_dict(x) for x in d.get("empresas", [])]
        return cls(version=int(d.get("version", CONFIG_VERSION)), empresas=empresas)


def default_config() -> AppConfig:
    return AppConfig(version=CONFIG_VERSION, empresas=[])


def load_config() -> AppConfig:
    _migrar_config_legado()
    path = config_path()
    if not path.is_file():
        cfg = default_config()
        save_config(cfg)
        return cfg
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default_config()
    if not isinstance(raw, dict):
        return default_config()
    return AppConfig.from_dict(raw)


def save_config(cfg: AppConfig) -> Path:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(cfg.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def list_empresa_ids(cfg: AppConfig | None = None) -> list[str]:
    cfg = cfg or load_config()
    return [e.id for e in cfg.empresas]


def empresa_por_id(empresa_id: str, cfg: AppConfig | None = None) -> EmpresaRecord | None:
    cfg = cfg or load_config()
    eid = empresa_id.strip().lower()
    for e in cfg.empresas:
        if e.id.lower() == eid:
            return e
    return None


def rede_titulo(empresa_id: str, cfg: AppConfig | None = None) -> str:
    emp = empresa_por_id(empresa_id, cfg)
    return emp.nome.upper() if emp else empresa_id.upper()


def norm_empresa(empresa_id: str, cfg: AppConfig | None = None) -> str:
    cfg = cfg or load_config()
    if not cfg.empresas:
        return ""
    raw = (empresa_id or "").strip().lower()
    if not raw:
        return cfg.empresas[0].id
    for e in cfg.empresas:
        if e.id.lower() == raw or e.nome.lower() == raw:
            return e.id
    return cfg.empresas[0].id


def list_redes(cfg: AppConfig | None = None) -> list[str]:
    cfg = cfg or load_config()
    return [e.id for e in cfg.empresas]


def olts_dict(empresa_id: str, cfg: AppConfig | None = None) -> dict[int, OltProfile]:
    cfg = cfg or load_config()
    eid = norm_empresa(empresa_id, cfg)
    if not eid:
        return {}
    emp = empresa_por_id(eid, cfg)
    if not emp:
        return {}
    out: dict[int, OltProfile] = {}
    for rec in sorted(emp.olts, key=lambda o: o.id):
        out[rec.id] = OltProfile.from_record(emp.id, rec)
    return out


def proximo_olt_id(emp: EmpresaRecord) -> int:
    if not emp.olts:
        return 1
    return max(o.id for o in emp.olts) + 1


def adicionar_empresa(nome: str, cfg: AppConfig | None = None) -> EmpresaRecord:
    cfg = cfg or load_config()
    base = slugify(nome)
    eid = base
    n = 2
    while empresa_por_id(eid, cfg):
        eid = f"{base}_{n}"
        n += 1
    emp = EmpresaRecord(id=eid, nome=nome.strip(), olts=[])
    cfg.empresas.append(emp)
    save_config(cfg)
    return emp


def atualizar_empresa(empresa_id: str, nome: str, cfg: AppConfig | None = None) -> None:
    cfg = cfg or load_config()
    emp = empresa_por_id(empresa_id, cfg)
    if not emp:
        raise ValueError("Empresa não encontrada.")
    emp.nome = nome.strip()
    save_config(cfg)


def remover_empresa(empresa_id: str, cfg: AppConfig | None = None) -> None:
    cfg = cfg or load_config()
    cfg.empresas = [e for e in cfg.empresas if e.id.lower() != empresa_id.strip().lower()]
    save_config(cfg)


def salvar_olt(empresa_id: str, olt: OltRecord, cfg: AppConfig | None = None) -> None:
    cfg = cfg or load_config()
    emp = empresa_por_id(empresa_id, cfg)
    if not emp:
        raise ValueError("Empresa não encontrada.")
    for i, existing in enumerate(emp.olts):
        if existing.id == olt.id:
            emp.olts[i] = olt
            save_config(cfg)
            return
    emp.olts.append(olt)
    save_config(cfg)


def remover_olt(empresa_id: str, olt_id: int, cfg: AppConfig | None = None) -> None:
    cfg = cfg or load_config()
    emp = empresa_por_id(empresa_id, cfg)
    if not emp:
        return
    emp.olts = [o for o in emp.olts if o.id != olt_id]
    save_config(cfg)


def vendor_defaults(vendor: str) -> dict[str, str]:
    v = vendor.lower()
    if v not in VENDOR_CMD_HELP:
        v = "huawei"
    return dict(VENDOR_CMD_HELP[v])
