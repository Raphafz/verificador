"""Testes de planos e enforcement de quotas."""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from core.models import Company, CTOMapFile
from core.quotas import QuotaExceeded, check_quota, enforce_quota, get_usage

User = get_user_model()


@override_settings(QUOTA_ENFORCEMENT_ENABLED=True)
class QuotaEnforcementTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name="ISP Quota",
            slug="isp-quota",
            cnpj="11.222.333/0001-81",
            email="quota@isp.local",
            plan_code="P",
            module_verificador=True,
            quota_enforcement=True,
        )
        self.admin = User.objects.create_user(
            username="admin_quota",
            password="pass12345!",
            role="COMPANY_ADMIN",
            company=self.company,
            is_active=True,
            must_change_password=False,
        )

    def test_plan_p_limits(self):
        check = check_quota(self.company, "users")
        self.assertEqual(check.limit, 3)
        self.assertTrue(check.allowed)

    def test_blocks_extra_user(self):
        User.objects.create_user(
            username="u2",
            password="x",
            company=self.company,
            is_active=True,
            must_change_password=False,
        )
        User.objects.create_user(
            username="u3",
            password="x",
            company=self.company,
            is_active=True,
            must_change_password=False,
        )
        with self.assertRaises(QuotaExceeded):
            enforce_quota(self.company, "users", user=self.admin)

    def test_blocks_extra_map(self):
        for i in range(15):
            CTOMapFile.objects.create(
                company=self.company,
                uploaded_by=self.admin,
                description=f"mapa {i}",
            )
        with self.assertRaises(QuotaExceeded):
            enforce_quota(self.company, "maps", user=self.admin)

    def test_rm_bypasses_enforcement(self):
        rm = User.objects.create_user(
            username="rm1",
            password="x",
            role="RM",
            is_active=True,
            is_staff=True,
            must_change_password=False,
        )
        for i in range(15):
            CTOMapFile.objects.create(
                company=self.company,
                uploaded_by=self.admin,
                description=f"mapa {i}",
            )
        check = enforce_quota(self.company, "maps", user=rm)
        self.assertFalse(check.allowed)

    def test_usage_counts_active_users_only(self):
        User.objects.create_user(
            username="inactive",
            password="x",
            company=self.company,
            is_active=False,
            must_change_password=False,
        )
        usage = get_usage(self.company)
        self.assertEqual(usage["users"], 1)
