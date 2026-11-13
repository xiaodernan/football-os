"""The head-to-head: two footballers, one ledger, and a verdict that can be argued with.

The product has a comparison page for tactical systems (``/tactics/compare``) and never had one for the
people who play. This module is the arithmetic behind it, kept free of the database so the only thing it
can be wrong about is the comparison itself.

**What the verdict is.** Not a score out of a hundred — that number would be invented, and every invented
number looks like a measurement. It is a tally: seven categories, each one a column that already exists in
the world's tables, each one won, lost or levelled on its own terms, and the duellist who wins more of them
wins the duel. A 5–2 tally is a claim a reader can check column by column; a 87.4 "duel rating" is not.

**What it refuses to compare.** A per-90 rate needs minutes. A player with fewer than one full match has a
per-90 that is technically computable and statistically meaningless — one goal in nine minutes is "10.0 per
90" — so the category is marked unavailable rather than counted, and the verdict says how many of the seven
were actually decided. Silence about a category is a fact; a zero would be a lie.
"""

from __future__ import annotations

from typing import Any, Final

from app.models import RealPlayer

#: The shortest spell that makes a per-90 rate worth printing: one full match.
PER90_FLOOR_MINUTES: Final = 90

#: One yellow is a booking; one red is a sending-off and the match after it. Weighting the red at three
#: yellows is a convention, and it is written here so the column can be recomputed rather than trusted.
RED_WEIGHT: Final = 3

#: The order is the order the page prints, and the order a tie is broken in: goals first, because that is
#: what a reader came for, and discipline last, because it is the category nobody wants to win.
CATEGORY_ORDER: Final[tuple[str, ...]] = (
    "goals",
    "assists",
    "involvement_per_90",
    "rating",
    "minutes",
    "overall",
    "discipline",
)

#: Each category names its basis as a code, not a sentence: the API is read by clients in six languages and
#: a sentence here would be an English string shipped to five of them. `qa-api-strings` holds that line.
BASIS: Final[dict[str, str]] = {
    "goals": "season_total",
    "assists": "season_total",
    "involvement_per_90": "per_90",
    "rating": "season_mean",
    "minutes": "season_total",
    "overall": "coach_rating",
    "discipline": "weighted_cards",
}


def _per90(value: int, minutes: int) -> float | None:
    if minutes < PER90_FLOOR_MINUTES:
        return None
    return round(value * 90 / minutes, 2)


def _discipline(player: RealPlayer) -> int:
    return int(player.yellow_cards) + RED_WEIGHT * int(player.red_cards)


def _value(key: str, player: RealPlayer) -> float | None:
    """The raw figure for one category. `None` means the category cannot be decided, not that it is zero."""
    if key == "goals":
        return float(player.goals)
    if key == "assists":
        return float(player.assists)
    if key == "involvement_per_90":
        return _per90(int(player.goals) + int(player.assists), int(player.minutes))
    if key == "rating":
        return round(float(player.rating), 2)
    if key == "minutes":
        return float(player.minutes)
    if key == "overall":
        return float(player.overall)
    if key == "discipline":
        return float(_discipline(player))
    raise KeyError(key)


def _margin(left: float, right: float) -> float:
    return round(abs(left - right), 2)


def _row(key: str, left: RealPlayer, right: RealPlayer) -> dict[str, Any]:
    """One line of the ledger: both figures, who won it, and by how much.

    `lower_wins` is discipline's alone — a booking is not an achievement. Everything else is a count, a mean
    or a rate that a reader expects to see larger on the better side.
    """
    lower_wins = key == "discipline"
    left_value = _value(key, left)
    right_value = _value(key, right)
    if left_value is None or right_value is None:
        return {
            "key": key,
            "basis": BASIS[key],
            "lower_wins": lower_wins,
            "left": left_value,
            "right": right_value,
            "winner": "unavailable",
            "margin": None,
        }
    if left_value == right_value:
        winner = "level"
    elif (left_value > right_value) != lower_wins:
        winner = "left"
    else:
        winner = "right"
    return {
        "key": key,
        "basis": BASIS[key],
        "lower_wins": lower_wins,
        "left": left_value,
        "right": right_value,
        "winner": winner,
        "margin": _margin(left_value, right_value),
    }


def per90(player: RealPlayer) -> dict[str, float | None]:
    """The rates the player's own page shows, computed once here so two pages cannot disagree."""
    goals = int(player.goals)
    assists = int(player.assists)
    minutes = int(player.minutes)
    return {
        "goals": _per90(goals, minutes),
        "assists": _per90(assists, minutes),
        "involvement": _per90(goals + assists, minutes),
        "minutes_per_appearance": round(minutes / player.appearances, 1) if player.appearances else None,
    }


def compare(left: RealPlayer, right: RealPlayer) -> dict[str, Any]:
    """The ledger and the verdict. Pure: no session, no clock, no randomness."""
    rows = [_row(key, left, right) for key in CATEGORY_ORDER]
    counted = [row for row in rows if row["winner"] in {"left", "right"}]
    left_wins = [row["key"] for row in counted if row["winner"] == "left"]
    right_wins = [row["key"] for row in counted if row["winner"] == "right"]
    if len(left_wins) == len(right_wins):
        winner = "draw"
        decided_by: list[str] = []
    elif len(left_wins) > len(right_wins):
        winner = "left"
        decided_by = left_wins
    else:
        winner = "right"
        decided_by = right_wins
    return {
        "categories": rows,
        "verdict": {
            "winner": winner,
            "left_wins": len(left_wins),
            "right_wins": len(right_wins),
            "levelled": len([row for row in rows if row["winner"] == "level"]),
            "unavailable": len([row for row in rows if row["winner"] == "unavailable"]),
            "counted": len(counted),
            "decided_by": decided_by,
            "left_categories": left_wins,
            "right_categories": right_wins,
        },
        "method": {
            "categories": list(CATEGORY_ORDER),
            "basis": dict(BASIS),
            "per90_floor_minutes": PER90_FLOOR_MINUTES,
            "red_weight": RED_WEIGHT,
            "verdict": "category_tally",
            "tie": "draw",
        },
    }
