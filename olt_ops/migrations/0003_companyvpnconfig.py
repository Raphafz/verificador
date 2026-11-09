import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0013_ticketnotification_and_more"),
        ("olt_ops", "0002_oltequipment_list_command"),
    ]

    operations = [
        migrations.CreateModel(
            name="CompanyVpnConfig",
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
                    "is_enabled",
                    models.BooleanField(
                        default=False,
                        verbose_name="Usar VPN nas operações OLT",
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        blank=True,
                        help_text="Ex: VPN Matriz SP",
                        max_length=120,
                        verbose_name="Nome / identificação",
                    ),
                ),
                (
                    "vpn_type",
                    models.CharField(
                        choices=[("openvpn", "OpenVPN (.ovpn)")],
                        default="openvpn",
                        max_length=32,
                    ),
                ),
                (
                    "ovpn_content",
                    models.TextField(
                        blank=True,
                        help_text="Cole o conteúdo completo do arquivo .ovpn fornecido pelo admin da rede.",
                        verbose_name="Arquivo .ovpn",
                    ),
                ),
                (
                    "vpn_username",
                    models.CharField(
                        blank=True, max_length=128, verbose_name="Usuário VPN"
                    ),
                ),
                (
                    "vpn_password",
                    models.CharField(
                        blank=True,
                        help_text="Usado se o .ovpn tiver auth-user-pass.",
                        max_length=256,
                        verbose_name="Senha VPN",
                    ),
                ),
                ("notes", models.TextField(blank=True, verbose_name="Observações")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="vpn_config",
                        to="core.company",
                        verbose_name="Empresa",
                    ),
                ),
            ],
            options={
                "verbose_name": "VPN da empresa",
                "verbose_name_plural": "VPNs das empresas",
            },
        ),
    ]
