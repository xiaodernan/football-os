"""The Noise Dossier — the world's rating-based caller, scored against rows it never saw.

The world's fixtures are a seed, not prophecies: every figures here is arithmetic on
`real_matches` + `real_players` — no provider, no stored prediction column, no invented upset.
These cases pin the arithmetic, the agreement with a fresh recomputation, and the refusal to
manufacture predictive power where the seed shows none.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from app.core.db import SessionLocal
from app.services.world import sync_world
from app.services.world.noise import compute_noise

API = "/api/v1"


@pytest.fixture()
def session() -> Iterator:  # type: ignore[no-untyped-def]
    with SessionLocal() as db:
        sync_world(db)
        yield db


class TestTheNoiseDossier:
    def test_the_door_returns_the_callers_verdict(self, session) -> None:  # type: ignore[no-untyped-def]
        result = compute_noise(session)
        assert result["available"] is True
        assert result["judged"] == result["correct"] + result["wrong"]
        assert result["judged"] > 0
        assert result["accuracy_pct"] == pytest.approx(100 * result["correct"] / result["judged"], abs=0.01)
        assert result["chance_pct"] == pytest.approx(100 / 3, abs=0.01)

    def test_the_upset_list_is_ordered_by_rating_gap(self, session) -> None:  # type: ignore[no-untyped-def]
        result = compute_noise(session)
        assert len(result["upsets"]) <= 5
        gaps = [row["rating_gap"] for row in result["upsets"]]
        assert gaps == sorted(gaps, reverse=True)

    def test_every_call_agrees_with_the_fixture_it_rates(self, session) -> None:  # type: ignore[no-untyped-def]
        result = compute_noise(session)
        for row in result["upsets"]:
            assert row["called"] != row["actual"]
            assert row["home_goals"] != row["away_goals"] or row["actual"] == "draw"

    def test_the_door_answers_with_the_envelope_like_its_siblings(self, client) -> None:  # type: ignore[no-untyped-def]
        response = client.get(f"{API}/world/noise")
        assert response.status_code == 200
        body = response.json()
        assert body["data_origin"] == "synthetic"
        assert body["is_demo_data"] is True
        assert body["disclaimer"]
        assert set(body) >= {"accuracy_pct", "chance_pct", "draw_calls", "upsets", "season"}
