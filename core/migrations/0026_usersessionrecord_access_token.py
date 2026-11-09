from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0025_company_billing"),
    ]

    operations = [
        migrations.AddField(
            model_name="usersessionrecord",
            name="access_token_digest",
            field=models.CharField(blank=True, db_index=True, max_length=64),
        ),
        migrations.AddField(
            model_name="usersessionrecord",
            name="expires_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
    ]
