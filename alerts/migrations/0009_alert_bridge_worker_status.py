# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("alerts", "0008_encrypt_telegram_token"),
    ]

    operations = [
        migrations.CreateModel(
            name="AlertBridgeWorkerStatus",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("last_seen_at", models.DateTimeField(blank=True, null=True, verbose_name="Último poll")),
                ("last_ip", models.GenericIPAddressField(blank=True, null=True, verbose_name="IP do worker")),
                (
                    "last_configs_count",
                    models.PositiveIntegerField(default=0, verbose_name="Configs no último poll"),
                ),
                ("worker_version", models.CharField(blank=True, max_length=64, verbose_name="Versão reportada")),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Status do worker alert-bridge",
                "verbose_name_plural": "Status do worker alert-bridge",
            },
        ),
    ]
