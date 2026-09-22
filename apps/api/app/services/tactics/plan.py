"""The 50 tactical systems the M4 gate asks for, planned as data before anything touches a database.

Ten authored shapes × five temperaments (spec §65: "50 Tactical Systems"). Each system's payload
carries both phases' coordinates, the metrics measured from them, and strengths/risks that are
**generated from those measurements against the catalogue's own distribution** — so the sentence a
page prints was computed, not composed. The threshold is a quartile of the same 50 systems, and the
percentile is quoted inside the sentence, so a reader can check the claim against the table.

Nothing here reads a database, a provider or the clock.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Final

from app.models import TACTICS_DISCLAIMER
from app.services.tactics.analysis import CHANGES, Shape, in_possession, metrics_of, out_of_possession
from app.services.tactics.roles import ROLES
from app.services.tactics.shapes import FORMATION_SHAPES, TEMPERAMENTS
from app.services.world.names import slugify
from app.services.world.plan import Planned, content_hash, web_path

__all__ = [
    "RANKED_METRICS",
    "SYSTEM_COUNT",
    "PlannedSystem",
    "fingerprint",
    "planned_rows",
    "system_by_key",
    "system_by_slug",
    "tactical_problems",
    "tactical_systems",
]

SYSTEM_COUNT: Final = 50

# One disclaimer for this dataset, owned by the model layer that the API envelopes read. Duplicating
# the sentence here is how a page ends up labelling the same row two different ways.
PROVENANCE: Final = {
    "data_origin": "project-authored",
    "is_demo_data": False,
    "disclaimer": TACTICS_DISCLAIMER,
}
RANKED_METRICS: Final = ("space_behind", "spacing", "width", "line_separation", "isolation", "balance")

# (phase, metric, direction, sentence). `low` means a small value is the strength; `high` means a
# large value is the risk. Each fires only in the extreme quartile of the 50-system catalogue.
_STRENGTH_RULES: Final = (
    ("out", "space_behind", "low", "Defends with {value:.1f} m between the back line and its own goal ({percentile}): the least room in behind of any shape here."),
    ("out", "spacing", "low", "On average {value:.1f} m to the nearest team-mate when defending ({percentile}): nobody in the block is out of a pass."),
    ("in", "width", "high", "Spreads play to {value:.1f} m across ({percentile}), so their wide players must cover the whole flank."),
    ("in", "balance", "high", "The team's mass sits {value:.1f} m up the pitch ({percentile}), so most turnovers are won in their half."),
)
_RISK_RULES: Final = (
    ("in", "space_behind", "high", "The back line sits {value:.1f} m off its own goal in possession ({percentile}); one pass in behind is a run, not a scramble."),
    ("in", "line_separation", "high", "{value:.1f} m between the defensive and attacking lines in possession ({percentile}) is a channel a counter is played straight through."),
    ("in", "isolation", "high", "The most isolated team-mate is {value:.1f} m from the nearest support ({percentile}) — that is exactly where a press is set."),
    ("out", "width", "high", "Even defending, the block is {value:.1f} m wide ({percentile}); the far side stays a long way from the ball."),
)


def system_path(slug: str) -> str:
    """The §80 route for a tactical system, from the one route table the API publishes."""
    return web_path("tactics", slug)


def metric_value(shape: Shape, key: str) -> float:
    return {metric.key: metric.value for metric in metrics_of(shape)}[key]


@dataclass(frozen=True)
class PlannedSystem:
    """One planned row: the coordinates, the measurements taken from them, and what they imply.

    Named apart from the `TacticalSystem` table so a reader can tell "the plan wants this" from
    "the database holds this" — the same distinction `world.plan.Planned` draws.
    """

    key: str
    slug: str
    name: str
    formation: str
    temperament_key: str
    idea: str
    phase_in: Shape
    phase_out: Shape
    strengths: tuple[str, ...]
    risks: tuple[str, ...]
    demands: tuple[tuple[str, int], ...]

    def shape(self, phase: str) -> Shape:
        return self.phase_in if phase == "in" else self.phase_out

    def metrics(self, phase: str) -> tuple[Any, ...]:
        return metrics_of(self.shape(phase))

    def path(self) -> str:
        return system_path(self.slug)

    def payload(self) -> dict[str, Any]:
        temperament = TEMPERAMENTS[self.temperament_key]
        return {
            "natural_key": self.key,
            "slug": self.slug,
            "name": self.name,
            "formation": self.formation,
            "temperament_key": self.temperament_key,
            "temperament_label": temperament.label,
            "idea": self.idea,
            "path": self.path(),
            "phase_in": self.phase_in.as_dict(),
            "phase_out": self.phase_out.as_dict(),
            "metrics_in": [metric.to_dict() for metric in self.metrics("in")],
            "metrics_out": [metric.to_dict() for metric in self.metrics("out")],
            "strengths": list(self.strengths),
            "risks": list(self.risks),
            "demands": dict(self.demands),
            "roles": [ROLES[slot.role].to_dict() for slot in self.phase_in.slots],
            "instructions": list(temperament.instructions),
            "build_up": temperament.build_up,
            "tempo": temperament.tempo,
            "pressing_trigger": temperament.pressing_trigger,
            "width_note": temperament.width_note,
            "press_line_y": temperament.press_line_y,
            "block_depth": temperament.block_depth,
            "defensive_narrowing": temperament.defensive_narrowing,
            "counterfactuals": [change.to_dict() for change in CHANGES.values()],
            **PROVENANCE,
        }


def _ordinal(value: int) -> str:
    """1st, 2nd, 3rd, 11th … 22nd — a percentile that reads "82th" undermines the number next to it."""
    if 11 <= value % 100 <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
    return f"{value}{suffix}"


def _quartile_label(values: Sequence[float]) -> dict[float, str]:
    """Each distinct measurement in the catalogue, labelled with where it sits among the 50."""
    ordered = sorted(values)
    table: dict[float, str] = {}
    for value in set(ordered):
        below = sum(1 for candidate in ordered if candidate < value)
        share = below / len(ordered)
        band = "lowest quartile" if share < 0.25 else "highest quartile" if share >= 0.75 else "middle half"
        table[value] = f"{_ordinal(round(share * 100))} percentile, {band}"
    return table


def _verdict(
    system_name: str,
    phases: tuple[Shape, Shape],
    ranks: dict[tuple[str, str], dict[float, str]],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    def read(phase: str, metric: str) -> float:
        return metric_value(phases[0] if phase == "in" else phases[1], metric)

    strengths: list[str] = []
    risks: list[str] = []
    for rules, bucket in ((_STRENGTH_RULES, strengths), (_RISK_RULES, risks)):
        for phase, metric, direction, template in rules:
            value = read(phase, metric)
            label = ranks[(phase, metric)].get(value, "")
            extreme = "lowest quartile" if direction == "low" else "highest quartile"
            if label.endswith(extreme):
                bucket.append(template.format(value=value, percentile=label))
    if not strengths:
        strengths.append(f"{system_name} shows no extreme measurement of any kind in the catalogue: nothing to trade, nothing free.")
    if not risks:
        risks.append(f"No measured number in {system_name} sits in an extreme quartile, so its risks are the ones its temperament states.")
    return tuple(strengths), tuple(risks)


def _draft() -> tuple[tuple[str, str, str, str, str, Shape, Shape], ...]:
    rows: list[tuple[str, str, str, str, str, Shape, Shape]] = []
    for formation_name, shape in sorted(FORMATION_SHAPES.items()):
        for temperament_key, temperament in sorted(TEMPERAMENTS.items()):
            attacking = in_possession(shape, temperament)
            rows.append(
                (
                    f"{formation_name}:{temperament_key}",
                    slugify(f"{formation_name}-{temperament_key}"),
                    f"{formation_name} · {temperament.label}",
                    formation_name,
                    temperament_key,
                    attacking,
                    out_of_possession(attacking, temperament),
                )
            )
    return tuple(rows)


@lru_cache(maxsize=1)
def tactical_systems() -> tuple[PlannedSystem, ...]:
    """The full catalogue, each system graded against the whole set."""
    drafted = _draft()
    ranks: dict[tuple[str, str], dict[float, str]] = {}
    for phase in ("in", "out"):
        shapes = [row[5] if phase == "in" else row[6] for row in drafted]
        for metric in RANKED_METRICS:
            ranks[(phase, metric)] = _quartile_label([metric_value(shape, metric) for shape in shapes])

    systems: list[PlannedSystem] = []
    for key, slug, name, formation_name, temperament_key, attacking, defending in drafted:
        demands: dict[str, int] = {}
        for slot in attacking.slots:
            for attribute, level in ROLES[slot.role].demands.items():
                demands[attribute] = max(demands.get(attribute, 0), level)
        strengths, risks = _verdict(name, (attacking, defending), ranks)
        systems.append(
            PlannedSystem(
                key=key,
                slug=slug,
                name=name,
                formation=formation_name,
                temperament_key=temperament_key,
                idea=TEMPERAMENTS[temperament_key].idea,
                phase_in=attacking,
                phase_out=defending,
                strengths=strengths,
                risks=risks,
                demands=tuple(sorted(demands.items())),
            )
        )
    return tuple(systems)


def system_by_key(key: str) -> PlannedSystem | None:
    return next((system for system in tactical_systems() if system.key == key), None)


def system_by_slug(slug: str) -> PlannedSystem | None:
    return next((system for system in tactical_systems() if system.slug == slug), None)


def fingerprint() -> str:
    return content_hash({"systems": [system.payload() for system in tactical_systems()]})


def planned_rows() -> list[Planned]:
    """The rows the sync layer wants to exist — one per system, hash-addressed by content."""
    return [Planned(natural_key=system.key, payload=system.payload(), content_hash=content_hash(system.payload())) for system in tactical_systems()]


def tactical_problems(systems: Iterable[PlannedSystem] | None = None) -> list[str]:
    """Everything that would make this catalogue unfit to store. An empty list means fit."""
    rows = list(systems) if systems is not None else list(tactical_systems())
    problems: list[str] = []
    if len(rows) != SYSTEM_COUNT:
        problems.append(f"expected {SYSTEM_COUNT} tactical systems, planned {len(rows)}")
    keys = [system.key for system in rows]
    slugs = [system.slug for system in rows]
    if len(set(keys)) != len(keys):
        problems.append("duplicate system keys")
    if len(set(slugs)) != len(slugs):
        problems.append("duplicate system slugs")
    for system in rows:
        for phase in ("in", "out"):
            shape = system.shape(phase)
            bands = {ROLES[slot.role].band for slot in shape.slots}
            if len(shape.points) != 11:
                problems.append(f"{system.key} {phase}: {len(shape.points)} positions")
            for band in ("goalkeeper", "defensive", "midfield", "attacking"):
                if band not in bands:
                    problems.append(f"{system.key} {phase}: no {band} band")
            for metric in system.metrics(phase):
                if not metric.value == metric.value or metric.value < 0 or metric.value > 1e5:
                    problems.append(f"{system.key} {phase}: {metric.key} = {metric.value}")
        if not system.strengths or not system.risks:
            problems.append(f"{system.key} has no measured strengths or risks")
        if system.path() != f"/tactics/{system.slug}":
            problems.append(f"{system.key} path does not carry its slug")
    return problems
