"""Mensagens na tela de login quando a sessão foi encerrada."""
from django.contrib import messages


SESSION_END_MESSAGES = {
    "replaced": (
        "Sua sessão foi encerrada porque este usuário entrou em outro dispositivo "
        "ou em outro endereço IP."
    ),
    "expired": "Sua sessão expirou. Faça login novamente.",
    "ip_changed": (
        "Sua sessão foi encerrada porque o endereço IP da conexão mudou. "
        "Entre novamente se foi você."
    ),
    "invalid": "Sessão inválida ou expirada. Faça login novamente.",
}


def flash_session_end_reason(request) -> None:
    reason = (request.GET.get("session") or "").strip().lower()
    if reason in SESSION_END_MESSAGES:
        messages.warning(request, SESSION_END_MESSAGES[reason])
    if request.GET.get("idle"):
        messages.info(request, "Sua sessão expirou por inatividade. Faça login novamente.")
