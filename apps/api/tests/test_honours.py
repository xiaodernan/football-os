"""The Roll of Honours — 16 tournaments the product carries, arithmetic printed on every read."""

from __future__ import annotations

from starlette.testclient import TestClient

from app.main import app
from app.services.world.honours import compute_honours

API = "/api/v1"


def test_the_roll_carries_both_families() -> None:
    payload = compute_honours()
    kinds = {entry["kind"] for entry in payload["entries"]}
    assert kinds == {"worldcup", "euro"}
    assert payload["totals"]["entries"] == 23


def test_every_row_prints_its_own_final_from_the_snapshot() -> None:
    payload = compute_honours()
    for entry in payload["entries"]:
        assert entry["champion"]
        assert entry["runner_up"]
        assert isinstance(entry["score_extra_time"], list)
        assert len(entry["on_field"]) == 2
        assert entry["date"]
        assert entry["venue"]
        if entry["has_penalties"]:
            assert entry["score_penalties"][0] != entry["score_penalties"][1]
        extra_time_years = {"1934", "1966", "1978", "1994", "2006", "2010", "2014", "2022", "euro2021"}
        went = entry["went_extra_time"]
        assert went == (entry["tournament"] in extra_time_years), f"{entry['tournament']} went={went}"


def test_the_repeat_champions_are_counted_from_the_rows() -> None:
    payload = compute_honours()
    lines = {row["champion"]: row for row in payload["champion_lines"]}
    assert {name for name, row in lines.items() if row["wins"] >= 2} == {"Argentina", "Brazil", "France", "Italy", "Spain", "West Germany"}
    for name, row in lines.items():
        assert row["wins"] == sum(1 for entry in payload["entries"] if entry["champion"] == name)
    worldcup_entries = [entry for entry in payload["entries"] if entry["kind"] == "worldcup"]
    euro_entries = [entry for entry in payload["entries"] if entry["kind"] == "euro"]
    assert len(worldcup_entries) == 21
    assert len(euro_entries) == 2
    assert sum(entry["total_matches"] for entry in payload["entries"]) == payload["totals"]["matches"]


def test_the_door_answers() -> None:
    client = TestClient(app)
    response = client.get(f"{API}/world/honours")
    assert response.status_code == 200
    body = response.json()
    assert len(body["entries"]) == 23
    assert body["provenance"]["data_origin"] == "public-real"
    assert body["totals"]["matches"] == sum(entry["total_matches"] for entry in body["entries"])
