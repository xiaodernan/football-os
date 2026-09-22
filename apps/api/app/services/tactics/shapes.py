"""The authored data behind the Tactical Lab: ten base shapes and five temperaments.

A *shape* is a set of boot positions in metres, written down once as a balanced structure. A
*temperament* is a documented transformation of that structure — how far the line steps up, how
narrow the block gets, which roles push higher when their team owns the ball. The 50 systems the
M4 gate asks for (`ROADMAP.md`, spec §65) are the cross product, so:

* nothing is typed twice — the in- and out-of-possession coordinates are **derived**, which is what
  lets the animation interpolate two views of one structure rather than two unrelated drawings;
* a change to one shape moves every system that uses it, and the plan's content hash notices;
* the numbers a page reports can be traced back to these metres plus one documented transform.

Coordinates follow `pitch.py`: origin at the centre of this team's own goal, `y` toward the
opponent, `x` negative on this team's left.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from app.services.tactics.pitch import PITCH_LENGTH, Point
from app.services.tactics.roles import ROLES

__all__ = ["Slot", "TEMPERAMENTS", "FORMATION_SHAPES", "formation", "temperament"]


@dataclass(frozen=True)
class Slot:
    """One position on the board: a role, at a place, in the balanced shape."""

    role: str
    x: float
    y: float

    def point(self) -> Point:
        return Point(self.x, self.y)


def _shape(*slots: tuple[str, float, float]) -> tuple[Slot, ...]:
    shape = tuple(Slot(role, x, y) for role, x, y in slots)
    if len(shape) != 11:
        raise ValueError(f"a formation needs exactly 11 slots, got {len(shape)}")
    goalkeepers = [slot for slot in shape if slot.role == "GK"]
    if len(goalkeepers) != 1:
        raise ValueError("a formation needs exactly one goalkeeper")
    if any(slot.role not in ROLES for slot in shape):
        raise ValueError(f"unknown role in shape: {[s.role for s in shape if s.role not in ROLES]}")
    if any(not (-34.0 <= slot.x <= 34.0) or not (0.0 <= slot.y <= PITCH_LENGTH) for slot in shape):
        raise ValueError("a slot sits off the grass")
    return shape


# --- Ten base shapes. The numbers are the balanced structure; temperaments move them from here.
FORMATION_SHAPES: Final[dict[str, tuple[Slot, ...]]] = {
    "4-3-3": _shape(
        ("GK", 0.0, 3.0),
        ("RB", 26.0, 24.0),
        ("DCB", 9.0, 20.0),
        ("DCB", -9.0, 20.0),
        ("LB", -26.0, 24.0),
        ("DM", 0.0, 38.0),
        ("CM", 12.0, 48.0),
        ("CM", -12.0, 48.0),
        ("RW", 24.0, 68.0),
        ("ST", 0.0, 74.0),
        ("LW", -24.0, 68.0),
    ),
    "4-4-2": _shape(
        ("GK", 0.0, 3.0),
        ("RB", 26.0, 26.0),
        ("DCB", 9.0, 22.0),
        ("DCB", -9.0, 22.0),
        ("LB", -26.0, 26.0),
        ("RM", 24.0, 48.0),
        ("CM", 9.0, 52.0),
        ("CM", -9.0, 52.0),
        ("LM", -24.0, 48.0),
        ("ST", 7.0, 72.0),
        ("ST", -7.0, 72.0),
    ),
    "4-2-3-1": _shape(
        ("GK", 0.0, 3.0),
        ("RB", 26.0, 24.0),
        ("DCB", 9.0, 20.0),
        ("DCB", -9.0, 20.0),
        ("LB", -26.0, 24.0),
        ("DM", 10.0, 38.0),
        ("DM", -10.0, 38.0),
        ("AM", 0.0, 58.0),
        ("RW", 20.0, 66.0),
        ("ST", 0.0, 74.0),
        ("LW", -20.0, 66.0),
    ),
    "3-5-2": _shape(
        ("GK", 0.0, 3.0),
        ("DCB", 11.0, 21.0),
        ("DCB", 0.0, 19.0),
        ("DCB", -11.0, 21.0),
        ("RWB", 29.0, 44.0),
        ("CM", 11.0, 48.0),
        ("DM", 0.0, 40.0),
        ("CM", -11.0, 48.0),
        ("LWB", -29.0, 44.0),
        ("ST", 7.0, 72.0),
        ("ST", -7.0, 72.0),
    ),
    "3-4-3": _shape(
        ("GK", 0.0, 3.0),
        ("DCB", 12.0, 21.0),
        ("DCB", 0.0, 19.0),
        ("DCB", -12.0, 21.0),
        ("RWB", 27.0, 42.0),
        ("CM", 9.0, 48.0),
        ("CM", -9.0, 48.0),
        ("LWB", -27.0, 42.0),
        ("RW", 20.0, 68.0),
        ("ST", 0.0, 74.0),
        ("LW", -20.0, 68.0),
    ),
    "4-4-1-1": _shape(
        ("GK", 0.0, 3.0),
        ("RB", 26.0, 25.0),
        ("DCB", 9.0, 21.0),
        ("DCB", -9.0, 21.0),
        ("LB", -26.0, 25.0),
        ("RM", 23.0, 47.0),
        ("DM", 9.0, 40.0),
        ("CM", -9.0, 44.0),
        ("LM", -23.0, 47.0),
        ("SS", 0.0, 62.0),
        ("ST", 0.0, 75.0),
    ),
    "4-1-4-1": _shape(
        ("GK", 0.0, 3.0),
        ("RB", 26.0, 25.0),
        ("DCB", 9.0, 21.0),
        ("DCB", -9.0, 21.0),
        ("LB", -26.0, 25.0),
        ("DM", 0.0, 36.0),
        ("RM", 24.0, 52.0),
        ("CM", 8.0, 52.0),
        ("CM", -8.0, 52.0),
        ("LM", -24.0, 52.0),
        ("ST", 0.0, 73.0),
    ),
    "5-3-2": _shape(
        ("GK", 0.0, 3.0),
        ("RWB", 30.0, 32.0),
        ("DCB", 16.0, 21.0),
        ("DCB", 0.0, 19.0),
        ("DCB", -16.0, 21.0),
        ("LWB", -30.0, 32.0),
        ("CM", 11.0, 46.0),
        ("DM", 0.0, 40.0),
        ("CM", -11.0, 46.0),
        ("ST", 7.0, 70.0),
        ("ST", -7.0, 70.0),
    ),
    "4-3-1-2": _shape(
        ("GK", 0.0, 3.0),
        ("RB", 25.0, 25.0),
        ("DCB", 9.0, 21.0),
        ("DCB", -9.0, 21.0),
        ("LB", -25.0, 25.0),
        ("DM", 0.0, 38.0),
        ("CM", 12.0, 47.0),
        ("CM", -12.0, 47.0),
        ("AM", 0.0, 62.0),
        ("ST", 8.0, 73.0),
        ("ST", -8.0, 73.0),
    ),
    "3-4-2-1": _shape(
        ("GK", 0.0, 3.0),
        ("DCB", 12.0, 21.0),
        ("DCB", 0.0, 19.0),
        ("DCB", -12.0, 21.0),
        ("RWB", 28.0, 42.0),
        ("CM", 9.0, 47.0),
        ("CM", -9.0, 47.0),
        ("LWB", -28.0, 42.0),
        ("AM", 10.0, 62.0),
        ("AM", -10.0, 62.0),
        ("ST", 0.0, 74.0),
    ),
}


@dataclass(frozen=True)
class Temperament:
    """What a team does *with* a shape: how it defends, how it attacks, and by how much."""

    key: str
    label: str
    idea: str
    press_line_y: float
    block_depth: float
    defensive_narrowing: float
    in_possession_deltas: Mapping[str, tuple[float, float]]
    build_up: str
    tempo: str
    pressing_trigger: str
    width_note: str
    instructions: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "label": self.label,
            "idea": self.idea,
            "press_line_y": self.press_line_y,
            "block_depth": self.block_depth,
            "defensive_narrowing": self.defensive_narrowing,
            "build_up": self.build_up,
            "tempo": self.tempo,
            "pressing_trigger": self.pressing_trigger,
            "width_note": self.width_note,
            "instructions": list(self.instructions),
        }


TEMPERAMENTS: Final[dict[str, Temperament]] = {
    temperament.key: temperament
    for temperament in (
        Temperament(
            key="press-high",
            label="High press",
            idea="Win it back in their half, within five seconds of losing it.",
            press_line_y=72.0,
            block_depth=28.0,
            defensive_narrowing=0.94,
            in_possession_deltas={
                "RB": (1.0, 11.0),
                "LB": (-1.0, 11.0),
                "RWB": (1.0, 12.0),
                "LWB": (-1.0, 12.0),
                "CM": (0.0, 7.0),
                "DM": (0.0, 4.0),
                "RW": (2.0, 6.0),
                "LW": (-2.0, 6.0),
                "ST": (0.0, 5.0),
                "SS": (0.0, 5.0),
            },
            build_up="Short from the keeper, deliberately baiting the first presser.",
            tempo="Fast in the final third, patient until the trigger fires.",
            pressing_trigger="A backwards touch, a first touch away from the touchline, or a receiver facing their own goal.",
            width_note="Wide in build-up to stretch them, then pinched at the trigger.",
            instructions=(
                "The striker curves to shut the deepest centre-back",
                "Midfield jumps the moment the trigger lands",
                "Full-backs press the winger with the keeper behind",
            ),
        ),
        Temperament(
            key="control-possession",
            label="Possession control",
            idea="Keep the ball so the game happens where we choose, and far from our goal.",
            press_line_y=60.0,
            block_depth=32.0,
            defensive_narrowing=0.9,
            in_possession_deltas={
                "RB": (-14.0, 13.0),
                "LB": (14.0, 13.0),
                "DCB": (0.0, 6.0),
                "DM": (0.0, -3.0),
                "CM": (3.0, 8.0),
                "AM": (0.0, 6.0),
                "RW": (4.0, 5.0),
                "LW": (-4.0, 5.0),
                "ST": (0.0, 3.0),
            },
            build_up="A back three plus a pivot: five passing lanes through the first line.",
            tempo="Slow, with the ball and with the block: the point is the opponent's shape, not the clock.",
            pressing_trigger="Loss of possession inside their half triggers a six-second counter-press.",
            width_note="Wingers hold the touchline; full-backs invert into the midfield line.",
            instructions=(
                "Invert the full-backs to make a diamond in build-up",
                "Keep the ball on the far side until they commit",
                "Rest-defence: two players always stay central and high",
            ),
        ),
        Temperament(
            key="direct-transition",
            label="Direct transition",
            idea="Three passes to the final third: get vertical before they can set.",
            press_line_y=52.0,
            block_depth=30.0,
            defensive_narrowing=0.92,
            in_possession_deltas={
                "ST": (0.0, 9.0),
                "SS": (0.0, 9.0),
                "RW": (3.0, 8.0),
                "LW": (-3.0, 8.0),
                "CM": (0.0, 3.0),
                "RM": (2.0, 5.0),
                "LM": (-2.0, 5.0),
                "DM": (0.0, -2.0),
            },
            build_up="First option is always the pass in behind, not the safe one sideways.",
            tempo="Highest on the board: two or three touches per player maximum.",
            pressing_trigger="A poor touch in midfield, or a pass back to the full-back.",
            width_note="Front four stay as high and as split as the offside line allows.",
            instructions=(
                "Look over, then in behind, before you look sideways",
                "Everyone sprints the nearest space on a turnover",
                "Second balls are the attack, not an afterthought",
            ),
        ),
        Temperament(
            key="low-block",
            label="Compact low block",
            idea="Defend 30 metres of your own pitch first, then leave with the ball.",
            press_line_y=32.0,
            block_depth=22.0,
            defensive_narrowing=0.78,
            in_possession_deltas={
                "ST": (0.0, 7.0),
                "SS": (0.0, 7.0),
                "RW": (4.0, 4.0),
                "LW": (-4.0, 4.0),
                "DM": (0.0, -6.0),
                "CM": (0.0, -5.0),
                "RB": (0.0, -6.0),
                "LB": (0.0, -6.0),
                "RWB": (0.0, -8.0),
                "LWB": (0.0, -8.0),
            },
            build_up="Straight to the target, then the second ball is the attack.",
            tempo="Deliberately slow out of defence, explosive once the ball is won.",
            pressing_trigger="Almost never by choice: the block drops until a touch or a switch gives a trap.",
            width_note="Two banks of four, squeezed to about 24 metres across.",
            instructions=(
                "Hold the shape, do not chase the ball out of it",
                "The striker's job is to hold play, not to press",
                "Break the first pass on the turnover, do not dribble",
            ),
        ),
        Temperament(
            key="wide-overload",
            label="Wide overload",
            idea="Make the flank outnumber them, then cut back at the far post.",
            press_line_y=58.0,
            block_depth=30.0,
            defensive_narrowing=0.9,
            in_possession_deltas={
                "RW": (6.0, 9.0),
                "LW": (-6.0, 9.0),
                "RB": (3.0, 12.0),
                "LB": (-3.0, 12.0),
                "RWB": (2.0, 10.0),
                "LWB": (-2.0, 10.0),
                "AM": (4.0, 4.0),
                "CM": (4.0, 2.0),
                "ST": (0.0, 2.0),
            },
            build_up="Shift play to one touchline and commit three players to it.",
            tempo="Swings side to side until the overload lands, then accelerates.",
            pressing_trigger="The ball goes wide to their full-back, who cannot pass inside.",
            width_note="Maximum width on the ball side; the far winger becomes an extra striker.",
            instructions=(
                "Three to one on the flank, and no early cross",
                "Far-side winger attacks the back post",
                "Rest-defence on the far touchline to kill the break",
            ),
        ),
    )
}


def formation(name: str) -> tuple[Slot, ...]:
    shape = FORMATION_SHAPES.get(name)
    if shape is None:
        raise KeyError(f"unknown formation {name!r}")
    return shape


def temperament(key: str) -> Temperament:
    found = TEMPERAMENTS.get(key)
    if found is None:
        raise KeyError(f"unknown temperament {key!r}")
    return found
