"""The simulator's coach-read — one honest paragraph about a stored match, from the report's own numbers.

A stored simulation is an account's working record of one match: the seed, the model version, the two
clubs' stored squads, the tactical systems, the score, possession, shots, expected goals, momentum and
the momentum of every block. The model receives exactly that report as structured facts and speaks one
short paragraph about the match. It names the seed and the model version verbatim — the two facts that
make the piece honest — and it never invents a player beyond the two XI lists the report prints.

The door is the account's own, like the other `/simulate` doors. Without a configured provider the
panel prints the report's own facts and says the model's read is unavailable.

Feature name for the ledger: `simulate.analysis`.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.security import ownership_or_admin
from app.models import SimulationMatch, User
from app.providers import LlmResult, get_llm_provider
from app.services.model_ledger import record_model_call_safely

_SYSTEM = """\
You are a match analyst reading one deterministic simulation run by this product's hand-authored
`possession-block-v1@1.0.0` engine. You never see the real world — only the report this match produced.
Your task:

1. Speak one honest paragraph: the seed and model version name what this is; the two sides' tactical
   systems, the score, the xG split, the block events and the momentum line — all in one paragraph.
2. Do not invent a player name; the squads are stored rows and the report knows who played.
3. Do not predict the next match; this read is of this stored match only.
4. Plain English, no headings, no bullets, no emoji.
"""

_PROMPT = """\
Seed {seed} · model {model_version} · {minutes} minutes · {subs} substitutions · shift at minute {shift}
Home: {home_name} — system {home_system}, formation {home_formation}, momentum {home_momentum}
Away: {away_name} — system {away_system}, formation {away_formation}, momentum {away_momentum}
Score: {home_goals}-{away_goals} ({winner_side})
Possession: {home_possession:.1f}% / {away_possession:.1f}%
Shots: {home_shots}-{away_shots} ({home_sot}-{away_sot} on target)
Expected goals: {home_xg:.2f}-{away_xg:.2f}

The reader wants one honest paragraph about this match, from these numbers only.
"""


def _get_match(db: Session, owner: User, ident: str) -> SimulationMatch | None:
    match = db.scalar(
        select(SimulationMatch).where(or_(SimulationMatch.slug == ident, SimulationMatch.id == ident))
    )
    if match is None:
        return None
    ownership_or_admin(owner, match.owner_id, "simulation")
    return match


def compute_simulation_coach_read(db: Session, owner: User, ident: str) -> dict[str, Any]:
    match = _get_match(db, owner, ident)
    if match is None:
        return {"available": False, "provider": "unknown", "error": "no_such_simulation"}

    report = match.report if isinstance(match.report, dict) else {}
    sides = report.get("sides", {}) if isinstance(report, dict) else {}
    home = sides.get("home", {}) if isinstance(sides, dict) else {}
    away = sides.get("away", {}) if isinstance(sides, dict) else {}

    home_name = home.get("name", "?")
    away_name = away.get("name", "?")
    home_system = home.get("system_name", "?")
    away_system = away.get("system_name", "?")
    home_formation = home.get("formation", "?")
    away_formation = away.get("formation", "?")

    prompt = _PROMPT.format(
        seed=match.seed,
        model_version=match.model_version,
        minutes=match.minutes,
        subs=match.substitutions,
        shift=match.tactical_shift_minute,
        home_name=home_name,
        home_system=home_system,
        home_formation=home_formation,
        home_momentum=round(match.home_momentum, 2),
        away_name=away_name,
        away_system=away_system,
        away_formation=away_formation,
        away_momentum=round(match.away_momentum, 2),
        home_goals=match.home_goals,
        away_goals=match.away_goals,
        winner_side=match.winner_side,
        home_possession=float(home.get("possession_pct", 0) or 0),
        away_possession=float(away.get("possession_pct", 0) or 0),
        home_shots=home.get("shots", 0),
        away_shots=away.get("shots", 0),
        home_sot=home.get("shots_on_target", 0),
        away_sot=away.get("shots_on_target", 0),
        home_xg=float(home.get("expected_goals", 0) or 0),
        away_xg=float(away.get("expected_goals", 0) or 0),
    )

    provider = get_llm_provider()
    try:
        result = provider.complete(system=_SYSTEM, prompt=prompt, max_tokens=360, temperature=0.3)
    except Exception as error:  # noqa: BLE001 — the provider is the risk; the door must stay up.
        failure = LlmResult(
            text="",
            provider=getattr(provider, "name", "unknown"),
            model="unreachable",
            demo_mode=True,
            error=str(error)[:300],
            latency_ms=0,
        )
        record_model_call_safely(result=failure, feature="simulate.analysis")
        return {
            "available": False,
            "provider": failure.provider,
            "error": (failure.error or "unreachable gateway")[:160],
        }

    record_model_call_safely(result=result, feature="simulate.analysis")
    if result.error:
        return {
            "available": False,
            "provider": result.provider,
            "model": result.model,
            "error": (result.error or "provider error")[:160],
        }
    return {
        "available": True,
        "provider": result.provider,
        "model": result.model,
        "demo_mode": result.demo_mode,
        "input_tokens": result.input_tokens,
        "cached_input_tokens": result.cached_input_tokens,
        "cache_reported": result.cache_reported,
        "output_tokens": result.output_tokens,
        "latency_ms": result.latency_ms,
        "answer": result.text,
    }


__all__ = ["compute_simulation_coach_read"]
