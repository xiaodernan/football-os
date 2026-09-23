"""Turn stored rows into the numbers the engine plays with (M6, spec §19).

Two rules shape this module:

1. **Nothing is invented here.** Every input is either a row already in the database — a squad
   attribute, a player's form, a club's overall rating — or a metre the Tactical Lab measured off
   eleven coordinates. A side's quality is the mean of attributes its own players carry, and the
   formula that produced it travels with it in `factors`.
2. **A shape selects its own eleven.** The starting side is picked by the formation of the tactical
   system the club is playing, so a 4-2-3-1 and a 4-4-2 genuinely put different players forward,
   and the resulting attack/midfield/defence indices differ because of it.
3. **A squad can be told to be other than what the `real_players` rows say.** A career that signed a
   striker plays with that striker, and `SquadOverlay` is how the fact reaches this module: it adds and
   removes players on top of the club's stored rows, and the two counts are published as factors so a
   reader sees that the eleven was adjusted rather than read. Nothing else about how a side is built
   changes — the overlay only decides which rows are in the pool.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from statistics import mean

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RealPlayer, Team
from app.services.tactics.analysis import Metric, Shape, metrics_of
from app.services.tactics.plan import PlannedSystem, system_by_slug

# The bands a formation can staff. `CAM` and the wide midfielders count as midfield: in a 4-4-2 the
# wingers are midfielders, and where a system wants them high the shape's own metres say so.
BANDS: dict[str, tuple[str, ...]] = {
    "keeper": ("GK",),
    "defence": ("CB", "LB", "RB"),
    "midfield": ("CDM", "CM", "CAM", "LM", "RM"),
    "attack": ("LW", "RW", "ST", "CF"),
}

# Which of the world's 25 attributes each band is judged on. There is no goalkeeping attribute in this
# world's player model, so the keeper index is built from the mental and physical attributes that do
# exist and says so in its formula rather than pretending to a shot-stopping number.
BAND_ATTRIBUTES: dict[str, tuple[str, ...]] = {
    "keeper": ("positioning", "anticipation", "decision_making", "composure", "agility"),
    "defence": ("tackling", "defensive_awareness", "positioning", "heading", "strength", "anticipation"),
    "midfield": ("passing", "long_passing", "vision", "build_up", "transition", "composure", "stamina"),
    "attack": ("finishing", "off_ball_movement", "dribbling", "decision_making", "speed", "acceleration"),
}

# Pressing is a squad-wide habit rather than one band's job, so it reads every outfield attribute
# named `pressing`/`transition` across the eleven that were selected.
PRESS_ATTRIBUTES: tuple[str, ...] = ("pressing", "transition", "defensive_awareness", "stamina")

TACTICAL_METRICS = ("width", "depth", "coverage", "balance", "spacing", "isolation", "line_separation", "space_behind")


@dataclass(frozen=True)
class SquadOverlay:
    """Players one career put into, or took out of, a club's stored squad before a given round.

    Carried as rows rather than as numbers: `added` holds the player records themselves, so the
    attributes the engine reads are the ones that were on file when the deal was struck, and `removed`
    holds ids so a sold player cannot be selected by any formation.
    """

    added: tuple[RealPlayer, ...] = ()
    removed: frozenset[str] = field(default_factory=frozenset)
    label: str = ""

    @property
    def empty(self) -> bool:
        return not self.added and not self.removed


@dataclass(frozen=True)
class SideProfile:
    """One side as the engine sees it: identity, four band indices, a press index, and the metres."""

    team_id: str
    name: str
    short_name: str
    formation: str
    system_slug: str
    system_name: str
    attack: float
    midfield: float
    defence: float
    keeper: float
    press: float
    form: float
    overall: float
    squad_label: str = ""
    tactics: Mapping[str, float] = field(default_factory=dict)
    lineup: tuple[tuple[str, str, str], ...] = ()
    factors: tuple[Metric, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "team_id": self.team_id,
            "name": self.name,
            "short_name": self.short_name,
            "formation": self.formation,
            "system_slug": self.system_slug,
            "system_name": self.system_name,
            "indices": {
                "attack": round(self.attack, 3),
                "midfield": round(self.midfield, 3),
                "defence": round(self.defence, 3),
                "keeper": round(self.keeper, 3),
                "press": round(self.press, 3),
                "form": round(self.form, 3),
                "overall": round(self.overall, 3),
            },
            "squad_label": self.squad_label,
            "tactics": {key: round(value, 2) for key, value in self.tactics.items()},
            "lineup": [{"player": player, "position": position, "band": band} for player, position, band in self.lineup],
            "factors": [metric.to_dict() for metric in self.factors],
        }


def split_formation(formation: str) -> tuple[int, int, int]:
    """`4-2-3-1` → defenders 4, midfielders 5, attackers 1: first digit back, last one forward.

    A four-part shape folds its middle numbers into midfield, which is what a 4-2-3-1 is: a double
    pivot and a three behind the striker, seven midfielders in the band sense used here.
    """
    parts = [int(part) for part in formation.split("-") if part.strip().isdigit()]
    if len(parts) < 2:
        return (4, 4, 2)
    if len(parts) == 2:  # e.g. "2-8" from odd data: still a back line and a forward line.
        return (parts[0], 0, parts[1])
    return (parts[0], sum(parts[1:-1]), parts[-1])


def _rank(players: Iterable[RealPlayer]) -> list[RealPlayer]:
    return sorted(players, key=lambda player: (-player.overall, player.slug))


def select_starting_xi(players: Sequence[RealPlayer], defenders: int, midfielders: int, attackers: int) -> dict[str, list[RealPlayer]]:
    """Best available per band, by overall then slug, filling shortfalls from the nearest band.

    A squad without enough named defenders borrows a midfielder rather than leaving a hole: the
    shortfall is reported as a factor, so a side that had to improvise does not look identical to one
    that did not.
    """
    by_band: dict[str, list[RealPlayer]] = {band: [] for band in BANDS}
    keeper_pool = _rank([player for player in players if player.position in BANDS["keeper"]])
    by_band["keeper"] = keeper_pool[:1]
    wanted = {"defence": defenders, "midfield": midfielders, "attack": attackers}
    pools = {band: _rank([player for player in players if player.position in BANDS[band]]) for band in ("defence", "midfield", "attack")}
    taken = {player.id for player in by_band["keeper"]}
    for band, count in wanted.items():
        pool = [player for player in pools[band] if player.id not in taken]
        chosen = pool[:count]
        taken.update(player.id for player in chosen)
        by_band[band] = chosen
        if len(chosen) < count:
            # Nearest band order: a defence short-fall looks to midfield, an attack short-fall to midfield too.
            for donor in ("midfield", "attack", "defence"):
                if donor == band:
                    continue
                spare = [player for player in pools[donor] if player.id not in taken]
                need = count - len(by_band[band])
                extra = spare[:need]
                by_band[band].extend(extra)
                taken.update(player.id for player in extra)
                if len(by_band[band]) >= count:
                    break
    return by_band


def _band_index(players: Sequence[RealPlayer], keys: Sequence[str]) -> float:
    """Mean of the chosen attributes over the band, on the world's own 28–96 scale, shifted to 0–1.

    `(mean − 28) / 68` puts a squad that carries only the floor of each attribute at 0 and one at the
    model's ceiling at 1; nothing is calibrated against real football, and the engine says so.
    """
    values = [player.attributes.get(key, 0) for player in players for key in keys if player.attributes.get(key) is not None]
    if not values:
        return 0.0
    return max(0.0, min(1.0, (mean(values) - 28.0) / 68.0))


def band_index(players: Sequence[RealPlayer], band: str) -> float:
    """The number `team_profile` would print beside that band, for any set of players.

    Public because §22's tactical fit has to be the *same measurement* the engine plays with, not a
    second scale a reader would have to trust twice.
    """
    return _band_index(players, BAND_ATTRIBUTES[band])


def band_of_position(position: str) -> str:
    """Which band a stored position sits in, or `""` when this model does not staff it."""
    for band, positions in BANDS.items():
        if position in positions:
            return band
    return ""


def _metrics_of_system(system: PlannedSystem) -> dict[str, float]:
    shape: Shape = system.shape("in")
    return {metric.key: metric.value for metric in metrics_of(shape) if metric.key in TACTICAL_METRICS}


def team_profile(
    session: Session, team_id: str, *, system_slug: str | None = None, squad: SquadOverlay | None = None
) -> SideProfile:
    """Read one club's rows and build the side the engine will play.

    `squad` is the career's own transfer history applied to those rows; with none the club is its
    stored squad, which is what every non-career fixture has always meant.
    """
    team = session.get(Team, team_id)
    if team is None:
        raise LookupError(f"no team {team_id} in the generated world")
    rows = list(session.scalars(select(RealPlayer).where(RealPlayer.team_id == team_id)))
    if squad is not None:
        rows = [player for player in rows if player.id not in squad.removed]
        present = {player.id for player in rows}
        rows = [*rows, *[player for player in squad.added if player.id not in present]]
    if not rows:
        raise LookupError(f"team {team_id} has no players to select")

    system = system_by_slug(system_slug) if system_slug else None
    if system_slug and system is None:
        raise LookupError(f"no tactical system {system_slug}")
    formation = system.formation if system else team.formation
    defenders, midfielders, attackers = split_formation(formation)
    bands = select_starting_xi(rows, defenders, midfielders, attackers)
    eleven = [*bands["keeper"], *bands["defence"], *bands["midfield"], *bands["attack"]]

    attack = _band_index(bands["attack"], BAND_ATTRIBUTES["attack"])
    midfield = _band_index(bands["midfield"], BAND_ATTRIBUTES["midfield"])
    defence = _band_index(bands["defence"], BAND_ATTRIBUTES["defence"])
    keeper = _band_index(bands["keeper"], BAND_ATTRIBUTES["keeper"])
    press = _band_index(eleven, PRESS_ATTRIBUTES)
    form = mean(max(0.0, min(1.0, (player.form - 0.8) / 0.4)) for player in eleven) if eleven else 0.5
    overall = mean(player.overall for player in eleven) / 100.0 if eleven else 0.0

    tactics = _metrics_of_system(system) if system else {}
    factors = [
        Metric(
            "attack_index",
            "Attack index",
            attack,
            "0-1",
            f"mean of {', '.join(BAND_ATTRIBUTES['attack'])} over the {len(bands['attack'])} forwards this shape selects, rescaled (x−28)/68.",
        ),
        Metric(
            "midfield_index",
            "Midfield index",
            midfield,
            "0-1",
            f"mean of {', '.join(BAND_ATTRIBUTES['midfield'])} over the {len(bands['midfield'])} midfielders this shape selects, rescaled (x−28)/68.",
        ),
        Metric(
            "defence_index",
            "Defence index",
            defence,
            "0-1",
            f"mean of {', '.join(BAND_ATTRIBUTES['defence'])} over the {len(bands['defence'])} defenders, rescaled (x−28)/68.",
        ),
        Metric(
            "keeper_index",
            "Keeper index",
            keeper,
            "0-1",
            "the world's player model has no goalkeeping attribute, so this is positioning, anticipation, decision-making, composure and agility of the selected keeper, rescaled (x−28)/68.",
        ),
        Metric(
            "press_index",
            "Press index",
            press,
            "0-1",
            f"mean of {', '.join(PRESS_ATTRIBUTES)} across the selected eleven, rescaled (x−28)/68.",
        ),
        Metric("form_index", "Form index", form, "0-1", "mean of the selected eleven's stored form, rescaled from 0.8–1.2 to 0–1."),
        Metric(
            "squad_index",
            "Selected-eleven rating",
            overall,
            "0-1",
            f"mean overall of the {len(eleven)} players this formation selected, /100.",
        ),
    ]
    for key in ("width", "depth", "balance", "spacing", "isolation", "line_separation", "space_behind"):
        if key in tactics:
            factors.append(
                Metric(
                    f"tactics_{key}",
                    f"System {key.replace('_', ' ')}",
                    tactics[key],
                    "m" if key != "coverage" else "m²",
                    "measured by app.services.tactics.analysis.metrics_of from the eleven coordinates of the chosen system, in possession.",
                )
            )
    shortfalls = [
        Metric(
            f"{band}_short",
            f"{band} players available",
            float(len(bands[band])),
            "count",
            "count of the selected side sitting in this band; a shortfall was filled from another band, which is why the index beside it may not match the club's reputation.",
        )
        for band in ("defence", "midfield", "attack")
    ]

    squad_factors: list[Metric] = []
    if squad is not None and not squad.empty:
        squad_factors = [
            Metric(
                "transfers_in",
                "Signed players applied",
                float(len(squad.added)),
                "count",
                f"{squad.label}: these players were added to the club's stored squad rows before the side was selected, so the indices above are the squad this career has, not the squad the world generator wrote.",
            ),
            Metric(
                "transfers_out",
                "Departed players removed",
                float(len(squad.removed)),
                "count",
                "ids taken out of the squad rows before selection, so a player this career sold or released cannot be picked by any formation.",
            ),
        ]

    return SideProfile(
        team_id=team.id,
        name=team.name,
        short_name=team.short_name or team.name,
        formation=formation,
        system_slug=system.slug if system else "",
        system_name=system.name if system else "no system chosen — indices only",
        attack=attack,
        midfield=midfield,
        defence=defence,
        keeper=keeper,
        press=press,
        form=form,
        overall=overall,
        squad_label=squad.label if squad is not None else "",
        tactics=tactics,
        lineup=tuple((player.name, player.position, band) for band in ("keeper", "defence", "midfield", "attack") for player in bands[band]),
        factors=tuple([*factors, *shortfalls, *squad_factors]),
    )


def possession_share(home: SideProfile, away: SideProfile, home_tactics: Mapping[str, float], away_tactics: Mapping[str, float]) -> float:
    """Where the ball goes, from the two midfields and how pressable each shape is.

    `0.5 + 0.5·tanh(Δ/18)` with Δ built from the midfield index difference plus a term for
    press resistance: a side whose nearest-neighbour spacing is large (an isolated player the opponent
    cannot reach in time) keeps the ball more easily, and one whose lines are far apart plays through
    fewer central channels. The 18 is a chosen constant, not a fitted one.
    """

    def resistance(side: SideProfile, tactics: Mapping[str, float]) -> float:
        if not tactics:
            return 0.0
        return (tactics.get("spacing", 0.0) - 11.0) / 22.0 - (tactics.get("line_separation", 0.0) - 16.0) / 64.0

    delta = (home.midfield - away.midfield) * 26.0 + (resistance(home, home_tactics) - resistance(away, away_tactics)) * 6.0
    return max(0.24, min(0.76, 0.5 + 0.5 * math.tanh(delta / 18.0)))


__all__ = [
    "BANDS",
    "SideProfile",
    "SquadOverlay",
    "band_index",
    "band_of_position",
    "possession_share",
    "select_starting_xi",
    "split_formation",
    "team_profile",
]
