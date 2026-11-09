"""Envio de e-mails transacionais pelo painel RM (seleção de template)."""
from dataclasses import dataclass
from types import SimpleNamespace

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from core.account_activation import ACTIVATION_EXPIRY_MINUTES
from core.email.send_transactional import send_transactional_html
from core.email_branding import get_email_branding_context
from core.models import CustomUser, Ticket, TicketMessage
from core.utils import (
    generate_random_password,
    send_account_activation_email,
    send_user_welcome_email,
)


@dataclass(frozen=True)
class RmEmailTemplate:
    id: str
    label: str
    description: str
    requires_company: bool = False
    requires_rm_role: bool = False
    requires_ticket: bool = False


RM_EMAIL_TEMPLATES = (
    RmEmailTemplate("activation", "Ativação de conta", "Link para definir senha"),
    RmEmailTemplate(
        "welcome",
        "Boas-vindas",
        "Senha temporária (obriga troca no login)",
    ),
    RmEmailTemplate(
        "password_reset",
        "Recuperação de senha (empresa)",
        "Link esqueci a senha — portal da empresa",
        requires_company=True,
    ),
    RmEmailTemplate(
        "password_reset_rm",
        "Recuperação de senha (RM)",
        "Link esqueci a senha — portal RM",
        requires_rm_role=True,
    ),
    RmEmailTemplate("hello", "Teste simples", "E-mail básico de teste Resend"),
    RmEmailTemplate(
        "ticket_created",
        "Chamado criado",
        "Confirmação usuário + alerta RM (2 e-mails)",
        requires_company=True,
        requires_ticket=True,
    ),
    RmEmailTemplate(
        "ticket_message_client",
        "Mensagem no chamado (cliente→RM)",
        "Nova mensagem enviada pelo cliente",
        requires_company=True,
        requires_ticket=True,
    ),
    RmEmailTemplate(
        "ticket_message_rm",
        "Mensagem no chamado (RM→cliente)",
        "Resposta RM ao cliente",
        requires_company=True,
        requires_ticket=True,
    ),
)


def get_template(template_id: str) -> RmEmailTemplate | None:
    for template in RM_EMAIL_TEMPLATES:
        if template.id == template_id:
            return template
    return None


def _user_has_ticket(user: CustomUser) -> bool:
    if not user.company_id:
        return False
    return Ticket.objects.filter(company_id=user.company_id).exists()


def get_templates_for_user(user: CustomUser) -> list[dict]:
    """Templates aplicáveis ao usuário (para o select no painel RM)."""
    has_ticket = _user_has_ticket(user)
    options = []
    for template in RM_EMAIL_TEMPLATES:
        if template.requires_rm_role and user.role != "RM":
            continue
        if template.requires_company and (user.role == "RM" or not user.company_id):
            continue
        if template.requires_ticket and not has_ticket:
            continue
        options.append(
            {
                "id": template.id,
                "label": template.label,
                "description": template.description,
            }
        )
    return options


def _protocol_domain(request=None):
    if request:
        protocol = "https" if request.is_secure() else "http"
        domain = request.get_host()
    else:
        domain = getattr(settings, "SITE_DOMAIN", "127.0.0.1:8000")
        protocol = "http" if settings.DEBUG else "https"
    return protocol, domain


def _resend_delivery_hint() -> str:
    from_email = (getattr(settings, "DEFAULT_FROM_EMAIL", "") or "").lower()
    if "resend.dev" in from_email or settings.DEBUG:
        return (
            " Se não chegar na caixa de entrada, verifique spam e o painel "
            "Resend (resend.com/emails). Em teste, o Resend só entrega para "
            "e-mails verificados na sua conta."
        )
    return ""


def success_message(template_id: str, user: CustomUser) -> str:
    template = get_template(template_id)
    label = template.label if template else template_id
    msg = f"E-mail «{label}» enviado para {user.email}."
    if template_id == "activation":
        msg += f" O link expira em {ACTIVATION_EXPIRY_MINUTES} minutos."
    elif template_id == "welcome":
        msg += " A senha temporária foi definida no cadastro do usuário."
    elif template_id == "ticket_created":
        msg += " Foram enviados 2 e-mails (versão usuário e versão RM)."
    msg += _resend_delivery_hint()
    return msg


def _get_ticket_for_user(user: CustomUser, ticket_id: int | None = None) -> Ticket:
    if not user.company_id:
        raise ValueError("Usuário sem empresa — não há chamados.")

    qs = Ticket.objects.filter(company_id=user.company_id).select_related(
        "created_by", "company", "assigned_to"
    )
    if ticket_id:
        ticket = qs.filter(pk=ticket_id).first()
        if not ticket:
            raise ValueError(
                f"Chamado #{ticket_id} não encontrado na empresa do usuário."
            )
        return ticket

    ticket = qs.order_by("-created_at").first()
    if not ticket:
        raise ValueError(
            "Nenhum chamado na empresa deste usuário. Crie um chamado primeiro."
        )
    return ticket


def _message_for_ticket(ticket: Ticket, as_client: bool):
    msg = (
        TicketMessage.objects.filter(ticket=ticket)
        .select_related("sent_by")
        .order_by("-created_at")
        .first()
    )
    if msg:
        if as_client and msg.sent_by_id != ticket.created_by_id:
            pass
        elif not as_client and msg.sent_by and getattr(msg.sent_by, "role", "") == "RM":
            return msg
        elif msg:
            return msg

    sender = (
        ticket.created_by
        if as_client
        else (
            ticket.assigned_to
            or CustomUser.objects.filter(role="RM", is_active=True).first()
            or ticket.created_by
        )
    )
    return SimpleNamespace(
        message="Mensagem de exemplo enviada pelo painel RM.",
        sent_by=sender,
        created_at=ticket.updated_at or ticket.created_at,
    )


def send_rm_user_email(
    template_id: str,
    user: CustomUser,
    *,
    request=None,
    ticket_id: int | None = None,
) -> bool:
    recipient = (user.email or "").strip()
    if not recipient:
        return False

    if template_id == "activation":
        return send_account_activation_email(user, request=request)

    if template_id == "welcome":
        temp_password = generate_random_password(length=14, simple=True, alphanumeric=True)
        user.set_password(temp_password)
        user.must_change_password = True
        user.save(update_fields=["password", "must_change_password"])
        return send_user_welcome_email(user, temp_password, request=request)

    if template_id == "hello":
        send_mail(
            subject="RM Systems — teste de e-mail",
            message="E-mail de teste enviado pelo painel RM.",
            html_message=(
                "<p>E-mail simples de teste via Resend.</p>"
                "<p>RM Systems — Verificador de Viabilidade</p>"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )
        return True

    if template_id == "password_reset":
        if not user.company_id:
            raise ValueError("Usuário sem empresa — use recuperação RM.")
        company = user.company
        protocol, domain = _protocol_domain(request)
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        reset_path = reverse(
            "company:password_reset_confirm",
            kwargs={"company_slug": company.slug, "uidb64": uid, "token": token},
        )
        reset_url = f"{protocol}://{domain}{reset_path}"
        context = {
            "user": user,
            "company": company,
            "reset_url": reset_url,
            "domain": domain,
            "protocol": protocol,
            "site_name": "RM Systems",
            **get_email_branding_context(request),
        }
        subject = render_to_string("company/password_reset_subject.txt", context).strip()
        html = render_to_string("core/email/password_reset.html", context)
        send_transactional_html(
            subject=subject, html=html, recipient_list=[recipient], fail_silently=False
        )
        return True

    if template_id == "password_reset_rm":
        if user.role != "RM":
            raise ValueError("Template RM só para usuários com perfil RM.")
        protocol, domain = _protocol_domain(request)
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        reset_path = reverse(
            "rm:password_reset_confirm",
            kwargs={"uidb64": uid, "token": token},
        )
        reset_url = f"{protocol}://{domain}{reset_path}"
        context = {
            "user": user,
            "reset_url": reset_url,
            "domain": domain,
            "protocol": protocol,
            "site_name": "RM Systems",
            **get_email_branding_context(request),
        }
        subject = render_to_string("rm/password_reset_subject.txt", context).strip()
        html = render_to_string("core/email/password_reset.html", context)
        send_transactional_html(
            subject=subject, html=html, recipient_list=[recipient], fail_silently=False
        )
        return True

    if template_id == "ticket_created":
        ticket = _get_ticket_for_user(user, ticket_id)
        company = ticket.company
        actor = ticket.created_by
        protocol, domain = _protocol_domain(request)
        user_url = f"{protocol}://{domain}/{company.slug}/tickets/{ticket.id}/"
        rm_url = f"{protocol}://{domain}/rm/tickets/{ticket.id}/"
        base = {
            "ticket": ticket,
            "user": ticket.created_by,
            "actor": actor,
            "company": company,
            "opened_by_company_admin": getattr(actor, "is_company_admin", False),
            "domain": domain,
            "protocol": protocol,
            **get_email_branding_context(request),
        }
        user_subject = render_to_string(
            "core/email/ticket_created_subject.txt", {**base, "ticket_url": user_url}
        ).strip()
        user_html = render_to_string(
            "core/email/ticket_created_email.html", {**base, "ticket_url": user_url}
        )
        send_transactional_html(
            subject=user_subject,
            html=user_html,
            recipient_list=[recipient],
            fail_silently=False,
        )
        rm_subject = render_to_string(
            "core/email/ticket_created_rm_subject.txt", {**base, "ticket_url": rm_url}
        ).strip()
        rm_html = render_to_string(
            "core/email/ticket_created_rm_email.html", {**base, "ticket_url": rm_url}
        )
        send_transactional_html(
            subject=rm_subject,
            html=rm_html,
            recipient_list=[recipient],
            fail_silently=False,
        )
        return True

    if template_id in ("ticket_message_client", "ticket_message_rm"):
        ticket = _get_ticket_for_user(user, ticket_id)
        as_client = template_id == "ticket_message_client"
        message = _message_for_ticket(ticket, as_client=as_client)
        protocol, domain = _protocol_domain(request)
        ticket_url = f"{protocol}://{domain}/{ticket.company.slug}/tickets/{ticket.id}/"
        context = {
            "ticket": ticket,
            "message": message,
            "sender": message.sent_by,
            "ticket_url": ticket_url,
            "domain": domain,
            "protocol": protocol,
            **get_email_branding_context(request),
        }
        subject = render_to_string("core/email/ticket_message_subject.txt", context).strip()
        html = render_to_string("core/email/ticket_message_email.html", context)
        send_transactional_html(
            subject=subject, html=html, recipient_list=[recipient], fail_silently=False
        )
        return True

    raise ValueError(f"Template de e-mail desconhecido: {template_id}")
