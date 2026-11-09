"""
Remove log_output antigo de jobs OLT (retenção LGPD/operacional).

Cron sugerido (produção, diário 03:00):
  0 3 * * * cd /var/www/saas-viabilidade && python manage.py purge_olt_logs --days=7
"""
from __future__ import annotations

import os

from django.core.management.base import BaseCommand
from django.utils import timezone

from olt_ops.models import OnuCleanupJob


class Command(BaseCommand):
    help = "Purge de log_output em jobs OLT concluídos/falhos após N dias"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=int(os.getenv("OLT_LOG_RETENTION_DAYS", "7")),
            help="Idade mínima em dias (default: OLT_LOG_RETENTION_DAYS ou 7)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Apenas conta registros, não apaga",
        )

    def handle(self, *args, **options):
        days = max(1, options["days"])
        cutoff = timezone.now() - timezone.timedelta(days=days)
        qs = OnuCleanupJob.objects.filter(
            updated_at__lt=cutoff,
            status__in=("done", "failed"),
        ).exclude(log_output="")
        count = qs.count()
        if options["dry_run"]:
            self.stdout.write(f"[dry-run] {count} job(s) teriam log_output limpo (>{days} dias)")
            return
        updated = qs.update(log_output="")
        self.stdout.write(self.style.SUCCESS(f"log_output limpo em {updated} job(s) (retenção {days}d)"))
