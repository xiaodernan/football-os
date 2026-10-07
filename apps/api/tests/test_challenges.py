"""Manager live challenges (spec §21): the window, the goal, the reward, and what is only stated.

§21 asks for three properties — time limited, goal based, reward based — and this file tests each one
where it can actually break:

* **Time limited.** The window is enforced by `career.play_round`, the only path that plays a round, so
  the test plays a run to its limit through the career route and asserts the next call answers
  `window_closed` with the numbers that closed it — not that a page stopped offering a button.
* **Goal based.** The targets come from the scenario and the start endpoint accepts none, so the
  arithmetic is tested directly against crafted rows: the same run is `in_progress` with rounds left,
  `missed` when the window closes short, and `met` only when the window closed *and* every objective
  was reached. A target that could be lowered after the fact would make all three meaningless.
* **Reward based.** The reward is earned by `met` and by nothing else, including the case a reader is
  most likely to be suspicious of: every objective reached with rounds still to play earns nothing,
  because the window has not closed.

The remaining question is the one §21's own examples raise: are the constraints real? The catalogue is
tested to publish, for every constraint, whether it binds — and the answer moved when §22 landed: "no
transfers" is enforced now (the market refuses every deal for a career carrying the rule, and
`tests/test_transfers.py` proves it), while "academy players only" still says `enforced=False`, because
the selection has no age filter. A constraint that read as applied would be the one dishonest thing here.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.models import Career, Competition, Team
from app.services.simulation.challenges import (
    CHALLENGES,
    CLUB_SELECTORS,
    DIFFICULTIES,
    VERDICT_STATUSES,
    challenge_by_slug,
    challenge_problems,
    fingerprint,
    resolve_challenge_club,
    verdict_for,
)
from app.services.world import sync_world

API = "/api/v1/challenges"
CAREERS_API = "/api/v1/careers"
PASSWORD = "strong-pass-1234"
SHORT = "win-with-academy-players"  # a 6-round window: the cheapest scenario to play to its limit
CHOOSABLE = "low-budget-challenge"  # club_selector == "any", so it needs a club the caller names


@dataclass
class _Fixture:
    """The four fields the record sums read. A stub, so the arithmetic can be tested without a match."""

    outcome: str
    club_goals: int
    opponent_goals: int

    @property
    def points(self) -> int:
        return {"W": 3, "D": 1, "L": 0}[self.outcome]


@dataclass
class _Career:
    challenge_window: int
    challenge_slug: str = SHORT
    status: str = "active"
    rounds_played: int = 0


def _rows(sequence: str) -> list[_Fixture]:
    """Build fixtures from a compact string: 'W' a 2-1 win, 'D' a 1-1 draw, 'L' a 0-1 loss."""
    goals = {"W": (2, 1), "D": (1, 1), "L": (0, 1)}
    return [_Fixture(outcome=letter, club_goals=goals[letter][0], opponent_goals=goals[letter][1]) for letter in sequence]


@pytest.fixture(scope="module")
def world() -> dict[str, str]:
    """A seeded world, plus the competition with the most clubs and one club from it."""
    session = SessionLocal()
    try:
        sync_world(session)
        competition = max(
            session.scalars(select(Competition)).all(),
            key=lambda row: len(session.scalars(select(Team.id).where(Team.competition_id == row.id)).all()),
        )
        club = session.scalars(select(Team).where(Team.competition_id == competition.id).order_by(Team.slug)).first()
        assert club is not None
        return {"competition": competition.slug, "competition_id": competition.id, "club": club.slug, "club_id": club.id}
    finally:
        session.close()


@contextmanager
def _signed_in() -> Iterator[TestClient]:
    """A second account with its own cookie jar, so an ownership test cannot pass by accident."""
    from app.main import app

    with TestClient(app) as other:
        response = other.post(
            "/api/v1/auth/register",
            json={"email": f"other-{uuid4().hex[:8]}@example.test", "password": PASSWORD, "display_name": "Other Manager", "role": "player", "accepts_data_policy": True},
        )
        assert response.status_code == 201, response.text
        other.headers.update({"Authorization": f"Bearer {response.json()['access_token']}"})
        yield other


def _start(client: TestClient, slug: str, **fields: Any) -> Any:
    return client.post(f"{API}/{slug}/start", json={"manager_name": "Test Manager", **fields})


# --- 1. the catalogue is sound, and says which of its constraints bind -----------------------------


def test_the_catalogue_is_clean_and_has_six_scenarios() -> None:
    assert challenge_problems() == []
    assert len(CHALLENGES) == 6
    assert {challenge.slug for challenge in CHALLENGES} == {
        "save-a-relegation-threatened-club",
        "build-a-u23-squad",
        "win-with-academy-players",
        "three-year-rebuild",
        "no-transfer-challenge",
        "low-budget-challenge",
    }


def test_every_scenario_is_time_limited_goal_based_and_reward_based() -> None:
    for challenge in CHALLENGES:
        assert challenge.window_rounds >= 1, challenge.slug
        assert challenge.objectives, challenge.slug
        assert challenge.reward.get("key") and challenge.reward.get("label"), challenge.slug
        assert challenge.difficulty in DIFFICULTIES
        assert challenge.club_selector in CLUB_SELECTORS


def test_every_scenario_declares_an_enforced_window_and_a_fixed_goal() -> None:
    for challenge in CHALLENGES:
        by_key = {constraint.key: constraint for constraint in challenge.constraints}
        assert by_key["window"].enforced is True, challenge.slug
        assert by_key["fixed_goal"].enforced is True, challenge.slug


def test_constraints_that_nothing_can_apply_say_so() -> None:
    """The honesty test runs in both directions, because under-claiming is as wrong as over-claiming.

    `no_transfers` used to sit beside `academy_only` as published-but-not-applied. That became false
    when §22 landed: the market now refuses every deal for a career carrying this rule, so a catalogue
    that still advertised it as merely stated was telling a manager their hands were free when they
    were tied. The rule is asserted enforced here, and `tests/test_transfers.py` proves the refusal.
    """
    for challenge in CHALLENGES:
        for constraint in challenge.constraints:
            assert constraint.how, f"{challenge.slug}/{constraint.key} does not say what it does"
            if constraint.key == "academy_only":
                assert constraint.enforced is False, f"{challenge.slug}/{constraint.key} claims to be enforced"
                assert "no age filter" in constraint.how
            if constraint.key == "no_transfers":
                assert constraint.enforced is True, f"{challenge.slug}/{constraint.key} is applied but advertised as stated"
                assert "market.transferable()" in constraint.how
            if constraint.key == "budget":
                # The value binds (the caller cannot raise it) and the sentence says the effect does not.
                assert constraint.enforced is True
                assert "nothing spends it yet" in constraint.how


def test_a_problem_in_the_catalogue_is_reported_rather_than_ignored() -> None:
    """The guard `tactical_problems()` gives the 50 systems, applied to the scenarios."""
    from app.services.simulation.challenges import Challenge

    broken = Challenge(
        slug="broken",
        name="Broken",
        brief="",
        difficulty="impossible",
        window_rounds=0,
        club_selector="nonsense",
        philosophy="balanced",
        budget=0,
        system_slug="",
        objectives=({"kind": "not_a_kind", "target": 1},),
        constraints=(),
        reward={},
    )
    problems = challenge_problems((*CHALLENGES, broken))
    joined = " | ".join(problems)
    assert "difficulty" in joined
    assert "club_selector" in joined
    assert "cannot be played" in joined
    assert "not_a_kind" in joined
    assert "no key/label" in joined
    assert challenge_problems() == []  # the real catalogue is untouched by the probe


def test_the_catalogue_and_the_market_agree_about_whether_a_rule_binds() -> None:
    """The invariant that actually drifted, and the test that would have caught it.

    `challenges.py` and `market.transferable()` publish the same flag about the same rule from two
    places. §22 landed the market, updated its own flag to `enforced: True` and left the catalogue
    saying `False` — so a manager reading the scenario was told their hands were free while the market
    was already refusing every deal. Neither module is wrong on its own; the disagreement is the bug.
    """
    from app.services.simulation.market import transferable

    session = SessionLocal()
    try:
        checked = 0
        for challenge in CHALLENGES:
            constraint = next((item for item in challenge.constraints if item.key == "no_transfers"), None)
            if constraint is None:
                continue
            career = _Career(challenge_window=challenge.window_rounds, challenge_slug=challenge.slug)
            verdict = transferable(session, career)  # type: ignore[arg-type]
            assert verdict["ok"] is False and verdict["code"] == "transfers_forbidden", challenge.slug
            assert verdict["enforced"] == constraint.enforced, (
                f"{challenge.slug}: the catalogue publishes enforced={constraint.enforced} and the market publishes {verdict['enforced']} for the same rule"
            )
            checked += 1
        assert checked >= 2, "the two no-transfers scenarios must both be cross-checked"
    finally:
        session.close()


def test_the_fingerprint_moves_when_the_catalogue_does() -> None:
    assert fingerprint() == fingerprint()
    assert len(fingerprint()) == 16


# --- 2. the verdict, from crafted rows -------------------------------------------------------------


def test_an_open_run_is_in_progress_and_has_earned_nothing() -> None:
    challenge = challenge_by_slug(SHORT)
    assert challenge is not None
    verdict = verdict_for(challenge, _Career(challenge_window=6), _rows("WWW"))  # type: ignore[arg-type]
    assert verdict["status"] == "in_progress"
    assert verdict["window_closed"] is False
    assert verdict["rounds_played"] == 3
    assert verdict["rounds_remaining"] == 3
    assert verdict["reward"]["earned"] is False
    assert "still open" in verdict["reward"]["reason"]


def test_every_objective_reached_with_rounds_left_earns_nothing() -> None:
    """The case a reader should be suspicious of: four wins from four rounds is not yet four from six."""
    challenge = challenge_by_slug(SHORT)
    assert challenge is not None
    verdict = verdict_for(challenge, _Career(challenge_window=6), _rows("WWWW"))
    assert verdict["objectives_met"] == verdict["objectives_total"] == 1
    assert verdict["objectives"][0]["actual"] == 4
    assert verdict["status"] == "in_progress"
    assert verdict["reward"]["earned"] is False


def test_a_run_that_meets_every_goal_inside_its_window_earns_the_reward() -> None:
    challenge = challenge_by_slug(SHORT)
    assert challenge is not None
    verdict = verdict_for(challenge, _Career(challenge_window=6), _rows("WWWWLL"))
    assert verdict["status"] == "met"
    assert verdict["window_closed"] is True
    assert verdict["rounds_remaining"] == 0
    assert verdict["reward"]["earned"] is True
    assert "all 1 objectives met" in verdict["reward"]["reason"]


def test_a_run_that_uses_its_window_short_of_the_goal_is_missed() -> None:
    challenge = challenge_by_slug(SHORT)
    assert challenge is not None
    verdict = verdict_for(challenge, _Career(challenge_window=6), _rows("WWLLDD"))
    assert verdict["status"] == "missed"
    assert verdict["window_closed"] is True
    assert verdict["objectives"][0]["met"] is False
    assert verdict["reward"]["earned"] is False


def test_a_target_of_zero_or_below_is_reachable_by_an_empty_run() -> None:
    """`goal_difference` can be met by a run that has not played: the arithmetic must not invert it."""
    challenge = challenge_by_slug("three-year-rebuild")
    assert challenge is not None
    verdict = verdict_for(challenge, _Career(challenge_window=18, challenge_slug="three-year-rebuild"), [])
    difference = next(item for item in verdict["objectives"] if item["kind"] == "goal_difference")
    assert difference["actual"] == 0
    assert difference["met"] is True
    points = next(item for item in verdict["objectives"] if item["kind"] == "points")
    assert points["met"] is False
    assert verdict["status"] == "in_progress"


def test_every_objective_prints_the_formula_it_was_compared_with() -> None:
    challenge = challenge_by_slug("no-transfer-challenge")
    assert challenge is not None
    verdict = verdict_for(challenge, _Career(challenge_window=12, challenge_slug="no-transfer-challenge"), _rows("WWD"))
    for objective in verdict["objectives"]:
        assert objective["formula"] and objective["formula"] != "not a recognised objective kind", objective["kind"]
    unbeaten = next(item for item in verdict["objectives"] if item["kind"] == "unbeaten")
    assert unbeaten["actual"] == 3  # W W D


def test_the_verdict_uses_the_runs_own_window_when_it_differs_from_the_scenario() -> None:
    """A stored window is what was agreed when the run opened, so it is what closes the run."""
    challenge = challenge_by_slug(SHORT)
    assert challenge is not None
    assert challenge.window_rounds == 6  # the scenario's own window
    verdict = verdict_for(challenge, _Career(challenge_window=2), _rows("WW"))
    assert verdict["window_rounds"] == 2
    assert verdict["window_closed"] is True
    assert verdict["rounds_remaining"] == 0
    # Four wins were asked for and two rounds were played, so the shorter window closed it as missed.
    assert verdict["status"] == "missed"
    assert verdict["objectives"][0]["actual"] == 2
    assert verdict["reward"]["earned"] is False


def test_the_status_vocabulary_is_the_one_the_catalogue_publishes() -> None:
    assert set(VERDICT_STATUSES) == {"in_progress", "met", "missed"}


# --- 3. choosing the club is a measurement, not an adjective ----------------------------------------


def test_the_weakest_club_is_the_lowest_measured_eleven_in_that_competition(world: dict[str, str]) -> None:
    session = SessionLocal()
    try:
        challenge = challenge_by_slug("save-a-relegation-threatened-club")
        assert challenge is not None
        club, choice = resolve_challenge_club(session, challenge, competition=world["competition"])
        assert choice["selector"] == "weakest"
        ranking = [entry for entry in choice["ranking"] if entry["measurable"]]
        assert ranking, "no club in this competition could be measured"
        lowest = min(entry["overall"] for entry in ranking)
        assert choice["chosen"]["overall"] == lowest
        assert club.id == choice["chosen"]["team_id"]
        assert "profile.py" in choice["how"] and "lowest was taken" in choice["how"]
        # The ranking is published whole, so a reader sees the field rather than being told the answer.
        assert len(choice["ranking"]) == len(ranking)
    finally:
        session.close()


def test_a_scenario_that_lets_you_choose_still_needs_a_club(world: dict[str, str]) -> None:
    session = SessionLocal()
    try:
        challenge = challenge_by_slug(CHOOSABLE)
        assert challenge is not None
        with pytest.raises(ValueError, match="a club is required"):
            resolve_challenge_club(session, challenge)
        club, choice = resolve_challenge_club(session, challenge, club=world["club"])
        assert choice["selector"] == "any"
        assert club.slug == world["club"]
    finally:
        session.close()


def test_asking_for_the_weakest_club_without_a_competition_is_refused(world: dict[str, str]) -> None:
    session = SessionLocal()
    try:
        challenge = challenge_by_slug(SHORT)
        assert challenge is not None
        with pytest.raises(ValueError, match="a competition is required"):
            resolve_challenge_club(session, challenge)
        with pytest.raises(ValueError, match="no such competition"):
            resolve_challenge_club(session, challenge, competition="not-a-competition")
    finally:
        session.close()


# --- 4. over HTTP: the public catalogue, the private run, the closed window --------------------------


def test_the_catalogue_is_public_and_states_how_a_verdict_is_decided(client: TestClient) -> None:
    response = client.get(API)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 6
    assert body["integrity"]["clean"] is True and body["integrity"]["problems"] == []
    assert len(body["fingerprint"]) == 16
    assert set(body["verdict_statuses"]) == {"in_progress", "met", "missed"}
    assert "met when its window has closed" in body["how_a_verdict_is_decided"]
    assert "career.play_round" in body["window_enforced_by"]
    assert body["objective_formulas"]["points"]
    assert body["data_origin"] == "simulation" and body["is_demo_data"] is True
    assert body["disclaimer"]
    # The limitation a reader must not have to infer: the reward has no wallet behind it.
    assert "no wallet" in body["limitations"]["reward"]


def test_the_catalogue_publishes_the_competitions_a_run_can_be_pointed_at(client: TestClient, world: dict[str, str]) -> None:
    """A `weakest` scenario needs a competition named on the form, so the form gets the real list.

    The counts are compared against the store rather than against themselves: a page that offers
    "5 clubs" is making an arithmetic claim, and this is where it is checked.
    """
    response = client.get(API)
    assert response.status_code == 200, response.text
    rows = response.json()["competitions"]
    assert rows, "a seeded world must offer a competition to name"
    assert len({row["slug"] for row in rows}) == len(rows)
    named = next(row for row in rows if row["slug"] == world["competition"])
    session = SessionLocal()
    try:
        stored = int(session.scalar(select(func.count(Team.id)).where(Team.competition_id == named["id"])) or 0)
        stored_competitions = int(session.scalar(select(func.count(Competition.id))) or 0)
    finally:
        session.close()
    assert named["clubs"] == stored
    assert len(rows) == stored_competitions
    assert all(row["path"] == f"/competition/{row['slug']}" for row in rows), "the path must be the world's own SEO route"


def test_starting_a_run_needs_a_session(client: TestClient, world: dict[str, str]) -> None:
    response = client.post(f"{API}/{CHOOSABLE}/start", json={"manager_name": "Anonymous", "club": world["club"]})
    assert response.status_code == 401, response.text


def test_an_unknown_scenario_is_a_404(client: TestClient, auth_client) -> None:  # type: ignore[no-untyped-def]
    response = _start(auth_client, "not-a-scenario", club="anything")
    assert response.status_code == 404, response.text
    assert response.json()["detail"]["code"] == "no_such_challenge"


def test_the_weakest_club_scenario_needs_a_competition(auth_client) -> None:  # type: ignore[no-untyped-def]
    response = _start(auth_client, "save-a-relegation-threatened-club")
    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "cannot_choose_club" and detail["selector"] == "weakest"


def test_starting_a_run_opens_a_career_that_cannot_be_moved_off_its_scenario(auth_client, world: dict[str, str]) -> None:  # type: ignore[no-untyped-def]
    response = _start(auth_client, CHOOSABLE, club=world["club"])
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["started"] is True

    challenge = challenge_by_slug(CHOOSABLE)
    assert challenge is not None
    assert body["challenge"]["slug"] == CHOOSABLE
    assert body["challenge"]["window_rounds"] == challenge.window_rounds
    # The scenario's numbers reached the career row, and the caller supplied none of them.
    assert body["career"]["budget"] == challenge.budget
    assert body["career"]["philosophy"] == challenge.philosophy
    assert body["career"]["challenge_slug"] == CHOOSABLE
    assert body["career"]["challenge_window"] == challenge.window_rounds
    assert [item["kind"] for item in body["verdict"]["objectives"]] == [item["kind"] for item in challenge.objectives]

    verdict = body["verdict"]
    assert verdict["status"] == "in_progress"
    assert verdict["rounds_played"] == 0
    assert verdict["rounds_remaining"] == challenge.window_rounds
    assert verdict["reward"]["earned"] is False
    assert body["club_choice"]["selector"] == "any"
    assert body["next_fixture"]["available"] is True


def test_the_club_choice_is_reported_as_a_measurement(auth_client, world: dict[str, str]) -> None:  # type: ignore[no-untyped-def]
    response = _start(auth_client, "save-a-relegation-threatened-club", competition=world["competition"])
    assert response.status_code == 201, response.text
    choice = response.json()["club_choice"]
    assert choice["selector"] == "weakest"
    assert choice["competition"]["slug"] == world["competition"]
    assert choice["ranking"], "the ranking must travel with the choice"
    measured = [entry for entry in choice["ranking"] if entry["measurable"]]
    assert choice["chosen"]["overall"] == min(entry["overall"] for entry in measured)


def test_a_run_stops_at_its_window_through_the_career_route(auth_client, world: dict[str, str]) -> None:  # type: ignore[no-untyped-def]
    """The limit is enforced by the only path that plays a round, not by a page hiding a button."""
    started = _start(auth_client, SHORT, competition=world["competition"])
    assert started.status_code == 201, started.text
    slug = started.json()["run"]["slug"]
    window = started.json()["verdict"]["window_rounds"]

    for round_index in range(window):
        played = auth_client.post(f"{CAREERS_API}/{slug}/play")
        assert played.status_code == 200, played.text
        verdict = played.json()["challenge_verdict"]
        assert verdict["rounds_played"] == round_index + 1
        assert verdict["rounds_remaining"] == window - round_index - 1
        if verdict["rounds_remaining"] > 0:
            assert verdict["status"] == "in_progress"
        else:
            # The last round closes the window, so the run is already judged on that very response.
            assert verdict["window_closed"] is True
            assert verdict["status"] in ("met", "missed")

    refused = auth_client.post(f"{CAREERS_API}/{slug}/play")
    assert refused.status_code == 409, refused.text
    detail = refused.json()["detail"]
    assert detail["code"] == "window_closed"
    assert detail["rounds_played"] == window and detail["window_rounds"] == window
    assert detail["challenge_slug"] == SHORT
    # The refusal carries the final verdict, so the page has something to show instead of a dead end.
    assert detail["verdict"]["window_closed"] is True
    assert detail["verdict"]["status"] in ("met", "missed")
    assert detail["verdict"]["rounds_remaining"] == 0


def test_a_closed_run_is_missed_or_met_and_never_in_progress(auth_client, world: dict[str, str]) -> None:  # type: ignore[no-untyped-def]
    started = _start(auth_client, SHORT, competition=world["competition"])
    assert started.status_code == 201, started.text
    slug = started.json()["run"]["slug"]
    window = started.json()["verdict"]["window_rounds"]
    for _ in range(window):
        assert auth_client.post(f"{CAREERS_API}/{slug}/play").status_code == 200

    read = auth_client.get(f"{API}/runs/{slug}")
    assert read.status_code == 200, read.text
    verdict = read.json()["verdict"]
    assert verdict["window_closed"] is True
    assert verdict["status"] in ("met", "missed")
    assert verdict["reward"]["earned"] == (verdict["status"] == "met")
    assert verdict["judged_on"].startswith("the sums of this run's own")
    assert len(read.json()["fixtures"]) == window
    # The run says what a reward would mean, so a credit total cannot read as a balance.
    assert "no wallet" in read.json()["limitations"]["reward"]


def test_an_open_career_has_no_window_and_can_be_played_on(auth_client, world: dict[str, str]) -> None:  # type: ignore[no-untyped-def]
    """A career opened the §20 way must not acquire a §21 limit by accident."""
    opened = auth_client.post(
        CAREERS_API,
        json={"club": world["club"], "manager_name": "Open Manager", "philosophy": "balanced", "budget": 1000, "objectives": [{"kind": "wins", "target": 1}]},
    )
    assert opened.status_code == 200, opened.text
    body = opened.json()
    assert body["career"]["challenge_slug"] == "" and body["career"]["challenge_window"] == 0
    # Playing it proves the absence is not cosmetic: no scenario, so no window and no verdict.
    slug = body["career"]["slug"]
    played = auth_client.post(f"{CAREERS_API}/{slug}/play")
    assert played.status_code == 200, played.text
    assert played.json()["challenge_verdict"] is None


def test_a_run_belongs_to_the_account_that_started_it(auth_client, world: dict[str, str]) -> None:  # type: ignore[no-untyped-def]
    started = _start(auth_client, CHOOSABLE, club=world["club"])
    assert started.status_code == 201, started.text
    slug = started.json()["run"]["slug"]

    with _signed_in() as other:
        assert other.get(f"{API}/runs/{slug}").status_code == 404
        assert other.post(f"{CAREERS_API}/{slug}/play").status_code == 404
        listing = other.get(f"{API}/runs")
        assert listing.status_code == 200
        assert all(item["slug"] != slug for item in listing.json()["items"])

    mine = auth_client.get(f"{API}/runs")
    assert mine.status_code == 200, mine.text
    assert any(item["slug"] == slug for item in mine.json()["items"])


def test_the_run_listing_carries_the_verdict_and_the_scenario_name(auth_client, world: dict[str, str]) -> None:  # type: ignore[no-untyped-def]
    started = _start(auth_client, CHOOSABLE, club=world["club"])
    assert started.status_code == 201, started.text
    slug = started.json()["run"]["slug"]
    listing = auth_client.get(f"{API}/runs")
    assert listing.status_code == 200, listing.text
    entry = next(item for item in listing.json()["items"] if item["slug"] == slug)
    assert entry["challenge_slug"] == CHOOSABLE
    assert entry["challenge_name"] == challenge_by_slug(CHOOSABLE).name  # type: ignore[union-attr]
    assert entry["verdict"]["status"] == "in_progress"
    assert listing.json()["limit_per_user"] >= 1


def test_a_run_is_also_a_career_so_it_appears_in_the_career_list(auth_client, world: dict[str, str]) -> None:  # type: ignore[no-untyped-def]
    """One container, not two: a run is a career row, which is what makes the window enforceable once."""
    started = _start(auth_client, CHOOSABLE, club=world["club"])
    assert started.status_code == 201, started.text
    slug = started.json()["run"]["slug"]
    session = SessionLocal()
    try:
        row = session.scalar(select(Career).where(Career.slug == slug))
        assert row is not None
        assert row.challenge_slug == CHOOSABLE
        assert row.challenge_window > 0
    finally:
        session.close()
    listing = auth_client.get(CAREERS_API)
    assert listing.status_code == 200, listing.text
    assert any(item["slug"] == slug for item in listing.json()["items"])


def test_the_run_ceiling_is_enforced(auth_client, world: dict[str, str]) -> None:  # type: ignore[no-untyped-def]
    from app.api.v1.challenges import MAX_RUNS_PER_USER

    opened = 0
    for index in range(MAX_RUNS_PER_USER):
        response = _start(auth_client, CHOOSABLE, club=world["club"], manager_name=f"Ceiling {index}")
        if response.status_code == 409:
            break
        assert response.status_code == 201, response.text
        opened += 1
    assert opened >= 1
    refused = _start(auth_client, CHOOSABLE, club=world["club"], manager_name="One Too Many")
    assert refused.status_code == 409, refused.text
    assert refused.json()["detail"]["code"] == "run_limit"


def test_capabilities_reports_the_challenge_surface_from_the_data(client: TestClient) -> None:
    body = client.get("/api/v1/capabilities").json()
    assert body["m6_manager_challenges"] is True
    assert body["m6_challenges"]["counts"]["scenarios"] == 6
    assert "fictional scenario" in body["m6_challenges"]["disclaimer"]
