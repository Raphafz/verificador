"""Testes de token de sessão, revogação e validação de IP."""
from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory, TestCase, override_settings

from core.models import UserSessionRecord
from core.session_security import (
    issue_access_token,
    on_login_success,
    register_session,
    revoke_all_sessions,
    validate_active_session,
    _token_digest,
)

User = get_user_model()


def _request_with_session():
    factory = RequestFactory()
    request = factory.get("/")
    request.session = SessionStore()
    request.session.create()
    request.META["REMOTE_ADDR"] = "10.0.0.1"
    request.META["HTTP_USER_AGENT"] = "TestAgent/1.0"
    return request


@override_settings(
    SESSION_REVOKE_ON_NEW_LOGIN=True,
    SESSION_BIND_IP=True,
    SESSION_COOKIE_AGE=3600,
)
class SessionSecurityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="sessuser",
            email="sess@example.com",
            password="SecurePass123!",
        )

    def test_login_revokes_previous_sessions(self):
        old = SessionStore()
        old.create()
        UserSessionRecord.objects.create(
            user=self.user,
            session_key=old.session_key,
            access_token_digest="old",
            ip_address="10.0.0.2",
            is_current=True,
        )

        request = _request_with_session()
        on_login_success(request, self.user)

        self.assertFalse(
            UserSessionRecord.objects.filter(
                session_key=old.session_key,
                revoked_at__isnull=True,
            ).exists()
        )
        self.assertTrue(
            UserSessionRecord.objects.filter(
                user=self.user,
                session_key=request.session.session_key,
                revoked_at__isnull=True,
            ).exists()
        )

    def test_validate_rejects_revoked_session(self):
        request = _request_with_session()
        token, digest, expires = issue_access_token()
        register_session(request, self.user, access_token=token, expires_at=expires)
        request.session["_access_token"] = token
        request.session["_session_ip"] = "10.0.0.1"
        request.session["_session_expires_at"] = expires.isoformat()

        invalid, reason = validate_active_session(request, self.user)
        self.assertFalse(invalid)

        rec = UserSessionRecord.objects.get(session_key=request.session.session_key)
        rec.revoked_at = rec.last_seen_at
        rec.save(update_fields=["revoked_at"])

        invalid, reason = validate_active_session(request, self.user)
        self.assertTrue(invalid)
        self.assertEqual(reason, "replaced")

    def test_validate_rejects_ip_change_when_bound(self):
        request = _request_with_session()
        on_login_success(request, self.user)

        request.META["REMOTE_ADDR"] = "10.0.0.99"
        invalid, reason = validate_active_session(request, self.user)
        self.assertTrue(invalid)
        self.assertEqual(reason, "ip_changed")

    def test_token_digest_mismatch_invalid(self):
        request = _request_with_session()
        token, _, expires = issue_access_token()
        register_session(request, self.user, access_token=token, expires_at=expires)
        request.session["_access_token"] = "wrong-token"
        request.session["_session_ip"] = "10.0.0.1"
        request.session["_session_expires_at"] = expires.isoformat()

        invalid, reason = validate_active_session(request, self.user)
        self.assertTrue(invalid)
        self.assertEqual(reason, "invalid")

    def test_revoke_all_except_current(self):
        request = _request_with_session()
        on_login_success(request, self.user)
        other = SessionStore()
        other.create()
        UserSessionRecord.objects.create(
            user=self.user,
            session_key=other.session_key,
            access_token_digest=_token_digest("x"),
            is_current=False,
        )
        n = revoke_all_sessions(self.user, except_session_key=request.session.session_key)
        self.assertEqual(n, 1)
