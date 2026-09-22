"""M6 simulation over HTTP: the doors, the labels, and the reproducibility a stored row promises (spec §19, §59, §61).

The engine's own arithmetic is tested in `test_simulation.py`; this file tests the feature. Three
questions matter here:

* **Is it private?** A stored match belongs to the account that played it. A foreign id must read as
  404, and the public door must offer only what `/world/*` already offers.
* **Is it labelled?** Every response carries the fictional sentence, the authored-coefficient note and
  the seed, so no client can render a scoreline as a result.
* **Is it re-derivable?** `GET /simulate/{id}/replay` plays the stored match again from the stored
  inputs; the digest must come back identical, on SQLite and on PostgreSQL alike.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import Team
from app.services.world import sync_world

API = "/api/v1/simulate"


@pytest.fixture(scope="module")
def world() -> Iterator[dict[str, Any]]:
    """Two clubs from the generated world, which is what a fixture is actually played between."""
    session = SessionLocal()
    result = sync_world(session)
    assert result.ok, result.errors[:5]
    teams = list(session.scalars(select(Team).order_by(Team.name).limit(4)))
    session.close()
    return {"home": teams[0], "away": teams[1], "spare": teams[2]}


@pytest.fixture(scope="module")
def system_slugs() -> list[str]:
    from app.services.tactics.plan import tactical_systems

    return [system.slug for system in tactical_systems()]


def _play(client, world: dict[str, Any], **kwargs: Any):  # type: ignore[no-untyped-def]
    body = {
        "home_team": world["home"].id,
        "away_team": world["away"].id,
        "home_system": kwargs.pop("home_system", None),
        "away_system": kwargs.pop("away_system", None),
        **kwargs,
    }
    return client.post(API, json={key: value for key, value in body.items() if value is not None})


class TestOptions:
    def test_the_public_door_offers_clubs_systems_and_the_engines_own_claims(self, client, world) -> None:  # type: ignore[no-untyped-def]
        body = client.get(f"{API}/options").json()
        assert len(body["teams"]) >= 20
        assert len(body["systems"]) == 50
        assert body["teams"][0]["path"].startswith("/team/")
        assert body["systems"][0]["path"].startswith("/tactics/")
        engine = body["engine"]
        assert engine["name"] and engine["version"].count("@") == 1
        assert "fictional" in engine["disclaimer"]
        assert "no real match data" in engine["calibration"]
        assert all(factor["expression"] for factor in engine["factors"])
        assert body["data_origin"] == "synthetic"

    def test_options_needs_no_session(self, client, world) -> None:  # type: ignore[no-untyped-def]
        assert client.get(f"{API}/options", headers={"Authorization": ""}).status_code == 200


class TestPlaying:
    def test_playing_requires_an_account(self, client, world) -> None:  # type: ignore[no-untyped-def]
        assert client.post(API, json={"home_team": world["home"].id, "away_team": world["away"].id}).status_code == 401

    def test_a_fixture_comes_back_labelled_and_complete(self, auth_client, world) -> None:  # type: ignore[no-untyped-def]
        response = _play(auth_client, world, home_system="3-4-3-press-high", away_system="3-4-3-low-block")
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["data_origin"] == "simulation" and body["is_demo_data"] is True
        assert "fictional" in body["disclaimer"]
        assert body["path"].startswith("/simulate/")
        report = body["report"]
        assert report["provenance"]["data_origin"] == "simulation"
        assert report["score"]["home"] == body["score"]["home"]
        assert report["sides"]["home"]["system_slug"] == "3-4-3-press-high"
        assert report["sides"]["home"]["lineup"] and report["sides"]["away"]["lineup"]
        assert report["model"]["calibration"]
        assert 24 <= report["possession_share"]["home"] * 100 <= 76
        assert len(report["blocks"]) == 15
        assert body["digest"] == report["digest"]

    def test_the_seed_is_returned_because_without_it_the_match_is_unreproducible(self, auth_client, world) -> None:  # type: ignore[no-untyped-def]
        body = _play(auth_client, world).json()
        assert isinstance(body["seed"], int) and body["seed"] >= 0
        assert body["report"]["model"]["seed"] == body["seed"]

    def test_a_chosen_seed_replays_to_the_same_digest(self, auth_client, world) -> None:  # type: ignore[no-untyped-def]
        first = _play(auth_client, world, seed=424242).json()
        second = _play(auth_client, world, seed=424242).json()
        assert first["digest"] == second["digest"]
        assert first["report"]["events"] == second["report"]["events"]

    def test_an_unpicked_seed_is_not_reused_blindly(self, auth_client, world) -> None:  # type: ignore[no-untyped-def]
        digests = {_play(auth_client, world).json()["digest"] for _ in range(3)}
        assert len(digests) > 1, "three matches with no seed given should not be three copies of one draw"

    def test_a_club_that_is_not_in_the_world_is_refused(self, auth_client, world) -> None:  # type: ignore[no-untyped-def]
        response = _play(auth_client, world, home_team="no-such-club")
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "no_such_team"

    def test_a_system_that_is_not_one_of_the_fifty_is_refused(self, auth_client, world) -> None:  # type: ignore[no-untyped-def]
        response = _play(auth_client, world, home_system="not-a-system")
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "no_such_system"

    def test_only_the_documented_match_lengths_are_offered(self, auth_client, world) -> None:  # type: ignore[no-untyped-def]
        response = _play(auth_client, world, minutes=45)
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "bad_minutes"

    def test_a_fixture_needs_two_different_clubs(self, auth_client, world) -> None:  # type: ignore[no-untyped-def]
        # The away side is given by slug here, which is also how the id arrives: both must resolve.
        response = auth_client.post(API, json={"home_team": world["home"].id, "away_team": world["home"].slug})
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "same_team"

    def test_a_missing_field_is_refused_by_the_schema(self, auth_client, world) -> None:  # type: ignore[no-untyped-def]
        assert auth_client.post(API, json={"home_team": world["home"].id}).status_code == 422

    def test_a_club_can_be_named_by_its_slug(self, auth_client, world) -> None:  # type: ignore[no-untyped-def]
        response = auth_client.post(API, json={"home_team": world["home"].slug, "away_team": world["spare"].slug})
        assert response.status_code == 201, response.text
        assert response.json()["home_team_id"] == world["home"].id

    def test_a_shorter_match_is_stored_as_a_shorter_match(self, auth_client, world) -> None:
        body = _play(auth_client, world, minutes=30).json()
        assert body["minutes"] == 30
        assert len(body["report"]["blocks"]) == 5
        assert body["report"]["blocks"][-1]["minute_to"] == 30


class TestOwnership:
    def test_the_list_shows_only_this_accounts_matches(self, auth_client, world) -> None:  # type: ignore[no-untyped-def]
        played = _play(auth_client, world).json()
        body = auth_client.get(API).json()
        assert any(item["id"] == played["id"] for item in body["items"])
        assert all(item["data_origin"] == "simulation" for item in body["items"])
        assert body["total"] == len(body["items"])
        assert "report" not in body["items"][0], "a list row is a summary, not the whole report"
        assert body["engine"]["disclaimer"]

    def test_detail_resolves_by_id_and_by_slug(self, auth_client, world) -> None:  # type: ignore[no-untyped-def]
        played = _play(auth_client, world).json()
        for ident in (played["id"], played["slug"]):
            response = auth_client.get(f"{API}/{ident}")
            assert response.status_code == 200, response.text
            assert response.json()["digest"] == played["digest"]
            assert response.json()["report"]["events"] == played["report"]["events"]

    def test_another_account_cannot_see_it(self, auth_client, world) -> None:  # type: ignore[no-untyped-def]
        played = _play(auth_client, world).json()
        registration = auth_client.post(
            "/api/v1/auth/register",
            json={
                "email": f"other-{uuid4().hex[:8]}@example.test",
                "password": "strong-pass-1234",
                "display_name": "Other Supporter",
                "role": "player",
                "accepts_data_policy": True,
            },
        )
        assert registration.status_code == 201, registration.text
        token = registration.json()["access_token"]
        own = auth_client.headers.get("Authorization")
        auth_client.headers["Authorization"] = f"Bearer {token}"
        try:
            assert auth_client.get(f"{API}/{played['id']}").status_code == 404
            assert auth_client.post(API, json={"home_team": world["home"].id, "away_team": world["away"].id}).status_code == 201
            assert auth_client.get(API).json()["total"] == 1
        finally:
            auth_client.headers["Authorization"] = own or ""

    def test_a_match_can_be_deleted(self, auth_client, world) -> None:  # type: ignore[no-untyped-def]
        played = _play(auth_client, world).json()
        assert auth_client.delete(f"{API}/{played['slug']}").status_code == 204
        assert auth_client.get(f"{API}/{played['slug']}").status_code == 404

    def test_an_unknown_id_is_a_404_rather_than_a_500(self, auth_client) -> None:  # type: ignore[no-untyped-def]
        assert auth_client.get(f"{API}/sim-none").status_code == 404


class TestReplay:
    def test_a_stored_match_replays_to_its_own_digest(self, auth_client, world, system_slugs) -> None:  # type: ignore[no-untyped-def]
        played = _play(auth_client, world, home_system=system_slugs[0], away_system=system_slugs[9], seed=99).json()
        body = auth_client.get(f"{API}/{played['slug']}/replay").json()
        assert body["possible"] is True
        assert body["identical"] is True, body
        assert body["stored_digest"] == body["replayed_digest"] == played["digest"]
        assert body["stored_score"] == body["replayed_score"]

    def test_replay_is_private_too(self, auth_client, world) -> None:  # type: ignore[no-untyped-def]
        played = _play(auth_client, world).json()
        registration = auth_client.post(
            "/api/v1/auth/register",
            json={
                "email": f"third-{uuid4().hex[:8]}@example.test",
                "password": "strong-pass-1234",
                "display_name": "Third Party",
                "role": "player",
                "accepts_data_policy": True,
            },
        )
        own = auth_client.headers.get("Authorization")
        auth_client.headers["Authorization"] = f"Bearer {registration.json()['access_token']}"
        try:
            assert auth_client.get(f"{API}/{played['slug']}/replay").status_code == 404
        finally:
            auth_client.headers["Authorization"] = own or ""


class TestCapabilities:
    def test_m6_is_advertised_from_the_tables_not_from_the_code(self, client, world) -> None:  # type: ignore[no-untyped-def]
        body = client.get("/api/v1/capabilities").json()
        assert body["m6_simulation"] is True
        engine = body["m6_simulation_engine"]
        assert engine["tables_present"] is True
        assert engine["counts"]["simulations"] >= 1
        assert "fictional" in engine["disclaimer"]

    def test_m5_reports_what_the_host_can_actually_do(self, client) -> None:  # type: ignore[no-untyped-def]
        body = client.get("/api/v1/capabilities").json()
        video = body["m5_video"]
        assert video["tables_present"] is True
        assert set(video["media_tools"]) == {"ffmpeg", "ffprobe"}
        # The flag and the tools must agree: a host without ffmpeg cannot serve an upload.
        assert body["m5_video_analysis"] is (video["tables_present"] and all(video["media_tools"].values()))
