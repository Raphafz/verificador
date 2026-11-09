"""Políticas de retenção LGPD — configuráveis via settings."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.utils import timezone


@dataclass(frozen=True)
class RetentionPolicy:
    name: str
    days: int
    description: str
    model_label: str = ""


def get_retention_policies() -> list[RetentionPolicy]:
    return [
        RetentionPolicy(
            "geocoding_cache",
            max(1, int(getattr(settings, "GEOCODING_CACHE_TTL_HOURS", 24)) // 24),
            "Cache de geocoding (hash, sem endereço completo)",
            "ftth_viewer.GeocodingCache",
        ),
        RetentionPolicy(
            "viability_cache",
            int(getattr(settings, "CACHE_RETENTION_DAYS", 90)),
            "Cache de viabilidade FTTH",
            "ftth_viewer.ViabilidadeCache",
        ),
        RetentionPolicy(
            "activation_tokens",
            int(getattr(settings, "ACTIVATION_TOKEN_RETENTION_DAYS", 7)),
            "Tokens de ativação usados/expirados",
            "core.AccountActivationToken",
        ),
        RetentionPolicy(
            "audit_events",
            int(getattr(settings, "AUDIT_RETENTION_DAYS", 365)),
            "Trilha de auditoria de segurança",
            "core.SecurityAuditEvent",
        ),
        RetentionPolicy(
            "consent_records",
            int(getattr(settings, "CONSENT_RETENTION_DAYS", 1825)),
            "Registros de consentimento",
            "core.ConsentRecord",
        ),
        RetentionPolicy(
            "data_subject_requests",
            int(getattr(settings, "DSR_RETENTION_DAYS", 1825)),
            "Solicitações LGPD concluídas/rejeitadas",
            "core.DataSubjectRequest",
        ),
        RetentionPolicy(
            "support_tickets",
            int(getattr(settings, "TICKET_RETENTION_DAYS", 730)),
            "Tickets fechados/resolvidos — anonimização de conteúdo",
            "core.Ticket",
        ),
        RetentionPolicy(
            "olt_job_logs",
            int(getattr(settings, "OLT_LOG_RETENTION_DAYS", 7)),
            "log_output de jobs OLT",
            "olt_ops.OnuCleanupJob",
        ),
        RetentionPolicy(
            "lgpd_export_downloads",
            int(getattr(settings, "LGPD_EXPORT_TTL_HOURS", 24)) // 24 or 1,
            "Arquivos ZIP de exportação assinados",
            "core.LgpdExportDownload",
        ),
    ]


def cutoff_for_days(days: int):
    return timezone.now() - timedelta(days=days)


def policy_days(name: str, default: int) -> int:
    for p in get_retention_policies():
        if p.name == name:
            return p.days
    return default
