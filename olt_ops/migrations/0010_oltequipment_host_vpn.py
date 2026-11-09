from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("olt_ops", "0009_onu_job_queue"),
    ]

    operations = [
        migrations.AddField(
            model_name="oltequipment",
            name="host_vpn",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Opcional. IP/hostname após conectar na VPN (vazio = usa o campo Host).",
                max_length=255,
                verbose_name="Host via VPN",
            ),
        ),
    ]
