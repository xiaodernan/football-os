"""M6 Career Mode, the service layer: the generated calendar, an engine call, and sums of stored rows (spec §20).

The claims worth testing here are the ones a reader would be misled by if they were false:

* the career does not have its own match model — every round is decided by `possession-block-v1` and
  lands in `sim_matches` with its own digest;
* the fixture list is the club's own generated calendar, and the seed of a round comes from the career
  and the round number alone;
* the record, the table and the objective verdicts are sums of `career_fixtures`, and the copied
  scores are re-checked against the stored match when it is still there.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.security import hash_password, new_public_id
from app.models import (
    CAREER_PHLOSOPHIES,
    OBJECTIVE_FORMULA,
    OBJECTIVE_KINDS,
    Career,
    CareerFixture,
    CareerSeason,
    Competition,
    SimulationMatch,
    Team,
    User,
)
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


class TestCalendar:
    def test_every_round_is_the_clubs_own_generated_fixture(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        bounds = career_service.season_bounds(session, career)
        calendar = career_service.calendar_fixtures(session, career, bounds=bounds)
        assert calendar, "the world drew this club no fixtures, so there is no calendar to follow"
        for position, row in enumerate(calendar, start=1):
            plan = career_service.next_fixture_plan(session, _at(career, position), bounds=bounds)
            home = row.home_team_id == career.club_id
            opponent_id = row.away_team_id if home else row.home_team_id
            opponent = session.get(Team, opponent_id)
            assert plan["available"] is True and plan["source"] == "world_calendar"
            assert plan["side"] == ("home" if home else "away") and plan["opponent_team_id"] == opponent_id and plan["opponent_name"] == opponent.name
            assert plan["match_slug"] == row.slug and plan["round_label"] == row.round_label and plan["venue_name"] == row.venue_name
            assert plan["round_in_season"] == position and plan["season_index"] == 1
            assert plan["calendar"] == {"season": bounds["season"], "position": position, "of": len(calendar)}

    def test_the_calendar_meets_every_club_once_at_home_and_once_away(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        bounds = career_service.season_bounds(session, career)
        size = len(career_service.calendar_fixtures(session, career, bounds=bounds))
        pairs = [(plan["opponent_team_id"], plan["side"]) for plan in (career_service.next_fixture_plan(session, _at(career, index), bounds=bounds) for index in range(1, size + 1))]
        assert len(pairs) == 2 * len(world["opponents"]), "a double round-robin has two fixtures per opponent"
        for opponent in {team_id for team_id, _side in pairs}:
            assert sorted(side for team_id, side in pairs if team_id == opponent) == ["away", "home"], "each opponent is met once at home and once away"
        assert {side for _team, side in pairs} == {"home", "away"}, "the club itself travels in its own calendar"

    def test_a_round_after_the_generated_calendar_continues_on_the_careers_rotation(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        bounds = career_service.season_bounds(session, career)
        size = len(career_service.calendar_fixtures(session, career, bounds=bounds))
        plan = career_service.next_fixture_plan(session, _at(career, size + 1), bounds=bounds)
        assert plan["available"] is True and plan["source"] == "career_rotation"
        assert plan["cycle"] == 1 and plan["of"] == len(world["opponents"]) and plan["round_in_season"] == size + 1
        assert f"holds {size} fixtures" in plan["basis"], "the fallback names the calendar it outlived"

    def test_a_scheduled_opening_round_is_still_the_worlds_calendar(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        career.season = "2027"
        bounds = career_service.season_bounds(session, career)
        calendar = career_service.calendar_fixtures(session, career, bounds=bounds)
        assert len(calendar) == 1 and calendar[0].status == "scheduled", "the world publishes one unplayed opening round for 2027"
        plan = career_service.next_fixture_plan(session, career, bounds=bounds)
        assert plan["source"] == "world_calendar" and plan["match_slug"] == calendar[0].slug
        beyond = career_service.next_fixture_plan(session, career, round_index=2, bounds=bounds)
        assert beyond["source"] == "career_rotation", "one drawn round is a calendar of one, not a season"

    def test_a_season_the_world_never_drew_keeps_the_careers_rotation(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        career.season = "2031"
        bounds = career_service.season_bounds(session, career)
        plan = career_service.next_fixture_plan(session, career, bounds=bounds)
        assert plan["available"] is True and plan["source"] == "career_rotation"
        assert "no 2031 calendar" in plan["basis"]
        assert plan["opponent_name"] == session.scalars(select(Team).where(Team.slug == world["opponents"][0])).one().name
        assert plan["side"] == "home" and plan["cycle"] == 1

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
        assert set(view["limitations"]) == {"budget", "wages", "carry_over", "projections", "ledger", "scouting", "philosophy", "table", "objectives"}
        assert "read-only" in view["limitations"]["projections"] and "contracts" in view["limitations"]["projections"]
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
        assert aff["timeline"]["entries"] == 0 and aff["timeline"]["disagreements"] == 0
        assert aff["timeline"]["opening_balance"] == aff["timeline"]["closing_balance"] == aff["remaining"]
        # The board projection is wired and reads the same record the page prints.
        assert view["board"]["played"] == 1 and view["board"]["season_rounds"] > 0
        assert view["board"]["points_per_round"] == round(view["record"]["points"] / 1, 3)
        # A career that has made no deal has an empty contract book, not a missing one.
        assert view["contracts"]["deals"] == 0 and view["contracts"]["rows"] == []
        assert view["contracts"]["age_profile"]["players"] > 0 and view["contracts"]["age_profile"]["mean"] > 0
        # The position depth covers the whole squad: it sums to the same player count the age profile walked.
        assert sum(row["players"] for row in view["contracts"]["positions"]) == view["contracts"]["age_profile"]["players"]
        # The signing window is on the career payload too, so the page does not need `/market` for it.
        assert view["window"]["round"] == 2 and view["window"]["state"] in ("open", "closed")
        # Two code paths, one figure: the contract book's wage total and the affordability bill are the same held deals.
        assert view["contracts"]["total_weekly_wage"] == view["affordability"]["weekly_wage_bill"]
        # The next fixture's plan is on the view itself (so the endpoint does not compute it again), and the
        # brief is wired to the same round.
        assert view["next_fixture"]["available"] is True and view["next_fixture"]["round_index"] == 2
        assert view["next_fixture_brief"]["available"] is True and view["next_fixture_brief"]["round_index"] == 2
        assert view["highlights"]["available"] is True and view["highlights"]["played"] == 1

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


class TestBoard:
    def test_a_fresh_career_projects_nothing_and_names_its_horizon(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        board = career_service.board_view(session, career, [], career_service.record_of([]))
        assert board["played"] == 0 and board["projected"] == {}
        assert board["on_track"] is None and board["points_per_round"] is None
        assert board["season_rounds"] == 2 * len(world["opponents"]), "an open career's horizon is a double round-robin"
        assert "round-robin" in board["season_source"]
        assert board["formula"].startswith("projected = round(actual ÷ played × season_rounds)")

    def test_the_projection_is_the_record_at_the_seasons_pace(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        for _ in range(3):
            career_service.play_round(session, career)
        rows = career_service.fixtures_of(session, career)
        record = career_service.record_of(rows)
        board = career_service.board_view(session, career, rows, record)
        rounds = 2 * len(world["opponents"])
        assert board["season_rounds"] == rounds and board["played"] == 3
        assert board["projected"]["points"] == round(record["points"] / 3 * rounds)
        assert board["projected"]["wins"] == round(record["won"] / 3 * rounds)
        assert board["projected"]["goal_difference"] == round(record["goal_difference"] / 3 * rounds)
        assert board["points_per_round"] == round(record["points"] / 3, 3)
        verdict = next(item for item in board["objectives"] if item["kind"] == "wins")
        assert verdict["projected"] == board["projected"]["wins"]
        assert verdict["on_pace"] == (verdict["projected"] >= verdict["target"])
        assert board["on_track"] == verdict["on_pace"]

    def test_a_challenge_window_is_the_horizon_when_it_has_one(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        career.challenge_window = 5
        session.commit()
        board = career_service.board_view(session, career, [], career_service.record_of([]))
        assert board["season_rounds"] == 5 and "window" in board["season_source"]


class TestHeadToHead:
    def test_an_unseen_opponent_reads_as_zero_not_as_broken(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        view = career_service.head_to_head(session, career, "wtem_nobody")
        assert view["available"] is True and view["played"] == 0
        assert view["goals_for"] == view["goals_against"] == 0 and view["meetings"] == []
        assert "not met" in view["note"]

    def test_a_met_opponent_sums_only_this_careers_fixtures(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        for _ in range(3):
            career_service.play_round(session, career)
        rows = career_service.fixtures_of(session, career)
        opponent_id = rows[0].opponent_team_id
        met = [row for row in rows if row.opponent_team_id == opponent_id]
        view = career_service.head_to_head(session, career, opponent_id)
        assert view["played"] == len(met)
        assert view["won"] == sum(1 for row in met if row.outcome == "W")
        assert view["drawn"] == sum(1 for row in met if row.outcome == "D")
        assert view["lost"] == sum(1 for row in met if row.outcome == "L")
        assert view["goals_for"] == sum(row.club_goals for row in met)
        assert view["goals_against"] == sum(row.opponent_goals for row in met)
        assert view["points"] == 3 * view["won"] + view["drawn"]
        assert len(view["meetings"]) == min(5, len(met))

    def test_the_view_carries_head_to_head_for_the_next_opponent(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        for _ in range(3):
            career_service.play_round(session, career)
        view = career_service.career_view(session, career)
        assert "head_to_head" in view and view["head_to_head"]["available"] is True
        assert view["head_to_head"]["played"] == 0, "the fourth round of the calendar meets an opponent this career has not played"


class TestNextFixtureBrief:
    def test_the_brief_compares_the_engines_own_measurements(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        brief = career_service.next_fixture_brief(session, career)
        assert brief["available"] is True and brief["round_index"] == 1
        bands = ("attack", "midfield", "defence", "keeper", "press")
        for band in bands:
            assert brief["delta"][band] == round(brief["career"]["bands"][band] - brief["opponent"]["bands"][band], 3)
        assert all(brief["delta"][band] > 0 for band in brief["stronger_bands"])
        assert all(brief["delta"][band] < 0 for band in brief["weaker_bands"])
        assert set(brief["stronger_bands"]) | set(brief["weaker_bands"]) <= set(bands)
        assert brief["career"]["bands"] and brief["opponent"]["bands"]
        assert "comparison" in brief["note"] and brief["formula"].startswith("bands are the engine's own band indices")


class TestReadEfficiency:
    def test_the_career_view_reads_appearances_and_training_once(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        for _ in range(2):
            career_service.play_round(session, career)
        statements: list[str] = []
        engine = session.get_bind()

        def before(conn: object, cursor: object, statement: str, params: object, context: object, executemany: bool) -> None:  # type: ignore[no-untyped-def]
            statements.append(statement.lower())

        event.listen(engine, "before_cursor_execute", before)
        try:
            career_service.career_view(session, career)
        finally:
            event.remove(engine, "before_cursor_execute", before)
        appearance_reads = [s for s in statements if "from career_appearances" in s and s.lstrip().startswith("select")]
        training_reads = [s for s in statements if "from real_training_sessions" in s and s.lstrip().startswith("select")]
        # One read each: the shared fetch this view hands to carry_over, development, ledger and the
        # next-fixture brief (which needs the career side's condition for its profile). Before the dedup
        # it was five reads of appearances and three of training.
        assert len(appearance_reads) == 1, f"career_appearances read {len(appearance_reads)} times"
        assert len(training_reads) == 1, f"real_training_sessions read {len(training_reads)} times"

    def test_the_fixtures_loop_batches_the_opponent_slugs_instead_of_one_query_per_round(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        for _ in range(3):
            career_service.play_round(session, career)
        statements: list[str] = []
        engine = session.get_bind()

        def before(conn: object, cursor: object, statement: str, params: object, context: object, executemany: bool) -> None:  # type: ignore[no-untyped-def]
            statements.append(statement.lower())

        event.listen(engine, "before_cursor_execute", before)
        try:
            view = career_service.career_view(session, career)
        finally:
            event.remove(engine, "before_cursor_execute", before)
        assert len(view["fixtures"]) == 3
        normalized = [" ".join(statement.split()) for statement in statements]
        # `_team_slug`'s query is `select teams.slug from teams where teams.id = ?`; only the club's own
        # path still uses it, and the three opponents are resolved in one `where teams.id in (...)` batch.
        single_slug_reads = [s for s in normalized if "select teams.slug from teams" in s and "teams.id in" not in s]
        assert len(single_slug_reads) <= 1, f"opponent slugs resolved one round at a time: {len(single_slug_reads)} per-id reads"
        assert any("teams.id in" in s for s in normalized), "the batch opponent-slug lookup did not run"

    def test_the_consistency_check_batches_the_stored_matches(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        for _ in range(3):
            career_service.play_round(session, career)
        statements: list[str] = []
        engine = session.get_bind()

        def before(conn: object, cursor: object, statement: str, params: object, context: object, executemany: bool) -> None:  # type: ignore[no-untyped-def]
            statements.append(statement.lower())

        event.listen(engine, "before_cursor_execute", before)
        try:
            career_service.career_view(session, career)
        finally:
            event.remove(engine, "before_cursor_execute", before)
        normalized = [" ".join(statement.split()) for statement in statements]
        # `session.get(SimulationMatch, ...)` issues `... from sim_matches where sim_matches.id = ?`; the
        # batched check uses `sim_matches.id in (...)`, so no per-fixture match read should remain.
        per_id = [s for s in normalized if "from sim_matches" in s and "sim_matches.id in" not in s and "sim_matches.id =" in s]
        assert per_id == [], f"the consistency check read sim_matches one row at a time: {len(per_id)} per-id reads"

    def test_the_view_reads_the_fixture_list_once(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        for _ in range(3):
            career_service.play_round(session, career)
        statements: list[str] = []
        engine = session.get_bind()

        def before(conn: object, cursor: object, statement: str, params: object, context: object, executemany: bool) -> None:  # type: ignore[no-untyped-def]
            statements.append(statement.lower())

        event.listen(engine, "before_cursor_execute", before)
        try:
            career_service.career_view(session, career)
        finally:
            event.remove(engine, "before_cursor_execute", before)
        normalized = [" ".join(statement.split()) for statement in statements]
        fixture_reads = [s for s in normalized if "from career_fixtures" in s and s.lstrip().startswith("select")]
        assert len(fixture_reads) == 1, f"career_fixtures read {len(fixture_reads)} times; head_to_head should reuse the view's list"

    def test_the_list_summary_skips_the_heavy_blocks(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        career_service.play_round(session, career)
        statements: list[str] = []
        engine = session.get_bind()

        def before(conn: object, cursor: object, statement: str, params: object, context: object, executemany: bool) -> None:  # type: ignore[no-untyped-def]
            statements.append(statement.lower())

        event.listen(engine, "before_cursor_execute", before)
        try:
            summary = career_service.career_summary(session, career)
        finally:
            event.remove(engine, "before_cursor_execute", before)
        normalized = [" ".join(statement.split()) for statement in statements]
        # A list row needs the brief, the record and the objectives — not the projection blocks' tables.
        assert not any("from career_appearances" in s for s in normalized), "the list summary read the appearance table"
        assert not any("from real_training_sessions" in s for s in normalized), "the list summary read the training table"
        assert summary["record"]["played"] == 1 and summary["career"]["slug"] == career.slug
        assert isinstance(summary["objectives"], list) and summary["objectives"]

    def test_the_season_horizon_is_computed_once(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        career_service.play_round(session, career)
        statements: list[str] = []
        engine = session.get_bind()

        def before(conn: object, cursor: object, statement: str, params: object, context: object, executemany: bool) -> None:  # type: ignore[no-untyped-def]
            statements.append(statement.lower())

        event.listen(engine, "before_cursor_execute", before)
        try:
            career_service.career_view(session, career)
        finally:
            event.remove(engine, "before_cursor_execute", before)
        normalized = [" ".join(statement.split()) for statement in statements]
        # The board, contract book and window share one horizon now; the other reads are the fixture
        # fallback and the pyramid edge `seasons_view` asks the world's own boundary about. Match the WHERE
        # predicate, not the column list (a full-row select also names competition_id).
        club_reads = [s for s in normalized if "where teams.competition_id =" in s]
        assert len(club_reads) <= 3, f"the competition's clubs were read {len(club_reads)} times (horizon + rotation fallback + pyramid edge is 3)"


class TestSeasonHighlights:
    def test_a_fresh_career_has_no_highlights_to_report(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        highlights = career_service.season_highlights(career_service.fixtures_of(session, career), career)
        assert highlights["available"] is False and "no played round" in highlights["reason"]
        assert highlights["formula"].startswith("margins are club_goals")

    def test_the_highlights_are_read_off_the_fixtures_and_split_by_side(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        for _ in range(3):
            career_service.play_round(session, career)
        rows = career_service.fixtures_of(session, career)
        highlights = career_service.season_highlights(rows, career)
        record = career_service.record_of(rows)
        assert highlights["available"] is True and highlights["played"] == 3
        assert highlights["home"]["played"] + highlights["away"]["played"] == 3
        assert highlights["home"]["points"] + highlights["away"]["points"] == record["points"]
        assert highlights["clean_sheets"] == sum(1 for row in rows if int(row.opponent_goals) == 0)
        assert highlights["failed_to_score"] == sum(1 for row in rows if int(row.club_goals) == 0)
        margins = [int(row.club_goals) - int(row.opponent_goals) for row in rows]
        if highlights["biggest_win"] is not None:
            best = highlights["biggest_win"]
            assert best["club_goals"] - best["opponent_goals"] == max(margins) > 0
        if highlights["worst_loss"] is not None:
            worst = highlights["worst_loss"]
            assert worst["club_goals"] - worst["opponent_goals"] == min(margins) < 0
        assert 0 <= highlights["longest_winning_run"] <= highlights["longest_unbeaten_run"] <= 3


def _count_selects(session: Session, fn) -> int:  # type: ignore[no-untyped-def]
    """How many SELECTs `fn` issues, counted on the session's own bind."""
    statements: list[str] = []
    engine = session.get_bind()

    def before(conn: object, cursor: object, statement: str, params: object, context: object, executemany: bool) -> None:  # type: ignore[no-untyped-def]
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", before)
    try:
        fn()
    finally:
        event.remove(engine, "before_cursor_execute", before)
    return sum(1 for statement in statements if statement.lstrip().lower().startswith("select"))


class TestDeterminism:
    def test_reading_the_view_twice_gives_the_same_json(self, session, world) -> None:  # type: ignore[no-untyped-def]
        import json

        career = _career(session, world)
        career_service.play_round(session, career)
        first = json.dumps(career_service.career_view(session, career), sort_keys=True, default=str)
        second = json.dumps(career_service.career_view(session, career), sort_keys=True, default=str)
        assert first == second, "a view that changes between two reads is inventing state"

    def test_the_query_count_does_not_grow_with_the_season(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        for _ in range(2):
            career_service.play_round(session, career)
        early = _count_selects(session, lambda: career_service.career_view(session, career))
        for _ in range(2):
            career_service.play_round(session, career)
        later = _count_selects(session, lambda: career_service.career_view(session, career))
        assert later == early, f"a detail read grew from {early} to {later} SELECTs as the season lengthened — an N+1 is back"


def _pyramid_pair(session: Session) -> tuple[Competition, Competition]:
    """A league the world's own boundary pairs with the league below it, read off the stored move."""
    leagues = list(session.scalars(select(Competition).where(Competition.kind == "league").order_by(Competition.tier.desc(), Competition.slug)).all())
    for lower in leagues:
        above = career_service._pyramid_neighbours(session, lower)["above"]
        if above is not None:
            assert int(above.tier) == int(lower.tier) - 1, f"{above.slug} is tier {above.tier} against {lower.slug}'s tier {lower.tier}"
            return above, lower
    pytest.skip("the generated world has no tier boundary for a career to cross")


def _club_in(session: Session, competition: Competition) -> Team:
    return session.scalars(select(Team).where(Team.competition_id == competition.id).order_by(Team.slug).limit(1)).one()


def _career_at(session: Session, world: dict[str, Any], club: Team) -> Career:
    return career_service.create_career(
        session,
        owner_id=world["owner_id"],
        club=career_service.resolve_club(session, club.id),
        manager_name="Boundary Manager",
        philosophy=CAREER_PHLOSOPHIES[0],
        system_slug="",
        budget=1_000_000,
        objectives=OBJECTIVES,
        season="2026",
    )


def _fabricate_season(session: Session, career: Career, results: str) -> list[CareerFixture]:
    """Write one `career_fixtures` row per result character, in order, so a boundary has sums to judge.

    The rows are not engine output — the boundary rule reads `career_fixtures` and never a match report —
    so a fabricated season is exactly the population `close_season` sums. `match_id` stays None, which is
    the same state as a career whose stored report was deleted.
    """
    scores = {"W": (2, 0), "D": (1, 1), "L": (0, 1)}
    rows: list[CareerFixture] = []
    for index, result in enumerate(results, start=1):
        club_goals, opponent_goals = scores[result]
        row = CareerFixture(
            id=new_public_id("cf"),
            career_id=career.id,
            round_index=index,
            side="home" if index % 2 else "away",
            opponent_name=f"Fabricated Opponent {index}",
            opponent_short=f"FO{index}",
            venue_name="Fabricated Ground",
            club_goals=club_goals,
            opponent_goals=opponent_goals,
            outcome=result,
            points=career_service.POINTS_FOR[result],
        )
        session.add(row)
        rows.append(row)
    career.rounds_played = len(results)
    session.commit()
    session.refresh(career)
    return rows


class TestSeasons:
    def test_a_numeric_season_label_advances_and_a_named_one_stays(self) -> None:
        assert career_service.season_label("2026", 1) == "2026"
        assert career_service.season_label("2026", 2) == "2027"
        assert career_service.season_label("spring", 3) == "spring", "a scenario's named season is not guessed at"
        assert career_service.season_label("", 2) == ""

    def test_a_fresh_season_runs_from_the_first_round_to_the_horizons_last(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        bounds = career_service.season_bounds(session, career)
        rounds = 2 * len(world["opponents"])
        assert bounds["index"] == 1 and bounds["first_round"] == 1 and bounds["season"] == "2026"
        assert bounds["rounds"] == rounds and bounds["last_round"] == rounds
        assert "round-robin" in bounds["source"]

    def test_a_challenge_season_is_its_window_and_moves_no_club(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        career.challenge_window = 2
        session.commit()
        for _ in range(2):
            career_service.play_round(session, career)
        closed = career_service.seasons_of(session, career)
        assert len(closed) == 1, "the round that completed the window wrote exactly one season row"
        assert closed[0].verdict == "challenge" and closed[0].rule == "challenge"
        assert (closed[0].first_round, closed[0].last_round, closed[0].rounds) == (1, 2, 2)
        assert closed[0].line is None and closed[0].next_competition_id is None
        assert career.competition_id == closed[0].competition_id, "a challenge is judged by its objectives, so the pyramid does not move it"
        with pytest.raises(career_service.WindowClosed):
            career_service.play_round(session, career)

    def test_a_top_tier_season_at_exactly_the_relegation_line_stays(self, session, world) -> None:  # type: ignore[no-untyped-def]
        upper = _pyramid_pair(session)[0]
        career = _career_at(session, world, _club_in(session, upper))
        rounds = int(career_service.season_horizon(session, career)["rounds"])
        _fabricate_season(session, career, "D" * rounds)
        closed = career_service.close_season(session, career)
        assert closed is not None, "a season with every round drawn is complete and must close"
        assert closed.verdict == "stayed" and closed.rule == "relegation"
        assert closed.line == career_service.RELEGATION_PACE
        assert career.competition_id == upper.id, "the line is a floor: a season at it survives"
        view = career_service.seasons_view(session, career, career_service.fixtures_of(session, career))
        assert view["closed"][0]["points_per_round"] == 1.0
        assert view["closed"][0]["recheck"] == "this season's fixtures still say what the stored verdict said"

    def test_a_losing_top_tier_season_is_relegated_into_the_paired_league(self, session, world) -> None:  # type: ignore[no-untyped-def]
        upper, lower = _pyramid_pair(session)
        career = _career_at(session, world, _club_in(session, upper))
        rounds = int(career_service.season_horizon(session, career)["rounds"])
        _fabricate_season(session, career, "L" * rounds)
        closed = career_service.close_season(session, career)
        assert closed is not None and closed.verdict == "relegated" and closed.rule == "relegation"
        assert closed.line == career_service.RELEGATION_PACE and closed.next_competition_id == lower.id
        assert career.competition_id == lower.id and career.competition_name == lower.name
        plan = career_service.next_fixture_plan(session, career)
        assert plan["season_index"] == 2 and plan["round_in_season"] == 1 and plan["round_index"] == rounds + 1
        assert plan["opponent_team_id"] in {team.id for team in career_service.competition_clubs(session, lower.id, exclude_id=career.club_id or "")}

    def test_a_winning_lower_tier_season_is_promoted_into_the_paired_league(self, session, world) -> None:  # type: ignore[no-untyped-def]
        upper, lower = _pyramid_pair(session)
        career = _career_at(session, world, _club_in(session, lower))
        rounds = int(career_service.season_horizon(session, career)["rounds"])
        _fabricate_season(session, career, "W" * rounds)
        closed = career_service.close_season(session, career)
        assert closed is not None and closed.verdict == "promoted" and closed.rule == "promotion"
        assert closed.line == career_service.PROMOTION_PACE and closed.next_competition_id == upper.id
        assert int(closed.tier) == int(lower.tier) and closed.season == "2026"
        assert (closed.first_round, closed.last_round, closed.rounds) == (1, rounds, rounds)
        assert career.competition_id == upper.id and career.competition_name == upper.name
        assert session.scalars(select(Team.competition_id).where(Team.id == career.club_id)).one() == lower.id, "the career moved, the club's world membership did not"
        plan = career_service.next_fixture_plan(session, career)
        assert plan["season_index"] == 2 and plan["round_in_season"] == 1 and plan["round_index"] == rounds + 1
        assert plan["opponent_team_id"] in {team.id for team in career_service.competition_clubs(session, upper.id, exclude_id=career.club_id or "")}
        view = career_service.career_view(session, career)
        block = view["seasons"]["closed"][0]
        assert block["points_per_round"] == round(3 * rounds / rounds, 3) == 3.0
        assert block["recheck"] == "this season's fixtures still say what the stored verdict said"
        assert view["seasons"]["current"]["season_index"] == 2 and view["seasons"]["current"]["season"] == "2027"
        assert view["record"]["played"] == 0 and view["career_record"]["played"] == rounds, "the season record starts empty; the lifetime one keeps the sums"

    def test_the_boundary_round_closes_once_and_asking_twice_returns_the_row(self, session, world) -> None:  # type: ignore[no-untyped-def]
        upper, lower = _pyramid_pair(session)
        career = _career_at(session, world, _club_in(session, lower))
        rounds = int(career_service.season_horizon(session, career)["rounds"])
        _fabricate_season(session, career, "W" * rounds)
        first = career_service.close_season(session, career)
        second = career_service.close_season(session, career)
        assert first is not None and second is not None and first.id == second.id
        rows = career_service.seasons_of(session, career)
        assert len(rows) == 1 and len(session.scalars(select(CareerSeason.id).where(CareerSeason.career_id == career.id)).all()) == 1

    def test_a_career_with_no_competition_has_no_horizon_to_close(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        career.competition_id = None
        career.competition_name = ""
        session.commit()
        bounds = career_service.season_bounds(session, career)
        assert bounds["rounds"] == 0 and bounds["last_round"] is None
        assert career_service.close_season(session, career) is None, "no horizon means no last round and no boundary decision"
