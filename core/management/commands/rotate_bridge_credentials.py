"""
Gera novos ALERT_BRIDGE_API_TOKEN e BRIDGE_HMAC_SECRET para rotação.

Uso:
  python manage.py rotate_bridge_credentials
  python manage.py rotate_bridge_credentials --apply-hint
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from core.bridge_security import generate_bridge_credentials


class Command(BaseCommand):
    help = "Gera credenciais novas para rotação do alert-bridge (token + HMAC)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply-hint",
            action="store_true",
            help="Mostra passos para aplicar nos workers Node",
        )

    def handle(self, *args, **options):
        token, hmac_secret = generate_bridge_credentials()
        self.stdout.write(self.style.SUCCESS("Novas credenciais (copie para .env e reinicie workers):"))
        self.stdout.write(f"ALERT_BRIDGE_API_TOKEN={token}")
        self.stdout.write(f"BRIDGE_HMAC_SECRET={hmac_secret}")
        if options["apply_hint"]:
            self.stdout.write(
                "\n1. Atualize .env do Django e MENSAGENS/\n"
                "2. Atualize services/alert_bridge/.env se usar worker legado\n"
                "3. Reinicie Gunicorn + processos Node\n"
                "4. Rode: python manage.py check_security --strict"
            )
