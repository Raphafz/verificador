"""Throttling DRF — rate limit por usuário e IP."""
from rest_framework.throttling import SimpleRateThrottle


class BurstUserThrottle(SimpleRateThrottle):
    scope = "burst"

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return f"throttle_burst_u_{request.user.pk}"
        return self.get_ident(request)


class SustainedUserThrottle(SimpleRateThrottle):
    scope = "sustained"

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return f"throttle_sustained_u_{request.user.pk}"
        return self.get_ident(request)


class AnonBurstThrottle(SimpleRateThrottle):
    scope = "anon_burst"

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return None
        return self.get_ident(request)
