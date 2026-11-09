# Generated for PASSO 3 — LGPD enterprise

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0020_rename_core_secur_event_t_8a1f2d_idx_core_securi_event_t_a1f2eb_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="datasubjectrequest",
            name="last_error",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="datasubjectrequest",
            name="retry_count",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="datasubjectrequest",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AlterField(
            model_name="datasubjectrequest",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pendente"),
                    ("processing", "Em processamento"),
                    ("completed", "Concluída"),
                    ("rejected", "Rejeitada"),
                    ("failed", "Falhou"),
                ],
                default="pending",
                max_length=16,
            ),
        ),
        migrations.AddIndex(
            model_name="datasubjectrequest",
            index=models.Index(
                fields=["status", "request_type", "created_at"],
                name="core_dsr_status_type_created_idx",
            ),
        ),
        migrations.CreateModel(
            name="LgpdExportDownload",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("export_format", models.CharField(default="zip", max_length=8)),
                ("storage_path", models.CharField(blank=True, max_length=512)),
                ("file_size", models.PositiveIntegerField(default=0)),
                ("checksum_sha256", models.CharField(blank=True, max_length=64)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("download_count", models.PositiveSmallIntegerField(default=0)),
                ("max_downloads", models.PositiveSmallIntegerField(default=5)),
                ("last_downloaded_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lgpd_exports",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Download de exportação LGPD",
                "verbose_name_plural": "Downloads de exportação LGPD",
                "ordering": ["-created_at"],
            },
        ),
    ]
