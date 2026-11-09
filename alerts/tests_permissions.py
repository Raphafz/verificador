"""Permissões do módulo Alertas — apenas admin da empresa."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from core.lgpd_constants import LEGAL_DOCUMENT_VERSION, REQUIRED_CONSENT_TYPES
from core.models import Company, ConsentRecord

User = get_user_model()


def _grant_legal_consent(user):
    for doc in REQUIRED_CONSENT_TYPES:
        ConsentRecord.objects.get_or_create(
            user=user,
            document_type=doc,
            document_version=LEGAL_DOCUMENT_VERSION,
        )


class AlertsAdminOnlyTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name="ISP Alertas",
            slug="isp-alertas",
            cnpj="12.345.678/0001-90",
            email="alertas@isp.local",
            module_alertas=True,
            module_verificador=True,
        )
        self.admin = User.objects.create_user(
            username="admin_alertas",
            password="pass12345!",
            role="COMPANY_ADMIN",
            company=self.company,
            must_change_password=False,
        )
        self.user = User.objects.create_user(
            username="user_alertas",
            password="pass12345!",
            role="COMPANY_USER",
            company=self.company,
            must_change_password=False,
        )
        _grant_legal_consent(self.admin)
        _grant_legal_consent(self.user)
        self.client = Client()
        self.settings_url = reverse(
            "company:alerts:settings",
            kwargs={"company_slug": self.company.slug},
        )

    def test_company_admin_can_access_settings(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.settings_url)
        self.assertEqual(response.status_code, 200)

    def test_company_user_forbidden(self):
        self.client.force_login(self.user)
        response = self.client.get(self.settings_url)
        self.assertEqual(response.status_code, 403)
