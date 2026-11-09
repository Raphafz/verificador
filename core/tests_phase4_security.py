"""Testes PASSO 4 — segurança enterprise."""
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import Client, RequestFactory, TestCase, override_settings

from core.mfa_lockout import clear_mfa_failures, is_mfa_locked, record_mfa_failure
from core.middleware_http_methods import HttpMethodRestrictionMiddleware
from core.security_headers import build_content_security_policy

User = get_user_model()


class CspStrictTests(TestCase):
    @override_settings(CSP_STRICT=True)
    def test_csp_strict_no_unsafe_inline_script(self):
        class Req:
            csp_nonce = "abc123"

            def get_host(self):
                return "testserver"

            def is_secure(self):
                return False
        policy = build_content_security_policy(Req())
        self.assertIn("strict-dynamic", policy)
        self.assertIn("'nonce-abc123'", policy)
        self.assertNotIn("'unsafe-inline'", policy.split("script-src")[1].split(";")[0])

    @override_settings(CSP_STRICT=True)
    def test_img_src_without_https_wildcard(self):
        class Req:
            csp_nonce = "abc123"

            def get_host(self):
                return "testserver"

            def is_secure(self):
                return False

        policy = build_content_security_policy(Req())
        img_part = policy.split("img-src")[1].split(";")[0]
        img_sources = img_part.strip().split()
        self.assertNotIn("https:", img_sources)
        self.assertIn("tile.openstreetmap.org", img_part)

    @override_settings(CSP_STRICT=True)
    def test_strict_uses_unsafe_hashes_for_style_attr(self):
        class Req:
            csp_nonce = "n1"

            def get_host(self):
                return "testserver"

            def is_secure(self):
                return False

        policy = build_content_security_policy(Req())
        self.assertIn("style-src-attr 'unsafe-hashes'", policy)

    @override_settings(CSP_STRICT=True)
    def test_ftth_viewer_allows_inline_style_attr_for_leaflet(self):
        class Req:
            csp_nonce = "n1"
            path = "/fibramar/verificador/"

            def get_host(self):
                return "testserver"

            def is_secure(self):
                return False

        policy = build_content_security_policy(Req())
        self.assertIn("style-src-attr 'unsafe-inline' 'unsafe-hashes'", policy)


class CrlfProtectionTests(TestCase):
    def test_crlf_in_path_rejected(self):
        client = Client()
        response = client.get("/rm/login/%0d%0aInjected:1")
        self.assertEqual(response.status_code, 400)


class SecurityHeadersMiddlewareTests(TestCase):
    def test_trace_method_blocked(self):
        factory = RequestFactory()
        request = factory.generic("TRACE", "/")
        middleware = HttpMethodRestrictionMiddleware(lambda req: HttpResponse("ok"))
        response = middleware(request)
        self.assertEqual(response.status_code, 405)

    @override_settings(HIDE_SERVER_HEADER=True)
    def test_server_header_removed(self):
        client = Client()
        response = client.get("/rm/login/")
        self.assertNotIn("Server", response)

    @override_settings(CSP_STRICT=True)
    def test_coep_header_present_on_http(self):
        client = Client()
        response = client.get("/rm/login/")
        self.assertEqual(
            response.get("Cross-Origin-Embedder-Policy"), "credentialless"
        )


class MfaLockoutTests(TestCase):
    @override_settings(DEBUG=False)
    def test_mfa_lockout_after_failures(self):
        user = User.objects.create_user(username="mfa1", email="a@b.com", password="x" * 14)
        ip = "127.0.0.1"
        clear_mfa_failures(user.pk, ip)
        for _ in range(6):
            record_mfa_failure(user.pk, ip)
        locked, _ = is_mfa_locked(user.pk, ip)
        self.assertTrue(locked)


class SessionSecurityTests(TestCase):
    def test_concurrent_session_model(self):
        from core.models import UserSessionRecord

        user = User.objects.create_user(username="sess1", email="s@b.com", password="x" * 14)
        UserSessionRecord.objects.create(user=user, session_key="abc123", is_current=True)
        self.assertEqual(user.session_records.count(), 1)
