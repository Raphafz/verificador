"""Testes Etapa 3 — autorização multi-tenant e API."""
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient, APITestCase

from core.models import Company
from core.test_helpers import api_force_login, make_company

User = get_user_model()


class ApiAuthorizationEtapa3Test(APITestCase):
    def setUp(self):
        self.company = make_company(name="Auth Co", slug="auth-co", email="a@auth.local")
        self.admin = User.objects.create_user(
            username="admin_auth",
            password="pass12345!",
            role="COMPANY_ADMIN",
            company=self.company,
        )
        self.user = User.objects.create_user(
            username="user_auth",
            password="pass12345!",
            role="COMPANY_USER",
            company=self.company,
        )
        self.rm = User.objects.create_user(
            username="rm_auth",
            password="pass12345!",
            role="RM",
            is_staff=True,
        )
        self.client = APIClient()

    def test_company_user_cannot_list_users(self):
        api_force_login(self.client, self.user)
        response = self.client.get("/api/v1/users/")
        self.assertEqual(response.status_code, 403)

    def test_company_user_cannot_list_companies(self):
        api_force_login(self.client, self.user)
        response = self.client.get("/api/v1/companies/")
        self.assertEqual(response.status_code, 403)

    def test_company_admin_cannot_promote_user_to_admin_via_api(self):
        target = User.objects.create_user(
            username="target_promote",
            password="pass12345!",
            role="COMPANY_USER",
            company=self.company,
        )
        api_force_login(self.client, self.admin)
        response = self.client.patch(
            f"/api/v1/users/{target.pk}/",
            {"role": "COMPANY_ADMIN"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        target.refresh_from_db()
        self.assertEqual(target.role, "COMPANY_USER")

    def test_swagger_docs_require_rm(self):
        api_force_login(self.client, self.admin)
        response = self.client.get("/api/v1/docs/")
        self.assertEqual(response.status_code, 403)
        api_force_login(self.client, self.rm)
        response = self.client.get("/api/v1/docs/")
        self.assertIn(response.status_code, (200, 302))

    def test_geocoding_clear_forbidden_for_company_admin(self):
        from django.test import Client

        client = Client()
        client.force_login(self.admin)
        response = client.post("/auth-co/verificador/api/cache/geocoding/clear")
        self.assertEqual(response.status_code, 403)
