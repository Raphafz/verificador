"""Testa envio de todos os e-mails transacionais via Resend."""
from types import SimpleNamespace

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from core.email.send_transactional import send_transactional_html
from core.email_branding import get_email_branding_context
from core.models import Company, CustomUser, Ticket, TicketMessage
from core.utils import (
    _get_rm_ticket_notification_emails,
    generate_random_password,
    send_account_activation_email,
    send_user_welcome_email,
)


class Command(BaseCommand):
    help = (
        "Envia e-mails de teste via Resend. Use --all para todos os templates "
        "ou flags individuais (--welcome, --ticket-created, etc.)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--to",
            default="",
            help="Destinatário (padrão: EMAIL_SUPPORT_EMAIL ou marcelo.dengo@gmail.com)",
        )
        parser.add_argument(
            "--company",
            default="fibramar",
            help="Slug da empresa (padrão: fibramar)",
        )
        parser.add_argument(
            "--email",
            help="E-mail do usuário no banco (senão usa --to)",
        )
        parser.add_argument(
            "--ticket-id",
            type=int,
            help="ID do ticket para testes de chamado (senão usa o mais recente da empresa)",
        )
        parser.add_argument(
            "--list",
            action="store_true",
            help="Lista os tipos de e-mail disponíveis e sai",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Envia todos os templates de teste para --to",
        )
        parser.add_argument("--hello", action="store_true", help="E-mail simples de teste")
        parser.add_argument(
            "--password-reset",
            action="store_true",
            help="Recuperação de senha (portal da empresa)",
        )
        parser.add_argument(
            "--password-reset-rm",
            action="store_true",
            help="Recuperação de senha (portal RM)",
        )
        parser.add_argument(
            "--welcome",
            action="store_true",
            help="Boas-vindas com senha temporária",
        )
        parser.add_argument(
            "--activation",
            action="store_true",
            help="Ativação de conta (link para definir senha)",
        )
        parser.add_argument(
            "--ticket-created",
            action="store_true",
            help="Ticket criado (confirmação usuário + alerta RM -> --to)",
        )
        parser.add_argument(
            "--ticket-message-client",
            action="store_true",
            help="Nova mensagem no ticket (cliente -> RM, enviado para --to)",
        )
        parser.add_argument(
            "--ticket-message-rm",
            action="store_true",
            help="Nova mensagem no ticket (RM -> cliente, enviado para --to)",
        )

    def handle(self, *args, **options):
        if options["list"]:
            self._print_list()
            return

        backend = getattr(settings, "EMAIL_BACKEND", "")
        if "resend" not in backend.lower():
            self.stdout.write(
                self.style.WARNING(
                    f"EMAIL_BACKEND atual: {backend}\n"
                    "Configure EMAIL_BACKEND=core.email.resend_backend.ResendEmailBackend"
                )
            )

        if not getattr(settings, "RESEND_API_KEY", ""):
            raise CommandError("RESEND_API_KEY não configurada no .env")

        recipient = (options["to"] or "").strip()
        if not recipient:
            recipient = (
                getattr(settings, "EMAIL_SUPPORT_EMAIL", "") or "marcelo.dengo@gmail.com"
            ).strip()

        company_slug = options["company"]
        user_email = options.get("email")
        ticket_id = options.get("ticket_id")

        flags = [
            "hello",
            "password_reset",
            "password_reset_rm",
            "welcome",
            "activation",
            "ticket_created",
            "ticket_message_client",
            "ticket_message_rm",
        ]
        selected = []
        if options["all"]:
            selected = flags
        else:
            if options["hello"]:
                selected.append("hello")
            if options["password_reset"]:
                selected.append("password_reset")
            if options["password_reset_rm"]:
                selected.append("password_reset_rm")
            if options["welcome"]:
                selected.append("welcome")
            if options["activation"]:
                selected.append("activation")
            if options["ticket_created"]:
                selected.append("ticket_created")
            if options["ticket_message_client"]:
                selected.append("ticket_message_client")
            if options["ticket_message_rm"]:
                selected.append("ticket_message_rm")
            if not selected:
                selected = ["hello"]

        self.stdout.write(f"Destinatário: {recipient}")
        self.stdout.write(f"Remetente: {settings.DEFAULT_FROM_EMAIL}")
        self.stdout.write(f"Empresa: {company_slug}\n")

        for name in selected:
            method = getattr(self, f"_send_{name}")
            try:
                method(recipient, company_slug, user_email, ticket_id)
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"  [ERRO] {name}: {exc}"))

        self.stdout.write(self.style.SUCCESS("\nConcluído. Verifique a caixa de entrada e o painel Resend."))

    def _print_list(self):
        self.stdout.write("Tipos disponíveis (--all envia todos):\n")
        rows = [
            ("hello", "Teste simples Resend"),
            ("password_reset", "Esqueci a senha — empresa"),
            ("password_reset_rm", "Esqueci a senha — RM"),
            ("welcome", "Boas-vindas + senha temporária"),
            ("activation", "Ativação de conta (link)"),
            ("ticket_created", "Ticket novo (usuário + RM)"),
            ("ticket_message_client", "Mensagem no ticket (cliente para RM)"),
            ("ticket_message_rm", "Mensagem no ticket (RM para cliente)"),
        ]
        for flag, desc in rows:
            self.stdout.write(f"  --{flag.replace('_', '-'):28} {desc}")

    def _protocol_domain(self):
        domain = getattr(settings, "SITE_DOMAIN", "127.0.0.1:8000")
        protocol = "http" if settings.DEBUG else "https"
        return protocol, domain

    def _get_company(self, company_slug: str) -> Company:
        try:
            return Company.objects.get(slug=company_slug, is_active=True)
        except Company.DoesNotExist as exc:
            raise CommandError(f"Empresa '{company_slug}' não encontrada.") from exc

    def _resolve_user(self, company: Company, recipient: str, user_email: str | None):
        lookup = (user_email or recipient).strip()
        user = CustomUser.objects.filter(
            email__iexact=lookup,
            company=company,
            is_active=True,
        ).first()
        if user:
            return user
        rm_user = CustomUser.objects.filter(
            email__iexact=lookup,
            role="RM",
            is_active=True,
        ).first()
        if rm_user:
            return rm_user
        return CustomUser(
            username="usuario_teste_email",
            email=recipient,
            first_name="Usuário",
            last_name="Teste",
            company=company,
            role="COMPANY_USER",
            is_active=True,
        )

    def _get_ticket(self, company_slug: str, ticket_id: int | None) -> Ticket:
        company = self._get_company(company_slug)
        qs = Ticket.objects.filter(company=company).select_related(
            "created_by", "company", "assigned_to"
        )
        if ticket_id:
            ticket = qs.filter(pk=ticket_id).first()
            if not ticket:
                raise CommandError(f"Ticket id={ticket_id} não encontrado em {company_slug}.")
            return ticket
        ticket = qs.order_by("-created_at").first()
        if not ticket:
            raise CommandError(
                f"Nenhum ticket em {company_slug}. Crie um chamado ou use --ticket-id."
            )
        return ticket

    def _send_hello(self, recipient, company_slug, user_email, ticket_id):
        send_mail(
            subject="[TESTE] RM Systems — hello Resend",
            message="E-mail de teste enviado pelo comando test_resend_email.",
            html_message=(
                "<p><strong>[TESTE]</strong> E-mail simples via Resend.</p>"
                "<p>RM Systems — Verificador de Viabilidade</p>"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )
        self.stdout.write(self.style.SUCCESS("  [OK] hello"))

    def _send_password_reset(self, recipient, company_slug, user_email, ticket_id):
        company = self._get_company(company_slug)
        user = self._resolve_user(company, recipient, user_email)
        if not user.pk:
            raise CommandError("Usuário não encontrado no banco — necessário para reset empresa.")

        protocol, domain = self._protocol_domain()
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
            **get_email_branding_context(),
        }
        subject = "[TESTE] " + render_to_string(
            "company/password_reset_subject.txt", context
        ).strip()
        html = render_to_string("core/email/password_reset.html", context)
        send_transactional_html(
            subject=subject, html=html, recipient_list=[recipient], fail_silently=False
        )
        self.stdout.write(self.style.SUCCESS(f"  [OK] password_reset -> {recipient}"))

    def _send_password_reset_rm(self, recipient, company_slug, user_email, ticket_id):
        lookup = (user_email or recipient).strip()
        user = CustomUser.objects.filter(
            email__iexact=lookup, role="RM", is_active=True
        ).first()
        if not user:
            user = CustomUser.objects.filter(role="RM", is_active=True).first()
        if not user:
            raise CommandError("Nenhum usuário RM ativo no banco.")

        protocol, domain = self._protocol_domain()
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
            **get_email_branding_context(),
        }
        subject = "[TESTE] " + render_to_string("rm/password_reset_subject.txt", context).strip()
        html = render_to_string("core/email/password_reset.html", context)
        send_transactional_html(
            subject=subject, html=html, recipient_list=[recipient], fail_silently=False
        )
        self.stdout.write(self.style.SUCCESS(f"  [OK] password_reset_rm -> {recipient}"))

    def _send_welcome(self, recipient, company_slug, user_email, ticket_id):
        company = self._get_company(company_slug)
        user = self._resolve_user(company, recipient, user_email)
        user.email = recipient
        temp_password = generate_random_password(length=14, simple=True, alphanumeric=True)
        if not send_user_welcome_email(user, temp_password):
            raise CommandError("Falha ao enviar boas-vindas.")
        self.stdout.write(
            self.style.SUCCESS(
                f"  [OK] welcome -> {recipient} (senha teste: {temp_password})"
            )
        )

    def _send_activation(self, recipient, company_slug, user_email, ticket_id):
        company = self._get_company(company_slug)
        user = self._resolve_user(company, recipient, user_email)
        if not user.pk:
            raise CommandError(
                "Usuário precisa existir no banco para gerar token de ativação."
            )
        original = user.email
        user.email = recipient
        try:
            if not send_account_activation_email(user):
                raise CommandError("Falha ao enviar ativação.")
        finally:
            user.email = original
        self.stdout.write(self.style.SUCCESS(f"  [OK] activation -> {recipient}"))

    def _send_ticket_created(self, recipient, company_slug, user_email, ticket_id):
        ticket = self._get_ticket(company_slug, ticket_id)
        company = ticket.company
        actor = ticket.created_by

        protocol, domain = self._protocol_domain()
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
            **get_email_branding_context(),
        }

        user_subject = "[TESTE usuário] " + render_to_string(
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

        rm_subject = "[TESTE RM] " + render_to_string(
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

        prod_rm = ", ".join(_get_rm_ticket_notification_emails()) or "(nenhum)"
        self.stdout.write(
            self.style.SUCCESS(
                f"  [OK] ticket_created -> {recipient} (2 e-mails: usuário + RM)\n"
                f"      Ticket: {ticket.ticket_number} | Em produção RM recebe: {prod_rm}"
            )
        )

    def _send_ticket_message_client(self, recipient, company_slug, user_email, ticket_id):
        ticket = self._get_ticket(company_slug, ticket_id)
        msg = self._message_for_ticket(ticket, as_client=True)
        self._send_ticket_message_to_recipient(ticket, msg, recipient, label="cliente-RM")

    def _send_ticket_message_rm(self, recipient, company_slug, user_email, ticket_id):
        ticket = self._get_ticket(company_slug, ticket_id)
        msg = self._message_for_ticket(ticket, as_client=False)
        self._send_ticket_message_to_recipient(ticket, msg, recipient, label="RM-cliente")

    def _message_for_ticket(self, ticket: Ticket, as_client: bool) -> TicketMessage:
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

        sender = ticket.created_by if as_client else (
            ticket.assigned_to
            or CustomUser.objects.filter(role="RM", is_active=True).first()
            or ticket.created_by
        )
        return SimpleNamespace(
            message="Mensagem de teste do comando test_resend_email.",
            sent_by=sender,
            created_at=ticket.updated_at or ticket.created_at,
        )

    def _send_ticket_message_to_recipient(
        self, ticket: Ticket, message, recipient: str, label: str
    ):
        protocol, domain = self._protocol_domain()
        ticket_url = f"{protocol}://{domain}/{ticket.company.slug}/tickets/{ticket.id}/"
        context = {
            "ticket": ticket,
            "message": message,
            "sender": message.sent_by,
            "ticket_url": ticket_url,
            "domain": domain,
            "protocol": protocol,
            **get_email_branding_context(),
        }
        subject = "[TESTE " + label + "] " + render_to_string(
            "core/email/ticket_message_subject.txt", context
        ).strip()
        html = render_to_string("core/email/ticket_message_email.html", context)
        send_transactional_html(
            subject=subject, html=html, recipient_list=[recipient], fail_silently=False
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"  [OK] ticket_message ({label}) -> {recipient} | {ticket.ticket_number}"
            )
        )
