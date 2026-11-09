from django.db import migrations, models

import core.encrypted_fields


def encrypt_existing_olt_secrets(apps, schema_editor):
    from core.field_encryption import encrypt_value, is_encrypted

    OltEquipment = apps.get_model("olt_ops", "OltEquipment")
    CompanyVpnConfig = apps.get_model("olt_ops", "CompanyVpnConfig")
    for olt in OltEquipment.objects.exclude(password="").iterator():
        if olt.password and not is_encrypted(olt.password):
            olt.password = encrypt_value(olt.password)
            olt.save(update_fields=["password"])
    for vpn in CompanyVpnConfig.objects.all().iterator():
        changed = []
        for field in ("ipsec_psk", "vpn_password"):
            val = getattr(vpn, field) or ""
            if val and not is_encrypted(val):
                setattr(vpn, field, encrypt_value(val))
                changed.append(field)
        if changed:
            vpn.save(update_fields=changed)


class Migration(migrations.Migration):

    dependencies = [
        ("olt_ops", "0004_companyvpnconfig_l2tp_ipsec"),
    ]

    operations = [
        migrations.AlterField(
            model_name="oltequipment",
            name="password",
            field=core.encrypted_fields.EncryptedCharField(
                help_text="Armazenado criptografado no banco; restrinja acesso por perfil.",
                max_length=512,
            ),
        ),
        migrations.AlterField(
            model_name="companyvpnconfig",
            name="ipsec_psk",
            field=core.encrypted_fields.EncryptedCharField(
                blank=True,
                help_text="PSK configurada no gateway / no Windows como “chave”.",
                max_length=512,
                verbose_name="Chave pré-compartilhada (IPsec)",
            ),
        ),
        migrations.AlterField(
            model_name="companyvpnconfig",
            name="vpn_password",
            field=core.encrypted_fields.EncryptedCharField(
                blank=True,
                help_text="Usado se o .ovpn tiver auth-user-pass.",
                max_length=512,
                verbose_name="Senha VPN",
            ),
        ),
        migrations.RunPython(encrypt_existing_olt_secrets, migrations.RunPython.noop),
    ]
