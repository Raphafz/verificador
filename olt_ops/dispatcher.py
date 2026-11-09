"""Despacha jobs OLT para thread no host ou container Docker isolado."""
from __future__ import annotations

import logging
import os
import subprocess
import threading
from typing import Literal

from django.conf import settings
from django.db import close_old_connections

from .execution import (
    docker_available,
    effective_execution_mode,
    get_max_concurrent_jobs,
)
from .job_workers import append_job_line, run_delete_job, run_list_job
from .models import OnuCleanupJob
from .queue import enqueue_job, process_olt_queue
from .vpn_slot import (
    OltSlotBusyError,
    acquire_container_slot,
    release_container_slot,
)

logger = logging.getLogger(__name__)

Operation = Literal["list", "delete"]


def _docker_env_args() -> list[str]:
    """Variáveis mínimas para o worker Django dentro do container."""
    keys = getattr(
        settings,
        "OLT_WORKER_ENV_KEYS",
        [
            "DATABASE_URL",
            "DB_CONN_MAX_AGE",
            "DB_CONNECT_TIMEOUT",
            "SECRET_KEY",
            "FIELD_ENCRYPTION_KEY",
            "DJANGO_ENV",
            "DEBUG",
            "OLT_OPENVPN_BINARY",
            "OLT_VPN_CONNECT_TIMEOUT",
            "OLT_VPN_POST_CONNECT_DELAY",
            "OLT_LOG_MAX_CHARS",
            "REDIS_URL",
            "USE_REDIS_CACHE",
        ],
    )
    args: list[str] = []
    for key in keys:
        value = os.getenv(key, "")
        if value:
            args.extend(["-e", f"{key}={value}"])
    return args


def _build_docker_command(job_id: int, operation: Operation) -> list[str]:
    binary = getattr(settings, "OLT_DOCKER_BINARY", "docker")
    image = getattr(settings, "OLT_WORKER_IMAGE", "rmsys/olt-worker:latest")
    cmd = [
        binary,
        "run",
        "--rm",
        "--name",
        f"olt-job-{job_id}",
        "--cap-add=NET_ADMIN",
        "--device=/dev/net/tun",
        "--label",
        "rmsys.service=olt-worker",
        "--label",
        f"rmsys.job_id={job_id}",
    ]
    extra_args = getattr(settings, "OLT_DOCKER_RUN_ARGS", "")
    if extra_args.strip():
        cmd.extend(extra_args.strip().split())
    cmd.extend(_docker_env_args())
    cmd.extend(
        [
            "--add-host=host.docker.internal:host-gateway",
            image,
            "olt_run_job",
            "--job-id",
            str(job_id),
            "--operation",
            operation,
        ]
    )
    return cmd


def _container_worker(job_id: int, operation: Operation, slot_index: int) -> None:
    cmd = _build_docker_command(job_id, operation)
    append_job_line(job_id, f"--- Worker container ({settings.OLT_WORKER_IMAGE}) ---")
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=int(getattr(settings, "OLT_CONTAINER_JOB_TIMEOUT", 3600)),
        )
        if proc.stdout.strip():
            append_job_line(job_id, proc.stdout.strip()[-2000:])
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "container exit != 0").strip()
            append_job_line(job_id, f"ERRO container: {err[-1500:]}")
            _mark_failed_if_active(job_id, operation)
    except subprocess.TimeoutExpired:
        append_job_line(job_id, "ERRO: timeout do container OLT.")
        _mark_failed_if_active(job_id, operation)
    except FileNotFoundError:
        append_job_line(job_id, "ERRO: Docker não encontrado no servidor.")
        _mark_failed_if_active(job_id, operation)
    except Exception as exc:
        append_job_line(job_id, f"ERRO ao iniciar container: {exc}")
        _mark_failed_if_active(job_id, operation)
    finally:
        release_container_slot(job_id, slot_index)
        close_old_connections()
        job = OnuCleanupJob.objects.filter(pk=job_id).only("company_id").first()
        if job:
            process_olt_queue(job.company_id)


def _mark_failed_if_active(job_id: int, operation: Operation) -> None:
    from django.db import close_old_connections

    close_old_connections()
    job = OnuCleanupJob.objects.get(pk=job_id)
    active = ("listing",) if operation == "list" else ("running",)
    if job.status in active:
        job.status = "failed"
        job.save(update_fields=["status", "updated_at"])


def _host_thread_worker(job_id: int, operation: Operation) -> None:
    if operation == "list":
        run_list_job(job_id, use_host_vpn_lock=True)
    else:
        run_delete_job(job_id, use_host_vpn_lock=True)


def _dispatch_container(job_id: int, operation: Operation, company) -> None:
    max_parallel = get_max_concurrent_jobs(company)
    try:
        slot = acquire_container_slot(job_id, max_parallel)
    except OltSlotBusyError:
        enqueue_job(job_id, operation)
        return

    thread = threading.Thread(
        target=_container_worker,
        args=(job_id, operation, slot),
        name=f"olt-container-{job_id}",
        daemon=True,
    )
    thread.start()


def _dispatch_host(job_id: int, operation: Operation) -> None:
    thread = threading.Thread(
        target=_host_thread_worker,
        args=(job_id, operation),
        name=f"olt-host-{job_id}-{operation}",
        daemon=True,
    )
    thread.start()


def dispatch_job(job_id: int, operation: Operation) -> None:
    job = OnuCleanupJob.objects.select_related("company").get(pk=job_id)
    mode = effective_execution_mode(job.company)

    if mode == "container":
        if not docker_available():
            append_job_line(
                job_id,
                "AVISO: Docker indisponível — executando no host com mutex VPN.",
            )
            _dispatch_host(job_id, operation)
            return
        _dispatch_container(job_id, operation, job.company)
        return

    _dispatch_host(job_id, operation)


def start_list_offline(job_id: int) -> None:
    dispatch_job(job_id, "list")


def start_delete(job_id: int) -> None:
    dispatch_job(job_id, "delete")


def run_vpn_test_in_container(company, host: str, port: int) -> tuple[bool, str]:
    """Teste VPN via container efêmero (modo container)."""
    if not docker_available():
        from .vpn_manager import test_vpn_to_host

        return test_vpn_to_host(company, host, port)

    binary = getattr(settings, "OLT_DOCKER_BINARY", "docker")
    image = getattr(settings, "OLT_WORKER_IMAGE", "rmsys/olt-worker:latest")
    cmd = [
        binary,
        "run",
        "--rm",
        "--cap-add=NET_ADMIN",
        "--device=/dev/net/tun",
    ]
    cmd.extend(_docker_env_args())
    cmd.extend(
        [
            "--add-host=host.docker.internal:host-gateway",
            image,
            "olt_vpn_test",
            "--company-id",
            str(company.pk),
            "--host",
            host,
            "--port",
            str(port),
        ]
    )
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        log = (proc.stdout or proc.stderr or "").strip()
        return proc.returncode == 0, log
    except Exception as exc:
        return False, str(exc)
