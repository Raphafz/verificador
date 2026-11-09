"""Teste de VPN → OLT dentro de container (rede isolada)."""
from __future__ import annotations

import sys

from django.core.management.base import BaseCommand, CommandError

from core.models import Company
from olt_ops.vpn_manager import test_vpn_to_host


class Command(BaseCommand):
    help = "Testa VPN e conectividade TCP até a OLT (uso em container)."

    def add_arguments(self, parser):
        parser.add_argument("--company-id", type=int, required=True)
        parser.add_argument("--host", required=True)
        parser.add_argument("--port", type=int, default=22)

    def handle(self, *args, **options):
        try:
            company = Company.objects.get(pk=options["company_id"])
        except Company.DoesNotExist as exc:
            raise CommandError(f"Empresa {options['company_id']} não encontrada.") from exc

        ok, log = test_vpn_to_host(company, options["host"], options["port"])
        if log:
            self.stdout.write(log)
        if not ok:
            sys.exit(1)
        self.stdout.write(self.style.SUCCESS("Teste VPN/OLT OK."))
