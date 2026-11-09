"""Fila de jobs OLT quando slots VPN/container estão ocupados."""
from __future__ import annotations

import logging
from typing import Literal

from django.core.cache import cache

from .models import OnuCleanupJob

logger = logging.getLogger(__name__)

QUEUE_LOCK_KEY = "olt:queue:processor"
QUEUE_LOCK_TTL = 30

Operation = Literal["list", "delete"]


def enqueue_job(job_id: int, operation: Operation) -> None:
    from .operational_log import append_to_job_log, log_to_operations_file

    job = OnuCleanupJob.objects.get(pk=job_id)
    if job.status == "queued" and job.pending_operation == operation:
        return
    msg = "Na fila: aguardando slot VPN/OLT disponível. A operação iniciará automaticamente.\n"
    job.status = "queued"
    job.pending_operation = operation
    job.log_output = append_to_job_log(job.log_output or "", msg)
    job.save(update_fields=["status", "pending_operation", "log_output", "updated_at"])
    log_to_operations_file(job_id, msg)
    logger.info("Job OLT enfileirado id=%s operation=%s", job_id, operation)


def process_olt_queue(company_id: int | None = None) -> None:
    """Dispara o job mais antigo em fila (opcionalmente filtrado por empresa)."""
    if not cache.add(QUEUE_LOCK_KEY, "1", QUEUE_LOCK_TTL):
        return
    try:
        qs = (
            OnuCleanupJob.objects.filter(status="queued", pending_operation__in=("list", "delete"))
            .select_related("company")
            .order_by("updated_at")
        )
        if company_id is not None:
            qs = qs.filter(company_id=company_id)
        job = qs.first()
        if not job:
            return
        operation: Operation = job.pending_operation  # type: ignore[assignment]
        if operation not in ("list", "delete"):
            return
        job_id = job.pk
        reset_status = "draft" if operation == "list" else "ready"
        updated = OnuCleanupJob.objects.filter(pk=job_id, status="queued").update(
            status=reset_status,
        )
        if not updated:
            return
        from .dispatcher import dispatch_job

        logger.info("Processando fila OLT job=%s operation=%s", job_id, operation)
        dispatch_job(job_id, operation)
    finally:
        cache.delete(QUEUE_LOCK_KEY)
