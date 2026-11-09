"""Verifica heartbeat do worker alert-bridge (cron / systemd timer)."""
from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import mail_admins
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Alerta se o worker alert-bridge não fez poll recentemente."

    def handle(self, *args, **options):
        from alerts.models import AlertBridgeWorkerStatus
        from core.models import Company

        status = AlertBridgeWorkerStatus.get_status()
        alertas_ativos = Company.objects.filter(is_active=True, module_alertas=True).exists()

        if not alertas_ativos:
            self.stdout.write("Módulo alertas inativo em todas as empresas — skip.")
            return

        self.stdout.write(status["message"])

        if status.get("healthy"):
            return

        msg = f"ALERTA: {status['message']}"
        logger.error(msg)

        try:
            import sentry_sdk

            if getattr(settings, "SENTRY_DSN", "").strip():
                sentry_sdk.capture_message(msg, level="error")
        except Exception:
            logger.exception("Falha ao enviar alerta Sentry")

        try:
            mail_admins("Worker alert-bridge offline", msg, fail_silently=True)
        except Exception:
            logger.exception("Falha ao enviar e-mail de alerta bridge")
