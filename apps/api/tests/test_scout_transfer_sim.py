"""M7's transfer simulation — a projection tested hardest for the one thing it claims.

Every other claim in this tier is arithmetic the project already publishes and re-checks elsewhere, so the tests
here concentrate on the four things that are new:

* **nothing is written.** The claim is that a simulation is not a transaction, so the load-bearing test counts the
  rows a real signing would create — sim matches, squad moves, wage charges — plus the career's own budget and
  fixture list, runs a full projection, and requires every one of them unchanged. A test that only asserted
  `"writes": "nothing"` in a rules block would pass while the code committed matches;
* **the two lines of a round differ only by the eleven.** The same seed has to appear in both, and the two sides
  have to be built from `team_profile` over the same rows with and without one added player;
* **the arithmetic beside the projection** — fee, clause, wage, the standing committed rate, the rounds the money
  left after the fee would carry this player, the need band and the fit — are each re-derived here by calling the
  market function directly, not by reading the payload's own formula string;
* **refusals carry figures**, and the caps that trigger them live in the service rather than in pydantic, so a
  client sees the number it got wrong.

The projection is stochastic, so no test here asserts a scoreline. They assert that the same seed was used twice,
that the totals equal the sum of the printed rounds, and that a player who is not selected changes nothing at all.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.main import app
from app.models import Career, CareerFixture, CareerSquadMove, CareerWageCharge, RealPlayer, SimulationMatch, Team
from app.services.scouting.transfer_sim import (
    DEFAULT_ROUNDS,
    MAX_ROUNDS,
    REFUSALS,
    SIMULATION_RULE,
    TransferRefusal,
    limitations,
    not_does,
    rules,
    simulate_transfer,
    transfer_sim_counts,
    transfer_sim_ready,
)
from app.services.simulation import market
from app.services.simulation.career import next_fixture_plan
from app.services.simulation.profile import team_profile
from app.services.world import sync_world, world_ready

SIMULATE = "/api/v1/scout/simulate-transfer"
CAREERS = "/api/v1/careers"
PASSWORD = "strong-pass-1234"


@pytest.fixture(scope="module")
def world() -> dict[str, Any]:
    """A seeded world plus one career to project for, and the two players the tests need."""
    session = SessionLocal()
    try:
        sync_world(session)
        assert world_ready(session)
        rows = list(session.scalars(select(RealPlayer).order_by(RealPlayer.slug)).all())
        club = session.scalars(select(Team).order_by(Team.overall, Team.slug).limit(1)).one()
        outsider = max((row for row in rows if row.team_id != club.id), key=lambda row: (int(row.overall), row.slug))
        teammate = min((row for row in rows if row.team_id == club.id), key=lambda row: (int(row.overall), row.slug))
        weakest_out = min((row for row in rows if row.team_id != club.id), key=lambda row: (int(row.overall), row.slug))
        client = _account("Sim Manager")
        created = client.post(
            CAREERS,
            json={"club": club.id, "manager_name": "Sim Manager", "philosophy": "balanced", "budget": 6_000_000, "objectives": [{"kind": "wins", "target": 1, "label": "win once"}]},
        )
        assert created.status_code == 200, created.text
        return {
            "club_id": club.id,
            "career_slug": created.json()["career"]["slug"],
            "outsider": outsider.slug,
            "teammate": teammate.slug,
            "weakest_out": weakest_out.slug,
            "players": len(rows),
        }
    finally:
        session.close()


@pytest.fixture()
def session(world: dict[str, Any]) -> Iterator[Session]:
    """A session over the seeded world, so a subset run never reads an empty pool."""
    row = SessionLocal()
    try:
        yield row
    finally:
        row.close()


def _own_career(client: TestClient, club_id: str, label: str) -> str:
    """A career the calling account actually owns — the route refuses anybody else's before it looks at a player."""
    response = client.post(
        CAREERS,
        json={"club": club_id, "manager_name": label, "philosophy": "balanced", "budget": 6_000_000, "objectives": [{"kind": "wins", "target": 1, "label": "win once"}]},
    )
    assert response.status_code == 200, response.text
    return str(response.json()["career"]["slug"])


def _account(name: str = "Sim Manager") -> TestClient:
    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/register",
        json={"email": f"tsim-{uuid4().hex[:8]}@example.test", "password": PASSWORD, "display_name": name, "role": "player", "accepts_data_policy": True},
    )
    assert response.status_code == 201, response.text
    client.headers.update({"Authorization": f"Bearer {response.json()['access_token']}"})
    return client


def _career(session: Session, slug: str) -> Career:
    row = session.scalar(select(Career).where(Career.slug == slug))
    assert row is not None, slug
    return row


def _row(session: Session, slug: str) -> RealPlayer:
    player = session.scalar(select(RealPlayer).where(RealPlayer.slug == slug))
    assert player is not None, slug
    return player


def _written(session: Session, career: Career) -> dict[str, int]:
    """Everything a real signing would have changed, counted before and after a projection."""
    return {
        "sim_matches": int(session.scalar(select(func.count()).select_from(SimulationMatch)) or 0),
        "move_rows": int(session.scalar(select(func.count()).select_from(CareerSquadMove)) or 0),
        "wage_rows": int(session.scalar(select(func.count()).select_from(CareerWageCharge)) or 0),
        "fixtures": int(session.scalar(select(func.count()).select_from(CareerFixture).where(CareerFixture.career_id == career.id)) or 0),
        "budget": int(career.budget),
        "rounds_played": int(career.rounds_played),
        "players": int(session.scalar(select(func.count()).select_from(RealPlayer)) or 0),
    }


class TestNothingIsWritten:
    """The claim the whole tier rests on, checked by counting what a transaction would have created."""

    def test_a_projection_leaves_every_table_it_could_have_written_alone(self, session: Session, world: dict[str, Any]) -> None:
        career = _career(session, world["career_slug"])
        before = _written(session, career)
        result = simulate_transfer(session, career, player=world["outsider"], rounds=DEFAULT_ROUNDS)
        session.expire_all()
        after = _written(session, _career(session, world["career_slug"]))
        assert result["projection"]["rounds_projected"] >= 1, "a projection that projected nothing would pass this test vacuously"
        assert after == before

    def test_the_rules_say_so_and_the_payload_prints_what_it_does_not_do(self, session: Session, world: dict[str, Any]) -> None:
        career = _career(session, world["career_slug"])
        result = simulate_transfer(session, career, player=world["outsider"], rounds=1)
        assert result["rules"]["writes"].startswith("nothing")
        assert len(result["what_this_does_not_do"]) == 5
        assert any("buy" in line for line in result["what_this_does_not_do"]), "the market route is named as the door that is not opened here"
        assert result["what_this_does_not_do"] == not_does()

    def test_the_published_counts_report_zero_rows_written_by_a_simulation(self, session: Session) -> None:
        assert transfer_sim_counts(session)["rows_written_by_a_simulation"] == 0
        assert transfer_sim_ready(session) is True


class TestSameSeedTwoElevens:
    """Both lines of a round come from the same seed, and the only input that moves is the squad."""

    def test_every_projected_round_carries_one_seed_for_both_lines(self, session: Session, world: dict[str, Any]) -> None:
        career = _career(session, world["career_slug"])
        result = simulate_transfer(session, career, player=world["outsider"], rounds=3)
        assert len(result["projection"]["rounds"]) == 3
        for line in result["projection"]["rounds"]:
            assert line["same_seed"] is True, "the round says it held one seed; both of its own lines have to agree"
            assert isinstance(line["seed"], int) and line["seed"] > 0
            assert int(line["without"]["seed"]) == int(line["with_signing"]["seed"]) == int(line["seed"])
            assert line["without"]["outcome"] in {"W", "D", "L"} and line["with_signing"]["outcome"] in {"W", "D", "L"}

    def test_the_rounds_follow_the_rotation_the_career_would_really_play(self, session: Session, world: dict[str, Any]) -> None:
        career = _career(session, world["career_slug"])
        result = simulate_transfer(session, career, player=world["outsider"], rounds=3)
        for line in result["projection"]["rounds"]:
            plan = next_fixture_plan(session, career, round_index=int(line["round_index"]))
            assert line["opponent"] == plan["opponent_name"] and line["side"] == plan["side"] and line["seed"] == int(plan["seed"])

    def test_the_two_sides_are_built_from_the_same_rows_plus_one(self, session: Session, world: dict[str, Any]) -> None:
        career = _career(session, world["career_slug"])
        result = simulate_transfer(session, career, player=world["outsider"], rounds=1)
        before_ids = {str(row["player_id"]) for row in result["side"]["before"]["eleven"]}
        after_ids = {str(row["player_id"]) for row in result["side"]["after"]["eleven"]}
        signing = _row(session, world["outsider"])
        assert signing.id not in before_ids
        assert result["squad"]["size_after"] == result["squad"]["size_before"] + 1
        assert (signing.id in after_ids) == (str(signing.id) in {str(row["player_id"]) for row in result["side"]["comes_in"]})
        assert len(result["side"]["before"]["eleven"]) == len(result["side"]["after"]["eleven"]) == 11, "a side is eleven with or without the signing"

    def test_a_player_good_enough_to_start_is_the_one_who_moves_the_eleven(self, session: Session, world: dict[str, Any]) -> None:
        career = _career(session, world["career_slug"])
        result = simulate_transfer(session, career, player=world["outsider"], rounds=1)
        signing = _row(session, world["outsider"])
        after_ids = {str(row["player_id"]) for row in result["side"]["after"]["eleven"]}
        assert str(signing.id) in after_ids, "the strongest outside row in a 300-player world should start somewhere"
        assert result["side"]["comes_in"] and result["side"]["goes_out"], "an addition that starts must displace exactly one name"

    def test_a_signing_who_would_bench_changes_nothing_about_the_side(self, session: Session, world: dict[str, Any]) -> None:
        career = _career(session, world["career_slug"])
        result = simulate_transfer(session, career, player=world["weakest_out"], rounds=1)
        assert result["side"]["eleven_unchanged"] is True
        assert result["side"]["comes_in"] == [] and result["side"]["goes_out"] == []
        assert result["side"]["indices_delta"] == {key: 0.0 for key in result["side"]["before"]["indices"]}
        assert result["squad"]["size_after"] == result["squad"]["size_before"] + 1, "the squad still grew; only the eleven did not"


class TestPriceAndNeedArithmetic:
    """Every figure beside the projection is re-taken from the market's own functions."""

    def test_the_price_is_the_valuation_of_the_row_as_it_stands(self, session: Session, world: dict[str, Any]) -> None:
        career = _career(session, world["career_slug"])
        player = _row(session, world["outsider"])
        valuation = market.valuation(player)
        cost = simulate_transfer(session, career, player=world["outsider"], rounds=1)["cost"]
        assert cost["asking_fee"] == int(valuation["asking_fee"])
        assert cost["release_clause"] == int(valuation["release_clause"])
        assert cost["weekly_wage"] == int(valuation["weekly_wage"])
        assert cost["season_wage"] == int(valuation["weekly_wage"]) * 52
        assert cost["contract_years"] == int(valuation["contract_years"])

    def test_affordability_is_compared_to_the_balance_the_market_reports(self, session: Session, world: dict[str, Any]) -> None:
        career = _career(session, world["career_slug"])
        balance = market.budget_position(session, career)
        cost = simulate_transfer(session, career, player=world["outsider"], rounds=1)["cost"]
        assert cost["remaining_now"] == int(balance["remaining"])
        assert cost["affordable_by_fee"] == (cost["asking_fee"] <= cost["remaining_now"])
        assert cost["headroom_after_fee"] == cost["remaining_now"] - cost["asking_fee"]

    def test_the_wage_is_added_to_the_standing_committed_rate_not_invented(self, session: Session, world: dict[str, Any]) -> None:
        career = _career(session, world["career_slug"])
        standing = market.wage_bill(session, career, round_index=int(career.rounds_played) + 1)
        cost = simulate_transfer(session, career, player=world["outsider"], rounds=1)["cost"]
        assert cost["wage_committed_per_week"] == int(standing["fee"])
        assert cost["wage_after_this_player_per_week"] == int(standing["fee"]) + cost["weekly_wage"]
        assert cost["season_wage_after"] == cost["wage_after_this_player_per_week"] * 52

    def test_rounds_the_wage_bills_for_divides_the_leftovers_by_the_weekly_figure(self, session: Session, world: dict[str, Any]) -> None:
        career = _career(session, world["career_slug"])
        cost = simulate_transfer(session, career, player=world["outsider"], rounds=1)["cost"]
        assert cost["rounds_the_wage_bills_for"] == (cost["remaining_now"] - cost["asking_fee"]) // max(cost["weekly_wage"], 1)
        assert isinstance(cost["rounds_the_wage_bills_for"], int), "a whole number of rounds, not a fraction that flatters the deal"

    def test_the_need_band_and_the_fit_are_the_market_s_own_answer(self, session: Session, world: dict[str, Any]) -> None:
        career = _career(session, world["career_slug"])
        round_index = int(career.rounds_played) + 1
        need = market.club_need(session, career, round_index=round_index)
        result = simulate_transfer(session, career, player=world["outsider"], rounds=1)
        assert result["need"]["needed_band"] == need["needed_band"]
        assert result["need"]["as_of_round"] == round_index
        assert result["need"]["this_player_fills_it"] == (result["player"]["band"] == str(need["needed_band"]))
        fit = market.tactical_fit(_row(session, world["outsider"]), str(need["needed_band"]))
        assert result["fit"]["fit"] == pytest.approx(float(fit["fit"])) and result["fit"]["formula"] == market.FIT_FORMULA

    def test_the_squad_rule_is_can_field_side_on_both_sides_of_the_signing(self, session: Session, world: dict[str, Any]) -> None:
        career = _career(session, world["career_slug"])
        squad = list(session.scalars(select(RealPlayer).where(RealPlayer.team_id == career.club_id)))
        result = simulate_transfer(session, career, player=world["outsider"], rounds=1)["squad"]
        assert result["fielding_before"] == market.can_field_side(squad)
        assert result["fielding_after"] == market.can_field_side([*squad, _row(session, world["outsider"])])


class TestProjectionArithmetic:
    """The aggregate is the sum of the printed rounds, and nothing else."""

    def test_totals_and_verdict_counters_equal_the_rounds_printed(self, session: Session, world: dict[str, Any]) -> None:
        career = _career(session, world["career_slug"])
        projection = simulate_transfer(session, career, player=world["outsider"], rounds=3)["projection"]
        points = {"W": 3, "D": 1, "L": 0}
        for key in ("without", "with_signing"):
            lines = [line[key] for line in projection["rounds"]]
            assert projection["totals"][key]["goals"] == sum(int(row["for"]) for row in lines)
            assert projection["totals"][key]["against"] == sum(int(row["against"]) for row in lines)
            assert projection["totals"][key]["points"] == sum(points[str(row["outcome"])] for row in lines)
        assert projection["points_delta"] == projection["totals"]["with_signing"]["points"] - projection["totals"]["without"]["points"]
        assert projection["better"] + projection["same"] + projection["worse"] == projection["rounds_projected"]
        assert projection["rounds_asked"] == 3 and projection["rounds_projected"] <= 3

    def test_the_projection_is_deterministic_across_two_calls(self, session: Session, world: dict[str, Any]) -> None:
        career = _career(session, world["career_slug"])
        first = simulate_transfer(session, career, player=world["outsider"], rounds=2)["projection"]
        second = simulate_transfer(session, career, player=world["outsider"], rounds=2)["projection"]
        assert first == second, "the same seed against the same two elevens cannot answer twice differently"

    def test_the_seed_rule_is_printed_in_the_payload_that_used_it(self, session: Session, world: dict[str, Any]) -> None:
        career = _career(session, world["career_slug"])
        result = simulate_transfer(session, career, player=world["outsider"], rounds=1)
        assert result["projection"]["rule"] == SIMULATION_RULE
        assert "stochastic" in result["projection"]["one_sample"]
        assert len(result["limitations"]) >= 6 and result["limitations"] == limitations()


class TestRefusals:
    """Each refusal prints the number the reader needs in order to check the sentence."""

    def test_a_player_already_on_the_club_s_books_is_refused_by_name(self, session: Session, world: dict[str, Any]) -> None:
        career = _career(session, world["career_slug"])
        with pytest.raises(TransferRefusal) as raised:
            simulate_transfer(session, career, player=world["teammate"])
        assert raised.value.code == "already_at_this_club" and raised.value.figures["player"] == world["teammate"]

    def test_an_unknown_player_and_an_out_of_range_window_are_both_named_with_figures(self, session: Session, world: dict[str, Any]) -> None:
        career = _career(session, world["career_slug"])
        with pytest.raises(TransferRefusal) as who:
            simulate_transfer(session, career, player="definitely-not-here")
        assert who.value.code == "no_such_player" and who.value.figures["ident"] == "definitely-not-here"
        with pytest.raises(TransferRefusal) as how_many:
            simulate_transfer(session, career, player=world["outsider"], rounds=MAX_ROUNDS + 4)
        assert how_many.value.code == "bad_rounds" and how_many.value.figures == {"rounds": MAX_ROUNDS + 4, "min": 1, "max": MAX_ROUNDS}

    def test_zero_and_negative_rounds_are_refused_rather_than_projecting_nothing(self, session: Session, world: dict[str, Any]) -> None:
        """The lower bound matters as much as the upper one.

        A `rounds` of 0 does not fail: it returns an empty projection, and the route would then answer 200 with a
        table of no rounds, a totals block of zeroes, and a `points_delta` that looks like a finding. A mutation
        that dropped `wanted < 1` from the guard slipped past this file's other bound check for exactly that reason.
        """
        career = _career(session, world["career_slug"])
        for asked in (0, -3):
            with pytest.raises(TransferRefusal) as raised:
                simulate_transfer(session, career, player=world["outsider"], rounds=asked)
            assert raised.value.code == "bad_rounds", asked
            assert raised.value.figures == {"rounds": asked, "min": 1, "max": MAX_ROUNDS}

    def test_a_projection_always_carries_at_least_one_round(self, session: Session, world: dict[str, Any]) -> None:
        """The empty answer is the failure mode the bound above exists to keep out of the payload."""
        career = _career(session, world["career_slug"])
        for asked in (1, 2, 3):
            projection = simulate_transfer(session, career, player=world["outsider"], rounds=asked)["projection"]
            assert projection["rounds_projected"] >= 1, "an empty projection must not be reportable as a result"
            assert projection["rounds"] and projection["totals"]["without"]["points"] >= 0

    def test_a_retired_career_has_no_future_to_project(self, session: Session, world: dict[str, Any]) -> None:
        career = _career(session, world["career_slug"])
        career.status = "retired"
        session.flush()
        try:
            with pytest.raises(TransferRefusal) as raised:
                simulate_transfer(session, career, player=world["outsider"])
            assert raised.value.code == "retired_career" and raised.value.figures["status"] == "retired"
        finally:
            career.status = "active"
            session.flush()

    def test_a_closed_challenge_window_refuses_before_any_round_is_replayed(self, session: Session, world: dict[str, Any]) -> None:
        career = _career(session, world["career_slug"])
        career.challenge_window, career.rounds_played, career.challenge_slug = 2, 2, "test-window"
        session.flush()
        try:
            with pytest.raises(TransferRefusal) as raised:
                simulate_transfer(session, career, player=world["outsider"])
            assert raised.value.code == "window_closed"
            assert raised.value.figures == {"career": career.slug, "played": 2, "window": 2, "challenge_slug": "test-window"}
        finally:
            career.challenge_window, career.rounds_played, career.challenge_slug = 0, 0, ""
            session.flush()

    def test_the_published_codes_are_exactly_the_three_answer_shapes(self) -> None:
        from app.services.scouting.transfer_sim import CONFLICT_CODES, NOT_FOUND_CODES, UNPROCESSABLE_CODES

        classified = NOT_FOUND_CODES | UNPROCESSABLE_CODES | CONFLICT_CODES
        assert set(REFUSALS) == set(classified), sorted(set(REFUSALS) - classified)
        assert len(classified) == len(REFUSALS), "a code sits in two shapes"
        assert rules()["refusals"] == list(REFUSALS)


class TestRoutes:
    """The door a browser uses, checked for the same claims plus its own answer shapes."""

    def test_the_route_answers_a_projection_and_writes_nothing(self, session: Session, world: dict[str, Any]) -> None:
        client = _account("Route Manager")
        slug = _own_career(client, str(world["club_id"]), "Route Manager")
        career = _career(session, slug)
        before = _written(session, career)
        response = client.post(SIMULATE, json={"career": slug, "player": world["outsider"], "rounds": 2})
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["asked_for"] == {"career": slug, "player": world["outsider"], "rounds": 2}
        assert payload["career"]["slug"] == slug and payload["career"]["club_id"] == str(world["club_id"])
        assert len(payload["projection"]["rounds"]) == 2 and payload["projection"]["rounds_asked"] == 2
        assert payload["data_origin"] == "synthetic" and payload["is_demo_data"] is True and payload["demo_data"] is True
        session.expire_all()
        assert _written(session, _career(session, slug)) == before

    def test_a_foreign_career_is_not_a_projection_anyone_can_make(self, world: dict[str, Any]) -> None:
        owner, other = _account("Owner"), _account("Other")
        slug = _own_career(owner, str(world["club_id"]), "Owner")
        response = other.post(SIMULATE, json={"career": slug, "player": world["outsider"]})
        assert response.status_code == 404, response.text
        assert response.json()["detail"]["code"] == "not_found"

    def test_a_bad_round_count_reaches_the_service_that_prints_the_window(self, world: dict[str, Any]) -> None:
        client = _account("Bounds Manager")
        slug = _own_career(client, str(world["club_id"]), "Bounds Manager")
        response = client.post(SIMULATE, json={"career": slug, "player": world["outsider"], "rounds": 99})
        assert response.status_code == 422, response.text
        assert response.json()["detail"]["code"] == "bad_rounds", "pydantic must not pre-empt the refusal that carries the figures"
        assert response.json()["detail"]["max"] == MAX_ROUNDS

    def test_an_unknown_player_answers_404_from_the_route_too(self, world: dict[str, Any]) -> None:
        client = _account("Missing Manager")
        slug = _own_career(client, str(world["club_id"]), "Missing Manager")
        response = client.post(SIMULATE, json={"career": slug, "player": "definitely-not-here"})
        assert response.status_code == 404 and response.json()["detail"]["code"] == "no_such_player"

    def test_an_anonymous_caller_is_turned_away(self) -> None:
        assert TestClient(app).post(SIMULATE, json={"career": "x", "player": "y"}).status_code in (401, 403)

    def test_the_rules_endpoint_publishes_the_tier_and_its_answer_shapes(self) -> None:
        published = TestClient(app).get("/api/v1/scout/rules").json()["transfer_simulation"]
        assert set(published["refusals"]) <= set(REFUSALS)
        assert published["default_rounds"] == DEFAULT_ROUNDS and published["max_rounds"] == MAX_ROUNDS
        assert published["writes"] == "nothing: no sim match row, no move row, no wage charge, no budget change, no listing, no offer"
        assert published["ready"] is True and published["counts"]["rows_written_by_a_simulation"] == 0

    def test_capabilities_reports_the_tier_and_says_it_writes_nothing(self) -> None:
        flags = TestClient(app).get("/api/v1/capabilities").json()
        assert flags["m7_transfer_simulation"]["ready"] is True
        assert flags["m7_transfer_simulation"]["writes"] == "nothing"
        assert flags["m7_transfer_simulation"]["counts"]["max_rounds"] == MAX_ROUNDS


class TestFixturePlannerSeam:
    """The round-number seam the projection depends on, including the default every older caller uses."""

    def test_the_default_plan_is_still_the_round_after_the_last_one_played(self, session: Session, world: dict[str, Any]) -> None:
        career = _career(session, world["career_slug"])
        implicit = next_fixture_plan(session, career)
        explicit = next_fixture_plan(session, career, round_index=int(career.rounds_played) + 1)
        assert implicit == explicit
        assert implicit["round_index"] == int(career.rounds_played) + 1

    def test_reading_ahead_does_not_move_the_career(self, session: Session, world: dict[str, Any]) -> None:
        career = _career(session, world["career_slug"])
        before = (int(career.rounds_played), int(career.budget))
        far = next_fixture_plan(session, career, round_index=12)
        assert far["available"] is True and far["round_index"] == 12
        assert (int(career.rounds_played), int(career.budget)) == before
        assert far["seed"] != next_fixture_plan(session, career, round_index=11)["seed"]

    def test_a_side_flips_when_the_career_reaches_the_second_cycle(self, session: Session, world: dict[str, Any]) -> None:
        career = _career(session, world["career_slug"])
        first = next_fixture_plan(session, career, round_index=1)
        opponents = int(first["of"])
        assert opponents == len(list(session.scalars(select(Team.id).where(Team.competition_id == career.competition_id)))) - 1
        later = next_fixture_plan(session, career, round_index=opponents + 1)
        assert first["side"] == "home" and later["side"] == "away", "a career plays every club at home in its first cycle and away in its second"
        assert later["of"] == opponents and later["opponent_team_id"] == first["opponent_team_id"], "the second cycle meets the same club, on the other side"
        assert later["cycle"] == 2 and first["cycle"] == 1

    def test_the_profile_a_projection_selects_from_is_the_one_the_engine_would_play(self, session: Session, world: dict[str, Any]) -> None:
        career = _career(session, world["career_slug"])
        result = simulate_transfer(session, career, player=world["outsider"], rounds=1)
        plain = team_profile(session, str(career.club_id), system_slug=career.system_slug or None)
        assert [row["player_id"] for row in result["side"]["before"]["eleven"]] == [player_id for player_id, _slug, _name, _pos, _band in plain.selected]
        assert result["side"]["before"]["indices"]["overall"] == round(plain.overall, 3)
