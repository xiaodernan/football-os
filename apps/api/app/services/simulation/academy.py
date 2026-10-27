"""The career academy's outcomes (M13 item 7, career-domain half).

The roadmap asked for academy trainees graduating into the squad with attributes derived from their
stored load. Two honest constraints shape what landed:

* **There is no organisation-to-career link.** M8's academy tier (development plans, assessments,
  sessions) hangs off user-created tenants and shares no rows with a career, so this block reads the
  load the career domain actually stores: the world's own training sessions and the career's own
  appearance rows — the same two sources the `development` block projects from.
* **The graduation is deliberately not a dice roll.** The engine's selection and the development curve
  are deterministic, so a career replays byte-identically; a random roll would make a stored match's
  replay report a squad the one that played never used. "Graduating" is therefore measured, not drawn:
  the shape picks the eleven from the career's current squad exactly as `play_round` would, and a
  trainee under the age ceiling is `selected` in that eleven, `next_in_line` as the first reserve of
  his band, or `off_the_pace` at his band rank.

Everything is recomputed from the rows on every read and nothing is written back — the same discipline
the `development` block states, because a graduation verdict that edited the world would corrupt every
other page that reads it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Career, CareerAppearance, RealPlayer, Team
from app.services.simulation.carry_over import training_loads
from app.services.simulation.development import (
    DEVELOPMENT_RATE,
    DEVELOPMENT_TAU,
    TRAINING_MINUTES_PER_UNIT,
    developed_overall,
)
from app.services.simulation.profile import band_of_position, select_starting_xi, split_formation
from app.services.simulation.squad import squad_as_of
from app.services.tactics.plan import system_by_slug

#: A trainee is a squad player at or under this age. Authored: the world generates outfielders at
#: 17-34, so 21 names the season's genuine youth class without sweeping in the mid-20s squad players.
YOUTH_AGE_MAX: Final = 21

ACADEMY_FORMULA: Final = (
    "graduation is the engine's own selection read forward: the formation picks the eleven from the "
    "career's current squad by band, best stored overall first (slug breaks ties); a trainee at or "
    "under the age ceiling is `selected` in that eleven, `next_in_line` as the first reserve of his "
    "band (band rank = seats + 1), otherwise `off_the_pace` at his band rank. `projected_overall` "
    "applies the development curve to the stored overall toward the stored potential over "
    "effective_minutes = match_minutes + 0.5·training_load_units"
)

VERDICTS: Final = ("selected", "next_in_line", "off_the_pace")


def academy_class(
    squad: Sequence[RealPlayer],
    *,
    selected_ids: set[str],
    seats_per_band: Mapping[str, int],
    loads: Mapping[str, tuple[int, int]],
    youth_age_max: int = YOUTH_AGE_MAX,
) -> list[dict[str, Any]]:
    """The youth class judged against the eleven, one row per trainee.

    `squad` is the career's current squad (stored rows with the transfer overlay applied);
    `selected_ids` is the eleven the engine's own selection picks from those rows; `seats_per_band`
    counts how many of that eleven belong to each band by the players' own positions;
    `loads` maps player id → (career minutes, training load units). Pure: every figure is derived from
    the arguments, which makes the empty class and the verdict boundaries testable without a database.
    """
    pools: dict[str, list[RealPlayer]] = {}
    for player in squad:
        pools.setdefault(band_of_position(player.position), []).append(player)
    for pool in pools.values():
        pool.sort(key=lambda player: (-player.overall, player.slug))
    rank_of: dict[str, int] = {}
    for pool in pools.values():
        for index, player in enumerate(pool, start=1):
            rank_of[player.id] = index
    seat_overall: dict[str, int | None] = {}
    for band in set(seats_per_band) | set(pools):
        selected_in_band = [player for player in squad if player.id in selected_ids and band_of_position(player.position) == band]
        seat_overall[band] = min((player.overall for player in selected_in_band), default=None)

    rows: list[dict[str, Any]] = []
    for player in squad:
        if int(player.age) > youth_age_max:
            continue
        band = band_of_position(player.position)
        minutes, training_units = loads.get(player.id, (0, 0))
        effective = int(minutes) + int(round(TRAINING_MINUTES_PER_UNIT * training_units))
        projected = round(developed_overall(player.overall, potential=player.potential, minutes_played=effective), 1)
        seats = seats_per_band.get(band, 0)
        rank = rank_of.get(player.id)
        selected = player.id in selected_ids
        if selected:
            verdict = "selected"
        elif rank is not None and rank == seats + 1:
            verdict = "next_in_line"
        else:
            verdict = "off_the_pace"
        last_seat = seat_overall.get(band)
        rows.append(
            {
                "player_id": player.id,
                "player_slug": player.slug,
                "player_name": player.name,
                "position": player.position,
                "band": band,
                "age": int(player.age),
                "stored_overall": int(player.overall),
                "stored_potential": int(player.potential),
                "minutes": int(minutes),
                "training_units": int(training_units),
                "effective_minutes": effective,
                "projected_overall": projected,
                "potential_headroom": round(max(0.0, float(player.potential) - projected), 1),
                "band_rank": rank,
                "band_size": len(pools.get(band, [])),
                "seats_in_band": seats,
                "verdict": verdict,
                "gap_to_last_seat": (None if selected or last_seat is None else round(float(last_seat) - float(player.overall), 1)),
            }
        )
    rows.sort(key=lambda row: (-int(row["stored_overall"]), str(row["player_slug"])))
    return rows


def academy_view(
    session: Session,
    career: Career,
    *,
    appearances: list[CareerAppearance] | None = None,
    training: dict[str, int] | None = None,
) -> dict[str, Any]:
    """`career_view["academy"]`: the club's under-21 squad players and where each stands.

    The eleven is the engine's own `select_starting_xi` over the squad as of the next round — the same
    composition `team_profile` performs before every played round — so a `selected` verdict is not an
    opinion about talent but the fact the engine would hand this trainee a shirt. `appearances`/
    `training` let the career view hand in the rows it already fetched.
    """
    appearances = appearances if appearances is not None else list(session.scalars(select(CareerAppearance).where(CareerAppearance.career_id == career.id)).all())
    if not career.club_id:
        return _empty("the career has no club to run an academy at")
    minutes_by_player: dict[str, int] = {}
    for row in appearances:
        player_id = str(row.player_id)
        minutes_by_player[player_id] = minutes_by_player.get(player_id, 0) + int(row.minutes)
    training = training if training is not None else training_loads(session, sorted(minutes_by_player))
    stored = list(session.scalars(select(RealPlayer).where(RealPlayer.team_id == career.club_id)).all())
    overlay = squad_as_of(session, career, int(career.rounds_played) + 1, appearances=appearances, training=training)
    squad: list[RealPlayer] = list(stored)
    if overlay is not None:
        squad = [player for player in squad if player.id not in overlay.removed]
        present = {player.id for player in squad}
        squad = [*squad, *(player for player in overlay.added if player.id not in present)]
    if not squad:
        return _empty("the career's club has no players to select from")
    team = session.get(Team, career.club_id)
    if career.system_slug:
        system = system_by_slug(career.system_slug)
        if system is None:
            raise LookupError(f"no tactical system {career.system_slug}")
        formation = system.formation
    else:
        formation = team.formation if team is not None else ""
    defenders, midfielders, attackers = split_formation(formation)
    bands = select_starting_xi(squad, defenders, midfielders, attackers)
    eleven = [player for group in bands.values() for player in group]
    selected_ids = {player.id for player in eleven}
    seats_per_band: dict[str, int] = {}
    for player in eleven:
        band = band_of_position(player.position)
        seats_per_band[band] = seats_per_band.get(band, 0) + 1
    loads = {player_id: (minutes, int(training.get(player_id, 0))) for player_id, minutes in minutes_by_player.items()}
    trainees = academy_class(squad, selected_ids=selected_ids, seats_per_band=seats_per_band, loads=loads)
    if not trainees:
        return _empty(f"no squad player is at or under the age ceiling of {YOUTH_AGE_MAX}")
    return {
        "available": True,
        "youth_age_max": YOUTH_AGE_MAX,
        "class_size": len(trainees),
        "selected_count": sum(1 for row in trainees if row["verdict"] == "selected"),
        "next_in_line_count": sum(1 for row in trainees if row["verdict"] == "next_in_line"),
        "squad_size": len(squad),
        "formation": formation,
        "system_slug": career.system_slug or "",
        "trainees": trainees,
        "tau": DEVELOPMENT_TAU,
        "rate": DEVELOPMENT_RATE,
        "academy_formula": ACADEMY_FORMULA,
        "formulas": {
            "band_rank": "the trainee's place in his band's pool, ordered by stored overall descending then slug — the same order the engine's selection reads",
            "seats_in_band": "how many of the selected eleven belong to that band by their own positions, borrowed players counted where they came from",
            "next_in_line": "band_rank equals seats_in_band + 1 — the first name the shape would reach for in that band",
            "gap_to_last_seat": "the weakest selected player of the trainee's band, stored overall minus the trainee's stored overall; positive means he sits behind the last seat today",
            "projected_overall": "the development curve applied to the stored overall toward the stored potential over effective minutes; the same curve the `development` block applies to each attribute",
            "potential_headroom": "stored potential minus projected_overall, floored at zero — the curve never crosses potential, so this is the growth still owed",
        },
        "note": (
            "graduation here is measured, not drawn: the selection and the curve are deterministic, so a "
            "career replays identically and no dice are thrown. The M8 academy tier (development plans, "
            "assessments) is a separate tenant-scoped surface with no link to careers; this block reads "
            "the world's own training sessions and the career's own appearance rows, recomputed on every "
            "read and never written back — the stored squad elsewhere on this page is unchanged"
        ),
        "data_origin": "simulation",
        "is_demo_data": True,
    }


def _empty(reason: str) -> dict[str, Any]:
    return {
        "available": False,
        "youth_age_max": YOUTH_AGE_MAX,
        "class_size": 0,
        "selected_count": 0,
        "next_in_line_count": 0,
        "squad_size": 0,
        "trainees": [],
        "reason": reason,
        "academy_formula": ACADEMY_FORMULA,
        "data_origin": "simulation",
        "is_demo_data": True,
    }


__all__ = [
    "ACADEMY_FORMULA",
    "VERDICTS",
    "YOUTH_AGE_MAX",
    "academy_class",
    "academy_view",
]
