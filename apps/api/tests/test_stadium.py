"""M13 Phase 9 item 37: buying seats for the career's ground.

The stand is the first thing a manager can buy that is not a player, so the claims are the ledger's
ones: a purchase costs the published price, every bought seat is one more seat the next home gate can
sell, the balance and the timeline count the same row, and a refusal names the figure that decided it.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.security import hash_password, new_public_id
from app.models import Career, CareerStadiumWork, Competition, Team, User
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
    owner = User(
        id=new_public_id("usr"),
        email=f"stadium-{club.slug[:8]}@example.test",
        password_hash=hash_password("stadium-service-test"),
        display_name="Stadium Owner",
        role="player",
    )
    session.add(owner)
    session.commit()
    data = {"club_id": club.id, "club_name": club.name, "owner_id": owner.id}
    session.close()
    return data


@pytest.fixture()
def session() -> Iterator[Session]:
    value = SessionLocal()
    try:
        yield value
    finally:
        value.close()


def _career(session: Session, world: dict[str, Any], **kwargs: Any) -> Career:
    return career_service.create_career(
        session,
        owner_id=world["owner_id"],
        club=career_service.resolve_club(session, world["club_id"]),
        manager_name=kwargs.pop("manager_name", "Stadium Manager"),
        philosophy=kwargs.pop("philosophy", "balanced"),
        system_slug=kwargs.pop("system_slug", ""),
        budget=kwargs.pop("budget", BUDGET),
        objectives=kwargs.pop("objectives", [{"kind": "wins", "target": 1, "label": "win once"}]),
        season="2026",
    )


def _tier(session: Session, career: Career) -> int:
    competition = session.get(Competition, career.competition_id) if career.competition_id else None
    return int(competition.tier or 0) if competition is not None else 0


def _gate_capacity(session: Session, career: Career) -> int:
    club = session.get(Team, career.club_id) if career.club_id else None
    return int(market.gate_capacity_for(session, career, club, _tier(session, career))[0])


class TestStadiumPurchase:
    def test_the_published_price_buys_every_seat_the_gate_can_sell(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        before = _gate_capacity(session, career)
        work, view = market.buy_seats(session, career, seats=500)

        assert int(work.seats) == 500
        assert int(work.unit_cost) == market.STADIUM_SEAT_COST
        assert int(work.amount) == 500 * market.STADIUM_SEAT_COST
        assert int(work.capacity_after) - int(work.capacity_before) == 500
        assert view["bought_seats"] == 500 and view["rows"] == 1
        assert view["spent"] == 500 * market.STADIUM_SEAT_COST
        assert _gate_capacity(session, career) == before + 500

        position = market.budget_position(session, career)
        assert position["stadium_spent"] == 500 * market.STADIUM_SEAT_COST
        assert position["remaining"] == BUDGET - 500 * market.STADIUM_SEAT_COST

    def test_purchases_accumulate_and_the_timeline_counts_the_same_rows(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        market.buy_seats(session, career, seats=500)
        market.buy_seats(session, career, seats=1_000)
        career_service.play_round(session, career)

        view = market.stadium_view(session, career)
        assert view["bought_seats"] == 1_500 and view["rows"] == 2
        position = market.budget_position(session, career)
        assert position["stadium_spent"] == 1_500 * market.STADIUM_SEAT_COST
        assert position["remaining"] == market.affordability_view(session, career)["remaining"]

        timeline = market.budget_timeline(session, career, limit=0)
        assert timeline["disagreements"] == 0
        assert timeline["closing_balance"] == position["remaining"]
        assert sum(1 for row in timeline["rows"] if row["kind"] == "stadium") == 2
        assert any(row["kind"] == "stadium" and row["delta"] < 0 for row in timeline["rows"])

    def test_the_market_page_prints_the_ground_and_its_ledger_rows(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        market.buy_seats(session, career, seats=500)

        view = market.market_view(session, career)
        assert view["stadium"]["bought_seats"] == 500
        assert view["stadium"]["gate_capacity"] == _gate_capacity(session, career)
        assert view["budget"]["stadium_spent"] == 500 * market.STADIUM_SEAT_COST
        assert view["totals"]["stadium_rows"] == 1
        row = next(entry for entry in view["moves"] if entry["kind"] == "stadium")
        assert row["side"] == "out" and row["fee"] == 500 * market.STADIUM_SEAT_COST
        assert view["constants"]["stadium_seat_cost"] == market.STADIUM_SEAT_COST
        assert "stadium" in view["rules"]

    def test_every_refusal_names_its_rule_and_writes_nothing(self, session, world) -> None:  # type: ignore[no-untyped-def]
        poor = _career(session, world, budget=5_000)
        with pytest.raises(market.MarketRefusal) as expensive:
            market.buy_seats(session, poor, seats=500)
        assert expensive.value.code == "insufficient_budget"
        assert expensive.value.detail["price"] == 500 * market.STADIUM_SEAT_COST

        career = _career(session, world)
        with pytest.raises(market.MarketRefusal) as too_small:
            market.buy_seats(session, career, seats=market.STADIUM_MIN_SEATS - 1)
        assert too_small.value.code == "bad_seats"
        with pytest.raises(market.MarketRefusal) as too_large:
            market.buy_seats(session, career, seats=market.STADIUM_MAX_SEATS + 1)
        assert too_large.value.code == "bad_seats"

        challenge = _career(session, world)
        challenge.challenge_slug = "no-transfer-challenge"
        session.commit()
        with pytest.raises(market.MarketRefusal) as authored:
            market.buy_seats(session, challenge, seats=500)
        assert authored.value.code == "challenge_budget"

        retired = _career(session, world)
        retired.status = "retired"
        session.commit()
        with pytest.raises(market.MarketRefusal) as closed:
            market.buy_seats(session, retired, seats=500)
        assert closed.value.code == "career_retired"

        wrote = session.scalars(
            select(CareerStadiumWork).where(CareerStadiumWork.career_id.in_([career.id, poor.id, challenge.id, retired.id]))
        ).all()
        assert list(wrote) == []
