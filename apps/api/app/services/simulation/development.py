"""Career-linked player development (M13 item 4 — foundation).

A season of fixtures currently changes no player's stored attributes — see
`simulation.career.limitations()["carry_over"]`, which says so in the words the page prints. Training
sessions already develop the user's own `UserPlayer` through the coach engine; what is missing is the
*fixture-minutes* half: a player who actually plays a career's matches should develop, and the
development should be recomputed from the career's own appearance rows on every read — never a stored,
drifting counter — so a squad you develop genuinely changes and the change is auditable.

This module is the pure, deterministic, bounded core the integration will call. Given the minutes a
player has accumulated across a career's fixtures (and the sessions around them), it computes how far
each attribute has developed toward that player's `potential`. The curve is **authored, not fitted**:
growth saturates as an attribute approaches its potential, and an attribute at or above potential does
not grow. Constants are named so the shape is visible rather than guessed at.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

from app.models import ALL_ATTRIBUTES

#: Minutes of career football at which an attribute has closed ~63% of the gap to its potential.
#: Authored: a ~half-season of regular football moves a young player most of the way; the last approach
#: to potential is deliberately slow, as it is in any development model worth its name.
DEVELOPMENT_TAU: float = 3000.0

#: The fraction of remaining headroom an attribute closes at full saturation. Authored, not fitted: even
#: a full season of football leaves a young player short of potential, so development can continue next
#: season rather than snapping to the ceiling.
DEVELOPMENT_RATE: float = 0.18

#: The attribute floor a player starts from when one is not yet recorded. Matches `UserPlayer.attributes`'s
#: default of 40 so a world player with no stored attribute reads the same baseline the academy uses.
ATTRIBUTE_FLOOR: int = 40

#: A world training session's `load_units` counts as this many match minutes toward development. Authored: a
#: full off-pitch programme (high hundreds of units) should weigh like a fraction of a season's football,
#: not equal it, so match play stays the dominant driver of a career's development curve.
TRAINING_MINUTES_PER_UNIT: float = 0.5


def _develop_one(value: float, potential: float, minutes_played: int, *, tau: float, rate: float) -> float:
    """One attribute's developed value: a saturating climb toward `potential`.

    `headroom = potential - value`; `saturation = 1 - e^(-minutes/tau)`; the gain is
    `headroom · saturation · rate`. An attribute already at or above its potential gains nothing and is
    returned unchanged, so a stored attribute that sits above potential stays there; an attribute below
    potential gains strictly less than the headroom, so the ceiling is never crossed from below. Pure and
    deterministic.
    """
    headroom = potential - value
    if headroom <= 0.0:
        return value
    saturation = 1.0 - math.exp(-max(0, minutes_played) / tau)
    return value + headroom * saturation * rate


def developed_attributes(
    minutes_played: int,
    *,
    potential: int,
    attributes: Mapping[str, int],
    tau: float = DEVELOPMENT_TAU,
    rate: float = DEVELOPMENT_RATE,
) -> dict[str, int]:
    """A developed attribute set from `minutes_played` of career football.

    Every attribute in `ALL_ATTRIBUTES` rises toward `potential` by the saturating curve; one with no
    recorded value reads `ATTRIBUTE_FLOOR`. An attribute that already meets or exceeds `potential` is
    left unchanged, and one below it never overshoots, so the ceiling is respected from below. The result
    is reproducible from `minutes_played` alone, which is what makes the integration able to recompute it
    from the career's appearance rows instead of trusting a stored figure.
    """
    potential_f = float(potential)
    return {attribute: int(round(_develop_one(float(attributes.get(attribute, ATTRIBUTE_FLOOR)), potential_f, minutes_played, tau=tau, rate=rate))) for attribute in ALL_ATTRIBUTES}


def developed_overall(
    value: float,
    *,
    potential: int,
    minutes_played: int,
    tau: float = DEVELOPMENT_TAU,
    rate: float = DEVELOPMENT_RATE,
) -> float:
    """The same curve applied to one scalar quantity, left unrounded.

    The academy outcomes block projects the stored `overall` toward the stored `potential` with the
    exact arithmetic the attribute curve uses — same saturation, same rate, same ceiling — so the two
    projections can never disagree about how developed a player is. The float is returned unrounded;
    the caller decides the precision it prints.
    """
    return _develop_one(float(value), float(potential), minutes_played, tau=tau, rate=rate)


def development_summary(
    minutes_played: int,
    *,
    potential: int,
    attributes: Mapping[str, int],
    tau: float = DEVELOPMENT_TAU,
    rate: float = DEVELOPMENT_RATE,
) -> dict[str, object]:
    """The developed set plus the per-attribute gain, for the audit trail the integration will store.

    Returns `before`, `after` and `delta` per attribute, and the `minutes_played` they were computed
    from, so a reader can see exactly how a player moved and check the arithmetic against the rows.
    """
    after = developed_attributes(minutes_played, potential=potential, attributes=attributes, tau=tau, rate=rate)
    before = {attribute: int(attributes.get(attribute, ATTRIBUTE_FLOOR)) for attribute in ALL_ATTRIBUTES}
    delta = {attribute: after[attribute] - before[attribute] for attribute in ALL_ATTRIBUTES}
    return {
        "minutes_played": max(0, int(minutes_played)),
        "potential": int(potential),
        "before": before,
        "after": after,
        "delta": delta,
        "tau": tau,
        "rate": rate,
    }


__all__ = [
    "ATTRIBUTE_FLOOR",
    "DEVELOPMENT_RATE",
    "DEVELOPMENT_TAU",
    "TRAINING_MINUTES_PER_UNIT",
    "developed_attributes",
    "developed_overall",
    "development_summary",
]
