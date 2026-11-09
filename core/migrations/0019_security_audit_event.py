# Generated manually — trilha de auditoria Fase 3

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0018_company_cnpj_encrypted_hash"),
    ]

    operations = [
        migrations.CreateModel(
            name="SecurityAuditEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_type", models.CharField(db_index=True, max_length=64)),
                ("severity", models.CharField(choices=[("info", "Info"), ("warning", "Aviso"), ("critical", "Crítico")], db_index=True, default="info", max_length=16)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("request_id", models.CharField(blank=True, db_index=True, max_length=64)),
                ("correlation_id", models.CharField(blank=True, db_index=True, max_length=64)),
                ("details", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="security_audit_events", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Evento de auditoria",
                "verbose_name_plural": "Eventos de auditoria",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="securityauditevent",
            index=models.Index(fields=["event_type", "created_at"], name="core_secur_event_t_8a1f2d_idx"),
        ),
        migrations.AddIndex(
            model_name="securityauditevent",
            index=models.Index(fields=["severity", "created_at"], name="core_secur_severit_4b2c1a_idx"),
        ),
    ]
