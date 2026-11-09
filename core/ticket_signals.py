"""
Signals para notificações de tickets
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.db import transaction
import logging

from .models import Ticket, TicketMessage, TicketNotification, CustomUser

logger = logging.getLogger(__name__)


def is_rm_user(user):
    """Verifica se o usuário é da RMSys"""
    return user and (user.role == 'RM' or user.is_superuser)


def is_company_user(user):
    """Verifica se o usuário é de uma empresa"""
    return user and user.role != 'RM' and not user.is_superuser


def create_ticket_notification(ticket, notification_type, recipient, message, created_by=None):
    """Cria uma notificação de ticket"""
    try:
        TicketNotification.objects.create(
            ticket=ticket,
            notification_type=notification_type,
            recipient=recipient,
            message=message,
            created_by=created_by or ticket.created_by
        )
        logger.debug(f"Notificação criada: {notification_type} para {recipient.username} - Ticket {ticket.ticket_number}")
    except Exception as e:
        logger.exception(f"Erro ao criar notificação: {str(e)}")


@receiver(post_save, sender=Ticket)
def ticket_created_or_updated(sender, instance, created, **kwargs):
    """Detecta criação ou atualização de ticket"""
    try:
        if created:
            # Ticket criado - notificar RMSys
            logger.debug(f"Ticket criado: {instance.ticket_number} por {instance.created_by.username}")
            
            # Buscar todos os usuários RMSys ativos
            rm_users = CustomUser.objects.filter(
                role='RM',
                is_active=True
            ) | CustomUser.objects.filter(
                is_superuser=True,
                is_active=True
            )
            
            message = f"Novo ticket {instance.ticket_number} criado por {instance.company.name}: {instance.title}"
            
            for rm_user in rm_users.distinct():
                create_ticket_notification(
                    ticket=instance,
                    notification_type='ticket_created',
                    recipient=rm_user,
                    message=message,
                    created_by=instance.created_by
                )
        else:
            # Ticket atualizado - verificar mudanças
            if 'update_fields' in kwargs and kwargs['update_fields']:
                # Verificar se status mudou
                if 'status' in kwargs['update_fields']:
                    old_status = Ticket.objects.filter(pk=instance.pk).values_list('status', flat=True).first()
                    # Como já foi salvo, precisamos verificar de outra forma
                    # Vamos usar uma flag ou verificar no pre_save
                    pass
    except Exception as e:
        logger.exception(f"Erro no signal ticket_created_or_updated: {str(e)}")


# Variável para rastrear mudanças de status
_status_changes = {}


@receiver(pre_save, sender=Ticket)
def ticket_pre_save(sender, instance, **kwargs):
    """Captura estado anterior antes de salvar"""
    if instance.pk:
        try:
            old_instance = Ticket.objects.get(pk=instance.pk)
            _status_changes[instance.pk] = {
                'old_status': old_instance.status,
                'old_priority': old_instance.priority,
                'old_assigned_to': old_instance.assigned_to_id,
            }
        except Ticket.DoesNotExist:
            pass


@receiver(post_save, sender=Ticket)
def ticket_status_changed(sender, instance, created, **kwargs):
    """Detecta mudanças de status, prioridade ou atribuição"""
    if created:
        return  # Já tratado em ticket_created_or_updated
    
    try:
        changes = _status_changes.get(instance.pk, {})
        
        # Verificar mudança de status
        if changes.get('old_status') != instance.status:
            old_status = changes.get('old_status', '')
            new_status = instance.status
            
            # Determinar quem notificar
            if is_rm_user(instance.created_by):
                # Ticket criado por RM - notificar empresa
                recipients = CustomUser.objects.filter(
                    company=instance.company,
                    is_active=True
                )
                message = f"Status do ticket {instance.ticket_number} alterado de '{old_status}' para '{new_status}'"
            else:
                # Ticket criado por empresa - notificar empresa e RM atribuído
                recipients = CustomUser.objects.none()
                if instance.assigned_to:
                    recipients = CustomUser.objects.filter(pk=instance.assigned_to.pk)
                else:
                    # Se não tiver atribuído, notificar todos os RMs
                    recipients = CustomUser.objects.filter(
                        role='RM',
                        is_active=True
                    ) | CustomUser.objects.filter(
                        is_superuser=True,
                        is_active=True
                    )
                
                # Também notificar a empresa
                company_users = CustomUser.objects.filter(
                    company=instance.company,
                    is_active=True
                )
                recipients = recipients.union(company_users)
                
                message = f"Status do ticket {instance.ticket_number} alterado de '{old_status}' para '{new_status}'"
            
            for recipient in recipients.distinct():
                create_ticket_notification(
                    ticket=instance,
                    notification_type='status_changed',
                    recipient=recipient,
                    message=message,
                    created_by=instance.created_by
                )
        
        # Verificar mudança de prioridade
        if changes.get('old_priority') != instance.priority:
            old_priority = changes.get('old_priority', '')
            new_priority = instance.priority
            
            # Notificar empresa e RM atribuído
            recipients = CustomUser.objects.filter(
                company=instance.company,
                is_active=True
            )
            
            if instance.assigned_to:
                recipients = recipients.union(CustomUser.objects.filter(pk=instance.assigned_to.pk))
            else:
                rm_users = CustomUser.objects.filter(
                    role='RM',
                    is_active=True
                ) | CustomUser.objects.filter(
                    is_superuser=True,
                    is_active=True
                )
                recipients = recipients.union(rm_users)
            
            message = f"Prioridade do ticket {instance.ticket_number} alterada de '{old_priority}' para '{new_priority}'"
            
            for recipient in recipients.distinct():
                create_ticket_notification(
                    ticket=instance,
                    notification_type='priority_changed',
                    recipient=recipient,
                    message=message,
                    created_by=instance.created_by
                )
        
        # Verificar mudança de atribuição
        if changes.get('old_assigned_to') != instance.assigned_to_id:
            old_assigned_id = changes.get('old_assigned_to')
            new_assigned = instance.assigned_to
            
            # Notificar novo atribuído
            if new_assigned:
                message = f"Ticket {instance.ticket_number} atribuído a você: {instance.title}"
                create_ticket_notification(
                    ticket=instance,
                    notification_type='assigned',
                    recipient=new_assigned,
                    message=message,
                    created_by=instance.created_by
                )
            
            # Notificar empresa sobre atribuição
            company_users = CustomUser.objects.filter(
                company=instance.company,
                is_active=True
            )
            message = f"Ticket {instance.ticket_number} atribuído a {new_assigned.get_full_name() if new_assigned else 'atendente'}"
            
            for recipient in company_users:
                create_ticket_notification(
                    ticket=instance,
                    notification_type='assigned',
                    recipient=recipient,
                    message=message,
                    created_by=instance.created_by
                )
        
        # Limpar cache de mudanças
        if instance.pk in _status_changes:
            del _status_changes[instance.pk]
            
    except Exception as e:
        logger.exception(f"Erro no signal ticket_status_changed: {str(e)}")


@receiver(post_save, sender=TicketMessage)
def ticket_message_created(sender, instance, created, **kwargs):
    """Detecta criação de nova mensagem no ticket"""
    if not created:
        return
    
    try:
        ticket = instance.ticket
        sender_user = instance.sent_by
        
        # Determinar destinatários
        if is_rm_user(sender_user):
            # Mensagem enviada por RM - notificar empresa
            recipients = CustomUser.objects.filter(
                company=ticket.company,
                is_active=True
            )
            message = f"Nova mensagem no ticket {ticket.ticket_number} de {sender_user.get_full_name() or sender_user.username}"
        else:
            # Mensagem enviada por empresa - notificar RMSys
            recipients = CustomUser.objects.none()
            
            # Notificar RM atribuído se houver
            if ticket.assigned_to:
                recipients = CustomUser.objects.filter(pk=ticket.assigned_to.pk)
            else:
                # Notificar todos os RMs
                recipients = CustomUser.objects.filter(
                    role='RM',
                    is_active=True
                ) | CustomUser.objects.filter(
                    is_superuser=True,
                    is_active=True
                )
            
            message = f"Nova mensagem no ticket {ticket.ticket_number} de {ticket.company.name}: {instance.message[:100]}..."
        
        for recipient in recipients.distinct():
            # Não notificar o próprio remetente
            if recipient != sender_user:
                create_ticket_notification(
                    ticket=ticket,
                    notification_type='new_message',
                    recipient=recipient,
                    message=message,
                    created_by=sender_user
                )
                
    except Exception as e:
        logger.exception(f"Erro no signal ticket_message_created: {str(e)}")

