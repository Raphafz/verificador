# Generated manually
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ftth_viewer', '0002_remove_viabilidadecache_ftth_viewer_lat_608d76_idx_and_more'),
        ('core', '0006_add_flask_integration_fields'),
    ]

    operations = [
        # Excluir todos os caches sem empresa (se houver algum)
        migrations.RunSQL(
            "DELETE FROM ftth_viewer_viabilidadecache WHERE company_id IS NULL;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        # Tornar company obrigatório
        migrations.AlterField(
            model_name='viabilidadecache',
            name='company',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='viability_caches',
                to='core.company',
                verbose_name='Empresa',
                null=False
            ),
        ),
    ]

