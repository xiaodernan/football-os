"""M6 §20 carry-over: the trace a played round leaves, and the condition the next round reads.

Four claims carry this module, and each is tested where it is made:

* **A round is recorded, not remembered.** `career_appearances` holds one row per selected player per
  round, it outlives the match report it came from, and it goes when the career goes.
* **The next round reads it.** The same eleven, rebuilt for round 2, comes out with a lower form index
  than the club's stored rows give — and rebuilding it with the trace removed gives a different match,
  which is what makes the number a cause rather than a caption.
* **The published arithmetic is the arithmetic.** The condition a player gets is the figure the printed
  formula produces from the minutes and training loads on file, decay and floor included.
* **A club nobody manages is untouched.** With no trace the form index is the stored-form mean exactly
  as it was before this rule existed, which is why matches stored by other pages still replay.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.security import hash_password, new_public_id
from app.models import Career, CareerAppearance, CareerFixture, RealPlayer, RealTrainingSession, SimulationMatch, Team, User
from app.services.simulation import career as career_service
from app.services.simulation import carry_over
from app.services.simulation.profile import team_profile
from app.services.simulation.service import replay_is_identical
from app.services.simulation.squad import squad_as_of
from app.services.world import sync_world

BUDGET = 2_000_000
LINES = ("condition_index", "players_carrying_load")


@pytest.fixture(scope="module")
def world() -> dict[str, Any]:
    """The weakest club in the generated world and an account to hand it a season to.

    The weakest club is deliberate again (§22's reason holds): a test that a signed or traced player is
    in the eleven is worthless if the fixture could pass with a side nobody selected.
    """
    session = SessionLocal()
    result = sync_world(session)
    assert result.ok, result.errors[:5]
    club = session.scalars(select(Team).where(Team.competition_id.is_not(None)).order_by(Team.overall, Team.slug).limit(1)).one()
    owner = User(
        id=new_public_id("usr"),
        email=f"carry-{club.slug[:8]}@example.test",
        password_hash=hash_password("carry-over-service-test"),
        display_name="Carry Over Owner",
        role="player",
    )
    session.add(owner)
    session.commit()
    data: dict[str, Any] = {"club_id": club.id, "club_slug": club.slug, "owner_id": owner.id}
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
        manager_name="Carry Manager",
        philosophy="balanced",
        system_slug="",
        budget=BUDGET,
        objectives=[{"kind": "wins", "target": 1, "label": "win once"}],
        season="2026",
    )


def _rows(session: Session, career: Career, round_index: int) -> list[CareerAppearance]:
    return list(session.scalars(select(CareerAppearance).where(CareerAppearance.career_id == career.id, CareerAppearance.round_index == round_index).order_by(CareerAppearance.player_name)).all())


def _count(session: Session, career: Career) -> int:
    return int(session.scalar(select(func.count(CareerAppearance.id)).where(CareerAppearance.career_id == career.id)) or 0)


def _erase_round(session: Session, career: Career, round_index: int) -> None:
    """Lose one round's trace, the way an owner who deleted the ledger would.

    The tests that need this are not testing deletion for its own sake: they check that the engine's
    answer to a round whose trace is gone is a refusal, so the arithmetic cannot quietly rewrite history.
    """
    session.execute(delete(CareerAppearance).where(CareerAppearance.career_id == career.id, CareerAppearance.round_index == round_index))
    session.commit()


def _stored_form(session: Session, profile: Any) -> float:
    """The mean this module promises a side with no trace keeps: the eleven's stored form, rescaled."""
    players = list(session.scalars(select(RealPlayer).where(RealPlayer.id.in_([entry[0] for entry in profile.selected]))).all())
    by_id = {player.id: player for player in players}
    values = [max(0.0, min(1.0, (by_id[entry[0]].form - 0.8) / 0.4)) for entry in profile.selected]
    return sum(values) / len(values)


class TestAppearanceLedger:
    """The rows themselves: who played, for how long, and for as long as the career exists."""

    def test_a_played_round_traces_every_player_the_engine_selected(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        fixture, match = career_service.play_round(session, career)
        rows = _rows(session, career, 1)
        lineup = match.report["sides"][fixture.side]["lineup"]
        assert len(rows) == len(lineup) == 11, "one trace per selected player, and the report says who was selected"
        assert sorted(row.player_name for row in rows) == sorted(entry["player"] for entry in lineup)
        assert {row.minutes for row in rows} == {match.minutes}, "the engine models no substitutions, so a selected player plays the fixture"
        assert {row.side for row in rows} == {fixture.side}
        assert all(row.player_id and row.player_slug and row.position and row.band for row in rows)
        assert all(f"round {row.round_index}" in row.note for row in rows), "each row says which round it came from"
        assert {row.opponent_name for row in rows} == {fixture.opponent_name}
        assert all(row.is_demo_data and row.data_origin == "simulation" for row in rows)
        assert _count(session, career) == 11, "a round is traced once"

    def test_the_trace_outlives_the_match_report_it_came_from(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        _fixture, match = career_service.play_round(session, career)
        session.delete(match)
        session.commit()
        assert _count(session, career) == 11, "the load a round put on a squad belongs to the career, not to a report"
        assert len(carry_over.condition_map(session, career.id, round_index=2)) == 11

    def test_deleting_a_career_takes_its_ledger_with_it(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        career_service.play_round(session, career)
        career_id = career.id
        session.delete(career)
        session.commit()
        assert int(session.scalar(select(func.count(CareerAppearance.id)).where(CareerAppearance.career_id == career_id)) or 0) == 0

    def test_playing_the_same_round_twice_does_not_double_the_trace(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        career_service.play_round(session, career)
        rows = carry_over.record_appearances(
            session,
            career,
            round_index=1,
            lineup=[(entry[0], entry[1], entry[2], entry[3], entry[4]) for entry in team_profile(session, career.club_id or "").selected],
            side="home",
            minutes=90,
            opponent_name="anyone",
        )
        assert len(rows) == 11 and _count(session, career) == 11, "the ledger is keyed by round and player, so a re-run writes nothing new"


class TestConditionCarriesIntoTheNextRound:
    """Where the rows reach the engine: the side's form index, and the match that follows from it."""

    def test_a_club_nobody_manages_keeps_its_stored_form(self, session, world) -> None:  # type: ignore[no-untyped-def]
        plain = team_profile(session, world["club_id"])
        assert all(entry.key not in LINES for entry in plain.factors), "no trace, no condition line in the report"
        assert plain.form == pytest.approx(_stored_form(session, plain))
        assert squad_as_of(session, _career(session, world), 1) is None

    def test_the_first_round_of_a_career_is_still_the_clubs_own_side(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        before = team_profile(session, career.club_id or "")
        assert carry_over.condition_map(session, career.id, round_index=1) == {}
        career_service.play_round(session, career)
        assert carry_over.condition_map(session, career.id, round_index=1) == {}, "a round is not tired by the rounds after it"
        assert before.lineup, "the premise the next test turns over: nothing about this club was selected away"

    def test_the_second_round_reads_a_lower_form_off_the_same_eleven(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        plain = team_profile(session, career.club_id or "")
        career_service.play_round(session, career)
        overlay = squad_as_of(session, career, 2)
        assert overlay is not None and overlay.empty, "no transfer, so the squad rows are the club's own"
        assert overlay.carries_load and len(overlay.condition) == 11
        played = team_profile(session, career.club_id or "", squad=overlay)
        assert played.lineup == plain.lineup, "the same eleven is selected: carry-over changes how long they go, not who is picked"
        assert played.form < plain.form, "the eleven that played a round comes into the next one with less in it"
        weighted = [max(0.0, min(1.0, (player.form - 0.8) / 0.4)) * (0.5 + 0.5 * overlay.condition[entry[0]]) for entry, player in zip(played.selected, _eleven(session, played))]
        assert played.form == pytest.approx(sum(weighted) / len(weighted)), "the index is the mean of the eleven's weighted form, and the condition it reads is the one on file"
        lines = {entry.key: entry for entry in played.factors}
        assert all(key in lines for key in LINES)
        assert lines["players_carrying_load"].value == 11
        assert carry_over.CONDITION_FORMULA in lines["condition_index"].formula
        assert carry_over.LOAD_FORMULA in lines["condition_index"].formula
        assert carry_over.FORM_FORMULA in lines["form_index"].formula

    def test_replaying_a_round_rebuilds_the_load_it_started_with(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        career_service.play_round(session, career)
        _fixture, second = career_service.play_round(session, career)
        replay = replay_is_identical(session, second)
        assert replay["possible"] is True and replay["identical"] is True, "round 2's trace is its own history, so it re-derives"
        assert "carry load" in replay["squad"]["applied"]

    def test_a_round_is_decided_by_the_trace_before_it(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        career_service.play_round(session, career)
        _fixture, second = career_service.play_round(session, career)
        _erase_round(session, career, 1)
        after = replay_is_identical(session, second)
        assert after["possible"] is False and "condition" in after["reason"], "erase the trace and the replay refuses rather than blaming the engine for a different fixture"


class TestCarriedArithmetic:
    """The published sentences against the numbers, at the values a reader can reach."""

    def test_load_decays_by_half_for_every_round_in_between(self) -> None:
        rows = [CareerAppearance(round_index=index, player_id="p1", minutes=90) for index in (1, 2, 3, 4)]
        windows = carry_over.load_windows(rows, round_index=5)
        assert windows["p1"]["load"] == pytest.approx(90 + 45 + 22.5)
        assert windows["p1"]["rounds"] == 3 and windows["p1"]["minutes"] == 270
        assert carry_over.load_windows(rows[:1], round_index=5) == {}, "a round outside the window is dropped, not saved up"

    def test_condition_runs_from_full_fresh_at_the_top_to_the_floor_for_an_everpresent_starter(self) -> None:
        assert carry_over.condition_of(0, 0) == carry_over.CONDITION_CEILING
        assert carry_over.condition_of(90, 0) == round(1 - carry_over.FATIGUE_DEPTH * (90 / carry_over.WINDOW_LOAD), 4), "one match of a 157.5-unit window costs a twentieth of condition"
        assert carry_over.condition_of(carry_over.WINDOW_LOAD, 0) == carry_over.CONDITION_FLOOR, "a saturated untrained starter is at 0.55 raw, and the floor is what he keeps"
        assert carry_over.condition_of(carry_over.WINDOW_LOAD, carry_over.TRAINING_RESERVE_LOAD) == 0.70, "a complete reserve pulls a saturated starter off the floor"
        assert carry_over.condition_of(carry_over.WINDOW_LOAD, carry_over.TRAINING_RESERVE_LOAD * 4) == 0.70, "the reserve caps at one figure: extra sessions on file buy nothing past it"

    def test_a_players_own_training_record_gives_some_of_the_load_back(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        career_service.play_round(session, career)
        rows = _rows(session, career, 1)
        player = session.get(RealPlayer, rows[0].player_id)
        assert player is not None
        before = carry_over.condition_map(session, career.id, round_index=2)[player.id]
        session.add(
            RealTrainingSession(
                id=new_public_id("rts"),
                natural_key=f"test:carry-over:{career.id}:{player.id}",
                player_id=player.id,
                team_id=player.team_id,
                player_slug=player.slug,
                player_name=player.name,
                position=player.position,
                season="2026",
                session_date="2026-01-04",
                drill_slug="carry-over-test-drill",
                drill_title="A session written by a test",
                category="test",
                difficulty=5,
                duration_min=60,
                rpe=7,
                load_units=carry_over.TRAINING_RESERVE_LOAD,
                summary="one reserve's worth of load, inserted to check the rule and deleted afterwards",
                data_origin="synthetic",
                is_demo_data=True,
            )
        )
        session.commit()
        try:
            after = carry_over.condition_map(session, career.id, round_index=2)[player.id]
            assert after > before
            assert after - before == pytest.approx(min(carry_over.TRAINING_RESERVE, carry_over.CONDITION_CEILING - before))
            assert carry_over.training_loads(session, [player.id])[player.id] >= carry_over.TRAINING_RESERVE_LOAD
        finally:
            session.execute(delete(RealTrainingSession).where(RealTrainingSession.natural_key == f"test:carry-over:{career.id}:{player.id}"))
            session.commit()

    def test_the_reserve_and_the_window_are_written_into_the_published_sentence(self) -> None:
        assert f"{carry_over.WINDOW_LOAD:g}" in carry_over.CONDITION_FORMULA
        assert f"{carry_over.RECENT_ROUNDS}" in carry_over.LOAD_FORMULA
        assert f"{carry_over.DECAY}" in carry_over.LOAD_FORMULA
        assert str(carry_over.TRAINING_RESERVE_LOAD) in carry_over.RESERVE_FORMULA
        assert carry_over.FORM_WEIGHT in carry_over.FORM_FORMULA
        assert carry_over.CONDITION_FLOOR < carry_over.CONDITION_CEILING


class TestCarryOverView:
    """What the API prints beside a season, since a page cannot show a figure it is not given."""

    def test_the_view_adds_the_ledger_up_and_names_its_own_arithmetic(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        career_service.play_round(session, career)
        career_service.play_round(session, career)
        view = career_service.career_view(session, career)["carry_over"]
        assert view["rounds_played"] == 2 and view["rounds_traced"] == 2 and view["untraced_rounds"] == []
        assert view["appearances"] == 22 and view["players_traced"] >= 11
        assert view["last_traced_round"] == 2 and view["next_round"] == 3
        assert view["carrying_load"] == view["players_traced"], "everyone who played round 2 is still inside the window"
        assert view["mean_condition_of_last_xi"] < 1.0
        assert view["window_rounds"] == carry_over.RECENT_ROUNDS and view["decay_per_round"] == carry_over.DECAY
        assert view["disclaimer"] == carry_over.CARRY_DISCLAIMER
        for entry in view["most_loaded"]:
            assert entry["condition"] == carry_over.condition_of(entry["load_units"], entry["training_load_units"])
            assert entry["load_units"] > 0
        assert sum(row["minutes"] for row in view["rows"]) == 22 * 90
        assert view["load_formula"] == carry_over.LOAD_FORMULA and view["condition_formula"] == carry_over.CONDITION_FORMULA

    def test_a_round_that_left_no_trace_is_reported_as_a_hole(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        career_service.play_round(session, career)
        career_service.play_round(session, career)
        _erase_round(session, career, 1)
        view = career_service.career_view(session, career)["carry_over"]
        assert view["untraced_rounds"] == [1] and view["rounds_traced"] == 1
        assert "1 played round" in view["note"] and "measured without them" in view["note"]

    def test_the_limitation_the_page_prints_covers_what_does_not_carry(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        limits = career_service.limitations()
        assert "carry_over" in limits
        text = limits["carry_over"]
        assert "career_appearances" in text and "form index" in text and "growth" in text
        assert "no trace" in text, "the sentence says where the rule stops as well as where it starts"


def _eleven(session: Session, profile: Any) -> list[RealPlayer]:
    rows = list(session.scalars(select(RealPlayer).where(RealPlayer.id.in_([entry[0] for entry in profile.selected]))).all())
    by_id = {player.id: player for player in rows}
    return [by_id[entry[0]] for entry in profile.selected]


def test_a_career_fixture_and_its_trace_agree_on_the_round(session, world) -> None:  # type: ignore[no-untyped-def]
    career = _career(session, world)
    fixture, _match = career_service.play_round(session, career)
    assert fixture.round_index == 1
    assert {row.round_index for row in _rows(session, career, 1)} == {fixture.round_index}
    assert session.scalar(select(func.count(CareerFixture.id)).where(CareerFixture.career_id == career.id)) == 1
