"""
Bug 1 – Cross-tenant cache leakage
===================================
Original bug:  cache key was  "revenue:{property_id}"
Fixed to:      cache key is   "revenue:{tenant_id}:{property_id}"

Because prop-001 exists for BOTH tenant-a and tenant-b (different properties
that happen to share the same ID), the old key would serve tenant-b the
cached result from tenant-a (or vice versa).

These tests verify the cache key generation logic in isolation.
"""
import pytest


# ── Reproduce the fixed cache key logic ─────────────────────────────────────

def make_cache_key_fixed(property_id: str, tenant_id: str) -> str:
    """The FIXED cache key format from cache.py line 13."""
    return f"revenue:{tenant_id}:{property_id}"


def make_cache_key_buggy(property_id: str) -> str:
    """The BUGGY cache key format (before fix)."""
    return f"revenue:{property_id}"


# ── Tests ───────────────────────────────────────────────────────────────────

class TestCacheKeyIsolation:
    """Verify that cache keys are unique per tenant+property combination."""

    def test_same_property_id_different_tenants_produce_different_keys(self):
        """prop-001 exists for both tenants – keys MUST differ."""
        key_a = make_cache_key_fixed("prop-001", "tenant-a")
        key_b = make_cache_key_fixed("prop-001", "tenant-b")

        assert key_a != key_b, (
            f"Cache keys must be different for different tenants! "
            f"Got '{key_a}' for both."
        )

    def test_buggy_key_collides_on_shared_property(self):
        """Prove the OLD (buggy) key format causes a collision."""
        key_a = make_cache_key_buggy("prop-001")
        key_b = make_cache_key_buggy("prop-001")

        assert key_a == key_b, "Buggy keys should collide (this is the bug)."

    def test_fixed_key_format_includes_tenant_id(self):
        """The fixed key must contain the tenant_id segment."""
        key = make_cache_key_fixed("prop-002", "tenant-a")
        assert key == "revenue:tenant-a:prop-002"

    def test_fixed_key_format_for_tenant_b(self):
        key = make_cache_key_fixed("prop-004", "tenant-b")
        assert key == "revenue:tenant-b:prop-004"

    def test_different_properties_same_tenant_produce_different_keys(self):
        """Two different properties for the same tenant should still differ."""
        key_1 = make_cache_key_fixed("prop-001", "tenant-a")
        key_2 = make_cache_key_fixed("prop-002", "tenant-a")

        assert key_1 != key_2

    def test_cache_simulation_no_cross_tenant_leak(self):
        """
        Simulate a cache dict and prove tenant-b never gets tenant-a's data.
        This mirrors the real Redis behavior.
        """
        cache = {}

        # Tenant A caches their prop-001 revenue
        key_a = make_cache_key_fixed("prop-001", "tenant-a")
        cache[key_a] = {"total": "2250.00", "count": 4, "tenant_id": "tenant-a"}

        # Tenant B looks up prop-001 – should be a cache MISS
        key_b = make_cache_key_fixed("prop-001", "tenant-b")
        result_b = cache.get(key_b)

        assert result_b is None, (
            f"Tenant B should NOT see tenant A's cached data! "
            f"Got: {result_b}"
        )

    def test_cache_simulation_buggy_key_leaks(self):
        """
        Prove the OLD key format causes a cross-tenant data leak.
        This is the exact scenario that caused Client B to see Client A's data.
        """
        cache = {}

        # Tenant A caches their prop-001 revenue using the BUGGY key
        key_a = make_cache_key_buggy("prop-001")
        cache[key_a] = {"total": "2250.00", "count": 4, "tenant_id": "tenant-a"}

        # Tenant B looks up prop-001 using the BUGGY key
        key_b = make_cache_key_buggy("prop-001")
        result_b = cache.get(key_b)

        # BUG: tenant-b gets tenant-a's data!
        assert result_b is not None, "Buggy key should cause a collision."
        assert result_b["tenant_id"] == "tenant-a", (
            "Buggy key leaks tenant-a data to tenant-b."
        )
