"""Endpoints MFA — setup, verify, recovery (JWT)."""
from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError

from core.api_permissions import RequireMfaVerified
from core.jwt_tokens import MfaPendingToken, claim_mfa_verified, issue_mfa_pending_token, issue_token_pair
from core.mfa_lockout import clear_mfa_failures, is_mfa_locked, record_mfa_failure
from core.mfa_service import (
    create_totp_device,
    generate_backup_codes,
    has_mfa_enabled,
    mfa_required_for,
    provisioning_uri,
    qr_png_base64,
    verify_backup_code,
    verify_token,
)
from core.request_ip import get_client_ip
from core.spa_session_bridge import establish_django_session
from core.serializers import UserSerializer
from django.contrib.auth import get_user_model

User = get_user_model()


def _resolve_mfa_user(request, mfa_pending_token: str | None = None):
    if mfa_pending_token:
        try:
            token = MfaPendingToken(mfa_pending_token)
            return User.objects.get(pk=token["user_id"])
        except (TokenError, User.DoesNotExist, KeyError):
            return None
    if request.user.is_authenticated:
        return request.user
    return None


def _full_login_payload(user, *, mfa_verified: bool) -> dict:
    tokens = issue_token_pair(user, mfa_verified=mfa_verified)
    return {
        **tokens,
        "user": UserSerializer(user).data,
        "mfa_verified": mfa_verified,
        "needs_mfa": False,
        "must_change_password": bool(getattr(user, "must_change_password", False)),
    }


class MfaSetupAPIView(APIView):
    """
    POST /api/v1/auth/mfa/setup/
    - Sem `code`: inicia setup (otpauth URI + QR base64).
    - Com `code`: confirma TOTP e retorna backup codes.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        if not mfa_required_for(user):
            return Response({"detail": "MFA não é obrigatório para este usuário."}, status=400)

        code = (request.data.get("code") or request.data.get("token") or "").strip()

        if not code:
            device = create_totp_device(user)
            uri = provisioning_uri(device)
            return Response(
                {
                    "provisioning_uri": uri,
                    "qr_base64": qr_png_base64(uri),
                    "needs_confirmation": True,
                }
            )

        if verify_token(user, code):
            backup_codes = generate_backup_codes(user)
            return Response(
                {
                    "done": True,
                    "backup_codes": backup_codes,
                    "message": "MFA ativado. Guarde os códigos de backup.",
                }
            )

        return Response({"detail": "Código inválido."}, status=status.HTTP_400_BAD_REQUEST)


class MfaVerifyAPIView(APIView):
    """POST /api/v1/auth/mfa/verify/ — valida TOTP e emite token com mfa_verified=true."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        pending = (request.data.get("mfa_pending_token") or "").strip()
        code = (request.data.get("token") or request.data.get("code") or "").strip()
        backup = (request.data.get("backup_code") or "").strip()

        user = _resolve_mfa_user(request, pending or None)
        if user is None:
            return Response(
                {"detail": "Sessão MFA expirada ou token inválido. Faça login novamente."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        ip = get_client_ip(request)
        locked, retry = is_mfa_locked(user.pk, ip)
        if locked:
            return Response(
                {"detail": f"Muitas tentativas. Aguarde {retry // 60 + 1} minuto(s)."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        ok = verify_backup_code(user, backup) if backup else verify_token(user, code)
        if not ok:
            record_mfa_failure(user.pk, ip)
            return Response({"detail": "Código inválido."}, status=status.HTTP_401_UNAUTHORIZED)

        clear_mfa_failures(user.pk, ip)
        establish_django_session(request, user)
        return Response(_full_login_payload(user, mfa_verified=True))


class MfaRecoveryAPIView(APIView):
    """POST /api/v1/auth/mfa/recovery/ — regenera backup codes após TOTP válido."""

    permission_classes = [IsAuthenticated, RequireMfaVerified]

    def post(self, request):
        code = (request.data.get("token") or request.data.get("code") or "").strip()
        if not code or not verify_token(request.user, code):
            return Response({"detail": "Informe um código TOTP válido."}, status=400)

        backup_codes = generate_backup_codes(request.user)
        return Response({"backup_codes": backup_codes, "done": True})
