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
from sqlalchemy import event, select
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
        # The next fixture's brief is wired to the round after the one just played.
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
        assert view["head_to_head"]["played"] == 0, "the fourth round of the first cycle meets an opponent this career has not played"


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
