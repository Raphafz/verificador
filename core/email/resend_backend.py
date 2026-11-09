"""Backend de e-mail Django via API Resend (https://resend.com)."""
from __future__ import annotations

import logging

import resend
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.message import EmailMessage, EmailMultiAlternatives

logger = logging.getLogger(__name__)


class ResendEmailBackend(BaseEmailBackend):
    """Envia e-mails usando a API Resend."""

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        api_key = getattr(settings, "RESEND_API_KEY", "")
        if not api_key:
            if not self.fail_silently:
                raise ValueError("RESEND_API_KEY não configurada.")
            logger.error("RESEND_API_KEY não configurada — e-mail não enviado.")
            return 0

        resend.api_key = api_key
        sent = 0

        for message in email_messages:
            try:
                params = self._build_params(message)
                response = resend.Emails.send(params)
                sent += 1
                logger.info(
                    "E-mail enviado via Resend",
                    extra={
                        "recipients": params.get("to"),
                        "subject": params.get("subject"),
                        "resend_id": getattr(response, "id", None) or response.get("id"),
                    },
                )
            except Exception:
                logger.exception("Falha ao enviar e-mail via Resend")
                if not self.fail_silently:
                    raise

        return sent

    def _build_params(self, message: EmailMessage) -> dict:
        html_body, text_body = self._extract_bodies(message)

        from_email = message.from_email or settings.DEFAULT_FROM_EMAIL
        recipients = list(message.to or [])
        if not recipients:
            raise ValueError("Nenhum destinatário informado.")

        params: dict = {
            "from": from_email,
            "to": recipients,
            "subject": message.subject or "(sem assunto)",
        }

        if html_body:
            params["html"] = html_body
        if text_body:
            params["text"] = text_body
        elif html_body and not text_body:
            params["text"] = "Abra este e-mail em um cliente compatível com HTML."

        if message.reply_to:
            params["reply_to"] = list(message.reply_to)

        cc = list(message.cc or [])
        bcc = list(message.bcc or [])
        if cc:
            params["cc"] = cc
        if bcc:
            params["bcc"] = bcc

        inline = getattr(message, "transactional_inline_attachments", None)
        if inline:
            params["attachments"] = inline

        tags = getattr(settings, "RESEND_DEFAULT_TAGS", None)
        if tags:
            params["tags"] = tags

        return params

    @staticmethod
    def _extract_bodies(message: EmailMessage) -> tuple[str | None, str | None]:
        text_body = (message.body or "").strip() or None
        html_body = None

        if isinstance(message, EmailMultiAlternatives):
            for content, mimetype in message.alternatives:
                if mimetype == "text/html":
                    html_body = content
                    break

        return html_body, text_body
