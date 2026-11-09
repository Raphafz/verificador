# Generated manually — execução OLT por empresa

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("olt_ops", "0007_alter_oltequipment_list_command"),
    ]

    operations = [
        migrations.CreateModel(
            name="CompanyOltExecutionConfig",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "worker_mode",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("", "Padrão global (.env)"),
                            ("host", "Processo no host (thread + mutex VPN)"),
                            ("container", "Container Docker (rede isolada por job)"),
                        ],
                        default="",
                        help_text="Vazio = usa OLT_EXECUTION_MODE do .env",
                        max_length=16,
                        verbose_name="Modo de execução",
                    ),
                ),
                (
                    "max_concurrent_jobs",
                    models.PositiveSmallIntegerField(
                        default=0,
                        help_text="0 = usa OLT_MAX_PARALLEL_JOBS do .env",
                        verbose_name="Jobs paralelos máx.",
                    ),
                ),
                ("notes", models.TextField(blank=True, verbose_name="Observações")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="olt_execution",
                        to="core.company",
                        verbose_name="Empresa",
                    ),
                ),
            ],
            options={
                "verbose_name": "Execução OLT da empresa",
                "verbose_name_plural": "Execuções OLT das empresas",
            },
        ),
    ]
