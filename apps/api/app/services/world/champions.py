"""The Champions — the three real World Cups carried inside the product, side by side.

Every figure this door prints is recomputed on every call from the committed
openfootball snapshots the Real Book uses (2014, 2018, 2022; CC-BY 4.0). Nothing here is
authored, stored, or fetched: the final score, the goal totals, the widest margins and the
merged scorers ledger are all arithmetic on the committed bytes.

The synthetic world is not present in this door. When the user reads the synthetic
universe's own standings, they are on a different door; this one is the real one.
"""

from __future__ import annotations

from typing import Any

from app.services.world.real_book import ATTRIBUTION, compute_real_book


def _final_row(results: list[dict[str, Any]]) -> dict[str, Any] | None:
    for row in results:
        if row.get("round") == "Final":
            return row
    return None


def _cup_entry(tournament: str) -> dict[str, Any]:
    book = compute_real_book(tournament)
    facts = book["facts"]
    results = book["results"]
    goals = facts["goals_scored"]
    final_row = _final_row(results)
    return {
        "tournament": tournament,
        "title": facts["tournament"],
        "host": facts["host"],
        "venues": facts["venues"],
        "total_matches": facts["total_matches"],
        "goals_scored": goals,
        "goals_per_match": round(goals / facts["total_matches"], 2),
        "has_penalties": facts["has_penalties"],
        "champion": facts["champion"],
        "runner_up": facts["runner_up"],
        "golden_ball": facts["golden_ball"],
        "final": facts["final"],
        "final_row": {
            "date": final_row["date"] if final_row else None,
            "team1": final_row["team1"] if final_row else None,
            "team2": final_row["team2"] if final_row else None,
            "on_field": final_row["on_field"] if final_row else None,
            "et": final_row["et"] if final_row else None,
            "penalties": final_row["penalties"] if final_row else None,
            "ht": final_row["ht"] if final_row else None,
        } if final_row else None,
        "biggest_win": facts["biggest_win"],
        "top_scorers": book["scorers"][:5],
        "top_scorers_note": facts["joint_top_scorers_note"],
        "has_scorers": bool(book["scorers"]),
    }


def _merged_scorers(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per player across the three cups, per-cup goals, total, merged on the doors' own names.

    The per-cup figures are the books' own scorers tables, which already apply the 2022
    Mbappé-to-one-name merge; no other name is merged. Zeros mean the player did not score in
    that tournament's committed snapshot.
    """
    per_cup: dict[str, dict[str, int]] = {entry["tournament"]: {} for entry in entries}
    for entry in entries:
        for row in entry["top_scorers"]:
            per_cup[entry["tournament"]][row["name"]] = row["goals"]

    names = set().union(*(set(rows) for rows in per_cup.values()))
    merged: list[dict[str, Any]] = []
    for name in names:
        figures = {cup: per_cup[cup].get(name, 0) for cup in ("2014", "2018", "2022")}
        total = sum(figures.values())
        merged.append({"name": name, "goals_2014": figures["2014"], "goals_2018": figures["2018"], "goals_2022": figures["2022"], "total": total})
    merged.sort(key=lambda row: (-int(row["total"]), str(row["name"])))
    return merged[:12]


def compute_champions() -> dict[str, Any]:
    """Compute the six-cups comparison from the committed snapshots, every read."""
    from app.services.world.real_book import tournaments

    entries = [_cup_entry(year) for year in tournaments()]
    top_scorers_note = next(entry["top_scorers_note"] for entry in entries if entry["tournament"] == "2022")
    return {
        "available": True,
        "source": "openfootball worldcup.json (CC-BY 4.0)",
        "attribution": ATTRIBUTION,
        "provenance": {
            "data_origin": "public-real",
            "is_demo_data": False,
            "license": "CC-BY 4.0",
        },
        "entries": entries,
        "merged_scorers": _merged_scorers(entries),
        "joint_top_scorers_note": top_scorers_note,
    }


__all__ = ["compute_champions"]
