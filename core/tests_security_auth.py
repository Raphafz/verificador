"""Testes Etapa 2 — autenticação, redirect seguro, IP e MFA na API."""
import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from core.request_ip import get_client_ip
from core.safe_redirect import is_safe_redirect_url
from core.test_helpers import api_force_login, make_company

User = get_user_model()


class SafeRedirectTests(SimpleTestCase):
    def test_blocks_external_url(self):
        rf = RequestFactory()
        request = rf.get("/rm/login/")
        request.META["HTTP_HOST"] = "testserver"
        self.assertFalse(is_safe_redirect_url(request, "https://evil.example/phish"))

    def test_blocks_protocol_relative(self):
        rf = RequestFactory()
        request = rf.get("/rm/login/")
        request.META["HTTP_HOST"] = "testserver"
        self.assertFalse(is_safe_redirect_url(request, "//evil.example/"))

    @override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
    def test_allows_same_host_path(self):
        rf = RequestFactory()
        request = rf.get("/rm/login/")
        request.META["HTTP_HOST"] = "testserver"
        self.assertTrue(is_safe_redirect_url(request, "/dashboard/"))


class ClientIpTests(SimpleTestCase):
    def test_ignores_spoofed_xff_without_trusted_proxy(self):
        rf = RequestFactory()
        request = rf.get("/", REMOTE_ADDR="203.0.113.50")
        request.META["HTTP_X_FORWARDED_FOR"] = "1.2.3.4"
        self.assertEqual(get_client_ip(request), "203.0.113.50")

    def test_uses_xff_when_remote_is_trusted_proxy(self):
        rf = RequestFactory()
        request = rf.get("/", REMOTE_ADDR="127.0.0.1")
        request.META["HTTP_X_FORWARDED_FOR"] = "198.51.100.10, 127.0.0.1"
        self.assertEqual(get_client_ip(request), "198.51.100.10")


class LoginUsernameResolveTests(TestCase):
    def test_resolve_email_without_exception_for_unknown(self):
        from core.login_auth import resolve_login_username

        User.objects.create_user(
            username="known",
            email="known@test.local",
            password="TestPass123!@#xxxx",
        )
        self.assertEqual(resolve_login_username("known@test.local"), "known")
        self.assertEqual(resolve_login_username("unknown@test.local"), "unknown@test.local")


@override_settings(MFA_REQUIRED=True, MFA_REQUIRED_COMPANY_ADMINS=False)
class ApiMfaPermissionTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.rm = User.objects.create_user(
            username="rm_mfa_test",
            email="rm_mfa@test.local",
            password="TestPass123!@#xxxx",
            role="RM",
            is_staff=True,
        )
        self.client = APIClient()

    def test_api_denied_without_mfa_session(self):
        self.client.force_authenticate(user=self.rm)
        response = self.client.get("/api/v1/companies/")
        self.assertEqual(response.status_code, 403)

    def test_api_allowed_with_mfa_session_flag(self):
        api_force_login(self.client, self.rm)
        response = self.client.get("/api/v1/companies/")
        self.assertEqual(response.status_code, 200)
