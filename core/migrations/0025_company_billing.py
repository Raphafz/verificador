# Generated manually

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0024_company_plan_quotas"),
    ]

    operations = [
        migrations.CreateModel(
            name="CompanyBilling",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "provider",
                    models.CharField(
                        choices=[("manual", "Manual (RM)"), ("asaas", "Asaas")],
                        default="manual",
                        max_length=16,
                        verbose_name="Provedor",
                    ),
                ),
                ("asaas_customer_id", models.CharField(blank=True, max_length=64, verbose_name="ID cliente Asaas")),
                (
                    "asaas_subscription_id",
                    models.CharField(blank=True, max_length=64, verbose_name="ID assinatura Asaas"),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("trial", "Trial"),
                            ("active", "Ativa"),
                            ("past_due", "Inadimplente"),
                            ("suspended", "Suspensa"),
                            ("cancelled", "Cancelada"),
                        ],
                        default="trial",
                        max_length=16,
                        verbose_name="Status cobrança",
                    ),
                ),
                ("last_payment_at", models.DateTimeField(blank=True, null=True, verbose_name="Último pagamento")),
                ("last_webhook_at", models.DateTimeField(blank=True, null=True, verbose_name="Último webhook")),
                ("last_webhook_event", models.CharField(blank=True, max_length=64, verbose_name="Último evento")),
                ("notes", models.TextField(blank=True, verbose_name="Observações RM")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="billing",
                        to="core.company",
                        verbose_name="Empresa",
                    ),
                ),
            ],
            options={
                "verbose_name": "Cobrança da empresa",
                "verbose_name_plural": "Cobranças das empresas",
            },
        ),
    ]
