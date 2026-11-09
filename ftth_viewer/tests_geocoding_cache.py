"""Testes — cache de geocoding com hash e minimização LGPD."""
from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from ftth_viewer.geocoding_privacy import (
    anonymize_display_name,
    cache_key_for_query,
    hash_cache_key,
)
from ftth_viewer.models import GeocodingCache
from ftth_viewer.utils import get_cached_geocoding, purge_expired_geocoding_cache, set_cached_geocoding


@override_settings(
    GEOCODING_CACHE_SALT="test-salt-fixed",
    GEOCODING_CACHE_TTL_HOURS=1,
)
class GeocodingCachePrivacyTest(TestCase):
    def test_hash_is_irreversible_and_stable(self):
        h1 = hash_cache_key("Rua das Flores, 100, Rio de Janeiro")
        h2 = hash_cache_key("rua das flores, 100, rio de janeiro")
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)
        self.assertNotIn("flores", h1.lower())

    def test_coord_query_same_hash(self):
        h1, t1 = cache_key_for_query("-22.903500,-43.209600")
        h2, t2 = cache_key_for_query("-22.9035000,-43.2096000")
        self.assertEqual(t1, "reverse")
        self.assertEqual(t2, "reverse")
        self.assertEqual(h1, h2)

    def test_anonymize_strips_street(self):
        full = "Rua X, 123, Bairro Y, Rio de Janeiro, RJ, Brasil"
        hint = anonymize_display_name(full)
        self.assertNotIn("Rua X", hint)
        self.assertIn("Rio de Janeiro", hint)

    def test_set_get_does_not_store_full_address(self):
        query = "Av. Brasil, 500, Rio de Janeiro"
        set_cached_geocoding(
            query,
            {
                "lat": -22.9,
                "lng": -43.2,
                "endereco_completo": "Av. Brasil, 500, Centro, Rio de Janeiro, RJ, Brasil",
            },
        )
        obj = GeocodingCache.objects.get()
        self.assertEqual(len(obj.cache_key_hash), 64)
        self.assertNotEqual(obj.locality_hint, "Av. Brasil, 500, Centro, Rio de Janeiro, RJ, Brasil")
        self.assertFalse(hasattr(obj, "endereco"))
        self.assertFalse(hasattr(obj, "endereco_completo"))

        cached = get_cached_geocoding(query)
        self.assertIsNotNone(cached)
        self.assertEqual(cached["lat"], -22.9)
        self.assertTrue(cached.get("anonymized"))

    def test_ttl_expiry_removes_entry(self):
        set_cached_geocoding("Rua Teste TTL", {"lat": 1.0, "lng": 2.0, "endereco_completo": "Cidade, RJ, Brasil"})
        obj = GeocodingCache.objects.get()
        obj.expires_at = timezone.now() - timedelta(minutes=1)
        obj.save(update_fields=["expires_at"])
        self.assertIsNone(get_cached_geocoding("Rua Teste TTL"))
        self.assertEqual(GeocodingCache.objects.count(), 0)

    def test_purge_expired_command_helper(self):
        set_cached_geocoding("Outra Rua", {"lat": 3.0, "lng": 4.0, "endereco_completo": "Niterói, RJ, Brasil"})
        GeocodingCache.objects.update(expires_at=timezone.now() - timedelta(hours=2))
        removed = purge_expired_geocoding_cache()
        self.assertEqual(removed, 1)
