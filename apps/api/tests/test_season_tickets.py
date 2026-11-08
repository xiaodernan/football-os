"""M13 Phase 10 item 46: a season ticket is money now for seats later.

The gate prices one crowd. A season ticket sells the same seat for every home league round before the
season starts, at a discount, and those seats are then in the ground without being charged again. The
claims here are the ledger's usual ones — the row is the money, the receipt keeps the seats it did not
charge, and a refusal names the window or the block that decided it.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.security import hash_password, new_public_id
from app.models import Career, CareerGateReceipt, CareerSeasonTicket, Team, User
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


def _career(session: Session, world: dict[str, Any]) -> Career:
    owner = User(
        id=new_public_id("usr"),
        email=f"season-tickets-{new_public_id('s')}@example.test",
        password_hash=hash_password("season-ticket-service-test"),
        display_name="Season Ticket Owner",
        role="player",
    )
    session.add(owner)
    session.commit()
    return career_service.create_career(
        session,
        owner_id=owner.id,
        club=career_service.resolve_club(session, world["club_id"]),
        manager_name="Season Ticket Manager",
        philosophy="balanced",
        system_slug="",
        budget=BUDGET,
        objectives=[{"kind": "wins", "target": 1, "label": "win once"}],
        season="2026",
    )


def _sales(session: Session, career: Career) -> list[CareerSeasonTicket]:
    return list(
        session.scalars(
            select(CareerSeasonTicket).where(CareerSeasonTicket.career_id == career.id)
        ).all()
    )


class TestOffer:
    def test_the_offer_prices_the_season_s_home_rounds_at_the_discount(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        view = market.season_ticket_view(session, career)

        assert view["available"] is True and view["reason"] is None
        assert view["season_index"] == 1 and view["first_round"] == 1
        assert view["home_rounds"] > 0
        assert view["full_price"] == view["base_price"] * view["home_rounds"]
        assert view["unit_price"] == int(
            round(view["full_price"] * market.SEASON_TICKET_DISCOUNT_PCT / 100)
        )
        assert view["max_seats"] == (
            view["capacity"] * market.SEASON_TICKET_MAX_SHARE_PCT // 100
        ) // market.SEASON_TICKET_MIN_SEATS * market.SEASON_TICKET_MIN_SEATS
        assert view["sold"] is None and view["rows"] == [] and view["income"] == 0
        assert view["discount_pct"] == 85


class TestSale:
    def test_a_block_pays_now_and_lands_in_the_ledger(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        before = market.budget_position(session, career)["remaining"]
        view = market.season_ticket_view(session, career)
        seats = 1_000

        row, after = market.buy_season_tickets(session, career, seats=seats)

        assert int(row.seats) == seats
        assert int(row.unit_price) == view["unit_price"]
        assert int(row.amount) == seats * view["unit_price"]
        assert int(row.home_rounds) == view["home_rounds"]
        assert int(row.round_index) == view["first_round"]
        assert int(row.budget_after) == before + int(row.amount)
        assert after["sold"] is not None and after["sold"]["id"] == row.id
        assert after["income"] == int(row.amount)

        position = market.budget_position(session, career)
        assert position["remaining"] == before + int(row.amount)
        assert position["season_ticket_income"] == int(row.amount)
        assert position["season_ticket_rows"] == 1

        timeline = market.budget_timeline(session, career, limit=0)
        assert timeline["disagreements"] == 0
        assert timeline["closing_balance"] == position["remaining"]
        kinds = [entry["kind"] for entry in timeline["rows"]]
        assert "season_tickets" in kinds

        ledger = market.ledger_of([], [], season_tickets=[market.season_ticket_ledger_row(row)])
        assert [entry["kind"] for entry in ledger] == ["season_tickets"]
        assert ledger[0]["cash"] == "in" and ledger[0]["fee"] == int(row.amount)
        assert ledger[0]["season_index"] == view["season_index"]

    def test_season_seats_fill_the_ground_but_only_paid_seats_are_charged(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        seats = 1_000
        market.buy_season_tickets(session, career, seats=seats)

        for _ in range(6):
            fixture, _match = career_service.play_round(session, career)
            if str(fixture.side) == "home":
                break
        else:
            raise AssertionError("six rounds wrote no home fixture")

        receipt = session.scalar(
            select(CareerGateReceipt).where(
                CareerGateReceipt.career_id == career.id,
                CareerGateReceipt.round_index == fixture.round_index,
            )
        )
        assert receipt is not None
        assert int(receipt.season_ticket_seats) == seats
        assert int(receipt.attendance) >= seats
        paid = int(receipt.attendance) - seats
        assert int(receipt.amount) == int(
            round(paid * int(receipt.ticket_price) * int(receipt.price_pct) / 100)
        )
        assert "season-ticket seats are not charged again" in receipt.basis
        assert market.gate_row(receipt)["season_ticket_seats"] == seats


class TestRefusals:
    def test_a_second_sale_in_the_same_season_is_refused(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        market.buy_season_tickets(session, career, seats=500)

        with pytest.raises(market.MarketRefusal) as caught:
            market.buy_season_tickets(session, career, seats=500)
        assert caught.value.code == "season_tickets_already_sold"
        assert len(_sales(session, career)) == 1

    def test_the_window_closes_once_the_season_has_started(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        career_service.play_round(session, career)
        session.refresh(career)

        with pytest.raises(market.MarketRefusal) as caught:
            market.buy_season_tickets(session, career, seats=1_000)
        assert caught.value.code == "season_ticket_window_closed"
        assert caught.value.detail["played"] == 1
        assert _sales(session, career) == []

    def test_an_off_step_or_oversized_block_names_the_bounds(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        view = market.season_ticket_view(session, career)
        top = int(view["max_seats"])

        for value in (50, 150, top + 100):
            with pytest.raises(market.MarketRefusal) as caught:
                market.buy_season_tickets(session, career, seats=value)
            assert caught.value.code == "bad_season_ticket_seats"
            assert caught.value.detail["seats"] == value
            assert caught.value.detail["min_seats"] == 100
            assert caught.value.detail["step_seats"] == 100
        assert _sales(session, career) == []

    def test_a_challenge_or_retired_career_sells_nothing(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        career.challenge_slug = "season-ticket-probe"
        session.commit()
        with pytest.raises(market.MarketRefusal) as challenge:
            market.buy_season_tickets(session, career, seats=1_000)
        assert challenge.value.code == "challenge_budget"

        career.challenge_slug = ""
        career.status = "retired"
        session.commit()
        with pytest.raises(market.MarketRefusal) as retired:
            market.buy_season_tickets(session, career, seats=1_000)
        assert retired.value.code == "career_retired"
        assert _sales(session, career) == []
