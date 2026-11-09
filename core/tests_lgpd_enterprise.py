"""Testes PASSO 3 — LGPD enterprise."""
import json
import os
from io import BytesIO
import zipfile

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.lgpd_anonymization import anonymize_user_account, irreversible_subject_hash
from core.lgpd_constants import LEGAL_DOCUMENT_VERSION, REQUIRED_CONSENT_TYPES
from core.lgpd_export import build_user_data_payload, sign_export_token, unsign_export_token
from core.models import ConsentRecord, DataSubjectRequest, LgpdExportDownload

User = get_user_model()


class LgpdEnterpriseTests(TestCase):
    def _user_with_consent(self):
        from core.test_helpers import make_company

        company = make_company()
        user = User.objects.create_user(
            username="lgpduser",
            email="lgpd@example.com",
            password="TestPass123!@#x",
            company=company,
            role="COMPANY_USER",
            must_change_password=False,
        )
        for doc in REQUIRED_CONSENT_TYPES:
            ConsentRecord.objects.get_or_create(
                user=user,
                document_type=doc,
                document_version=LEGAL_DOCUMENT_VERSION,
            )
        return user

    def test_irreversible_hash_stable(self):
        h1 = irreversible_subject_hash(42)
        h2 = irreversible_subject_hash(42)
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)

    def test_export_zip_signed_download(self):
        user = self._user_with_consent()
        client = Client()
        client.force_login(user)
        r = client.get("/meus-dados/exportar/?format=zip")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("download_url", data)
        artifact = LgpdExportDownload.objects.get(user=user)
        token = sign_export_token(artifact.pk, user.pk)
        self.assertIsNotNone(unsign_export_token(token))
        r2 = client.get(data["download_url"])
        self.assertEqual(r2.status_code, 200)
        self.assertIn("zip", r2["Content-Type"])

    def test_export_payload_has_sections(self):
        user = self._user_with_consent()
        payload = build_user_data_payload(user)
        self.assertIn("consents", payload)
        self.assertIn("data_subject_requests", payload)

    def test_anonymize_user(self):
        user = User.objects.create_user(
            username="todelete",
            email="del@example.com",
            password="TestPass123!@#x",
        )
        user.is_active = False
        user.save()
        h = anonymize_user_account(user)
        user.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertIn("deleted_", user.username)
        self.assertNotIn("del@example.com", user.email)
        self.assertTrue(len(h) >= 32)

    @override_settings(DSR_MAX_RETRIES=2)
    def test_process_dsr_command(self):
        user = User.objects.create_user(
            username="dsruser",
            email="dsr@example.com",
            password="TestPass123!@#x",
        )
        user.is_active = False
        user.save()
        req = DataSubjectRequest.objects.create(
            user=user,
            request_type="delete",
            status="pending",
        )
        from django.core.management import call_command

        call_command("process_data_subject_requests", request_id=req.pk)
        req.refresh_from_db()
        self.assertEqual(req.status, "completed")
        user.refresh_from_db()
        self.assertIn("deleted_", user.username)
