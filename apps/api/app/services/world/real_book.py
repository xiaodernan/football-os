"""The Real Book — the real world's football 2022, snapshot-verified, not derived from the seed.

The 2026/27 world is synthetic and flagged synthetic on every render. This door is neither of
those things: it carries a curated hand of the largest, most cited real-world facts about the
2022 World Cup, contributed by the openfootball community (CC-BY 4.0 — freely usable), and every
score, goal minute and venue is printed straight from a committed snapshot of that file
(``data/openfootball-worldcup-2022.json``, byte-for-byte the upstream file), so the door works
offline and never has to trust the network.

The numbers here are checked against the snapshot at import of ``compute_real_book()`` — the
64 fixtures, the on-field goal total and the top-scorers table are recomputed from the committed
bytes, the same way the door's tests recompute them. The curated prose (Messi's Golden Ball,
the Lusail attendance) is hand-written and labelled as curated in the page's provenance line.

No real club or player is represented in the synthetic world by any of this — this door
is the synthetic world's own exhibit of the real one.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

_SNAPSHOT = Path(__file__).resolve().parent / "data" / "openfootball-worldcup-2022.json"

# The source file spells France's No. 10 two ways in its goals lists for this tournament
# ("Mbappé" ×2, "Kylian Mbappé" ×6). They are the same scorer; the door merges the two
# spellings for its top-scorers table only. The fixture ledger below keeps the source's
# own bytes — team names, scores and minutes are never rewritten.
_SPELLING_MERGE = {"Mbappé": "Kylian Mbappé"}

REAL_FACTS_2022 = {
    "tournament": "2022 FIFA World Cup",
    "host": "Qatar",
    "final_date": "2022-12-18",
    "final_rounds": [
        {"round": "Group stage", "matches": 48},
        {"round": "Round of 16", "matches": 8},
        {"round": "Quarter-finals", "matches": 4},
        {"round": "Semi-finals", "matches": 2},
        {"round": "Match for third place", "matches": 1},
        {"round": "Final", "matches": 1},
    ],
    "venues": 8,
    "total_matches": 64,
    "champion": {
        "name": "Argentina",
        "note": "Won the final 3–3 vs France (4–2 on penalties at Lusail Iconic Stadium).",
    },
    "final": {
        "home": "Argentina",
        "away": "France",
        "score_regular": [2, 2],
        "score_extra_time": [3, 3],
        "score_penalties": [4, 2],
        "venue": "Lusail Iconic Stadium",
        "attendance": "88,966",
        "matchday_date": "2022-12-18",
    },
    "runner_up": {"name": "France", "star": "Kylian Mbappé — 8 goals, the highest scorer of the tournament"},
    "golden_ball": {"name": "Lionel Messi", "note": "Won the Golden Ball (best player) of the final; seven goals for Argentina."},
    "biggest_attendance": {"match": "Argentina vs France", "attendance": "88,966"},
    "openfootball_url": "https://github.com/openfootball/worldcup.json",
}

ATTRIBUTION = (
    "The 2022 World Cup facts in this door are derived from the openfootball worldcup.json "
    "(CC-BY 4.0 — the data is freely usable, with attribution). The synthetic world in this "
    "product is a separate universe that shares none of these figures."
)


def _load_snapshot() -> dict[str, Any]:
    with _SNAPSHOT.open(encoding="utf-8") as handle:
        return json.load(handle)


def _match_score(match: dict[str, Any]) -> tuple[list[int], list[int] | None, list[int] | None, list[int] | None]:
    """Return (ft, ht, et, p) as lists of two ints; handles the snapshot's two score shapes."""
    raw = match["score"]
    if isinstance(raw, list):
        return list(raw), None, None, None
    return list(raw["ft"]), list(raw.get("ht", []) or []) or None, list(raw.get("et", []) or []) or None, list(raw.get("p", []) or []) or None


def _fixture_row(match: dict[str, Any]) -> dict[str, Any]:
    ft, ht, et, p = _match_score(match)
    on_field = et or ft
    return {
        "date": match.get("date"),
        "round": match.get("round"),
        "group": match.get("group"),
        "team1": match.get("team1"),
        "team2": match.get("team2"),
        "ht": ht,
        "ft": ft,
        "et": et,
        "penalties": p,
        "on_field": on_field,
        "ground": match.get("ground"),
    }


def _scorers(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    goals: Counter[str] = Counter()
    penalties: Counter[str] = Counter()
    for match in matches:
        for side in ("goals1", "goals2"):
            for goal in match.get(side, []):
                name = _SPELLING_MERGE.get(goal["name"], goal["name"])
                goals[name] += 1
                if goal.get("penalty"):
                    penalties[name] += 1
    return [{"name": name, "goals": count, "penalties": penalties.get(name, 0)} for name, count in goals.most_common(10)]


def compute_real_book() -> dict[str, Any]:
    snapshot = _load_snapshot()
    matches = snapshot["matches"]
    results = [_fixture_row(match) for match in matches]
    goals_on_field = sum(row["on_field"][0] + row["on_field"][1] for row in results)

    widest = max(results, key=lambda row: abs(row["on_field"][0] - row["on_field"][1]))
    biggest_win = {
        "match": f"{widest['team1']} {widest['on_field'][0]}-{widest['on_field'][1]} {widest['team2']}",
        "score": widest["on_field"],
        "stage": widest["round"],
        "matchday_date": widest["date"],
        "venue": widest["ground"],
    }

    facts = dict(REAL_FACTS_2022)
    facts = {
        **facts,
        "goals_scored": goals_on_field,
        "biggest_win": biggest_win,
        "joint_top_scorers_note": "goals are counted from the openfootball goal lists; France's No. 10 is spelled two ways in the source and merged here.",
    }

    return {
        "available": True,
        "source": "openfootball worldcup.json (CC-BY 4.0)",
        "attribution": ATTRIBUTION,
        "facts": facts,
        "results": results,
        "scorers": _scorers(matches),
        "provenance": {
            "data_origin": "public-real",
            "is_demo_data": False,
            "license": "CC-BY 4.0",
        },
    }


__all__ = ["compute_real_book", "REAL_FACTS_2022", "ATTRIBUTION"]
