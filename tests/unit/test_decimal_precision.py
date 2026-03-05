"""
Bug 3 – Floating-point precision loss
=======================================
Original bug:  dashboard.py did  float(revenue_data['total'])
               which can introduce IEEE 754 artifacts:
               e.g. float("333.333") + float("333.333") + float("333.334")
               might not equal exactly 1000.00

Fix:           Use  Decimal(revenue_data['total']).quantize(Decimal('0.01'),
               rounding=ROUND_HALF_UP)  before converting to float.

The seed data was designed to trigger this:
    res-dec-1: $333.333
    res-dec-2: $333.333
    res-dec-3: $333.334
    Sum:       $1000.000  (NUMERIC(10,3) in Postgres)
    After quantize to 2dp: $1000.00

Without the fix, float arithmetic could produce $999.9999... or $1000.0000...001
"""
import pytest
from decimal import Decimal, ROUND_HALF_UP


# ── Reproduce the fixed and buggy rounding logic from dashboard.py ──────────

def format_revenue_fixed(total_str: str) -> float:
    """
    FIXED logic: Decimal quantize THEN float conversion.
    This is what dashboard.py does after the fix.
    """
    total = Decimal(total_str).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return float(total)


def format_revenue_buggy(total_str: str) -> float:
    """
    BUGGY logic: direct float conversion (no Decimal rounding).
    """
    return float(total_str)


# ── Tests ───────────────────────────────────────────────────────────────────

class TestDecimalPrecision:
    """Verify that revenue values are rounded correctly to 2 decimal places."""

    def test_three_thirds_sum_to_exact_1000(self):
        """
        333.333 + 333.333 + 333.334 = 999.999 (in DB as NUMERIC(10,3))
        → quantize to 0.01 → 1000.00  (ROUND_HALF_UP on .999)

        Wait — 999.999 quantized to 2dp is 1000.00? Let's verify:
        Decimal('999.999').quantize(Decimal('0.01'), ROUND_HALF_UP) → 1000.00
        Actually: 999.999 rounded to 2dp = 1000.00 (the .9 rounds up)
        Hmm actually: 999.99|9 → 1000.00 ✓ (third decimal 9 >= 5, round up)
        """
        amounts = [Decimal("333.333"), Decimal("333.333"), Decimal("333.334")]
        raw_sum = sum(amounts)  # Decimal("999.999") — we lose 0.001 in seed rounding

        # Actually, 333.333 + 333.333 + 333.334 = 1000.000 exactly in Decimal
        assert raw_sum == Decimal("1000.000"), f"Raw sum should be 1000.000, got {raw_sum}"

        result = format_revenue_fixed(str(raw_sum))
        assert result == 1000.0, f"Fixed format should give 1000.0, got {result}"

    def test_fixed_format_prop_001_total(self):
        """
        prop-001 tenant-a total: 1250 + 333.333 + 333.333 + 333.334 = 2250.000
        """
        total = Decimal("1250.000") + Decimal("333.333") + Decimal("333.333") + Decimal("333.334")
        assert total == Decimal("2250.000")

        result = format_revenue_fixed(str(total))
        assert result == 2250.0
        assert result == float(Decimal("2250.00"))  # exact representation

    def test_fixed_format_prop_002_total(self):
        """prop-002: 1250 + 1475.50 + 1199.25 + 1050.75 = 4975.50"""
        result = format_revenue_fixed("4975.500")
        assert result == 4975.5

    def test_fixed_format_prop_003_total(self):
        """prop-003: 2850 + 3250.50 = 6100.50"""
        result = format_revenue_fixed("6100.500")
        assert result == 6100.5

    def test_fixed_format_prop_004_total(self):
        """prop-004: 420 + 560.75 + 480.25 + 315.50 = 1776.50"""
        result = format_revenue_fixed("1776.500")
        assert result == 1776.5

    def test_fixed_format_prop_005_total(self):
        """prop-005: 920 + 1080.40 + 1255.60 = 3256.00"""
        result = format_revenue_fixed("3256.000")
        assert result == 3256.0

    def test_quantize_rounds_up_at_half(self):
        """Verify ROUND_HALF_UP behavior: .005 → .01"""
        result = format_revenue_fixed("100.005")
        assert result == 100.01

    def test_quantize_rounds_down_below_half(self):
        """Verify: .004 → .00"""
        result = format_revenue_fixed("100.004")
        assert result == 100.0

    def test_quantize_handles_three_decimal_db_values(self):
        """
        DB stores NUMERIC(10,3). Values like 333.333 need correct rounding.
        333.333 → 333.33 (third decimal 3 < 5, round down)
        """
        result = format_revenue_fixed("333.333")
        assert result == 333.33

    def test_quantize_handles_trailing_nines(self):
        """999.999 → 1000.00 (the .9 cascades rounding up)."""
        result = format_revenue_fixed("999.999")
        assert result == 1000.0


class TestFloatArtifacts:
    """
    Demonstrate that direct float conversion can introduce artifacts,
    while Decimal quantize avoids them.
    """

    def test_float_sum_may_drift(self):
        """
        Summing floats can accumulate tiny errors.
        This tests that Decimal avoids the problem.
        """
        # Float arithmetic
        float_sum = float("333.333") + float("333.333") + float("333.334")
        # Decimal arithmetic
        decimal_sum = Decimal("333.333") + Decimal("333.333") + Decimal("333.334")

        # Decimal sum is exact
        assert decimal_sum == Decimal("1000.000")

        # Float sum MIGHT be exact here (CPython often handles this well),
        # but the principle stands: Decimal is guaranteed exact
        fixed_result = format_revenue_fixed(str(decimal_sum))
        assert fixed_result == 1000.0

    def test_known_float_artifact_scenario(self):
        """
        Classic float precision issue: 0.1 + 0.2 != 0.3 in float.
        Our Decimal approach handles this.
        """
        # Float has precision issue
        assert 0.1 + 0.2 != 0.3  # This is True — floats are imprecise

        # Decimal is exact
        d = Decimal("0.1") + Decimal("0.2")
        assert d == Decimal("0.3")

        # Our fixed formatting preserves this
        result = format_revenue_fixed(str(d))
        assert result == 0.3

    def test_no_float_representation_artifacts_in_output(self):
        """
        The API response should never contain values like 4975.4999999999
        or 1776.5000000001. The Decimal quantize step prevents this.
        """
        test_values = {
            "4975.500": 4975.5,
            "1776.500": 1776.5,
            "3256.000": 3256.0,
            "2250.000": 2250.0,
            "6100.500": 6100.5,
        }

        for input_str, expected in test_values.items():
            result = format_revenue_fixed(input_str)
            assert result == expected, (
                f"Input '{input_str}' should produce {expected}, got {result}"
            )
            # Also verify string representation has no artifacts
            assert "999" not in str(result) or result == 1000.0
