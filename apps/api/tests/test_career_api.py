"""Career Mode over HTTP: the public knobs, the private season, and the labels that must travel (spec §20, §61).

Four questions, in the order a reviewer would ask them:

* **Is the season private?** The knobs are already public fiction under `/world`; a career, its rounds
  and its record belong to the account that opened them, and a foreign slug reads as 404.
* **Is every number traceable?** A response prints the formula it summed by, the calendar rule that
  picked the opponent, and the digest of the match that decided the round.
* **Is the fiction said out loud?** `data_origin='simulation'`, the career disclaimer, and a
  `limitations` block that admits what the layer still does not do — wages are recorded rather than
  deducted, the philosophy label is not read by the engine, and the need it lists is arithmetic rather
  than an AI Scout (the budget itself is spent for real since §22, on `/api/v1/transfers`).
* **What survives deletion?** The career and its rounds go; the match reports it played stay, because
  the account chose to play them.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import OBJECTIVE_FORMULA, Team
from app.services.world import sync_world

API = "/api/v1/careers"
PASSWORD = "strong-pass-1234"


@pytest.fixture(scope="module")
def club_id() -> str:
    session = SessionLocal()
    sync_world(session)
    ident = str(session.scalars(select(Team.id).order_by(Team.slug).limit(1)).one())
    session.close()
    return ident


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


def _body(club: str, **kwargs: Any) -> dict[str, Any]:
    return {
        "club": club,
        "manager_name": kwargs.pop("manager_name", "Alex Demo"),
        "philosophy": kwargs.pop("philosophy", "possession"),
        "system": kwargs.pop("system", None),
        "budget": kwargs.pop("budget", 250_000),
        "objectives": kwargs.pop("objectives", [{"kind": "wins", "target": 2, "label": "win twice"}]),
        **kwargs,
    }


class TestPublicKnobs:
    def test_options_offers_clubs_systems_and_the_objective_formulas(self, client) -> None:  # type: ignore[no-untyped-def]
        body = client.get(f"{API}/options").json()
        assert len(body["clubs"]) >= 20 and len(body["systems"]) == 50
        assert set(body["objective_kinds"]) == set(OBJECTIVE_FORMULA)
        assert body["objective_kinds"]["points"] == OBJECTIVE_FORMULA["points"]
        assert body["philosophies"] and body["max_careers_per_user"] == 5
        assert body["data_origin"] == "simulation" and "fiction" in body["disclaimer"]

    def test_options_needs_no_session(self, client) -> None:  # type: ignore[no-untyped-def]
        assert client.get(f"{API}/options", headers={"Authorization": ""}).status_code == 200

    def test_a_career_and_its_rounds_need_an_account(self, client, club_id) -> None:  # type: ignore[no-untyped-def]
        assert client.get(API).status_code == 401
        assert client.get(f"{API}/anything").status_code == 401
        assert client.post(API, json=_body(club_id)).status_code == 401


class TestOpening:
    def test_an_unknown_club_is_a_404_that_says_where_clubs_live(self, auth_client, club_id) -> None:  # type: ignore[no-untyped-def]
        response = auth_client.post(API, json=_body("no-such-club-anywhere"))
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "no_such_club"
        assert response.json()["detail"]["see"] == f"{API}/options"

    def test_the_knobs_are_checked_before_a_career_is_written(self, auth_client, club_id) -> None:  # type: ignore[no-untyped-def]
        for patch, code in (
            ({"philosophy": "tiki-taka"}, "bad_philosophy"),
            ({"objectives": [{"kind": "assists", "target": 3}]}, "bad_objective"),
            ({"objectives": []}, "no_objectives"),
            ({"system": "4-4-2-not-real"}, "no_such_system"),
        ):
            response = auth_client.post(API, json=_body(club_id, **patch))
            assert response.status_code in (404, 422), response.text
            assert response.json()["detail"]["code"] == code, f"the door answered {response.json()!r}, the refusal code {code!r} was required"

    def test_opening_a_career_returns_the_record_and_the_next_fixture(self, auth_client, club_id) -> None:  # type: ignore[no-untyped-def]
        response = auth_client.post(API, json=_body(club_id, system="4-3-3-press-high"))
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["career"]["manager_name"] == "Alex Demo" and body["career"]["club_id"] == club_id
        assert body["career"]["system_path"] == "/tactics/4-3-3-press-high"
        assert body["record"]["played"] == 0 and body["record"]["points"] == 0
        assert body["objectives"][0]["target"] == 2 and body["objectives"][0]["met"] is False
        assert body["objectives"][0]["formula"] == OBJECTIVE_FORMULA["wins"]
        assert body["next_fixture"]["available"] is True and body["next_fixture"]["basis"]
        assert body["is_demo_data"] is True and "fiction" in body["disclaimer"]
        assert set(body["limitations"]) == {"budget", "wages", "carry_over", "projections", "ledger", "scouting", "philosophy", "table", "objectives", "world_calendar"}

    def test_the_career_appears_in_the_accounts_own_list(self, auth_client, club_id) -> None:  # type: ignore[no-untyped-def]
        opened = auth_client.post(API, json=_body(club_id)).json()
        listed = auth_client.get(API).json()
        assert listed["total"] >= 1 and listed["limit_per_user"] == 5
        row = next(item for item in listed["items"] if item["slug"] == opened["career"]["slug"])
        assert row["record"]["played"] == 0 and row["objectives_met"] == 0 and row["is_demo_data"] is True


class TestPlayingASeason:
    def test_a_round_is_played_by_the_engine_and_linkable(self, auth_client, club_id) -> None:  # type: ignore[no-untyped-def]
        slug = auth_client.post(API, json=_body(club_id)).json()["career"]["slug"]
        response = auth_client.post(f"{API}/{slug}/play")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["played"] is True
        assert body["match"]["path"].startswith("/simulate/") and len(body["match"]["digest"]) == 16
        assert body["career"]["rounds_played"] == 1 and body["record"]["played"] == 1
        assert body["fixtures"][0]["match_path"] == body["match"]["path"]
        assert body["fixtures"][0]["opponent_path"].startswith("/team/")
        assert "re-checked" in body["consistency"], body["consistency"]
        assert body["model_versions"] and body["model_versions"][0].count("@") == 1

    def test_three_rounds_build_a_table_the_record_agrees_with(self, auth_client, club_id) -> None:  # type: ignore[no-untyped-def]
        slug = auth_client.post(API, json=_body(club_id)).json()["career"]["slug"]
        for _ in range(3):
            assert auth_client.post(f"{API}/{slug}/play").status_code == 200
        body = auth_client.get(f"{API}/{slug}").json()
        assert body["record"]["played"] == 3
        mine = next(entry for entry in body["table"] if entry["is_career_club"])
        assert (mine["points"], mine["played"]) == (body["record"]["points"], 3)
        assert sum(entry["played"] for entry in body["table"]) == 6, "each round touches two clubs"
        seeds = [fixture["seed"] for fixture in body["fixtures"]]
        assert len(set(seeds)) == 3 and all(seed > 0 for seed in seeds)
        # The development projection is part of the career payload and reads from the rounds just played.
        dev = body["development"]
        assert dev["players_developed"] > 0 and dev["total_minutes"] > 0
        assert dev["development_formula"].startswith("developed(value, potential, minutes)")
        assert all(entry["effective_minutes"] >= entry["minutes"] for entry in dev["top_developed"])
        # Every read-only projection the career page renders is on the wire, with its own formula. This is
        # the contract the web tier consumes; losing a block here would blank a section silently.
        assert body["board"]["season_rounds"] > 0 and body["board"]["formula"]
        assert body["highlights"]["available"] is True and body["highlights"]["played"] == 3
        assert body["affordability"]["formula"] and {"signing", "timeline"} <= set(body["affordability"])
        assert body["contracts"]["formula"] and "age_profile" in body["contracts"] and body["contracts"]["positions"]
        assert body["window"]["state"] in ("open", "closed") and body["window"]["round"] == 4
        assert body["next_fixture"]["round_index"] == 4, "the detail carries its next-fixture plan on the view itself"
        assert body["head_to_head"]["available"] is True
        assert body["next_fixture_brief"]["available"] is True
        assert body["ledger"]["leaders"]["per90_formula"]

    def test_the_same_career_played_twice_gives_the_same_opponents(self, auth_client, club_id) -> None:  # type: ignore[no-untyped-def]
        """The fixture list is the generated calendar, so two accounts managing the same club face the
        same order — the career's own seed decides the score, not the opponent."""
        first = auth_client.post(API, json=_body(club_id)).json()["career"]["slug"]
        with _signed_in() as other:
            second = other.post(API, json=_body(club_id)).json()["career"]["slug"]
            plan = other.get(f"{API}/{second}").json()["next_fixture"]
        mine = auth_client.get(f"{API}/{first}").json()["next_fixture"]
        assert (mine["opponent_name"], mine["side"]) == (plan["opponent_name"], plan["side"])

    def test_retiring_stops_the_season_and_bringing_it_back_resumes(self, auth_client, club_id) -> None:  # type: ignore[no-untyped-def]
        slug = auth_client.post(API, json=_body(club_id)).json()["career"]["slug"]
        retired = auth_client.post(f"{API}/{slug}/retire").json()
        assert retired["status"] == "retired" and retired["career"]["status"] == "retired"
        refused = auth_client.post(f"{API}/{slug}/play")
        assert refused.status_code == 409 and refused.json()["detail"]["code"] == "cannot_play"
        assert auth_client.post(f"{API}/{slug}/retire").json()["status"] == "active"
        assert auth_client.post(f"{API}/{slug}/play").status_code == 200


class TestOwnership:
    def test_another_account_sees_no_career_and_cannot_play_one(self, auth_client, club_id) -> None:  # type: ignore[no-untyped-def]
        slug = auth_client.post(API, json=_body(club_id)).json()["career"]["slug"]
        auth_client.post(f"{API}/{slug}/play")
        with _signed_in() as other:
            assert other.get(API).json()["total"] == 0
            for method, path in (("get", f"{API}/{slug}"), ("post", f"{API}/{slug}/play"), ("post", f"{API}/{slug}/retire"), ("delete", f"{API}/{slug}")):
                response = getattr(other, method)(path)
                assert response.status_code == 404, f"{method!r} {path!r} answered {response.status_code!r}, 404 was required"
                assert response.json()["detail"]["code"] == "not_found"

    def test_deleting_a_career_keeps_the_matches_the_account_chose_to_play(self, auth_client, club_id) -> None:  # type: ignore[no-untyped-def]
        slug = auth_client.post(API, json=_body(club_id)).json()["career"]["slug"]
        match_path = auth_client.post(f"{API}/{slug}/play").json()["match"]["path"]
        removed = auth_client.delete(f"{API}/{slug}")
        assert removed.status_code == 200 and removed.json()["matches_kept"] is True
        assert auth_client.get(f"{API}/{slug}").status_code == 404
        assert auth_client.get("/api/v1/simulate").json()["total"] >= 1
        assert auth_client.get(match_path.replace("/simulate", "/api/v1/simulate")).status_code == 200


class TestCeiling:
    def test_five_careers_is_the_stated_limit_and_says_so(self, auth_client, club_id) -> None:  # type: ignore[no-untyped-def]
        for index in range(5):
            assert auth_client.post(API, json=_body(club_id, manager_name=f"Manager {index}")).status_code == 200
        sixth = auth_client.post(API, json=_body(club_id, manager_name="Manager 6"))
        assert sixth.status_code == 409
        assert sixth.json()["detail"]["message"].startswith("this account already has 5 of 5")
