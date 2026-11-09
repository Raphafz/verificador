"""Remove tokens de ativação expirados ou antigos (LGPD / segurança)."""
from django.core.management.base import BaseCommand

from core.account_activation import purge_expired_activation_tokens


class Command(BaseCommand):
    help = "Remove tokens de ativação de conta expirados ou usados há mais de 7 dias"

    def handle(self, *args, **options):
        deleted = purge_expired_activation_tokens()
        self.stdout.write(self.style.SUCCESS(f"Removidos {deleted} registro(s) de ativação."))
