"""User tactics boards: validation of hand-placed coordinates, and the numbers derived from them (spec §13, §21, §61).

A board is the user's own arrangement, so the discipline here is the opposite of the authored
catalogue's: nothing is trusted. Every coordinate is checked against the model (eleven slots, exactly
one keeper, roles that exist, finite metres on the grass) before it is stored, because the shared view
will recompute its metrics from those numbers and print them as measurements. An invalid board is a
422 with the list of problems — never a stored row that renders confidently wrong figures.

The block may also be *derived* rather than drawn: `derive_block` runs the same published transform
the 50 authored systems use, so "press the same eleven back into a 28 m block" produces a defending
shape the reader can check against the stated formula instead of a second freehand drawing.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any, Final

from app.services.tactics.analysis import Shape, defend_block, metrics_of, shape_from_rows
from app.services.tactics.pitch import HALF_WIDTH, PITCH_LENGTH, Point, out_of_bounds
from app.services.tactics.roles import ROLES

__all__ = [
    "BOARD_LIMIT_PER_USER",
    "DEFAULT_BLOCK",
    "VISIBILITIES",
    "block_settings",
    "derive_block",
    "metrics_for",
    "problems_with",
    "roles_on",
]

BOARD_LIMIT_PER_USER: Final = 24
DEFAULT_BLOCK: Final = {"press_line_y": 52.0, "block_depth": 28.0, "defensive_narrowing": 0.9}
VISIBILITIES: Final = ("private", "shared")


def roles_on(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    return [str(row.get("role", "")) for row in rows]


def problems_with(rows: Sequence[Mapping[str, Any]], *, label: str) -> list[str]:
    """Why this set of eleven positions could not be stored. Empty means it can."""
    problems: list[str] = []
    if len(rows) != 11:
        problems.append(f"{label}: {len(rows)} positions, expected 11")
        return problems
    if sum(1 for row in rows if row.get("role") == "GK") != 1:
        problems.append(f"{label}: exactly one goalkeeper is required")
    for row in rows:
        role = str(row.get("role", ""))
        if role not in ROLES:
            problems.append(f"{label}: unknown role {role!r}")
            continue
        try:
            x = float(str(row.get("x")))
            y = float(str(row.get("y")))
        except (TypeError, ValueError):
            problems.append(f"{label} {role}: x/y must be numbers")
            continue
        if not (math.isfinite(x) and math.isfinite(y)):
            problems.append(f"{label} {role}: coordinates must be finite metres, got {x}, {y}")
            continue
        if out_of_bounds(Point(x, y)):
            problems.append(f"{label} {role}: ({x}, {y}) m is off a {HALF_WIDTH} × {PITCH_LENGTH} m pitch")
    return problems


def derive_block(rows: Sequence[Mapping[str, Any]], block: Mapping[str, float] | None = None) -> list[dict[str, Any]]:
    """The defending shape implied by a possession shape, via the published transform."""
    settings = {**DEFAULT_BLOCK, **(block or {})}
    shape = shape_from_rows(rows)
    defended = defend_block(
        shape,
        press_line_y=float(settings["press_line_y"]),
        block_depth=float(settings["block_depth"]),
        narrowing=float(settings["defensive_narrowing"]),
    )
    return defended.as_dict()


def metrics_for(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Recomputed from the stored coordinates, so a board's numbers always match its dots."""
    shape: Shape = shape_from_rows(rows)
    return [metric.to_dict() for metric in metrics_of(shape)]


def block_settings(block: Mapping[str, float] | None) -> dict[str, float]:
    """Clamped, merged with the defaults, and returned in the form the UI restates as a formula."""
    settings = {**DEFAULT_BLOCK, **(block or {})}
    depth = min(max(float(settings["block_depth"]), 8.0), 45.0)
    line = min(max(float(settings["press_line_y"]), depth), PITCH_LENGTH)
    narrowing = min(max(float(settings["defensive_narrowing"]), 0.6), 1.0)
    return {"press_line_y": line, "block_depth": depth, "defensive_narrowing": narrowing}
