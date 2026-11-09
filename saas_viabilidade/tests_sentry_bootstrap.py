"""Testes — bootstrap Sentry."""
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from saas_viabilidade.sentry_bootstrap import init_sentry


class SentryBootstrapTest(SimpleTestCase):
    @override_settings(DEBUG=True)
    @patch.dict("os.environ", {"SENTRY_DSN": ""}, clear=False)
    def test_init_skips_without_dsn(self):
        self.assertFalse(init_sentry(debug=True, environment="test"))

    @override_settings(DEBUG=True)
    @patch("sentry_sdk.init")
    @patch.dict(
        "os.environ",
        {"SENTRY_DSN": "https://key@o0.ingest.sentry.io/1", "SENTRY_TRACES_SAMPLE_RATE": "0"},
        clear=False,
    )
    def test_init_uses_lgpd_safe_defaults(self, mock_init):
        with patch("sentry_sdk.integrations.django.DjangoIntegration"), patch(
            "sentry_sdk.integrations.logging.LoggingIntegration"
        ):
            result = init_sentry(debug=True, environment="development")
        self.assertTrue(result)
        kwargs = mock_init.call_args.kwargs
        self.assertFalse(kwargs["send_default_pii"])
        self.assertEqual(kwargs["environment"], "development")
