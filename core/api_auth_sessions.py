"""Sessões JWT (refresh tokens) e dispositivos confiáveis MFA."""
from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from core.api_permissions import RequireMfaVerified
from core.mfa_service import list_trusted_devices, revoke_all_trusted_devices, revoke_trusted_device
from core.models import UserSessionRecord
from core.session_security import revoke_session_record


class TrustedDevicesAPIView(APIView):
    """GET/DELETE /api/v1/auth/trusted-devices/"""

    permission_classes = [IsAuthenticated, RequireMfaVerified]

    def get(self, request):
        devices = list_trusted_devices(request.user)
        data = [
            {
                "id": d.pk,
                "label": d.device_label,
                "ip_address": d.ip_address,
                "created_at": d.created_at,
                "last_used_at": d.last_used_at,
                "expires_at": d.expires_at,
            }
            for d in devices
        ]
        return Response({"devices": data})

    def delete(self, request):
        device_id = request.data.get("device_id") or request.query_params.get("device_id")
        if device_id == "all":
            n = revoke_all_trusted_devices(request.user)
            return Response({"revoked": n})
        if device_id:
            ok = revoke_trusted_device(request.user, int(device_id))
            if ok:
                return Response({"revoked": 1})
            return Response({"detail": "Dispositivo não encontrado."}, status=404)
        return Response({"detail": "Informe device_id ou device_id=all."}, status=400)


class SessionsAPIView(APIView):
    """GET/DELETE /api/v1/auth/sessions/ — sessões Django + refresh tokens JWT."""

    permission_classes = [IsAuthenticated, RequireMfaVerified]

    def get(self, request):
        from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

        django_sessions = UserSessionRecord.objects.filter(
            user=request.user,
            revoked_at__isnull=True,
        ).order_by("-last_seen_at")

        jwt_tokens = OutstandingToken.objects.filter(user=request.user).order_by("-created_at")

        return Response(
            {
                "django_sessions": [
                    {
                        "id": s.pk,
                        "type": "django_session",
                        "ip_address": s.ip_address,
                        "user_agent": s.user_agent,
                        "is_current": s.session_key == request.session.session_key,
                        "last_seen_at": s.last_seen_at,
                        "expires_at": s.expires_at,
                    }
                    for s in django_sessions
                ],
                "jwt_refresh_tokens": [
                    {
                        "id": t.pk,
                        "type": "jwt_refresh",
                        "jti": str(t.jti),
                        "created_at": t.created_at,
                        "expires_at": t.expires_at,
                        "blacklisted": BlacklistedToken.objects.filter(token=t).exists(),
                    }
                    for t in jwt_tokens
                ],
            }
        )

    def delete(self, request):
        session_id = request.data.get("session_id") or request.query_params.get("session_id")
        session_type = (request.data.get("type") or request.query_params.get("type") or "").strip()

        if not session_id:
            return Response({"detail": "Informe session_id e type."}, status=400)

        if session_type == "django_session":
            rec = UserSessionRecord.objects.filter(
                pk=session_id,
                user=request.user,
                revoked_at__isnull=True,
            ).first()
            if not rec:
                return Response({"detail": "Sessão não encontrada."}, status=404)
            if rec.session_key == request.session.session_key:
                return Response(
                    {"detail": "Use logout para encerrar a sessão atual."},
                    status=400,
                )
            revoke_session_record(rec)
            return Response({"revoked": True})

        if session_type == "jwt_refresh":
            from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

            rec = OutstandingToken.objects.filter(pk=session_id, user=request.user).first()
            if not rec:
                return Response({"detail": "Token não encontrado."}, status=404)
            try:
                RefreshToken(str(rec.token)).blacklist()
            except TokenError:
                pass
            return Response({"revoked": True})

        return Response({"detail": "type deve ser django_session ou jwt_refresh."}, status=400)
