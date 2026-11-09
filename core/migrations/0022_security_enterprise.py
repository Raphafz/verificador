# PASSO 4 — MFA trusted devices + session records

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0021_lgpd_enterprise"),
    ]

    operations = [
        migrations.CreateModel(
            name="TrustedDevice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token_digest", models.CharField(db_index=True, max_length=64)),
                ("device_label", models.CharField(blank=True, max_length=128)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_used_at", models.DateTimeField(auto_now=True)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="trusted_devices",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Dispositivo confiável MFA",
                "verbose_name_plural": "Dispositivos confiáveis MFA",
            },
        ),
        migrations.CreateModel(
            name="UserSessionRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("session_key", models.CharField(db_index=True, max_length=64)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.CharField(blank=True, max_length=512)),
                ("is_current", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_seen_at", models.DateTimeField(auto_now=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="session_records",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Sessão de usuário",
                "verbose_name_plural": "Sessões de usuários",
            },
        ),
        migrations.AddIndex(
            model_name="trusteddevice",
            index=models.Index(fields=["user", "token_digest"], name="core_trust_user_token_idx"),
        ),
        migrations.AddIndex(
            model_name="usersessionrecord",
            index=models.Index(fields=["user", "revoked_at"], name="core_sess_user_revoked_idx"),
        ),
    ]
