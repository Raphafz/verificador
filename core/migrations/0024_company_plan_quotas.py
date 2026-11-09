# Generated manually for plan/quota enforcement

from django.db import migrations, models


def infer_plan_codes(apps, schema_editor):
    Company = apps.get_model("core", "Company")
    for company in Company.objects.all():
        if company.module_olt:
            company.plan_code = "XL"
        elif company.module_alertas:
            company.plan_code = "G"
        else:
            company.plan_code = "M"
        company.save(update_fields=["plan_code"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0023_rename_core_dsr_status_type_created_idx_core_datasu_status_43d46e_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="company",
            name="plan_code",
            field=models.CharField(
                choices=[
                    ("P", "P — Essencial"),
                    ("M", "M — Comercial"),
                    ("G", "G — Operação"),
                    ("XL", "XL — Rede"),
                ],
                default="M",
                help_text="Define limites de usuários, mapas, viabilidade e módulos.",
                max_length=4,
                verbose_name="Plano comercial",
            ),
        ),
        migrations.AddField(
            model_name="company",
            name="quota_enforcement",
            field=models.BooleanField(
                default=True,
                help_text="Desmarque apenas para acordos especiais (RM).",
                verbose_name="Aplicar limites do plano",
            ),
        ),
        migrations.AddField(
            model_name="company",
            name="quota_override_users",
            field=models.PositiveIntegerField(
                blank=True, null=True, verbose_name="Override: usuários"
            ),
        ),
        migrations.AddField(
            model_name="company",
            name="quota_override_maps",
            field=models.PositiveIntegerField(
                blank=True, null=True, verbose_name="Override: mapas"
            ),
        ),
        migrations.AddField(
            model_name="company",
            name="quota_override_viability_month",
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                verbose_name="Override: consultas viabilidade/mês",
            ),
        ),
        migrations.AddField(
            model_name="company",
            name="quota_override_whatsapp_chips",
            field=models.PositiveIntegerField(
                blank=True, null=True, verbose_name="Override: chips WhatsApp"
            ),
        ),
        migrations.AddField(
            model_name="company",
            name="quota_override_alert_phones",
            field=models.PositiveIntegerField(
                blank=True, null=True, verbose_name="Override: números de alerta"
            ),
        ),
        migrations.AddField(
            model_name="company",
            name="quota_override_alert_messages_month",
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                verbose_name="Override: mensagens alerta/mês",
            ),
        ),
        migrations.AddField(
            model_name="company",
            name="quota_override_olts",
            field=models.PositiveIntegerField(
                blank=True, null=True, verbose_name="Override: OLTs"
            ),
        ),
        migrations.AddField(
            model_name="company",
            name="quota_override_olt_jobs_month",
            field=models.PositiveIntegerField(
                blank=True, null=True, verbose_name="Override: jobs ONU/mês"
            ),
        ),
        migrations.RunPython(infer_plan_codes, migrations.RunPython.noop),
    ]
