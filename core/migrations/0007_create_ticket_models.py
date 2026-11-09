# Generated manually for Ticket and TicketMessage models

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_add_flask_integration_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='Ticket',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255, verbose_name='Título')),
                ('description', models.TextField(verbose_name='Descrição')),
                ('status', models.CharField(choices=[('aberto', 'Aberto'), ('em_andamento', 'Em Andamento'), ('aguardando_cliente', 'Aguardando Cliente'), ('resolvido', 'Resolvido'), ('fechado', 'Fechado')], default='aberto', max_length=20, verbose_name='Status')),
                ('priority', models.CharField(choices=[('baixa', 'Baixa'), ('normal', 'Normal'), ('alta', 'Alta'), ('urgente', 'Urgente')], default='normal', max_length=20, verbose_name='Prioridade')),
                ('ticket_number', models.CharField(help_text='Gerado automaticamente', max_length=20, unique=True, verbose_name='Número do Ticket')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Criado em')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Atualizado em')),
                ('resolved_at', models.DateTimeField(blank=True, null=True, verbose_name='Resolvido em')),
                ('closed_at', models.DateTimeField(blank=True, null=True, verbose_name='Fechado em')),
                ('assigned_to', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_tickets', to=settings.AUTH_USER_MODEL, verbose_name='Atendido por')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tickets', to='core.company', verbose_name='Empresa')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='created_tickets', to=settings.AUTH_USER_MODEL, verbose_name='Criado por')),
            ],
            options={
                'verbose_name': 'Ticket',
                'verbose_name_plural': 'Tickets',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='TicketMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('message', models.TextField(verbose_name='Mensagem')),
                ('read', models.BooleanField(default=False, verbose_name='Lido')),
                ('read_at', models.DateTimeField(blank=True, null=True, verbose_name='Lido em')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Criado em')),
                ('sent_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ticket_messages', to=settings.AUTH_USER_MODEL, verbose_name='Enviado por')),
                ('ticket', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='core.ticket', verbose_name='Ticket')),
            ],
            options={
                'verbose_name': 'Mensagem do Ticket',
                'verbose_name_plural': 'Mensagens dos Tickets',
                'ordering': ['created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='ticket',
            index=models.Index(fields=['company', 'status'], name='core_ticket_company_idx'),
        ),
        migrations.AddIndex(
            model_name='ticket',
            index=models.Index(fields=['created_by', 'created_at'], name='core_ticket_created_idx'),
        ),
        migrations.AddIndex(
            model_name='ticket',
            index=models.Index(fields=['assigned_to', 'status'], name='core_ticket_assigned_idx'),
        ),
        migrations.AddIndex(
            model_name='ticket',
            index=models.Index(fields=['ticket_number'], name='core_ticket_number_idx'),
        ),
        migrations.AddIndex(
            model_name='ticketmessage',
            index=models.Index(fields=['ticket', 'created_at'], name='core_ticketm_ticket_idx'),
        ),
        migrations.AddIndex(
            model_name='ticketmessage',
            index=models.Index(fields=['sent_by', 'created_at'], name='core_ticketm_sent_by_idx'),
        ),
        migrations.AddIndex(
            model_name='ticketmessage',
            index=models.Index(fields=['read'], name='core_ticketm_read_idx'),
        ),
    ]

