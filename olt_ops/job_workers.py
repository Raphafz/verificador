"""Lógica de execução de jobs OLT (host, container ou management command)."""
from __future__ import annotations

from typing import Callable

from django.db import close_old_connections
from django.utils import timezone

from .execution import company_needs_vpn
from .models import OnuCleanupJob
from .olt_service import delete_onus, list_offline_onus
from .operational_log import append_to_job_log, format_olt_reference, log_to_operations_file
from .queue import enqueue_job, process_olt_queue
from .vpn_manager import VpnConnectionError, company_vpn_context
from .vpn_slot import (
    OltSlotBusyError,
    acquire_host_vpn_lock,
    release_host_vpn_lock,
)


def append_job_line(job_id: int, line: str) -> None:
    if not line:
        return
    close_old_connections()
    job = OnuCleanupJob.objects.get(pk=job_id)
    chunk = line if line.endswith("\n") else line + "\n"
    job.log_output = append_to_job_log(job.log_output or "", chunk)
    job.save(update_fields=["log_output", "updated_at"])
    log_to_operations_file(job_id, chunk)


def make_log_sink(job_id: int) -> Callable[[str], None]:
    def sink(line: str) -> None:
        append_job_line(job_id, line)

    return sink


def _fail_job(job_id: int, *, allowed_statuses: tuple[str, ...], new_status: str = "failed") -> None:
    close_old_connections()
    job = OnuCleanupJob.objects.get(pk=job_id)
    if job.status in allowed_statuses:
        job.status = new_status
        job.save(update_fields=["status", "updated_at"])


def run_list_job(job_id: int, *, use_host_vpn_lock: bool = True) -> None:
    close_old_connections()
    job = OnuCleanupJob.objects.select_related("olt", "olt__company").get(pk=job_id)
    stamp = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
    sink = make_log_sink(job_id)
    job.status = "listing"
    job.save(update_fields=["status", "updated_at"])
    append_job_line(job_id, f"[{stamp}] Iniciando listagem offline…")
    append_job_line(
        job_id,
        format_olt_reference(job.olt.name, job.olt.host, extra=f"Porta {job.gpon_port}"),
    )

    vpn_locked = False
    try:
        if use_host_vpn_lock and company_needs_vpn(job.company):
            append_job_line(job_id, "Aguardando slot VPN (outra operação pode estar ativa)…")
            acquire_host_vpn_lock(job_id)
            vpn_locked = True
            append_job_line(job_id, "Slot VPN adquirido.")

        with company_vpn_context(
            job.company,
            target_host=job.olt.host,
            target_port=job.olt.connection_port,
            log_fn=sink,
        ):
            list_offline_onus(job, log_sink=sink)
    except OltSlotBusyError:
        enqueue_job(job_id, "list")
    except VpnConnectionError:
        _fail_job(job_id, allowed_statuses=("listing", "draft", "ready"))
    except Exception as exc:
        _fail_job(job_id, allowed_statuses=("listing", "draft", "ready"))
        append_job_line(job_id, f"ERRO: {exc}")
    finally:
        if vpn_locked:
            release_host_vpn_lock(job_id)
        process_olt_queue(job.company_id)


def run_delete_job(job_id: int, *, use_host_vpn_lock: bool = True) -> None:
    close_old_connections()
    job = OnuCleanupJob.objects.select_related("olt", "olt__company").get(pk=job_id)
    stamp = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
    n = len(job.serial_list())
    sink = make_log_sink(job_id)
    append_job_line(job_id, f"[{stamp}] Iniciando exclusão de {n} ONU(s)…")
    append_job_line(job_id, format_olt_reference(job.olt.name, job.olt.host))
    job.status = "running"
    job.save(update_fields=["status", "updated_at"])

    vpn_locked = False
    try:
        if use_host_vpn_lock and company_needs_vpn(job.company):
            append_job_line(job_id, "Aguardando slot VPN (outra operação pode estar ativa)…")
            acquire_host_vpn_lock(job_id)
            vpn_locked = True
            append_job_line(job_id, "Slot VPN adquirido.")

        with company_vpn_context(
            job.company,
            target_host=job.olt.host,
            target_port=job.olt.connection_port,
            log_fn=sink,
        ):
            delete_onus(job, log_sink=sink)
    except OltSlotBusyError:
        enqueue_job(job_id, "delete")
    except VpnConnectionError:
        _fail_job(job_id, allowed_statuses=("running",))
    except Exception as exc:
        _fail_job(job_id, allowed_statuses=("running",))
        append_job_line(job_id, f"ERRO: {exc}")
    finally:
        if vpn_locked:
            release_host_vpn_lock(job_id)
        process_olt_queue(job.company_id)
