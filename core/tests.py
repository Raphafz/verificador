"""
Testes core — modelos, API REST registrada, segurança básica.
Testes de integração UI legados foram consolidados em tests_phase3_security.
"""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from rest_framework.test import APIClient

from .models import Company
from .test_helpers import api_force_login, make_company

User = get_user_model()


class CompanyModelTest(TestCase):
    def test_company_creation_with_cnpj_hash(self):
        company = make_company()
        self.assertEqual(company.name, "Test Company")
        self.assertTrue(company.cnpj_hash)
        self.assertTrue(company.slug)


class UserModelTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@user.com",
            password="TestPass123!@#x",
            company=self.company,
            role="COMPANY_ADMIN",
        )

    def test_user_creation(self):
        self.assertEqual(self.user.company, self.company)
        self.assertEqual(self.user.role, "COMPANY_ADMIN")


class RestApiTest(TestCase):
    def setUp(self):
        self.company = make_company(name="API Co", email="api@co.com")
        self.rm = User.objects.create_user(
            username="rmapi",
            email="rm@rm.com",
            password="TestPass123!@#x",
            role="RM",
            is_staff=True,
        )
        self.client = APIClient()
        api_force_login(self.client, self.rm)

    def test_api_companies_list(self):
        response = self.client.get("/api/v1/companies/")
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.json()), 1)

    def test_api_company_stats(self):
        response = self.client.get(f"/api/v1/companies/{self.company.id}/stats/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("total_users", data)


class HealthEndpointTest(TestCase):
    def test_health_live(self):
        r = Client().get("/health/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")

    def test_request_id_header(self):
        r = Client().get("/health/")
        self.assertIn("X-Request-ID", r)
