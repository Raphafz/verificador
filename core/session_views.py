"""Gestão de sessões ativas — revogação pelo usuário."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from core.models import UserSessionRecord
from core.permissions import rm_admin_required
from core.session_security import revoke_all_sessions, revoke_session_record


@login_required
def my_sessions(request):
    records = UserSessionRecord.objects.filter(
        user=request.user,
        revoked_at__isnull=True,
    ).order_by("-last_seen_at")
    sk = request.session.session_key
    return render(request, "core/my_sessions.html", {
        "sessions": records,
        "current_key": sk,
    })


@login_required
@require_POST
def revoke_session(request, session_id: int):
    rec = UserSessionRecord.objects.filter(
        pk=session_id,
        user=request.user,
        revoked_at__isnull=True,
    ).first()
    if rec and rec.session_key != request.session.session_key:
        revoke_session_record(rec)
        messages.success(request, "Sessão encerrada.")
    elif rec:
        messages.warning(request, "Use sair para encerrar a sessão atual.")
    return redirect("rm:my_sessions")


@login_required
@require_POST
def revoke_all_other_sessions(request):
    n = revoke_all_sessions(request.user, except_session_key=request.session.session_key)
    messages.success(request, f"{n} sessão(ões) encerrada(s).")
    return redirect("rm:my_sessions")
