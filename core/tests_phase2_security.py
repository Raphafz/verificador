"""Testes Fase 2 — hardening LGPD e segurança."""
import os
import time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.bridge_security import build_bridge_signature, validate_bridge_request
from core.cnpj_utils import format_cnpj, hash_cnpj, mask_cnpj_display
from core.field_encryption import decrypt_value, encrypt_value, is_encrypted
from core.models import Company
from core.utils import generate_random_password

User = get_user_model()


class CnpjSecurityTests(TestCase):
    def test_hash_deterministic(self):
        h1 = hash_cnpj("12.345.678/0001-99")
        h2 = hash_cnpj("12345678000199")
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)

    def test_mask_hides_digits(self):
        masked = mask_cnpj_display("12.345.678/0001-99")
        self.assertNotIn("1234", masked)
        self.assertTrue(masked.endswith("99") or "99" in masked)

    def test_company_save_encrypts_cnpj(self):
        company = Company.objects.create(
            name="Test Co",
            slug="test-co-sec",
            cnpj="11.222.333/0001-81",
            email="test@example.com",
        )
        company.refresh_from_db()
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT cnpj FROM core_company WHERE id = %s", [company.pk])
            raw = cursor.fetchone()[0]
        self.assertTrue(is_encrypted(raw))
        self.assertEqual(company.cnpj, format_cnpj("11222333000181"))
        self.assertEqual(company.cnpj_hash, hash_cnpj("11222333000181"))


class BridgeSecurityTests(TestCase):
    @override_settings(
        ALLOWED_HOSTS=["testserver"],
    )
    @patch.dict(os.environ, {
        "ALERT_BRIDGE_API_TOKEN": "test-token-xyz",
        "BRIDGE_HMAC_SECRET": "hmac-secret-xyz",
        "ALERT_BRIDGE_ALLOWED_IPS": "127.0.0.1",
    })
    def test_validate_bridge_ok(self):
        from django.test import RequestFactory
        rf = RequestFactory()
        token = "test-token-xyz"
        ts = str(int(time.time()))
        nonce = "a" * 24
        sig = build_bridge_signature(ts, nonce, token)
        request = rf.get(
            "/api/internal/alert-bridge/configs/",
            HTTP_X_BRIDGE_TOKEN=token,
            HTTP_X_BRIDGE_TIMESTAMP=ts,
            HTTP_X_BRIDGE_NONCE=nonce,
            HTTP_X_BRIDGE_SIGNATURE=sig,
            REMOTE_ADDR="127.0.0.1",
        )
        self.assertIsNone(validate_bridge_request(request))

    @patch.dict(os.environ, {
        "ALERT_BRIDGE_API_TOKEN": "test-token-xyz",
        "BRIDGE_HMAC_SECRET": "hmac-secret-xyz",
        "ALERT_BRIDGE_ALLOWED_IPS": "127.0.0.1",
    })
    def test_validate_bridge_rejects_replay(self):
        from django.test import RequestFactory
        from django.core.cache import cache
        cache.clear()
        rf = RequestFactory()
        token = "test-token-xyz"
        ts = str(int(time.time()))
        nonce = "b" * 24
        sig = build_bridge_signature(ts, nonce, token)
        kwargs = dict(
            HTTP_X_BRIDGE_TOKEN=token,
            HTTP_X_BRIDGE_TIMESTAMP=ts,
            HTTP_X_BRIDGE_NONCE=nonce,
            HTTP_X_BRIDGE_SIGNATURE=sig,
            REMOTE_ADDR="127.0.0.1",
        )
        r1 = rf.get("/api/internal/alert-bridge/configs/", **kwargs)
        self.assertIsNone(validate_bridge_request(r1))
        r2 = rf.get("/api/internal/alert-bridge/configs/", **kwargs)
        err = validate_bridge_request(r2)
        self.assertIsNotNone(err)
        self.assertEqual(err.status_code, 403)


class PasswordEntropyTests(TestCase):
    def test_minimum_length_14(self):
        pwd = generate_random_password()
        self.assertGreaterEqual(len(pwd), 14)


class CspNonceTests(TestCase):
    @override_settings(CSP_STRICT=True)
    def test_csp_nonce_on_response(self):
        client = Client()
        response = client.get("/rm/login/")
        self.assertIn("Content-Security-Policy", response)
        policy = response["Content-Security-Policy"]
        self.assertIn("nonce-", policy)
        self.assertIn("strict-dynamic", policy)
        self.assertIn("script-src-elem", policy)
