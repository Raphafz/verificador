# LGPD — GeocodingCache: hash SHA-256, TTL, sem endereço completo

from datetime import timedelta

from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


def _migrate_legacy_geocoding(apps, schema_editor):
    GeocodingCache = apps.get_model("ftth_viewer", "GeocodingCache")
    from ftth_viewer.geocoding_privacy import (
        anonymize_display_name,
        cache_key_for_query,
        compute_expires_at,
        is_coord_cache_key,
    )

    retention_days = int(getattr(settings, "CACHE_RETENTION_DAYS", 90))
    seen_hashes = set()
    batch = []

    for row in GeocodingCache.objects.all().iterator():
        legacy_key = (row.endereco or "").strip()
        if not legacy_key:
            continue

        try:
            key_hash, qtype = cache_key_for_query(legacy_key)
        except Exception:
            continue

        if key_hash in seen_hashes:
            continue
        seen_hashes.add(key_hash)

        hint_source = getattr(row, "endereco_completo", "") or legacy_key
        if is_coord_cache_key(legacy_key):
            hint = anonymize_display_name(hint_source)
        else:
            hint = anonymize_display_name(hint_source)

        expires = compute_expires_at(row.updated_at)
        max_exp = row.updated_at + timedelta(days=retention_days)
        if expires > max_exp:
            expires = max_exp

        batch.append(
            GeocodingCache(
                id=row.id,
                cache_key_hash=key_hash,
                query_type=qtype,
                lat=row.lat,
                lng=row.lng,
                locality_hint=(hint or "")[:120],
                expires_at=expires,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
        )

    if not batch:
        return

    GeocodingCache.objects.bulk_update(
        batch,
        ["cache_key_hash", "query_type", "lat", "lng", "locality_hint", "expires_at"],
        batch_size=500,
    )


def _delete_unmigrated_rows(apps, schema_editor):
    GeocodingCache = apps.get_model("ftth_viewer", "GeocodingCache")
    GeocodingCache.objects.filter(cache_key_hash__isnull=True).delete()


def _noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("ftth_viewer", "0005_rename_ftth_viewer_lat_mapas_idx_ftth_viewer_lat_b315ec_idx"),
    ]

    operations = [
        migrations.AddField(
            model_name="geocodingcache",
            name="cache_key_hash",
            field=models.CharField(
                db_index=True,
                max_length=64,
                null=True,
                unique=True,
                verbose_name="Hash da consulta (SHA-256)",
            ),
        ),
        migrations.AddField(
            model_name="geocodingcache",
            name="query_type",
            field=models.CharField(
                choices=[("address", "Endereço → coordenadas"), ("reverse", "Coordenadas → região")],
                db_index=True,
                default="address",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="geocodingcache",
            name="locality_hint",
            field=models.CharField(
                blank=True,
                help_text="Apenas cidade/UF/país — sem logradouro",
                max_length=120,
                verbose_name="Região anonimizada",
            ),
        ),
        migrations.AddField(
            model_name="geocodingcache",
            name="expires_at",
            field=models.DateTimeField(db_index=True, null=True, verbose_name="Expira em"),
        ),
        migrations.RunPython(_migrate_legacy_geocoding, _noop_reverse),
        migrations.RunPython(_delete_unmigrated_rows, _noop_reverse),
        migrations.RemoveField(model_name="geocodingcache", name="endereco"),
        migrations.RemoveField(model_name="geocodingcache", name="endereco_completo"),
        migrations.AlterField(
            model_name="geocodingcache",
            name="cache_key_hash",
            field=models.CharField(
                db_index=True,
                max_length=64,
                unique=True,
                verbose_name="Hash da consulta (SHA-256)",
            ),
        ),
        migrations.AlterField(
            model_name="geocodingcache",
            name="expires_at",
            field=models.DateTimeField(db_index=True, verbose_name="Expira em"),
        ),
        migrations.AddIndex(
            model_name="geocodingcache",
            index=models.Index(fields=["expires_at", "query_type"], name="ftth_geo_exp_type_idx"),
        ),
        migrations.AddIndex(
            model_name="geocodingcache",
            index=models.Index(fields=["updated_at"], name="ftth_geo_updated_idx"),
        ),
    ]
