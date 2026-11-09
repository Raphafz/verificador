"""Testes — API REST multi-tenant (RBAC + object-level)."""
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient, APITestCase

from core.models import Company, CTOMapFile
from core.test_helpers import api_force_login

User = get_user_model()


class ApiTenantScopeTest(APITestCase):
    def setUp(self):
        self.company_a = Company.objects.create(
            name="Empresa A",
            slug="empresa-a",
            cnpj="12.345.678/0001-90",
            email="a@test.local",
            plan_code="M",
        )
        self.company_b = Company.objects.create(
            name="Empresa B",
            slug="empresa-b",
            cnpj="98.765.432/0001-10",
            email="b@test.local",
            plan_code="M",
        )
        self.admin_a = User.objects.create_user(
            username="admin_a",
            password="pass12345!",
            role="COMPANY_ADMIN",
            company=self.company_a,
        )
        self.admin_b = User.objects.create_user(
            username="admin_b",
            password="pass12345!",
            role="COMPANY_ADMIN",
            company=self.company_b,
        )
        self.user_a = User.objects.create_user(
            username="user_a",
            password="pass12345!",
            role="COMPANY_USER",
            company=self.company_a,
        )
        self.client = APIClient()

    def test_company_admin_sees_only_own_company(self):
        api_force_login(self.client, self.admin_a)
        response = self.client.get("/api/v1/companies/")
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in response.data}
        self.assertEqual(ids, {self.company_a.pk})

    def test_company_admin_cannot_retrieve_other_company(self):
        api_force_login(self.client, self.admin_a)
        response = self.client.get(f"/api/v1/companies/{self.company_b.pk}/")
        self.assertEqual(response.status_code, 404)

    def test_cannot_reassign_user_company_via_patch(self):
        api_force_login(self.client, self.admin_a)
        target = User.objects.create_user(
            username="target_a",
            password="pass12345!",
            role="COMPANY_USER",
            company=self.company_a,
        )
        response = self.client.patch(
            f"/api/v1/users/{target.pk}/",
            {"company": self.company_b.pk},
            format="json",
        )
        self.assertIn(response.status_code, (200, 400))
        target.refresh_from_db()
        self.assertEqual(target.company_id, self.company_a.pk)

    def test_maps_scoped_to_tenant(self):
        map_a = CTOMapFile.objects.create(
            company=self.company_a,
            uploaded_by=self.admin_a,
            description="mapa A",
        )
        CTOMapFile.objects.create(
            company=self.company_b,
            uploaded_by=self.admin_b,
            description="mapa B",
        )
        api_force_login(self.client, self.admin_a)
        response = self.client.get("/api/v1/maps/")
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in response.data}
        self.assertEqual(ids, {map_a.pk})

    def test_company_user_can_list_maps_readonly(self):
        CTOMapFile.objects.create(
            company=self.company_a,
            uploaded_by=self.admin_a,
            description="mapa A",
        )
        api_force_login(self.client, self.user_a)
        response = self.client.get("/api/v1/maps/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_company_user_cannot_create_user(self):
        api_force_login(self.client, self.user_a)
        response = self.client.post(
            "/api/v1/users/",
            {
                "username": "hacker",
                "password": "pass12345!",
                "email": "h@x.com",
                "role": "COMPANY_USER",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_company_user_cannot_list_users(self):
        api_force_login(self.client, self.user_a)
        response = self.client.get("/api/v1/users/")
        self.assertEqual(response.status_code, 403)

    def test_company_admin_create_user_forces_company_user_role(self):
        api_force_login(self.client, self.admin_a)
        response = self.client.post(
            "/api/v1/users/",
            {
                "username": "new_api_user",
                "password": "pass12345!",
                "email": "new@a.local",
                "role": "COMPANY_ADMIN",
            },
            format="json",
        )
        self.assertIn(response.status_code, (201, 400))
        if response.status_code == 201:
            created = User.objects.get(username="new_api_user")
            self.assertEqual(created.role, "COMPANY_USER")
            self.assertEqual(created.company_id, self.company_a.pk)
