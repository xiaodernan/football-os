"""M13 item 28: a career's own clock ages its players and retires them at a season boundary.

The world stores one `real_players.age` per player and every career shares it, so ageing a player in
one career must not age them in another. The clock therefore lives on the career: a player's effective
age is the stored age plus the seasons this career has closed. These tests hold the three consequences
that make the clock real rather than descriptive:

* the offset is the closed-season count, and a valuation and a contract book read the same number;
* the boundary writes a `retire` row for a player whose career-clock age has reached the threshold, so
  the squad overlay drops them and the wage bill stops charging them;
* a retirement never leaves the club unable to field eleven with a keeper, and a challenge career with
  no season after its window retires nobody.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.security import hash_password, new_public_id
from app.models import Career, CareerFixture, CareerSquadMove, RealPlayer, Team, TransferListing, User
from app.services.simulation import ageing, intake, market
from app.services.simulation import career as career_service
from app.services.simulation import squad as squad_service
from app.services.world import sync_world

BUDGET = 4_000_000


@pytest.fixture(scope="module")
def world() -> dict[str, Any]:
    session = SessionLocal()
    result = sync_world(session)
    assert result.ok, result.errors[:5]
    club = session.scalars(select(Team).order_by(Team.overall, Team.slug).limit(1)).one()
    rivals = list(session.scalars(select(Team).where(Team.competition_id == club.competition_id, Team.id != club.id)).all())
    outsiders = list(session.scalars(select(Team).where(Team.competition_id != club.competition_id, Team.competition_id.is_not(None))).all())
    owner = User(
        id=new_public_id("usr"),
        email=f"ageing-{club.slug[:8]}@example.test",
        password_hash=hash_password("ageing-service-test"),
        display_name="Ageing Owner",
        role="player",
    )
    session.add(owner)
    session.commit()
    data: dict[str, Any] = {
        "club_id": club.id,
        "club_name": club.name,
        "rival_ids": [team.id for team in rivals],
        "outsider_id": outsiders[0].id,
        "owner_id": owner.id,
    }
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
    return career_service.create_career(
        session,
        owner_id=world["owner_id"],
        club=career_service.resolve_club(session, world["club_id"]),
        manager_name="Ageing Manager",
        philosophy="balanced",
        system_slug="",
        budget=BUDGET,
        objectives=[{"kind": "wins", "target": 1, "label": "win once"}],
        season="2026",
    )


def _squad(session: Session, career: Career) -> list[RealPlayer]:
    return squad_service.current_squad(session, career)[0]


def _fabricate_season(session: Session, career: Career, rounds: int) -> None:
    """Write one winning fixture per round, so the boundary has a record to judge."""
    for index in range(1, rounds + 1):
        session.add(
            CareerFixture(
                id=new_public_id("cf"),
                career_id=career.id,
                round_index=index,
                side="home" if index % 2 else "away",
                opponent_name=f"Fabricated Opponent {index}",
                opponent_short=f"FO{index}",
                venue_name="Fabricated Ground",
                club_goals=1,
                opponent_goals=0,
                outcome="W",
                points=career_service.POINTS_FOR["W"],
            )
        )
    career.rounds_played = rounds
    session.commit()
    session.refresh(career)


def _sign(session: Session, world: dict[str, Any], career: Career) -> tuple[RealPlayer, CareerSquadMove]:
    """Sign one rival's best attacker at its release clause and return the player and the row."""
    player = max(
        (row for team_id in world["rival_ids"] + [world["outsider_id"]] for row in session.scalars(select(RealPlayer).where(RealPlayer.team_id == team_id))),
        key=lambda row: (row.overall, row.potential),
    )
    price = market.valuation(player)
    listing = TransferListing(
        id=new_public_id("tl"),
        career_id=career.id,
        player_id=player.id,
        player_slug=player.slug,
        player_name=player.name,
        position=player.position,
        age=player.age,
        overall=player.overall,
        potential=player.potential,
        from_team_id=player.team_id,
        from_team_name=str(session.scalar(select(Team.name).where(Team.id == player.team_id)) or ""),
        asking_fee=price["asking_fee"],
        current_price=price["asking_fee"],
        release_clause=price["release_clause"],
        contract_years=price["contract_years"],
        weekly_wage=price["weekly_wage"],
        tactical_fit=market.tactical_fit(player, "attack")["fit"],
        needed_band="attack",
        status="open",
        listed_round=1,
        negotiations=0,
        last_offer=0,
    )
    session.add(listing)
    session.commit()
    move, _detail = market.buy(session, career, ident=listing.id, use_clause=True)
    return player, move


def test_effective_age_is_the_stored_age_plus_the_careers_closed_seasons(session, world) -> None:  # type: ignore[no-untyped-def]
    career = _career(session, world)
    player = _squad(session, career)[0]
    assert ageing.closed_seasons(session, career) == 0
    assert ageing.effective_age(player, 0) == int(player.age)
    assert ageing.effective_age(player, 3) == int(player.age) + 3
    assert ageing.effective_age(player, -1) == int(player.age), "a negative offset is not a younger player"


def test_the_boundary_retires_a_player_at_forty_and_stops_his_wage(session, world) -> None:  # type: ignore[no-untyped-def]
    career = _career(session, world)
    player, signing = _sign(session, world, career)
    original_age = int(player.age)
    try:
        player.age = ageing.RETIREMENT_AGE - 1
        session.commit()
        season_rounds = int(career_service.season_horizon(session, career)["rounds"])
        bill_before = int(market.wage_bill(session, career, round_index=1)["fee"])
        _fabricate_season(session, career, season_rounds)

        closed = career_service.close_season(session, career)
        assert closed is not None
        retire = session.scalar(
            select(CareerSquadMove).where(
                CareerSquadMove.career_id == career.id,
                CareerSquadMove.player_id == player.id,
                CareerSquadMove.kind == ageing.RETIRE_KIND,
            )
        )
        assert retire is not None, "turning forty at the boundary writes a retire row"
        assert int(retire.round_index) == season_rounds + 1, "the retirement binds from the next season's first round"
        assert int(retire.weekly_wage) == int(signing.weekly_wage) and int(retire.fee) == 0
        assert retirement_row(player, _squad(session, career)) is None, "the overlay drops the retired player"
        youth = list(
            session.scalars(
                select(CareerSquadMove).where(CareerSquadMove.career_id == career.id, CareerSquadMove.kind == "youth")
            ).all()
        )
        assert youth, "the boundary replaces the retiree from the academy's own class"
        assert all(int(row.fee) == 0 and int(row.expiry_round) > season_rounds for row in youth)
        after = _squad(session, career)
        assert all(any(member.id == row.player_id for member in after) for row in youth)
        bill_after = int(market.wage_bill(session, career, round_index=season_rounds + 1)["fee"])
        assert bill_after == bill_before - int(signing.weekly_wage) + sum(int(row.weekly_wage) for row in youth)
        book = career_service.career_view(session, career)["contracts"]
        assert any(item["kind"] == ageing.RETIRE_KIND for item in book["recent"])
        intake_row = next(item for item in book["rows"] if item["player_id"] == youth[0].player_id)
        assert intake_row["kind"] == "youth" and intake_row["renewal"] is not None
        assert book["age_profile"]["retirement_age"] == ageing.RETIREMENT_AGE
        view = career_service.career_view(session, career)
        for row in market.market_view(session, career)["squad"]["players"]:
            stored = session.get(RealPlayer, row["player_id"])
            assert stored is not None and int(row["age"]) == int(stored.age) + 1, "the market squad prints the career-clock age"
        for row in view["academy"].get("trainees", []):
            stored = session.get(RealPlayer, row["player_id"])
            assert stored is not None and int(row["age"]) == int(stored.age) + 1, "the academy prints the same age"
    finally:
        player.age = original_age
        session.commit()


def retirement_row(player: RealPlayer, squad: list[RealPlayer]) -> RealPlayer | None:
    return next((row for row in squad if row.id == player.id), None)


def test_a_retirement_that_would_leave_no_side_is_retained(session, world) -> None:  # type: ignore[no-untyped-def]
    career = _career(session, world)
    squad = _squad(session, career)
    original = {player.id: int(player.age) for player in squad}
    try:
        for player in squad:
            player.age = ageing.RETIREMENT_AGE - 1
        session.commit()
        season_rounds = int(career_service.season_horizon(session, career)["rounds"])
        _fabricate_season(session, career, season_rounds)

        result = ageing.retire_at_boundary(session, career, round_index=season_rounds + 1, closed=1)
        session.commit()
        kept = _squad(session, career)
        assert int(result["squad_after"]) == len(kept) >= 11
        assert sum(1 for player in kept if player.position == "GK") >= 1
        assert result["retained"], "the guard names the oldest candidates it had to keep"
        assert len(result["retired"]) + len(result["retained"]) == len(squad)
    finally:
        for player in squad:
            player.age = original[player.id]
        session.commit()


def test_a_challenge_career_has_no_boundary_to_retire_anyone(session, world) -> None:  # type: ignore[no-untyped-def]
    career = _career(session, world)
    squad = _squad(session, career)
    original = {player.id: int(player.age) for player in squad}
    try:
        career.challenge_window = 2
        for player in squad:
            player.age = ageing.RETIREMENT_AGE - 1
        session.commit()
        _fabricate_season(session, career, 2)

        assert career_service.close_season(session, career) is not None
        retired = session.scalars(
            select(CareerSquadMove).where(CareerSquadMove.career_id == career.id, CareerSquadMove.kind == ageing.RETIRE_KIND)
        ).all()
        assert retired == [], "a challenge window closes one season and no later boundary retires its squad"
    finally:
        for player in squad:
            player.age = original[player.id]
        session.commit()


def test_a_boundary_with_no_retirement_signs_no_youth(session, world) -> None:  # type: ignore[no-untyped-def]
    career = _career(session, world)
    season_rounds = int(career_service.season_horizon(session, career)["rounds"])
    _fabricate_season(session, career, season_rounds)
    assert career_service.close_season(session, career) is not None
    youth = session.scalars(
        select(CareerSquadMove).where(CareerSquadMove.career_id == career.id, CareerSquadMove.kind == "youth")
    ).all()
    assert youth == [], "an intake replaces retirees; with none, the boundary signs nobody"


def test_the_intake_promotes_at_most_four_on_a_free_contract(session, world) -> None:  # type: ignore[no-untyped-def]
    career = _career(session, world)
    season_rounds = int(career_service.season_horizon(session, career)["rounds"])
    position = _squad(session, career)[0].position
    retired = [{"player_name": f"Retired {index}", "position": position} for index in range(6)]

    result = intake.youth_intake(session, career, round_index=season_rounds + 1, season_rounds=season_rounds, retired=retired)
    session.commit()
    assert 1 <= len(result["promoted"]) <= intake.MAX_YOUTH_INTAKE
    for row in result["promoted"]:
        assert row["weekly_wage"] >= 0
        assert row["expiry_round"] == season_rounds + 1 + row["contract_years"] * season_rounds - 1
        assert row["replaces"] == "" or str(row["replaces"]).startswith("Retired")
    moves = session.scalars(
        select(CareerSquadMove).where(CareerSquadMove.career_id == career.id, CareerSquadMove.kind == "youth")
    ).all()
    assert len(moves) == len(result["promoted"]) and all(int(move.fee) == 0 for move in moves)

    empty = intake.youth_intake(session, career, round_index=season_rounds + 1, season_rounds=season_rounds, retired=[])
    assert empty["promoted"] == [] and "nothing to replace" in empty["reason"]
