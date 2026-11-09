from django.db import migrations, models

import core.encrypted_fields


class Migration(migrations.Migration):

    dependencies = [
        ("olt_ops", "0005_encrypt_sensitive_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="oltequipment",
            name="enable_password",
            field=core.encrypted_fields.EncryptedCharField(
                blank=True,
                help_text=(
                    "Opcional. Senha após o comando enable (ex.: zxr10). "
                    "Vazio = usa a mesma senha de login."
                ),
                max_length=512,
                verbose_name="Senha enable (ZTE)",
            ),
        ),
    ]
