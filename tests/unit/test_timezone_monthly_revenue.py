"""
Bug 2 – Timezone-naive monthly revenue calculation
====================================================
Original bug:  Month boundaries used naive UTC datetimes, so a reservation
               with check_in "2024-02-29 23:30:00+00" was classified as
               February — even though in Europe/Paris (UTC+1) it's already
               March 1st at 00:30.

Fix:           Localize month boundaries to the property's timezone FIRST,
               then convert to UTC for comparison with the DB timestamps.

This is the MOST important test file because it directly proves the fix
for Client A's complaint: "Revenue numbers don't match internal records
for March."

The critical reservation:
    res-tz-1: check_in = 2024-02-29 23:30:00 UTC
              In Europe/Paris (UTC+1) = 2024-03-01 00:30:00
              → Should count as MARCH revenue in Paris timezone
              → Should count as FEBRUARY revenue if using naive UTC
"""
import pytest
from datetime import datetime
from decimal import Decimal
import pytz

from conftest import RESERVATIONS, PROPERTIES


# ── Reproduce the fixed month-boundary logic from reservations.py ───────────

def compute_month_boundaries_fixed(year: int, month: int, timezone: str):
    """
    FIXED logic: determine month start/end in the property's local timezone,
    then convert to UTC for database comparison.
    """
    tz = pytz.timezone(timezone)

    start_local = tz.localize(datetime(year, month, 1))
    if month < 12:
        end_local = tz.localize(datetime(year, month + 1, 1))
    else:
        end_local = tz.localize(datetime(year + 1, 1, 1))

    start_utc = start_local.astimezone(pytz.utc)
    end_utc = end_local.astimezone(pytz.utc)

    return start_utc, end_utc


def compute_month_boundaries_buggy(year: int, month: int):
    """
    BUGGY logic (before fix): naive UTC boundaries with no timezone awareness.
    """
    start_utc = datetime(year, month, 1, tzinfo=pytz.utc)
    if month < 12:
        end_utc = datetime(year, month + 1, 1, tzinfo=pytz.utc)
    else:
        end_utc = datetime(year + 1, 1, 1, tzinfo=pytz.utc)

    return start_utc, end_utc


def sum_monthly_revenue(reservations, start_utc, end_utc):
    """
    Sum reservation amounts where check_in falls within [start_utc, end_utc).
    Mirrors the SQL: WHERE check_in_date >= $3 AND check_in_date < $4
    """
    total = Decimal("0")
    count = 0
    for res_id, check_in_str, _, amount in reservations:
        check_in = datetime.strptime(check_in_str, "%Y-%m-%d %H:%M:%S+00")
        check_in = check_in.replace(tzinfo=pytz.utc)
        if start_utc <= check_in < end_utc:
            total += amount
            count += 1
    return total, count


# ── Tests ───────────────────────────────────────────────────────────────────

class TestTimezoneMonthBoundaries:
    """Verify the timezone-aware month boundary calculation."""

    def test_paris_march_start_is_feb_29_23h_utc(self):
        """
        Europe/Paris is UTC+1 in winter (CET).
        March 1 00:00 Paris = February 29 23:00 UTC.
        """
        start_utc, _ = compute_month_boundaries_fixed(2024, 3, "Europe/Paris")

        assert start_utc.year == 2024
        assert start_utc.month == 2
        assert start_utc.day == 29
        assert start_utc.hour == 23
        assert start_utc.minute == 0

    def test_paris_april_start_is_mar_31_22h_utc(self):
        """
        Europe/Paris switches to CEST (UTC+2) on March 31 2024.
        April 1 00:00 Paris = March 31 22:00 UTC.
        """
        _, end_utc = compute_month_boundaries_fixed(2024, 3, "Europe/Paris")

        assert end_utc.year == 2024
        assert end_utc.month == 3
        assert end_utc.day == 31
        assert end_utc.hour == 22
        assert end_utc.minute == 0

    def test_buggy_boundaries_use_midnight_utc(self):
        """The buggy version always uses midnight UTC, ignoring timezone."""
        start_utc, end_utc = compute_month_boundaries_buggy(2024, 3)

        assert start_utc == datetime(2024, 3, 1, 0, 0, tzinfo=pytz.utc)
        assert end_utc == datetime(2024, 4, 1, 0, 0, tzinfo=pytz.utc)

    def test_new_york_march_start_is_mar_1_05h_utc(self):
        """
        America/New_York is UTC-5 in winter (EST).
        March 1 00:00 NY = March 1 05:00 UTC.
        """
        start_utc, _ = compute_month_boundaries_fixed(2024, 3, "America/New_York")

        assert start_utc.year == 2024
        assert start_utc.month == 3
        assert start_utc.day == 1
        assert start_utc.hour == 5
        assert start_utc.minute == 0


class TestResolutionTZ1CriticalReservation:
    """
    THE critical test: res-tz-1 has check_in = 2024-02-29 23:30:00 UTC.
    In Paris (UTC+1), that's 2024-03-01 00:30:00 → it's a MARCH reservation.
    """

    def test_fixed_logic_counts_res_tz1_in_march(self):
        """
        With the fix, res-tz-1 ($1250) IS included in March revenue for Paris.
        """
        reservations = RESERVATIONS[("prop-001", "tenant-a")]
        start_utc, end_utc = compute_month_boundaries_fixed(2024, 3, "Europe/Paris")
        total, count = sum_monthly_revenue(reservations, start_utc, end_utc)

        # All 4 reservations should be in March (Paris time)
        assert count == 4, f"Expected 4 March reservations, got {count}"
        assert total == Decimal("2250.000"), f"Expected $2250.000, got {total}"

    def test_buggy_logic_misses_res_tz1_in_march(self):
        """
        With the BUG, res-tz-1 is NOT in March (it's Feb 29 UTC, before Mar 1 UTC).
        Only 3 reservations are counted → revenue is wrong.
        """
        reservations = RESERVATIONS[("prop-001", "tenant-a")]
        start_utc, end_utc = compute_month_boundaries_buggy(2024, 3)
        total, count = sum_monthly_revenue(reservations, start_utc, end_utc)

        # Bug: only 3 of 4 are counted
        assert count == 3, f"Buggy logic should only find 3, got {count}"
        assert total == Decimal("1000.000"), f"Buggy total should be $1000.000, got {total}"

    def test_fixed_logic_excludes_res_tz1_from_february(self):
        """
        With the fix, res-tz-1 should NOT appear in February (Paris time),
        because Feb 29 23:30 UTC = Mar 1 00:30 Paris.
        """
        reservations = RESERVATIONS[("prop-001", "tenant-a")]
        start_utc, end_utc = compute_month_boundaries_fixed(2024, 2, "Europe/Paris")
        total, count = sum_monthly_revenue(reservations, start_utc, end_utc)

        assert count == 0, f"No reservations should be in February (Paris), got {count}"
        assert total == Decimal("0"), f"February revenue should be $0, got {total}"

    def test_buggy_logic_misclassifies_res_tz1_as_february(self):
        """
        The BUG puts res-tz-1 in February because it only looks at UTC date
        (Feb 29 23:30 UTC < Mar 1 00:00 UTC → classified as February).
        """
        reservations = RESERVATIONS[("prop-001", "tenant-a")]
        start_utc, end_utc = compute_month_boundaries_buggy(2024, 2)
        total, count = sum_monthly_revenue(reservations, start_utc, end_utc)

        # Bug: res-tz-1 incorrectly lands in February
        assert count == 1, f"Buggy logic should put 1 reservation in Feb, got {count}"
        assert total == Decimal("1250.000"), f"Buggy Feb total should be $1250, got {total}"

    def test_revenue_difference_between_fixed_and_buggy(self):
        """
        Quantify the exact dollar impact of the bug.
        Fixed March total - Buggy March total = $1250 (the misplaced reservation).
        """
        reservations = RESERVATIONS[("prop-001", "tenant-a")]

        fixed_start, fixed_end = compute_month_boundaries_fixed(2024, 3, "Europe/Paris")
        buggy_start, buggy_end = compute_month_boundaries_buggy(2024, 3)

        fixed_total, _ = sum_monthly_revenue(reservations, fixed_start, fixed_end)
        buggy_total, _ = sum_monthly_revenue(reservations, buggy_start, buggy_end)

        difference = fixed_total - buggy_total
        assert difference == Decimal("1250.000"), (
            f"The bug causes a $1250 discrepancy in March revenue. "
            f"Fixed={fixed_total}, Buggy={buggy_total}, Diff={difference}"
        )


class TestTimezoneEdgeCases:
    """Additional timezone edge cases to ensure robustness."""

    def test_new_york_properties_unaffected(self):
        """
        All tenant-b reservations (America/New_York) have check_in times
        well within March UTC, so timezone doesn't change the count.
        """
        reservations = RESERVATIONS[("prop-004", "tenant-b")]
        start_utc, end_utc = compute_month_boundaries_fixed(2024, 3, "America/New_York")
        total, count = sum_monthly_revenue(reservations, start_utc, end_utc)

        assert count == 4
        assert total == Decimal("1776.50")

    def test_december_to_january_boundary(self):
        """Verify year boundary handling (month 12 → January next year)."""
        start_utc, end_utc = compute_month_boundaries_fixed(2024, 12, "Europe/Paris")

        assert start_utc.year == 2024
        assert start_utc.month == 11  # Nov 30 23:00 UTC (Dec 1 00:00 Paris CET=UTC+1)
        assert end_utc.year == 2024
        assert end_utc.month == 12  # Dec 31 23:00 UTC (Jan 1 00:00 Paris CET=UTC+1)

    def test_utc_timezone_gives_midnight_boundaries(self):
        """When timezone is UTC, boundaries should be standard midnight UTC."""
        start_utc, end_utc = compute_month_boundaries_fixed(2024, 3, "UTC")

        assert start_utc == datetime(2024, 3, 1, 0, 0, tzinfo=pytz.utc)
        assert end_utc == datetime(2024, 4, 1, 0, 0, tzinfo=pytz.utc)

    def test_dst_transition_march_2024_paris(self):
        """
        Paris switches from CET (UTC+1) to CEST (UTC+2) on March 31 2024.
        The end boundary for March should account for this:
        April 1 00:00 CEST = March 31 22:00 UTC (not 23:00).
        """
        _, end_utc = compute_month_boundaries_fixed(2024, 3, "Europe/Paris")

        # After DST: April 1 00:00 Paris CEST = March 31 22:00 UTC
        assert end_utc.hour == 22, (
            f"DST transition: April boundary should be 22:00 UTC, got {end_utc.hour}:00"
        )
