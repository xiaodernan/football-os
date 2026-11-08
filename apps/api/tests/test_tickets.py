"""M13 Phase 10 item 44: the manager sets the gate price.

The price is the first decision that trades one figure against another: a dearer seat earns more per
head and sells fewer, a cheaper one fills the ground and earns less each. The claims are the ledger's
usual ones — the stored row is the money, the receipt keeps the price it was paid on, and a refusal
names the setting that decided it.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.security import hash_password, new_public_id
from app.models import Career, CareerGateReceipt, Team, User
from app.services.simulation import career as career_service
from app.services.simulation import market
from app.services.world import sync_world

BUDGET = 2_000_000


@pytest.fixture(scope="module")
def world() -> dict[str, Any]:
    session = SessionLocal()
    result = sync_world(session)
    assert result.ok, result.errors[:5]
    club = session.scalars(select(Team).order_by(Team.overall, Team.slug).limit(1)).one()
    data = {"club_id": club.id, "club_name": club.name}
    session.close()
    return data


@pytest.fixture()
def session() -> Iterator[Session]:
    value = SessionLocal()
    try:
        yield value
    finally:
        value.close()


def _owner(session: Session) -> User:
    owner = User(
        id=new_public_id("usr"),
        email=f"tickets-{new_public_id('t')}@example.test",
        password_hash=hash_password("tickets-service-test"),
        display_name="Ticket Owner",
        role="player",
    )
    session.add(owner)
    session.commit()
    return owner


def _career(session: Session, world: dict[str, Any]) -> Career:
    owner = _owner(session)
    return career_service.create_career(
        session,
        owner_id=owner.id,
        club=career_service.resolve_club(session, world["club_id"]),
        manager_name="Ticket Manager",
        philosophy="balanced",
        system_slug="",
        budget=BUDGET,
        objectives=[{"kind": "wins", "target": 1, "label": "win once"}],
        season="2026",
    )


def _home_receipt(session: Session, career: Career) -> CareerGateReceipt:
    """Play until a home round writes its gate; the first fixture of a drawn season may be away."""
    for _ in range(4):
        career_service.play_round(session, career)
        rows = list(
            session.scalars(select(CareerGateReceipt).where(CareerGateReceipt.career_id == career.id)).all()
        )
        if rows:
            return rows[0]
    raise AssertionError("four rounds wrote no home gate")


class TestDemandCurve:
    def test_the_curve_falls_with_the_price_and_states_its_maximum(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        view = market.ticket_price_view(session, career)

        assert view["price_pct"] == 100 and view["demand_pct"] == 100
        assert view["revenue_index"] == 100
        assert view["best_price_pct"] == 120
        assert view["best_revenue_index"] == 106
        assert view["min_pct"] == 50 and view["max_pct"] == 200 and view["step_pct"] == 5
        assert market.demand_pct_for(50) > 100
        assert market.demand_pct_for(120) == 88
        assert market.demand_pct_for(200) == 20

        prices = range(view["min_pct"], view["max_pct"] + 1, view["step_pct"])
        demands = [market.demand_pct_for(value) for value in prices]
        assert demands == sorted(demands, reverse=True)

    def test_a_cheaper_seat_fills_more_of_the_ground_and_a_dearer_one_less(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)

        market.set_ticket_price(session, career, price_pct=80)
        cheap = market.ticket_price_view(session, career)
        market.set_ticket_price(session, career, price_pct=140)
        dear = market.ticket_price_view(session, career)

        assert cheap["demand_pct"] > 100 > dear["demand_pct"]
        assert cheap["revenue_index"] < 100 < dear["revenue_index"]
        assert dear["best_revenue_index"] > dear["revenue_index"]


class TestGatePrice:
    def test_a_neutral_price_pays_item_33s_gate_exactly(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        receipt = _home_receipt(session, career)

        assert receipt.price_pct == 100 and receipt.demand_pct == 100
        assert receipt.amount == receipt.attendance * receipt.ticket_price
        row = market.gate_row(receipt)
        assert row["price_pct"] == 100 and row["demand_pct"] == 100
        assert "at 100%" in row["detail"]

    def test_a_dearer_price_is_paid_on_the_crowd_it_draws(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        market.set_ticket_price(session, career, price_pct=120)
        receipt = _home_receipt(session, career)

        assert receipt.price_pct == 120 and receipt.demand_pct == 88
        assert receipt.amount == int(round(receipt.attendance * receipt.ticket_price * 120 / 100))
        assert "demand 88%" in receipt.basis

    def test_a_later_price_change_does_not_rewrite_a_paid_crowd(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        receipt = _home_receipt(session, career)
        paid = (receipt.amount, receipt.attendance, receipt.price_pct, receipt.demand_pct)

        market.set_ticket_price(session, career, price_pct=150)
        session.refresh(receipt)

        assert (receipt.amount, receipt.attendance, receipt.price_pct, receipt.demand_pct) == paid
        session.refresh(career)
        assert career.ticket_price_pct == 150


class TestRefusals:
    def test_an_off_step_price_names_the_bounds_and_the_step(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)

        for value in (33, 117, 205):
            with pytest.raises(market.MarketRefusal) as caught:
                market.set_ticket_price(session, career, price_pct=value)
            assert caught.value.code == "bad_ticket_price"
            assert caught.value.detail["price_pct"] == value
            assert caught.value.detail["min_pct"] == 50
            assert caught.value.detail["max_pct"] == 200
            assert caught.value.detail["step_pct"] == 5

        assert career.ticket_price_pct == 100

    def test_a_challenge_or_retired_career_prices_no_gate(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        career.challenge_slug = "ticket-probe"
        session.commit()
        with pytest.raises(market.MarketRefusal) as challenge:
            market.set_ticket_price(session, career, price_pct=120)
        assert challenge.value.code == "challenge_budget"

        career.challenge_slug = ""
        career.status = "retired"
        session.commit()
        with pytest.raises(market.MarketRefusal) as retired:
            market.set_ticket_price(session, career, price_pct=120)
        assert retired.value.code == "career_retired"
