"""The Roll of Honours — every tournament this product carries, side by side, computed every read.

The Real Book prints each of them in its own volume; this door is the spine: the lineage of finals,
in one table, one row each — year, host, fixture, outcome, the widest margin, everything counted
from the committed bytes and nothing invented. It holds World Cups and European Championships —
the openfootball family — and nothing else.

The synthetic world is not present here. The real world's finals are what they are.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.services.world.real_book import _REGISTRY, ATTRIBUTION, compute_real_book


def _pick_row(results: list[dict[str, Any]]) -> dict[str, Any]:
    final = next((row for row in results if row.get("round") == "Final"), None)
    if final is None:
        raise RuntimeError("the committed snapshot has no Final row — this cannot happen for a tournament the door carries")
    return final


def compute_honours() -> dict[str, Any]:
    tournaments = list(_REGISTRY.items())  # registry order: newest first
    entries = []
    for year, registry in tournaments:
        book = compute_real_book(year)
        champion = book["facts"]["champion"]
        runner_up = book["facts"]["runner_up"]
        final_row = _pick_row(book["results"])
        on_field = final_row["on_field"]
        entry = {
            "tournament": year,
            "kind": registry.get("kind", "worldcup"),
            "title": book["facts"]["tournament"],
            "host": book["facts"]["host"],
            "date": final_row["date"],
            "venue": final_row["ground"],
            "champion": champion["name"],
            "champion_note": champion["note"],
            "runner_up": runner_up["name"],
            "score_regular": book["facts"]["final"]["score_regular"],
            "score_extra_time": book["facts"]["final"]["score_extra_time"],
            "score_penalties": book["facts"]["final"]["score_penalties"],
            "has_penalties": book["facts"]["has_penalties"],
            "went_extra_time": final_row["et"] is not None,
            "on_field": on_field,
            "goals_scored": book["facts"]["goals_scored"],
            "venues": book["facts"]["venues"],
            "biggest_win": book["facts"]["biggest_win"],
            "total_matches": book["facts"]["total_matches"],
        }
        entries.append(entry)

    # Repeat champions across the twelve — pure arithmetic on the registry order.
    counts = Counter(entry["champion"] for entry in entries)
    champion_lines = []
    for name, wins in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        years = [entry["tournament"] for entry in entries if entry["champion"] == name]
        # The registry order is newest-first; flip for a read-the-spine-down chronology.
        years_chrono = sorted(years, reverse=True)
        champion_lines.append({"champion": name, "wins": wins, "years": years_chrono, "kinds": sorted({entry["kind"] for entry in entries if entry["champion"] == name})})

    total_matches = sum(entry["total_matches"] for entry in entries)
    total_goals = sum(entry["goals_scored"] for entry in entries)
    return {
        "available": True,
        "source": "openfootball worldcup.json + openfootball euro.json (CC-BY 4.0)",
        "attribution": ATTRIBUTION,
        "provenance": {
            "data_origin": "public-real",
            "is_demo_data": False,
            "license": "CC-BY 4.0",
        },
        "entries": entries,
        "champion_lines": champion_lines,
        "totals": {
            "entries": len(entries),
            "matches": total_matches,
            "goals_on_field": total_goals,
        },
    }


__all__ = ["compute_honours"]
