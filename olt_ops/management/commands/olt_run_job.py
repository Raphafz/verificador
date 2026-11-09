"""Executa um job OLT dentro de container Docker (rede isolada)."""
from __future__ import annotations

from django.core.management.base import BaseCommand

from olt_ops.job_workers import run_delete_job, run_list_job


class Command(BaseCommand):
    help = "Executa job OLT (list/delete) — entrypoint do container olt-worker."

    def add_arguments(self, parser):
        parser.add_argument("--job-id", type=int, required=True)
        parser.add_argument(
            "--operation",
            choices=("list", "delete"),
            required=True,
        )

    def handle(self, *args, **options):
        job_id = options["job_id"]
        operation = options["operation"]
        self.stdout.write(f"Iniciando job {job_id} ({operation}) no worker isolado…")

        if operation == "list":
            run_list_job(job_id, use_host_vpn_lock=False)
        else:
            run_delete_job(job_id, use_host_vpn_lock=False)

        self.stdout.write(self.style.SUCCESS(f"Job {job_id} finalizado."))
