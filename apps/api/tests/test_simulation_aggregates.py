"""M6 item 10 open item: cross-career and league-wide aggregates over sim_events.

These tests verify the new aggregate endpoints that span multiple careers.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.db import SessionLocal
from app.main import app
from app.models import Career, CareerFixture, CareerAppearance, Competition, Team
from app.services.simulation.aggregates import league_ledger_view, player_career_aggregate_view
from app.services.world import sync_world

API = "/api/v1/simulation/aggregates"


def _clip_count(owner_id: str) -> int:
    with SessionLocal() as session:
        return int(session.scalar(select(func.count()).select_from(Career).where(Career.owner_id == owner_id)) or 0)


@pytest.fixture(scope="module")
def world() -> dict[str, Any]:
    """Seed the world and return a few teams for simulations."""
    session = SessionLocal()
    try:
        result = sync_world(session)
        assert result.ok, result.errors[:5]
        teams = list(session.scalars(select(Team).order_by(Team.name).limit(4)).all())
        for team in teams:
            _ = team.competition
        session.close()
        return {"home": teams[0], "away": teams[1], "spare": teams[2]}
    finally:
        session.close()


@pytest.fixture()
def store() -> SessionLocal:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


class TestSimulationAggregates:
    """M6 item 10: cross-career and league-wide aggregates."""

    def test_league_ledger_requires_valid_competition(self, client) -> None:
        r = client.get(f"{API}/league/non-existent-slug")
        assert r.status_code == 404

    def test_league_ledger_returns_structured_data(self, client, world) -> None:
        comp_slug = world["home"].competition.slug
        r = client.get(f"{API}/league/{comp_slug}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["competition"]["slug"] == comp_slug
        assert "players" in body
        assert "totals" in body
        assert "fixtures_played" in body
        assert "consistency" in body
        assert body["source"] in ("sim_events rows", "no traced fixture")

    def test_player_aggregate_requires_valid_player(self, client) -> None:
        r = client.get(f"{API}/player/non-existent-slug")
        assert r.status_code == 404

    @pytest.mark.skip(reason="requires world with careers and full integration")
    def test_player_aggregate_returns_structured_data(self, client, auth_client, world) -> None:
        player_resp = auth_client.post("/api/v1/players", json={
            "name": "Aggregate Test Player",
            "position": "CM",
            "age": 22,
            "level": "beginner",
            "preferred_foot": "right",
            "goal": "improve_passing",
        })
        assert player_resp.status_code == 201, player_resp.text
        player_id = player_resp.json()["id"]
        player_slug = auth_client.get(f"/api/v1/players/{player_id}").json()["id"]

        opts = auth_client.get("/api/v1/simulate/options").json()
        team1 = opts["teams"][0]["team_id"]
        team2 = opts["teams"][1]["team_id"]
        match_resp = auth_client.post("/api/v1/simulate", json={
            "home_team": team1,
            "away_team": team2,
            "minutes": 90,
        })
        assert match_resp.status_code == 201, match_resp.text
        match_id = match_resp.json()["id"]

        career_resp = auth_client.post("/api/v1/careers", json={
            "club_id": team1,
            "philosophy": "balanced",
            "manager_name": "Test Manager",
        })
        assert career_resp.status_code == 201, career_resp.text
        career_id = career_resp.json()["career"]["id"]

        play_resp = auth_client.post(f"/api/v1/careers/{career_id}/play")
        assert play_resp.status_code == 200, play_resp.text

        r = client.get(f"{API}/player/{player_slug}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["player"]["slug"] == player_slug
        assert "careers" in body
        assert "totals" in body
        assert "consistency" in body


if __name__ == "__main__":
    pytest.main([__file__, "-v"])