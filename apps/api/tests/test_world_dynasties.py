"""The Dynasties — the tier-1 streak ledger, arithmetic on `real_matches` only.

The streaks are recomputed from the completed rows on every call. These cases pin the
arithmetic (win runs require consecutive Ws; unbeaten allows draws), the ordering, and the
envelope parity with the sibling world doors — never any authored claim.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from app.core.db import SessionLocal
from app.services.world import sync_world
from app.services.world.dynasties import compute_dynasties

API = "/api/v1"


@pytest.fixture()
def session() -> Iterator:  # type: ignore[no-untyped-def]
    with SessionLocal() as db:
        sync_world(db)
        yield db


class TestTheDynasties:
    def test_the_streaks_are_ordered_by_length_then_start(self, session) -> None:  # type: ignore[no-untyped-def]
        result = compute_dynasties(session)
        assert result["available"] is True
        for key in ("win_streaks", "unbeaten_runs"):
            lengths = [row["length"] for row in result[key]]
            assert lengths == sorted(lengths, reverse=True)

    def test_every_streak_names_a_real_club_and_rounds(self, session) -> None:  # type: ignore[no-untyped-def]
        result = compute_dynasties(session)
        for key in ("win_streaks", "unbeaten_runs"):
            floor = 2 if key == "win_streaks" else 3
            for row in result[key]:
                assert row["length"] >= floor
                assert row["team"]["slug"]
                assert row["start_round"] and row["end_round"]

    def test_the_longest_streaks_head_the_boards(self, session) -> None:  # type: ignore[no-untyped-def]
        result = compute_dynasties(session)
        if result["win_streaks"]:
            assert result["longest_win"] == result["win_streaks"][0]
        if result["unbeaten_runs"]:
            assert result["longest_unbeaten"] == result["unbeaten_runs"][0]
        if result["ablaze"]["current_win_run"] > 0:
            assert result["ablaze"]["team"] is not None

    def test_the_door_answers_with_the_envelope_like_its_siblings(self, client) -> None:  # type: ignore[no-untyped-def]
        response = client.get(f"{API}/world/dynasties")
        assert response.status_code == 200
        body = response.json()
        assert body["data_origin"] == "synthetic"
        assert body["is_demo_data"] is True
        assert body["disclaimer"]
        assert set(body) >= {"judged", "longest_win", "longest_unbeaten", "win_streaks", "unbeaten_runs", "ablaze", "season"}
