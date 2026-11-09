from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("olt_ops", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="oltequipment",
            name="list_command",
            field=models.CharField(
                blank=True,
                help_text="Vazio = padrão Huawei/ZTE. Ex: display ont info 0 1 14 all",
                max_length=255,
                verbose_name="Comando listar offline",
            ),
        ),
    ]
