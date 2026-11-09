from django.db import migrations, models
import django.db.models.deletion


def migrate_legacy_whatsapp_to_lines(apps, schema_editor):
    AlertBridgeConfig = apps.get_model("alerts", "AlertBridgeConfig")
    WhatsAppLine = apps.get_model("alerts", "WhatsAppLine")

    for config in AlertBridgeConfig.objects.all():
        mode = getattr(config, "whatsapp_login_mode", None) or "qr"
        phone = getattr(config, "whatsapp_pairing_phone", "") or ""
        if WhatsAppLine.objects.filter(company_id=config.company_id).exists():
            continue
        WhatsAppLine.objects.create(
            company_id=config.company_id,
            label="Chip principal",
            login_mode=mode,
            pairing_phone=phone,
            is_active=True,
            is_default=True,
            sort_order=0,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0012_company_saas_modules"),
        ("alerts", "0002_alertbridgeconfig_whatsapp_login"),
    ]

    operations = [
        migrations.CreateModel(
            name="WhatsAppLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("label", models.CharField(help_text='Ex: "Chip Alertas 1", "Operação RJ"', max_length=80, verbose_name="Nome / identificação")),
                ("login_mode", models.CharField(choices=[("qr", "QR Code"), ("pairing", "Código de pareamento")], default="qr", max_length=16, verbose_name="Modo de conexão")),
                ("pairing_phone", models.CharField(blank=True, help_text="DDI+DDD+número, só dígitos. Obrigatório no modo pareamento.", max_length=20, verbose_name="Número (pareamento)")),
                ("is_active", models.BooleanField(default=True, verbose_name="Linha ativa")),
                ("is_default", models.BooleanField(default=False, help_text="Chip padrão que envia as mensagens do Telegram.", verbose_name="Usar para enviar alertas")),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="whatsapp_lines", to="core.company", verbose_name="Empresa")),
            ],
            options={
                "verbose_name": "Linha WhatsApp",
                "verbose_name_plural": "Linhas WhatsApp",
                "ordering": ["-is_default", "sort_order", "label"],
            },
        ),
        migrations.AddConstraint(
            model_name="whatsappline",
            constraint=models.UniqueConstraint(fields=("company", "label"), name="alerts_whatsappline_unique_label_per_company"),
        ),
        migrations.RunPython(migrate_legacy_whatsapp_to_lines, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="alertbridgeconfig",
            name="whatsapp_login_mode",
        ),
        migrations.RemoveField(
            model_name="alertbridgeconfig",
            name="whatsapp_pairing_phone",
        ),
    ]
