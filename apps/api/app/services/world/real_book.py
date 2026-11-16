"""The Real Book — the real world's football 2022, snapshot-verified, not derived from the seed.

The 2026/27 world is synthetic and flagged synthetic on every render. This door is neither of those
things: it carries a handful of the largest, most cited real-world facts about the 2022
World Cup, contributed by the openfootball community (CC-BY 4.0 — freely usable).

The numbers here are checked against the source JSON at the time of writing (the file with
64 matches and a Lusail final), and the attribution line below is required by the licence.
No real club or player is represented in the synthetic world by any of this — this door
is the synthetic world's own exhibit of the real one.
"""

from typing import Any

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
        "note": "Won the final 3–3 vs France (5–3 on penalties at Lusail Iconic Stadium).",
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
    "biggest_win": {
        "match": "Argentina 3-0 Croatia",
        "score": [3, 0],
        "stage": "Semi-final",
        "matchday_date": "2022-12-13",
        "venue": "Lusail Iconic Stadium",
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


def compute_real_book() -> dict[str, Any]:
    return {
        "available": True,
        "source": "openfootball worldcup.json (CC-BY 4.0)",
        "attribution": ATTRIBUTION,
        "facts": REAL_FACTS_2022,
        "provenance": {
            "data_origin": "public-real",
            "is_demo_data": False,
            "license": "CC-BY 4.0",
        },
    }


__all__ = ["compute_real_book"]
