# Generated manually for OLT job queue

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("olt_ops", "0008_companyoltexecutionconfig"),
    ]

    operations = [
        migrations.AddField(
            model_name="onucleanupjob",
            name="pending_operation",
            field=models.CharField(
                blank=True,
                choices=[("list", "Listagem"), ("delete", "Exclusão")],
                max_length=8,
                verbose_name="Operação pendente (fila)",
            ),
        ),
        migrations.AlterField(
            model_name="onucleanupjob",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "Rascunho"),
                    ("queued", "Na fila"),
                    ("listing", "Listando offline"),
                    ("ready", "Pronto para excluir"),
                    ("running", "Excluindo"),
                    ("done", "Concluído"),
                    ("failed", "Falhou"),
                ],
                default="draft",
                max_length=16,
            ),
        ),
    ]
