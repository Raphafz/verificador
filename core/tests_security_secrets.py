"""Testes Etapa 1 — segredos, bootstrap e criptografia de campos."""
import os
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.test import SimpleTestCase, override_settings

from core.field_encryption import (
    FieldEncryptionNotConfiguredError,
    decrypt_value,
    encrypt_value,
    is_encrypted,
)
from saas_viabilidade.security_bootstrap import (
    SecurityBootstrapError,
    resolve_field_encryption_key,
    validate_field_encryption_key_strength,
    validate_secret_key_strength,
)


class SecretKeyValidationTests(SimpleTestCase):
    def test_rejects_insecure_known_key(self):
        issues = validate_secret_key_strength("dev-secret-key-change-me")
        self.assertTrue(issues)

    def test_accepts_strong_key(self):
        key = "x" * 50 + "abcdefghijklmnopqrstuvwxyz"
        issues = validate_secret_key_strength(key)
        self.assertEqual(issues, [])


class FieldEncryptionKeyValidationTests(SimpleTestCase):
    def test_rejects_empty_key(self):
        self.assertIn("ausente", validate_field_encryption_key_strength("")[0])

    def test_accepts_valid_fernet_key(self):
        key = Fernet.generate_key().decode()
        self.assertEqual(validate_field_encryption_key_strength(key), [])


class FieldEncryptionBehaviorTests(SimpleTestCase):
    @override_settings(SECRET_KEY="test-secret-key-with-enough-entropy-for-django-12345")
    @patch.dict(os.environ, {"FIELD_ENCRYPTION_KEY": Fernet.generate_key().decode()}, clear=False)
    def test_roundtrip_with_env_key(self):
        enc = encrypt_value("segredo-olt")
        self.assertTrue(is_encrypted(enc))
        self.assertEqual(decrypt_value(enc), "segredo-olt")

    @override_settings(
        SECRET_KEY="test-secret-key-with-enough-entropy-for-django-12345",
        DEBUG=True,
        IS_PRODUCTION=False,
    )
    @patch.dict(
        os.environ,
        {
            "FIELD_ENCRYPTION_KEY": "",
            "ALLOW_FIELD_ENCRYPTION_SECRET_FALLBACK": "true",
        },
        clear=False,
    )
    def test_fallback_only_with_explicit_opt_in(self):
        enc = encrypt_value("legado-dev")
        self.assertEqual(decrypt_value(enc), "legado-dev")

    @override_settings(
        SECRET_KEY="test-secret-key-with-enough-entropy-for-django-12345",
        FIELD_ENCRYPTION_KEY="",
    )
    @patch.dict(os.environ, {"FIELD_ENCRYPTION_KEY": ""}, clear=False)
    @patch("core.field_encryption._allow_secret_key_derivation", return_value=False)
    def test_encrypt_fails_without_key_or_opt_in(self, _mock_derivation):
        os.environ.pop("ALLOW_FIELD_ENCRYPTION_SECRET_FALLBACK", None)
        with self.assertRaises(FieldEncryptionNotConfiguredError):
            encrypt_value("x")


class BootstrapFieldEncryptionTests(SimpleTestCase):
    def test_production_requires_valid_key(self):
        key = Fernet.generate_key().decode()
        with patch.dict(
            os.environ,
            {"FIELD_ENCRYPTION_KEY": key},
            clear=False,
        ):
            resolve_field_encryption_key(is_production=True, is_test=False)

    def test_production_rejects_missing_key(self):
        with patch.dict(os.environ, {"FIELD_ENCRYPTION_KEY": ""}, clear=False):
            with self.assertRaises(SecurityBootstrapError):
                resolve_field_encryption_key(is_production=True, is_test=False)

    def test_test_run_allows_missing_key(self):
        resolve_field_encryption_key(is_production=False, is_test=True)

    def test_dev_requires_key_or_opt_in(self):
        env = {
            "FIELD_ENCRYPTION_KEY": "",
            "ALLOW_FIELD_ENCRYPTION_SECRET_FALLBACK": "",
        }
        with patch.dict(os.environ, env, clear=False):
            with self.assertRaises(SecurityBootstrapError):
                resolve_field_encryption_key(is_production=False, is_test=False)
