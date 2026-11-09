"""Metering e bloqueio automático de limites por plano."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.utils import timezone

from core.plans import PlanLimits, get_plan


class QuotaExceeded(ValidationError):
    """Limite do plano atingido — bloqueia a operação."""


@dataclass(frozen=True)
class QuotaCheck:
    metric: str
    label: str
    used: int
    limit: int
    allowed: bool

    @property
    def remaining(self) -> int:
        if self.limit <= 0:
            return 0
        return max(0, self.limit - self.used)

    @property
    def percent(self) -> float:
        if self.limit <= 0:
            return 100.0 if self.used > 0 else 0.0
        return min(100.0, round((self.used / self.limit) * 100, 1))


METRIC_LABELS = {
    "users": "Usuários ativos",
    "maps": "Mapas CTO",
    "viability_month": "Consultas de viabilidade (mês)",
    "whatsapp_chips": "Chips WhatsApp",
    "alert_phones": "Números de alerta",
    "alert_messages_month": "Mensagens de alerta (mês)",
    "olts": "OLTs cadastradas",
    "olt_jobs_month": "Jobs ONU (mês)",
}


def _month_start() -> datetime:
    now = timezone.now()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _enforcement_enabled(company, user=None) -> bool:
    if user and (
        getattr(user, "is_rm_admin", False) or getattr(user, "is_superuser", False)
    ):
        return False
    if not getattr(settings, "QUOTA_ENFORCEMENT_ENABLED", True):
        return False
    return getattr(company, "quota_enforcement", True)


def resolve_limits(company) -> PlanLimits:
    plan = get_plan(company.plan_code)
    overrides = {
        "max_users": company.quota_override_users,
        "max_maps": company.quota_override_maps,
        "max_viability_month": company.quota_override_viability_month,
        "max_whatsapp_chips": company.quota_override_whatsapp_chips,
        "max_alert_phones": company.quota_override_alert_phones,
        "max_alert_messages_month": company.quota_override_alert_messages_month,
        "max_olts": company.quota_override_olts,
        "max_olt_jobs_month": company.quota_override_olt_jobs_month,
    }
    if not any(v is not None for v in overrides.values()):
        return plan
    # dataclass is frozen — build a copy with overrides
    data = {
        "code": plan.code,
        "label": plan.label,
        "monthly_price_brl": plan.monthly_price_brl,
        "max_users": overrides["max_users"] if overrides["max_users"] is not None else plan.max_users,
        "max_maps": overrides["max_maps"] if overrides["max_maps"] is not None else plan.max_maps,
        "max_viability_month": (
            overrides["max_viability_month"]
            if overrides["max_viability_month"] is not None
            else plan.max_viability_month
        ),
        "max_whatsapp_chips": (
            overrides["max_whatsapp_chips"]
            if overrides["max_whatsapp_chips"] is not None
            else plan.max_whatsapp_chips
        ),
        "max_alert_phones": (
            overrides["max_alert_phones"]
            if overrides["max_alert_phones"] is not None
            else plan.max_alert_phones
        ),
        "max_alert_messages_month": (
            overrides["max_alert_messages_month"]
            if overrides["max_alert_messages_month"] is not None
            else plan.max_alert_messages_month
        ),
        "max_olts": overrides["max_olts"] if overrides["max_olts"] is not None else plan.max_olts,
        "max_olt_jobs_month": (
            overrides["max_olt_jobs_month"]
            if overrides["max_olt_jobs_month"] is not None
            else plan.max_olt_jobs_month
        ),
        "modules": plan.modules,
    }
    return PlanLimits(**data)


def _count_alert_phones(company) -> int:
    try:
        config = company.alert_bridge
    except Exception:
        return 0
    return len(config.whatsapp_phones_list())


def get_usage(company) -> dict[str, int]:
    from core.models import CTOMapFile, CustomUser
    from ftth_viewer.models import ViabilidadeCache

    month_start = _month_start()
    usage = {
        "users": CustomUser.objects.filter(company=company, is_active=True).count(),
        "maps": CTOMapFile.objects.filter(company=company).count(),
        "viability_month": ViabilidadeCache.objects.filter(
            company=company,
            created_at__gte=month_start,
        ).count(),
        "whatsapp_chips": company.whatsapp_lines.filter(is_active=True).count(),
        "alert_phones": _count_alert_phones(company),
        "alert_messages_month": 0,
        "olts": 0,
        "olt_jobs_month": 0,
    }

    try:
        from olt_ops.models import OltEquipment, OnuCleanupJob

        usage["olts"] = OltEquipment.objects.filter(company=company, is_active=True).count()
        usage["olt_jobs_month"] = OnuCleanupJob.objects.filter(
            company=company,
            created_at__gte=month_start,
        ).exclude(status="draft").count()
    except Exception:
        pass

    return usage


def _limit_for_metric(limits: PlanLimits, metric: str) -> int:
    return {
        "users": limits.max_users,
        "maps": limits.max_maps,
        "viability_month": limits.max_viability_month,
        "whatsapp_chips": limits.max_whatsapp_chips,
        "alert_phones": limits.max_alert_phones,
        "alert_messages_month": limits.max_alert_messages_month,
        "olts": limits.max_olts,
        "olt_jobs_month": limits.max_olt_jobs_month,
    }.get(metric, 0)


def check_quota(company, metric: str, *, extra: int = 1) -> QuotaCheck:
    limits = resolve_limits(company)
    usage = get_usage(company)
    used = usage.get(metric, 0)
    limit = _limit_for_metric(limits, metric)
    projected = used + extra
    allowed = limit <= 0 or projected <= limit
    return QuotaCheck(
        metric=metric,
        label=METRIC_LABELS.get(metric, metric),
        used=used,
        limit=limit,
        allowed=allowed,
    )


def quota_block_message(check: QuotaCheck, *, plan_code: str) -> str:
    upgrade_hint = {
        "P": "M Comercial",
        "M": "G Operação",
        "G": "XL Rede",
        "XL": "limites personalizados com o suporte RM",
    }.get(plan_code, "um plano superior")
    if check.limit <= 0:
        return (
            f"O recurso «{check.label}» não está incluso no plano {plan_code}. "
            f"Faça upgrade para {upgrade_hint} ou contate o suporte RM Systems."
        )
    return (
        f"Limite do plano {plan_code} atingido para {check.label}: "
        f"{check.used}/{check.limit}. "
        f"Faça upgrade para {upgrade_hint} ou remova uso excedente."
    )


def enforce_quota(company, metric: str, *, extra: int = 1, user=None) -> QuotaCheck:
    check = check_quota(company, metric, extra=extra)
    if _enforcement_enabled(company, user) and not check.allowed:
        raise QuotaExceeded(quota_block_message(check, plan_code=company.plan_code))
    return check


def invalidate_usage_summary_cache(company_id: int) -> None:
    cache.delete(f"quota_summary:v1:{company_id}")


def get_usage_summary(company) -> dict[str, Any]:
    limits = resolve_limits(company)
    usage = get_usage(company)
    plan = get_plan(company.plan_code)
    items = []
    for metric in METRIC_LABELS:
        limit = _limit_for_metric(limits, metric)
        if limit <= 0 and usage.get(metric, 0) == 0 and metric in (
            "whatsapp_chips",
            "alert_phones",
            "alert_messages_month",
            "olts",
            "olt_jobs_month",
        ):
            continue
        check = QuotaCheck(
            metric=metric,
            label=METRIC_LABELS[metric],
            used=usage.get(metric, 0),
            limit=limit,
            allowed=limit <= 0 or usage.get(metric, 0) <= limit,
        )
        items.append(
            {
                "metric": metric,
                "label": check.label,
                "used": check.used,
                "limit": check.limit,
                "remaining": check.remaining,
                "percent": check.percent,
                "allowed": check.allowed,
                "at_limit": check.limit > 0 and check.used >= check.limit,
                "near_limit": check.limit > 0 and check.percent >= 80,
            }
        )
    return {
        "plan_code": company.plan_code,
        "plan_label": plan.label,
        "enforcement": company.quota_enforcement,
        "items": items,
    }
