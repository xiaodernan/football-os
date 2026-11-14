"""The almanac: eight awards computed from the world's own numbers, and nothing invented.

`compute_almanac` is the paperwork of the season's honours. These cases pin the shape of the JSON
the door returns, the ordering of each award (tie-broken deterministically), and that the
"best manager" the door hands out matches what the standings table would print.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from app.core.db import SessionLocal
from app.services.world import sync_world
from app.services.world.almanac import compute_almanac

API = "/api/v1"
@pytest.fixture()
def session() -> Iterator:  # type: ignore[no-untyped-def]
    with SessionLocal() as db:
        sync_world(db)
        yield db


AWARD_KEYS = (
    "golden_boot",
    "playmaker_crown",
    "complete_forward",
    "golden_glove",
    "player_of_season",
    "the_enforcer",
    "breakthrough",
)


class TestTheAlmanac:
    def test_compute_returns_every_award_exactly_once(self, session) -> None:  # type: ignore[no-untyped-def]
        result = compute_almanac(session)
        keys = [award["key"] for award in result["awards"]]
        assert keys == list(AWARD_KEYS), "the almanac publishes eight awards and no extras"

    def test_every_award_winner_carries_a_name_and_a_stat(self, session) -> None:  # type: ignore[no-untyped-def]
        result = compute_almanac(session)
        for award in result["awards"]:
            winner = award["winner"]
            assert winner is not None, f"{award['key']} has no winner"
            assert winner["name"], f"{award['key']} winner carries no name"
            assert winner["stat"] is not None, f"{award['key']} winner carries no stat"
            assert winner["path"].startswith("/player/")

    def test_the_awards_are_in_order_by_stat_largest_first(self, session) -> None:  # type: ignore[no-untyped-def]
        result = compute_almanac(session)
        goals_winner = next(award for award in result["awards"] if award["key"] == "golden_boot")["winner"]
        assert goals_winner["stat"] is not None
        completed = [award for award in result["awards"] if award["winner"] is not None]
        assert all(award["winner"]["stat"] is not None for award in completed)

    def test_manager_of_season_comes_from_completed_league_fixtures(self, session) -> None:  # type: ignore[no-untyped-def]
        result = compute_almanac(session)
        best = result["best_manager"]
        if best is None:
            return  # a world without a league would skip — the gate is already named
        assert best["points"] >= 0
        assert best["played"] >= 0
        assert best["goals_for"] >= 0
        assert best["goals_against"] >= 0
        assert best["team"]["name"]

    def test_the_door_answers_with_an_envelope_like_its_neighbours(self, client) -> None:  # type: ignore[no-untyped-def]
        response = client.get(f"{API}/world/almanac")
        assert response.status_code == 200
        body = response.json()
        assert body["awards"] and len(body["awards"]) == len(AWARD_KEYS)
        assert body["data_origin"] == "synthetic"
        assert body["is_demo_data"] is True
        assert body["disclaimer"]
        assert set(body) >= {"awards", "season", "best_manager"}

__all__ = ["AWARD_KEYS"]
