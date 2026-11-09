"""
Comando Django para limpar todos os tickets e suas mensagens do banco de dados.
"""
from django.core.management.base import BaseCommand
from core.models import Ticket, TicketMessage


class Command(BaseCommand):
    help = 'Limpa todos os tickets e suas mensagens do banco de dados'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirma a exclusão sem pedir confirmação interativa',
        )

    def handle(self, *args, **options):
        # Contar tickets e mensagens antes de deletar
        tickets_count = Ticket.objects.count()
        messages_count = TicketMessage.objects.count()
        
        if tickets_count == 0 and messages_count == 0:
            self.stdout.write(
                self.style.SUCCESS('✓ Não há tickets ou mensagens para limpar.')
            )
            return
        
        # Confirmar exclusão
        if not options['confirm']:
            self.stdout.write(
                self.style.WARNING(
                    f'\n⚠️  ATENÇÃO: Esta operação irá deletar PERMANENTEMENTE:\n'
                    f'   - {tickets_count} ticket(s)\n'
                    f'   - {messages_count} mensagem(ns)\n\n'
                    f'Esta ação NÃO pode ser desfeita!\n'
                )
            )
            
            confirm = input('Deseja continuar? (digite "SIM" para confirmar): ')
            
            if confirm.upper() != 'SIM':
                self.stdout.write(
                    self.style.ERROR('✗ Operação cancelada.')
                )
                return
        
        # Deletar mensagens primeiro (devido à foreign key)
        if messages_count > 0:
            deleted_messages = TicketMessage.objects.all().delete()[0]
            self.stdout.write(
                self.style.SUCCESS(f'✓ {deleted_messages} mensagem(ns) deletada(s).')
            )
        
        # Deletar tickets
        if tickets_count > 0:
            deleted_tickets = Ticket.objects.all().delete()[0]
            self.stdout.write(
                self.style.SUCCESS(f'✓ {deleted_tickets} ticket(s) deletado(s).')
            )
        
        self.stdout.write(
            self.style.SUCCESS('\n✓ Limpeza concluída com sucesso!')
        )

