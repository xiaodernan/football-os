"""From authored metres to explainable numbers: shape transforms, metrics and counterfactuals.

Three rules the whole module obeys:

1. **Derive, never restate.** The out-of-possession shape is computed from the in-possession one by
   one published transform, so a board cannot show eleven players attacking and a different,
   unrelated eleven defending.
2. **Every metric ships with its formula.** `Metric.formula` reaches the API, so the page can print
   *how* 12.4 m was obtained instead of asking a reader to trust it (spec §62).
3. **A "what if" is arithmetic.** A counterfactual applies a named offset and recomputes; it can
   never produce a number the geometry does not support, and it reports which metric moved and by
   how much.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from statistics import mean
from typing import Final

from app.services.tactics.pitch import Point, centroid, clamp_point, nearest_neighbour_distances
from app.services.tactics.roles import ROLES
from app.services.tactics.shapes import Slot, Temperament

__all__ = [
    "CHANGES",
    "METRIC_KEYS",
    "Change",
    "Metric",
    "Shape",
    "ShapeDiff",
    "analyse",
    "apply_change",
    "in_possession",
    "metrics_of",
    "out_of_possession",
    "shape_from_rows",
]

# The eight measurements a shape yields, in the order `metrics_of` reports them. The test suite
# asserts the two agree, so this can be used as a contract without drifting.
METRIC_KEYS: Final = ("width", "depth", "coverage", "balance", "spacing", "isolation", "line_separation", "space_behind")


@dataclass(frozen=True)
class Shape:
    """Eleven labelled positions: the board's whole input."""

    slots: tuple[Slot, ...]
    points: tuple[Point, ...]

    def by_band(self) -> dict[str, list[Point]]:
        grouped: dict[str, list[Point]] = {}
        for slot, point in zip(self.slots, self.points, strict=True):
            grouped.setdefault(ROLES[slot.role].band, []).append(point)
        return grouped

    def outfield(self) -> tuple[Point, ...]:
        return tuple(point for slot, point in zip(self.slots, self.points, strict=True) if slot.role != "GK")

    def as_dict(self) -> list[dict[str, object]]:
        return [
            {
                "role": slot.role,
                "label": ROLES[slot.role].label,
                "band": ROLES[slot.role].band,
                "x": round(point.x, 2),
                "y": round(point.y, 2),
                "zone": f"{point.x:+.1f},{point.y:.1f}",
            }
            for slot, point in zip(self.slots, self.points, strict=True)
        ]


def shape_from_rows(rows: Sequence[Mapping[str, object]]) -> Shape:
    """The inverse of `Shape.as_dict()`.

    The API recomputes a counterfactual from the coordinates stored in the database rather than
    serving a stored answer, so the answer always matches the board a reader is looking at — and a
    row written by an older build cannot smuggle a stale conclusion.
    """
    slots = tuple(Slot(str(row["role"]), float(str(row["x"])), float(str(row["y"]))) for row in rows)
    return Shape(slots, tuple(slot.point() for slot in slots))


def in_possession(shape: Sequence[Slot], temperament: Temperament) -> Shape:
    """Balanced coordinates plus this temperament's documented per-role shifts."""
    points = tuple(clamp_point(slot.point().scaled(*(temperament.in_possession_deltas.get(slot.role, (0.0, 0.0))))) for slot in shape)
    return Shape(tuple(shape), points)


def out_of_possession(shape: Shape, temperament: Temperament) -> Shape:
    """The same eleven, rescaled into the defending block.

    Transform (published to the UI): the outfield players' `y` spans are mapped linearly from
    ``[min_y, max_y]`` onto ``[press_line - block_depth, press_line]``, and `x` is multiplied by
    ``defensive_narrowing``. The keeper stays on its line. Nothing is added or removed, so
    possession and non-possession are two views of one structure — which is what the animation
    interpolates between.
    """
    outfield_y = [point.y for slot, point in zip(shape.slots, shape.points, strict=True) if slot.role != "GK"]
    low, high = min(outfield_y), max(outfield_y)
    target_low = temperament.press_line_y - temperament.block_depth
    span = high - low or 1.0
    points: list[Point] = []
    for slot, point in zip(shape.slots, shape.points, strict=True):
        if slot.role == "GK":
            points.append(Point(point.x, min(point.y, 4.0)))
            continue
        ratio = (point.y - low) / span
        y = target_low + ratio * temperament.block_depth
        x = point.x * temperament.defensive_narrowing
        points.append(clamp_point(Point(x, y)))
    return Shape(shape.slots, tuple(points))


@dataclass(frozen=True)
class Metric:
    """One measured number, its unit, and the sentence that says how it was obtained."""

    key: str
    label: str
    value: float
    unit: str
    formula: str

    def to_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "label": self.label,
            "value": round(self.value, 2),
            "unit": self.unit,
            "formula": self.formula,
        }


def metrics_of(shape: Shape) -> tuple[Metric, ...]:
    """The seven measurements the Tactical Lab reports. Pure functions of the eleven points."""
    points = shape.points
    outfield = shape.outfield()
    centre = centroid(outfield)
    xs = [point.x for point in outfield]
    ys = [point.y for point in outfield]
    width = max(xs) - min(xs)
    depth = max(ys) - min(ys)
    bands = shape.by_band()
    nn = nearest_neighbour_distances(list(outfield))

    def band_y(band: str) -> float | None:
        values = [point.y for point in bands.get(band, [])]
        return mean(values) if values else None

    defensive_y, midfield_y, attacking_y = band_y("defensive"), band_y("midfield"), band_y("attacking")
    back_line_y = min((point.y for slot, point in zip(shape.slots, points, strict=True) if ROLES[slot.role].band == "defensive"), default=0.0)
    gaps: list[float] = []
    if defensive_y is not None and midfield_y is not None:
        gaps.append(abs(midfield_y - defensive_y))
    if midfield_y is not None and attacking_y is not None:
        gaps.append(abs(attacking_y - midfield_y))

    metrics: list[Metric] = [
        Metric("width", "Width", width, "m", "max(x) - min(x) across the ten outfield positions."),
        Metric("depth", "Vertical span", depth, "m", "max(y) - min(y) across the ten outfield positions."),
        Metric(
            "coverage",
            "Area covered",
            width * depth,
            "m²",
            "width × vertical span, against a full pitch of 7,140 m².",
        ),
        Metric("balance", "Balanced point", centre.y, "m", "mean(y) of the outfield players: where the team's mass sits, from its own goal."),
        Metric(
            "spacing",
            "Mean team-mate distance",
            mean(nn) if nn else 0.0,
            "m",
            "for each outfield player, the distance to its nearest team-mate; then the mean.",
        ),
        Metric(
            "isolation",
            "Most isolated player",
            max(nn) if nn else 0.0,
            "m",
            "the largest of those nearest-neighbour distances: the team-mate a press cannot reach in time.",
        ),
        Metric(
            "line_separation",
            "Separation between the lines",
            mean(gaps) if gaps else 0.0,
            "m",
            "mean distance between the average y of the defensive/midfield bands and the midfield/attacking bands.",
        ),
        Metric(
            "space_behind",
            "Space behind the back line",
            max(0.0, back_line_y),
            "m",
            "how far the deepest defender sits from its own goal line — the channel a run in behind must be played into.",
        ),
    ]
    return tuple(metrics)


@dataclass(frozen=True)
class Change:
    """A named "what happens if…" the board offers, and the arithmetic it performs.

    `roles` and `bands` together name every slot the change is allowed to move. The board prints that
    list and the test asserts against it, so a label like "raise the back line" cannot quietly be
    implemented as "move the whole defensive band" or vice versa.
    """

    key: str
    label: str
    note: str
    phase: str  # in_possession | out_of_possession
    target: tuple[str, ...]
    roles: tuple[str, ...] = ()
    bands: tuple[str, ...] = ()
    dx: float = 0.0
    dy: float = 0.0
    scale_x: float = 1.0

    def matches(self, slot: Slot) -> bool:
        return slot.role in self.roles or ROLES[slot.role].band in self.bands

    def desired(self, slot: Slot, point: Point) -> Point:
        """Where this change would put a slot before the touchline is consulted."""
        if not self.matches(slot):
            return point
        return Point(point.x * self.scale_x + self.dx, point.y + self.dy)

    def apply(self, slot: Slot, point: Point) -> Point:
        return self.desired(slot, point) if self.matches(slot) else clamp_point(self.desired(slot, point))

    def to_dict(self) -> dict[str, object]:
        return {"key": self.key, "label": self.label, "note": self.note, "phase": self.phase, "target": list(self.target)}


CHANGES: Final[dict[str, Change]] = {
    change.key: change
    for change in (
        Change(
            key="raise-back-line",
            label="Raise the back line 8 m",
            note="Compresses the team so the lines sit closer together — and hands the space behind it to the opponent.",
            phase="in_possession",
            target=("the defensive line",),
            bands=("defensive",),
            dy=8.0,
        ),
        Change(
            key="drop-forwards",
            label="Drop the forwards 6 m deeper",
            note="A shorter pass from midfield, less pressure on their centre-backs, more room for their full-backs.",
            phase="in_possession",
            target=("the front line",),
            bands=("attacking",),
            dy=-6.0,
        ),
        Change(
            key="widen-front",
            label="Stretch the front line 12% wider",
            note="More space between their wide players — and more ground for a counter to cross.",
            phase="in_possession",
            target=("the front line",),
            bands=("attacking",),
            scale_x=1.12,
        ),
        Change(
            key="narrow-midfield",
            label="Narrow the midfield 30%",
            note="Easier to pass through the middle third; leaves the flanks to the full-backs alone.",
            phase="in_possession",
            target=("the midfield line",),
            bands=("midfield",),
            scale_x=0.7,
        ),
        Change(
            key="step-everything-up",
            label="Step the whole outfield 5 m up",
            note="Every pass is played 5 m closer to their goal, and every recovery is 5 m longer.",
            phase="in_possession",
            target=("all ten outfield players",),
            bands=("defensive", "midfield", "attacking"),
            dy=5.0,
        ),
        Change(
            key="push-wide-pair",
            label="Push the wing-backs 10 m higher",
            note="Width at the top of the pitch in a back three, and an exposed channel down each flank.",
            phase="in_possession",
            target=("the two wing-backs",),
            roles=("RWB", "LWB"),
            dy=10.0,
        ),
    )
}


def apply_change(shape: Shape, change: Change) -> Shape:
    """Return the shape this change describes — clamped to the grass, always."""
    return Shape(shape.slots, tuple(change.apply(slot, point) for slot, point in zip(shape.slots, shape.points, strict=True)))


@dataclass(frozen=True)
class ShapeDiff:
    """What a counterfactual did: the two shapes, and every metric that moved."""

    change: Change
    before: tuple[Metric, ...]
    after: tuple[Metric, ...]

    @property
    def moved(self) -> list[tuple[Metric, Metric, float]]:
        rows: list[tuple[Metric, Metric, float]] = []
        after_by_key = {metric.key: metric for metric in self.after}
        for before in self.before:
            after = after_by_key[before.key]
            if abs(after.value - before.value) >= 0.05:
                rows.append((before, after, after.value - before.value))
        return rows

    def to_dict(self) -> dict[str, object]:
        return {
            "change": self.change.to_dict(),
            "before": [metric.to_dict() for metric in self.before],
            "after": [metric.to_dict() for metric in self.after],
            "moved": [
                {
                    "key": before.key,
                    "label": before.label,
                    "before": round(before.value, 2),
                    "after": round(after.value, 2),
                    "delta": round(delta, 2),
                    "unit": before.unit,
                    "formula": before.formula,
                }
                for before, after, delta in self.moved
            ],
        }


def analyse(shape: Shape, changes: Mapping[str, Change] = CHANGES) -> list[ShapeDiff]:
    """Every counterfactual the board offers, evaluated against one shape."""
    before = metrics_of(shape)
    return [ShapeDiff(change, before, metrics_of(apply_change(shape, change))) for change in changes.values()]
