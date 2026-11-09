from django.core.management.base import BaseCommand
from django.core.cache import cache
from core.rate_limiting import clear_all_rate_limits

class Command(BaseCommand):
    help = 'Limpar todos os rate limits do sistema'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirma a limpeza dos rate limits',
        )

    def handle(self, *args, **options):
        if not options['confirm']:
            self.stdout.write(
                self.style.WARNING(
                    'Para limpar os rate limits, use: python manage.py clear_rate_limit --confirm'
                )
            )
            return

        try:
            clear_all_rate_limits()
            self.stdout.write(
                self.style.SUCCESS('Rate limits limpos com sucesso!')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Erro ao limpar rate limits: {e}')
            )
