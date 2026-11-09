"""Testes Fase 3 — logging, API, auditoria, retenção."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

from core.audit_trail import record_security_event
from core.models import SecurityAuditEvent
from core.test_helpers import make_company
from core.upload_security import secure_upload_filename

User = get_user_model()


class Phase3SecurityTests(TestCase):
    def test_secure_filename_random(self):
        a = secure_upload_filename("mapa.csv")
        b = secure_upload_filename("mapa.csv")
        self.assertNotEqual(a, b)
        self.assertTrue(a.endswith(".csv"))

    def test_audit_trail_persists(self):
        user = User.objects.create_user(
            username="audituser",
            email="a@b.com",
            password="TestPass123!@#x",
        )
        record_security_event("test_event", user=user, details={"email": "secret@test.com"})
        self.assertEqual(SecurityAuditEvent.objects.filter(event_type="test_event").count(), 1)
        ev = SecurityAuditEvent.objects.get(event_type="test_event")
        self.assertNotIn("secret@test.com", str(ev.details))

    @override_settings(MFA_REQUIRED=False)
    def test_health_security_endpoint(self):
        r = Client().get("/health/security/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("csp_strict", r.json())

    def test_lgpd_export_csv(self):
        company = make_company()
        user = User.objects.create_user(
            username="exportuser",
            email="e@u.com",
            password="TestPass123!@#x",
            company=company,
            role="COMPANY_USER",
            must_change_password=False,
        )
        client = Client()
        client.force_login(user)
        from core.models import ConsentRecord
        from core.lgpd_constants import LEGAL_DOCUMENT_VERSION, REQUIRED_CONSENT_TYPES
        for doc in REQUIRED_CONSENT_TYPES:
            ConsentRecord.objects.get_or_create(
                user=user,
                document_type=doc,
                document_version=LEGAL_DOCUMENT_VERSION,
            )
        r = client.get("/meus-dados/exportar/?format=csv")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r["Content-Type"])
