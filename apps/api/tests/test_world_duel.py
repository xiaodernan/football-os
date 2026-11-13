"""The head-to-head: a tally a reader can check, and the categories it refuses to decide.

The arithmetic is tested without a database, because the only thing it can be wrong about is the comparison
itself — which column wins, what a tie is, and what happens when a player has not played enough for a rate.
The HTTP tests then prove the two idents reach it, that a missing half is named, and that a player cannot be
matched against himself.
"""

from __future__ import annotations

from typing import Any

from app.models import RealPlayer
from app.services.world.duel import CATEGORY_ORDER, PER90_FLOOR_MINUTES, compare, per90

API = "/api/v1/world"


def _player(**overrides: Any) -> RealPlayer:
    """A footballer with only the columns the ledger reads; every other column keeps its model default."""
    fields: dict[str, Any] = {
        "id": "plr_test",
        "slug": "test-player",
        "name": "Test Player",
        "position": "ST",
        "age": 24,
        "overall": 70,
        "minutes": 900,
        "appearances": 10,
        "starts": 10,
        "goals": 5,
        "assists": 2,
        "rating": 7.0,
        "yellow_cards": 1,
        "red_cards": 0,
        "clean_sheets": 0,
        "attributes": {"pace": 70},
    }
    fields.update(overrides)
    return RealPlayer(**fields)


class TestTheRates:
    def test_a_player_below_one_full_match_has_no_rate(self) -> None:
        """Nine minutes and a goal is "10.0 per 90" — computable, and meaningless. The floor is the point."""
        cameo = _player(minutes=PER90_FLOOR_MINUTES - 1, goals=1, assists=0)
        assert per90(cameo)["goals"] is None
        assert per90(cameo)["involvement"] is None

    def test_a_striker_with_ten_in_nine_hundred_is_one_a_match(self) -> None:
        rates = per90(_player(minutes=900, goals=10, assists=5))
        assert rates["goals"] == 1.0
        assert rates["assists"] == 0.5
        assert rates["involvement"] == 1.5
        assert rates["minutes_per_appearance"] == 90.0

    def test_a_player_with_no_appearances_has_no_minutes_per_appearance(self) -> None:
        assert per90(_player(appearances=0, minutes=0))["minutes_per_appearance"] is None


class TestTheLedger:
    def test_every_category_is_a_row_in_the_documented_order(self) -> None:
        body = compare(_player(), _player(id="plr_b", slug="b"))
        assert tuple(row["key"] for row in body["categories"]) == CATEGORY_ORDER
        assert all(row["basis"] for row in body["categories"])

    def test_the_better_figure_wins_and_the_margin_is_absolute(self) -> None:
        better = _player(id="plr_a", slug="a", goals=9)
        worse = _player(id="plr_b", slug="b", goals=4)
        goals = next(row for row in compare(better, worse)["categories"] if row["key"] == "goals")
        assert goals["winner"] == "left" and goals["margin"] == 5

    def test_a_booking_is_not_an_achievement(self) -> None:
        """Discipline is the one column where the smaller figure wins, and it must not be inverted by accident."""
        clean = _player(id="plr_a", slug="a", yellow_cards=1, red_cards=0)
        dirty = _player(id="plr_b", slug="b", yellow_cards=6, red_cards=1)
        row = next(row for row in compare(clean, dirty)["categories"] if row["key"] == "discipline")
        assert row["lower_wins"] is True
        assert (row["left"], row["right"]) == (1.0, 9.0)
        assert row["winner"] == "left"

    def test_equal_figures_level_the_category_instead_of_moving_the_tally(self) -> None:
        body = compare(_player(id="plr_a", slug="a"), _player(id="plr_b", slug="b"))
        assert {row["winner"] for row in body["categories"]} == {"level"}
        assert body["verdict"] == {
            "winner": "draw",
            "left_wins": 0,
            "right_wins": 0,
            "levelled": len(CATEGORY_ORDER),
            "unavailable": 0,
            "counted": 0,
            "decided_by": [],
            "left_categories": [],
            "right_categories": [],
        }

    def test_an_unavailable_category_is_named_not_counted_as_a_loss(self) -> None:
        """The cameo has fewer than ninety minutes, so the per-90 row cannot be decided — for either side."""
        cameo = _player(id="plr_a", slug="a", minutes=12, goals=1, assists=0)
        regular = _player(id="plr_b", slug="b", minutes=900, goals=3, assists=3)
        body = compare(cameo, regular)
        row = next(item for item in body["categories"] if item["key"] == "involvement_per_90")
        assert row["winner"] == "unavailable" and row["margin"] is None
        assert body["verdict"]["unavailable"] == 1
        # Every category is accounted for exactly once: decided, levelled, or unavailable. The count is not
        # asserted as a fixed number — these two players agree on rating and overall, and a test that forgot
        # that would be asserting the fixture rather than the rule.
        verdict = body["verdict"]
        assert verdict["counted"] + verdict["levelled"] + verdict["unavailable"] == len(CATEGORY_ORDER)
        assert verdict["counted"] == len(verdict["left_categories"]) + len(verdict["right_categories"])

    def test_the_tally_names_the_categories_the_winner_took(self) -> None:
        sharper = _player(id="plr_a", slug="a", goals=20, assists=1, minutes=1800, rating=7.8, overall=82)
        steady = _player(id="plr_b", slug="b", goals=1, assists=12, minutes=2400, rating=6.9, overall=74, yellow_cards=4)
        body = compare(sharper, steady)
        verdict = body["verdict"]
        assert verdict["winner"] == "left"
        assert verdict["left_wins"] == len(verdict["left_categories"])
        assert verdict["left_wins"] + verdict["right_wins"] + verdict["levelled"] + verdict["unavailable"] == len(CATEGORY_ORDER)
        assert set(verdict["decided_by"]) == set(verdict["left_categories"])


class TestTheDoor:
    def _two(self, client) -> tuple[str, str]:  # type: ignore[no-untyped-def]
        items = client.get(f"{API}/players", params={"page_size": 2, "sort": "minutes"}).json()["items"]
        return items[0]["slug"], items[1]["slug"]

    def test_two_slugs_are_compared_and_carry_their_labels(self, client) -> None:  # type: ignore[no-untyped-def]
        left, right = self._two(client)
        response = client.get(f"{API}/duel", params={"left": left, "right": right})
        assert response.status_code == 200
        body = response.json()
        assert body["left"]["player"]["slug"] == left and body["right"]["player"]["slug"] == right
        assert body["is_demo_data"] is True and body["disclaimer"]
        assert body["verdict"]["counted"] >= 1
        assert [row["key"] for row in body["categories"]] == list(CATEGORY_ORDER)
        # The page needs the radar: every duellist arrives with his attributes, not a rate computed from them.
        assert isinstance(body["left"]["attributes"], dict) and body["left"]["attributes"]

    def test_the_same_player_twice_is_refused(self, client) -> None:  # type: ignore[no-untyped-def]
        left, _ = self._two(client)
        response = client.get(f"{API}/duel", params={"left": left, "right": left})
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "same_player"

    def test_a_missing_half_is_named_left_or_right(self, client) -> None:  # type: ignore[no-untyped-def]
        left, right = self._two(client)
        missing = client.get(f"{API}/duel", params={"left": "no-such-player-anywhere", "right": right})
        assert missing.status_code == 404
        assert missing.json()["detail"]["side"] == "left"
        other = client.get(f"{API}/duel", params={"left": left, "right": "no-such-player-anywhere"})
        assert other.json()["detail"]["side"] == "right"

    def test_both_idents_are_required(self, client) -> None:  # type: ignore[no-untyped-def]
        assert client.get(f"{API}/duel", params={"left": "one"}).status_code == 422
