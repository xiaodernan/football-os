"""The timeline: the season matchday by matchday, told with arithmetic alone.

`compute_timeline` walks the tier-1 league's completed fixtures in kickoff order and holds the
table running. These cases pin the shape, the deterministic contract, the arithmetic behind the
takeover and settlement beats, and — the one that matters most — that the story the page tells
cannot drift from the artefacts the almanac already prints.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from app.core.db import SessionLocal
from app.services.world import sync_world
from app.services.world.timeline import compute_timeline

API = "/api/v1"


@pytest.fixture()
def session() -> Iterator:  # type: ignore[no-untyped-def]
    with SessionLocal() as db:
        sync_world(db)
        yield db


def _timeline(session):  # type: ignore[no-untyped-def]
    return compute_timeline(session)


class TestTheTimeline:
    def test_the_rounds_are_ascending_and_every_round_has_fixtures(self, session) -> None:  # type: ignore[no-untyped-def]
        timeline = _timeline(session)
        assert timeline["available"] is True
        matchdays = [round_data["matchday"] for round_data in timeline["rounds"]]
        assert matchdays == sorted(matchdays)
        assert len(matchdays) == len(set(matchdays))
        for round_data in timeline["rounds"]:
            assert round_data["fixtures"] > 0
            assert round_data["goals"] >= 0
            assert round_data["label"].startswith("Matchday ")

    def test_the_champion_is_the_same_imprint_the_almanac_prints(self, session) -> None:  # type: ignore[no-untyped-def]
        from app.services.world.almanac import _league_centre, _title_race_from

        timeline = _timeline(session)
        centre = _league_centre(session)
        race = _title_race_from(centre)
        assert race["available"] is True
        assert timeline["champion"]["id"] == race["champion"]["id"]
        assert timeline["champion"]["points"] == race["champion"]["points"]

    def test_once_the_champion_led_they_never_gave_it_back(self, session) -> None:  # type: ignore[no-untyped-def]
        timeline = _timeline(session)
        champion_id = timeline["champion"]["id"]
        takeover = timeline["beats"]["takeover"]
        assert takeover["available"] is True
        start = takeover["matchday"]
        for round_data in timeline["rounds"]:
            if round_data["matchday"] >= start:
                assert round_data["leader"]["id"] == champion_id

    def test_the_settlement_moment_is_ahead_of_the_final_whistle(self, session) -> None:  # type: ignore[no-untyped-def]
        timeline = _timeline(session)
        settled = timeline["beats"]["settled"]
        if not settled["available"]:
            # an unsettled title must be explained, never invented — decided at the whistle, on a tiebreak
            final = timeline["rounds"][-1]
            expected = (
                final["leader"]["id"] == timeline["champion"]["id"]
                and final["runner_up"] is not None
                and final["runner_up"]["points"] == final["leader"]["points"]
            )
            assert settled["decided_on_tiebreak"] == expected
            return
        assert settled["matchday"] <= timeline["matchdays"]
        champion_id = timeline["champion"]["id"]
        for round_data in timeline["rounds"]:
            if round_data["matchday"] >= settled["matchday"]:
                assert round_data["leader"]["id"] == champion_id

    def test_the_chart_matches_the_rounds_one_for_one(self, session) -> None:  # type: ignore[no-untyped-def]
        timeline = _timeline(session)
        chart_by_round = {point["matchday"]: point for point in timeline["chart"]}
        for round_data in timeline["rounds"]:
            point = chart_by_round[round_data["matchday"]]
            assert point["leader_points"] == round_data["leader"]["points"]
            assert point["gap"] == round_data["gap"]

    def test_the_avalanche_is_the_matchday_with_the_most_goals(self, session) -> None:  # type: ignore[no-untyped-def]
        timeline = _timeline(session)
        goals = [round_data["goals"] for round_data in timeline["rounds"]]
        assert timeline["beats"]["avalanche"]["goals"] == max(goals)

    def test_the_door_answers_with_the_world_envelope(self, client) -> None:  # type: ignore[no-untyped-def]
        response = client.get(f"{API}/world/timeline")
        assert response.status_code == 200
        body = response.json()
        assert body["data_origin"] == "synthetic"
        assert body["is_demo_data"] is True
        assert body["disclaimer"]
        assert set(body) >= {"rounds", "beats", "chart", "champion", "competition", "season"}
