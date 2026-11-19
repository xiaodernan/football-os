"""The Upset Register's coach-read — one honest paragraph on where the favourite's edge fell short.

The register is computed from every completed tier-1 fixture scored by combined overall
ratings — the largest gaps the underdog closed, the fortress draws at a gap of eight or more,
and the season's tally. The model receives exactly those rows: the biggest upset with its
scoreline and gap, the fortresses, the season's tally, and the five largest upsets. It speaks
one short paragraph on what the register found. It never invents a club, player or figure
beyond the snapshot, and refuses to name a fixture the door did not print.

Without a configured provider the door answers `available: false` and the register's own
arithmetic stands on the page.

Feature name for the ledger: `world.upsets.read`.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.providers import LlmResult, get_llm_provider
from app.services.knowledge.library_charter import LIBRARY_CHARTER
from app.services.model_ledger import record_model_call_safely
from app.services.world.upsets import compute_upsets

_SYSTEM = """\
You are the voice of The Upset Register — the tier-1 fixtures where the favourite's rating edge
was not enough on the day. You see exactly the rows the register computed: the biggest gap an
underdog closed, the fortress draws at a rating gap of eight or more, and the season's tally.
You know nothing else about this league. Your task:

1. Speak one short paragraph on what the register found — where the favourite's edge fell short,
   which gap closed largest, and whether the fortresses held up under an eight-rating gap.
2. Name every club, fixture, scoreline and figure exactly as the rows print them. No inventing
   clubs, no inventing fixtures, no inventing rating gaps.
3. The mean gap is a mean; the rate is a percentage of judged fixtures — do not present either
   as a prediction, a forecast, or a claim about any future match.
4. Plain English, one paragraph, no headings, no bullets, no emoji.
"""

_PROMPT = """\
Season 2026/27 — what the Upset Register counted for tier-1:

Competition: {competition_name} (tier-1), season {season}
Judged fixtures: {judged}
Upsets closed: {upset_count}  ·  Fortresses held: {fortress_count}  ·  Mean gap fallen: {mean_gap}
Upset rate: {upset_rate_pct}% of judged fixtures

The largest gap closed:
{biggest_upset_block}

The five largest upsets (ordered by gap closed, then by margin earned):
{upsets_block}

The fortresses held (level at a gap of 8.0 or more):
{fortresses_block}

The reader wants one honest paragraph on what these rows show.
"""


def _fixture_row_block(row: dict[str, Any] | None) -> str:
    if not row:
        return "  (none logged in this season)"
    home = (row.get("home") or {}).get("name", "?")
    away = (row.get("away") or {}).get("name", "?")
    favourite = row.get("favorite", "?")
    return (
        f"  {row.get('round_label', '?')} · {home} {row.get('home_goals', '?')}–{row.get('away_goals', '?')} {away}\n"
        f"  favourite: {favourite}  ·  rating gap closed: {row.get('rating_gap', '?')}"
    )


def _rows_block(rows: list[dict[str, Any]] | None, limit: int = 5) -> str:
    if not rows:
        return "  (none logged in this season)"
    lines = []
    for index, row in enumerate(rows[:limit], start=1):
        home = (row.get("home") or {}).get("name", "?")
        away = (row.get("away") or {}).get("name", "?")
        lines.append(
            f"  {index}. {row.get('round_label', '?')} · {home} {row.get('home_goals', '?')}–"
            f"{row.get('away_goals', '?')} {away} · gap {row.get('rating_gap', '?')}"
        )
    return "\n".join(lines)


def compute_upsets_coach_read(db: Session) -> dict[str, Any]:
    try:
        register = compute_upsets(db)
    except Exception as error:  # noqa: BLE001 — the door must answer, not 500
        record_model_call_safely(
            result=LlmResult(
                text="",
                provider="unknown",
                model="upsets-coach-read",
                demo_mode=True,
                error=str(error)[:300],
                latency_ms=0,
            ),
            feature="world.upsets.read",
        )
        return {"available": False, "edition": "2026/27", "provider": "unknown", "error": "upset register recompute failed"}

    if not register.get("available"):
        return {
            "available": False,
            "edition": "2026/27",
            "provider": "unknown",
            "error": register.get("reason", "the upset register could not be computed"),
        }

    prompt = _PROMPT.format(
        competition_name=register.get("competition", "?"),
        season=(register.get("season") or {}).get("label", "2026/27"),
        judged=register.get("judged", 0),
        upset_count=register.get("upset_count", 0),
        fortress_count=register.get("fortress_count", 0),
        mean_gap=register.get("mean_upset_gap", 0.0),
        upset_rate_pct=register.get("upset_rate_pct", 0.0),
        biggest_upset_block=_fixture_row_block(register.get("biggest_upset")),
        upsets_block=_rows_block(register.get("upsets"), limit=5),
        fortresses_block=_rows_block(register.get("fortresses"), limit=5),
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
        record_model_call_safely(result=failure, feature="world.upsets.read")
        return {
            "available": False,
            "edition": "2026/27",
            "provider": failure.provider,
            "error": (failure.error or "unreachable gateway")[:160],
        }

    record_model_call_safely(result=result, feature="world.upsets.read")
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


__all__ = ["compute_upsets_coach_read"]
