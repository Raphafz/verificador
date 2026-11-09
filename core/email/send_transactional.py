"""Envio de e-mails HTML transacionais com imagens inline (CID)."""
from __future__ import annotations

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

from core.email_branding import (
    _should_embed_images,
    get_email_inline_attachments,
)


def send_transactional_html(
    *,
    subject: str,
    html: str,
    recipient_list: list[str],
    fail_silently: bool = False,
) -> int:
    msg = EmailMultiAlternatives(
        subject=subject,
        body="Abra este e-mail em um cliente compatível com HTML.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=recipient_list,
    )
    msg.attach_alternative(html, "text/html")

    if _should_embed_images():
        inline = get_email_inline_attachments()
        if inline:
            msg.transactional_inline_attachments = inline

    return msg.send(fail_silently=fail_silently)
