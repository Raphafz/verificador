from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0011_add_db_index_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="company",
            name="module_verificador",
            field=models.BooleanField(
                default=True,
                help_text="Mapas CTO e verificação de viabilidade",
                verbose_name="Módulo Verificador FTTH",
            ),
        ),
        migrations.AddField(
            model_name="company",
            name="module_alertas",
            field=models.BooleanField(
                default=False,
                help_text="Bridge Telegram → WhatsApp para monitoramento",
                verbose_name="Módulo Alertas",
            ),
        ),
        migrations.AddField(
            model_name="company",
            name="module_olt",
            field=models.BooleanField(
                default=False,
                help_text="Gestão de ONTs offline em OLT Huawei/ZTE",
                verbose_name="Módulo OLT/ONU",
            ),
        ),
    ]
