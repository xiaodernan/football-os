"""The world's XI — eleven slots, one captain, no invention.

`compute_matchday_xi` selects the highest-rated eleven in the Lyndera Superleague for the same tier-1
competition the almanac already speaks for, with players filling the 4-3-3 slots left-to-right.
"""

from __future__ import annotations

import pytest

from app.services.world.matchday_xi import compute_matchday_xi

API = "/api/v1"
SLOTS = (
    (1, "GK"),
    (2, "RB"),
    (4, "CB"),
    (5, "CB"),
    (3, "LB"),
    (6, "CDM"),
    (8, "CM"),
    (10, "CM"),
    (7, "RW"),
    (9, "ST"),
    (11, "LW"),
)


@pytest.fixture()
def client_call(client):  # type: ignore[no-untyped-def]
    """Return ``(response, json)`` for one ``GET /api/v1/world/matchday-xi``."""
    response = client.get(f"{API}/world/matchday-xi")
    return response, response.json()


class TestTheDoor:
    def test_the_door_answers_with_an_envelope(self, client_call):  # type: ignore[no-untyped-def]
        response, body = client_call
        assert response.status_code == 200
        assert body["data_origin"] == "synthetic"
        assert body["is_demo_data"] is True
        assert set(body) >= {"season", "competition", "formation", "slots", "captain"}

    def test_slots_arrive_in_shirt_number_order(self, client_call):  # type: ignore[no-untyped-def]
        _, body = client_call
        assert len(body["slots"]) == 11
        assert [(slot["number"], slot["position"]) for slot in body["slots"]] == list(SLOTS)

    def test_every_slot_carries_a_path_to_its_player(self, client_call):  # type: ignore[no-untyped-def]
        _, body = client_call
        for slot in body["slots"]:
            assert slot["path"].startswith("/player/"), f"slot {slot['number']} has no player path"
            assert slot["overall"] > 0

    def test_no_player_appears_twice(self, client_call):  # type: ignore[no-untyped-def]
        _, body = client_call
        names = [slot["name"] for slot in body["slots"]]
        assert len(set(names)) == len(names), "some player was picked twice"

    def test_substituted_slots_are_flagged_not_silent(self, client_call):  # type: ignore[no-untyped-def]
        _, body = client_call
        for slot in body["slots"]:
            if slot.get("substituted"):
                assert slot.get("slack"), f"slot {slot['number']} claims a substitution without naming its position"

    def test_captain_is_on_the_pitch(self, client_call):  # type: ignore[no-untyped-def]
        _, body = client_call
        slugs = {slot["path"] for slot in body["slots"]}
        assert body["captain"]["path"] in slugs
