"""The Finals' coach-read — one honest paragraph on the cup ledger of this world.

The Finals door recompute every completed cup Final on every read: who lifted it, the loudest
fixture, the haul each club holds. The model receives exactly those rows — the eight Finals with
their competitions, clubs, scorelines, venue, winners and best-rated starters of each final (MVP
name, rating, goals, assists) — plus the loudest final and the cup-win table. It never invents
a club, player, venue or figure beyond the snapshot; a cup is what the rows say, not what the
reader hopes.

Without a configured provider the door answers `available: false` and the Finals stand alone on
the page.

Feature name for the ledger: `world.finals.read`.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.providers import LlmResult, get_llm_provider
from app.services.knowledge.library_charter import LIBRARY_CHARTER
from app.services.model_ledger import record_model_call_safely
from app.services.world.finals import compute_finals

_SYSTEM = """\
You are the voice of The Finals — the cup ledger of this product's synthetic world, recomputed
on every read. You see exactly the eight Finals the door printed: competition, kickoff, the two
clubs, the scoreline, the winner, the venue, and the best-rated starter of each final with
their rating, goals and assists — plus the cup-haul table for every club that has won one. You
know nothing else about this league. Your task:

1. Speak one short paragraph on the cup ledger — which clubs lifted which cup, the loudest
   final with its venue and score, and the haul of cups share among the winners.
2. Name every club, competition, fixture, player and figure exactly as the rows print them. No
   inventing clubs, venue towns, scorers or ratings.
3. The MVP of a final is the best-rated starter in the rows — do not promote them to captain,
   legend or anything else the rows do not say.
4. Plain English, one paragraph, no headings, no bullets, no emoji.
"""

_PROMPT = """\
Season 2026/27 — what the Finals door printed for the cup ledger:

Competitions decided: {finals_count}  ·  Goals scored across all finals: {goals}
Loudest final: {loudest_block}

Finals (in kickoff order):
{finals_block}

Cup haul (clubs that lifted at least one):
{cup_wins_block}

The reader wants one honest paragraph on what the cup ledger shows.
"""


def _fmt_final(row: dict[str, Any]) -> str:
    home = (row.get("home") or {}).get("name", "?")
    away = (row.get("away") or {}).get("name", "?")
    competition = (row.get("competition") or {}).get("name", "?")
    mvp = row.get("mvp") or {}
    mvp_part = (
        f" · best-rated starter {mvp.get('name', '?')} ({mvp.get('position', '?')}, rating {mvp.get('rating', '?')}, "
        f"{mvp.get('goals', 0)} goals {mvp.get('assists', 0)} assists)"
        if mvp
        else ""
    )
    return (
        f"  {competition} · {row.get('fixture', {}).get('kickoff', '?')} · {home} {row.get('home_goals', '?')}–"
        f"{row.get('away_goals', '?')} {away} · winner: {(row.get('winning_team') or {}).get('name', 'drawn')}"
        f"{mvp_part}"
    )


def _loudest_block(loudest: dict[str, Any] | None) -> str:
    if not loudest:
        return "(no loudest final — the season has not written one)"
    return (
        f"{(loudest.get('competition') or {}).get('name', '?')} · {loudest.get('goals', '?')} goals "
        f"({loudest.get('home_goals', '?')}–{loudest.get('away_goals', '?')}) at {loudest.get('venue', '?')}"
    )


def _cup_wins_block(rows: list[dict[str, Any]] | None) -> str:
    if not rows:
        return "  (no club has lifted a cup yet)"
    lines = []
    for row in rows:
        team = (row.get("team") or {}).get("name", "?")
        cups = row.get("cups", 0)
        names = ", ".join(row.get("names", []))
        lines.append(f"  {team} — {cups} cup(s): {names}")
    return "\n".join(lines)


def compute_finals_coach_read(db: Session) -> dict[str, Any]:
    try:
        ledger = compute_finals(db)
    except Exception as error:  # noqa: BLE001 — the door must answer, not 500
        record_model_call_safely(
            result=LlmResult(
                text="",
                provider="unknown",
                model="finals-coach-read",
                demo_mode=True,
                error=str(error)[:300],
                latency_ms=0,
            ),
            feature="world.finals.read",
        )
        return {"available": False, "edition": "2026/27", "provider": "unknown", "error": "finals recompute failed"}

    if not ledger.get("available"):
        return {
            "available": False,
            "edition": "2026/27",
            "provider": "unknown",
            "error": ledger.get("reason", "the finals ledger could not be computed"),
        }

    rows = ledger.get("finals", [])
    prompt = _PROMPT.format(
        finals_count=ledger.get("stats", {}).get("finals", 0),
        goals=ledger.get("stats", {}).get("goals", 0),
        loudest_block=_loudest_block(ledger.get("loudest")),
        finals_block="\n".join(_fmt_final(row) for row in rows) if rows else "  (none logged)",
        cup_wins_block=_cup_wins_block(ledger.get("cup_wins")),
    )

    provider = get_llm_provider()
    try:
        result = provider.complete(system=LIBRARY_CHARTER + _SYSTEM, prompt=prompt, max_tokens=380, temperature=0.3)
    except Exception as error:  # noqa: BLE001
        failure = LlmResult(
            text="",
            provider=getattr(provider, "name", "unknown"),
            model="unreachable",
            demo_mode=True,
            error=str(error)[:300],
            latency_ms=0,
        )
        record_model_call_safely(result=failure, feature="world.finals.read")
        return {
            "available": False,
            "edition": "2026/27",
            "provider": failure.provider,
            "error": (failure.error or "unreachable gateway")[:160],
        }

    record_model_call_safely(result=result, feature="world.finals.read")
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


__all__ = ["compute_finals_coach_read"]
