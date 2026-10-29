"""The board's wage ceiling (Phase 2 item 6): a hard cap on what may be committed.

A career's balance is what is *left*; it says nothing about how much more the board will let the club
commit to wages every round, and sales income walks the balance back up without touching that. This
unit makes the ceiling an object of its own: stated when the career is opened (like the budget, and
`0` for none), enforced by the same helper from `buy` and `loan`, and published beside the arithmetic
it constrains.

The claims worth pinning are the ones a reader can check:

* a stated ceiling is stored as stated, and an unstated one means *no* ceiling, not a ceiling of zero;
* a bill exactly at the ceiling is within it, one credit over is refused with the figures that decided it;
* a loan is charged exactly like a buy, and a sale frees the headroom it needs;
* `0` means no ceiling, which is what a career opened before the column holds.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.security import hash_password, new_public_id
from app.models import Career, Team, TransferListing, User
from app.services.simulation import career as career_service
from app.services.simulation import market
from app.services.simulation.market import WAGE_CEILING_FORMULA, MarketRefusal, signing_impact, wage_headroom
from app.services.world import sync_world

BUDGET = 4_000_000


@pytest.fixture(scope="module")
def world() -> dict[str, Any]:
    session = SessionLocal()
    result = sync_world(session)
    assert result.ok, result.errors[:5]
    club = session.scalars(select(Team).order_by(Team.overall, Team.slug).limit(1)).one()
    owner = User(
        id=new_public_id("usr"),
        email=f"ceiling-{uuid4().hex[:8]}@example.test",
        password_hash=hash_password("wage-ceiling-test"),
        display_name="Ceiling Owner",
        role="player",
    )
    session.add(owner)
    session.commit()
    data: dict[str, Any] = {"club_id": club.id, "owner_id": owner.id}
    session.close()
    return data


@pytest.fixture()
def session() -> Iterator[Session]:
    value = SessionLocal()
    try:
        yield value
    finally:
        value.close()


def _career(session: Session, world: dict[str, Any], *, budget: int = BUDGET, wage_ceiling: int = 0) -> Career:
    return career_service.create_career(
        session,
        owner_id=world["owner_id"],
        club=career_service.resolve_club(session, world["club_id"]),
        manager_name="Ceiling Manager",
        philosophy="balanced",
        system_slug="",
        budget=budget,
        objectives=[{"kind": "wins", "target": 1, "label": "win once"}],
        season="2026",
        wage_ceiling=wage_ceiling,
    )


def _listings(session: Session, career: Career) -> list[TransferListing]:
    """The open offers, cheapest first, priced by the market's own valuation."""
    market.open_market(session, career)
    rows = list(session.scalars(select(TransferListing).where(TransferListing.career_id == career.id, TransferListing.status == "open")).all())
    assert rows, "the market opened no offers"
    return sorted(rows, key=lambda row: (int(row.current_price), int(row.weekly_wage), row.id))


def _listing(session: Session, career: Career) -> TransferListing:
    return _listings(session, career)[0]


class TestThePureArithmetic:
    def test_no_ceiling_has_no_headroom_rather_than_a_headroom_of_zero(self) -> None:
        assert wage_headroom(0, 250) is None
        assert wage_headroom(-1, 250) is None

    def test_headroom_is_signed_so_an_overrun_is_visible(self) -> None:
        assert wage_headroom(100, 40) == 60
        assert wage_headroom(100, 100) == 0
        assert wage_headroom(100, 130) == -30

    def test_a_preview_without_a_ceiling_answers_none(self) -> None:
        impact = signing_impact(1000, 50, price=100, proposed_weekly_wage=20)
        assert impact["wage_ceiling"] == 0
        assert impact["wage_affordable"] is None
        assert impact["wage_headroom_after"] is None

    def test_a_preview_at_the_ceiling_is_within_it_and_one_over_is_not(self) -> None:
        at = signing_impact(1000, 50, price=100, proposed_weekly_wage=50, wage_ceiling=100)
        assert at["new_weekly_wage_bill"] == 100 and at["wage_affordable"] is True and at["wage_headroom_after"] == 0
        over = signing_impact(1000, 50, price=100, proposed_weekly_wage=51, wage_ceiling=100)
        assert over["wage_affordable"] is False and over["wage_headroom_after"] == -1

    def test_the_formula_names_the_rule_the_code_enforces(self) -> None:
        assert "stated when the career is opened" in WAGE_CEILING_FORMULA
        assert "0 = the board sets no cap" in WAGE_CEILING_FORMULA
        assert "wage_ceiling_exceeded" in WAGE_CEILING_FORMULA


class TestTheCeilingAtTheDoor:
    def test_a_career_stores_the_ceiling_it_was_opened_with(self, session: Session, world: dict[str, Any]) -> None:
        career = _career(session, world, budget=400_000, wage_ceiling=1_234)
        assert int(career.wage_ceiling) == 1_234
        unstated = _career(session, world, budget=400_000)
        assert int(unstated.wage_ceiling) == 0, "an unstated ceiling is no ceiling, not zero credits"

    def test_a_bill_exactly_at_the_ceiling_is_within_it(self, session: Session, world: dict[str, Any]) -> None:
        career = _career(session, world)
        row = _listing(session, career)
        ceiling = int(row.weekly_wage)
        career.wage_ceiling = ceiling
        session.commit()
        move, _ = market.buy(session, career, ident=row.id, use_clause=True)
        assert int(move.weekly_wage) == ceiling
        position = market.budget_position(session, career)
        assert position["wage_ceiling"] == ceiling
        assert position["wage_committed_per_week"] == ceiling
        assert position["wage_headroom"] == 0

    def test_one_credit_over_the_ceiling_is_refused_with_the_figures(self, session: Session, world: dict[str, Any]) -> None:
        career = _career(session, world)
        row = _listing(session, career)
        career.wage_ceiling = int(row.weekly_wage) - 1
        session.commit()
        with pytest.raises(MarketRefusal) as caught:
            market.buy(session, career, ident=row.id, use_clause=True)
        assert caught.value.code == "wage_ceiling_exceeded"
        detail = caught.value.detail
        assert detail["wage_ceiling"] == int(row.weekly_wage) - 1
        assert detail["proposed_weekly_wage"] == int(row.weekly_wage)
        assert detail["new_weekly_wage_bill"] == int(row.weekly_wage)
        assert detail["weekly_wage_bill"] == 0
        assert detail["wage_headroom"] == int(row.weekly_wage) - 1
        assert detail["formula"] == WAGE_CEILING_FORMULA
        assert session.scalars(select(TransferListing).where(TransferListing.id == row.id)).one().status == "open"

    def test_a_loan_is_charged_the_same_way(self, session: Session, world: dict[str, Any]) -> None:
        career = _career(session, world)
        row = _listing(session, career)
        career.wage_ceiling = int(row.weekly_wage) - 1
        session.commit()
        with pytest.raises(MarketRefusal) as caught:
            market.loan(session, career, ident=row.id)
        assert caught.value.code == "wage_ceiling_exceeded"
        career.wage_ceiling = int(row.weekly_wage)
        session.commit()
        move, _ = market.loan(session, career, ident=row.id)
        assert int(move.weekly_wage) == int(career.wage_ceiling)

    def test_a_sale_frees_the_headroom_for_the_next_signing(self, session: Session, world: dict[str, Any]) -> None:
        career = _career(session, world)
        rows = _listings(session, career)
        first = rows[0]
        second = next(row for row in rows if int(row.weekly_wage) > int(first.weekly_wage))
        career.wage_ceiling = int(first.weekly_wage) + int(second.weekly_wage) - 1
        session.commit()
        move, _ = market.buy(session, career, ident=first.id, use_clause=True)
        with pytest.raises(MarketRefusal) as caught:
            market.buy(session, career, ident=second.id, use_clause=True)
        assert caught.value.code == "wage_ceiling_exceeded"
        market.sell(session, career, ident=move.player_id)
        move2, _ = market.buy(session, career, ident=second.id, use_clause=True)
        assert int(move2.weekly_wage) == int(second.weekly_wage)

    def test_no_ceiling_refuses_nothing(self, session: Session, world: dict[str, Any]) -> None:
        career = _career(session, world)
        career.wage_ceiling = 0
        session.commit()
        row = _listing(session, career)
        move, _ = market.buy(session, career, ident=row.id, use_clause=True)
        assert int(move.weekly_wage) > 0
        view = market.affordability_view(session, career)
        assert view["wage_ceiling"] == 0 and view["wage_headroom"] is None and view["within_ceiling"] is True

    def test_the_view_and_the_listing_carry_the_same_verdict(self, session: Session, world: dict[str, Any]) -> None:
        career = _career(session, world)
        row = _listing(session, career)
        career.wage_ceiling = int(row.weekly_wage) - 1
        session.commit()
        view = market.affordability_view(session, career)
        assert view["within_ceiling"] is True
        market_view = market.market_view(session, career)
        listed = next(item for item in market_view["listings"] if item["id"] == row.id)
        assert listed["signing"]["wage_affordable"] is False
        assert listed["signing"]["wage_ceiling"] == int(career.wage_ceiling)
        assert listed["signing"]["wage_headroom_after"] == -1
        assert market_view["rules"]["wage_ceiling"] == WAGE_CEILING_FORMULA
