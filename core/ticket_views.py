"""
Views para o sistema de tickets
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.utils import timezone
from django.views.decorators.http import require_http_methods
import json
import logging

from .forms import TicketForm, TicketMessageForm
from .models import Ticket, TicketMessage, Company, CustomUser
from .utils import (
    run_in_background,
    send_ticket_created_email,
    send_ticket_message_email,
)
from .permissions import rm_admin_required, company_access_required, company_access_required_json

logger = logging.getLogger(__name__)


def _serialize_ticket_message(msg, current_user):
    sent_by_name = "-"
    sent_by_role = "unknown"
    if msg.sent_by:
        sent_by_name = msg.sent_by.get_full_name() or msg.sent_by.username or "-"
        sent_by_role = getattr(msg.sent_by, "role", "unknown")
    return {
        "id": msg.id,
        "message": msg.message or "",
        "sent_by": sent_by_name,
        "sent_by_role": sent_by_role,
        "created_at": msg.created_at.strftime("%d/%m/%Y %H:%M") if msg.created_at else "",
        "is_sent_by_me": msg.sent_by == current_user if msg.sent_by else False,
    }


def _parse_message_text(request):
    content_type = request.content_type or ""
    if "application/json" in content_type:
        try:
            payload = json.loads(request.body.decode("utf-8") or "{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {}
        return (payload.get("message") or "").strip()
    return (request.POST.get("message") or "").strip()


def _create_ticket_message(ticket, user, text, request):
    if ticket.status == "fechado":
        return None, "Este ticket está fechado."
    if len(text) < 1:
        return None, "A mensagem não pode estar vazia."
    form = TicketMessageForm({"message": text}, user=user, ticket=ticket)
    if not form.is_valid():
        err = form.errors.get("message", ["Mensagem inválida."])[0]
        return None, str(err)
    message = form.save(commit=False)
    message.ticket = ticket
    message.sent_by = user
    message.save()
    run_in_background(send_ticket_message_email, ticket, message, request)
    return message, None


def _get_ticket_chat_messages(ticket):
    """Mensagens do chat sem duplicar a descrição inicial do ticket."""
    chat_messages = list(
        TicketMessage.objects.filter(ticket=ticket)
        .select_related('sent_by')
        .order_by('created_at')
    )
    if not chat_messages or not (ticket.description or '').strip():
        return chat_messages
    first = chat_messages[0]
    if (
        first.sent_by_id == ticket.created_by_id
        and first.message.strip() == ticket.description.strip()
    ):
        return chat_messages[1:]
    return chat_messages


@login_required
@company_access_required(require_admin=False, allow_user_role=True)
def company_ticket_create(request, company_slug):
    """Criar novo ticket (empresa)"""
    try:
        company = get_object_or_404(Company, slug=company_slug)
        
        if request.method == 'POST':
            form = TicketForm(request.POST, user=request.user, company=company)
            if form.is_valid():
                try:
                    # Criar ticket
                    ticket = form.save(commit=False)
                    ticket.company = company
                    ticket.created_by = request.user
                    
                    # Garantir que status está definido
                    if not ticket.status:
                        ticket.status = 'aberto'
                    
                    # Garantir que priority está definido
                    if not ticket.priority:
                        ticket.priority = 'normal'
                    
                    logger.debug(f"Salvando ticket: title={ticket.title}, company={company.id}, created_by={request.user.id}")
                    ticket.save()
                    logger.debug(f"Ticket salvo com ID: {ticket.id}, número: {ticket.ticket_number}")
                    
                    # Criar primeira mensagem com a descrição
                    try:
                        if ticket.description:
                            TicketMessage.objects.create(
                                ticket=ticket,
                                message=ticket.description,
                                sent_by=request.user
                            )
                            logger.debug(f"Primeira mensagem criada para ticket {ticket.id}")
                    except Exception as e:
                        logger.exception(f"Erro ao criar primeira mensagem do ticket: {str(e)}")
                        # Não deixar o ticket sem mensagem - usar descrição como fallback
                        messages.warning(request, 'Ticket criado, mas houve um problema ao salvar a primeira mensagem.')
                    
                    run_in_background(
                        lambda: send_ticket_created_email(
                            ticket, request, actor=request.user
                        )
                    )
                    logger.debug(f"E-mails de ticket {ticket.id} agendados em background")
                    
                    messages.success(request, f'Ticket {ticket.ticket_number} criado com sucesso! Você receberá um email com os detalhes.')
                    return redirect('company:ticket_detail', company_slug=company_slug, ticket_id=ticket.id)
                except Exception as e:
                    logger.exception(f"Erro ao salvar ticket: {str(e)}")
                    # Mensagem de erro mais amigável
                    error_msg = str(e)
                    if 'ticket_number' in error_msg.lower() or 'unique' in error_msg.lower():
                        error_msg = 'Erro ao gerar número do ticket. Tente novamente.'
                    elif 'required' in error_msg.lower() or 'null' in error_msg.lower():
                        error_msg = 'Campos obrigatórios não preenchidos. Verifique o formulário.'
                    
                    messages.error(request, f'Erro ao criar ticket: {error_msg}')
                    # Adicionar erro ao form para exibir na página
                    form.add_error(None, error_msg)
            else:
                # Log de erros de validação
                logger.debug(f"Erros de validação no formulário: {form.errors}")
        else:
            form = TicketForm(user=request.user, company=company)
        
        return render(request, 'company/tickets/create.html', {
            'form': form,
            'company': company
        })
    except Exception as e:
        logger.exception(f"Erro inesperado em company_ticket_create: {str(e)}")
        messages.error(request, f'Erro inesperado ao criar ticket: {str(e)}')
        return render(request, 'company/tickets/create.html', {
            'form': TicketForm(user=request.user, company=company) if 'company' in locals() else TicketForm(),
            'company': company if 'company' in locals() else None,
            'error': str(e)
        })


@login_required
@company_access_required(require_admin=False, allow_user_role=True)
def company_ticket_list(request, company_slug):
    """Listar tickets da empresa"""
    try:
        company = get_object_or_404(Company, slug=company_slug)
        
        # Verificar se os modelos existem no banco (migrações aplicadas)
        try:
            # Filtrar tickets da empresa e do usuário (se não for admin)
            if request.user.is_company_admin:
                tickets = Ticket.objects.filter(company=company)
            else:
                tickets = Ticket.objects.filter(company=company, created_by=request.user)
        except Exception as e:
            logger.error(f"Erro ao acessar modelos Ticket: {str(e)}")
            messages.error(request, 'Erro ao carregar tickets. Por favor, execute as migrações do banco de dados.')
            return render(request, 'company/tickets/list.html', {
                'tickets': [],
                'company': company,
                'status_filter': '',
                'ticket_stats': {'total': 0, 'abertos': 0, 'em_andamento': 0, 'finalizados': 0},
                'error': 'Modelos não migrados. Execute: python manage.py migrate'
            })
        
        # Estatísticas (antes do filtro de status)
        ticket_stats = {
            'total': tickets.count(),
            'abertos': tickets.filter(status='aberto').count(),
            'em_andamento': tickets.filter(
                status__in=['em_andamento', 'aguardando_cliente']
            ).count(),
            'finalizados': tickets.filter(status__in=['resolvido', 'fechado']).count(),
        }

        # Filtros
        status_filter = request.GET.get('status', '')
        if status_filter:
            tickets = tickets.filter(status=status_filter)
        
        # Ordenação
        tickets = tickets.order_by('-created_at')
        
        # Paginação
        paginator = Paginator(tickets, 20)
        page = request.GET.get('page', 1)
        try:
            page = int(page)
            if page < 1:
                page = 1
        except (ValueError, TypeError):
            page = 1
        try:
            tickets_page = paginator.get_page(page)
        except (EmptyPage, PageNotAnInteger):
            tickets_page = paginator.get_page(1)
        
        return render(request, 'company/tickets/list.html', {
            'tickets': tickets_page,
            'company': company,
            'status_filter': status_filter,
            'ticket_stats': ticket_stats,
        })
    except Exception as e:
        logger.exception(f"Erro inesperado em company_ticket_list: {str(e)}")
        messages.error(request, f'Erro ao carregar tickets: {str(e)}')
        return render(request, 'company/tickets/list.html', {
            'tickets': [],
            'company': company if 'company' in locals() else None,
            'status_filter': '',
            'ticket_stats': {'total': 0, 'abertos': 0, 'em_andamento': 0, 'finalizados': 0},
            'error': str(e)
        })


@login_required
@company_access_required(require_admin=False, allow_user_role=True)
def company_ticket_detail(request, company_slug, ticket_id):
    """Visualizar ticket e chat (empresa)"""
    try:
        company = get_object_or_404(Company, slug=company_slug)
        ticket = get_object_or_404(Ticket, id=ticket_id, company=company)
        
        # Verificar permissão (admin pode ver todos, usuário apenas os seus)
        if not request.user.is_company_admin and ticket.created_by != request.user:
            messages.error(request, 'Você não tem permissão para acessar este ticket.')
            return redirect('company:ticket_list', company_slug=company_slug)
        
        # Marcar mensagens como lidas
        try:
            if ticket.created_by == request.user:
                # Marcar mensagens do RM como lidas
                TicketMessage.objects.filter(
                    ticket=ticket,
                    sent_by__role='RM',
                    read=False
                ).update(read=True, read_at=timezone.now())
        except Exception as e:
            logger.warning(f"Erro ao marcar mensagens como lidas: {str(e)}")
        
        try:
            chat_messages = _get_ticket_chat_messages(ticket)
        except Exception as e:
            logger.error(f"Erro ao buscar mensagens do ticket: {str(e)}")
            chat_messages = []
        
        if request.method == 'POST':
            # Verificar se é para fechar o ticket
            if 'close_ticket' in request.POST:
                # Apenas o criador do ticket ou admin da empresa pode fechar
                if ticket.created_by == request.user or request.user.is_company_admin:
                    if ticket.status != 'fechado':
                        ticket.status = 'fechado'
                        ticket.save()
                        messages.success(request, f'Ticket {ticket.ticket_number} fechado com sucesso!')
                    else:
                        messages.info(request, 'Este ticket já está fechado.')
                    return redirect('company:ticket_detail', company_slug=company_slug, ticket_id=ticket.id)
                else:
                    messages.error(request, 'Você não tem permissão para fechar este ticket.')
                    return redirect('company:ticket_detail', company_slug=company_slug, ticket_id=ticket.id)
            
            # Adicionar mensagem
            form = TicketMessageForm(request.POST, user=request.user, ticket=ticket)
            if form.is_valid():
                # Não permitir adicionar mensagens em tickets fechados
                if ticket.status == 'fechado':
                    messages.error(request, 'Não é possível adicionar mensagens em tickets fechados.')
                    return redirect('company:ticket_detail', company_slug=company_slug, ticket_id=ticket.id)
                
                message = form.save(commit=False)
                message.ticket = ticket
                message.sent_by = request.user
                message.save()
                run_in_background(send_ticket_message_email, ticket, message, request)
                messages.success(request, 'Mensagem enviada com sucesso!')
                return redirect('company:ticket_detail', company_slug=company_slug, ticket_id=ticket.id)
        else:
            form = TicketMessageForm(user=request.user, ticket=ticket)
        
        return render(request, 'company/tickets/detail.html', {
            'ticket': ticket,
            'chat_messages': chat_messages,
            'form': form,
            'company': company,
        })
    except Exception as e:
        logger.exception(f"Erro inesperado em company_ticket_detail: {str(e)}")
        messages.error(request, f'Erro ao carregar ticket: {str(e)}')
        return redirect('company:ticket_list', company_slug=company_slug)


@login_required
@rm_admin_required
def rm_ticket_list(request):
    """Listar todos os tickets (RM)"""
    tickets = Ticket.objects.all().order_by('-created_at')
    
    # Filtros
    status_filter = request.GET.get('status', '')
    company_filter = request.GET.get('company', '')
    assigned_to_me = request.GET.get('assigned_to_me', '')
    
    if status_filter:
        tickets = tickets.filter(status=status_filter)
    
    if company_filter:
        tickets = tickets.filter(company_id=company_filter)
    
    if assigned_to_me == 'true':
        tickets = tickets.filter(assigned_to=request.user)
    
    # Paginação
    paginator = Paginator(tickets, 20)
    page = request.GET.get('page', 1)
    try:
        page = int(page)
        if page < 1:
            page = 1
    except (ValueError, TypeError):
        page = 1
    try:
        tickets_page = paginator.get_page(page)
    except (EmptyPage, PageNotAnInteger):
        tickets_page = paginator.get_page(1)
    
    companies = Company.objects.filter(is_active=True).order_by('name')
    
    return render(request, 'rm/tickets/list.html', {
        'tickets': tickets_page,
        'status_filter': status_filter,
        'company_filter': company_filter,
        'companies': companies
    })


@login_required
@rm_admin_required
def rm_ticket_detail(request, ticket_id):
    """Visualizar ticket e chat (RM)"""
    ticket = get_object_or_404(Ticket, id=ticket_id)
    
    # Marcar mensagens do cliente como lidas
    TicketMessage.objects.filter(
        ticket=ticket,
        sent_by=ticket.created_by,
        read=False
    ).update(read=True, read_at=timezone.now())
    
    chat_messages = _get_ticket_chat_messages(ticket)
    
    if request.method == 'POST':
        # Verificar se é para fechar o ticket
        if 'close_ticket' in request.POST:
            if ticket.status != 'fechado':
                ticket.status = 'fechado'
                ticket.save()
                messages.success(request, f'Ticket {ticket.ticket_number} fechado com sucesso!')
            else:
                messages.info(request, 'Este ticket já está fechado.')
            return redirect('rm:ticket_detail', ticket_id=ticket.id)
        
        # Verificar se é para atualizar status ou adicionar mensagem
        if 'update_status' in request.POST:
            ticket.status = request.POST.get('status')
            if 'assigned_to' in request.POST and request.POST.get('assigned_to'):
                ticket.assigned_to_id = request.POST.get('assigned_to')
            ticket.save()
            messages.success(request, 'Status do ticket atualizado!')
            return redirect('rm:ticket_detail', ticket_id=ticket.id)
        else:
            # Adicionar mensagem
            form = TicketMessageForm(request.POST, user=request.user, ticket=ticket)
            if form.is_valid():
                # Não permitir adicionar mensagens em tickets fechados
                if ticket.status == 'fechado':
                    messages.error(request, 'Não é possível adicionar mensagens em tickets fechados.')
                    return redirect('rm:ticket_detail', ticket_id=ticket.id)
                
                message = form.save(commit=False)
                message.ticket = ticket
                message.sent_by = request.user
                message.save()
                run_in_background(send_ticket_message_email, ticket, message, request)
                messages.success(request, 'Mensagem enviada com sucesso!')
                return redirect('rm:ticket_detail', ticket_id=ticket.id)
    else:
        form = TicketMessageForm(user=request.user, ticket=ticket)
    
    # Lista de RM admins para atribuição
    rm_admins = CustomUser.objects.filter(role='RM', is_active=True)
    
    return render(request, 'rm/tickets/detail.html', {
        'ticket': ticket,
        'chat_messages': chat_messages,
        'form': form,
        'rm_admins': rm_admins,
    })


@login_required
@company_access_required_json(require_admin=False)
@require_http_methods(["GET", "POST"])
def get_new_messages(request, company_slug, ticket_id):
    """API do chat: GET = novas mensagens, POST = enviar mensagem (JSON)."""
    try:
        company = get_object_or_404(Company, slug=company_slug)
        ticket = get_object_or_404(Ticket, id=ticket_id, company=company)
        
        # Verificar permissão
        if not request.user.is_company_admin and ticket.created_by != request.user:
            return JsonResponse({'error': 'Sem permissão'}, status=403)

        if request.method == "POST":
            text = _parse_message_text(request)
            message, err = _create_ticket_message(ticket, request.user, text, request)
            if err:
                return JsonResponse({"error": err}, status=400)
            return JsonResponse({
                "ok": True,
                "message": _serialize_ticket_message(message, request.user),
            })
        
        # Buscar mensagens não lidas
        last_message_id = request.GET.get('last_message_id', 0)
        try:
            last_message_id = int(last_message_id)
        except (ValueError, TypeError):
            last_message_id = 0
        
        try:
            new_messages = TicketMessage.objects.filter(
                ticket=ticket,
                id__gt=last_message_id
            ).select_related('sent_by').order_by('created_at')
            
            # Marcar como lidas se for o criador do ticket
            if ticket.created_by == request.user:
                new_messages.filter(sent_by__role='RM', read=False).update(read=True, read_at=timezone.now())
        except Exception as e:
            logger.exception(f"Erro ao buscar mensagens: {str(e)}")
            return JsonResponse({'error': 'Erro ao buscar mensagens', 'messages': [], 'has_new': False}, status=500)
        
        messages_data = [
            _serialize_ticket_message(msg, request.user) for msg in new_messages
        ]
        
        return JsonResponse({
            'messages': messages_data,
            'has_new': len(messages_data) > 0
        })
    except Exception as e:
        logger.exception(f"Erro inesperado em get_new_messages: {str(e)}")
        return JsonResponse({'error': 'Erro interno do servidor', 'messages': [], 'has_new': False}, status=500)


@login_required
@rm_admin_required
@require_http_methods(["GET", "POST"])
def rm_get_new_messages(request, ticket_id):
    """API do chat RM: GET = novas mensagens, POST = enviar mensagem."""
    try:
        ticket = get_object_or_404(Ticket, id=ticket_id)

        if request.method == "POST":
            text = _parse_message_text(request)
            message, err = _create_ticket_message(ticket, request.user, text, request)
            if err:
                return JsonResponse({"error": err}, status=400)
            return JsonResponse({
                "ok": True,
                "message": _serialize_ticket_message(message, request.user),
            })
        
        last_message_id = request.GET.get('last_message_id', 0)
        try:
            last_message_id = int(last_message_id)
        except (ValueError, TypeError):
            last_message_id = 0
        
        try:
            new_messages = TicketMessage.objects.filter(
                ticket=ticket,
                id__gt=last_message_id
            ).select_related('sent_by').order_by('created_at')
            
            # Marcar mensagens do cliente como lidas
            if ticket.created_by:
                new_messages.filter(sent_by=ticket.created_by, read=False).update(read=True, read_at=timezone.now())
        except Exception as e:
            logger.exception(f"Erro ao buscar mensagens: {str(e)}")
            return JsonResponse({'error': 'Erro ao buscar mensagens', 'messages': [], 'has_new': False}, status=500)
        
        messages_data = [
            _serialize_ticket_message(msg, request.user) for msg in new_messages
        ]
        
        return JsonResponse({
            'messages': messages_data,
            'has_new': len(messages_data) > 0
        })
    except Exception as e:
        logger.exception(f"Erro inesperado em rm_get_new_messages: {str(e)}")
        return JsonResponse({'error': 'Erro interno do servidor', 'messages': [], 'has_new': False}, status=500)

