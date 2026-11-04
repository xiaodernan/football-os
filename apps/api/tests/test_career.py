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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.security import hash_password, new_public_id
from app.models import (
    ALL_ATTRIBUTES,
    CAREER_PHLOSOPHIES,
    OBJECTIVE_BONUS_EFFECT,
    OBJECTIVE_FORMULA,
    OBJECTIVE_KINDS,
    Career,
    CareerAppearance,
    CareerBudgetAward,
    CareerDevelopment,
    CareerFixture,
    CareerSeason,
    Competition,
    RealMatch,
    RealPlayer,
    SimulationMatch,
    Team,
    User,
)
from app.services.simulation import career as career_service
from app.services.simulation import market
from app.services.simulation.profile import team_profile
from app.services.simulation.service import replay_is_identical
from app.services.simulation.squad import squad_as_of
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


class TestWorldTie:
    """M13 item 12, the tie half: a round that played the world's fixture says so, and neither side is rewritten."""

    def test_a_calendar_round_records_the_generated_fixture_it_played(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        plan = career_service.next_fixture_plan(session, career)
        fixture, _match = career_service.play_round(session, career)
        drawn = session.scalars(select(RealMatch).where(RealMatch.slug == plan["match_slug"])).one()
        assert fixture.round_index == 1
        assert fixture.world_match_id == drawn.id and fixture.world_match_slug == drawn.slug

    def test_the_generated_fixture_keeps_the_score_the_world_played(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        plan = career_service.next_fixture_plan(session, career)
        drawn = session.scalars(select(RealMatch).where(RealMatch.slug == plan["match_slug"])).one()
        before = (drawn.status, drawn.home_goals, drawn.away_goals, drawn.summary, drawn.content_hash)
        fixture, _match = career_service.play_round(session, career)
        session.refresh(drawn)
        assert (drawn.status, drawn.home_goals, drawn.away_goals, drawn.summary, drawn.content_hash) == before, "a career round never rewrites the generated fixture"
        assert fixture.world_match_id == drawn.id, "the round names the fixture it played, not one it rewrote"

    def test_a_rotation_round_names_no_generated_fixture(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        bounds = career_service.season_bounds(session, career)
        size = len(career_service.calendar_fixtures(session, career, bounds=bounds))
        _at(career, size + 1)
        fixture, _match = career_service.play_round(session, career)
        assert fixture.round_index == size + 1
        assert fixture.world_match_id is None and fixture.world_match_slug is None, "a round the world never drew invents no fixture"

    def test_the_view_prints_the_careers_score_beside_the_worlds_own(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        plan = career_service.next_fixture_plan(session, career)
        career_service.play_round(session, career)
        drawn = session.scalars(select(RealMatch).where(RealMatch.slug == plan["match_slug"])).one()
        row = career_service.career_view(session, career)["fixtures"][0]
        assert row["world_match_slug"] == plan["match_slug"] and row["world_match_path"] == f"/match/{plan['match_slug']}"
        assert row["world_match_still_stored"] is True
        assert row["world_status"] == drawn.status
        assert row["world_goals"] == {"home": drawn.home_goals, "away": drawn.away_goals}

    def test_a_fixture_the_world_no_longer_holds_keeps_the_slug_and_loses_the_link(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        career_service.play_round(session, career)
        stored = career_service.fixtures_of(session, career)
        kept_slug = stored[0].world_match_slug
        stored[0].world_match_id = "removed-world-fixture"
        session.commit()
        row = career_service.career_view(session, career)["fixtures"][0]
        assert kept_slug and row["world_match_slug"] == kept_slug
        assert row["world_match_path"] is None and row["world_match_still_stored"] is False
        assert row["world_status"] is None and row["world_goals"] is None

    def test_the_limitation_says_the_tie_is_one_way(self) -> None:
        text = career_service.limitations()["world_calendar"]
        assert "one-way" in text and "no career result is written into it" in text


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
        assert set(view["limitations"]) == {"budget", "wages", "carry_over", "projections", "ledger", "scouting", "philosophy", "table", "objectives", "world_calendar"}
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

    def test_a_fresh_career_has_applied_nothing_and_names_the_round_it_would(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        dev = career_service.career_view(session, career)["development"]
        assert dev["applied_rows"] == 0 and dev["applied_players"] == 0
        assert dev["last_applied_round"] == 0
        assert dev["applies_from_round"] == 1, "a career that has played nothing would apply its first snapshot in round 1"

    def test_every_played_round_writes_one_row_per_selected_player(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        _fixture, match = career_service.play_round(session, career)
        appearances = list(session.scalars(select(CareerAppearance).where(CareerAppearance.career_id == career.id)).all())
        rows = list(session.scalars(select(CareerDevelopment).where(CareerDevelopment.career_id == career.id)).all())
        assert len(appearances) == len(rows) == 11, "a played round traces and develops the same eleven"
        assert {row.player_id for row in rows} == {row.player_id for row in appearances}
        for row in rows:
            assert row.round_index == 1
            assert row.minutes_total == int(match.minutes), "a development row reads the fixture's full length"
            assert row.effective_minutes >= row.minutes_total, "training load never subtracts from match minutes"
            assert row.overall_after >= row.overall_before, "development never lowers the scalar curve"
            assert set(row.attributes) == set(ALL_ATTRIBUTES), "a row stores the full after-state"
            player = session.get(RealPlayer, row.player_id)
            assert player is not None
            for attribute in ALL_ATTRIBUTES:
                ceiling = max(int((player.attributes or {}).get(attribute, career_service.ATTRIBUTE_FLOOR)), int(player.potential))
                assert row.attributes[attribute] <= ceiling, "a stored attribute already above potential is left alone, a lower one never crosses it"

    def test_the_next_round_plays_the_eleven_the_last_round_developed(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        career_service.play_round(session, career)
        overlay = squad_as_of(session, career, 2)
        assert overlay is not None and overlay.carries_development
        assert len(overlay.developed) == 11
        profile = team_profile(session, career.club_id or "", system_slug=career.system_slug or None, squad=overlay)
        developed_factor = next(factor for factor in profile.factors if factor.key == "developed_players")
        carried = [player_id for player_id, _slug, _name, _position, _band in profile.selected if player_id in overlay.developed]
        assert carried, "the eleven the next round selects reads its own development rows"
        assert developed_factor.value == float(len(carried)), "the engine names how many of its own eleven carry a development row"

    def test_a_round_never_reads_the_development_it_writes(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        career_service.play_round(session, career)
        assert squad_as_of(session, career, 1) is None, "round 1 played before its own row existed; replaying it must not see it"
        written = squad_as_of(session, career, 2)
        assert written is not None and written.carries_development, "round 2 is the first round that reads what round 1 wrote"

    def test_replaying_a_stored_round_keeps_its_digest_after_later_rounds(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        first = career_service.play_round(session, career)[1]
        second = career_service.play_round(session, career)[1]
        replay_first = replay_is_identical(session, first)
        assert replay_first["possible"] is True and replay_first["identical"] is True, "round 1's replay reads the rows that existed before it, none of them its own"
        replay_second = replay_is_identical(session, second)
        assert replay_second["possible"] is True and replay_second["identical"] is True, "round 2's replay reads round 1's row and nothing written after it"

    def test_the_worlds_stored_rows_are_never_rewritten(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        before = {player.id: (dict(player.attributes or {}), int(player.overall)) for player in session.scalars(select(RealPlayer).where(RealPlayer.team_id == career.club_id)).all()}
        for _ in range(2):
            career_service.play_round(session, career)
        session.expire_all()
        after = {player.id: (dict(player.attributes or {}), int(player.overall)) for player in session.scalars(select(RealPlayer).where(RealPlayer.team_id == career.club_id)).all()}
        assert after == before, "development is this career's own snapshot, not a rewrite of the generated world"

    def test_the_view_reports_the_rows_it_applied_and_the_round_they_apply_from(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        for _ in range(2):
            career_service.play_round(session, career)
        dev = career_service.career_view(session, career)["development"]
        assert dev["applied_rows"] == 22, "two played rounds write eleven rows each"
        assert dev["applied_players"] == 11
        assert dev["last_applied_round"] == 2
        assert dev["applies_from_round"] == 3
        for entry in dev["top_developed"]:
            assert entry["applied_round"] in (1, 2)
            assert entry["overall_after"] >= entry["overall_before"]


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


def _fabricate_season(session: Session, career: Career, results: str, *, start: int = 1) -> list[CareerFixture]:
    """Write one `career_fixtures` row per result character, in order, so a boundary has sums to judge.

    The rows are not engine output — the boundary rule reads `career_fixtures` and never a match report —
    so a fabricated season is exactly the population `close_season` sums. `match_id` stays None, which is
    the same state as a career whose stored report was deleted. `start` is the round the season begins at,
    so a second season after a boundary can be fabricated without rewriting the first one.
    """
    scores = {"W": (2, 0), "D": (1, 1), "L": (0, 1)}
    rows: list[CareerFixture] = []
    for offset, result in enumerate(results):
        index = start + offset
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
    career.rounds_played = start + len(results) - 1
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

    def test_a_closed_challenge_window_still_sums_its_own_rounds(self, session, world) -> None:  # type: ignore[no-untyped-def]
        """The window that closed is still the season the page reads.

        The boundary row is written when the window's last round is played. A span that advanced past it
        left every season read (record, table, objectives, board) summing zero rows while the fixture
        table still listed the window — the state the challenge walk reported as `Pts 8 / Points 0 /
        record 0-0-0`. The row is a decision on the one season a challenge career has, not the start of
        a second one `play_round` would refuse.
        """
        career = _career(session, world)
        career.challenge_window = 2
        session.commit()
        _fabricate_season(session, career, "WD")
        closed = career_service.close_season(session, career)
        assert closed is not None and closed.verdict == "challenge"
        bounds = career_service.season_bounds(session, career)
        assert (bounds["index"], bounds["first_round"], bounds["rounds"], bounds["last_round"]) == (1, 1, 2, 2), (
            "the closed window is the career's one season, so the span does not advance"
        )
        view = career_service.career_view(session, career)
        assert view["record"]["played"] == 2 and view["record"]["won"] == 1
        assert view["record"]["points"] == sum(int(row["points"]) for row in view["fixtures"]) == 4, (
            "the record and the fixture table count the same rounds after the window closed"
        )
        assert view["objectives"][0]["actual"] == view["record"]["won"]
        assert view["seasons"]["current"]["season_index"] == view["seasons"]["closed"][0]["season_index"] == 1
        assert view["next_fixture"]["available"] is False and "window closed at round 2" in view["next_fixture"]["reason"], (
            "the view offers no round the window refuses"
        )
        assert view["next_fixture_brief"]["available"] is False
        again = career_service.close_season(session, career)
        assert again is not None and again.id == closed.id, "the window closes once, whatever the round count says"

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


def _awards(session: Session, career: Career) -> list[CareerBudgetAward]:
    return list(
        session.scalars(
            select(CareerBudgetAward).where(CareerBudgetAward.career_id == career.id).order_by(CareerBudgetAward.season_index, CareerBudgetAward.id)
        ).all()
    )


def _grants(session: Session, career: Career) -> list[CareerBudgetAward]:
    """The season grants alone: the award table also pays objective bonuses (item 36)."""
    return [row for row in _awards(session, career) if str(row.kind) == "season_grant"]


class TestSeasonGrants:
    """The board pays for a closed season (M13 Phase 7 item 24), and the ledger says how much.

    A career's budget could only ever go down before this: fees left it, wages left it, and only a sale
    put anything back. These tests hold the three claims that make the money real — the grant is the
    season's own rounds and points, it arrives as a ledger row the balance arithmetic already counts, and
    it is paid once per season by the boundary rather than by whoever remembers to call.
    """

    def test_a_promoted_season_pays_for_its_rounds_points_and_verdict(self, session, world) -> None:  # type: ignore[no-untyped-def]
        upper, lower = _pyramid_pair(session)
        career = _career_at(session, world, _club_in(session, lower))
        rounds = int(career_service.season_horizon(session, career)["rounds"])
        _fabricate_season(session, career, "W" * rounds)
        before = market.budget_position(session, career)
        assert before["granted"] == 0 and before["grant_rows"] == 0

        closed = career_service.close_season(session, career)
        assert closed is not None and closed.verdict == "promoted"

        rows = _grants(session, career)
        assert len(rows) == 1, "the boundary paid once for the season it closed"
        award = rows[0]
        assert (award.season_index, award.round_index, award.kind) == (1, rounds, "season_grant")
        points = 3 * rounds
        assert award.amount == rounds * market.SEASON_GRANT_PER_ROUND + points * market.SEASON_GRANT_PER_POINT + market.PROMOTION_GRANT
        assert award.promotion == market.PROMOTION_GRANT
        assert award.basis == (
            f"{rounds} round(s) × {market.SEASON_GRANT_PER_ROUND:,} + {points} point(s) × {market.SEASON_GRANT_PER_POINT:,} + promotion {market.PROMOTION_GRANT:,}"
        )
        assert award.amount_units == career.budget_units

        after = market.budget_position(session, career)
        assert after["granted"] == award.amount
        assert award.budget_after == int(before["remaining"]) + award.amount
        assert int(after["remaining"]) - int(before["remaining"]) == award.amount + int(after["received_objectives"]), "the grant and the objective bonus it was paid with are both new money"

    def test_a_season_that_stays_pays_its_rounds_and_points_and_no_promotion(self, session, world) -> None:  # type: ignore[no-untyped-def]
        upper, _lower = _pyramid_pair(session)
        career = _career_at(session, world, _club_in(session, upper))
        rounds = int(career_service.season_horizon(session, career)["rounds"])
        _fabricate_season(session, career, "D" * rounds)
        closed = career_service.close_season(session, career)
        assert closed is not None and closed.verdict == "stayed"
        award = _grants(session, career)[0]
        assert award.promotion == 0
        assert award.amount == rounds * market.SEASON_GRANT_PER_ROUND + rounds * market.SEASON_GRANT_PER_POINT
        assert "promotion" not in award.basis

    def test_a_relegated_season_is_paid_for_as_well(self, session, world) -> None:  # type: ignore[no-untyped-def]
        """A demotion is still a season played, and the grant rewards the record, not the verdict alone."""
        upper, _lower = _pyramid_pair(session)
        career = _career_at(session, world, _club_in(session, upper))
        rounds = int(career_service.season_horizon(session, career)["rounds"])
        _fabricate_season(session, career, "L" * rounds)
        closed = career_service.close_season(session, career)
        assert closed is not None and closed.verdict == "relegated"
        award = _grants(session, career)[0]
        assert (award.amount, award.promotion) == (rounds * market.SEASON_GRANT_PER_ROUND, 0)

    def test_a_challenge_window_pays_no_grant(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        career.challenge_window = 2
        session.commit()
        _fabricate_season(session, career, "WW")
        closed = career_service.close_season(session, career)
        assert closed is not None and closed.verdict == "challenge"
        assert _awards(session, career) == [], "the run is judged by the challenge's own reward"
        assert market.budget_position(session, career)["granted"] == 0

    def test_a_second_season_pays_again(self, session, world) -> None:  # type: ignore[no-untyped-def]
        upper, lower = _pyramid_pair(session)
        career = _career_at(session, world, _club_in(session, lower))
        first_rounds = int(career_service.season_horizon(session, career)["rounds"])
        _fabricate_season(session, career, "W" * first_rounds)
        assert career_service.close_season(session, career) is not None
        assert career.competition_id == upper.id

        bounds = career_service.season_bounds(session, career)
        assert (bounds["index"], bounds["first_round"]) == (2, first_rounds + 1)
        second_rounds = int(bounds["rounds"])
        _fabricate_season(session, career, "D" * second_rounds, start=bounds["first_round"])
        assert career_service.close_season(session, career) is not None

        rows = _grants(session, career)
        assert [int(row.season_index) for row in rows] == [1, 2]
        assert rows[1].round_index == first_rounds + second_rounds
        expected = rows[0].amount + rows[1].amount
        position = market.budget_position(session, career)
        assert position["granted"] == expected
        assert position["granted"] + int(position["received_objectives"]) == int(position["remaining"]) - int(career.budget)

    def test_the_grant_is_one_row_per_season_even_when_a_writer_forgets(self, session, world) -> None:  # type: ignore[no-untyped-def]
        """The unique key holds the promise, not the call site."""
        upper, lower = _pyramid_pair(session)
        career = _career_at(session, world, _club_in(session, lower))
        rounds = int(career_service.season_horizon(session, career)["rounds"])
        _fabricate_season(session, career, "W" * rounds)
        closed = career_service.close_season(session, career)
        again = career_service.close_season(session, career)
        assert closed is not None and again.id == closed.id
        assert len(_grants(session, career)) == 1, "asking the boundary twice pays twice nothing"

        duplicate = CareerBudgetAward(
            id=new_public_id("awd"),
            career_id=career.id,
            season_index=1,
            round_index=rounds,
            kind="season_grant",
            amount=1,
            amount_units=career.budget_units,
            basis="a hand-written second grant for the same season",
            promotion=0,
            budget_after=1,
            data_origin="simulation",
            is_demo_data=True,
        )
        session.add(duplicate)
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()

    def test_the_ledger_adds_up_across_a_grant(self, session, world) -> None:  # type: ignore[no-untyped-def]
        upper, lower = _pyramid_pair(session)
        career = _career_at(session, world, _club_in(session, lower))
        rounds = int(career_service.season_horizon(session, career)["rounds"])
        _fabricate_season(session, career, "W" * rounds)
        assert career_service.close_season(session, career) is not None
        award = _grants(session, career)[0]

        timeline = market.budget_timeline(session, career, limit=0)
        position = market.budget_position(session, career)
        grants = [row for row in timeline["rows"] if row["kind"] == "season_grant"]
        assert len(grants) == 1
        assert grants[0]["delta"] == award.amount
        assert grants[0]["label"] == f"board grant for season {award.season_index}"
        assert timeline["disagreements"] == 0, "a row that arrives by a different rule than the others still stores its own running balance"
        assert timeline["closing_balance"] == int(position["remaining"]) == int(career.budget) + award.amount + int(position["received_objectives"])

    def test_the_market_door_prints_the_grant_in_the_ledger(self, session, world) -> None:  # type: ignore[no-untyped-def]
        upper, lower = _pyramid_pair(session)
        career = _career_at(session, world, _club_in(session, lower))
        rounds = int(career_service.season_horizon(session, career)["rounds"])
        _fabricate_season(session, career, "W" * rounds)
        assert career_service.close_season(session, career) is not None
        award = _grants(session, career)[0]

        view = market.market_view(session, career)
        assert view["totals"]["grant_rows"] == 1
        assert view["budget"]["granted"] == award.amount
        assert view["rules"]["grant"] == market.BUDGET_AWARD_FORMULA
        assert view["constants"]["season_grant_per_round"] == market.SEASON_GRANT_PER_ROUND
        ledger = view["moves"]
        assert [row for row in ledger if row["kind"] == "season_grant"][0]["cash"] == "in"
        assert ledger[-1]["round_index"] == rounds, "the boundary's grant is the last row of the round that closed the season"
        assert sum(int(row["fee"]) * (1 if row["cash"] == "in" else -1) for row in ledger) + int(career.budget) == int(view["budget"]["remaining"])

        affordable = market.affordability_view(session, career)
        assert affordable["granted"] == award.amount
        assert affordable["granted"] + int(affordable["received_objectives"]) == affordable["remaining"] - int(career.budget)
        assert affordable["timeline"]["rows"][-1]["kind"] == "objective_bonus", "the boundary's bonuses are the last rows of the season"

    def test_the_seasons_block_prints_the_grant_beside_the_verdict(self, session, world) -> None:  # type: ignore[no-untyped-def]
        upper, lower = _pyramid_pair(session)
        career = _career_at(session, world, _club_in(session, lower))
        rounds = int(career_service.season_horizon(session, career)["rounds"])
        _fabricate_season(session, career, "W" * rounds)
        assert career_service.close_season(session, career) is not None
        award = _grants(session, career)[0]

        view = career_service.career_view(session, career)
        block = view["seasons"]["closed"][0]["grant"]
        assert block["amount"] == award.amount == award.budget_after - int(career.budget)
        assert block["units"] == award.amount_units == career.budget_units
        assert block["basis"] == award.basis
        assert block["formula"] == market.BUDGET_AWARD_FORMULA
        assert block["round_index"] == rounds

    def test_the_current_season_projects_what_closing_now_would_pay(self, session, world) -> None:  # type: ignore[no-untyped-def]
        """The projection is the boundary's own arithmetic over the season's played rounds."""
        upper, lower = _pyramid_pair(session)
        career = _career_at(session, world, _club_in(session, lower))
        rounds = int(career_service.season_horizon(session, career)["rounds"])
        _fabricate_season(session, career, "W" * rounds)
        current = career_service.seasons_view(session, career, career_service.fixtures_of(session, career))["current"]
        grant = current["grant_if_closed_now"]
        assert grant["units"] == career.budget_units, "a projected sum is stated in the career's own units, like the row it would become"
        assert grant["rounds"] == current["played"] == rounds
        assert grant["points"] == current["record"]["points"] == 3 * rounds
        assert current["at_this_pace"] == "promoted"
        assert grant["amount"] == rounds * market.SEASON_GRANT_PER_ROUND + (3 * rounds) * market.SEASON_GRANT_PER_POINT + market.PROMOTION_GRANT
        assert _awards(session, career) == [], "a projection is not a payment"
        assert market.budget_position(session, career)["granted"] == 0

    def test_a_fresh_season_projects_a_grant_of_nothing(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _career(session, world)
        grant = career_service.seasons_view(session, career, career_service.fixtures_of(session, career))["current"]["grant_if_closed_now"]
        assert (grant["rounds"], grant["points"], grant["amount"]) == (0, 0, 0)
        assert grant["basis"] == "0 round(s) × 8,000 + 0 point(s) × 2,500"

    def test_a_grant_that_pays_nothing_writes_no_row(self, session, world) -> None:  # type: ignore[no-untyped-def]
        """The two verdicts that produce no money leave no row behind for a page to explain."""
        career = _career(session, world)
        assert market.pay_season_grant(session, career, season_index=1, round_index=1, rounds_played=0, points=0, verdict="stayed") is None
        assert market.pay_season_grant(session, career, season_index=1, round_index=1, rounds_played=3, points=6, verdict="challenge") is None
        assert _awards(session, career) == []


class TestObjectiveBonuses:
    """The board pays the targets it set (M13 Phase 9 item 36).

    Item 24 made a season pay for its rounds and points, and the objectives a manager chose were still
    only prose. These tests hold that a met objective is money, that every rule the board prints about an
    objective is the rule that pays it — a miss pays nothing, a target of zero asks for nothing, a
    challenge's window is judged elsewhere — and that the money joins the one ledger the page sums.
    """

    def _career_with(self, session: Session, world: dict[str, Any], *objectives: tuple[str, int, str]) -> Career:
        return _career(
            session,
            world,
            objectives=[{"kind": kind, "target": target, "label": label} for kind, target, label in objectives],
        )

    def _bonuses(self, session: Session, career: Career) -> list[CareerBudgetAward]:
        return [row for row in _awards(session, career) if str(row.kind) == "objective_bonus"]

    def test_a_met_objective_pays_its_bonus_into_the_balance(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = self._career_with(session, world, ("wins", 1, "win once"))
        rounds = int(career_service.season_horizon(session, career)["rounds"])
        before = market.budget_position(session, career)
        _fabricate_season(session, career, "W" * rounds)
        assert career_service.close_season(session, career) is not None

        bonuses = self._bonuses(session, career)
        assert len(bonuses) == 1
        bonus = bonuses[0]
        assert (bonus.season_index, bonus.round_index, bonus.stage) == (1, rounds, "wins")
        assert bonus.amount == market.OBJECTIVE_BONUS_BY_KIND["wins"]
        assert bonus.basis == f"win once: {rounds} ≥ 1 pays {bonus.amount:,} {career.budget_units}"
        assert bonus.amount_units == career.budget_units

        after = market.budget_position(session, career)
        assert after["received_objectives"] == bonus.amount and after["objective_rows"] == 1
        assert after["objective_detail"] == f"season 1 wins: {bonus.amount:,}"
        grant = _grants(session, career)[0]
        assert int(after["remaining"]) - int(before["remaining"]) == grant.amount + bonus.amount
        assert bonus.budget_after == grant.budget_after + bonus.amount, "the bonus chains onto the grant it was paid with"

    def test_an_objective_the_season_missed_pays_nothing(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = self._career_with(session, world, ("wins", 99, "more wins than a season allows"))
        rounds = int(career_service.season_horizon(session, career)["rounds"])
        _fabricate_season(session, career, "W" * rounds)
        assert career_service.close_season(session, career) is not None
        assert self._bonuses(session, career) == []
        position = market.budget_position(session, career)
        assert (position["received_objectives"], position["objective_rows"]) == (0, 0)
        assert len(_grants(session, career)) == 1, "the season is still paid for its rounds and points"

    def test_a_target_of_zero_asks_for_nothing_and_pays_nothing(self, session, world) -> None:  # type: ignore[no-untyped-def]
        """The verdict still says met — nothing had to be met — and the money rule is where that is refused."""
        career = self._career_with(session, world, ("wins", 0, "nothing asked"))
        verdict = career_service.objectives_of(career, {"won": 5, "points": 15, "goal_difference": 5, "unbeaten_run": 3})[0]
        assert verdict["met"] is True
        report = market.objective_bonus_report(objectives=[verdict], verdict="stayed", units=career.budget_units)
        assert report["amount"] == 0 and report["rows"] == []

        rounds = int(career_service.season_horizon(session, career)["rounds"])
        _fabricate_season(session, career, "W" * rounds)
        assert career_service.close_season(session, career) is not None
        assert self._bonuses(session, career) == [], "a target nothing had to be met for is not a demand the board pays"

    def test_each_met_objective_pays_its_own_rate(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = self._career_with(
            session,
            world,
            ("wins", 1, "win once"),
            ("points", 3, "three points"),
            ("goal_difference", 1, "a positive margin"),
            ("unbeaten", 1, "unbeaten once"),
        )
        rounds = int(career_service.season_horizon(session, career)["rounds"])
        _fabricate_season(session, career, "W" * rounds)
        assert career_service.close_season(session, career) is not None
        paid = {str(row.stage): int(row.amount) for row in self._bonuses(session, career)}
        assert paid == market.OBJECTIVE_BONUS_BY_KIND
        assert sum(paid.values()) == 145_000
        assert market.budget_position(session, career)["received_objectives"] == 145_000

    def test_a_challenge_window_pays_no_bonus(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = self._career_with(session, world, ("wins", 1, "win once"))
        career.challenge_window = 2
        session.commit()
        _fabricate_season(session, career, "WW")
        closed = career_service.close_season(session, career)
        assert closed is not None and closed.verdict == "challenge"
        assert _awards(session, career) == [], "the run is judged by the challenge's own reward"

    def test_the_bonus_is_one_row_per_kind_per_season(self, session, world) -> None:  # type: ignore[no-untyped-def]
        """The unique key holds the promise, not the call site, exactly as it does for the grant."""
        career = self._career_with(session, world, ("wins", 1, "win once"))
        rounds = int(career_service.season_horizon(session, career)["rounds"])
        _fabricate_season(session, career, "W" * rounds)
        assert career_service.close_season(session, career) is not None
        duplicate = CareerBudgetAward(
            id=new_public_id("awd"),
            career_id=career.id,
            season_index=1,
            round_index=rounds,
            kind="objective_bonus",
            stage="wins",
            amount=1,
            amount_units=career.budget_units,
            basis="a hand-written second bonus for the same objective",
            promotion=0,
            budget_after=1,
            data_origin="simulation",
            is_demo_data=True,
        )
        session.add(duplicate)
        with pytest.raises(IntegrityError):
            session.flush()
        session.rollback()

    def test_the_ledger_adds_up_across_the_boundary(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = self._career_with(session, world, ("wins", 1, "win once"), ("points", 3, "three points"))
        rounds = int(career_service.season_horizon(session, career)["rounds"])
        _fabricate_season(session, career, "W" * rounds)
        assert career_service.close_season(session, career) is not None

        timeline = market.budget_timeline(session, career, limit=0)
        position = market.budget_position(session, career)
        bonuses = [row for row in timeline["rows"] if row["kind"] == "objective_bonus"]
        assert [row["label"] for row in bonuses] == ["objective bonus, points", "objective bonus, wins"], "the boundary's grant, then the bonuses in kind order"
        kinds = [row["kind"] for row in timeline["rows"]]
        assert kinds.index("season_grant") < kinds.index("objective_bonus")
        assert timeline["disagreements"] == 0
        assert timeline["closing_balance"] == int(position["remaining"])

    def test_the_market_door_publishes_the_bonus(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = self._career_with(session, world, ("wins", 1, "win once"), ("points", 3, "three points"))
        rounds = int(career_service.season_horizon(session, career)["rounds"])
        _fabricate_season(session, career, "W" * rounds)
        assert career_service.close_season(session, career) is not None
        total = market.OBJECTIVE_BONUS_BY_KIND["wins"] + market.OBJECTIVE_BONUS_BY_KIND["points"]

        view = market.market_view(session, career)
        assert view["totals"]["bonus_rows"] == 2
        assert view["budget"]["received_objectives"] == total
        assert view["rules"]["objective_bonus"] == market.OBJECTIVE_BONUS_FORMULA
        assert view["constants"]["objective_bonus_by_kind"] == market.OBJECTIVE_BONUS_BY_KIND
        rows = [row for row in view["moves"] if row["kind"] == "objective_bonus"]
        assert [row["player_name"] for row in rows] == ["objective bonus, points", "objective bonus, wins"]
        assert all(row["effect"] == OBJECTIVE_BONUS_EFFECT and row["cash"] == "in" for row in rows)

        affordable = market.affordability_view(session, career)
        assert affordable["received_objectives"] == total
        assert affordable["objective_rows"] == 2

    def test_the_seasons_block_projects_a_bonus_and_prints_the_paid_one(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = self._career_with(session, world, ("wins", 1, "win once"), ("points", 3, "three points"))
        rounds = int(career_service.season_horizon(session, career)["rounds"])
        _fabricate_season(session, career, "W" * (rounds - 1))
        current = career_service.seasons_view(session, career, career_service.fixtures_of(session, career))["current"]
        projected = current["bonus_if_closed_now"]
        assert projected["amount"] == market.OBJECTIVE_BONUS_BY_KIND["wins"] + market.OBJECTIVE_BONUS_BY_KIND["points"]
        assert [row["kind"] for row in projected["rows"]] == ["wins", "points"]
        assert projected["formula"] == market.OBJECTIVE_BONUS_FORMULA
        assert self._bonuses(session, career) == [], "a projection is not a payment"

        _fabricate_season(session, career, "W", start=rounds)
        assert career_service.close_season(session, career) is not None
        block = career_service.career_view(session, career)["seasons"]["closed"][0]
        assert block["grant"] is not None
        assert block["bonuses"]["amount"] == projected["amount"]
        assert [row["kind"] for row in block["bonuses"]["rows"]] == ["points", "wins"], "the stored rows carry the ledger's kind order, not the projection's objective order"
        assert block["bonuses"]["formula"] == market.OBJECTIVE_BONUS_FORMULA
        wins_row = next(row for row in block["bonuses"]["rows"] if row["kind"] == "wins")
        assert wins_row["basis"].startswith("win once:") and "≥ 1 pays" in wins_row["basis"]
