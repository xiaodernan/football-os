"""Tests for the career-linked development curve (M13 item 4 foundation).

The curve is the pure, deterministic core the integration will call to recompute a player's developed
attributes from the career's appearance rows. These tests pin its contract: deterministic, monotonic in
minutes, saturating and potential-capped, no growth at or above potential, and unchanged at zero minutes.
"""

from __future__ import annotations

from app.models import ALL_ATTRIBUTES
from app.services.simulation.development import (
    ATTRIBUTE_FLOOR,
    developed_attributes,
    development_summary,
)


def _attrs(**overrides: int) -> dict[str, int]:
    base = {attribute: ATTRIBUTE_FLOOR for attribute in ALL_ATTRIBUTES}
    base.update(overrides)
    return base


def test_zero_minutes_leaves_attributes_unchanged() -> None:
    attrs = _attrs(finishing=55, stamina=60)
    assert developed_attributes(0, potential=80, attributes=attrs) == attrs


def test_development_is_deterministic() -> None:
    attrs = _attrs(finishing=55, stamina=60)
    first = developed_attributes(1800, potential=80, attributes=attrs)
    second = developed_attributes(1800, potential=80, attributes=attrs)
    assert first == second


def test_development_increases_with_minutes_and_stops_saturating() -> None:
    attrs = _attrs(finishing=55)
    at_low = developed_attributes(900, potential=80, attributes=attrs)["finishing"]
    at_mid = developed_attributes(3000, potential=80, attributes=attrs)["finishing"]
    at_high = developed_attributes(12000, potential=80, attributes=attrs)["finishing"]
    assert at_low < at_mid < at_high, f"finishing should rise with minutes: {at_low}, {at_mid}, {at_high}"
    # A very large minutes figure does not overshoot potential: the ceiling is never crossed.
    assert at_high <= 80, f"no attribute should pass potential: saw {at_high}"
    # Saturation: doubling minutes from a large base adds little.
    at_very_high = developed_attributes(48000, potential=80, attributes=attrs)["finishing"]
    assert at_very_high - at_high < at_high - at_mid, "growth should slow as it approaches potential"


def test_no_attribute_exceeds_potential() -> None:
    attrs = _attrs(finishing=78, stamina=79)
    developed = developed_attributes(20000, potential=80, attributes=attrs)
    assert all(0 <= value <= 80 for value in developed.values())


def test_no_growth_when_at_or_above_potential() -> None:
    attrs = _attrs(finishing=80, stamina=85)
    developed = developed_attributes(5000, potential=80, attributes=attrs)
    assert developed["finishing"] == 80
    assert developed["stamina"] == 85


def test_unrecorded_attribute_reads_the_floor() -> None:
    # An attribute absent from the input reads ATTRIBUTE_FLOOR and still develops from there.
    partial = {"finishing": 55}  # stamina etc. absent
    developed = developed_attributes(3000, potential=80, attributes=partial)
    assert developed["stamina"] > ATTRIBUTE_FLOOR


def test_summary_reports_before_after_and_delta() -> None:
    attrs = _attrs(finishing=55, stamina=60)
    summary = development_summary(3000, potential=80, attributes=attrs)
    assert summary["minutes_played"] == 3000
    assert summary["potential"] == 80
    assert summary["before"] == attrs
    assert summary["after"] == developed_attributes(3000, potential=80, attributes=attrs)
    for attribute in ALL_ATTRIBUTES:
        assert summary["delta"][attribute] == summary["after"][attribute] - summary["before"][attribute]
    # Every delta is non-negative: minutes played only ever develops a player.
    assert all(delta >= 0 for delta in summary["delta"].values())
