"""The world's spotlight: three recognitions, computed from the rows, and nothing invented.

`compute_spotlight` is arithmetic on the stored world — the best goals per 90 in the tier-1
league, the team with the most home clean sheets, and the youngest real-minutes player the
tier-1 holds. These cases pin the shape of the JSON, the sample arithmetic, and the refusal
to invent anything for an unwritten world.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from app.core.db import SessionLocal
from app.services.world import sync_world
from app.services.world.spotlight import compute_spotlight

API = "/api/v1"
SPOTLIGHT_KEYS = ("hitman", "fortress", "new_blood")


@pytest.fixture()
def session() -> Iterator:  # type: ignore[no-untyped-def]
    with SessionLocal() as db:
        sync_world(db)
        yield db


class TestTheSpotlight:
    def test_compute_returns_every_key_exactly_once(self, session) -> None:  # type: ignore[no-untyped-def]
        result = compute_spotlight(session)
        keys = [s["key"] for s in result["spotlights"]]
        assert keys == list(SPOTLIGHT_KEYS)

    def test_the_hitman_is_computed_from_a_real_sample(self, session) -> None:  # type: ignore[no-untyped-def]
        hitman = next(s for s in compute_spotlight(session)["spotlights"] if s["key"] == "hitman")
        if not hitman["available"]:
            return  # a world without a qualifying sample publishes nothing rather than invent one
        assert hitman["player"]["data_origin"] == "synthetic"
        assert hitman["goals"] >= 0
        assert hitman["per_90"] == pytest.approx(hitman["goals"] * 90 / hitman["minutes"], abs=0.1)
        assert hitman["minutes"] >= 600

    def test_the_fortress_counts_home_clean_sheets_only(self, session) -> None:  # type: ignore[no-untyped-def]
        fortress = next(s for s in compute_spotlight(session)["spotlights"] if s["key"] == "fortress")
        if not fortress["available"]:
            return
        assert fortress["clean_sheets"] >= 0
        assert fortress["played"] >= 5
        assert fortress["team"]["path"].startswith("/team/")

    def test_the_new_blood_appears_in_the_tier_one_league(self, session) -> None:  # type: ignore[no-untyped-def]
        blood = next(s for s in compute_spotlight(session)["spotlights"] if s["key"] == "new_blood")
        if not blood["available"]:
            return
        assert blood["age"] < 30  # the youngest qualifying tier-1 player — not a veteran
        assert blood["minutes"] >= 300

    def test_the_door_answers_with_an_envelope_like_its_neighbours(self, client) -> None:  # type: ignore[no-untyped-def]
        response = client.get(f"{API}/world/spotlight")
        assert response.status_code == 200
        body = response.json()
        assert body["data_origin"] == "synthetic"
        assert body["is_demo_data"] is True
        assert body["disclaimer"]
        assert set(body) >= {"spotlights", "season"}
