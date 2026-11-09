"""Planos comerciais RM Systems — espelham docs/PRECOS-RM-SYSTEMS.md."""
from dataclasses import dataclass
from typing import FrozenSet


@dataclass(frozen=True)
class PlanLimits:
    code: str
    label: str
    monthly_price_brl: int
    max_users: int
    max_maps: int
    max_viability_month: int
    max_whatsapp_chips: int
    max_alert_phones: int
    max_alert_messages_month: int
    max_olts: int
    max_olt_jobs_month: int
    modules: FrozenSet[str]

    def module_set(self) -> set[str]:
        return set(self.modules)


PLAN_CHOICES = (
    ("P", "P — Essencial"),
    ("M", "M — Comercial"),
    ("G", "G — Operação"),
    ("XL", "XL — Rede"),
)

PLANS: dict[str, PlanLimits] = {
    "P": PlanLimits(
        code="P",
        label="Essencial",
        monthly_price_brl=297,
        max_users=3,
        max_maps=15,
        max_viability_month=500,
        max_whatsapp_chips=0,
        max_alert_phones=0,
        max_alert_messages_month=0,
        max_olts=0,
        max_olt_jobs_month=0,
        modules=frozenset({"verificador"}),
    ),
    "M": PlanLimits(
        code="M",
        label="Comercial",
        monthly_price_brl=497,
        max_users=8,
        max_maps=40,
        max_viability_month=2_000,
        max_whatsapp_chips=0,
        max_alert_phones=0,
        max_alert_messages_month=0,
        max_olts=0,
        max_olt_jobs_month=0,
        modules=frozenset({"verificador"}),
    ),
    "G": PlanLimits(
        code="G",
        label="Operação",
        monthly_price_brl=797,
        max_users=15,
        max_maps=80,
        max_viability_month=8_000,
        max_whatsapp_chips=2,
        max_alert_phones=8,
        max_alert_messages_month=3_000,
        max_olts=0,
        max_olt_jobs_month=0,
        modules=frozenset({"verificador", "alertas"}),
    ),
    "XL": PlanLimits(
        code="XL",
        label="Rede",
        monthly_price_brl=1_497,
        max_users=40,
        max_maps=200,
        max_viability_month=25_000,
        max_whatsapp_chips=6,
        max_alert_phones=25,
        max_alert_messages_month=15_000,
        max_olts=5,
        max_olt_jobs_month=120,
        modules=frozenset({"verificador", "alertas", "olt"}),
    ),
}


def get_plan(code: str) -> PlanLimits:
    return PLANS.get(code, PLANS["M"])


def infer_plan_code_from_modules(company) -> str:
    """Heurística para empresas legadas sem plano definido."""
    if company.module_olt:
        return "XL"
    if company.module_alertas:
        return "G"
    return "M"


def apply_plan_modules(company, plan_code: str | None = None) -> None:
    """Sincroniza flags de módulo conforme o plano (não salva)."""
    code = plan_code or company.plan_code
    plan = get_plan(code)
    company.module_verificador = "verificador" in plan.modules
    company.module_alertas = "alertas" in plan.modules
    company.module_olt = "olt" in plan.modules
