"""M13 Phase 11 item 47: the club builds a training ground.

Item 4's development curve reads the world's training sessions, but every club trained on the same
ground. This file holds the claims that make a level real: it is bought from the balance as its own
ledger row, it raises the match-minute value of every later session, and the ground cannot be bought
past its ceiling or without the money.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.security import hash_password, new_public_id
from app.models import Career, CareerTrainingWork, Team, User
from app.services.simulation import career as career_service
from app.services.simulation import market
from app.services.simulation.development import (
    TRAINING_LEVEL_BONUS_PCT,
    TRAINING_MAX_LEVEL,
    developed_attributes,
    training_minutes,
)
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


def _career(session: Session, world: dict[str, Any], *, budget: int = BUDGET) -> Career:
    owner = User(
        id=new_public_id("usr"),
        email=f"training-{new_public_id('t')}@example.test",
        password_hash=hash_password("training-service-test"),
        display_name="Training Owner",
        role="player",
    )
    session.add(owner)
    session.commit()
    return career_service.create_career(
        session,
        owner_id=owner.id,
        club=career_service.resolve_club(session, world["club_id"]),
        manager_name="Training Manager",
        philosophy="balanced",
        system_slug="",
        budget=budget,
        objectives=[{"kind": "wins", "target": 1, "label": "win once"}],
        season="2026",
    )


def _works(session: Session, career: Career) -> list[CareerTrainingWork]:
    return list(
        session.scalars(
            select(CareerTrainingWork)
            .where(CareerTrainingWork.career_id == career.id)
            .order_by(CareerTrainingWork.round_index, CareerTrainingWork.created_at)
        ).all()
    )


class TestCurve:
    def test_each_level_makes_a_session_worth_more_and_level_zero_is_the_old_curve(self) -> None:
        assert training_minutes(0) == 0
        assert training_minutes(400, level=0) == 200
        assert training_minutes(400, level=1) == 220
        assert training_minutes(400, level=TRAINING_MAX_LEVEL) == 300
        assert training_minutes(1_000, level=0) == 500
        assert training_minutes(1_000, level=TRAINING_MAX_LEVEL) == 750
        assert TRAINING_LEVEL_BONUS_PCT == 10 and TRAINING_MAX_LEVEL == 5

        base = developed_attributes(500, potential=90, attributes={"ball_control": 60})
        upgraded = developed_attributes(750, potential=90, attributes={"ball_control": 60})
        assert upgraded["ball_control"] >= base["ball_control"] > 60


class TestTrainingGround:
    def test_a_fresh_career_owns_the_inherited_ground(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        view = market.training_view(session, career)

        assert view["available"] is True and view["reason"] is None
        assert view["level"] == 0 and view["bonus_pct"] == 0
        assert view["max_level"] == TRAINING_MAX_LEVEL
        assert view["next_level"] == 1 and view["next_bonus_pct"] == 10
        assert view["next_cost"] == market.TRAINING_UPGRADE_BASE_COST
        assert view["spent"] == 0 and view["rows"] == []

    def test_a_level_is_bought_from_the_balance_and_lands_in_the_ledger(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        before = market.budget_position(session, career)["remaining"]

        rows, after = market.buy_training_level(session, career, levels=1)

        assert len(rows) == 1
        row = rows[0]
        assert int(row.level_before) == 0 and int(row.level_after) == 1
        assert int(row.bonus_pct_before) == 0 and int(row.bonus_pct_after) == 10
        assert int(row.amount) == market.TRAINING_UPGRADE_BASE_COST
        assert int(row.budget_after) == before - int(row.amount)
        session.refresh(career)
        assert int(career.training_level) == 1
        assert after["level"] == 1 and after["bonus_pct"] == 10
        assert after["next_cost"] == market.TRAINING_UPGRADE_BASE_COST * 2

        position = market.budget_position(session, career)
        assert position["remaining"] == before - int(row.amount)
        assert position["training_spent"] == int(row.amount)
        assert position["training_rows"] == 1

        timeline = market.budget_timeline(session, career, limit=0)
        assert timeline["disagreements"] == 0
        assert timeline["closing_balance"] == position["remaining"]
        assert "training" in [entry["kind"] for entry in timeline["rows"]]

        view = market.market_view(session, career)
        training_rows = [entry for entry in view["moves"] if entry["kind"] == "training"]
        assert len(training_rows) == 1
        assert training_rows[0]["cash"] == "out" and training_rows[0]["fee"] == int(row.amount)
        assert training_rows[0]["level_after"] == 1

    def test_two_levels_write_two_rows_and_chain_the_balance(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        before = market.budget_position(session, career)["remaining"]

        rows, after = market.buy_training_level(session, career, levels=2)

        assert [int(row.level_after) for row in rows] == [1, 2]
        assert [int(row.amount) for row in rows] == [
            market.TRAINING_UPGRADE_BASE_COST,
            market.TRAINING_UPGRADE_BASE_COST * 2,
        ]
        assert int(rows[0].budget_after) == before - int(rows[0].amount)
        assert int(rows[1].budget_after) == int(rows[0].budget_after) - int(rows[1].amount)
        assert after["level"] == 2 and after["bonus_pct"] == 20
        assert len(_works(session, career)) == 2


class TestRefusals:
    def test_a_maxed_ground_refuses_another_level(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world, budget=3_000_000)
        market.buy_training_level(session, career, levels=TRAINING_MAX_LEVEL)

        with pytest.raises(market.MarketRefusal) as caught:
            market.buy_training_level(session, career, levels=1)
        assert caught.value.code == "training_maxed"
        assert caught.value.detail["max_level"] == TRAINING_MAX_LEVEL

    def test_an_out_of_range_purchase_names_the_bounds(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)

        for value in (0, -1, TRAINING_MAX_LEVEL + 1):
            with pytest.raises(market.MarketRefusal) as caught:
                market.buy_training_level(session, career, levels=value)
            assert caught.value.code == "bad_training_levels"
            assert caught.value.detail["max_levels"] == TRAINING_MAX_LEVEL
        assert _works(session, career) == []

    def test_a_balance_that_cannot_pay_writes_nothing(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world, budget=10_000)

        with pytest.raises(market.MarketRefusal) as caught:
            market.buy_training_level(session, career, levels=1)
        assert caught.value.code == "insufficient_budget"
        assert caught.value.detail["price"] == market.TRAINING_UPGRADE_BASE_COST
        assert _works(session, career) == []

    def test_a_challenge_or_retired_career_builds_nothing(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        career.challenge_slug = "training-probe"
        session.commit()
        with pytest.raises(market.MarketRefusal) as challenge:
            market.buy_training_level(session, career, levels=1)
        assert challenge.value.code == "challenge_budget"

        career.challenge_slug = ""
        career.status = "retired"
        session.commit()
        with pytest.raises(market.MarketRefusal) as retired:
            market.buy_training_level(session, career, levels=1)
        assert retired.value.code == "career_retired"
        assert _works(session, career) == []
