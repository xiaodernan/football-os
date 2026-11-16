"""The Champions — three real World Cups, side by side; every figure from the committed bytes."""

from __future__ import annotations

from app.services.world.champions import compute_champions


def test_the_ten_cups_are_present_in_order() -> None:
    payload = compute_champions()
    assert payload["available"] is True
    assert [entry["tournament"] for entry in payload["entries"]] == ["2022", "2018", "2014", "2010", "2006", "2002", "1998", "1994", "1990", "1986", "1982", "1978", "1974", "1970"]


def test_each_cup_prints_its_own_champion_and_final_from_the_snapshot() -> None:
    entries = {entry["tournament"]: entry for entry in compute_champions()["entries"]}
    assert entries["2022"]["champion"]["name"] == "Argentina"
    assert entries["2018"]["champion"]["name"] == "France"
    assert entries["2014"]["champion"]["name"] == "Germany"
    assert entries["2010"]["champion"]["name"] == "Spain"
    assert entries["2006"]["champion"]["name"] == "Italy"
    assert entries["2002"]["champion"]["name"] == "Brazil"
    assert entries["1998"]["champion"]["name"] == "France"
    assert entries["1994"]["champion"]["name"] == "Brazil"
    assert entries["1990"]["champion"]["name"] == "West Germany"
    assert entries["1986"]["champion"]["name"] == "Argentina"
    for year, entry in entries.items():
        final = entry["final"]
        row = entry["final_row"]
        assert row is not None, year
        assert row["on_field"] is not None, year
        assert final["venue"], year
        if entry["has_penalties"]:
            assert final["score_penalties"] != [0, 0], year
    assert entries["2006"]["has_penalties"] is True
    assert entries["1994"]["has_penalties"] is True
    assert entries["2022"]["has_penalties"] is True
    for year in ("2018", "2014", "2010", "2002", "1998", "1990", "1986"):
        assert entries[year]["has_penalties"] is False


def test_goal_totals_and_ratios_match_the_real_book_recompute() -> None:
    from app.services.world.real_book import compute_real_book

    for entry in compute_champions()["entries"]:
        book = compute_real_book(entry["tournament"])
        assert entry["goals_scored"] == book["facts"]["goals_scored"]
        assert entry["goals_per_match"] == round(book["facts"]["goals_scored"] / book["facts"]["total_matches"], 2)
        assert entry["venues"] == book["facts"]["venues"]


def test_the_widest_margin_is_computed_from_the_snapshot() -> None:
    for entry in compute_champions()["entries"]:
        win = entry["biggest_win"]
        assert "-" in win["match"]
        assert win["score"][0] != win["score"][1]
        assert win["matchday_date"]


def test_the_merged_scorers_ledger_sums_its_own_columns() -> None:
    payload = compute_champions()
    per_cup = {
        "2014": {row["name"]: row["goals"] for entry in payload["entries"] if entry["tournament"] == "2014" for row in entry["top_scorers"]},
        "2018": {row["name"]: row["goals"] for entry in payload["entries"] if entry["tournament"] == "2018" for row in entry["top_scorers"]},
        "2022": {row["name"]: row["goals"] for entry in payload["entries"] if entry["tournament"] == "2022" for row in entry["top_scorers"]},
    }
    assert payload["merged_scorers"], "the ledger must print at least one row"
    for row in payload["merged_scorers"]:
        assert row["total"] == row["goals_2014"] + row["goals_2018"] + row["goals_2022"]
        assert row["goals_2014"] == per_cup["2014"].get(row["name"], 0)
        assert row["goals_2018"] == per_cup["2018"].get(row["name"], 0)
        assert row["goals_2022"] == per_cup["2022"].get(row["name"], 0)
    totals = [row["total"] for row in payload["merged_scorers"]]
    assert totals == sorted(totals, reverse=True)


def test_provenance_is_public_real() -> None:
    provenance = compute_champions()["provenance"]
    assert provenance["data_origin"] == "public-real"
    assert provenance["is_demo_data"] is False


def test_the_door_answers() -> None:
    from starlette.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    response = client.get("/api/v1/world/champions")
    assert response.status_code == 200
    body = response.json()
    assert len(body["entries"]) == 14
    assert {entry["tournament"] for entry in body["entries"]} == {"1970", "1974", "1978", "1982", "1986", "1990", "1994", "1998", "2002", "2006", "2010", "2014", "2018", "2022"}
    assert body["provenance"]["data_origin"] == "public-real"
    assert [entry["has_scorers"] for entry in body["entries"]] == [True, True, True, False, False, False, False, False, False, False, False, False, False, False]
