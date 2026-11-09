"""
Utilitários para o sistema
"""
import logging
import secrets
import string
import threading

from django.contrib.auth.hashers import make_password
from django.conf import settings
from core.email.send_transactional import send_transactional_html
from core.email_branding import get_email_branding_context
from django.template.loader import render_to_string
from django.contrib.sites.shortcuts import get_current_site

logger = logging.getLogger(__name__)


def run_in_background(func, *args, **kwargs):
    """Executa tarefa pesada (ex.: e-mail) sem bloquear a resposta HTTP."""
    def _runner():
        from django.db import close_old_connections

        close_old_connections()
        try:
            func(*args, **kwargs)
        except Exception:
            logger.exception("Erro em tarefa em background")
        finally:
            close_old_connections()

    threading.Thread(target=_runner, daemon=True).start()


def generate_random_password(length=14, simple=False, alphanumeric=False):
    """
    Gera uma senha aleatória
    
    Args:
        length (int): Tamanho da senha (padrão: 14, mínimo enterprise)
        simple (bool): Se True, gera senha simples (apenas números ou alfanumérica)
        alphanumeric (bool): Se True e simple=True, gera com letras e números. Se False e simple=True, gera apenas números
    
    Returns:
        str: Senha aleatória
    """
    length = max(int(length), 14)

    if simple:
        if alphanumeric:
            # Senha simples com letras (maiúsculas e minúsculas) e números - para novos usuários
            # Garantir que tenha pelo menos uma letra minúscula, uma maiúscula e um número
            password = [
                secrets.choice(string.ascii_lowercase),  # Pelo menos 1 letra minúscula
                secrets.choice(string.ascii_uppercase),  # Pelo menos 1 letra maiúscula
                secrets.choice(string.digits),           # Pelo menos 1 número
            ]
            
            # Preencher o resto com letras e números aleatórios
            alphabet = string.ascii_letters + string.digits
            for _ in range(length - 3):
                password.append(secrets.choice(alphabet))
            
            # Embaralhar a senha
            secrets.SystemRandom().shuffle(password)
            
            return ''.join(password)
        else:
            # Senha simples de apenas números - para usuários antigos e superusuários
            return ''.join(secrets.choice(string.digits) for _ in range(length))
    
    # Caracteres permitidos: letras minúsculas, maiúsculas, números e símbolos
    alphabet = string.ascii_letters + string.digits + "!@#$%&*"
    
    # Garantir que a senha tenha pelo menos:
    # - 1 letra minúscula
    # - 1 letra maiúscula
    # - 1 número
    # - 1 símbolo
    
    password = [
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%&*")
    ]
    
    # Preencher o resto com caracteres aleatórios
    for _ in range(length - 4):
        password.append(secrets.choice(alphabet))
    
    # Embaralhar a senha
    secrets.SystemRandom().shuffle(password)
    
    return ''.join(password)


def send_user_credentials_email(user, plain_password=None, request=None):
    """
    Envia e-mail de boas-vindas com senha temporária (novo usuário).

    Requer plain_password. Sem senha, tenta apenas o fluxo de ativação por link (legado).
    """
    if plain_password:
        return send_user_welcome_email(user, plain_password, request=request)
    return send_account_activation_email(user, request=request)


def send_user_welcome_email(user, temporary_password, request=None):
    """E-mail de boas-vindas com credenciais e aviso de troca obrigatória de senha."""
    from .log_sanitizer import mask_email

    logger = __import__("logging").getLogger("security")

    try:
        if not user.email:
            logger.warning(
                "Boas-vindas: usuário sem e-mail",
                extra={"user_id": user.id},
            )
            return False

        if not temporary_password:
            logger.warning(
                "Boas-vindas: senha temporária ausente",
                extra={"user_id": user.id},
            )
            return False

        if user.role == "RM" or not user.company:
            user_type = getattr(settings, "EMAIL_BRAND_NAME", "RM Systems")
            login_url = f"{'https' if not settings.DEBUG else 'http'}://{getattr(settings, 'SITE_DOMAIN', 'localhost')}/rm/login/"
            if request:
                protocol = "https" if request.is_secure() else "http"
                login_url = f"{protocol}://{request.get_host()}/rm/login/"
        else:
            user_type = user.company.name
            if request:
                protocol = "https" if request.is_secure() else "http"
                login_url = f"{protocol}://{request.get_host()}/{user.company.slug}/login/"
            else:
                domain = getattr(settings, "SITE_DOMAIN", "rmsys.app")
                protocol = "http" if settings.DEBUG else "https"
                login_url = f"{protocol}://{domain}/{user.company.slug}/login/"

        context = {
            "user": user,
            "user_type": user_type,
            "temporary_password": temporary_password,
            "login_url": login_url,
            **get_email_branding_context(request),
        }

        subject = render_to_string(
            "core/email/user_welcome_subject.txt",
            context,
        ).strip()

        message = render_to_string(
            "core/email/user_welcome_email.html",
            context,
        )

        send_transactional_html(
            subject=subject,
            html=message,
            recipient_list=[user.email],
            fail_silently=False,
        )

        logger.info(
            "E-mail de boas-vindas enviado",
            extra={"user_id": user.id, "email_masked": mask_email(user.email)},
        )
        return True

    except Exception:
        logger.error(
            "Erro ao enviar e-mail de boas-vindas",
            extra={"user_id": user.id, "email_masked": mask_email(getattr(user, "email", ""))},
            exc_info=True,
        )
        return False


def send_account_activation_email(user, request=None):
    """
    Envia link de ativação expirável para o usuário definir a senha no primeiro acesso.
    """
    from .account_activation import ACTIVATION_EXPIRY_MINUTES, build_activation_url, create_activation_token
    from .log_sanitizer import mask_email

    logger = __import__("logging").getLogger("security")

    try:
        if not user.email:
            logger.warning(
                "Ativação: usuário sem e-mail",
                extra={"user_id": user.id},
            )
            return False

        raw_token = create_activation_token(user, request=request)
        activation_url = build_activation_url(request, raw_token)

        if user.role == "RM" or not user.company:
            user_type = "RM Systems"
            login_url_hint = activation_url.split("/ativar-conta/")[0] + "/rm/login/"
        else:
            user_type = user.company.name
            login_url_hint = (
                activation_url.split("/ativar-conta/")[0]
                + f"/{user.company.slug}/login/"
            )

        context = {
            "user": user,
            "activation_url": activation_url,
            "login_url": login_url_hint,
            "user_type": user_type,
            "expiry_minutes": ACTIVATION_EXPIRY_MINUTES,
            **get_email_branding_context(request),
        }

        subject = render_to_string(
            "core/email/account_activation_subject.txt",
            context,
        ).strip()

        message = render_to_string(
            "core/email/account_activation_email.html",
            context,
        )

        send_transactional_html(
            subject=subject,
            html=message,
            recipient_list=[user.email],
            fail_silently=False,
        )

        logger.info(
            "E-mail de ativação enviado",
            extra={"user_id": user.id, "email_masked": mask_email(user.email)},
        )
        return True

    except Exception as e:
        logger.error(
            "Erro ao enviar e-mail de ativação",
            extra={"user_id": user.id, "email_masked": mask_email(getattr(user, "email", ""))},
            exc_info=True,
        )
        return False


def _get_rm_ticket_notification_emails():
    """E-mails que recebem alertas de novos tickets (admins RM + suporte)."""
    from .models import CustomUser

    emails = set()
    support = (getattr(settings, "EMAIL_SUPPORT_EMAIL", "") or "").strip()
    if support:
        emails.add(support.lower())

    for admin in CustomUser.objects.filter(role="RM", is_active=True).exclude(email=""):
        if admin.email:
            emails.add(admin.email.strip().lower())

    if not emails:
        fallback = getattr(settings, "DEFAULT_FROM_EMAIL", None)
        if fallback:
            emails.add(fallback.strip().lower())

    return sorted(emails)


def send_ticket_created_email(ticket, request=None, actor=None):
    """
    Envia e-mails quando um ticket é criado:
    - Confirmação para o usuário (criador do ticket)
    - Alerta para a equipe RM Systems (admins RM + suporte@)

    Args:
        ticket: Instância do Ticket
        request: Objeto HttpRequest (para obter domain)
        actor: Usuário que abriu o ticket (request.user); usado para texto do e-mail RM

    Returns:
        bool: True se pelo menos um envio foi feito com sucesso
    """
    import logging
    from .log_sanitizer import mask_email

    logger = logging.getLogger(__name__)

    try:
        actor = actor or ticket.created_by
        opened_by_company_admin = bool(
            actor and getattr(actor, "is_company_admin", False)
        )

        if request:
            current_site = get_current_site(request)
            domain = current_site.domain
            protocol = "https" if request.is_secure() else "http"
        else:
            domain = getattr(settings, "SITE_DOMAIN", "rmsys.app")
            protocol = "https"

        company_ticket_url = (
            f"{protocol}://{domain}/{ticket.company.slug}/tickets/{ticket.id}/"
            if ticket.company
            else f"{protocol}://{domain}/rm/tickets/{ticket.id}/"
        )
        rm_ticket_url = f"{protocol}://{domain}/rm/tickets/{ticket.id}/"

        base_context = {
            "ticket": ticket,
            "user": ticket.created_by,
            "actor": actor,
            "company": ticket.company,
            "opened_by_company_admin": opened_by_company_admin,
            "domain": domain,
            "protocol": protocol,
            **get_email_branding_context(request),
        }

        user_sent = False
        creator = ticket.created_by
        creator_email = (getattr(creator, "email", None) or "").strip()

        if creator_email:
            user_context = {
                **base_context,
                "ticket_url": company_ticket_url,
            }
            user_subject = render_to_string(
                "core/email/ticket_created_subject.txt", user_context
            ).strip()
            user_html = render_to_string(
                "core/email/ticket_created_email.html", user_context
            )
            send_transactional_html(
                subject=user_subject,
                html=user_html,
                recipient_list=[creator_email],
                fail_silently=False,
            )
            user_sent = True
            logger.info(
                "E-mail de ticket criado enviado ao usuário",
                extra={
                    "ticket_id": ticket.id,
                    "ticket_number": ticket.ticket_number,
                    "email_masked": mask_email(creator_email),
                },
            )
        else:
            logger.warning(
                "Ticket criado sem e-mail do criador",
                extra={"ticket_id": ticket.id, "user_id": getattr(creator, "id", None)},
            )

        rm_context = {
            **base_context,
            "ticket_url": rm_ticket_url,
        }
        rm_subject = render_to_string(
            "core/email/ticket_created_rm_subject.txt", rm_context
        ).strip()
        rm_html = render_to_string(
            "core/email/ticket_created_rm_email.html", rm_context
        )

        rm_recipients = _get_rm_ticket_notification_emails()
        # Não duplicar o mesmo endereço do criador no alerta RM (conteúdos diferentes)
        creator_lower = creator_email.lower() if creator_email else ""
        rm_recipients = [e for e in rm_recipients if e != creator_lower]

        rm_sent = False
        for rm_email in rm_recipients:
            send_transactional_html(
                subject=rm_subject,
                html=rm_html,
                recipient_list=[rm_email],
                fail_silently=False,
            )
            rm_sent = True
            logger.info(
                "E-mail de novo ticket enviado à equipe RM",
                extra={
                    "ticket_id": ticket.id,
                    "email_masked": mask_email(rm_email),
                },
            )

        return user_sent or rm_sent

    except Exception as e:
        logger.error(
            "Erro ao enviar e-mail de ticket criado",
            extra={"ticket_id": getattr(ticket, "id", None)},
            exc_info=True,
        )
        return False


def send_ticket_message_email(ticket, message, request=None):
    """
    Envia email quando uma nova mensagem é adicionada ao ticket
    
    Args:
        ticket: Instância do Ticket
        message: Instância do TicketMessage
        request: Objeto HttpRequest
    
    Returns:
        bool: True se enviado com sucesso, False caso contrário
    """
    try:
        if request:
            current_site = get_current_site(request)
            domain = current_site.domain
            protocol = 'https' if request.is_secure() else 'http'
        else:
            domain = getattr(settings, 'SITE_DOMAIN', 'rmsys.app')
            protocol = 'https'
        
        # URL de visualização do ticket
        if ticket.company:
            ticket_url = f"{protocol}://{domain}/{ticket.company.slug}/tickets/{ticket.id}/"
        else:
            ticket_url = f"{protocol}://{domain}/rm/tickets/{ticket.id}/"
        
        # Determinar destinatário
        if message.sent_by == ticket.created_by:
            # Mensagem do cliente, enviar para RM
            # Enviar para todos os RM admins se não houver atendente atribuído
            if not ticket.assigned_to:
                from .models import CustomUser
                rm_admins = CustomUser.objects.filter(role='RM', is_active=True)
                recipients = [admin.email for admin in rm_admins if admin.email and admin.email]
                if not recipients:
                    recipients = [settings.DEFAULT_FROM_EMAIL]
            else:
                recipients = [ticket.assigned_to.email] if ticket.assigned_to.email else [settings.DEFAULT_FROM_EMAIL]
        else:
            # Mensagem do RM, enviar para o cliente
            recipients = [ticket.created_by.email] if ticket.created_by.email else [settings.DEFAULT_FROM_EMAIL]
        
        context = {
            'ticket': ticket,
            'message': message,
            'sender': message.sent_by,
            'ticket_url': ticket_url,
            'domain': domain,
            'protocol': protocol,
            **get_email_branding_context(request),
        }
        
        subject = render_to_string(
            'core/email/ticket_message_subject.txt',
            context
        ).strip()
        
        message_html = render_to_string(
            'core/email/ticket_message_email.html',
            context
        )
        
        for recipient_email in recipients:
            send_transactional_html(
                subject=subject,
                html=message_html,
                recipient_list=[recipient_email],
                fail_silently=False,
            )
        
        return True
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Erro ao enviar email de nova mensagem: {str(e)}", exc_info=True)
        return False

