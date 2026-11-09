"""API de autenticação JWT — login, logout, me, change-password, tenant context."""
from __future__ import annotations

from django.contrib.auth import authenticate, get_user_model
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from core.api_permissions import RequireMfaVerified
from core.api_tenant import TenantResolutionError, get_company_for_request, get_company_from_user_context
from core.jwt_tokens import claim_mfa_verified, issue_mfa_pending_token, issue_token_pair
from core.login_auth import INVALID_LOGIN_COMPANY_MESSAGE, INVALID_LOGIN_MESSAGE, resolve_login_username
from core.login_lockout import clear_failures, is_locked, record_failure
from core.mfa_service import has_mfa_enabled, mfa_required_for
from core.spa_session_bridge import clear_django_session, establish_django_session
from core.serializers import UserSerializer

User = get_user_model()


def _user_permissions(user) -> dict:
    return {
        "is_rm_admin": bool(getattr(user, "is_rm_admin", False)),
        "is_company_admin": bool(getattr(user, "is_company_admin", False)),
        "role": getattr(user, "role", ""),
    }


def _login_response_payload(user, *, mfa_verified: bool, needs_mfa: bool = False) -> dict:
    tokens = issue_token_pair(user, mfa_verified=mfa_verified)
    mfa_req = mfa_required_for(user)
    return {
        **tokens,
        "user": UserSerializer(user, context={}).data,
        "mfa_required": mfa_req,
        "mfa_verified": mfa_verified if mfa_req else True,
        "needs_mfa": needs_mfa,
        "must_change_password": bool(getattr(user, "must_change_password", False)),
    }


class LoginAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        username_input = (request.data.get("username") or request.data.get("email") or "").strip()
        password = (request.data.get("password") or "").strip()
        company_slug = (request.data.get("company_slug") or "").strip() or None

        if not username_input or not password:
            return Response({"detail": "Informe usuário e senha."}, status=status.HTTP_400_BAD_REQUEST)

        locked, retry = is_locked(request, username_input)
        if locked:
            return Response(
                {"detail": f"Muitas tentativas. Aguarde {retry // 60 + 1} minuto(s)."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        username = resolve_login_username(username_input)
        user = authenticate(request, username=username, password=password)

        if user is None or not user.is_active:
            record_failure(request, username_input)
            msg = INVALID_LOGIN_COMPANY_MESSAGE if company_slug else INVALID_LOGIN_MESSAGE
            return Response({"detail": msg}, status=status.HTTP_401_UNAUTHORIZED)

        if company_slug:
            if not user.company or user.company.slug != company_slug:
                record_failure(request, username_input)
                return Response({"detail": INVALID_LOGIN_COMPANY_MESSAGE}, status=status.HTTP_401_UNAUTHORIZED)
        elif not (user.is_rm_admin or user.is_superuser):
            record_failure(request, username_input)
            return Response(
                {"detail": "Use o login da sua empresa ou credenciais de operador RM."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        clear_failures(request, username_input)

        if getattr(user, "must_change_password", False):
            establish_django_session(request, user)
            return Response(
                _login_response_payload(user, mfa_verified=False, needs_mfa=False)
                | {"must_change_password": True},
            )

        needs_mfa = mfa_required_for(user) and has_mfa_enabled(user)
        needs_mfa_setup = mfa_required_for(user) and not has_mfa_enabled(user)

        if needs_mfa:
            payload = _login_response_payload(user, mfa_verified=False, needs_mfa=True)
            payload["mfa_pending_token"] = issue_mfa_pending_token(user)
            return Response(payload)

        if needs_mfa_setup:
            establish_django_session(request, user)
            return Response(
                _login_response_payload(user, mfa_verified=False, needs_mfa=False)
                | {"needs_mfa_setup": True},
            )

        establish_django_session(request, user)
        return Response(_login_response_payload(user, mfa_verified=True, needs_mfa=False))


class LogoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh = (request.data.get("refresh") or "").strip()
        if refresh:
            try:
                RefreshToken(refresh).blacklist()
            except TokenError:
                pass
        clear_django_session(request)
        return Response({"detail": "Logout realizado."}, status=status.HTTP_200_OK)


class MeAPIView(APIView):
    permission_classes = [IsAuthenticated, RequireMfaVerified]

    def get(self, request):
        from core.modules import get_company_modules

        user = request.user
        company = user.company
        modules = get_company_modules(company, user) if company else []
        data = UserSerializer(user, context={"request": request}).data
        data["permissions"] = _user_permissions(user)
        data["modules"] = modules
        if company:
            data["company"] = {
                "id": company.id,
                "name": company.name,
                "slug": company.slug,
                "plan_code": company.plan_code,
                "enabled_modules": company.enabled_modules(),
            }
        data["mfa_required"] = mfa_required_for(user)
        token_mfa = claim_mfa_verified(getattr(request, "auth", None))
        data["mfa_verified"] = token_mfa if data["mfa_required"] else True
        establish_django_session(request, user)
        return Response(data)


class ChangePasswordAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        new_password = (request.data.get("new_password") or "").strip()
        confirm = (request.data.get("confirm_password") or "").strip()

        if not new_password or not confirm:
            return Response({"detail": "Preencha a nova senha e a confirmação."}, status=status.HTTP_400_BAD_REQUEST)
        if new_password != confirm:
            return Response({"detail": "As senhas não coincidem."}, status=status.HTTP_400_BAD_REQUEST)
        if len(new_password) < 8:
            return Response({"detail": "A senha deve ter no mínimo 8 caracteres."}, status=status.HTTP_400_BAD_REQUEST)
        if request.user.check_password(new_password):
            return Response(
                {"detail": "A nova senha deve ser diferente da senha provisória."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        user.set_password(new_password)
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password"])

        from django.contrib.auth import update_session_auth_hash

        update_session_auth_hash(request, user)

        needs_mfa = mfa_required_for(user) and has_mfa_enabled(user)
        if needs_mfa:
            payload = _login_response_payload(user, mfa_verified=False, needs_mfa=True)
            payload["mfa_pending_token"] = issue_mfa_pending_token(user)
            payload["must_change_password"] = False
            return Response(payload)

        return Response(_login_response_payload(user, mfa_verified=True, needs_mfa=False))


def _company_context_payload(company, user):
    from core.modules import get_company_modules
    from core.quotas import get_usage_summary

    return {
        "id": company.id,
        "name": company.name,
        "slug": company.slug,
        "plan_code": company.plan_code,
        "enabled_modules": company.enabled_modules(),
        "modules": get_company_modules(company, user),
        "quotas": get_usage_summary(company),
    }


class CompaniesMeAPIView(APIView):
    """GET /api/v1/companies/me/ — tenant do contexto (JWT + X-Company-Slug)."""

    permission_classes = [IsAuthenticated, RequireMfaVerified]

    def get(self, request):
        company = get_company_from_user_context(request)
        if not company:
            if request.user.is_rm_admin:
                return Response(
                    {
                        "detail": "Operador RM sem tenant. Informe X-Company-Slug ou acesse via slug.",
                        "mode": "rm_operator",
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )
            return Response({"detail": "Sem empresa associada."}, status=status.HTTP_404_NOT_FOUND)
        return Response(_company_context_payload(company, request.user))


class CompanyMeAPIView(APIView):
    """GET /api/v1/companies/{slug}/ — contexto explícito por slug."""

    permission_classes = [IsAuthenticated, RequireMfaVerified]

    def get(self, request, slug):
        try:
            company = get_company_for_request(request, slug)
        except TenantResolutionError:
            return Response({"detail": "Conflito de tenant."}, status=status.HTTP_400_BAD_REQUEST)

        establish_django_session(request, request.user)
        return Response(_company_context_payload(company, request.user))
