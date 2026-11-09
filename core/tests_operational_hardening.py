"""Testes PASSO 2 — sanitização OLT e bridge."""
import os
import time
from unittest.mock import patch

from django.test import RequestFactory, TestCase, override_settings

from core.bridge_security import build_bridge_signature, validate_bridge_request
from core.operational_sanitizer import mask_host_for_log, sanitize_operational_text
from olt_ops.operational_log import append_to_job_log, sanitize_chunk


class OperationalSanitizerTests(TestCase):
    def test_masks_password_kv(self):
        raw = "password: MinhaSenha123\nenable secret mysecret"
        out = sanitize_operational_text(raw)
        self.assertNotIn("MinhaSenha123", out)
        self.assertNotIn("mysecret", out)
        self.assertIn("[REDACTED]", out)

    def test_masks_private_ip(self):
        out = sanitize_operational_text("conectado 192.168.1.50 porta 22")
        self.assertIn("192.168.*.*", out)
        self.assertNotIn("192.168.1.50", out)

    def test_redacts_unknown_short_command(self):
        out = sanitize_operational_text(">>> zxr10secret\n")
        self.assertIn("[REDACTED]", out)
        self.assertNotIn("zxr10secret", out)

    def test_keeps_display_commands(self):
        out = sanitize_operational_text(">>> display ont info 0 1 14 all")
        self.assertIn("display ont info", out)

    def test_mask_host_private(self):
        self.assertIn("*", mask_host_for_log("10.20.30.40"))

    def test_truncates_job_log(self):
        with self.settings(OLT_LOG_MAX_CHARS=100):
            big = "x" * 200
            result = append_to_job_log("", big, classify=False)
            self.assertLessEqual(len(result), 100)
            self.assertIn("truncado", result)

    def test_sanitize_chunk_empty(self):
        self.assertEqual(sanitize_chunk(""), "")


class BridgeHmacPolicyTests(TestCase):
    @override_settings(IS_PRODUCTION=True)
    @patch.dict(os.environ, {
        "ALERT_BRIDGE_API_TOKEN": "token-abc",
        "BRIDGE_HMAC_SECRET": "",
        "ALERT_BRIDGE_ALLOWED_IPS": "127.0.0.1",
    }, clear=False)
    def test_production_requires_hmac_secret(self):
        rf = RequestFactory()
        request = rf.get("/api/internal/alert-bridge/configs/", REMOTE_ADDR="127.0.0.1")
        err = validate_bridge_request(request)
        self.assertIsNotNone(err)
        self.assertEqual(err.status_code, 503)

    @override_settings(IS_PRODUCTION=True)
    @patch.dict(os.environ, {
        "ALERT_BRIDGE_API_TOKEN": "same-value",
        "BRIDGE_HMAC_SECRET": "same-value",
        "ALERT_BRIDGE_ALLOWED_IPS": "127.0.0.1",
    }, clear=False)
    def test_production_rejects_hmac_equal_token(self):
        rf = RequestFactory()
        request = rf.get("/api/internal/alert-bridge/configs/", REMOTE_ADDR="127.0.0.1")
        err = validate_bridge_request(request)
        self.assertIsNotNone(err)
        self.assertEqual(err.status_code, 503)
