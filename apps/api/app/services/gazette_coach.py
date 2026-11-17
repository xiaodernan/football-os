"""The Gazette's coach-read — one honest paragraph on the latest edition's printing.

The Gazette door publishes one edition per completed tier-1 matchday: the scorecard, the table
after it, the loudest fixture, the hot hand and the round's numbers. The model receives exactly
the latest edition's printing — edition number, competition, table leader and gap, loud fixture,
hot hand, and the round's arithmetic — and speaks one short paragraph on the edition. It never
invents a club, fixture, score, venue or figure beyond the edition the door prints, and it makes
no claim about the next matchday.

Without a configured provider the door answers `available: false` and the gazette stands alone.

Feature name for the ledger: `world.gazette.read`.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.providers import LlmResult, get_llm_provider
from app.services.model_ledger import record_model_call_safely
from app.services.world.gazette import compute_gazette

_SYSTEM = """\
You are the voice of The Gazette — the tier-1 season's paper of record, one edition per completed
matchday. You see exactly the latest edition the door printed: edition number and total, the
competition, the table leader and the gap to the runner-up, the loudest fixture with its score and
venue, the hot hand (the club that put the most past anyone this round), and the round's numbers —
goals, draws, clean sheets, the season average. You know nothing else about this league. Your task:

1. Speak one short paragraph on this edition — the scorecard's shape, who shifted the table, the
   loudest fixture, the hot hand, and how the goals-this-round compare to the season average.
2. Name every club, fixture, score, venue and figure exactly as the rows print them. No inventing
   clubs, scores, venues or editions.
3. The edition reports a finished matchday; it says nothing about any future fixture. Do not
   present it as a forecast.
4. Plain English, one paragraph, no headings, no bullets, no emoji.
"""

_PROMPT = """\
Season 2026/27 — what The Gazette printed for edition {edition} of {total_editions} ({competition_name}, tier-1):

Published: {published_at}
Table leader: {leader_name} · gap to runner-up: {gap} point(s)
The loudest fixture: {loudest_block}
Hot hand: {hot_hand_block}
Numbers: goals this round {goals} · draws {draws} · clean sheets {clean_sheets} · season average goals/edition {average} · fixtures played {fixture_count}

The reader wants one honest paragraph on this edition.
"""


def _fixture_block(row: dict[str, Any] | None) -> str:
    if not row:
        return "(none)"
    home = (row.get("home") or {}).get("name", "?")
    away = (row.get("away") or {}).get("name", "?")
    return (
        f"{home} {row.get('home_goals', '?')}–{row.get('away_goals', '?')} {away} · {row.get('venue', '?')} · "
        f"kickoff {row.get('kickoff', '?')}"
    )


def _hot_hand_block(row: dict[str, Any] | None) -> str:
    if not row:
        return "(nobody scored)"
    team = (row.get("team") or {}).get("name", "?")
    return f"{team} · {row.get('goals', 0)} goal(s) this round"


def compute_gazette_coach_read(db: Session) -> dict[str, Any]:
    try:
        edition = compute_gazette(db)
    except Exception as error:  # noqa: BLE001 — the door must answer, not 500
        record_model_call_safely(
            result=LlmResult(
                text="",
                provider="unknown",
                model="gazette-coach-read",
                demo_mode=True,
                error=str(error)[:300],
                latency_ms=0,
            ),
            feature="world.gazette.read",
        )
        return {"available": False, "edition": "2026/27", "provider": "unknown", "error": "gazette recompute failed"}

    if not edition.get("available"):
        return {
            "available": False,
            "edition": "2026/27",
            "provider": "unknown",
            "error": edition.get("reason", "the gazette could not be computed") if not edition.get("out_of_range") else "edition out of range",
        }

    leader = edition.get("table_leader") or {}
    leader_team = (leader.get("team") or {}) if isinstance(leader, dict) else {}
    loudest = edition.get("lead")
    numbers = edition.get("number", {})
    prompt = _PROMPT.format(
        edition=edition.get("edition", "?"),
        total_editions=edition.get("total_editions", "?"),
        competition_name=(edition.get("competition") or {}).get("name", "?"),
        published_at=edition.get("published_at", "?"),
        leader_name=leader_team.get("name", "?"),
        gap=edition.get("table_gap", 0),
        loudest_block=_fixture_block(loudest),
        hot_hand_block=_hot_hand_block(edition.get("hot_hand")),
        goals=numbers.get("goals_this_round", 0),
        draws=numbers.get("draws", 0),
        clean_sheets=numbers.get("clean_sheets", 0),
        average=numbers.get("season_average_goals", 0.0),
        fixture_count=numbers.get("fixtures", 0),
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
        record_model_call_safely(result=failure, feature="world.gazette.read")
        return {
            "available": False,
            "edition": "2026/27",
            "provider": failure.provider,
            "error": (failure.error or "unreachable gateway")[:160],
        }

    record_model_call_safely(result=result, feature="world.gazette.read")
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


__all__ = ["compute_gazette_coach_read"]
