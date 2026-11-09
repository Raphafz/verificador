from django.db import migrations

import core.encrypted_fields


def encrypt_tokens(apps, schema_editor):
    from core.field_encryption import encrypt_value, is_encrypted

    AlertBridgeConfig = apps.get_model("alerts", "AlertBridgeConfig")
    for cfg in AlertBridgeConfig.objects.exclude(telegram_bot_token="").iterator():
        tok = cfg.telegram_bot_token
        if tok and not is_encrypted(tok):
            cfg.telegram_bot_token = encrypt_value(tok)
            cfg.save(update_fields=["telegram_bot_token"])


class Migration(migrations.Migration):

    dependencies = [
        ("alerts", "0007_alter_alertbridgeconfig_filter_enabled_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="alertbridgeconfig",
            name="telegram_bot_token",
            field=core.encrypted_fields.EncryptedCharField(
                blank=True,
                help_text="Obtenha em @BotFather",
                max_length=512,
                verbose_name="Token do bot Telegram",
            ),
        ),
        migrations.RunPython(encrypt_tokens, migrations.RunPython.noop),
    ]
