# LGPD — CNPJ criptografado + hash indexável

from django.db import migrations, models

from core.cnpj_utils import cnpj_digits, format_cnpj, hash_cnpj
from core.field_encryption import encrypt_value, is_encrypted


def _migrate_cnpj_forward(apps, schema_editor):
    Company = apps.get_model("core", "Company")
    batch = []
    for company in Company.objects.all().iterator():
        raw = company.cnpj or ""
        if is_encrypted(raw):
            try:
                from core.field_encryption import decrypt_value
                plain = decrypt_value(raw)
            except Exception:
                plain = raw
        else:
            plain = raw
        digits = cnpj_digits(plain)
        if len(digits) != 14:
            continue
        formatted = format_cnpj(digits)
        company.cnpj = encrypt_value(formatted)
        company.cnpj_hash = hash_cnpj(digits)
        batch.append(company)
    if batch:
        Company.objects.bulk_update(batch, ["cnpj", "cnpj_hash"], batch_size=200)


def _noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0017_rename_core_act_user_used_exp_idx_core_accoun_user_id_d002cd_idx"),
    ]

    operations = [
        migrations.AddField(
            model_name="company",
            name="cnpj_hash",
            field=models.CharField(
                db_index=True,
                editable=False,
                max_length=64,
                null=True,
                unique=True,
                verbose_name="Hash CNPJ (busca)",
            ),
        ),
        migrations.RunPython(_migrate_cnpj_forward, _noop),
        migrations.RemoveIndex(
            model_name="company",
            name="core_compan_cnpj_50a6e8_idx",
        ),
        migrations.AlterField(
            model_name="company",
            name="cnpj",
            field=models.CharField(max_length=512, verbose_name="CNPJ"),
        ),
        migrations.AlterField(
            model_name="company",
            name="cnpj_hash",
            field=models.CharField(
                blank=True,
                db_index=True,
                editable=False,
                max_length=64,
                null=True,
                unique=True,
                verbose_name="Hash CNPJ (busca)",
            ),
        ),
    ]
