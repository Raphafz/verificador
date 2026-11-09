"""
Checklist P2 (RELATORIO-P2.md): consentimento, portal titular, Argon2, retenção.
"""
import os

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Verifica e aplica checklist LGPD P2"

    def add_arguments(self, parser):
        parser.add_argument(
            "--purge-caches",
            action="store_true",
            help="Executa purge_old_caches com CACHE_RETENTION_DAYS",
        )
        parser.add_argument(
            "--dry-run-purge",
            action="store_true",
            help="Simula purge (apenas exibe contagem)",
        )

    def handle(self, *args, **options):
        from core.models import ConsentRecord, DataSubjectRequest

        # Argon2
        hashers = settings.PASSWORD_HASHERS
        if hashers and "Argon2" in hashers[0]:
            self.stdout.write(self.style.SUCCESS("PASSWORD_HASHERS: Argon2 ativo"))
        else:
            self.stdout.write(self.style.ERROR("Argon2 não é o hasher principal"))

        # Consentimento
        version = getattr(settings, "LEGAL_DOCUMENT_VERSION", None) or os.getenv(
            "LEGAL_DOCUMENT_VERSION", "2026-05-21"
        )
        self.stdout.write(f"LEGAL_DOCUMENT_VERSION: {version}")
        self.stdout.write(f"ConsentRecord no banco: {ConsentRecord.objects.count()}")
        self.stdout.write(f"DataSubjectRequest no banco: {DataSubjectRequest.objects.count()}")

        # Rotas
        routes = [
            "/consent-required/",
            "/meus-dados/",
            "/meus-dados/exportar/",
            "/encarregado-dados/",
        ]
        self.stdout.write("Rotas LGPD: " + ", ".join(routes))

        # Rate limit
        if settings.DEBUG:
            self.stdout.write(
                self.style.WARNING(
                    "DEBUG=True: rate limit desligado (use FORCE_RATE_LIMIT=true para testar)"
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS("Produção: rate limit ativo"))

        days = int(getattr(settings, "CACHE_RETENTION_DAYS", 90))
        self.stdout.write(f"CACHE_RETENTION_DAYS: {days}")

        if options["purge_caches"]:
            call_command("purge_old_caches", days=days)
        elif options["dry_run_purge"]:
            from datetime import timedelta

            from django.utils import timezone

            from ftth_viewer.models import GeocodingCache, ViabilidadeCache

            cutoff = timezone.now() - timedelta(days=days)
            geo = GeocodingCache.objects.filter(updated_at__lt=cutoff).count()
            via = ViabilidadeCache.objects.filter(created_at__lt=cutoff).count()
            self.stdout.write(f"Purge simulado: {geo} geocoding + {via} viabilidade (> {days}d)")

        self.stdout.write("")
        self.stdout.write("Cron sugerido (Linux):")
        self.stdout.write(
            f"  0 3 * * 0 cd /var/www/saas-viabilidade && python manage.py purge_old_caches --days={days}"
        )
        self.stdout.write("")
        self.stdout.write("Pendente organizacional: docs/ROPA.md, docs/SUBOPERADORES-LGPD.md")
