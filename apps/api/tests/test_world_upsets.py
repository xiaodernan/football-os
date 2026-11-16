"""The Upset Register — the tier-1 underdog, honoured by its own arithmetic.

Every figure is a recomputation from `real_matches` + `real_players` — no provider, no
stored "upset" column. These cases pin the arithmetic, the ordering, and the tally
identities; the door is judged on rows it never knew in advance.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from app.core.db import SessionLocal
from app.services.world import sync_world
from app.services.world.upsets import compute_upsets

API = "/api/v1"


@pytest.fixture()
def session() -> Iterator:  # type: ignore[no-untyped-def]
    with SessionLocal() as db:
        sync_world(db)
        yield db


class TestTheUpsetRegister:
    def test_the_tally_agrees_with_the_entries(self, session) -> None:  # type: ignore[no-untyped-def]
        result = compute_upsets(session)
        assert result["available"] is True
        assert result["judged"] > 0
        assert result["upset_count"] >= len(result["upsets"])
        assert result["fortress_count"] >= len(result["fortresses"])
        assert result["upset_rate_pct"] == pytest.approx(100 * result["upset_count"] / result["judged"], abs=0.01)

    def test_the_upset_board_is_ordered_by_gap_then_margin(self, session) -> None:  # type: ignore[no-untyped-def]
        result = compute_upsets(session)
        gaps = [row["rating_gap"] for row in result["upsets"]]
        assert gaps == sorted(gaps, reverse=True)
        for row in result["upsets"]:
            assert row["kind"] == "upset"
            assert abs((row["home_goals"] or 0) - (row["away_goals"] or 0)) >= 1

    def test_every_fortress_row_is_a_level_finish_with_a_large_gap(self, session) -> None:  # type: ignore[no-untyped-def]
        result = compute_upsets(session)
        for row in result["fortresses"]:
            assert row["kind"] == "fortress"
            assert row["home_goals"] == row["away_goals"]
            assert row["rating_gap"] >= 8.0

    def test_the_biggest_upset_heads_the_board_when_one_exists(self, session) -> None:  # type: ignore[no-untyped-def]
        result = compute_upsets(session)
        if result["upsets"]:
            assert result["biggest_upset"] == result["upsets"][0]
            assert result["mean_upset_gap"] > 0

    def test_the_door_answers_with_the_envelope_like_its_siblings(self, client) -> None:  # type: ignore[no-untyped-def]
        response = client.get(f"{API}/world/upsets")
        assert response.status_code == 200
        body = response.json()
        assert body["data_origin"] == "synthetic"
        assert body["is_demo_data"] is True
        assert body["disclaimer"]
        assert set(body) >= {"upset_count", "fortress_count", "judged", "upsets", "recent_upsets", "season"}
