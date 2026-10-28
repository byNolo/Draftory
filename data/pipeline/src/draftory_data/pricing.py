"""Provisional currency policies over reviewed, already-smoothed M7A values."""

from fractions import Fraction

from .source import DataError

POLICIES = ("linear", "elite", "confidence-discount", "tier-cap")
POLICY_ID = "m8c2-elite-1-30-smoothed-v1"
DEFAULT_BUDGET = 65  # Provisional playtest choice after the documented budget experiment.


def round_half_up(value: Fraction) -> int:
    value += Fraction(1, 2)
    return value.numerator // value.denominator


def tier_boundaries(values: dict[str, Fraction]) -> dict[str, Fraction]:
    if not values:
        raise DataError("Nonempty reviewed values required")
    ordered = sorted(values.values())
    return {
        "middle": ordered[(len(ordered) - 1) // 4],
        "aboveAverage": ordered[3 * (len(ordered) - 1) // 4],
        "elite": ordered[95 * (len(ordered) - 1) // 100],
    }


def value_tier(value: Fraction, boundaries: dict[str, Fraction]) -> str:
    for name in ("elite", "aboveAverage", "middle"):
        if value >= boundaries[name]:
            return name
    return "low"


def price(
    value: Fraction,
    low: Fraction,
    high: Fraction,
    pa: int,
    policy: str,
    elite_boundary: Fraction,
) -> int:
    if policy not in POLICIES or type(pa) is not int or pa < 50 or high < low:
        raise DataError("Unsupported pricing policy, value range or historical PA")
    if not low <= value <= high or not low <= elite_boundary <= high:
        raise DataError("Value outside the reviewed pool")
    z = (value - low) / (high - low) if high > low else Fraction(1, 2)
    base = 1 + (19 * z if policy == "linear" else 29 * z * z)
    if policy == "confidence-discount":
        # Currency discount only: at most 15%, tapering to zero at 200 PA.
        base *= 1 - Fraction(3, 20) * Fraction(max(0, 200 - pa), 150)
    if policy == "tier-cap" and pa < 200:
        boundary_z = (elite_boundary - low) / (high - low) if high > low else Fraction(1, 2)
        base = min(base, 1 + 29 * boundary_z * boundary_z)
    return max(1, round_half_up(base))


def prices(values: dict[str, Fraction], players: list[dict], policy: str) -> dict[str, int]:
    boundaries = tier_boundaries(values)
    low, high = min(values.values()), max(values.values())
    return {
        p["id"]: price(values[p["id"]], low, high, p["pa"], policy, boundaries["elite"])
        for p in players
    }
