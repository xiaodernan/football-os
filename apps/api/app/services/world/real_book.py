"""The Real Book — the real world's football, snapshot-verified, not derived from the seed.

The 2026/27 world is synthetic and flagged synthetic on every render. This door is neither of
those things: it carries curated facts about the real FIFA World Cups of 2018 and 2022,
contributed by the openfootball community (CC-BY 4.0 — freely usable), and every score, goal
minute and venue is printed straight from committed snapshots of those files (under ``data/``),
so the door works offline and never has to trust the network.

The numbers here are recomputed from the committed bytes on every ``compute_real_book()`` call —
the fixtures, the on-field goal total and the top-scorers table included. The curated prose
(Messi's Golden Ball, the Luzhniki attendance question) is hand-written and labelled as curated
in the page's provenance line.

No real club or player is represented in the synthetic world by any of this — this door
is the synthetic world's own exhibit of the real one.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

_DATA = Path(__file__).resolve().parent / "data"

# Per-tournament registry. The 2018 snapshot spells players the way the source spells them;
# no names are merged there. The 2022 snapshot spells France's No. 10 two ways and this module
# merges them for the door's scorers table — the fixture ledger keeps the source's own bytes.
_REGISTRY: dict[str, dict[str, Any]] = {
    "2022": {
        "snapshot": "openfootball-worldcup-2022.json",
        "spelling_merge": {"Mbappé": "Kylian Mbappé"},
        "facts": {
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
            "has_penalties": True,
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
        },
        "joint_top_scorers_note": "goals are counted from the openfootball goal lists; France's No. 10 is spelled two ways in the source and merged here.",
    },
    "2018": {
        "snapshot": "openfootball-worldcup-2018.json",
        "spelling_merge": {},
        "facts": {
            "tournament": "2018 FIFA World Cup",
            "host": "Russia",
            "final_date": "2018-07-15",
            "final_rounds": [
                {"round": "Group stage", "matches": 48},
                {"round": "Round of 16", "matches": 8},
                {"round": "Quarter-finals", "matches": 4},
                {"round": "Semi-finals", "matches": 2},
                {"round": "Match for third place", "matches": 1},
                {"round": "Final", "matches": 1},
            ],
            "venues": 13,
            "total_matches": 64,
            "has_penalties": False,
            "champion": {
                "name": "France",
                "note": "Won the final 4–2 vs Croatia (2–1 at half time) at Luzhniki Stadium, Moscow.",
            },
            "final": {
                "home": "France",
                "away": "Croatia",
                "score_regular": [4, 2],
                "score_extra_time": [4, 2],
                "score_penalties": [0, 0],
                "venue": "Luzhniki Stadium",
                "attendance": None,
                "matchday_date": "2018-07-15",
            },
            "runner_up": {"name": "Croatia", "star": "Luka Modrić — the Golden Ball, won by the final's runner-up"},
            "golden_ball": {"name": "Luka Modrić", "note": "Golden Ball, Croatia — the tournament's best player, won by a player whose team lost the final."},
            "openfootball_url": "https://github.com/openfootball/worldcup.json",
        },
        "joint_top_scorers_note": "goals are counted from the openfootball goal lists as committed, without merging; the FIFA Golden Boot credit is curator knowledge.",
    },
    "2014": {
        "snapshot": "openfootball-worldcup-2014.json",
        "spelling_merge": {},
        "facts": {
            "tournament": "2014 FIFA World Cup",
            "host": "Brazil",
            "final_date": "2014-07-13",
            "final_rounds": [
                {"round": "Group stage", "matches": 48},
                {"round": "Round of 16", "matches": 8},
                {"round": "Quarter-finals", "matches": 4},
                {"round": "Semi-finals", "matches": 2},
                {"round": "Match for third place", "matches": 1},
                {"round": "Final", "matches": 1},
            ],
            "venues": 12,
            "total_matches": 64,
            "has_penalties": False,
            "champion": {
                "name": "Germany",
                "note": "Won the final 1–0 vs Argentina (Götze, 113') at Maracanã Stadium, Rio de Janeiro.",
            },
            "final": {
                "home": "Germany",
                "away": "Argentina",
                "score_regular": [0, 0],
                "score_extra_time": [1, 0],
                "score_penalties": [0, 0],
                "venue": "Maracanã Stadium",
                "attendance": None,
                "matchday_date": "2014-07-13",
            },
            "runner_up": {"name": "Argentina", "star": "Lionel Messi — the Golden Ball, won for the second tournament in a row"},
            "golden_ball": {"name": "Lionel Messi", "note": "Golden Ball, Argentina — won while losing the final, as in 2010."},
            "openfootball_url": "https://github.com/openfootball/worldcup.json",
        },
        "joint_top_scorers_note": "goals are counted from the openfootball goal lists as committed, without merging; the FIFA Golden Boot credit is curator knowledge (James Rodríguez's six-goal tally is the canonical citation)",
    },
}

ATTRIBUTION = (
    "The World Cup facts in this door are derived from the openfootball worldcup.json "
    "(CC-BY 4.0 — the data is freely usable, with attribution). The synthetic world in this "
    "product is a separate universe that shares none of these figures."
)


class UnknownTournament(ValueError):
    """Raised when the requested tournament is not one the door carries."""


def tournaments() -> list[str]:
    return list(_REGISTRY)


def _load_snapshot(filename: str) -> dict[str, Any]:
    with (_DATA / filename).open(encoding="utf-8") as handle:
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


def _scorers(matches: list[dict[str, Any]], merge: dict[str, str]) -> list[dict[str, Any]]:
    goals: Counter[str] = Counter()
    penalties: Counter[str] = Counter()
    for match in matches:
        for side in ("goals1", "goals2"):
            for goal in match.get(side, []):
                name = merge.get(goal["name"], goal["name"])
                goals[name] += 1
                if goal.get("penalty"):
                    penalties[name] += 1
    return [{"name": name, "goals": count, "penalties": penalties.get(name, 0)} for name, count in goals.most_common(10)]


def compute_real_book(tournament: str = "2022") -> dict[str, Any]:
    registry = _REGISTRY.get(tournament)
    if registry is None:
        raise UnknownTournament(tournament)

    snapshot = _load_snapshot(registry["snapshot"])
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

    facts = dict(registry["facts"])
    facts = {
        **facts,
        "goals_scored": goals_on_field,
        "biggest_win": biggest_win,
        "joint_top_scorers_note": registry["joint_top_scorers_note"],
    }

    return {
        "available": True,
        "tournament": tournament,
        "source": "openfootball worldcup.json (CC-BY 4.0)",
        "attribution": ATTRIBUTION,
        "facts": facts,
        "results": results,
        "scorers": _scorers(matches, registry["spelling_merge"]),
        "provenance": {
            "data_origin": "public-real",
            "is_demo_data": False,
            "license": "CC-BY 4.0",
        },
    }


__all__ = ["compute_real_book", "ATTRIBUTION", "tournaments", "UnknownTournament"]
