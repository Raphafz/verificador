from django.db import migrations, models


def default_send_alerts_from_default(apps, schema_editor):
    WhatsAppLine = apps.get_model("alerts", "WhatsAppLine")
    WhatsAppLine.objects.filter(is_default=True).update(send_alerts=True)


class Migration(migrations.Migration):

    dependencies = [
        ("alerts", "0003_whatsappline_multi"),
    ]

    operations = [
        migrations.AddField(
            model_name="whatsappline",
            name="send_alerts",
            field=models.BooleanField(
                default=False,
                help_text="Se marcado, este chip envia alertas do Telegram (pode marcar vários).",
                verbose_name="Enviar alertas",
            ),
        ),
        migrations.RunPython(default_send_alerts_from_default, migrations.RunPython.noop),
    ]
