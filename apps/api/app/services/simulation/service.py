"""Running and keeping simulations (M6, spec §19, §20, §61).

This module is the seam between the engine, which knows nothing about the database, and the routes,
which know nothing about football. Three things are decided here:

* **Where an input comes from.** A side is built by `team_profile`, which reads a club's stored squad
  and the metres of the tactical system it is playing. Nothing here invents a number: an unknown club
  or system raises `LookupError`, which the routes turn into a 404 rather than a plausible guess.
* **What is kept.** The whole report goes into `sim_matches.report`, alongside the four inputs that
  produced it, so a stored match can be replayed and its digest checked against the one on file.
  `replay_is_identical` does exactly that and is what the tests assert.
* **Who can see it.** A simulation is not user content — the clubs are the project's own fiction — but
  which clubs an account chooses to play is theirs, so the list and the detail are owner-only, the
  same door §61 puts on boards and clips.
"""

from __future__ import annotations

import secrets
from typing import Any, Final

from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session

from app.core.security import new_public_id
from app.models import SimulationMatch, Team
from app.services.simulation.engine import (
    CALIBRATION_NOTE,
    ENGINE_NAME,
    FACTOR_EXPRESSIONS,
    MODEL_VERSION,
    SIMULATION_DISCLAIMER,
    MatchInputs,
    simulate_match,
)
from app.services.simulation.profile import SideProfile, SquadOverlay, team_profile
from app.services.simulation.squad import replay_squads
from app.services.tactics.plan import tactical_systems
from app.services.world import world_ready
from app.services.world.names import slugify

SIM_LIMIT_PER_USER: Final = 100
MINUTES_CHOICES: Final = (30, 60, 90, 120)
BLOCK_MINUTES: Final = 6


def engine_description() -> dict[str, Any]:
    """What the model is, for the page that offers it — the same strings the report carries."""
    return {
        "name": ENGINE_NAME,
        "version": MODEL_VERSION,
        "disclaimer": SIMULATION_DISCLAIMER,
        "calibration": CALIBRATION_NOTE,
        "factors": list(FACTOR_EXPRESSIONS),
        "minute_choices": list(MINUTES_CHOICES),
        "block_minutes": BLOCK_MINUTES,
        "inputs_are_from": ["teams", "real_players", "tactical_systems"],
    }


def options(session: Session) -> list[dict[str, Any]]:
    """The clubs on offer: one row per team, with the squad the profile step would select from."""
    rows = session.scalars(select(Team).order_by(Team.name)).all()
    return [
        {
            "team_id": team.id,
            "slug": team.slug,
            "name": team.name,
            "short_name": team.short_name or team.name,
            "formation": team.formation,
            "overall": team.overall,
            "squad_size": team.squad_size,
            "path": f"/team/{team.slug}",
            "data_origin": team.data_origin,
        }
        for team in rows
    ]


def system_options() -> list[dict[str, Any]]:
    """The 50 authored systems, with the formation each one staffs."""
    return [
        {
            "slug": system.slug,
            "name": system.name,
            "formation": system.formation,
            "label": f"{system.name} · {system.formation}",
            "path": f"/tactics/{system.slug}",
        }
        for system in tactical_systems()
    ]


def run_simulation(
    session: Session,
    *,
    owner_id: str,
    home_team_id: str,
    away_team_id: str,
    home_system: str | None = None,
    away_system: str | None = None,
    seed: int | None = None,
    minutes: int = 90,
    home_squad: SquadOverlay | None = None,
    away_squad: SquadOverlay | None = None,
) -> SimulationMatch:
    """Play one fixture, store it, and hand back the row whose `report` is the engine's output.

    The seed is chosen when the caller does not supply one and is always stored, because a simulation
    whose seed is lost is a claim the project cannot re-derive.

    `home_squad`/`away_squad` carry a career's transfers (spec §22) onto the side. They are inputs the
    match's own report records through the selected eleven, and `replay_is_identical` rebuilds them
    from the same move rows, so a career match stays re-derivable after a signing.
    """
    home = team_profile(session, home_team_id, system_slug=home_system, squad=home_squad)
    away = team_profile(session, away_team_id, system_slug=away_system, squad=away_squad)
    inputs = MatchInputs(home=home, away=away, seed=seed if seed is not None else secrets.randbelow(2_147_483_647), minutes=minutes, block_minutes=BLOCK_MINUTES)
    report = simulate_match(inputs)

    slug = slugify(f"{home.short_name}-v-{away.short_name}-{report['digest']}")[:70]
    if session.scalar(select(SimulationMatch).where(SimulationMatch.slug == slug)):
        slug = f"{slug}-{secrets.token_hex(2)}"[:80]
    match = SimulationMatch(
        id=new_public_id("sim"),
        slug=slug,
        owner_id=owner_id,
        model_version=MODEL_VERSION,
        seed=inputs.seed,
        minutes=inputs.minutes,
        block_minutes=inputs.block_minutes,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        home_system=home.system_slug,
        away_system=away.system_slug,
        home_goals=int(report["score"]["home"]),
        away_goals=int(report["score"]["away"]),
        winner_side=str(report["score"]["winner"]["side"]),
        digest=str(report["digest"]),
        report=report,
        data_origin="simulation",
        is_demo_data=True,
    )
    session.add(match)
    session.commit()
    session.refresh(match)
    return match


def replay_is_identical(session: Session, match: SimulationMatch) -> dict[str, Any]:
    """Re-run a stored match from its stored inputs and compare the digest, field by field.

    The inputs include a career's squad if the match was a career round: `replay_squads` finds the
    fixture that recorded it and rebuilds the arrivals and departures as they stood *before that
    round*, so a signing made afterwards cannot quietly rewrite an older result. When the eleven that
    comes out differs from the eleven the report says was picked, the answer is a refusal — replaying
    a different squad and reporting the engine disagreed would blame the model for an input change.

    The same reasoning covers the indices the report printed. `form` is an input the engine reads, and
    since carry-over it reads the appearance trace as of the round being replayed, so a trace row
    deleted or a training applied after the match moves it without the model changing. A match whose
    rebuilt side prints a different index is therefore refused, with both figures named.
    """
    if not match.home_team_id or not match.away_team_id:
        return {"possible": False, "reason": "one of the clubs is no longer in the generated world"}
    home_squad, away_squad, squad_note = replay_squads(session, match.id, match.home_team_id, match.away_team_id)
    home = team_profile(session, match.home_team_id, system_slug=match.home_system or None, squad=home_squad)
    away = team_profile(session, match.away_team_id, system_slug=match.away_system or None, squad=away_squad)
    stored = _as_mapping(match.report)
    changed = [side for side, profile in (("home", home), ("away", away)) if _lineup_changed(stored, side, profile)]
    if changed:
        return {
            "possible": False,
            "reason": (
                f"the {' and '.join(changed)} side's selected eleven is no longer the eleven this match picked, so replaying it would compare two different fixtures rather than re-deriving this one"
            ),
            "squad": squad_note,
            "model_version": match.model_version,
        }
    sides = {"home": home, "away": away}
    moves = {side: _indices_changed(stored, side, profile) for side, profile in sides.items()}
    moved = [(side, keys) for side, keys in moves.items() if keys]
    if moved:
        figures = "; ".join(f"the {side} side's " + " and ".join(f"{key} index ({_fmt(on_file)} on file, {_fmt(rebuilt)} rebuilt)" for key, on_file, rebuilt in keys) for side, keys in moved)
        return {
            "possible": False,
            "reason": (
                f"{figures} no longer match what this match printed — an index the engine reads is an input, not a "
                "result, and it can move without the engine changing: a side's form index is built from each selected "
                "player's stored form and from the condition his load trace gives him *as of the round being replayed*, "
                "so a training applied after this match or a trace row deleted since it was played rebuilds a different "
                "side. Replaying that would compare two different inputs rather than re-derive this one"
            ),
            "squad": squad_note,
            "model_version": match.model_version,
        }
    report = simulate_match(MatchInputs(home=home, away=away, seed=match.seed, minutes=match.minutes, block_minutes=match.block_minutes))
    return {
        "possible": True,
        "stored_digest": match.digest,
        "replayed_digest": report["digest"],
        "identical": report["digest"] == match.digest,
        "stored_score": stored.get("score"),
        "replayed_score": report["score"],
        "squad": squad_note,
        "model_version": match.model_version,
    }


def _lineup_changed(stored: dict[str, Any], side: str, profile: SideProfile) -> bool:
    """True only when the report names an eleven and the rebuilt one differs from it.

    A match stored before lineups were written, or one whose report is missing, is treated as
    unchanged: there is nothing on file to disagree with, and inventing a difference would be a claim.
    """
    recorded = _as_mapping(_as_mapping(stored.get("sides")).get(side)).get("lineup")
    if not isinstance(recorded, list) or not recorded:
        return False
    before = [str(row.get("player", "")) for row in recorded if isinstance(row, dict)]
    return before != [name for name, _, _ in profile.lineup]


def _indices_changed(stored: dict[str, Any], side: str, profile: SideProfile) -> tuple[tuple[str, float, float], ...]:
    """Which of the six indices the report printed differ from the ones the rebuilt side now carries.

    The same discipline as the eleven: a match whose report prints no indices is treated as unchanged
    rather than as a mismatch. This is where carry-over shows up — `form` is the only index that reads
    the appearance trace, so a round whose trace rows were deleted after it was played rebuilds a
    fresher, sharper side than the one that actually kicked off.
    """
    recorded = _as_mapping(_as_mapping(_as_mapping(stored.get("sides")).get(side)).get("indices"))
    printed = _as_mapping(profile.to_dict()["indices"])
    moves: list[tuple[str, float, float]] = []
    for key, rebuilt in printed.items():
        if key not in recorded:
            continue
        on_file = float(recorded[key])
        if float(rebuilt) != on_file:
            moves.append((key, on_file, float(rebuilt)))
    return tuple(moves)


def _fmt(value: object) -> str:
    """A figure for prose: a missing index reads as `?` rather than as a number invented here."""
    return "?" if not isinstance(value, (int, float)) else f"{float(value):.3f}".rstrip("0").rstrip(".")


def _as_mapping(value: object) -> dict[str, Any]:
    """A JSON column read back is a dict, an empty dict, or None; the payload shape wants the first.

    The stored report is copied rather than handed out, so a caller cannot mutate an ORM attribute by
    editing what it received.
    """
    return dict(value) if isinstance(value, dict) else {}


def row(match: SimulationMatch, *, full: bool = False) -> dict[str, Any]:
    """The API shape of a stored match. A list row is a summary; a detail carries the whole report."""
    report = _as_mapping(match.report)
    payload: dict[str, Any] = {
        "id": match.id,
        "slug": match.slug,
        "path": f"/simulate/{match.slug}",
        "model_version": match.model_version,
        "seed": match.seed,
        "minutes": match.minutes,
        "block_minutes": match.block_minutes,
        "home_team_id": match.home_team_id,
        "away_team_id": match.away_team_id,
        "home_system": match.home_system,
        "away_system": match.away_system,
        "score": {"home": match.home_goals, "away": match.away_goals, "winner_side": match.winner_side},
        "digest": match.digest,
        "created_at": match.created_at.isoformat() if match.created_at else None,
        "data_origin": match.data_origin,
        "is_demo_data": match.is_demo_data,
        "disclaimer": SIMULATION_DISCLAIMER,
    }
    sides = _as_mapping(report.get("sides"))
    for key in ("home", "away"):
        side = _as_mapping(sides.get(key))
        payload[f"{key}_summary"] = {
            "name": side.get("name", ""),
            "short_name": side.get("short_name", ""),
            "system_name": side.get("system_name", ""),
            "formation": side.get("formation", ""),
            "possession_pct": side.get("possession_pct", 0),
            "shots": side.get("shots", 0),
            "shots_on_target": side.get("shots_on_target", 0),
            "expected_goals": side.get("expected_goals", 0),
        }
    if full:
        payload["report"] = report
    return payload


def sim_tables_present(session: Session) -> bool:
    return "sim_matches" in inspect(session.get_bind()).get_table_names()


def sim_counts(session: Session) -> dict[str, int]:
    if not sim_tables_present(session):
        return {"simulations": 0}
    return {"simulations": int(session.scalar(select(func.count()).select_from(SimulationMatch)) or 0)}


def sim_ready(session: Session) -> bool:
    """M6 is live when its own table exists and the world it plays from is present.

    Deliberately not "someone has run a match": the gate is whether the feature can serve, and the
    counts travel beside it so a reader can see an empty-but-working surface for what it is.
    """
    return sim_tables_present(session) and world_ready(session)


__all__ = [
    "BLOCK_MINUTES",
    "MINUTES_CHOICES",
    "SIM_LIMIT_PER_USER",
    "engine_description",
    "options",
    "replay_is_identical",
    "row",
    "run_simulation",
    "sim_counts",
    "sim_ready",
    "sim_tables_present",
    "system_options",
]
