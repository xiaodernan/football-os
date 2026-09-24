"""M6 stored timeline (ROADMAP item 4): the report's events as rows, and the check that keeps them honest.

Four claims carry this module, and only one of them is "the rows exist":

* **A row is the report's own event, not a retelling.** `event_dict` gives a row back in the shape the
  engine printed, keys included, and the whole list compares equal to `report["events"]` — on real
  match data as well as on the six event shapes pinned by hand below.
* **A disagreement is named, not averaged.** A report rewritten in place keeps its length, so the check
  is field by field, in the report's order, and it says which field and what each side claims. The
  report wins: it is the engine's output, and these rows are a copy of it.
* **A name is not an identity.** Two players of one surname produce an `ambiguous` row that claims no
  player id, because guessing would write one man's record under another's name.
* **No rows is a statement about the table, not about the match.** A match played before this table
  existed says so and has its timeline read off the report — never printed as an empty fixture.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.security import hash_password, new_public_id
from app.models import EVENT_TYPES, RealPlayer, SimulationEvent, SimulationMatch, Team, User
from app.services.simulation import career as career_service
from app.services.simulation.events import (
    ATTRIBUTION_FORMULA,
    TIMELINE_FORMULA,
    build_rows,
    compare_with_report,
    event_dict,
    identities,
    rows_of,
    timeline_of,
    timeline_view,
    write_timeline,
)
from app.services.simulation.profile import SideProfile, team_profile
from app.services.simulation.service import replay_is_identical, run_simulation
from app.services.world import sync_world

BUDGET = 2_000_000
ELEVEN: tuple[tuple[str, str, str], ...] = (
    ("Ana Keeper", "GK", "keeper"),
    ("Bea Doyle", "CB", "defence"),
    ("Cai Marsh", "LB", "defence"),
    ("Dee Allan", "RB", "defence"),
    ("Eli Vance", "CB", "defence"),
    ("Fay Otley", "CDM", "midfield"),
    ("Gus Perry", "CM", "midfield"),
    ("Hal Brodie", "CAM", "midfield"),
    ("Ivo Nash", "LM", "midfield"),
    ("Joy Alden", "RW", "attack"),
    ("Kit Ravel", "ST", "attack"),
)


def _side(*, team_id: str = "T1", name: str = "Northgate United", duplicate: bool = False) -> SideProfile:
    """A profile whose `lineup` and `selected` are the same eleven, as `team_profile` builds them.

    With `duplicate` the ninth slot takes the eleventh slot's name, which is the only case where the
    attribution rule has to refuse to choose.
    """
    lineup = ELEVEN
    if duplicate:
        lineup = (*ELEVEN[:8], ("Kit Ravel", "LM", "midfield"), *ELEVEN[9:])
    selected = tuple((f"{team_id}-p{index}", player.lower().replace(" ", "-"), player, position, band) for index, (player, position, band) in enumerate(lineup))
    return SideProfile(
        team_id=team_id,
        name=name,
        short_name=name.split()[0],
        formation="4-2-3-1",
        system_slug="test",
        system_name="test system",
        attack=0.5,
        midfield=0.5,
        defence=0.5,
        keeper=0.5,
        press=0.5,
        form=0.5,
        overall=0.5,
        tactics={"depth": 30.0, "width": 40.0, "line_separation": 16.0, "space_behind": 12.0, "spacing": 11.0},
        lineup=lineup,
        selected=selected,
    )


def _profile_pair() -> dict[str, SideProfile]:
    return {"home": _side(), "away": _side(team_id="T2", name="Southbank Rovers")}


def _report(events: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "events": events,
        "sides": {
            "home": {"team_id": "T1", "name": "Northgate United", "short_name": "Northgate"},
            "away": {"team_id": "T2", "name": "Southbank Rovers", "short_name": "Southbank"},
        },
    }


def _event(minute: int, kind: str, side: str, player: str, position: str, **extra: Any) -> dict[str, Any]:
    event: dict[str, Any] = {
        "minute": minute,
        "type": kind,
        "side": side,
        "team": "Northgate" if side == "home" else "Southbank",
        "player": player,
        "position": position,
        "detail": f"{kind} involving {player}",
    }
    event.update(extra)
    return event


def _rows_for(*events: dict[str, Any]) -> list[SimulationEvent]:
    """Rows built from a hand-written report: no database, so no dependence on what a draw produced."""
    return build_rows(SimulationMatch(id=new_public_id("sim"), slug="unit-fixture"), _report(list(events)), _profile_pair())


@pytest.fixture(scope="module")
def world() -> dict[str, Any]:
    """Two clubs with a squad apiece, and an account to put the matches under.

    The strongest clubs are deliberate: a timeline of twenty events is a timeline, and a fixture the
    model barely shoots in would let a near-empty list pass the checks below for the wrong reason.
    """
    session = SessionLocal()
    result = sync_world(session)
    assert result.ok, result.errors[:5]
    teams = list(session.scalars(select(Team).where(Team.competition_id.is_not(None)).order_by(Team.overall.desc(), Team.slug).limit(2)))
    assert len(teams) == 2, "the generated world has no two clubs to play"
    owner = User(
        id=new_public_id("usr"),
        email=f"timeline-{teams[0].slug[:8]}@example.test",
        password_hash=hash_password("stored-timeline-service-test"),
        display_name="Timeline Owner",
        role="player",
    )
    session.add(owner)
    session.commit()
    data: dict[str, Any] = {"home_id": teams[0].id, "away_id": teams[1].id, "owner_id": owner.id}
    session.close()
    return data


@pytest.fixture()
def session() -> Iterator[Session]:
    value = SessionLocal()
    try:
        yield value
    finally:
        value.close()


@pytest.fixture()
def match(session: Session, world: dict[str, Any]) -> SimulationMatch:
    """A stored fixture with at least two goals and one booking.

    The seeds are tried in order rather than tuned per assertion: the shape checks below claim things
    about a goal and about a card, and a fixture that happened to contain neither would let both
    assertions pass by checking nothing.
    """
    for seed in range(5150, 5180):
        played = run_simulation(session, owner_id=world["owner_id"], home_team_id=world["home_id"], away_team_id=world["away_id"], seed=seed)
        types = [str(event["type"]) for event in played.report["events"]]
        if types.count("goal") >= 2 and "yellow_card" in types:
            return played
    pytest.skip("no seed in the range produced a fixture with two goals and a booking")


def _rewrite(match: SimulationMatch, index: int, **changes: Any) -> None:
    """Replace one event of a stored report, the way a bad writer would: in place, same length."""
    report = dict(match.report)
    events = [dict(event) for event in report["events"]]
    events[index] = {**events[index], **changes}
    report["events"] = events
    match.report = report


def _clear(session: Session, match: SimulationMatch) -> None:
    for row in rows_of(session, match):
        session.delete(row)
    session.commit()


class TestRowsAreTheReportsEvents:
    def test_every_event_becomes_one_row_in_the_reports_order(self, session: Session, match: SimulationMatch) -> None:
        rows = rows_of(session, match)
        events = match.report["events"]
        assert len(rows) == len(events)
        assert [row.ordinal for row in rows] == list(range(len(events)))
        assert timeline_of(session, match) == events, "a rebuilt event list must equal the report's, key for key"

    def test_the_key_set_follows_the_event_type(self) -> None:
        """The six shapes the engine writes, pinned by hand so an absent type cannot hide a wrong one."""
        rows = _rows_for(
            _event(3, "goal", "home", "Kit Ravel", "ST", chance="big_chance", expected_goals=0.31, score="1-0"),
            _event(14, "shot_saved", "away", "Gus Perry", "CM", chance="normal_chance", expected_goals=0.08),
            _event(22, "shot_off_target", "home", "Joy Alden", "RW", chance="set_piece", expected_goals=0.04),
            _event(37, "yellow_card", "away", "Fay Otley", "CDM"),
            _event(58, "red_card", "home", "Dee Allan", "RB"),
            _event(71, "injury", "away", "Ivo Nash", "LM"),
        )
        assert len(rows) == 6
        by_type = {row.event_type: event_dict(row) for row in rows}
        assert set(by_type) == set(EVENT_TYPES)
        assert set(by_type["goal"]) == {"minute", "type", "side", "team", "player", "position", "detail", "chance", "expected_goals", "score"}
        assert set(by_type["shot_saved"]) == {"minute", "type", "side", "team", "player", "position", "detail", "chance", "expected_goals"}
        assert set(by_type["yellow_card"]) == {"minute", "type", "side", "team", "player", "position", "detail"}
        assert by_type["goal"]["score"] == "1-0"
        assert by_type["goal"]["expected_goals"] == pytest.approx(0.31)
        assert by_type["injury"]["detail"] == "injury involving Ivo Nash"

    def test_a_real_fixture_carries_its_goals_and_bookings_the_same_way(self, session: Session, match: SimulationMatch) -> None:
        """The same rule over drawn data: the column set a type uses is the set its rows use.

        Which types a fixture contains is the draw's business, so no type is asserted to be here — the
        shapes are pinned above. What this checks is that real rows do not leak a scoreline into a
        booking or drop a chance from a shot.
        """
        rows = rows_of(session, match)
        present = {row.event_type for row in rows}
        assert present and present <= set(EVENT_TYPES), f"the engine wrote event types this module does not know: {sorted(present - set(EVENT_TYPES))}"
        assert all(row.score and "-" in row.score for row in rows if row.event_type == "goal")
        assert all(row.chance and row.expected_goals is not None for row in rows if row.event_type in ("goal", "shot_saved", "shot_off_target"))
        assert all(not row.chance and row.expected_goals is None and not row.score for row in rows if row.event_type in ("yellow_card", "red_card", "injury"))
        assert all(row.side in ("home", "away") and row.match_slug == match.slug for row in rows)

    def test_an_identified_event_points_at_a_player_in_the_side_that_printed_him(self, session: Session, match: SimulationMatch) -> None:
        profiles = {
            "home": team_profile(session, match.home_team_id, system_slug=match.home_system or None),
            "away": team_profile(session, match.away_team_id, system_slug=match.away_system or None),
        }
        named = {side: {player_id: name for player_id, _slug, name, _position, _band in profile.selected} for side, profile in profiles.items()}
        rows = [row for row in rows_of(session, match) if row.attribution == "identified"]
        assert rows, "no event was attributed to a player, so the identity rule went untested"
        for row in rows:
            assert row.player_id in named[row.side]
            assert named[row.side][row.player_id] == row.player_name
        player_ids = {row.player_id for row in rows}
        assert None not in player_ids
        for row in rows:
            player = session.get(RealPlayer, str(row.player_id))
            assert player is not None and player.slug == row.player_slug and player.name == row.player_name

    def test_the_timeline_is_never_written_back_into_the_report(self, session: Session, match: SimulationMatch) -> None:
        # The rows hang off the report; the report must not start carrying ids, or every stored digest
        # would disagree with itself and `replay` would stop matching.
        assert "player_id" not in json.dumps(match.report)
        verdict = replay_is_identical(session, match)
        assert verdict["possible"] is True and verdict["identical"] is True, verdict

    def test_rewriting_a_timeline_replaces_it_instead_of_doubling_it(self, session: Session, match: SimulationMatch) -> None:
        sides = {
            "home": team_profile(session, match.home_team_id, system_slug=match.home_system or None),
            "away": team_profile(session, match.away_team_id, system_slug=match.away_system or None),
        }
        before = len(match.report["events"])
        write_timeline(session, match, sides=sides)
        write_timeline(session, match, sides=sides)
        session.commit()
        assert len(rows_of(session, match)) == before
        assert session.scalar(select(func.count()).select_from(SimulationEvent).where(SimulationEvent.match_id == match.id)) == before

    def test_a_match_and_a_ordinal_name_one_row_only(self, session: Session, match: SimulationMatch) -> None:
        """The pair is an event's whole identity, so the table refuses a second claim on it."""
        row = rows_of(session, match)[0]
        session.add(
            SimulationEvent(
                id=new_public_id("sev"),
                match_id=match.id,
                match_slug=match.slug,
                ordinal=row.ordinal,
                minute=120,
                event_type="goal",
                side="home",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


class TestComparisonAgainstTheReport:
    def test_a_fresh_timeline_agrees_and_says_what_it_counted(self, session: Session, match: SimulationMatch) -> None:
        body = compare_with_report(session, match)
        assert body["checked"] == body["report_events"] == len(match.report["events"])
        assert body["agree"] is True
        assert body["offenders"] == []
        assert "agree with the report" in body["verdict"]

    def test_a_renamed_scorer_is_caught_and_the_field_is_named(self, session: Session, match: SimulationMatch) -> None:
        events = match.report["events"]
        goal_index = next((index for index, event in enumerate(events) if event["type"] == "goal"), None)
        assert goal_index is not None, "the fixture has no goal to rewrite"
        original = str(events[goal_index]["player"])
        _rewrite(match, goal_index, player="Nobody On File")
        session.commit()
        body = compare_with_report(session, match)
        assert body["agree"] is False
        assert any("player" in offender for offender in body["offenders"])
        assert "Nobody On File" in body["verdict"] and original in body["verdict"]
        # The report is treated as the record: the rows are reported as wrong, never rewritten to match.
        assert "the report is the engine's output" in body["verdict"]
        assert rows_of(session, match)[goal_index].player_name == original

    def test_a_moved_minute_is_caught_even_though_the_length_is_unchanged(self, session: Session, match: SimulationMatch) -> None:
        _rewrite(match, 0, minute=int(match.report["events"][0]["minute"]) + 7)
        session.commit()
        body = compare_with_report(session, match)
        assert body["checked"] == body["report_events"]
        assert body["agree"] is False
        assert any("minute" in offender for offender in body["offenders"])

    def test_a_lost_row_is_reported_as_a_count_and_not_as_silence(self, session: Session, match: SimulationMatch) -> None:
        row = rows_of(session, match)[0]
        session.delete(row)
        session.commit()
        body = compare_with_report(session, match)
        assert body["agree"] is False
        assert any("rows are stored" in offender for offender in body["offenders"])

    def test_a_match_with_no_rows_names_the_table_rather_than_the_match(self, session: Session, match: SimulationMatch) -> None:
        _clear(session, match)
        body = compare_with_report(session, match)
        assert body["checked"] == 0
        assert body["report_events"] == len(match.report["events"]) > 0
        assert body["agree"] is False
        assert "played before the events table existed" in body["verdict"]

    def test_a_report_with_no_events_and_no_rows_is_not_called_stale(self, session: Session, match: SimulationMatch) -> None:
        match.report = {**match.report, "events": []}
        _clear(session, match)
        body = compare_with_report(session, match)
        assert body["agree"] is True
        assert "no rows and no events" in body["verdict"]

    def test_the_offender_list_is_capped_and_the_verdict_says_the_true_number(self, session: Session, match: SimulationMatch) -> None:
        report = dict(match.report)
        report["events"] = [{**event, "detail": "rewritten"} for event in report["events"]]
        match.report = report
        session.commit()
        body = compare_with_report(session, match)
        total = len(match.report["events"])
        assert total > 3
        assert len(body["offenders"]) == 3
        assert f"{total} of {total} events disagree" in body["verdict"]


class TestAttribution:
    def test_a_name_the_eleven_prints_once_becomes_the_players_own_row(self) -> None:
        rows = _rows_for(_event(12, "goal", "home", "Kit Ravel", "ST", chance="big_chance", expected_goals=0.31, score="1-0"))
        assert [row.attribution for row in rows] == ["identified"]
        assert rows[0].player_id == "T1-p10"
        assert rows[0].player_slug == "kit-ravel"
        assert rows[0].team_id == "T1"

    def test_two_players_of_one_name_claim_neither(self) -> None:
        report = _report([_event(31, "shot_saved", "home", "Kit Ravel", "LM", chance="normal_chance", expected_goals=0.08)])
        rows = build_rows(SimulationMatch(id=new_public_id("sim"), slug="unit-fixture"), report, {"home": _side(duplicate=True), "away": _side(team_id="T2", name="Southbank Rovers")})
        assert [row.attribution for row in rows] == ["ambiguous"]
        assert rows[0].player_id is None
        assert rows[0].player_slug == ""
        # The name is still printed and the club is still known: only the identity is refused.
        assert rows[0].player_name == "Kit Ravel"
        assert rows[0].team_id == "T1"

    def test_a_name_outside_the_eleven_is_unnamed(self) -> None:
        rows = _rows_for(_event(44, "yellow_card", "home", "A Strangers Name", ""))
        assert rows[0].attribution == "unnamed"
        assert rows[0].player_id is None

    def test_a_side_with_no_profile_keeps_its_club_and_claims_no_player(self) -> None:
        report = _report([_event(58, "injury", "away", "Southbank", "")])
        rows = build_rows(SimulationMatch(id=new_public_id("sim"), slug="unit-fixture"), report, {"home": _side()})
        assert rows[0].side == "away"
        assert rows[0].team_id == "T2", "the report's own side block names the club, so the row can too"
        assert rows[0].attribution == "unnamed"
        assert rows[0].player_id is None

    def test_identities_lists_every_row_behind_a_shared_name(self) -> None:
        found = identities(_side(duplicate=True))
        assert len(found["Kit Ravel"]) == 2
        assert len(found["Ana Keeper"]) == 1
        assert found["Kit Ravel"][0][1] == "kit-ravel"


class TestWhatAReaderGets:
    def test_the_view_says_where_the_events_came_from_and_how_the_types_split(self, session: Session, match: SimulationMatch) -> None:
        body = timeline_view(session, match)
        events = match.report["events"]
        assert body["source"] == "sim_events rows"
        assert body["count"] == body["stored_rows"] == body["report_events"] == len(events)
        assert sum(body["by_type"].values()) == len(events)
        assert body["by_type"].get("goal", 0) == sum(1 for event in events if event["type"] == "goal")
        assert body["events"] == events
        assert "agree with the report" in body["consistency"]
        assert body["identified"] > 0
        assert body["identified"] <= body["stored_rows"]
        assert body["formula"] == TIMELINE_FORMULA
        assert body["attribution_formula"] == ATTRIBUTION_FORMULA
        assert "fictional" in body["disclaimer"]
        assert body["data_origin"] == "simulation" and body["is_demo_data"] is True

    def test_the_view_falls_back_to_the_report_and_says_that_is_what_it_did(self, session: Session, match: SimulationMatch) -> None:
        _clear(session, match)
        body = timeline_view(session, match)
        assert body["source"] == "the match report's own JSON"
        assert body["stored_rows"] == 0
        assert body["count"] == body["report_events"] == len(match.report["events"])
        assert body["events"] == match.report["events"], "a fallback must still show the timeline, not a blank"
        assert "before the events table existed" in body["source_note"]
        assert "played before the events table existed" in body["consistency"]

    def test_a_career_round_gets_a_timeline_the_same_way(self, session: Session, world: dict[str, Any]) -> None:
        """The career path calls the same `run_simulation`, so a played round is addressable too."""
        career = career_service.create_career(
            session,
            owner_id=world["owner_id"],
            club=career_service.resolve_club(session, world["home_id"]),
            manager_name="Timeline Manager",
            philosophy="balanced",
            system_slug="",
            budget=BUDGET,
            objectives=[{"kind": "wins", "target": 1, "label": "win once"}],
            season="2026",
        )
        fixture, played = career_service.play_round(session, career)
        assert fixture.match_id == played.id
        events = played.report["events"]
        rows = rows_of(session, played)
        assert len(rows) == len(events) > 0
        assert compare_with_report(session, played)["agree"] is True
        assert [row.match_slug for row in rows] == [played.slug] * len(events)


class TestRowsLeaveWithTheirMatch:
    def test_deleting_a_match_takes_its_timeline(self, session: Session, world: dict[str, Any]) -> None:
        played = run_simulation(session, owner_id=world["owner_id"], home_team_id=world["home_id"], away_team_id=world["away_id"], seed=777)
        count = len(played.report["events"])
        assert count > 0
        match_id = played.id
        session.delete(played)
        session.commit()
        session.expire_all()
        assert session.scalar(select(func.count()).select_from(SimulationEvent).where(SimulationEvent.match_id == match_id)) == 0


class TestThroughTheApi:
    def test_a_detail_carries_the_timeline_and_a_list_row_does_not(self, auth_client, world) -> None:  # type: ignore[no-untyped-def]
        played = auth_client.post("/api/v1/simulate", json={"home_team": world["home_id"], "away_team": world["away_id"], "seed": 20260925}).json()
        detail = auth_client.get(f"/api/v1/simulate/{played['slug']}").json()
        timeline = detail["timeline"]
        assert timeline["events"] == played["report"]["events"]
        assert timeline["source"] == "sim_events rows"
        assert "agree with the report" in timeline["consistency"]
        assert timeline["count"] == len(played["report"]["events"])
        listed = auth_client.get("/api/v1/simulate").json()["items"][0]
        assert "timeline" not in listed, "a list row is a summary"
        assert "report" not in listed

    def test_a_match_played_over_http_has_rows_on_disk(self, auth_client, session, world) -> None:  # type: ignore[no-untyped-def]
        played = auth_client.post("/api/v1/simulate", json={"home_team": world["home_id"], "away_team": world["away_id"], "seed": 606}).json()
        stored = session.scalars(select(SimulationMatch).where(SimulationMatch.id == played["id"])).one()
        assert len(rows_of(session, stored)) == len(played["report"]["events"])
        assert session.scalar(select(func.count()).select_from(SimulationEvent).where(SimulationEvent.match_slug == stored.slug)) == len(played["report"]["events"])

    def test_deleting_over_http_takes_the_rows(self, auth_client, session, world) -> None:  # type: ignore[no-untyped-def]
        played = auth_client.post("/api/v1/simulate", json={"home_team": world["home_id"], "away_team": world["away_id"], "seed": 607}).json()
        assert auth_client.delete(f"/api/v1/simulate/{played['slug']}").status_code == 204
        session.expire_all()
        assert session.scalar(select(func.count()).select_from(SimulationEvent).where(SimulationEvent.match_id == played["id"])) == 0
