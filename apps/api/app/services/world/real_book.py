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
        "kind": "worldcup",
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
        "kind": "worldcup",
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
        "kind": "worldcup",
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
    "2010": {
        "kind": "worldcup",
        "snapshot": "openfootball-worldcup-2010.json",
        "spelling_merge": {},
        "facts": {
            "tournament": "2010 FIFA World Cup",
            "host": "South Africa",
            "final_date": "2010-07-11",
            "final_rounds": [
                {"round": "Group stage", "matches": 48},
                {"round": "Round of 16", "matches": 8},
                {"round": "Quarter-finals", "matches": 4},
                {"round": "Semi-finals", "matches": 2},
                {"round": "Match for third place", "matches": 1},
                {"round": "Final", "matches": 1},
            ],
            "venues": 10,
            "total_matches": 64,
            "has_penalties": False,
            "champion": {
                "name": "Spain",
                "note": "Won the final 1-0 vs Netherlands (Iniesta, 116', extra time) at Soccer City, Johannesburg.",
            },
            "final": {
                "home": "Netherlands",
                "away": "Spain",
                "score_regular": [0, 0],
                "score_extra_time": [0, 1],
                "score_penalties": [0, 0],
                "venue": "Soccer City, Johannesburg",
                "attendance": None,
                "matchday_date": "2010-07-11",
            },
            "runner_up": {"name": "Netherlands", "star": "Thomas Müller won the Golden Boot with 5 goals (curator knowledge; the 2010 snapshot carries fixtures, not scorer lists)"},
            "golden_ball": {"name": "Diego Forlán", "note": "Golden Ball, Uruguay — the tournament's best player with 5 goals (curator knowledge; the 2010 snapshot carries fixtures, not scorer lists)"},
            "openfootball_url": "https://github.com/openfootball/worldcup.json",
        },
        "joint_top_scorers_note": "the 2010 snapshot carries fixtures and scorelines, not scorer lists; the scorers table is absent from this cup and every top-scorer claim on the tiles is curator knowledge, labelled as such.",
    },
    "2006": {
        "kind": "worldcup",
        "snapshot": "openfootball-worldcup-2006.json",
        "spelling_merge": {},
        "facts": {
            "tournament": "2006 FIFA World Cup",
            "host": "Germany",
            "final_date": "2006-07-09",
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
            "has_penalties": True,
            "champion": {
                "name": "Italy",
                "note": "Won the final 1-1 vs France (5-3 on penalties) at Olympiastadion, Berlin.",
            },
            "final": {
                "home": "Italy",
                "away": "France",
                "score_regular": [1, 1],
                "score_extra_time": [1, 1],
                "score_penalties": [5, 3],
                "venue": "Olympiastadion, Berlin",
                "attendance": None,
                "matchday_date": "2006-07-09",
            },
            "runner_up": {"name": "France", "star": "Zinedine Zidane — the Golden Ball, won by the final's runner-up; he was sent off in extra time for a headbutt after levelling from the spot"},
            "golden_ball": {"name": "Fabio Cannavaro", "note": "Golden Ball, Italy — the champions' captain and best player (curator knowledge; the 2006 snapshot carries only a partial scorer list, no minutes table)"},
            "openfootball_url": "https://github.com/openfootball/worldcup.json",
        },
        "joint_top_scorers_note": "the 2006 snapshot carries goal minutes only for nine entries in four matches; the door prints no scorers table for this cup, and every scorer claim on the tiles is curator knowledge, labelled as such.",
        "skip_scorers": True,
    },
    "2002": {
        "kind": "worldcup",
        "snapshot": "openfootball-worldcup-2002.json",
        "spelling_merge": {},
        "facts": {
            "tournament": "2002 FIFA World Cup",
            "host": "South Korea & Japan",
            "final_date": "2002-06-30",
            "final_rounds": [
                {"round": "Group stage", "matches": 48},
                {"round": "Round of 16", "matches": 8},
                {"round": "Quarter-finals", "matches": 4},
                {"round": "Semi-finals", "matches": 2},
                {"round": "Match for third place", "matches": 1},
                {"round": "Final", "matches": 1},
            ],
            "venues": 20,
            "total_matches": 64,
            "has_penalties": False,
            "champion": {
                "name": "Brazil",
                "note": "Won the final 2-0 vs Germany at International Stadium Yokohama (Ronaldo, twice in the second half).",
            },
            "final": {
                "home": "Germany",
                "away": "Brazil",
                "score_regular": [0, 2],
                "score_extra_time": [0, 2],
                "score_penalties": [0, 0],
                "venue": "International Stadium Yokohama, Yokohama",
                "attendance": None,
                "matchday_date": "2002-06-30",
            },
            "runner_up": {"name": "Germany", "star": "Germany reached the final — the Golden Ball went to their goalkeeper, Oliver Kahn (see the Golden Ball tile)"},
            "golden_ball": {"name": "Oliver Kahn", "note": "Golden Ball, Germany — the tournament's best player, a goalkeeper for the losing finalists (curator knowledge; the 2002 snapshot carries fixtures, not scorer lists)"},
            "openfootball_url": "https://github.com/openfootball/worldcup.json",
        },
        "joint_top_scorers_note": "the 2002 snapshot carries fixtures and scorelines, not scorer lists; the scorers table is absent from this cup and every top-scorer claim on the tiles is curator knowledge, labelled as such.",
    },
    "1998": {
        "kind": "worldcup",
        "snapshot": "openfootball-worldcup-1998.json",
        "spelling_merge": {},
        "facts": {
            "tournament": "1998 FIFA World Cup",
            "host": "France",
            "final_date": "1998-07-12",
            "final_rounds": [
                {"round": "Group stage", "matches": 48},
                {"round": "Round of 16", "matches": 8},
                {"round": "Quarter-finals", "matches": 4},
                {"round": "Semi-finals", "matches": 2},
                {"round": "Match for third place", "matches": 1},
                {"round": "Final", "matches": 1},
            ],
            "venues": 10,
            "total_matches": 64,
            "has_penalties": False,
            "champion": {
                "name": "France",
                "note": "Won the final 3-0 vs Brazil at Stade de France, Saint-Denis.",
            },
            "final": {
                "home": "Brazil",
                "away": "France",
                "score_regular": [0, 3],
                "score_extra_time": [0, 3],
                "score_penalties": [0, 0],
                "venue": "Stade de France, Saint-Denis",
                "attendance": None,
                "matchday_date": "1998-07-12",
            },
            "runner_up": {"name": "Brazil", "star": "Ronaldo — the Golden Ball, won by the final's runner-up (curator knowledge; the 1998 snapshot carries fixtures, not scorer lists)"},
            "golden_ball": {"name": "Ronaldo", "note": "Golden Ball, Brazil — the tournament's best player (curator knowledge; the 1998 snapshot carries fixtures, not scorer lists)"},
            "openfootball_url": "https://github.com/openfootball/worldcup.json",
        },
        "joint_top_scorers_note": "the 1998 snapshot carries fixtures and scorelines, not scorer lists; the scorers table is absent from this cup and every top-scorer claim on the tiles is curator knowledge, labelled as such.",
    },
    "1994": {
        "kind": "worldcup",
        "snapshot": "openfootball-worldcup-1994.json",
        "spelling_merge": {},
        "facts": {
            "tournament": "1994 FIFA World Cup",
            "host": "United States",
            "final_date": "1994-07-17",
            "final_rounds": [
                {"round": "Group stage", "matches": 36},
                {"round": "Round of 16", "matches": 8},
                {"round": "Quarter-finals", "matches": 4},
                {"round": "Semi-finals", "matches": 2},
                {"round": "Match for third place", "matches": 1},
                {"round": "Final", "matches": 1},
            ],
            "venues": 9,
            "total_matches": 52,
            "has_penalties": True,
            "champion": {
                "name": "Brazil",
                "note": "Won the final 0-0 vs Italy (3-2 on penalties) at the Rose Bowl, Pasadena.",
            },
            "final": {
                "home": "Brazil",
                "away": "Italy",
                "score_regular": [0, 0],
                "score_extra_time": [0, 0],
                "score_penalties": [3, 2],
                "venue": "Rose Bowl, Pasadena",
                "attendance": None,
                "matchday_date": "1994-07-17",
            },
            "runner_up": {"name": "Italy", "star": "Roberto Baggio's penalty flew above the bar in the shoot-out — the final was decided from the spot (curator knowledge; the 1994 snapshot carries fixtures, not scorer lists)"},
            "golden_ball": {"name": "Romário", "note": "Golden Ball, Brazil — the tournament's best player (curator knowledge; the 1994 snapshot carries fixtures, not scorer lists)"},
            "openfootball_url": "https://github.com/openfootball/worldcup.json",
        },
        "joint_top_scorers_note": "the 1994 snapshot carries fixtures and scorelines, not scorer lists; the scorers table is absent from this cup and every top-scorer claim on the tiles is curator knowledge, labelled as such.",
    },
    "1990": {
        "kind": "worldcup",
        "snapshot": "openfootball-worldcup-1990.json",
        "spelling_merge": {},
        "facts": {
            "tournament": "1990 FIFA World Cup",
            "host": "Italy",
            "final_date": "1990-07-08",
            "final_rounds": [
                {"round": "Group stage", "matches": 36},
                {"round": "Round of 16", "matches": 8},
                {"round": "Quarter-finals", "matches": 4},
                {"round": "Semi-finals", "matches": 2},
                {"round": "Match for third place", "matches": 1},
                {"round": "Final", "matches": 1},
            ],
            "venues": 14,
            "total_matches": 52,
            "has_penalties": False,
            "champion": {
                "name": "West Germany",
                "note": "Won the final 1-0 vs Argentina (Brehme, 85', from the spot) at Stadio Olimpico, Rome.",
            },
            "final": {
                "home": "West Germany",
                "away": "Argentina",
                "score_regular": [1, 0],
                "score_extra_time": [1, 0],
                "score_penalties": [0, 0],
                "venue": "Stadio Olimpico, Rome",
                "attendance": None,
                "matchday_date": "1990-07-08",
            },
            "runner_up": {"name": "Argentina", "star": "Argentina reached the final for the second consecutive World Cup (curator knowledge; the 1990 snapshot carries only eight scorer entries)"},
            "golden_ball": {"name": "Salvatore Schillaci", "note": "Golden Ball, Italy — the tournament's best player with 6 goals (curator knowledge; the 1990 snapshot carries only eight scorer entries)"},
            "openfootball_url": "https://github.com/openfootball/worldcup.json",
        },
        "joint_top_scorers_note": "the 1990 snapshot carries goal minutes for eight entries in five matches; the door prints no scorers table for this cup, and every top-scorer claim on the tiles is curator knowledge, labelled as such.",
        "skip_scorers": True,
    },
    "1986": {
        "kind": "worldcup",
        "snapshot": "openfootball-worldcup-1986.json",
        "spelling_merge": {},
        "facts": {
            "tournament": "1986 FIFA World Cup",
            "host": "Mexico",
            "final_date": "1986-06-29",
            "final_rounds": [
                {"round": "Group stage", "matches": 36},
                {"round": "Round of 16", "matches": 8},
                {"round": "Quarter-finals", "matches": 4},
                {"round": "Semi-finals", "matches": 2},
                {"round": "Match for third place", "matches": 1},
                {"round": "Final", "matches": 1},
            ],
            "venues": 12,
            "total_matches": 52,
            "has_penalties": False,
            "champion": {
                "name": "Argentina",
                "note": "Won the final 3-2 vs West Germany at Estadio Azteca, Mexico City.",
            },
            "final": {
                "home": "Argentina",
                "away": "West Germany",
                "score_regular": [3, 2],
                "score_extra_time": [3, 2],
                "score_penalties": [0, 0],
                "venue": "Estadio Azteca, Mexico City",
                "attendance": None,
                "matchday_date": "1986-06-29",
            },
            "runner_up": {"name": "West Germany", "star": "Gary Lineker — the Golden Boot with 6 goals (curator knowledge; the 1986 snapshot carries fixtures, not scorer lists)"},
            "golden_ball": {"name": "Diego Maradona", "note": "Golden Ball, Argentina — the tournament's best player (curator knowledge; the 1986 snapshot carries fixtures, not scorer lists)"},
            "openfootball_url": "https://github.com/openfootball/worldcup.json",
        },
        "joint_top_scorers_note": "the 1986 snapshot carries fixtures and scorelines, not scorer lists; the scorers table is absent from this cup and every top-scorer claim on the tiles is curator knowledge, labelled as such.",
    },
    "euro2024": {
        "kind": "euro",
        "snapshot": "openfootball-euro-2024.json",
        "spelling_merge": {},
        "facts": {
            "tournament": "UEFA Euro 2024",
            "host": "Germany",
            "final_date": "2024-07-14",
            "final_rounds": [
                {"round": "Group stage", "matches": 36},
                {"round": "Round of 16", "matches": 8},
                {"round": "Quarter-finals", "matches": 4},
                {"round": "Semi-finals", "matches": 2},
                {"round": "Final", "matches": 1},
            ],
            "venues": 10,
            "total_matches": 51,
            "has_penalties": False,
            "champion": {
                "name": "Spain",
                "note": "Won the final 2-1 vs England (Oyarzabal, 86') at Berlin.",
            },
            "final": {
                "home": "Spain",
                "away": "England",
                "score_regular": [2, 1],
                "score_extra_time": [2, 1],
                "score_penalties": [0, 0],
                "venue": "Berlin",
                "attendance": None,
                "matchday_date": "2024-07-14",
            },
            "runner_up": {"name": "England", "star": "Harry Kane — co-top scorer with 3 goals; the Golden Boot was shared by six players with 3 goals each (Musiala, Kane, Gakpo, Malen, Schranz, Mikautadze) (curator knowledge; the snapshot carries the goals, not the boot credit)"},
            "golden_ball": {"name": "Rodri", "note": "Golden Ball, Spain — the tournament's best player (curator knowledge)"},
            "openfootball_url": "https://github.com/openfootball/euro.json",
        },
        "joint_top_scorers_note": "goals are counted from the openfootball euro.json snapshot (Euro 2024, CC-BY 4.0) as committed. The Golden Boot was shared by six players with 3 goals each; the snapshot does not name a single winner.",
    },
    "euro2021": {
        "kind": "euro",
        "snapshot": "openfootball-euro-2021.json",
        "spelling_merge": {},
        "facts": {
            "tournament": "UEFA Euro 2021 (the 2020 European Championship)",
            "host": "11 cities across Europe",
            "final_date": "2021-07-11",
            "final_rounds": [
                {"round": "Group stage", "matches": 36},
                {"round": "Round of 16", "matches": 8},
                {"round": "Quarter-finals", "matches": 4},
                {"round": "Semi-finals", "matches": 2},
                {"round": "Final", "matches": 1},
            ],
            "venues": 11,
            "total_matches": 51,
            "has_penalties": True,
            "champion": {
                "name": "Italy",
                "note": "Won the final 1-1 vs England (Bonucci 67') 3-2 on penalties at London (Wembley).",
            },
            "final": {
                "home": "Italy",
                "away": "England",
                "score_regular": [1, 1],
                "score_extra_time": [1, 1],
                "score_penalties": [3, 2],
                "venue": "London",
                "attendance": None,
                "matchday_date": "2021-07-11",
            },
            "runner_up": {"name": "England", "star": "Patrick Schick and Cristiano Ronaldo — co-top scorers with 5 goals each (curator knowledge; the snapshot carries the goals, not the boot credit)"},
            "golden_ball": {"name": "Gianluigi Donnarumma", "note": "Golden Ball, Italy — the tournament's best player, the final's shoot-out hero (curator knowledge)"},
            "openfootball_url": "https://github.com/openfootball/euro.json",
        },
        "joint_top_scorers_note": "goals are counted from the openfootball euro.json snapshot (Euro 2021, played in 2021 against Global tournament postponement, CC-BY 4.0) as committed. The Golden Boot was shared; the snapshot does not name a single winner.",
    },
}

ATTRIBUTION = (
    "The World Cup facts in this door are derived from the openfootball worldcup.json "
    "(CC-BY 4.0 — the data is freely usable, with attribution). The synthetic world in this "
    "product is a separate universe that shares none of these figures."
)


class UnknownTournament(ValueError):
    """Raised when the requested tournament is not one the door carries."""


def tournaments(kind: str | None = "worldcup") -> list[str]:
    if kind is None:
        return list(_REGISTRY)
    return [key for key, entry in _REGISTRY.items() if entry.get("kind", "worldcup") == kind]


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

    scorers = _scorers(matches, registry["spelling_merge"])
    if registry.get("skip_scorers"):
        # The 2006 snapshot transcribes goal minutes only for nine entries in four matches; printing them as
        # "the scorers, counted from the file" would be a false claim. The fixtures ledger still prints in full.
        scorers = []

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
        "scorers": scorers,
        "provenance": {
            "data_origin": "public-real",
            "is_demo_data": False,
            "license": "CC-BY 4.0",
        },
    }


__all__ = ["compute_real_book", "ATTRIBUTION", "tournaments", "UnknownTournament"]
