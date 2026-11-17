"""The Honours Spine's coach-read — one honest paragraph on the lineage of finals this product carries.

The honours door prints every tournament this product holds (openfootball worldcup.json + euro.json,
CC-BY 4.0): the final of each, the champion lines, the totals. The model receives exactly those
rows — 24 finals, the repeat champions, the widest wins — and speaks one short paragraph on the
lineage. It never invents a final, a champion, a score, a venue or a year beyond the committed
snapshots, and it makes no claim about tournaments the door does not carry.

Without a configured provider the door answers `available: false` and the honours stand alone on
the page.

Feature name for the ledger: `world.honours.read`.
"""

from __future__ import annotations

from typing import Any

from app.providers import LlmResult, get_llm_provider
from app.services.model_ledger import record_model_call_safely
from app.services.world.honours import compute_honours

_SYSTEM = """\
You are the voice of The Roll of Honours — the lineage of finals this product carries from the
committed openfootball snapshots (worldcup.json + euro.json, CC-BY 4.0). You see exactly the
rows the door printed: each tournament's final, the two nations involved, the scores (regular
time, extra time, penalties where they happened), the venue, the widest win in the tournament,
and the repeat-champion lines. You know nothing else about football. Your task:

1. Speak one short paragraph on the lineage — which nations repeat in the champion lines, which
   tournaments ended in extra time or penalties, and where the door's own biggest wins landed.
2. Name every tournament, year, nation, champion, score, venue and figure exactly as the rows
   print them. No inventing nations, finals, scores or venues — the snapshots are the world the
   door speaks for, and nothing else is known.
3. The counts are counts over these 24 finals only; they are not a ranking of nations, and no
   figure you give may extend beyond the rows you were handed.
4. Plain English, one paragraph, no headings, no bullets, no emoji.
"""

_PROMPT = """\
Season 2026/27 — what The Roll of Honours printed:

Tournaments carried: {entries_count}  ·  Total matches: {matches}  ·  Goals on field: {goals}

Finals (registry order, newest first):
{entries_block}

Repeat champions (by wins, then name):
{champion_lines_block}

The reader wants one honest paragraph on the lineage of these finals.
"""


def _fmt_entry(entry: dict[str, Any]) -> str:
    pens = f" · decided on penalties {'-'.join(str(s) for s in entry.get('score_penalties', []))}" if entry.get("has_penalties") else ""
    et = f" (aet {'-'.join(str(s) for s in entry.get('score_extra_time', []))})" if entry.get("went_extra_time") else ""
    score = entry.get("score_regular", ["?", "?"])
    return (
        f"  {entry.get('tournament')} ({entry.get('kind')}) · {entry.get('host', '?')} · "
        f"{entry.get('champion')} def. {entry.get('runner_up')} {score[0]}–{score[1]}{et}{pens} · "
        f"{entry.get('venue', '?')} · biggest win: {(entry.get('biggest_win') or {}).get('match', '?')} "
        f"({entry.get('goals_scored', '?')} goals across the tournament)"
    )


def _fmt_champion_line(line: dict[str, Any]) -> str:
    kinds = "+".join(line.get("kinds", []))
    years = ", ".join(line.get("years", []))
    return f"  {line.get('champion', '?')} — {line.get('wins', 0)} ({kinds}): {years}"


def compute_honours_coach_read() -> dict[str, Any]:
    try:
        honours = compute_honours()
    except Exception as error:  # noqa: BLE001 — the door must answer, not 500
        record_model_call_safely(
            result=LlmResult(
                text="",
                provider="unknown",
                model="honours-coach-read",
                demo_mode=True,
                error=str(error)[:300],
                latency_ms=0,
            ),
            feature="world.honours.read",
        )
        return {"available": False, "edition": "2026/27", "provider": "unknown", "error": "honours recompute failed"}

    if not honours.get("available"):
        return {
            "available": False,
            "edition": "2026/27",
            "provider": "unknown",
            "error": honours.get("reason", "the honours could not be computed"),
        }

    entries = honours.get("entries", [])
    champion_lines = honours.get("champion_lines", [])
    totals = honours.get("totals", {})
    prompt = _PROMPT.format(
        entries_count=totals.get("entries", 0),
        matches=totals.get("matches", 0),
        goals=totals.get("goals_on_field", 0),
        entries_block="\n".join(_fmt_entry(entry) for entry in entries) if entries else "  (none carried)",
        champion_lines_block="\n".join(_fmt_champion_line(line) for line in champion_lines) if champion_lines else "  (none)",
    )

    provider = get_llm_provider()
    try:
        result = provider.complete(system=_SYSTEM, prompt=prompt, max_tokens=380, temperature=0.3)
    except Exception as error:  # noqa: BLE001
        failure = LlmResult(
            text="",
            provider=getattr(provider, "name", "unknown"),
            model="unreachable",
            demo_mode=True,
            error=str(error)[:300],
            latency_ms=0,
        )
        record_model_call_safely(result=failure, feature="world.honours.read")
        return {
            "available": False,
            "edition": "2026/27",
            "provider": failure.provider,
            "error": (failure.error or "unreachable gateway")[:160],
        }

    record_model_call_safely(result=result, feature="world.honours.read")
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


__all__ = ["compute_honours_coach_read"]
