"""Cadastra/atualiza OLTs da Fibramar a partir do menu legado (Putty)."""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from core.models import Company
from olt_ops.models import OltEquipment

# Origem: script batch de acesso às OLTs Fibramar (SSH/Telnet + portas).
FIBRAMAR_OLTS: tuple[dict, ...] = (
    {
        "name": "HUAWEI MA5680T - PONTA NEGRA",
        "host": "172.16.8.10",
        "port": 22,
        "vendor": "huawei",
        "protocol": "ssh",
        "username": "admincrnet",
        "password": "just281190",
    },
    {
        "name": "HUAWEI MA5800-X2 - SAO JOSE DE EMBASSAI",
        "host": "172.16.8.20",
        "port": 22,
        "vendor": "huawei",
        "protocol": "ssh",
        "username": "root",
        "password": "Just@281190@",
    },
    {
        "name": "HUAWEI MA5800-X2 - VALE DA FIGUEIRA",
        "host": "172.16.8.246",
        "port": 22,
        "vendor": "huawei",
        "protocol": "ssh",
        "username": "root",
        "password": "Just@281190@",
    },
    {
        "name": "HUAWEI MA5800-X7 - MARICA - CENTRO",
        "host": "172.16.8.30",
        "port": 22,
        "vendor": "huawei",
        "protocol": "ssh",
        "username": "root",
        "password": "Just@281190@",
    },
    {
        "name": "ZTE C350 - ITAIPUACU",
        "host": "172.16.8.62",
        "port": 22,
        "vendor": "zte",
        "protocol": "ssh",
        "username": "crnet",
        "password": "Just@281190",
    },
    {
        "name": "ZTE C300 - WEB.COM",
        "host": "160.238.249.1",
        "port": 2335,
        "vendor": "zte",
        "protocol": "telnet",
        "username": "carlos",
        "password": "just281190",
    },
    {
        "name": "ZTE C350 - VILA VELHA - ES",
        "host": "186.26.83.10",
        "port": 2323,
        "vendor": "zte",
        "protocol": "telnet",
        "username": "ixcsoft",
        "password": "8dQeuKJkYoEX",
    },
    {
        "name": "HUAWEI MA5800-X7 - SAQUAREMA",
        "host": "138.204.76.68",
        "port": 65023,
        "vendor": "huawei",
        "protocol": "telnet",
        "username": "ispconfig",
        "password": "x22SZo74QmDD9wR",
    },
    {
        "name": "HUAWEI MA5800-X2 - MIMOSO - ES",
        "host": "170.84.53.80",
        "port": 65023,
        "vendor": "huawei",
        "protocol": "telnet",
        "username": "root",
        "password": "Just@281190@",
    },
    {
        "name": "HUAWEI MA5800-X7 - ARARUAMA",
        "host": "179.42.140.3",
        "port": 2332,
        "vendor": "huawei",
        "protocol": "telnet",
        "username": "ixcsoft",
        "password": "78lpD74Hkdke",
    },
    {
        "name": "HUAWEI MA5680T - UNAMAR PISTA",
        "host": "179.42.140.4",
        "port": 2331,
        "vendor": "huawei",
        "protocol": "telnet",
        "username": "radiususr",
        "password": "x22SZo74QmDD9wR",
    },
    {
        "name": "HUAWEI MA5800-X2 - MUQUI - ES",
        "host": "189.201.214.193",
        "port": 2223,
        "vendor": "huawei",
        "protocol": "telnet",
        "username": "ispcloud",
        "password": "ISP@!Cl01osd1",
    },
    {
        "name": "HUAWEI MA5800-X7 - JACONE",
        "host": "179.42.140.0",
        "port": 2223,
        "vendor": "huawei",
        "protocol": "telnet",
        "username": "root",
        "password": "Just@281190@",
    },
    {
        "name": "HUAWEI MA5800-X7 - SANTOS DUMONT - MG",
        "host": "200.169.1.96",
        "port": 2323,
        "vendor": "huawei",
        "protocol": "telnet",
        "username": "ixcsoft",
        "password": "Ef[3uD8jfXf7",
    },
    {
        "name": "HUAWEI MA5800-X7 - PIUMA - ES",
        "host": "186.26.81.0",
        "port": 2333,
        "vendor": "huawei",
        "protocol": "ssh",
        "username": "fibramar",
        "password": "Fibramar@2025",
    },
    {
        "name": "HUAWEI MA5800-X7 - BENFICA - MG",
        "host": "186.248.57.112",
        "port": 2222,
        "vendor": "huawei",
        "protocol": "ssh",
        "username": "crnetnoc",
        "password": "8JZaMp87uuU3F@",
    },
)


class Command(BaseCommand):
    help = "Cadastra ou atualiza as 16 OLTs Fibramar (menu Putty legado)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--company-slug",
            default="fibramar",
            help="Slug da empresa (padrão: fibramar).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostra o que seria feito sem gravar no banco.",
        )

    def handle(self, *args, **options):
        slug = options["company_slug"]
        dry_run = options["dry_run"]

        try:
            company = Company.objects.get(slug=slug)
        except Company.DoesNotExist as exc:
            raise CommandError(f"Empresa '{slug}' não encontrada.") from exc

        created = updated = 0
        for row in FIBRAMAR_OLTS:
            defaults = {
                "name": row["name"],
                "port": row["port"],
                "vendor": row["vendor"],
                "protocol": row["protocol"],
                "username": row["username"],
                "password": row["password"],
                "is_active": True,
            }
            if dry_run:
                exists = OltEquipment.objects.filter(company=company, host=row["host"]).exists()
                action = "atualizaria" if exists else "criaria"
                self.stdout.write(f"[dry-run] {action}: {row['name']} ({row['host']})")
                continue

            obj, was_created = OltEquipment.objects.update_or_create(
                company=company,
                host=row["host"],
                defaults=defaults,
            )
            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f"Criada: {obj.name} ({obj.host})"))
            else:
                updated += 1
                self.stdout.write(f"Atualizada: {obj.name} ({obj.host})")

        if dry_run:
            self.stdout.write(self.style.WARNING(f"Dry-run: {len(FIBRAMAR_OLTS)} OLT(s) processadas."))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Concluído para {company.name}: {created} criada(s), {updated} atualizada(s)."
            )
        )
