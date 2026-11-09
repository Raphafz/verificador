"""Purge dedicado do cache de geocoding (TTL + retenção)."""
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from ftth_viewer.models import GeocodingCache
from ftth_viewer.utils import purge_expired_geocoding_cache


class Command(BaseCommand):
    help = "Remove entradas expiradas do GeocodingCache e aplica retenção por idade"

    def add_arguments(self, parser):
        default_days = int(getattr(settings, "CACHE_RETENTION_DAYS", 90))
        parser.add_argument("--days", type=int, default=default_days)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        now = timezone.now()
        ttl_qs = GeocodingCache.objects.filter(expires_at__lt=now)
        retention_cutoff = now - timedelta(days=options["days"])
        retention_qs = GeocodingCache.objects.filter(updated_at__lt=retention_cutoff)

        if options["dry_run"]:
            self.stdout.write(
                f"[dry-run] TTL: {ttl_qs.count()}, retenção {options['days']}d: {retention_qs.count()}"
            )
            return

        ttl_removed = purge_expired_geocoding_cache()
        retention_removed, _ = retention_qs.delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Removidos — TTL: {ttl_removed}, retenção: {retention_removed}"
            )
        )
