"""Testes Etapa 4 — API hardening (paths, erros JSON, webhook)."""
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.json_responses import MSG_SERVER_ERROR, json_error
from core.test_helpers import make_company

User = get_user_model()


class JsonResponsesTest(TestCase):
    @override_settings(DEBUG=False)
    def test_json_error_hides_exception_in_production(self):
        response = json_error("detalhe interno", status=500, exc=RuntimeError("segredo"))
        data = json.loads(response.content)
        self.assertEqual(data["erro"], MSG_SERVER_ERROR)
        self.assertNotIn("segredo", response.content.decode())

    @override_settings(DEBUG=True)
    def test_json_error_shows_exception_in_debug(self):
        response = json_error("fallback", status=500, exc=RuntimeError("detalhe-debug"))
        data = json.loads(response.content)
        self.assertIn("detalhe-debug", data["erro"])


@override_settings(
    ASAAS_WEBHOOK_TOKEN="test-webhook-secret",
    DEBUG=False,
)
class AsaasWebhookSecurityTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse("asaas_webhook")
        self.payload = {"event": "PAYMENT_RECEIVED", "payment": {"customer": "cus_x"}}

    def test_rejects_token_in_query_string(self):
        response = self.client.post(
            f"{self.url}?token=test-webhook-secret",
            data=json.dumps(self.payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_accepts_token_in_header(self):
        response = self.client.post(
            self.url,
            data=json.dumps(self.payload),
            content_type="application/json",
            HTTP_ASAAS_ACCESS_TOKEN="test-webhook-secret",
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data.get("ok"))
        self.assertNotIn("company", data)

    @override_settings(ASAAS_WEBHOOK_TOKEN="")
    def test_unconfigured_webhook_returns_503(self):
        response = self.client.post(
            self.url,
            data=json.dumps(self.payload),
            content_type="application/json",
            HTTP_ASAAS_ACCESS_TOKEN="any",
        )
        self.assertEqual(response.status_code, 503)


@override_settings(DEBUG=False, MFA_REQUIRED=False)
class FtthApiArquivosSecurityTest(TestCase):
    def setUp(self):
        self.company = make_company(name="FTTH Co", slug="ftth-co", email="ftth@test.local")
        self.user = User.objects.create_user(
            username="ftth_user",
            password="pass12345!",
            role="COMPANY_USER",
            company=self.company,
            must_change_password=False,
        )
        self.client = Client()
        self.client.force_login(self.user)
        session = self.client.session
        session["mfa_verified_at"] = timezone.now().isoformat()
        session.save()

    @patch("ftth_viewer.views.CTOMapFile")
    @patch("ftth_viewer.views.cache")
    def test_api_arquivos_response_has_no_caminho_field(self, mock_cache, mock_model):
        from unittest.mock import MagicMock

        mock_cache.get.return_value = None
        mapa = MagicMock()
        mapa.file_name = "mapa.kml"
        mapa.file_type = "kml"
        mapa.id = 7
        mapa.file = MagicMock()
        mapa.file.path = "/secret/media/mapas/mapa.kml"
        mock_model.objects.filter.return_value.select_related.return_value.order_by.return_value = [
            mapa
        ]
        from django.test import RequestFactory

        from ftth_viewer.views import api_arquivos

        request = RequestFactory().get("/verificador/api/arquivos")
        request.user = self.user
        response = api_arquivos(request)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(len(data), 1)
        self.assertNotIn("caminho", data[0])
        self.assertEqual(data[0]["id"], 7)


@override_settings(HEALTH_SECURITY_ALLOWED_IPS=("10.0.0.1",))
class HealthSecurityRestrictionTest(TestCase):
    def test_health_security_forbidden_for_unknown_ip(self):
        response = Client().get("/health/security/")
        self.assertEqual(response.status_code, 403)

    @override_settings(HEALTH_SECURITY_ALLOWED_IPS=())
    def test_health_security_open_when_allowlist_empty(self):
        response = Client().get("/health/security/")
        self.assertEqual(response.status_code, 200)
