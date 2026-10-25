"""M6 Career Mode, the service layer: a rotation, an engine call, and sums of stored rows (spec §20).

The claims worth testing here are the ones a reader would be misled by if they were false:

* the career does not have its own match model — every round is decided by `possession-block-v1` and
  lands in `sim_matches` with its own digest;
* the fixture list is a *rotation* anyone can reproduce, and the seed of a round comes from the career
  and the round number alone;
* the record, the table and the objective verdicts are sums of `career_fixtures`, and the copied
  scores are re-checked against the stored match when it is still there.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.security import hash_password, new_public_id
from app.models import CAREER_PHLOSOPHIES, OBJECTIVE_FORMULA, OBJECTIVE_KINDS, Career, SimulationMatch, Team, User
from app.services.simulation import career as career_service
from app.services.world import sync_world
from app.services.world.names import slugify

OBJECTIVES = [{"kind": "wins", "target": 1, "label": "win once"}]


@pytest.fixture(scope="module")
def world() -> dict[str, Any]:
    session = SessionLocal()
    result = sync_world(session)
    assert result.ok, result.errors[:5]
    club = session.scalars(select(Team).order_by(Team.slug).limit(1)).one()
    opponents = list(session.scalars(select(Team).where(Team.competition_id == club.competition_id, Team.id != club.id).order_by(Team.slug)).all())
    owner = User(
        id=new_public_id("usr"),
        email=f"career-{club.slug[:8]}@example.test",
        password_hash=hash_password("career-service-test"),
        display_name="Career Owner",
        role="player",
    )
    session.add(owner)
    session.commit()
    data: dict[str, Any] = {"club_id": club.id, "club_name": club.name, "opponents": [team.slug for team in opponents], "owner_id": owner.id}
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
        manager_name=kwargs.pop("manager_name", "Test Manager"),
        philosophy=kwargs.pop("philosophy", CAREER_PHLOSOPHIES[0]),
        system_slug=kwargs.pop("system_slug", ""),
        budget=kwargs.pop("budget", 1_000_000),
        objectives=kwargs.pop("objectives", OBJECTIVES),
        season="2026",
    )


class TestOpening:
    def test_a_career_borrows_its_competition_from_the_club_row(self, session, world) -> None:  # type: ignore[no-untyped-def]
        club = career_service.resolve_club(session, world["club_id"])
        career = _career(session, world)
        assert career.competition_id == club.competition_id
        assert career.competition_name and career.club_name == club.name
        assert career.rounds_played == 0 and career.status == "active"
        assert career.data_origin == "simulation" and career.is_demo_data is True

    def test_the_slug_survives_a_second_career_with_the_same_manager(self, session, world) -> None:  # type: ignore[no-untyped-def]
        first = _career(session, world)
        second = _career(session, world)
        assert first.slug != second.slug
        base = slugify(f"Test Manager-{world['club_name'][:4]}")
        assert first.slug.startswith(base[:12]) and second.slug.startswith(base[:12]), f"two careers must share the 12-char prefix {base[:12]!r}, got {first.slug!r} and {second.slug!r}"


class TestRotation:
    def test_the_first_cycle_meets_every_club_once_at_home(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        career.rounds_played = 0
        plan_first = career_service.next_fixture_plan(session, career)
        assert plan_first["available"] is True and plan_first["side"] == "home"
        assert plan_first["opponent_name"] == session.scalars(select(Team).where(Team.slug == world["opponents"][0])).one().name
        sequence: list[tuple[str, str]] = []
        for round_index in range(1, len(world["opponents"]) + 1):
            career.rounds_played = round_index - 1
            plan = career_service.next_fixture_plan(session, career)
            sequence.append((plan["opponent_name"], plan["side"]))
        assert len({name for name, _ in sequence}) == len(world["opponents"]), "the first cycle must meet each club exactly once"
        assert {side for _, side in sequence} == {"home"}

    def test_the_second_cycle_is_the_same_order_away(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        size = len(world["opponents"])
        first = [career_service.next_fixture_plan(session, _at(career, index))["opponent_name"] for index in range(1, size + 1)]
        second_pairs = [(plan["opponent_name"], plan["side"]) for plan in (career_service.next_fixture_plan(session, _at(career, size + index)) for index in range(1, size + 1))]
        assert [name for name, _ in second_pairs] == first, "the rotation repeats its order, it does not reshuffle"
        assert {side for _, side in second_pairs} == {"away"}

    def test_a_round_seed_comes_from_the_career_and_the_round_only(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        plan = career_service.next_fixture_plan(session, career)
        again = career_service.next_fixture_plan(session, career)
        assert plan["seed"] == again["seed"] == career_service._digest_seed(career.id, 1)
        later = career_service.next_fixture_plan(session, _at(career, 2))
        assert later["seed"] != plan["seed"]

    def test_a_club_with_no_competition_is_refused_in_words(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        career.competition_id = None
        plan = career_service.next_fixture_plan(session, career)
        assert plan["available"] is False and "competition" in plan["reason"]


def _at(career: Career, round_index: int) -> Career:
    career.rounds_played = round_index - 1
    return career


class TestPlaying:
    def test_a_round_is_decided_by_the_engine_and_stored_twice(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        fixture, match = career_service.play_round(session, career)
        assert fixture.round_index == 1 and career.rounds_played == 1
        assert match.owner_id == career.owner_id and match.digest == fixture.digest
        assert match.model_version == fixture.model_version and match.seed == fixture.seed
        home, away = (match.home_goals, match.away_goals) if fixture.side == "home" else (match.away_goals, match.home_goals)
        assert (fixture.club_goals, fixture.opponent_goals) == (home, away)
        assert fixture.outcome == "W" if fixture.club_goals > fixture.opponent_goals else "D" if fixture.club_goals == fixture.opponent_goals else "L"
        assert fixture.points == career_service.POINTS_FOR[fixture.outcome]
        stored = session.get(SimulationMatch, fixture.match_id)
        assert stored is not None and len(stored.report["blocks"]) == 15

    def test_three_rounds_leave_three_rows_and_a_record_that_adds_up(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        for _ in range(3):
            career_service.play_round(session, career)
        rows = career_service.fixtures_of(session, career)
        record = career_service.record_of(rows)
        assert [row.round_index for row in rows] == [1, 2, 3]
        assert record["played"] == 3 == record["won"] + record["drawn"] + record["lost"]
        assert record["goal_difference"] == record["goals_for"] - record["goals_against"]
        assert record["points"] == 3 * record["won"] + record["drawn"]
        assert record["points_formula"].startswith("sum(career_fixtures.points")
        assert len(record["form"]) <= 5

    def test_a_retired_career_refuses_to_play(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        career.status = "retired"
        with pytest.raises(ValueError, match="retired"):
            career_service.play_round(session, career)


class TestJudging:
    def test_objectives_are_compared_with_the_sums_and_say_how(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        career.objectives = [{"kind": kind, "target": 0, "label": kind} for kind in OBJECTIVE_KINDS]
        verdicts = career_service.objectives_of(career, career_service.record_of(career_service.fixtures_of(session, career)))
        assert {item["kind"] for item in verdicts} == set(OBJECTIVE_KINDS)
        assert all(item["met"] and item["formula"] for item in verdicts), "a target of zero is met by definition"
        assert all(item["formula"] in OBJECTIVE_FORMULA.values() for item in verdicts), "the printed formula is the one the code uses"

    def test_a_target_no_row_meets_is_reported_as_unmet_with_its_formula(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        career.objectives = [{"kind": "wins", "target": 5, "label": "five wins"}]
        verdict = career_service.objectives_of(career, career_service.record_of(career_service.fixtures_of(session, career)))[0]
        assert verdict["met"] is False and verdict["actual"] == 0 and verdict["target"] == 5
        assert verdict["formula"] == "count of career_fixtures where outcome = W"

    def test_the_table_touches_two_clubs_per_fixture_and_puts_the_career_club_in_it(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        for _ in range(4):
            career_service.play_round(session, career)
        rows = career_service.fixtures_of(session, career)
        table = career_service.mini_table(rows, career)
        assert sum(entry["played"] for entry in table) == 2 * len(rows)
        mine = next(entry for entry in table if entry["is_career_club"])
        assert mine["name"] == career.club_name and mine["played"] == len(rows)
        record = career_service.record_of(rows)
        assert (mine["points"], mine["goal_difference"]) == (record["points"], record["goal_difference"])
        assert [entry["position"] for entry in table] == list(range(1, len(table) + 1))
        assert all(table[i - 1]["points"] >= table[i]["points"] for i in range(1, len(table))), "the table is ordered by the points it prints"

    def test_the_view_carries_the_labels_a_page_cannot_forget(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        career_service.play_round(session, career)
        view = career_service.career_view(session, career)
        assert view["is_demo_data"] is True and view["data_origin"] == "simulation"
        assert "fiction" in view["disclaimer"]
        assert set(view["limitations"]) == {"budget", "wages", "carry_over", "ledger", "scouting", "philosophy", "table", "objectives"}
        assert "re-checked" in view["consistency"]
        fixture = view["fixtures"][0]
        assert fixture["match_path"] == f"/simulate/{fixture['match_slug']}"
        assert fixture["opponent_path"].startswith("/team/") and view["career"]["club_path"].startswith("/team/")
        # The affordability block is the same arithmetic the transfers page prints, read-only.
        aff = view["affordability"]
        assert aff["formula"] and aff["units"] == career.budget_units
        assert aff["remaining"] == view["career"]["budget"], "a career with no move and no wage row has spent nothing"
        assert aff["weekly_wage_bill"] == 0 and aff["wage_runway_rounds"] is None
        assert aff["signing"]["price"] == 0 and aff["signing"]["fee_affordable"] is True

    def test_a_deleted_match_report_leaves_the_career_readable(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        fixture, match = career_service.play_round(session, career)
        session.delete(session.get(SimulationMatch, match.id))
        session.commit()
        rows = career_service.fixtures_of(session, career)
        view = career_service.career_view(session, career)
        assert rows[0].club_goals == view["record"]["goals_for"], "the copy on the row is what the sum reports"
        assert "no longer stored" in view["consistency"], view["consistency"]


class TestDevelopment:
    def test_a_fresh_career_projected_no_development(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        view = career_service.career_view(session, career)
        dev = view["development"]
        assert dev["players_developed"] == 0
        assert dev["total_minutes"] == 0
        assert dev["top_developed"] == []
        assert "fixture-minutes" in dev["note"]
        assert dev["tau"] == career_service.DEVELOPMENT_TAU and dev["rate"] == career_service.DEVELOPMENT_RATE

    def test_played_rounds_project_development_from_minutes(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        for _ in range(3):
            career_service.play_round(session, career)
        view = career_service.career_view(session, career)
        dev = view["development"]
        assert dev["players_developed"] > 0, "a played career traces appearances the projection can read"
        assert dev["total_minutes"] > 0
        for entry in dev["top_developed"]:
            assert "effective_minutes" in entry and "training_units" in entry
            assert entry["effective_minutes"] >= entry["minutes"], "training load never subtracts from match minutes"
            for attr in entry["before"]:
                assert entry["after"][attr] - entry["before"][attr] == entry["delta"][attr], "delta is always after minus before"
                assert entry["after"][attr] >= entry["before"][attr], "development never lowers an attribute"
                assert entry["after"][attr] <= max(entry["before"][attr], entry["potential"]), "development never crosses potential from below, and leaves an attribute already above it untouched"
        assert "stored" in dev["note"], "the projection is read-only and says so"
        assert dev["development_formula"].startswith("developed(value, potential, minutes)")
