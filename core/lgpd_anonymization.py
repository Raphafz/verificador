"""
Anonimização LGPD — hash irreversível, minimização e preservação de auditoria agregada.
"""
from __future__ import annotations

import hashlib
import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.audit_trail import record_security_event
from core.models import (
    CustomUser,
    DataSubjectRequest,
    Ticket,
    TicketMessage,
    TicketNotification,
)

logger = logging.getLogger("audit")


def _lgpd_salt() -> str:
    return (
        getattr(settings, "CNPJ_HASH_SALT", "").strip()
        or getattr(settings, "GEOCODING_CACHE_SALT", "").strip()
        or settings.SECRET_KEY
    )


def irreversible_subject_hash(user_id: int, *, purpose: str = "subject") -> str:
    """Hash irreversível para referência em logs/auditoria sem PII."""
    raw = f"{_lgpd_salt()}:lgpd:{purpose}:{user_id}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def anonymize_ticket_content_for_user(user: CustomUser) -> int:
    """Anonimiza mensagens e descrições associadas ao titular (preserva metadados do ticket)."""
    n = 0
    TicketMessage.objects.filter(sent_by=user).update(message="[REDACTED — titular anonimizado]")
    n += TicketMessage.objects.filter(sent_by=user).count()

    for ticket in Ticket.objects.filter(created_by=user):
        if ticket.description and "[REDACTED" not in ticket.description:
            ticket.description = "[REDACTED — titular anonimizado]"
            ticket.save(update_fields=["description"])
            n += 1

    TicketNotification.objects.filter(recipient=user).update(message="[REDACTED]")
    return n


@transaction.atomic
def anonymize_user_account(user: CustomUser) -> str:
    """
    Anonimiza conta inativa. Retorna hash do titular para auditoria.
    Preserva SecurityAuditEvent existentes (user FK pode ficar NULL após SET_NULL).
    """
    subject_hash = irreversible_subject_hash(user.pk)
    uid = user.pk

    anonymize_ticket_content_for_user(user)

    user.username = f"deleted_{subject_hash[:16]}"
    user.email = f"{subject_hash[:24]}@anon.invalid"
    user.first_name = ""
    user.last_name = ""
    user.phone = ""
    user.is_active = False
    user.set_unusable_password()
    user.save()

    record_security_event(
        "lgpd_user_anonymized",
        user=None,
        details={
            "subject_hash": subject_hash,
            "former_user_id": uid,
            "anonymized_at": timezone.now().isoformat(),
        },
        severity="info",
    )
    return subject_hash


def purge_consent_records_older_than(cutoff) -> int:
    from core.models import ConsentRecord

    deleted, _ = ConsentRecord.objects.filter(accepted_at__lt=cutoff).delete()
    return deleted


def purge_closed_tickets_older_than(cutoff) -> int:
    """Minimiza PII em tickets fechados/resolvidos antigos."""
    qs = Ticket.objects.filter(
        status__in=("fechado", "resolvido"),
        updated_at__lt=cutoff,
    )
    count = 0
    for ticket in qs.iterator():
        ticket.title = f"Ticket {ticket.ticket_number} (arquivado)"
        ticket.description = "[REDACTED — política de retenção]"
        ticket.save(update_fields=["title", "description"])
        TicketMessage.objects.filter(ticket=ticket).update(
            message="[REDACTED — política de retenção]"
        )
        count += 1
    return count


def mark_dsr_processing(req: DataSubjectRequest) -> None:
    req.status = "processing"
    req.retry_count = getattr(req, "retry_count", 0)
    req.save(update_fields=["status", "retry_count"])


def complete_dsr(req: DataSubjectRequest, *, detail_suffix: str = "") -> None:
    req.status = "completed"
    req.completed_at = timezone.now()
    if detail_suffix:
        req.details = (req.details or "") + detail_suffix
    req.last_error = ""
    req.save(update_fields=["status", "completed_at", "details", "last_error"])


def fail_dsr(req: DataSubjectRequest, error: str, *, final: bool = False) -> None:
    req.last_error = str(error)[:2000]
    req.retry_count = getattr(req, "retry_count", 0) + 1
    if final:
        req.status = "failed"
        req.completed_at = timezone.now()
    req.save(update_fields=["last_error", "retry_count", "status", "completed_at"])
