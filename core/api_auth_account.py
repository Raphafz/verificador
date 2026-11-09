"""Ativação de conta e password reset — API JWT-friendly."""
from __future__ import annotations

import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.account_activation import consume_activation_token, get_user_for_activation_token
from core.jwt_tokens import issue_token_pair
from core.models import Company
from core.password_reset import CompanyPasswordResetView
from core.serializers import UserSerializer

logger = logging.getLogger(__name__)
User = get_user_model()


class ActivateAPIView(APIView):
    """POST /api/v1/auth/activate/ — ativação por link (RM/empresa)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        token = (request.data.get("token") or "").strip()
        password = (request.data.get("password") or request.data.get("password1") or "").strip()
        confirm = (request.data.get("password_confirm") or request.data.get("password2") or "").strip()

        if not token or not password:
            return Response({"detail": "Token e senha são obrigatórios."}, status=400)
        if password != confirm:
            return Response({"detail": "As senhas não coincidem."}, status=400)

        user, record = get_user_for_activation_token(token)
        if not user:
            return Response({"detail": "Link inválido ou expirado."}, status=403)

        try:
            validate_password(password, user)
        except ValidationError as exc:
            return Response({"detail": " ".join(exc.messages)}, status=400)

        user.set_password(password)
        user.must_change_password = False
        user.is_active = True
        user.save(update_fields=["password", "must_change_password", "is_active"])

        consumed = consume_activation_token(token, request)
        if not consumed:
            return Response({"detail": "Não foi possível concluir a ativação."}, status=400)

        from core.mfa_service import has_mfa_enabled, mfa_required_for

        mfa_ok = not (mfa_required_for(user) and has_mfa_enabled(user))
        tokens = issue_token_pair(user, mfa_verified=mfa_ok)
        return Response(
            {
                **tokens,
                "user": UserSerializer(user).data,
                "mfa_verified": mfa_ok,
                "needs_mfa": mfa_required_for(user) and has_mfa_enabled(user),
            },
            status=status.HTTP_200_OK,
        )


class PasswordResetRequestAPIView(APIView):
    """POST /api/v1/auth/password-reset/ — solicita e-mail de redefinição."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        email = (request.data.get("email") or "").strip()
        company_slug = (request.data.get("company_slug") or "").strip() or None

        if not email:
            return Response({"detail": "Informe o e-mail."}, status=400)

        msg = "Se o e-mail estiver cadastrado, você receberá um link para redefinir a senha."

        if company_slug:
            try:
                company = Company.objects.get(slug=company_slug, is_active=True)
            except Company.DoesNotExist:
                return Response({"detail": msg})
            users = User.objects.filter(email__iexact=email, company=company, is_active=True)
            if users.exists():
                view = CompanyPasswordResetView()
                view.request = request
                view.company = company
                for user in users:
                    view.send_reset_email(user)
        else:
            users = User.objects.filter(email__iexact=email, is_active=True, role="RM")
            if users.exists():
                from core.password_reset import RMPasswordResetView

                view = RMPasswordResetView()
                view.request = request
                for user in users:
                    try:
                        view.send_reset_email(user)
                    except AttributeError:
                        logger.warning("Password reset RM via API: send_reset_email indisponível")

        return Response({"detail": msg})


class PasswordResetConfirmAPIView(APIView):
    """POST /api/v1/auth/password-reset/confirm/ — confirma nova senha."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        uidb64 = (request.data.get("uid") or request.data.get("uidb64") or "").strip()
        token = (request.data.get("token") or "").strip()
        new_password = (request.data.get("new_password") or request.data.get("password") or "").strip()
        company_slug = (request.data.get("company_slug") or "").strip() or None

        if not uidb64 or not token or not new_password:
            return Response({"detail": "Parâmetros incompletos."}, status=400)

        try:
            uid = urlsafe_base64_decode(uidb64).decode()
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response({"detail": "Link inválido."}, status=400)

        if company_slug and (not user.company or user.company.slug != company_slug):
            return Response({"detail": "Link inválido para esta empresa."}, status=400)

        if not default_token_generator.check_token(user, token):
            return Response({"detail": "Link expirado ou inválido."}, status=400)

        try:
            validate_password(new_password, user)
        except ValidationError as exc:
            return Response({"detail": " ".join(exc.messages)}, status=400)

        user.set_password(new_password)
        user.save(update_fields=["password"])
        return Response({"detail": "Senha redefinida com sucesso."})
