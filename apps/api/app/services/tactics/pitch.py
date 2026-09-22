"""Pitch geometry in metres — the coordinate system every tactical number is measured in.

Why a module of its own: the Tactical Lab's claims (a side is too wide, its lines are 12 m apart,
a change opens 6 m behind) must be *reproducible* from stored coordinates, not restated from prose.
So the geometry lives here, pure and deterministic, with the formula kept next to the function that
computes it — the API hands both to the web tier, which renders them (spec §62).

Convention (stated once, used everywhere):

* origin = centre of the team's **own** goal line, on the grass
* `y` = 0 … 105 m toward the opponent's goal (so "higher up the pitch" means larger `y`)
* `x` = -34 … +34 m across the width, negative is the team's left
* a stored point is the centre of a player's boots, and every metric is documented in those terms

The dimensions are the ones written in the Laws of the Game (IFAB Law 1); they are measurements of
a playing area, not creative content.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Final

# --- Law 1: a senior pitch is at most 110 × 68 m; the international standard used here is 105 × 68.
PITCH_LENGTH: Final = 105.0
PITCH_WIDTH: Final = 68.0
HALF_WIDTH: Final = PITCH_WIDTH / 2
PENALTY_AREA_DEPTH: Final = 16.5
PENALTY_AREA_WIDTH: Final = 40.32
GOAL_AREA_DEPTH: Final = 5.5
GOAL_AREA_WIDTH: Final = 18.32
CENTRE_CIRCLE_RADIUS: Final = 9.15
GOAL_WIDTH: Final = 7.32

# Three vertical bands, measured from the team's own goal line.
THIRD_DEFENSIVE: Final = "defensive"
THIRD_MIDDLE: Final = "middle"
THIRD_ATTACKING: Final = "attacking"

# Five channels across the width, numbered from the team's left.
LANES: Final = ("LW", "LC", "C", "RC", "RW")

__all__ = [
    "CENTRE_CIRCLE_RADIUS",
    "GOAL_AREA_DEPTH",
    "GOAL_AREA_WIDTH",
    "GOAL_WIDTH",
    "LANES",
    "PENALTY_AREA_DEPTH",
    "PENALTY_AREA_WIDTH",
    "PITCH_LENGTH",
    "PITCH_WIDTH",
    "THIRD_ATTACKING",
    "THIRD_DEFENSIVE",
    "THIRD_MIDDLE",
    "Point",
    "centroid",
    "clamp_point",
    "distance",
    "lane_of",
    "nearest_neighbour_distances",
    "out_of_bounds",
    "pitch_area",
    "third_of",
    "zone_of",
]


@dataclass(frozen=True)
class Point:
    """One player's position in metres. Frozen so a plan built twice cannot drift."""

    x: float
    y: float

    def __post_init__(self) -> None:
        # `float("nan")` would pass `<=` comparisons silently and poison every aggregate.
        if not (math.isfinite(self.x) and math.isfinite(self.y)):
            raise ValueError(f"non-finite coordinate: {self!r}")

    def scaled(self, dx: float = 0.0, dy: float = 0.0) -> Point:
        """A translated copy, still inside the pitch — the primitive behind every counterfactual."""
        return clamp_point(Point(self.x + dx, self.y + dy))

    def as_dict(self) -> dict[str, float]:
        return {"x": round(self.x, 2), "y": round(self.y, 2)}


def out_of_bounds(point: Point) -> list[str]:
    """Every rule this point breaks, so a validator can name the failure instead of rejecting blindly."""
    problems: list[str] = []
    if abs(point.x) > HALF_WIDTH:
        problems.append(f"x={point.x} is outside -{HALF_WIDTH}…+{HALF_WIDTH} m")
    if not 0.0 <= point.y <= PITCH_LENGTH:
        problems.append(f"y={point.y} is outside 0…{PITCH_LENGTH} m")
    return problems


def clamp_point(point: Point) -> Point:
    """Pull a point back onto the grass. Coordinates are only ever moved *inside* the pitch."""
    return Point(
        max(-HALF_WIDTH, min(HALF_WIDTH, point.x)),
        max(0.0, min(PITCH_LENGTH, point.y)),
    )


def distance(a: Point, b: Point) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def pitch_area() -> float:
    return PITCH_LENGTH * PITCH_WIDTH


def third_of(point: Point) -> str:
    """Which third of the pitch the point sits in, measured from this team's own goal line."""
    if point.y < PITCH_LENGTH / 3:
        return THIRD_DEFENSIVE
    if point.y < 2 * PITCH_LENGTH / 3:
        return THIRD_MIDDLE
    return THIRD_ATTACKING


def lane_of(point: Point) -> str:
    """One of five equal channels, from this team's left wing to its right."""
    index = min(len(LANES) - 1, max(0, int((point.x + HALF_WIDTH) / (PITCH_WIDTH / len(LANES)))))
    return LANES[index]


def zone_of(point: Point) -> str:
    """`third-lane`, the key the board colours and the analysis groups by."""
    return f"{third_of(point)}-{lane_of(point)}"


def nearest_neighbour_distances(points: Sequence[Point]) -> list[float]:
    """For each player, the distance to its closest team-mate — the raw form of "are they compact?".

    O(n²) on eleven points, which is 55 comparisons: nothing here needs a spatial index, and the
    naive version is the one a reader can check by hand.
    """
    return [min((distance(a, b) for b in points if b is not a), default=0.0) for a in points]


def centroid(points: Iterable[Point]) -> Point:
    """The mean position — the shape's centre of mass, not any player's location."""
    values = list(points)
    if not values:
        raise ValueError("centroid of no points is undefined")
    return Point(sum(p.x for p in values) / len(values), sum(p.y for p in values) / len(values))
