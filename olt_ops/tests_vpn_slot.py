"""Testes — slots VPN e mutex host."""
from django.core.cache import cache
from django.test import TestCase, override_settings

from olt_ops.vpn_slot import (
    HOST_VPN_LOCK_KEY,
    OltSlotBusyError,
    SLOT_KEY_PREFIX,
    acquire_container_slot,
    acquire_host_vpn_lock,
    release_container_slot,
    release_host_vpn_lock,
)


@override_settings(CACHES={
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "olt-vpn-slot-tests",
    }
})
class VpnSlotTest(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_host_vpn_mutex_exclusive(self):
        acquire_host_vpn_lock(1)
        with self.assertRaises(OltSlotBusyError):
            acquire_host_vpn_lock(2, wait_timeout=0.5)
        release_host_vpn_lock(1)
        acquire_host_vpn_lock(2, wait_timeout=1)

    def test_container_slots_parallel_limit(self):
        acquire_container_slot(10, 2, wait_timeout=1)
        acquire_container_slot(20, 2, wait_timeout=1)
        with self.assertRaises(OltSlotBusyError):
            acquire_container_slot(30, 2, wait_timeout=0.5)
        release_container_slot(10, 0)
        idx = acquire_container_slot(30, 2, wait_timeout=1)
        self.assertIn(idx, (0, 1))

    def test_release_only_own_slot(self):
        acquire_container_slot(99, 1, wait_timeout=1)
        release_container_slot(100, 0)
        self.assertEqual(cache.get(f"{SLOT_KEY_PREFIX}0"), "99")
        release_container_slot(99, 0)
