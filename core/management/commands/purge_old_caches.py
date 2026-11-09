"""Remove caches de geocoding/viabilidade (TTL + retenção LGPD)."""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from ftth_viewer.models import GeocodingCache, ViabilidadeCache
from ftth_viewer.utils import purge_expired_geocoding_cache


class Command(BaseCommand):
    help = "Remove caches expirados (TTL) e entradas antigas de geocoding/viabilidade"

    def add_arguments(self, parser):
        from django.conf import settings

        default_days = int(getattr(settings, "CACHE_RETENTION_DAYS", 90))
        parser.add_argument(
            "--days",
            type=int,
            default=default_days,
            help=f"Idade máxima em dias (padrão: {default_days}, CACHE_RETENTION_DAYS)",
        )
        parser.add_argument(
            "--skip-ttl",
            action="store_true",
            help="Não remover entradas com expires_at vencido (apenas retenção por dias)",
        )

    def handle(self, *args, **options):
        ttl_removed = 0 if options["skip_ttl"] else purge_expired_geocoding_cache()

        cutoff = timezone.now() - timedelta(days=options["days"])
        geo_retention, _ = GeocodingCache.objects.filter(updated_at__lt=cutoff).delete()
        via_deleted, _ = ViabilidadeCache.objects.filter(created_at__lt=cutoff).delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Geocoding: {ttl_removed} expirados (TTL), {geo_retention} retenção (> {options['days']}d); "
                f"Viabilidade: {via_deleted} removidos"
            )
        )
