"""A career's cup run (M13 Phase 8 item 32): the world's bracket, the engine's tie, and the prize.

The claims worth testing are the ones a reader would be misled by if they were false:

* the bracket is the world's own draw — the quarter-final opponent, side and venue come from a stored
  `real_matches` row rather than from a rotation this module invented;
* a tie the career wins advances it along that same bracket, and a tie it loses ends the run;
* a round won pays its prize into `career_budget_awards`, the table the balance already sums, and a
  replay of the same round cannot pay twice;
* a career the world did not enter, a season the world drew no cup for, and a challenge career each say
  so instead of inventing a fixture.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.security import hash_password, new_public_id
from app.models import (
    Career,
    CareerAppearance,
    CareerBudgetAward,
    CareerCupTie,
    CareerGateReceipt,
    CareerUpkeepCharge,
    Competition,
    RealMatch,
    User,
)
from app.services.simulation import career as career_service
from app.services.simulation import carry_over, market
from app.services.simulation import cup as cup_service
from app.services.world import sync_world

OBJECTIVES = [{"kind": "wins", "target": 1, "label": "win once"}]
BUDGET = 2_000_000


@pytest.fixture(scope="module")
def world() -> dict[str, Any]:
    """A cup the world drew for 2026 and a club it put in that cup's quarter-finals."""
    session = SessionLocal()
    assert sync_world(session).ok
    rows = session.execute(
        select(RealMatch, Competition)
        .join(Competition, Competition.id == RealMatch.competition_id)
        .where(Competition.kind == "cup", RealMatch.season == "2026")
        .order_by(RealMatch.competition_id, RealMatch.round_label)
    ).all()
    quarters = [(match, comp) for match, comp in rows if str(match.round_label).startswith("Quarter-final")]
    assert quarters, "the generated world drew no cup quarter-final, so this module has nothing to read"
    match, cup = quarters[0]
    owner = User(
        id=new_public_id("usr"),
        email=f"cup-{new_public_id('x')[:8]}@example.test",
        password_hash=hash_password("cup-service-test"),
        display_name="Cup Owner",
        role="player",
    )
    session.add(owner)
    session.commit()
    data: dict[str, Any] = {
        "owner_id": owner.id,
        "cup_id": cup.id,
        "cup_slug": cup.slug,
        "cup_name": cup.name,
        "club_id": match.home_team_id,
        "opponent_id": match.away_team_id,
    }
    session.close()
    return data


@pytest.fixture()
def session() -> Iterator[Session]:
    value = SessionLocal()
    try:
        yield value
    finally:
        value.rollback()
        value.close()


def _career(session: Session, world: dict[str, Any], **kwargs: Any) -> Career:
    return career_service.create_career(
        session,
        owner_id=world["owner_id"],
        club=career_service.resolve_club(session, world["club_id"]),
        manager_name=kwargs.pop("manager_name", "Cup Manager"),
        philosophy=kwargs.pop("philosophy", "balanced"),
        system_slug=kwargs.pop("system_slug", ""),
        budget=kwargs.pop("budget", BUDGET),
        objectives=kwargs.pop("objectives", OBJECTIVES),
        season=kwargs.pop("season", "2026"),
    )


def _run(session: Session, career: Career, *, cup_slug: str | None = None) -> dict[str, Any]:
    view = cup_service.cup_view(session, career)
    runs = view["runs"]
    if cup_slug is None:
        return runs[0]
    return next(run for run in runs if run["cup_slug"] == cup_slug)


def _forge_tie(session: Session, career: Career, world: dict[str, Any], *, stage_index: int, outcome: str, roster: dict[str, str]) -> CareerCupTie:
    """A played tie, written by hand: the bracket tests do not need the engine to know who won."""
    stage = ("Quarter-final", "Semi-final", "Final")[stage_index - 1]
    tie = CareerCupTie(
        id=new_public_id("ctie"),
        career_id=career.id,
        season_index=1,
        season="2026",
        cup_id=str(world["cup_id"]),
        cup_slug=str(world["cup_slug"]),
        cup_name=str(world["cup_name"]),
        stage=stage,
        stage_index=stage_index,
        round_index=int(career.rounds_played),
        opponent_team_id=roster["opponent_id"],
        opponent_name=roster["opponent_name"],
        opponent_short=roster["opponent_short"],
        venue_name="Forged Ground",
        club_goals=2 if outcome == "W" else 0,
        opponent_goals=0 if outcome == "W" else 1,
        outcome=outcome,
        decided_by="goals",
        world_match_id=None,
        basis="hand-written for the bracket test",
        data_origin="simulation",
        is_demo_data=True,
    )
    session.add(tie)
    session.commit()
    return tie


class TestCupBracket:
    def test_the_view_lists_the_bracket_the_world_drew(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        view = cup_service.cup_view(session, career)
        assert view["available"] is True and view["reason"] is None
        run = _run(session, career, cup_slug=str(world["cup_slug"]))
        assert run["cup_name"] == world["cup_name"]
        assert run["status"] == "live"
        assert run["stage"] == {"index": 1, "label": "Quarter-final", "of": 3}
        assert run["next"] is not None
        assert run["next"]["stage"] == "Quarter-final"
        assert run["next"]["opponent_team_id"] == world["opponent_id"]
        assert run["next"]["side"] == "home"
        assert world["cup_name"] in str(run["next"]["basis"])
        assert run["record"] == {"played": 0, "won": 0, "lost": 0, "goals_for": 0, "goals_against": 0}
        published = cup_service.CUP_FORMULA
        assert "world's own knockout bracket" in published and "penalties" in published

    def test_a_won_quarter_final_points_at_the_semi_final_the_world_drew(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        first = _run(session, career, cup_slug=str(world["cup_slug"]))["next"]
        tie = _forge_tie(
            session,
            career,
            world,
            stage_index=1,
            outcome="W",
            roster={
                "opponent_id": str(first["opponent_team_id"]),
                "opponent_name": str(first["opponent_name"]),
                "opponent_short": "",
            },
        )
        run = _run(session, career, cup_slug=str(world["cup_slug"]))
        assert run["record"]["played"] == 1 and run["record"]["won"] == 1
        assert run["status"] == "live" and run["next"] is not None
        assert run["next"]["stage"] == "Semi-final" and run["next"]["stage_index"] == 2
        # The opponent and the side are the world's own semi-final, read off the bracket rather than guessed:
        # the club's quarter-final feeds one half, and the other club in that half's semi is next.
        rows = cup_service._stage_rows(session, str(world["cup_id"]), "2026")
        quarter = next(row for row in rows["Quarter-final"] if row.home_team_id == world["club_id"])
        half = rows["Quarter-final"].index(quarter) // 2
        semi = rows["Semi-final"][half]
        seeded = cup_service._winner(quarter)
        assert seeded in (semi.home_team_id, semi.away_team_id), "the quarter-final feeds this half of the draw"
        assert run["next"]["opponent_team_id"] in (semi.home_team_id, semi.away_team_id)
        assert run["next"]["opponent_team_id"] != seeded
        assert tie.opponent_team_id != run["next"]["opponent_team_id"]

    def test_a_lost_tie_ends_the_run_and_a_won_final_wins_the_cup(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        first = _run(session, career, cup_slug=str(world["cup_slug"]))["next"]
        _forge_tie(
            session,
            career,
            world,
            stage_index=1,
            outcome="L",
            roster={"opponent_id": str(first["opponent_team_id"]), "opponent_name": str(first["opponent_name"]), "opponent_short": ""},
        )
        run = _run(session, career, cup_slug=str(world["cup_slug"]))
        assert run["status"] == "eliminated" and run["next"] is None
        with pytest.raises(cup_service.CupRefusal) as refused:
            cup_service.play_cup_tie(session, career, cup=str(world["cup_slug"]))
        assert refused.value.code == "cup_run_over"

    def test_three_wins_win_the_cup_and_there_is_nothing_left_to_play(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        for stage in (1, 2, 3):
            run = _run(session, career, cup_slug=str(world["cup_slug"]))
            slot = run["next"]
            assert slot is not None, f"stage {stage} had no tie to play"
            _forge_tie(
                session,
                career,
                world,
                stage_index=stage,
                outcome="W",
                roster={"opponent_id": str(slot["opponent_team_id"]), "opponent_name": str(slot["opponent_name"]), "opponent_short": ""},
            )
        run = _run(session, career, cup_slug=str(world["cup_slug"]))
        assert run["status"] == "won" and run["next"] is None
        assert run["stage"]["index"] == 4 and run["stage"]["label"] == "Final"
        with pytest.raises(cup_service.CupRefusal) as refused:
            cup_service.play_cup_tie(session, career, cup=str(world["cup_slug"]))
        assert refused.value.code == "cup_run_over"


class TestCupPrizes:
    def test_a_won_tie_pays_its_stage_prize_into_the_award_table(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        slot = _run(session, career, cup_slug=str(world["cup_slug"]))["next"]
        tie = _forge_tie(
            session,
            career,
            world,
            stage_index=1,
            outcome="W",
            roster={"opponent_id": str(slot["opponent_team_id"]), "opponent_name": str(slot["opponent_name"]), "opponent_short": ""},
        )
        assert market.budget_position(session, career)["received_cup"] == 0
        award = market.pay_cup_prize(session, career, tie=tie)
        assert award is not None
        assert (award.kind, award.stage, award.amount) == ("cup_prize", f"{world['cup_slug']}:Quarter-final", market.CUP_PRIZE_BY_STAGE[1])
        assert award.amount_units == career.budget_units
        assert "won the" in award.basis and "40,000" in award.basis

        position = market.budget_position(session, career)
        assert position["received_cup"] == award.amount and position["cup_rows"] == 1
        assert position["grant_rows"] == 0 and position["granted"] == 0, "a cup prize is not the board's grant"
        assert position["remaining"] == BUDGET + award.amount
        assert award.budget_after == position["remaining"]

        timeline = market.budget_timeline(session, career, limit=0)
        assert timeline["disagreements"] == 0
        prize_rows = [row for row in timeline["rows"] if row["kind"] == "cup_prize"]
        assert len(prize_rows) == 1 and prize_rows[0]["label"].startswith("cup prize, ")

        ledger = market.market_view(session, career)
        assert ledger["totals"]["cup_prize_rows"] == 1
        assert any(row["kind"] == "cup_prize" and row["cash"] == "in" for row in ledger["moves"])

    def test_the_same_round_cannot_pay_twice(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        slot = _run(session, career, cup_slug=str(world["cup_slug"]))["next"]
        tie = _forge_tie(
            session,
            career,
            world,
            stage_index=1,
            outcome="W",
            roster={"opponent_id": str(slot["opponent_team_id"]), "opponent_name": str(slot["opponent_name"]), "opponent_short": ""},
        )
        assert market.pay_cup_prize(session, career, tie=tie) is not None
        duplicate = CareerBudgetAward(
            id=new_public_id("awd"),
            career_id=career.id,
            season_index=1,
            round_index=0,
            kind="cup_prize",
            stage=f"{world['cup_slug']}:Quarter-final",
            amount=1,
            amount_units=career.budget_units,
            basis="a hand-written second prize for the same round",
            promotion=0,
            budget_after=1,
            data_origin="simulation",
            is_demo_data=True,
        )
        session.add(duplicate)
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()

    def test_the_stage_prizes_are_published_and_add_up(self) -> None:
        assert market.CUP_PRIZE_BY_STAGE == {1: 40_000, 2: 90_000, 3: 220_000}
        assert market.RULES["cup_prize"] == market.CUP_PRIZE_FORMULA
        assert sum(market.CUP_PRIZE_BY_STAGE.values()) == 350_000


class TestCupEntries:
    def test_a_season_the_world_drew_no_cup_for_says_so(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world, season="2099")
        view = cup_service.cup_view(session, career)
        assert view["available"] is False and view["runs"] == []
        assert "2099" in str(view["reason"])
        with pytest.raises(cup_service.CupRefusal) as refused:
            cup_service.play_cup_tie(session, career)
        assert refused.value.code == "no_cup_run"

    def test_a_challenge_career_enters_no_cup(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        career.challenge_slug = "some-authored-run"
        career.challenge_window = 2
        session.commit()
        view = cup_service.cup_view(session, career)
        assert view["available"] is False
        assert "authored constraint" in str(view["reason"])
        with pytest.raises(cup_service.CupRefusal) as refused:
            cup_service.play_cup_tie(session, career)
        assert refused.value.code == "no_cup_run"

    def test_a_retired_career_plays_no_tie(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        career.status = "retired"
        session.commit()
        with pytest.raises(cup_service.CupRefusal) as refused:
            cup_service.play_cup_tie(session, career, cup=str(world["cup_slug"]))
        assert refused.value.code == "career_retired"


class TestCupTie:
    def test_a_played_tie_is_the_engines_result_and_the_brackets_fixture(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        before = _run(session, career, cup_slug=str(world["cup_slug"]))["next"]
        tie, match = cup_service.play_cup_tie(session, career, cup=str(world["cup_slug"]))
        assert tie.match_id == match.id and tie.digest == match.digest
        assert (tie.cup_slug, tie.stage, tie.stage_index) == (world["cup_slug"], "Quarter-final", 1)
        assert tie.opponent_team_id == before["opponent_team_id"] and tie.side == before["side"]
        assert (tie.club_goals, tie.opponent_goals) == (
            match.home_goals if tie.side == "home" else match.away_goals,
            match.away_goals if tie.side == "home" else match.home_goals,
        )
        assert career.rounds_played == 0, "a cup tie is not a league round"

        run = _run(session, career, cup_slug=str(world["cup_slug"]))
        assert run["record"]["played"] == 1
        if tie.outcome == "W":
            assert run["next"] is not None and run["next"]["stage"] == "Semi-final"
            assert run["prizes"]["total"] == market.CUP_PRIZE_BY_STAGE[1]
            assert run["ties"][0]["prize"] is not None
        else:
            assert run["status"] == "eliminated" and run["next"] is None
            assert run["prizes"]["total"] == 0 and run["ties"][0]["prize"] is None

    def test_the_prize_is_paid_at_the_round_the_tie_was_played_after(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        career_service.play_round(session, career)
        tie, _match = cup_service.play_cup_tie(session, career, cup=str(world["cup_slug"]))
        assert tie.round_index == career.rounds_played == 1
        awards = [row for row in session.scalars(select(CareerBudgetAward).where(CareerBudgetAward.career_id == career.id)).all() if row.kind == "cup_prize"]
        if tie.outcome == "W":
            assert len(awards) == 1 and awards[0].round_index == 1
        else:
            assert awards == []

    def test_a_drawn_tie_is_separated_by_the_digest(self) -> None:
        even = cup_service.settle(1, 1, "0000000012345678")
        odd = cup_service.settle(1, 1, "0000000112345678")
        assert even["advanced"] is True and odd["advanced"] is False
        assert even["decided_by"] == "penalties" and "4-3" in even["penalty_note"]
        assert odd["decided_by"] == "penalties" and "3-4" in odd["penalty_note"]
        won = cup_service.settle(2, 0, "0000000112345678")
        assert won == {"advanced": True, "decided_by": "goals", "penalty_note": "", "shootout": ""}
        lost = cup_service.settle(0, 1, "0000000012345678")
        assert lost["advanced"] is False


class TestCupGateAndMinutes:
    """A tie is played on a ground and by an eleven (M13 Phase 9 item 34)."""

    def test_a_home_tie_pays_a_gate_and_leaves_the_elevens_minutes(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        career_service.play_round(session, career)
        league_rows = list(
            session.scalars(
                select(CareerAppearance).where(
                    CareerAppearance.career_id == career.id, CareerAppearance.tie_id.is_(None)
                )
            ).all()
        )
        assert len(league_rows) == 11, "the league round traced its eleven before the tie"
        before_balance = market.budget_position(session, career)["remaining"]

        tie, _match = cup_service.play_cup_tie(session, career, cup=str(world["cup_slug"]))
        assert tie.side == "home" and tie.round_index == career.rounds_played == 1
        gate = session.scalars(
            select(CareerGateReceipt).where(
                CareerGateReceipt.career_id == career.id, CareerGateReceipt.tie_id == tie.id
            )
        ).one()
        assert gate.round_index == 1 and gate.attendance > 0
        assert gate.amount == gate.attendance * gate.ticket_price
        assert "at home" in gate.basis and "form" in gate.basis

        # The tie's trace shares round 1 with the league round's and does not displace it: that sharing is
        # exactly what the one-gate-per-round and one-trace-per-player uniques used to refuse.
        cup_rows = list(
            session.scalars(
                select(CareerAppearance).where(
                    CareerAppearance.career_id == career.id, CareerAppearance.tie_id == tie.id
                )
            ).all()
        )
        assert len(cup_rows) == 11 and {row.minutes for row in cup_rows} == {90}
        assert all(row.round_index == 1 for row in cup_rows)
        assert {row.id for row in cup_rows}.isdisjoint({row.id for row in league_rows})
        assert len(
            list(
                session.scalars(
                    select(CareerAppearance).where(
                        CareerAppearance.career_id == career.id, CareerAppearance.tie_id.is_(None)
                    )
                ).all()
            )
        ) == 11

        run = _run(session, career, cup_slug=str(world["cup_slug"]))
        assert run["ties"][0]["gate"]["amount"] == gate.amount
        assert run["gates"] == {"total": gate.amount, "rows": 1}
        assert run["ties"][0]["gate"]["attendance"] == gate.attendance
        position = market.budget_position(session, career)
        assert position["received_gate_cup"] == gate.amount and position["gate_cup_rows"] == 1
        cup_upkeep = sum(
            int(row.amount)
            for row in session.scalars(
                select(CareerUpkeepCharge).where(CareerUpkeepCharge.tie_id == tie.id)
            ).all()
        )
        assert position["remaining"] - before_balance == (
            run["gates"]["total"] + run["prizes"]["total"] - cup_upkeep
        )
        assert cup_upkeep > 0
        timeline = market.budget_timeline(session, career, limit=0)
        assert timeline["disagreements"] == 0
        assert any(row["kind"] == "cup_gate" for row in timeline["rows"])
        assert any(row["kind"] == "cup_upkeep" for row in timeline["rows"])

        # Cup minutes are load: the carry-over counts them without calling the tie a league round.
        carried = carry_over.carry_over_view(session, career, next_round=int(career.rounds_played) + 1)
        assert carried["rounds_traced"] == 1 and carried["cup_appearances"] == 11
        assert carried["appearances"] == 22
        assert carried["carrying_load"] >= 11

    def test_only_a_home_tie_pays_and_a_final_is_the_competitions(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        slot = _run(session, career, cup_slug=str(world["cup_slug"]))["next"]
        roster = {
            "opponent_id": str(slot["opponent_team_id"]),
            "opponent_name": str(slot["opponent_name"]),
            "opponent_short": "",
        }
        away = _forge_tie(session, career, world, stage_index=1, outcome="W", roster=roster)
        away.side = "away"
        session.commit()
        assert market.pay_cup_gate(session, career, tie=away) is None

        final = _forge_tie(session, career, world, stage_index=3, outcome="W", roster=roster)
        final.side = "home"
        session.commit()
        assert market.pay_cup_gate(session, career, tie=final) is None

    def test_a_tie_cannot_be_paid_two_gates(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        tie, _match = cup_service.play_cup_tie(session, career, cup=str(world["cup_slug"]))
        duplicate = CareerGateReceipt(
            id=new_public_id("gate"),
            career_id=career.id,
            round_index=int(tie.round_index),
            tie_id=tie.id,
            attendance=1,
            ticket_price=1,
            amount=1,
            amount_units=career.budget_units,
            basis="a hand-written second gate for the same tie",
            budget_after=1,
            data_origin="simulation",
            is_demo_data=True,
        )
        session.add(duplicate)
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()


@pytest.fixture(scope="module")
def drawn(world: dict[str, Any]) -> dict[str, Any]:
    """Next season's cup: the world draws its quarter-finals and nothing later (M13 Phase 9 item 35)."""
    session = SessionLocal()
    row = session.execute(
        select(RealMatch, Competition)
        .join(Competition, Competition.id == RealMatch.competition_id)
        .where(
            Competition.kind == "cup",
            RealMatch.season == "2027",
            RealMatch.round_label == "Quarter-final 1",
        )
        .order_by(RealMatch.competition_id)
        .limit(1)
    ).first()
    assert row is not None, "the world drew no 2027 cup quarter-final, so item 35 has nothing to read"
    match, cup = row
    data = {
        **world,
        "season": "2027",
        "cup_id": cup.id,
        "cup_slug": cup.slug,
        "cup_name": cup.name,
        "club_id": match.home_team_id,
        "opponent_id": match.away_team_id,
        "world_match_id": match.id,
    }
    session.close()
    return data


class TestDrawnBracket:
    def test_a_second_season_reads_the_drawn_quarter_final(self, session, drawn) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, drawn, season="2027")
        view = cup_service.cup_view(session, career)
        assert view["available"] is True and view["season"] == "2027"
        run = _run(session, career, cup_slug=str(drawn["cup_slug"]))
        assert run["status"] == "live" and run["next"] is not None
        assert run["next"]["stage"] == "Quarter-final"
        assert run["next"]["world_match_id"] == drawn["world_match_id"]
        row = session.get(RealMatch, drawn["world_match_id"])
        assert row is not None and row.status == "scheduled"
        assert row.home_goals is None and row.away_goals is None, "a drawn tie carries no score"
        assert "drew" in str(run["next"]["basis"])

    def test_a_won_quarter_final_resolves_the_adjacent_tie(self, session, drawn) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, drawn, season="2027")
        slot = _run(session, career, cup_slug=str(drawn["cup_slug"]))["next"]
        _forge_tie(
            session,
            career,
            drawn,
            stage_index=1,
            outcome="W",
            roster={
                "opponent_id": str(slot["opponent_team_id"]),
                "opponent_name": str(slot["opponent_name"]),
                "opponent_short": "",
            },
        )
        first = _run(session, career, cup_slug=str(drawn["cup_slug"]))
        assert first["status"] == "live" and first["next"] is not None
        assert first["next"]["stage"] == "Semi-final" and first["next"]["world_match_id"] is None
        assert "not a drawn row yet" in first["next"]["basis"]
        assert "Quarter-final 1 meets Quarter-final 2" in first["next"]["basis"] or "Quarter-final 3 meets Quarter-final 4" in first["next"]["basis"]

        rows = cup_service._stage_rows(session, str(drawn["cup_id"]), "2027")
        quarter = next(row for row in rows["Quarter-final"] if row.home_team_id == drawn["club_id"])
        half = rows["Quarter-final"].index(quarter) // 2
        adjacent = rows["Quarter-final"][2 * half + (1 - rows["Quarter-final"].index(quarter) % 2)]
        expected, _note = cup_service._drawn_winner(session, adjacent)
        assert first["next"]["opponent_team_id"] == expected
        again = _run(session, career, cup_slug=str(drawn["cup_slug"]))
        assert again["next"]["opponent_team_id"] == expected, "the resolved tie is stable across reads"

    def test_reaching_the_final_names_the_other_halfs_route(self, session, drawn) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, drawn, season="2027")
        for stage in (1, 2):
            slot = _run(session, career, cup_slug=str(drawn["cup_slug"]))["next"]
            assert slot is not None
            _forge_tie(
                session,
                career,
                drawn,
                stage_index=stage,
                outcome="W",
                roster={
                    "opponent_id": str(slot["opponent_team_id"]),
                    "opponent_name": str(slot["opponent_name"]),
                    "opponent_short": "",
                },
            )
        run = _run(session, career, cup_slug=str(drawn["cup_slug"]))
        assert run["next"] is not None and run["next"]["stage"] == "Final"
        assert run["next"]["venue_name"] == "Neutral venue"
        assert "other half of the bracket" in run["next"]["basis"]
        rows = cup_service._stage_rows(session, str(drawn["cup_id"]), "2027")
        quarter = next(row for row in rows["Quarter-final"] if row.home_team_id == drawn["club_id"])
        half = rows["Quarter-final"].index(quarter) // 2
        expected, _note = cup_service._drawn_half_winner(session, session.get(Competition, drawn["cup_id"]), "2027", rows, 1 - half)
        assert run["next"]["opponent_team_id"] == expected
