"""The Dynasties' coach-read — one honest paragraph on the world's streak ledger.

The dynasties door walks every completed tier-1 fixture once, scores W/D/L per club in kickoff
order, and prints the five longest winning streaks, the five longest unbeaten runs and who is
 ablaze at the latest completed matchday. The model receives exactly those aggregates and speaks
one short paragraph on the streaks this world produced. It never invents a club, run or result
beyond the snapshot; a streak is arithmetic on the rows, not a confession of invincibility.

Without a configured provider the door answers `available: false` and the ledger stands alone.

Feature name for the ledger: `world.dynasties.read`.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.providers import LlmResult, get_llm_provider
from app.services.knowledge.library_charter import LIBRARY_CHARTER
from app.services.model_ledger import record_model_call_safely
from app.services.world.dynasties import compute_dynasties

_SYSTEM = """\
You are the voice of The Dynasties — the tier-1 streak ledger, computed from every completed
fixture. You see exactly the rows the door printed: the longest winning streak, the longest
unbeaten run, and who is ablaze at the latest completed matchday, with names, lengths, rounds
and matches. You know nothing else about this league. Your task:

1. Speak one short paragraph on the streak ledger — which club holds the longest run of wins and
   how it ended, which club holds the longest unbeaten run, and who is ablaze right now.
2. Name every club, matchday, length and figure exactly as the rows print them. No inventing
   clubs, runs or results beyond the snapshot.
3. A streak is a run of results in kickoff order, not a prophecy and not a claim about any
   future fixture. Do not present it as one.
4. Plain English, one paragraph, no headings, no bullets, no emoji.
"""

_PROMPT = """\
Season 2026/27 — what the Dynasties streak ledger printed for {competition_name} (tier-1):

Judged fixtures: {judged}
Longest win streak: {longest_win_block}
Longest unbeaten run: {longest_unbeaten_block}
Ablaze right now: {ablaze_block}

The five longest winning streaks:
{win_streaks_block}

The five longest unbeaten runs:
{unbeaten_runs_block}

The reader wants one honest paragraph on what these streaks hold up.
"""


def _run_block(run: dict[str, Any] | None) -> str:
    if not run:
        return "(none)"
    team = (run.get("team") or {}).get("name", "?")
    return (
        f"{team} · {run.get('length', '?')} match(es) "
        f"({run.get('start_round', '?')} → {run.get('end_round', '?')})"
    )


def _top_lines(runs: list[dict[str, Any]] | None, limit: int = 5) -> str:
    if not runs:
        return "  (none)"
    lines = []
    for index, run in enumerate(runs[:limit], start=1):
        team = (run.get("team") or {}).get("name", "?")
        lines.append(
            f"  {index}. {team} · {run.get('length', '?')} match(es) "
            f"({run.get('start_round', '?')} → {run.get('end_round', '?')})"
        )
    return "\n".join(lines)


def _ablaze_block(ablaze: dict[str, Any] | None) -> str:
    if not ablaze or not ablaze.get("team"):
        return "(nobody is ablaze at the latest completed matchday)"
    team = ablaze["team"].get("name", "?")
    return f"{team} · {ablaze.get('current_win_run', 0)} win(s) on the trot · {ablaze.get('matches', 0)} played this season"


def compute_dynasties_coach_read(db: Session) -> dict[str, Any]:
    try:
        ledger = compute_dynasties(db)
    except Exception as error:  # noqa: BLE001 — the door must answer, not 500
        record_model_call_safely(
            result=LlmResult(
                text="",
                provider="unknown",
                model="dynasties-coach-read",
                demo_mode=True,
                error=str(error)[:300],
                latency_ms=0,
            ),
            feature="world.dynasties.read",
        )
        return {"available": False, "edition": "2026/27", "provider": "unknown", "error": "dynasties recompute failed"}

    if not ledger.get("available"):
        return {
            "available": False,
            "edition": "2026/27",
            "provider": "unknown",
            "error": ledger.get("reason", "the streak ledger could not be computed"),
        }

    prompt = _PROMPT.format(
        competition_name=ledger.get("competition", "?"),
        judged=ledger.get("judged", 0),
        longest_win_block=_run_block(ledger.get("longest_win")),
        longest_unbeaten_block=_run_block(ledger.get("longest_unbeaten")),
        ablaze_block=_ablaze_block(ledger.get("ablaze")),
        win_streaks_block=_top_lines(ledger.get("win_streaks")),
        unbeaten_runs_block=_top_lines(ledger.get("unbeaten_runs")),
    )

    provider = get_llm_provider()
    try:
        result = provider.complete(system=LIBRARY_CHARTER + _SYSTEM, prompt=prompt, max_tokens=320, temperature=0.3)
    except Exception as error:  # noqa: BLE001
        failure = LlmResult(
            text="",
            provider=getattr(provider, "name", "unknown"),
            model="unreachable",
            demo_mode=True,
            error=str(error)[:300],
            latency_ms=0,
        )
        record_model_call_safely(result=failure, feature="world.dynasties.read")
        return {
            "available": False,
            "edition": "2026/27",
            "provider": failure.provider,
            "error": (failure.error or "unreachable gateway")[:160],
        }

    record_model_call_safely(result=result, feature="world.dynasties.read")
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


__all__ = ["compute_dynasties_coach_read"]
