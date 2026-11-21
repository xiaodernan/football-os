"""The Noise Dossier's coach-read — one honest paragraph on the caller the seed defeats.

The dossier is computed from the tier-1 fixtures and each side's combined overall of its eleven
strongest. The model receives exactly the run: how many fixture-calls the rating-based caller got
right, the accuracy against the 33.33% chance line, the draws it called and how many landed, the
best streak, and the five largest gaps it misread. It speaks one short paragraph on what the
noise means. It never invents a club, fixture or figure beyond the snapshot, and never
presents the caller as predictive of any future match.

Without a configured provider the door answers `available: false` and the dossier's own
arithmetic stands on the page.

Feature name for the ledger: `world.noise.read`.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.providers import LlmResult, get_llm_provider
from app.services.model_ledger import record_model_call_safely
from app.services.verified_phrasing import phrase_verified_complete as _verified_complete
from app.services.world.noise import compute_noise

_SYSTEM = """\
You are the voice of The Noise Dossier — the ledger of how often the rating-based caller was
right about the tier-1 fixtures it did not see when they were scored. You see exactly the
run: the judged count, the correct and wrong calls, the accuracy against the 33.33% chance
line, the draw calls and how many landed, the best streak of correct calls, and the five
largest wrong calls with their scorelines and rating gaps. You know nothing else about this
league. Your task:

1. Speak one short paragraph on what the caller's run showed — where the seed defeated the
   arithmetic, how far above or below the chance line the run landed, and the shape of the
   five largest wrong calls.
2. Name every club, fixture, scoreline and figure exactly as the rows print them. No
   inventing clubs, no inventing fixtures, no inventing gaps.
3. The accuracy is a measurement of one seeded season; it is not a forecast, a betting
   edge, or a claim about any future fixture. Do not present it as one.
4. Plain English, one paragraph, no headings, no bullets, no emoji.
"""

_PROMPT = """\
Season 2026/27 — what the Noise Dossier measured for tier-1:

Competition: {competition_name} (tier-1), season {season}
Judged fixtures: {judged}  ·  Correct calls: {correct}  ·  Wrong calls: {wrong}
Accuracy: {accuracy_pct}%  ·  Chance line: {chance_pct}%  ·  Draw window: ±{draw_window}
Draw calls: {draw_calls}  ·  Draws that landed: {draw_hits}  ·  Draw hit rate: {draw_hit_pct}%
Longest streak of correct calls: {best_streak}

The five largest wrong calls (ordered by the rating gap the caller misread):
{upsets_block}

The reader wants one honest paragraph on what this run says about the seed's noise.
"""


def _upsets_block(rows: list[dict[str, Any]] | None) -> str:
    if not rows:
        return "  (none logged — every call landed in this season)"
    lines = []
    for index, row in enumerate(rows[:5], start=1):
        home = (row.get("home") or {}).get("name", "?")
        away = (row.get("away") or {}).get("name", "?")
        lines.append(
            f"  {index}. {home} {row.get('home_goals', '?')}–{row.get('away_goals', '?')} {away} "
            f"· called {row.get('called', '?')}, actual {row.get('actual', '?')} · gap {row.get('rating_gap', '?')}"
        )
    return "\n".join(lines)


def compute_noise_coach_read(db: Session) -> dict[str, Any]:
    try:
        dossier = compute_noise(db)
    except Exception as error:  # noqa: BLE001 — the door must answer, not 500
        record_model_call_safely(
            result=LlmResult(
                text="",
                provider="unknown",
                model="noise-coach-read",
                demo_mode=True,
                error=str(error)[:300],
                latency_ms=0,
            ),
            feature="world.noise.read",
        )
        return {"available": False, "edition": "2026/27", "provider": "unknown", "error": "noise dossier recompute failed"}

    if not dossier.get("available"):
        return {
            "available": False,
            "edition": "2026/27",
            "provider": "unknown",
            "error": dossier.get("reason", "the noise dossier could not be computed"),
        }

    prompt = _PROMPT.format(
        competition_name=dossier.get("competition", "?"),
        season=(dossier.get("season") or {}).get("label", "2026/27"),
        judged=dossier.get("judged", 0),
        correct=dossier.get("correct", 0),
        wrong=dossier.get("wrong", 0),
        accuracy_pct=dossier.get("accuracy_pct", 0.0),
        chance_pct=dossier.get("chance_pct", 33.33),
        draw_window=dossier.get("draw_window", 4.0),
        draw_calls=dossier.get("draw_calls", 0),
        draw_hits=dossier.get("draw_hits", 0),
        draw_hit_pct=dossier.get("draw_hit_pct", 0.0),
        best_streak=dossier.get("best_streak", 0),
        upsets_block=_upsets_block(dossier.get("upsets")),
    )

    provider = get_llm_provider()
    try:
        result = _verified_complete(provider=provider, system=_SYSTEM, prompt=prompt, feature="world.noise.read", max_tokens=320, temperature=0.3)
    except Exception as error:  # noqa: BLE001
        failure = LlmResult(
            text="",
            provider=getattr(provider, "name", "unknown"),
            model="unreachable",
            demo_mode=True,
            error=str(error)[:300],
            latency_ms=0,
        )
        record_model_call_safely(result=failure, feature="world.noise.read")
        return {
            "available": False,
            "edition": "2026/27",
            "provider": failure.provider,
            "error": (failure.error or "unreachable gateway")[:160],
        }

    record_model_call_safely(result=result, feature="world.noise.read")
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


__all__ = ["compute_noise_coach_read"]
