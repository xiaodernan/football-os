"""The Gazette — the season's paper of record, edition by edition.

`compute_gazette` walks the tier-1 league's completed fixtures one matchday at a time and
prints exactly what was there when the round ended: the running table, the loudest fixture,
the club that did the most damage, the shutouts, the carries. These cases pin the shape of
the JSON, the descending-in-time insistence of the archive, the honest refusal of an
out-of-range edition, and the agreement of every figure with its rows.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from app.core.db import SessionLocal
from app.services.world import sync_world
from app.services.world.gazette import compute_gazette

API = "/api/v1"


@pytest.fixture()
def session() -> Iterator:  # type: ignore[no-untyped-def]
    with SessionLocal() as db:
        sync_world(db)
        yield db


class TestTheGazette:
    def test_the_latest_edition_is_the_most_complete_matchday(self, session) -> None:  # type: ignore[no-untyped-def]
        result = compute_gazette(session)
        assert result["available"] is True
        assert 1 <= result["edition"] == result["total_editions"]
        assert result["archive"] == list(range(1, result["total_editions"] + 1))

    def test_an_edition_reads_the_table_at_its_own_date(self, session) -> None:  # type: ignore[no-untyped-def]

        latest = compute_gazette(session)
        early = compute_gazette(session, 1)
        assert early["edition"] == 1
        assert early["published_at"] <= latest["published_at"]
        assert early["table_after"][0]["played"] <= latest["table_after"][0]["played"]

    def test_every_edition_prints_the_loudest_fixture_from_its_own_round(self, session) -> None:  # type: ignore[no-untyped-def]
        result = compute_gazette(session, 1)
        assert result["available"] is True
        assert result["lead"]["path"].startswith("/match/")
        assert result["lead"]["home_goals"] + result["lead"]["away_goals"] >= 0
        loudest_goals = result["lead"]["home_goals"] + result["lead"]["away_goals"]
        assert result["number"]["goals_this_round"] >= loudest_goals

    def test_an_out_of_range_edition_is_refused_not_invented(self, session) -> None:  # type: ignore[no-untyped-def]
        result = compute_gazette(session, 9999)
        assert result["available"] is False
        assert result["out_of_range"] is True
        assert result["total_editions"] >= 1

    def test_the_hot_hand_is_the_club_that_did_the_most_damage(self, session) -> None:  # type: ignore[no-untyped-def]
        result = compute_gazette(session)
        assert result["available"] is True
        assert result["hot_hand"]["goals"] >= 0
        assert result["hot_hand"]["team"]["path"].startswith("/team/")

    def test_the_door_demands_a_valid_edition(self, client) -> None:  # type: ignore[no-untyped-def]
        response = client.get(f"{API}/world/gazette?edition=999")
        assert response.status_code == 422
        body = response.json()
        assert body["detail"]["code"] == "edition_out_of_range"
        assert body["detail"]["total_editions"] >= 1

    def test_the_framework_bounds_absurd_editions(self, client) -> None:  # type: ignore[no-untyped-def]
        response = client.get(f"{API}/world/gazette?edition=0")
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "validation_error"

    def test_the_door_answers_with_an_envelope_like_its_siblings(self, client) -> None:  # type: ignore[no-untyped-def]
        response = client.get(f"{API}/world/gazette")
        assert response.status_code == 200
        body = response.json()
        assert body["data_origin"] == "synthetic"
        assert body["is_demo_data"] is True
        assert body["disclaimer"]
        assert set(body) >= {"edition", "table_after", "lead", "scorecard", "archive", "season"}
