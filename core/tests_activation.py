"""
Testes do fluxo de ativação de conta (link único, sem senha por e-mail).
"""
import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.account_activation import (
    ACTIVATION_EXPIRY_MINUTES,
    _digest,
    consume_activation_token,
    create_activation_token,
    get_user_for_activation_token,
)
from core.models import AccountActivationToken, Company
from core.utils import send_account_activation_email
from core.views import rm_user_send_email

User = get_user_model()


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    ACCOUNT_ACTIVATION_EXPIRY_MINUTES=30,
    MFA_REQUIRED=False,
)
class AccountActivationTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name="Empresa Teste",
            cnpj="12.345.678/0001-99",
            email="empresa@test.com",
        )
        self.user = User.objects.create(
            username="novo_user",
            email="novo@test.com",
        )
        self.user.set_unusable_password()
        self.user.company = self.company
        self.user.role = "COMPANY_USER"
        self.user.must_change_password = False
        self.user.save()

    def test_create_token_stores_digest_not_plaintext(self):
        raw = create_activation_token(self.user)
        self.assertGreater(len(raw), 32)
        record = AccountActivationToken.objects.get(user=self.user, used_at__isnull=True)
        self.assertEqual(record.token_digest, _digest(raw))
        self.assertNotEqual(record.token_digest, raw)
        self.assertTrue(record.django_token)

    def test_token_single_use(self):
        raw = create_activation_token(self.user)
        user, _ = get_user_for_activation_token(raw)
        self.assertEqual(user.pk, self.user.pk)

        consumed = consume_activation_token(raw)
        self.assertEqual(consumed.pk, self.user.pk)

        user2, _ = get_user_for_activation_token(raw)
        self.assertIsNone(user2)

    def test_token_expires(self):
        raw = create_activation_token(self.user)
        record = AccountActivationToken.objects.get(token_digest=_digest(raw))
        record.expires_at = timezone.now() - timedelta(minutes=1)
        record.save(update_fields=["expires_at"])

        user, _ = get_user_for_activation_token(raw)
        self.assertIsNone(user)

    def test_activation_email_has_no_password(self):
        send_account_activation_email(self.user)
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].alternatives[0][0] if mail.outbox[0].alternatives else mail.outbox[0].body
        self.assertIn("ativar-conta/", body)
        self.assertNotIn("Senha:", body)
        self.assertNotIn("password-highlight", body)

    def test_activation_view_sets_password_and_logs_in(self):
        raw = create_activation_token(self.user)
        client = Client()
        url = reverse("account_activate", kwargs={"token": raw})

        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Defina sua senha")

        response = client.post(
            url,
            {"password1": "NovaSenhaSegura1!", "password2": "NovaSenhaSegura1!"},
        )
        self.assertEqual(response.status_code, 302)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NovaSenhaSegura1!"))
        self.assertFalse(self.user.must_change_password)

        record = AccountActivationToken.objects.get(token_digest=_digest(raw))
        self.assertIsNotNone(record.used_at)

    def test_new_token_invalidates_previous(self):
        first = create_activation_token(self.user)
        second = create_activation_token(self.user)
        user, _ = get_user_for_activation_token(first)
        self.assertIsNone(user)
        user2, _ = get_user_for_activation_token(second)
        self.assertEqual(user2.pk, self.user.pk)

    def test_rm_admin_can_resend_activation_email(self):
        rm_admin = User.objects.create_user(
            username="rm_admin_test",
            email="admin-rm@test.com",
            password="AdminSegura1!",
        )
        rm_admin.role = "RM"
        rm_admin.must_change_password = False
        rm_admin.save()

        request = RequestFactory().post(
            reverse("rm:user_send_email", kwargs={"user_id": self.user.pk}),
            {"template": "activation"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        request.user = rm_admin

        response = rm_user_send_email(request, user_id=self.user.pk)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data["success"])
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.user.email, mail.outbox[0].to)

    def test_rm_resend_activation_requires_email(self):
        rm_admin = User.objects.create_user(
            username="rm_admin_test2",
            email="admin-rm2@test.com",
            password="AdminSegura1!",
        )
        rm_admin.role = "RM"
        rm_admin.must_change_password = False
        rm_admin.save()

        no_email_user = User.objects.create(username="sem_email", email="")
        no_email_user.company = self.company
        no_email_user.role = "COMPANY_USER"
        no_email_user.save()

        request = RequestFactory().post(
            reverse("rm:user_send_email", kwargs={"user_id": no_email_user.pk}),
            {"template": "activation"},
        )
        request.user = rm_admin

        response = rm_user_send_email(request, user_id=no_email_user.pk)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(json.loads(response.content)["success"])
