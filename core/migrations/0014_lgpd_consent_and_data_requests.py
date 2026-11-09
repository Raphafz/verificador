# Generated manually — LGPD consentimento e solicitações de titulares
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0013_ticketnotification_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="ConsentRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("document_type", models.CharField(
                    choices=[
                        ("terms", "Termos de Uso"),
                        ("privacy", "Política de Privacidade"),
                        ("cookies", "Política de Cookies"),
                    ],
                    max_length=32,
                )),
                ("document_version", models.CharField(help_text="Versão do documento aceito (ex.: 2026-05-21)", max_length=32)),
                ("accepted_at", models.DateTimeField(auto_now_add=True, verbose_name="Aceito em")),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.CharField(blank=True, max_length=512)),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="consent_records",
                    to=settings.AUTH_USER_MODEL,
                    verbose_name="Usuário",
                )),
            ],
            options={
                "verbose_name": "Registro de consentimento",
                "verbose_name_plural": "Registros de consentimento",
            },
        ),
        migrations.CreateModel(
            name="DataSubjectRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("request_type", models.CharField(
                    choices=[
                        ("export", "Exportação de dados"),
                        ("delete", "Eliminação de conta"),
                        ("rectify", "Correção de dados"),
                        ("other", "Outro"),
                    ],
                    max_length=16,
                )),
                ("status", models.CharField(
                    choices=[
                        ("pending", "Pendente"),
                        ("completed", "Concluída"),
                        ("rejected", "Rejeitada"),
                    ],
                    default="pending",
                    max_length=16,
                )),
                ("details", models.TextField(blank=True)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="data_subject_requests",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "verbose_name": "Solicitação do titular",
                "verbose_name_plural": "Solicitações dos titulares",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="consentrecord",
            index=models.Index(fields=["user", "document_type", "document_version"], name="core_consent_user_doc_idx"),
        ),
        migrations.AddConstraint(
            model_name="consentrecord",
            constraint=models.UniqueConstraint(
                fields=("user", "document_type", "document_version"),
                name="core_consent_unique_per_version",
            ),
        ),
    ]
