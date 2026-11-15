"""The Finals — every completed cup Final, the player of each, and the cup holders' table.

Arithmetic on `real_matches` and `real_player_match_stats`. These cases pin the shape,
the determinism, the loudest arithmetic, and the refusal to invent a cup in an empty world.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from app.core.db import SessionLocal
from app.services.world import sync_world
from app.services.world.finals import compute_finals

API = "/api/v1"


@pytest.fixture()
def session() -> Iterator:  # type: ignore[no-untyped-def]
    with SessionLocal() as db:
        sync_world(db)
        yield db


class TestTheFinals:
    def test_every_final_reports_its_line(self, session) -> None:  # type: ignore[no-untyped-def]
        result = compute_finals(session)
        assert result["available"] is True
        for final in result["finals"]:
            assert final["fixture"]["path"].startswith("/match/")
            assert (final["winning_team"] is not None) == (final["winner"] != "drawn")
            assert final["mvp"] is not None
            assert final["mvp"]["path"].startswith("/player/")

    def test_the_loudest_is_the_most_goals(self, session) -> None:  # type: ignore[no-untyped-def]
        result = compute_finals(session)
        goal_sums = [row["home_goals"] + row["away_goals"] for row in result["finals"]]
        assert result["loudest"]["goals"] == max(goal_sums)
        assert result["stats"]["goals"] == sum(goal_sums)
        assert result["stats"]["finals"] == len(result["finals"])

    def test_the_cup_tally_adds_up(self, session) -> None:  # type: ignore[no-untyped-def]
        result = compute_finals(session)
        total = sum(row["cups"] for row in result["cup_wins"])
        decided = sum(1 for row in result["finals"] if row["winner"] != "drawn")
        assert total == decided
        for row in result["cup_wins"]:
            assert row["cups"] == len(row["names"])

    def test_the_door_answers_like_its_siblings(self, client) -> None:  # type: ignore[no-untyped-def]
        response = client.get(f"{API}/world/finals")
        assert response.status_code == 200
        body = response.json()
        assert body["data_origin"] == "synthetic"
        assert body["is_demo_data"] is True
        assert body["disclaimer"]
        assert set(body) >= {"finals", "stats", "loudest", "cup_wins", "season"}
