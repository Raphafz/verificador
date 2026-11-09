"""
Views para notificações de tickets
"""
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Q, Count
from django.utils import timezone
import logging

from .models import TicketNotification

logger = logging.getLogger(__name__)


@login_required
@require_http_methods(["GET"])
def get_notifications(request):
    """API para buscar notificações do usuário"""
    try:
        # Buscar notificações não lidas primeiro
        unread_count = TicketNotification.objects.filter(
            recipient=request.user,
            read=False
        ).count()
        
        # Buscar últimas notificações (lidas e não lidas)
        limit = int(request.GET.get('limit', 20))
        notifications = TicketNotification.objects.filter(
            recipient=request.user
        ).select_related(
            'ticket',
            'ticket__company',
            'created_by'
        ).order_by('-created_at')[:limit]
        
        notifications_data = []
        for notification in notifications:
            notifications_data.append({
                'id': notification.id,
                'type': notification.notification_type,
                'type_display': notification.get_notification_type_display(),
                'message': notification.message,
                'ticket_id': notification.ticket.id,
                'ticket_number': notification.ticket.ticket_number,
                'ticket_title': notification.ticket.title,
                'company_name': notification.ticket.company.name if notification.ticket.company else '',
                'read': notification.read,
                'read_at': notification.read_at.isoformat() if notification.read_at else None,
                'created_at': notification.created_at.isoformat(),
                'created_by': notification.created_by.get_full_name() if notification.created_by else None,
            })
        
        return JsonResponse({
            'success': True,
            'unread_count': unread_count,
            'notifications': notifications_data
        })
    except Exception as e:
        logger.exception(f"Erro ao buscar notificações: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Erro ao buscar notificações',
            'unread_count': 0,
            'notifications': []
        }, status=500)


@login_required
@require_http_methods(["POST"])
def mark_notification_read(request, notification_id):
    """Marca uma notificação como lida"""
    try:
        notification = TicketNotification.objects.get(
            id=notification_id,
            recipient=request.user
        )
        notification.mark_as_read()
        
        return JsonResponse({
            'success': True,
            'message': 'Notificação marcada como lida'
        })
    except TicketNotification.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Notificação não encontrada'
        }, status=404)
    except Exception as e:
        logger.exception(f"Erro ao marcar notificação como lida: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Erro ao marcar notificação como lida'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def mark_all_notifications_read(request):
    """Marca todas as notificações do usuário como lidas"""
    try:
        updated = TicketNotification.objects.filter(
            recipient=request.user,
            read=False
        ).update(
            read=True,
            read_at=timezone.now()
        )
        
        return JsonResponse({
            'success': True,
            'message': f'{updated} notificação(ões) marcada(s) como lida(s)',
            'updated_count': updated
        })
    except Exception as e:
        logger.exception(f"Erro ao marcar todas as notificações como lidas: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Erro ao marcar notificações como lidas'
        }, status=500)


@login_required
@require_http_methods(["GET"])
def get_unread_count(request):
    """Retorna apenas a contagem de notificações não lidas"""
    try:
        count = TicketNotification.objects.filter(
            recipient=request.user,
            read=False
        ).count()
        
        return JsonResponse({
            'success': True,
            'unread_count': count
        })
    except Exception as e:
        logger.exception(f"Erro ao buscar contagem de notificações: {str(e)}")
        return JsonResponse({
            'success': False,
            'unread_count': 0
        }, status=500)

