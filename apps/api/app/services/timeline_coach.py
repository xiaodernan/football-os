"""The Timeline's coach-read — one honest paragraph on the season's story arc.

The timeline door walks the tier-1 fixtures matchday by matchday and computes the season's own
highlights — the eventual champion's opening lead, the goal-avalanche matchday, the matchday from
which they never relinquished the lead, and the matchday after which every rival's ceiling fell
short of the champion's points. The model receives exactly those highlights plus the champion's
final figures, and speaks one short paragraph on how the season went. It never invents a fixture,
club, matchday or figure beyond the door's own arithmetic; the settled mark is arithmetic, not a
verdict on merit.

Without a configured provider the door answers `available: false` and the timeline stands alone.

Feature name for the ledger: `world.timeline.read`.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.providers import LlmResult, get_llm_provider
from app.services.model_ledger import record_model_call_safely
from app.services.world.timeline import compute_timeline

_SYSTEM = """\
You are the voice of The Timeline — the tier-1 season told matchday by matchday, computed from
the stored fixtures. You see exactly the season's own highlights: the eventual champion's final
figures, whether the champion led on matchday one, the goal-avalanche matchday, the matchday from
which they never relinquished the lead, and the matchday after which every rival's ceiling fell
short of the champion's points. You know nothing else about this league. Your task:

1. Speak one short paragraph on how the season went — the opening, the avalanche matchday, the
   takeover, the settlement, and the champion's final figures.
2. Name every club, matchday, goal count and figure exactly as the rows print them. No inventing
   fixtures, clubs or matchdays — the highlights are the whole story the door tells.
3. The settlement is this door's own arithmetic over remaining matchdays; it is not a verdict on
   talent or style, and this paragraph makes no claim beyond it.
4. Plain English, one paragraph, no headings, no bullets, no emoji.
"""

_PROMPT = """\
Season 2026/27 — what the Timeline printed for {competition_name} (tier-1):

Matchdays played: {matchdays}
Champion: {champion_name} — {champ_points} points from {champ_played} played ({champ_won} W · {champ_drawn} D · {champ_lost} L · {champ_gd} GD)
Opened the season: {opening_line}
Goal-avalanche matchday: {avalanche_line}
Takeover from: {takeover_line}
Settled at: {settled_line}

The reader wants one honest paragraph on the season's arc.
"""


def _opening_line(beats: dict[str, Any]) -> str:
    opening = beats.get("opening", {}) or {}
    if not opening.get("available"):
        return "(no opening chapter recorded)"
    leader = (opening.get("leader") or {}).get("name", "?")
    led = "yes" if opening.get("eventual_champion_led") else f"no ({leader} led)"
    return f"matchday {opening.get('matchday')} · eventual champion led from the first: {led}"


def _avalanche_line(beats: dict[str, Any]) -> str:
    avalanche = beats.get("avalanche", {}) or {}
    if not avalanche.get("available"):
        return "(none)"
    return f"matchday {avalanche.get('matchday')} — {avalanche.get('goals', 0)} goals across {avalanche.get('fixtures', 0)} fixtures"


def _takeover_line(beats: dict[str, Any]) -> str:
    takeover = beats.get("takeover", {}) or {}
    if not takeover.get("available"):
        return "(none)"
    return f"matchday {takeover.get('matchday')} · never relinquished the lead over the next {takeover.get('lead_matchdays', 0)} matchdays"


def _settled_line(beats: dict[str, Any]) -> str:
    settled = beats.get("settled", {}) or {}
    if settled.get("available"):
        return f"matchday {settled.get('matchday')} · every rival's ceiling fell short of {settled.get('points', '?')} points with a gap of {settled.get('gap', '?')}"
    if settled.get("decided_on_tiebreak"):
        return "the season ended with the title sealed at the whistle, on the tiebreak — the ceiling never strictly fell short"
    return "(settlement not reached — the walk never cleared every rival's ceiling)"


def compute_timeline_coach_read(db: Session) -> dict[str, Any]:
    try:
        season = compute_timeline(db)
    except Exception as error:  # noqa: BLE001 — the door must answer, not 500
        record_model_call_safely(
            result=LlmResult(
                text="",
                provider="unknown",
                model="timeline-coach-read",
                demo_mode=True,
                error=str(error)[:300],
                latency_ms=0,
            ),
            feature="world.timeline.read",
        )
        return {"available": False, "edition": "2026/27", "provider": "unknown", "error": "timeline recompute failed"}

    if not season.get("available"):
        return {
            "available": False,
            "edition": "2026/27",
            "provider": "unknown",
            "error": season.get("reason", "the timeline could not be computed"),
        }

    champion = season.get("champion", {})
    beats = season.get("beats", {})
    prompt = _PROMPT.format(
        competition_name=season.get("competition", "?"),
        matchdays=season.get("matchdays", 0),
        champion_name=champion.get("name", "?"),
        champ_points=champion.get("points", 0),
        champ_played=champion.get("played", 0),
        champ_won=champion.get("won", 0),
        champ_drawn=champion.get("drawn", 0),
        champ_lost=champion.get("lost", 0),
        champ_gd=champion.get("goal_difference", 0),
        opening_line=_opening_line(beats),
        avalanche_line=_avalanche_line(beats),
        takeover_line=_takeover_line(beats),
        settled_line=_settled_line(beats),
    )

    provider = get_llm_provider()
    try:
        result = provider.complete(system=_SYSTEM, prompt=prompt, max_tokens=320, temperature=0.3)
    except Exception as error:  # noqa: BLE001
        failure = LlmResult(
            text="",
            provider=getattr(provider, "name", "unknown"),
            model="unreachable",
            demo_mode=True,
            error=str(error)[:300],
            latency_ms=0,
        )
        record_model_call_safely(result=failure, feature="world.timeline.read")
        return {
            "available": False,
            "edition": "2026/27",
            "provider": failure.provider,
            "error": (failure.error or "unreachable gateway")[:160],
        }

    record_model_call_safely(result=result, feature="world.timeline.read")
    if result.error:
        return {
            "available": False,
            "edition": "2026/27",
            "provider": result.provider,
            "model": result.model,
            "error": (result.error or "provider error")[:160],
        }
    return {
        "available": True,
        "edition": "2026/27",
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


__all__ = ["compute_timeline_coach_read"]
