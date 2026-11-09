# -----------------------------------------------------------------------------
# Sinal opcional para limitar um usuário a uma única sessão ativa.
# -----------------------------------------------------------------------------
# Como habilitar:
# 1. Descomente este arquivo inteiro, removendo os prefixos '# ' das linhas.
# 2. Em core/apps.py, descomente a importação de 'core.signals_single_session'
#    para que o Django registre o listener `user_logged_in`.
# 3. Garanta que o modelo `UserSession` também esteja ativo em core/models.py.
# 4. Rode migrações para criar a tabela de controle de sessões.
#
# from django.contrib.auth.signals import user_logged_in
# from django.contrib.sessions.models import Session
# from django.dispatch import receiver
#
# from .models import UserSession
#
#
# @receiver(user_logged_in)
# def ensure_single_session(sender, request, user, **kwargs):
#     """
#     Mantém apenas uma sessão por usuário:
#     - Registra a sessão atual na tabela UserSession.
#     - Remove a sessão anterior se ainda estiver ativa.
#     """
#     session_key = request.session.session_key
#
#     if not session_key:
#         return
#
#     user_session, _created = UserSession.objects.get_or_create(user=user)
#
#     previous_key = user_session.session_key
#     if previous_key and previous_key != session_key:
#         Session.objects.filter(session_key=previous_key).delete()
#
#     user_session.session_key = session_key
#     user_session.save(update_fields=['session_key', 'updated_at'])

