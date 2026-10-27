"""M6 cross-match ledger (ROADMAP item 10): a season summed out of `sim_events`, and the check on the sum.

Three claims carry this module, and the interesting one is not "the totals add up":

* **The totals are a query, not a counter.** Every figure is recomputed from the rows on the read, so a
  row deleted underneath the ledger changes the next page — no stored season total can drift from the
  table it claims to summarise.
* **The ledger prints its own audit.** Its goal total is set beside `career_fixtures.club_goals` for the
  same matches, a number copied out of the same reports by a different route. When the two disagree the
  sentence names both figures and rewrites neither, and a round whose rows are gone is called a gap —
  never a 0-0.
* **Only the club's own side is counted.** An event belongs to the side that printed it, so an away round
  contributes the club's away events, and an event no id could be found for stays out of the per-player
  rows while its count and its name are still published.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.security import hash_password, new_public_id
from app.main import app
from app.models import Career, CareerFixture, SimulationEvent, SimulationMatch, Team, User
from app.services.simulation import career as career_service
from app.services.simulation import ledger as ledger_service
from app.services.simulation.ledger import CONSISTENCY_FORMULA, LEDGER_FORMULA, LEDGER_LIMIT, ledger_view
from app.services.world import sync_world

BUDGET = 2_000_000
CHANCE_TYPES = ("goal", "shot_saved", "shot_off_target")
CARE = {"manager_name": "Ledger Manager", "philosophy": "balanced", "system_slug": "", "budget": BUDGET}


@pytest.fixture(scope="module")
def world() -> dict[str, Any]:
    """The strongest club in the generated world, and an account to hand it a season to.

    The strongest, not the weakest as §20's tests chose: a ledger over a side that never scores can only
    ever demonstrate zeroes, and the arithmetic this file is about is a goal shared between two readings.
    """
    session = SessionLocal()
    result = sync_world(session)
    assert result.ok, result.errors[:5]
    club = session.scalars(select(Team).where(Team.competition_id.is_not(None)).order_by(Team.overall.desc(), Team.slug).limit(1)).one()
    owner = User(
        id=new_public_id("usr"),
        email=f"ledger-{uuid4().hex[:8]}@example.test",
        password_hash=hash_password("ledger-service-test"),
        display_name="Ledger Owner",
        role="player",
    )
    session.add(owner)
    session.commit()
    data: dict[str, Any] = {"club_id": club.id, "club_short": club.short_name, "owner_id": owner.id}
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
        objectives=[{"kind": "wins", "target": 1, "label": "win once"}],
        season="2026",
        **CARE,
    )


def _season(session: Session, world: dict[str, Any], rounds: int) -> Career:
    career = _career(session, world)
    for _ in range(rounds):
        career_service.play_round(session, career)
    return career


def _match_ids(session: Session, career: Career) -> list[str]:
    """The career's stored matches, oldest first, as the ledger reaches them."""
    return [str(row.match_id) for row in ledger_service.fixtures_of_career(session, career) if row.match_id]


def _club_rows(session: Session, career: Career) -> list[SimulationEvent]:
    """This club's own events over this career's stored matches, gathered without the ledger's SQL."""
    match_ids = _match_ids(session, career)
    if not match_ids:
        return []
    stmt = select(SimulationEvent).where(SimulationEvent.match_id.in_(match_ids))
    if career.club_id:
        stmt = stmt.where(SimulationEvent.team_id == career.club_id)
    return list(session.scalars(stmt).all())


def _open_career(auth_client, world: dict[str, Any], manager_name: str = "Api Manager") -> str:  # type: ignore[no-untyped-def]
    """Open a career over HTTP, so the route's own shape is what the tests then read."""
    response = auth_client.post(
        "/api/v1/careers",
        json={"club": world["club_id"], "manager_name": manager_name, "philosophy": "balanced", "budget": BUDGET, "objectives": [{"kind": "wins", "target": 1, "label": "win once"}]},
    )
    assert response.status_code == 200, response.text
    return str(response.json()["career"]["slug"])


def _season_with_a_goal(session: Session, world: dict[str, Any], rounds: int = 20) -> Career:
    """One career, played round by round until the ledger reports a goal.

    Incremental on purpose: a fresh career per attempt would replay the same opening rounds over again
    and turn a slow world into a slow test suite. The cap is 20, not 8, because a fixture's seed is
    `_digest_seed(career.id, round)` and `career.id` is random — a single unlucky run of eight goalless
    rounds is rare but real, and the helper returns as soon as the first goal lands, so the higher cap
    costs nothing on the common path and removes the flake.
    """
    career = _career(session, world)
    for _ in range(rounds):
        career_service.play_round(session, career)
        if ledger_view(session, career)["totals"]["goals"] > 0:
            return career
    pytest.fail(f"{rounds} rounds at the world's strongest club produced no goal event — the fixture has stopped meaning anything")


def _match_with_a_goal(session: Session, career: Career) -> str:
    """The round the club actually scored in — a test that deletes a goal elsewhere proves nothing.

    The first round of a season is not it: the engine spreads its chances, so an opening fixture can hold
    no goal at all, and the deletion would then change nothing while looking like a passing check.
    """
    return str(next(row.match_id for row in _club_rows(session, career) if row.event_type == "goal"))


class TestTotalsAreTheRows:
    """Every figure is a query over `sim_events`, and nothing but a query."""

    def test_every_club_total_is_what_a_direct_count_of_the_rows_gives(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _season(session, world, 2)
        view = ledger_view(session, career)
        counted = Counter(row.event_type for row in _club_rows(session, career))
        assert view["totals"]["goals"] == counted["goal"]
        assert view["totals"]["yellow_cards"] == counted["yellow_card"]
        assert view["totals"]["red_cards"] == counted["red_card"]
        assert view["totals"]["injuries"] == counted["injury"]
        assert view["totals"]["attempts"] == sum(counted[kind] for kind in CHANCE_TYPES)
        assert view["totals"]["events"] == sum(counted.values())
        assert view["fixtures_played"] == view["fixtures_traced"] == 2
        # `by_type` is built from the rows that exist, so a kind with no row has no key rather than a zero
        # entry. Two fixtures at an average club can legitimately hold no goal — the PostgreSQL leg found
        # exactly that — and a line that indexed `["goal"]` outright was asserting the world's contents
        # rather than the ledger's arithmetic. What has to hold either way is the pairing: a key appears
        # precisely when the rows count it, and its figure is that count.
        assert ("goal" in view["by_type"]) is (counted["goal"] > 0)
        assert view["by_type"].get("goal", {}).get("events", 0) == counted["goal"]

    def test_a_players_goal_count_is_that_players_goal_rows(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _season_with_a_goal(session, world)
        view = ledger_view(session, career)
        identified = [row for row in _club_rows(session, career) if row.attribution == "identified"]
        by_player = Counter((str(row.player_id), row.event_type) for row in identified)
        top = view["players"][0]
        assert top["goals"] > 0 and top["goals"] == by_player[(top["player_id"], "goal")]
        assert top["attempts"] == sum(count for (player, kind), count in by_player.items() if player == top["player_id"] and kind in CHANCE_TYPES)
        assert top["events_by_type"]["goal"] == top["goals"]
        assert sum(row["goals"] for row in view["players"]) <= view["totals"]["goals"], "a goal no id could be found for belongs to the club, not to a name"

    def test_expected_goals_are_summed_off_the_chance_rows(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _season(session, world, 2)
        view = ledger_view(session, career)
        rows = [row for row in _club_rows(session, career) if row.event_type in CHANCE_TYPES]
        assert rows, "two rounds at the strongest side produce chances to sum"
        for player in view["players"]:
            if player["attempts"]:
                expected = round(sum(float(row.expected_goals or 0.0) for row in rows if row.player_id == player["player_id"] and row.attribution == "identified"), 3)
                assert player["expected_goals"] == expected, player["name"]
        club_xg = round(sum(float(row.expected_goals or 0.0) for row in rows), 3)
        assert view["totals"]["expected_goals"] == club_xg

    def test_a_match_a_player_appears_in_is_counted_once_however_many_events_it_holds(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _season(session, world, 3)
        view = ledger_view(session, career)
        rows = [row for row in _club_rows(session, career) if row.attribution == "identified"]
        assert len({str(row.match_id) for row in rows}) > 1, "the fixture needs more than one match to test a per-match count"
        for player in view["players"]:
            mine = [row for row in rows if row.player_id == player["player_id"]]
            assert player["matches_with_events"] == len({str(row.match_id) for row in mine}), player["name"]
            assert 0 < player["matches_with_events"] <= 3
            assert player["matches_with_events"] <= len(mine), "a footprint of matches cannot exceed the events inside them"

    def test_the_page_recomputes_off_the_rows_rather_than_repeating_a_stored_counter(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _season_with_a_goal(session, world)
        before = ledger_view(session, career)
        session.execute(delete(SimulationEvent).where(SimulationEvent.match_id == _match_with_a_goal(session, career), SimulationEvent.event_type == "goal"))
        after = ledger_view(session, career)
        assert after["totals"]["goals"] < before["totals"]["goals"], "a goal the rows no longer hold must not survive on the page"
        assert after["club"] == before["club"] and after["formula"] == before["formula"]

    def test_reading_the_ledger_writes_nothing_back(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _season(session, world, 2)
        session.expire_all()
        rows_before = int(session.scalar(select(func.count()).select_from(SimulationEvent)) or 0)
        first = ledger_view(session, career)
        second = ledger_view(session, career)
        assert first == second, "two reads of one season are the same answer, not two chances to drift"
        assert int(session.scalar(select(func.count()).select_from(SimulationEvent)) or 0) == rows_before
        assert not session.new and not session.dirty and not session.deleted


class TestOnlyTheClubsOwnSide:
    """An event belongs to the side that printed it, whichever end the career's club stood in."""

    def test_the_opposition_is_excluded_by_the_side_not_by_the_fixture(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _season(session, world, 2)
        view = ledger_view(session, career)
        everything = int(session.scalar(select(func.count()).select_from(SimulationEvent).where(SimulationEvent.match_id.in_(_match_ids(session, career)))) or 0)
        assert view["totals"]["events"] < everything, "both sides printed events, so a club total equal to the fixture is counting the opposition"
        assert view["totals"]["events"] == len(_club_rows(session, career))

    def test_an_away_round_contributes_the_clubs_events_from_the_away_side(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _season(session, world, 6)
        away = list(session.scalars(select(CareerFixture).where(CareerFixture.career_id == career.id, CareerFixture.side == "away")).all())
        assert away, "a five-club competition travels away from round five"
        for fixture in away:
            by_team = int(session.scalar(select(func.count()).select_from(SimulationEvent).where(SimulationEvent.match_id == str(fixture.match_id), SimulationEvent.team_id == career.club_id)) or 0)
            by_side = int(session.scalar(select(func.count()).select_from(SimulationEvent).where(SimulationEvent.match_id == str(fixture.match_id), SimulationEvent.side == "away")) or 0)
            assert by_team > 0 and by_team == by_side, f"round {fixture.round_index} stored the wrong end of the fixture"
        assert ledger_view(session, career)["fixtures_traced"] == len(_match_ids(session, career))

    def test_an_event_with_no_id_stays_out_of_the_players_and_is_named_apart(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _season_with_a_goal(session, world)
        view = ledger_view(session, career)
        victim = next(row for row in _club_rows(session, career) if row.event_type == "goal" and row.attribution == "identified")
        name = str(victim.player_name)
        named_before = sum(row["goals"] for row in view["players"])
        ambiguous_before = view["unattributed"]["events"]["ambiguous"]
        session.execute(update(SimulationEvent).where(SimulationEvent.id == victim.id).values(player_id=None, player_slug="", attribution="ambiguous"))
        rewritten = ledger_view(session, career)
        assert rewritten["totals"]["goals"] == view["totals"]["goals"], "the club still scored, whoever the rows cannot name"
        assert rewritten["unattributed"]["events"]["ambiguous"] == ambiguous_before + 1
        assert name in rewritten["unattributed"]["ambiguous_names"]
        assert sum(row["goals"] for row in rewritten["players"]) == named_before - 1


class TestTheLedgerAuditsItself:
    """The second reading of the same season, published whether or not it agrees."""

    def test_a_plain_season_agrees_and_says_which_two_figures_it_compared(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _season(session, world, 2)
        view = ledger_view(session, career)
        goals = sum(int(row.club_goals) for row in ledger_service.fixtures_of_career(session, career) if row.match_id)
        assert view["totals"]["goals"] == goals == view["club_goals_traced"]
        assert "the two readings agree" in view["consistency"]
        assert str(goals) in view["consistency"] and "2 traced fixture(s)" in view["consistency"]

    def test_a_goal_the_rows_lose_makes_the_two_readings_disagree_without_rewriting_either(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _season_with_a_goal(session, world)
        held = {int(row.round_index): int(row.club_goals) for row in ledger_service.fixtures_of_career(session, career)}
        session.execute(delete(SimulationEvent).where(SimulationEvent.match_id == _match_with_a_goal(session, career), SimulationEvent.event_type == "goal"))
        view = ledger_view(session, career)
        assert "the two disagree" in view["consistency"]
        assert str(view["totals"]["goals"]) in view["consistency"] and str(view["club_goals_traced"]) in view["consistency"]
        session.expire_all()
        assert {int(row.round_index): int(row.club_goals) for row in ledger_service.fixtures_of_career(session, career)} == held, "the fixture list is not corrected to match a deleted copy"

    def test_a_fixture_whose_rows_are_gone_is_reported_as_a_gap_not_a_scoreless_match(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _season(session, world, 3)
        session.execute(delete(SimulationEvent).where(SimulationEvent.match_id == _match_ids(session, career)[-1]))
        view = ledger_view(session, career)
        assert view["fixtures_untraced"] == 1 and view["fixtures_traced"] == 2
        assert "gap rather than a disagreement" in view["consistency"] and "the two readings agree" in view["consistency"]
        assert view["consistency"].index("1 played fixture(s) have no rows") > view["consistency"].index("the two readings agree")

    def test_a_deleted_report_takes_its_round_out_of_the_ledger_without_taking_it_out_of_the_season(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _season(session, world, 2)
        match = session.scalars(select(SimulationMatch).where(SimulationMatch.id == _match_ids(session, career)[0])).one()
        session.delete(match)
        session.commit()
        session.expire_all()
        view = ledger_view(session, career)
        fixture = next(row for row in ledger_service.fixtures_of_career(session, career) if row.round_index == 1)
        assert fixture.match_id is None, "the round survives its report as a row with nothing to read"
        assert view["fixtures_played"] == 2 and view["fixtures_traced"] == 1 and view["fixtures_untraced"] == 1
        assert "gap rather than a disagreement" in view["consistency"]

    def test_a_career_that_has_never_played_is_a_sum_over_nothing_and_says_so(self, session, world) -> None:  # type: ignore[no-untyped-def]
        view = ledger_view(session, _career(session, world))
        assert view["players"] == [] and view["by_type"] == {}
        assert view["fixtures_played"] == 0 == view["fixtures_traced"]
        assert view["source"] == "no traced fixture"
        assert "sum over no rows" in view["consistency"]
        assert all(value == 0 for value in view["totals"].values())


class TestWhatThePanelPublishes:
    """The formulas, the fiction label, and the cap on how many names one page shows."""

    def test_the_view_carries_the_formulas_it_was_built_with(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _season(session, world, 1)
        view = ledger_view(session, career)
        assert view["formula"] == LEDGER_FORMULA and view["consistency_formula"] == CONSISTENCY_FORMULA
        assert "player_id" in view["attribution_formula"]
        assert "fiction" in view["disclaimer"]
        assert view["data_origin"] == "simulation" and view["is_demo_data"] is True
        assert view["club"]["team_id"] == career.club_id and view["scope"].startswith("only events whose side")

    def test_a_long_ledger_is_cut_short_out_loud(self, session, world, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        career = _season(session, world, 4)
        full = ledger_view(session, career)
        assert full["players_with_events"] > 2, "four rounds should have involved more than two names"
        monkeypatch.setattr(ledger_service, "LEDGER_LIMIT", 2)
        cut = ledger_view(session, career)
        assert cut["players_shown"] == 2 == len(cut["players"])
        assert cut["players_with_events"] == full["players_with_events"] and cut["truncated"] is True
        assert [row["player_id"] for row in cut["players"]] == [row["player_id"] for row in full["players"][:2]], "the cap keeps the top of the order"
        assert full["truncated"] is False and full["players_with_events"] <= LEDGER_LIMIT, "the cap has to be a real cut, not the page's normal shape"


class TestThroughTheApi:
    """The same figures, reached over HTTP by the account that owns the season."""

    def test_a_career_detail_carries_a_ledger_and_a_list_row_does_not(self, auth_client, session, world) -> None:  # type: ignore[no-untyped-def]
        slug = _open_career(auth_client, world)
        assert auth_client.post(f"/api/v1/careers/{slug}/play").status_code == 200
        detail = auth_client.get(f"/api/v1/careers/{slug}").json()
        listed = auth_client.get("/api/v1/careers").json()["items"][0]
        assert "ledger" in detail and "ledger" not in listed, "a list row is a summary"
        assert detail["ledger"]["formula"] == LEDGER_FORMULA
        assert detail["ledger"]["fixtures_played"] == 1
        stored = session.scalars(select(Career).where(Career.slug == slug)).one()
        assert detail["ledger"]["totals"] == ledger_view(session, stored)["totals"]

    def test_the_report_of_the_match_and_the_ledger_tell_the_same_story_about_one_side(self, auth_client, world) -> None:  # type: ignore[no-untyped-def]
        slug = _open_career(auth_client, world)
        played = auth_client.post(f"/api/v1/careers/{slug}/play").json()
        detail = auth_client.get(played["match"]["path"].replace("/simulate", "/api/v1/simulate")).json()
        side = next(row for row in played["fixtures"] if row["match_slug"] == played["match"]["slug"])["side"]
        club_events = [event for event in detail["report"]["events"] if event["side"] == side]
        assert detail["timeline"]["source"] == "sim_events rows"
        assert played["ledger"]["totals"]["events"] == len(club_events)
        assert played["ledger"]["totals"]["goals"] == sum(1 for event in club_events if event["type"] == "goal")
        assert played["ledger"]["totals"]["goals"] == side_goals(side, detail["report"])

    def test_playing_a_round_moves_the_ledger_by_exactly_that_round(self, auth_client, world) -> None:  # type: ignore[no-untyped-def]
        slug = _open_career(auth_client, world)
        before = auth_client.get(f"/api/v1/careers/{slug}").json()["ledger"]
        played = auth_client.post(f"/api/v1/careers/{slug}/play").json()
        after = played["ledger"]
        fixture = next(row for row in played["fixtures"] if row["match_still_stored"])
        assert before["fixtures_played"] == 0 and after["fixtures_played"] == 1
        assert after["totals"]["events"] > 0 and after["players_with_events"] > 0
        assert after["totals"]["goals"] == int(fixture["club_goals"]) == after["club_goals_traced"]
        assert "the two readings agree" in after["consistency"]

    def test_another_managers_season_is_not_readable_as_a_ledger(self, auth_client, world) -> None:  # type: ignore[no-untyped-def]
        slug = _open_career(auth_client, world)
        assert auth_client.post(f"/api/v1/careers/{slug}/play").status_code == 200
        with _signed_in() as other:
            assert other.get(f"/api/v1/careers/{slug}").status_code == 404


def side_goals(side: str, report: dict[str, Any]) -> int:
    """The goals the match report printed for one side, read off its own score line."""
    return int(report["sides"][side]["goals"])


@contextmanager
def _signed_in() -> Iterator[TestClient]:
    """A second account, so an ownership answer cannot be produced by a coincidence of headers."""
    with TestClient(app) as other:
        response = other.post(
            "/api/v1/auth/register",
            json={"email": f"ledger-other-{uuid4().hex[:8]}@example.test", "password": "strong-pass-1234", "display_name": "Other Manager", "role": "player", "accepts_data_policy": True},
        )
        assert response.status_code == 201, response.text
        other.headers.update({"Authorization": f"Bearer {response.json()['access_token']}"})
        yield other


class TestTheLedgerGoesWithItsSeason:
    """Nothing here is stored apart from the rows, so nothing can outlive them."""

    def test_deleting_every_row_leaves_no_player_and_no_total(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _season(session, world, 2)
        assert ledger_view(session, career)["fixtures_traced"] == 2
        session.execute(delete(SimulationEvent).where(SimulationEvent.match_id.in_(_match_ids(session, career))))
        view = ledger_view(session, career)
        assert view["totals"]["events"] == 0 and view["players"] == [] and view["by_type"] == {}
        assert view["fixtures_played"] == 2 and view["fixtures_traced"] == 0
        assert "no event rows at all" in view["consistency"]

    def test_deleting_the_season_takes_the_fixtures_and_leaves_the_reports_their_rows_belong_to(self, auth_client, session, world) -> None:  # type: ignore[no-untyped-def]
        slug = _open_career(auth_client, world, "Ledger Gone")
        played = auth_client.post(f"/api/v1/careers/{slug}/play").json()
        career_id = str(played["career"]["id"])
        stored = session.scalars(select(SimulationMatch).where(SimulationMatch.slug == played["match"]["slug"])).one()
        assert auth_client.delete(f"/api/v1/careers/{slug}").status_code == 200
        session.expire_all()
        assert session.scalar(select(func.count()).select_from(CareerFixture).where(CareerFixture.career_id == career_id)) == 0
        assert session.scalar(select(func.count()).select_from(SimulationEvent).where(SimulationEvent.match_id == stored.id)) > 0, (
            "a report that survives keeps its rows, and so keeps its own ledger elsewhere"
        )


class TestSeasonLeaders:
    def test_the_leaders_are_the_tops_of_the_rows_and_per90_uses_appearance_minutes(self, session, world) -> None:  # type: ignore[no-untyped-def]
        career = _season(session, world, 3)
        view = ledger_view(session, career)
        block = view["leaders"]
        assert block["per90_formula"] and block["per90_min_minutes"] == 90
        rows = view["players"]
        assert rows and all({"minutes", "appearances", "goals_per90"} <= set(row) for row in rows)
        for row in rows:
            if row["minutes"] > 0:
                assert row["goals_per90"] == round(row["goals"] / row["minutes"] * 90, 2)
            else:
                assert row["goals_per90"] is None, "no appearance minutes means no per-90, not a zero"
        top = block["leaders"]["top_scorer"]
        assert top is not None and top["value"] == max(row["goals"] for row in rows)
        best = block["leaders"]["best_per90"]
        assert best is not None, "eight rounds give at least one player over the minutes floor"
        winner = next(row for row in rows if row["slug"] == best["player_slug"])
        assert winner["minutes"] >= 90 and best["value"] == winner["goals_per90"]
