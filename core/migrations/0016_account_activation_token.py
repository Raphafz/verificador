# LGPD — ativação de conta sem senha em e-mail

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0015_rename_core_consent_user_doc_idx_core_consen_user_id_95572c_idx"),
    ]

    operations = [
        migrations.CreateModel(
            name="AccountActivationToken",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token_digest", models.CharField(db_index=True, max_length=64, unique=True)),
                (
                    "django_token",
                    models.CharField(
                        blank=True,
                        help_text="Token auxiliar (PasswordResetTokenGenerator) validado no servidor",
                        max_length=128,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("used_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("created_ip", models.GenericIPAddressField(blank=True, null=True)),
                ("used_ip", models.GenericIPAddressField(blank=True, null=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="activation_tokens",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Usuário",
                    ),
                ),
            ],
            options={
                "verbose_name": "Token de ativação de conta",
                "verbose_name_plural": "Tokens de ativação de conta",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="accountactivationtoken",
            index=models.Index(fields=["user", "used_at", "expires_at"], name="core_act_user_used_exp_idx"),
        ),
    ]
