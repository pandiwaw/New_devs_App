"""
Shared fixtures and seed data for unit tests.

These tests verify the three bug fixes at the function/logic level,
without requiring Docker, a running database, or any external services.

Run with:  pytest tests/unit/ -v
       or: python -m pytest tests/unit/ -v
"""
try:
    import pytest
    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False

from decimal import Decimal


# ── Seed data (mirrors database/seed.sql exactly) ──────────────────────────

PROPERTIES = {
    ("prop-001", "tenant-a"): {"name": "Beach House Alpha", "timezone": "Europe/Paris"},
    ("prop-001", "tenant-b"): {"name": "Mountain Lodge Beta", "timezone": "America/New_York"},
    ("prop-002", "tenant-a"): {"name": "City Apartment Downtown", "timezone": "Europe/Paris"},
    ("prop-003", "tenant-a"): {"name": "Country Villa Estate", "timezone": "Europe/Paris"},
    ("prop-004", "tenant-b"): {"name": "Lakeside Cottage", "timezone": "America/New_York"},
    ("prop-005", "tenant-b"): {"name": "Urban Loft Modern", "timezone": "America/New_York"},
}

# Every reservation from seed.sql, keyed by (property_id, tenant_id)
# Format: (id, check_in_utc, check_out_utc, total_amount)
RESERVATIONS = {
    ("prop-001", "tenant-a"): [
        # THE critical timezone edge case: Feb 29 23:30 UTC = Mar 1 00:30 Paris
        ("res-tz-1",  "2024-02-29 23:30:00+00", "2024-03-05 10:00:00+00", Decimal("1250.000")),
        ("res-dec-1", "2024-03-15 10:00:00+00", "2024-03-18 10:00:00+00", Decimal("333.333")),
        ("res-dec-2", "2024-03-16 10:00:00+00", "2024-03-19 10:00:00+00", Decimal("333.333")),
        ("res-dec-3", "2024-03-17 10:00:00+00", "2024-03-20 10:00:00+00", Decimal("333.334")),
    ],
    ("prop-002", "tenant-a"): [
        ("res-004", "2024-03-05 14:00:00+00", "2024-03-08 11:00:00+00", Decimal("1250.00")),
        ("res-005", "2024-03-12 16:00:00+00", "2024-03-15 10:00:00+00", Decimal("1475.50")),
        ("res-006", "2024-03-20 15:00:00+00", "2024-03-23 12:00:00+00", Decimal("1199.25")),
        ("res-007", "2024-03-25 18:00:00+00", "2024-03-28 14:00:00+00", Decimal("1050.75")),
    ],
    ("prop-003", "tenant-a"): [
        ("res-008", "2024-03-02 15:00:00+00", "2024-03-09 12:00:00+00", Decimal("2850.00")),
        ("res-009", "2024-03-18 16:00:00+00", "2024-03-25 11:00:00+00", Decimal("3250.50")),
    ],
    ("prop-004", "tenant-b"): [
        ("res-010", "2024-03-08 18:00:00+00", "2024-03-11 15:00:00+00", Decimal("420.00")),
        ("res-011", "2024-03-14 17:00:00+00", "2024-03-18 14:00:00+00", Decimal("560.75")),
        ("res-012", "2024-03-22 16:00:00+00", "2024-03-26 13:00:00+00", Decimal("480.25")),
        ("res-013", "2024-03-28 19:00:00+00", "2024-03-31 15:00:00+00", Decimal("315.50")),
    ],
    ("prop-005", "tenant-b"): [
        ("res-014", "2024-03-06 19:00:00+00", "2024-03-10 16:00:00+00", Decimal("920.00")),
        ("res-015", "2024-03-15 18:00:00+00", "2024-03-19 17:00:00+00", Decimal("1080.40")),
        ("res-016", "2024-03-24 20:00:00+00", "2024-03-29 14:00:00+00", Decimal("1255.60")),
    ],
    # tenant-b owns prop-001 but has ZERO reservations for it
    ("prop-001", "tenant-b"): [],
}


if HAS_PYTEST:
    @pytest.fixture
    def seed_properties():
        return PROPERTIES

    @pytest.fixture
    def seed_reservations():
        return RESERVATIONS
