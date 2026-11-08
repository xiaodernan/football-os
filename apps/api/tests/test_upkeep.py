"""M13 Phase 10 item 45: the ground costs money to run.

Item 37 made a stand a purchase and item 44 made its seats a price. Without a running cost the only
reason not to build was the once-off fee, which a full house repays in a few seasons. This file holds
the claims that make the cost real: only a home round pays, the rate follows the physical ground, a
challenge pays nothing, and the row closes the same timeline the gate and the wages close.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.security import hash_password, new_public_id
from app.models import Career, CareerFixture, CareerGateReceipt, CareerUpkeepCharge, Team, User
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
        email=f"upkeep-{new_public_id('u')}@example.test",
        password_hash=hash_password("upkeep-service-test"),
        display_name="Upkeep Owner",
        role="player",
    )
    session.add(owner)
    session.commit()
    return career_service.create_career(
        session,
        owner_id=owner.id,
        club=career_service.resolve_club(session, world["club_id"]),
        manager_name="Upkeep Manager",
        philosophy="balanced",
        system_slug="",
        budget=BUDGET,
        objectives=[{"kind": "wins", "target": 1, "label": "win once"}],
        season="2026",
    )


def _upkeep_rows(session: Session, career: Career) -> list[CareerUpkeepCharge]:
    return list(
        session.scalars(
            select(CareerUpkeepCharge)
            .where(CareerUpkeepCharge.career_id == career.id)
            .order_by(CareerUpkeepCharge.round_index)
        ).all()
    )


class TestUpkeepCharge:
    def test_a_home_round_pays_for_the_seats_it_opens(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        view = market.stadium_view(session, career)
        expected = int(round(view["capacity"] * market.STADIUM_UPKEEP_PER_SEAT_PCT / 100))
        assert view["upkeep_per_home_round"] == expected > 0

        for _ in range(6):
            fixture, _match = career_service.play_round(session, career)
            if str(fixture.side) == "home":
                break
        else:
            raise AssertionError("six rounds wrote no home fixture")

        rows = _upkeep_rows(session, career)
        assert len(rows) == 1
        charge = rows[0]
        assert int(charge.round_index) == int(fixture.round_index)
        assert int(charge.capacity) == view["capacity"]
        assert int(charge.seat_rate_pct) == market.STADIUM_UPKEEP_PER_SEAT_PCT
        assert int(charge.amount) == expected

        gate = session.scalar(
            select(CareerGateReceipt).where(
                CareerGateReceipt.career_id == career.id,
                CareerGateReceipt.round_index == fixture.round_index,
            )
        )
        assert gate is not None
        assert int(charge.budget_after) == int(gate.budget_after) - int(charge.amount)

        position = market.budget_position(session, career)
        assert position["upkeep_spent"] == int(charge.amount)
        assert position["upkeep_rows"] == 1
        assert position["remaining"] == BUDGET + int(gate.amount) - int(charge.amount)

        timeline = market.budget_timeline(session, career, limit=0)
        assert timeline["disagreements"] == 0 and timeline["closing_balance"] == position["remaining"]
        kinds = [row["kind"] for row in timeline["rows"]]
        assert kinds.index("gate") < kinds.index("upkeep")

    def test_an_away_round_pays_nothing(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        away: CareerFixture | None = None
        for _ in range(8):
            fixture, _match = career_service.play_round(session, career)
            if str(fixture.side) == "away":
                away = fixture
                break
        assert away is not None, "eight rounds drew no away fixture"
        assert not any(int(row.round_index) == int(away.round_index) for row in _upkeep_rows(session, career))

    def test_a_challenge_career_pays_no_upkeep(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        career.challenge_slug = "upkeep-probe"
        session.commit()
        for _ in range(3):
            career_service.play_round(session, career)
        assert _upkeep_rows(session, career) == []
        assert market.budget_position(session, career)["upkeep_spent"] == 0

    def test_a_bought_stand_raises_the_running_cost_by_its_share(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        before_view = market.stadium_view(session, career)
        before = before_view["upkeep_per_home_round"]
        market.buy_seats(session, career, seats=500)
        after = market.stadium_view(session, career)

        assert after["capacity"] == before_view["capacity"] + 500
        assert after["upkeep_per_home_round"] - before == int(
            round(500 * market.STADIUM_UPKEEP_PER_SEAT_PCT / 100)
        )

    def test_the_ledger_carries_the_cost_as_its_own_row(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        for _ in range(6):
            fixture, _match = career_service.play_round(session, career)
            if str(fixture.side) == "home":
                break
        view = market.market_view(session, career)
        rows = [row for row in view["moves"] if row["kind"] == "upkeep"]
        assert len(rows) == 1
        assert rows[0]["cash"] == "out" and rows[0]["fee"] > 0
        assert rows[0]["capacity"] == view["stadium"]["capacity"]
        assert rows[0]["seat_rate_pct"] == market.STADIUM_UPKEEP_PER_SEAT_PCT
        assert "running rate" in rows[0]["detail"]
