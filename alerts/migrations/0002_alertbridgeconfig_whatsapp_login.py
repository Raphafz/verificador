from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("alerts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="alertbridgeconfig",
            name="whatsapp_login_mode",
            field=models.CharField(
                choices=[("qr", "QR Code"), ("pairing", "Código de pareamento")],
                default="qr",
                max_length=16,
                verbose_name="Conexão WhatsApp",
            ),
        ),
        migrations.AddField(
            model_name="alertbridgeconfig",
            name="whatsapp_pairing_phone",
            field=models.CharField(
                blank=True,
                max_length=20,
                verbose_name="Número WhatsApp (pareamento)",
                help_text="DDI + DDD + número, só dígitos. Ex: 5521999999999",
            ),
        ),
    ]
