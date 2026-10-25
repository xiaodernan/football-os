"""The read-only affordability arithmetic (Phase 2): a wage runway and a signing preview.

`wage_runway` and `signing_impact` are pure functions over the figures `budget_position` already
publishes, so they are tested without a database: the claims worth pinning are that a zero wage bill has
no wage limit rather than an infinite one, a partial round does not buy another round, an overdrawn
balance has a spent runway, and a signing is affordable exactly when the balance after its fee stays
non-negative.
"""

from __future__ import annotations

from app.services.simulation.market import AFFORDABILITY_FORMULA, signing_impact, wage_runway


class TestWageRunway:
    def test_no_wage_bill_has_no_wage_limit(self) -> None:
        assert wage_runway(1000, 0) is None

    def test_a_negative_bill_is_treated_as_no_obligation(self) -> None:
        assert wage_runway(1000, -5) is None

    def test_the_runway_is_the_balance_divided_by_the_weekly_bill(self) -> None:
        assert wage_runway(1000, 50) == 20

    def test_a_partial_round_does_not_buy_another_round(self) -> None:
        assert wage_runway(149, 50) == 2

    def test_an_overdrawn_balance_has_a_spent_runway(self) -> None:
        assert wage_runway(-10, 50) == 0


class TestSigningImpact:
    def test_an_affordable_signing_moves_the_balance_and_the_bill(self) -> None:
        impact = signing_impact(1000, 50, price=300, proposed_weekly_wage=20)
        assert impact["fee_affordable"] is True
        assert impact["remaining_after_fee"] == 700
        assert impact["new_weekly_wage_bill"] == 70
        assert impact["new_wage_runway_rounds"] == 10

    def test_an_unaffordable_fee_is_reported_with_its_shortfall(self) -> None:
        impact = signing_impact(100, 50, price=300, proposed_weekly_wage=10)
        assert impact["fee_affordable"] is False
        assert impact["remaining_after_fee"] == -200
        assert impact["new_wage_runway_rounds"] == 0

    def test_a_zero_wage_signing_leaves_the_bill_alone(self) -> None:
        impact = signing_impact(1000, 50, price=0, proposed_weekly_wage=0)
        assert impact["new_weekly_wage_bill"] == 50
        assert impact["new_wage_runway_rounds"] == 20

    def test_the_published_formula_names_the_runway_and_the_fee_test(self) -> None:
        assert "wage_runway_rounds" in AFFORDABILITY_FORMULA
        assert "remaining − price" in AFFORDABILITY_FORMULA
