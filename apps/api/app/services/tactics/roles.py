"""Role catalogue: what each slot on the board is *asked* to do, separately in and out of possession.

Spec §11/§12 ask for roles that carry a job, not a shirt number. Each role below is project-authored
coaching vocabulary: a band (used for line separation), the two duties the Tactical Lab animates
between, the instructions a coach would actually give, and the six tactical attributes
(`app.models.ATTRIBUTE_GROUPS["tactical"]`) the role leans on hardest — which is what lets the AI
feedback say *why* a player profile fits or does not fit a system, instead of asserting it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final

# The six tactical attribute groups the player model already stores. Reused rather than re-invented
# so a role's demand can be compared against a real player row.
TACTICAL_ATTRIBUTES: Final = ("pressing", "build_up", "off_ball_movement", "defensive_awareness", "space_occupation", "transition")

BANDS: Final = ("goalkeeper", "defensive", "midfield", "attacking")


@dataclass(frozen=True)
class Role:
    key: str
    label: str
    band: str
    in_possession: str
    out_of_possession: str
    instructions: tuple[str, ...]
    demands: Mapping[str, int] = field(default_factory=dict)
    risk: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "label": self.label,
            "band": self.band,
            "in_possession": self.in_possession,
            "out_of_possession": self.out_of_possession,
            "instructions": list(self.instructions),
            "demands": dict(self.demands),
            "risk": self.risk,
        }


def _role(
    key: str,
    label: str,
    band: str,
    in_possession: str,
    out_of_possession: str,
    instructions: tuple[str, ...],
    demands: Mapping[str, int],
    risk: str,
) -> Role:
    """One row of the catalogue, validated at import time rather than at request time."""
    unknown = set(demands) - set(TACTICAL_ATTRIBUTES)
    if unknown:  # pragma: no cover - a programming error, caught by the import-time tests
        raise ValueError(f"role {key} demands unknown attributes: {sorted(unknown)}")
    if band not in BANDS:  # pragma: no cover
        raise ValueError(f"role {key} has unknown band {band!r}")
    return Role(key, label, band, in_possession, out_of_possession, instructions, dict(demands), risk)


ROLES: Final[dict[str, Role]] = {
    role.key: role
    for role in (
        _role(
            "GK",
            "Sweeper keeper",
            "goalkeeper",
            "Starts the first pass: short to the near centre-back, or diagonal to the far winger when they press high.",
            "Commands the space behind the line, so the defensive line can sit 10-15 m higher than a shot-stopper would allow.",
            ("Sweep behind a high line", "Take the short option against a press", "Distribute to the back foot, not the touchline"),
            {"build_up": 82, "defensive_awareness": 70, "space_occupation": 60},
            "A poor first pass turns a high line into an opposition chance inside five metres.",
        ),
        _role(
            "DCB",
            "Ball-playing centre-back",
            "defensive",
            "Splits wide to receive facing forward; line-breaks with the first pass when the press is committed.",
            "Defends the space between the centre-backs, steps to the ball only with cover behind.",
            ("Split wide on the first touch", "Show onto the striker", "Delay, do not dive"),
            {"build_up": 78, "defensive_awareness": 82, "pressing": 55},
            "Carrying rather than passing invites a counter through the middle channel.",
        ),
        _role(
            "RB",
            "High full-back",
            "defensive",
            "Holds the width at the touchline to make the pitch as wide as it can be; overlaps the winger.",
            "The widest defender in the block: recovers to the channel it left behind.",
            ("Hold the touchline", "Time the overlap, do not race into it", "Sprint back on the turnover"),
            {"space_occupation": 80, "transition": 76, "defensive_awareness": 62},
            "Every attack it joins is a 60 m recovery run it owes on the turnover.",
        ),
        _role(
            "LB",
            "High full-back (left)",
            "defensive",
            "Mirrors the right side: width, overlap, and the pass back inside when the lane is closed.",
            "Mirrors the right side: recovers to the left channel.",
            ("Hold the touchline", "Overlap behind the winger", "Communicate the switch"),
            {"space_occupation": 80, "transition": 76, "defensive_awareness": 62},
            "The left channel is exposed on any turnover in the opposition half.",
        ),
        _role(
            "RWB",
            "Wing-back (right)",
            "defensive",
            "The only width on its flank in a back three: receives high, crosses early.",
            "Drops into a back five; the outside channel becomes its responsibility alone.",
            ("Provide the only width on the flank", "Cross from the byline, not the corner", "Recover to the five"),
            {"space_occupation": 84, "transition": 80, "build_up": 62},
            "One player, 68 metres of flank: a sustained attack on that side is a numbers deficit.",
        ),
        _role(
            "LWB",
            "Wing-back (left)",
            "defensive",
            "The mirror: high and wide on the left in a back three.",
            "Drops into the left of a back five.",
            ("Provide the only width on the flank", "Track back on the switch", "Do not give the corner away cheaply"),
            {"space_occupation": 84, "transition": 80, "build_up": 62},
            "The switch of play is the fastest route to its space.",
        ),
        _role(
            "DM",
            "Holding midfielder",
            "midfield",
            "The rest-defence anchor: sits between the lines, offers the way out under pressure.",
            "Protects the space in front of the back line; the first defender to screen a run through the middle.",
            ("Screen, do not follow", "Be the safest option", "Position on the half-turn"),
            {"defensive_awareness": 88, "space_occupation": 74, "pressing": 66},
            "Stepping to press leaves the shot-blocking channel open unless a centre-back covers.",
        ),
        _role(
            "CM",
            "Box-to-box midfielder",
            "midfield",
            "Carries the ball through the middle third and arrives in the box as a second option.",
            "Presses the ball-side number eight and defends the middle third as a unit.",
            ("Play on the front foot", "Scan before the ball arrives", "Follow the run to the far post"),
            {"transition": 84, "off_ball_movement": 78, "pressing": 74, "build_up": 70},
            "Volume running is worthless if the arrival timing is always two seconds late.",
        ),
        _role(
            "AM",
            "Attacking midfielder",
            "midfield",
            "Receives between the opposition lines, turns, and plays the through ball or the shot.",
            "The first presser on the deepest opposition midfielder: curved runs to steer play outside.",
            ("Land in the blind side", "Show them wide", "Press the turn, not the receiver"),
            {"pressing": 72, "off_ball_movement": 86, "space_occupation": 78},
            "The least defensive role on the pitch: a side that does not press from the front loses it twice.",
        ),
        _role(
            "RM",
            "Wide midfielder (right)",
            "midfield",
            "Width in build-up, then the run beyond the full-back when the move crosses halfway.",
            "The right hand of the block: stays on the pass, not the dribble, until the press is triggered.",
            ("Stay wide until the trigger", "Track the overlapping full-back", "Defend the byline"),
            {"space_occupation": 76, "transition": 74, "defensive_awareness": 66},
            "A narrow wide player removes the only stretch a mid block has.",
        ),
        _role(
            "LM",
            "Wide midfielder (left)",
            "midfield",
            "Mirrors the right: width, then the run beyond.",
            "The left hand of the block.",
            ("Stay wide until the trigger", "Track the overlap", "Cover the near post"),
            {"space_occupation": 76, "transition": 74, "defensive_awareness": 66},
            "Narrowness on this flank lets a full-back be picked out at will.",
        ),
        _role(
            "RW",
            "Inverted winger (right)",
            "attacking",
            "Drinks inside onto the stronger foot to shoot or clip the far post; the half-space is its office.",
            "Presses the opposition centre-back from the inside, cutting the diagonal field.",
            ("Attack the half-space", "Bend it to the far post", "Press the inside shoulder"),
            {"off_ball_movement": 84, "space_occupation": 76, "pressing": 64},
            "Going inside is only a virtue when the full-back overlaps outside it.",
        ),
        _role(
            "LW",
            "Inverted winger (left)",
            "attacking",
            "Mirrors the right: inside to shoot, half-space to receive.",
            "Presses the far centre-back from the inside.",
            ("Attack the half-space", "Cut the diagonal", "Finish the move at the far post"),
            {"off_ball_movement": 84, "space_occupation": 76, "pressing": 64},
            "If the full-back does not overlap, the lane it vacates belongs to the opposition.",
        ),
        _role(
            "ST",
            "Pressing centre-forward",
            "attacking",
            "Holds the ball up until the midfield arrives; the target on a direct pass.",
            "Sets the pressing line and the trigger: which centre-back it shows the ball to.",
            ("Curve the run to the outside shoulder", "Hold until the eight arrives", "Sprint the second centre-back"),
            {"pressing": 78, "off_ball_movement": 82, "transition": 72},
            "A striker that does not press lets the opposition build from the back unopposed.",
        ),
        _role(
            "SS",
            "Second striker",
            "attacking",
            "Runs the channel behind the last line the moment the target holds the ball.",
            "Blocks the deepest pass and harries the recovering centre-backs.",
            ("Run the blind side", "Never be offside by choice", "Follow the shot in"),
            {"off_ball_movement": 90, "space_occupation": 80, "defensive_awareness": 52},
            "Almost nothing defensively: the team defends with ten, permanently.",
        ),
    )
}


def role_for(key: str) -> Role:
    """The catalogue is closed: a shape that names an unknown slot is a bug, not a 500."""
    found = ROLES.get(key)
    if found is None:  # pragma: no cover - guarded by the plan validator
        raise KeyError(f"unknown tactical role {key!r}")
    return found
