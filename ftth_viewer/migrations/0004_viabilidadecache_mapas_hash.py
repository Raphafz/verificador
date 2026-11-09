from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ftth_viewer", "0003_make_company_required"),
    ]

    operations = [
        migrations.AddField(
            model_name="viabilidadecache",
            name="mapas_hash",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                help_text="Hash dos IDs dos mapas ativos quando a verificação foi feita",
                max_length=500,
            ),
        ),
        migrations.AlterUniqueTogether(
            name="viabilidadecache",
            unique_together={("lat", "lon", "company", "mapas_hash")},
        ),
        migrations.RemoveIndex(
            model_name="viabilidadecache",
            name="ftth_viewer_lat_e90c5a_idx",
        ),
        migrations.AddIndex(
            model_name="viabilidadecache",
            index=models.Index(
                fields=["lat", "lon", "company", "mapas_hash"],
                name="ftth_viewer_lat_mapas_idx",
            ),
        ),
    ]
