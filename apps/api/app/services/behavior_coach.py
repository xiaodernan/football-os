"""The coach reads the admin console's window — one honest ask per press, gated by the same passphrase.

The coach answers out loud only when a provider is configured (`OPENAI_API_KEY`); without one, the
door answers `available: false` and the console's rule-based reads stand alone — the product never
pretends a coach lived where there is no model. Every claim the coach makes must name a number
that came through this function: the totals, the pages with the most bounce, the slowest funnel,
the two-week trend and the recommendations the console itself printed. The coach is an adviser on
top of the arithmetic, never a source of numbers.

The coach's own calls are written to the model ledger (`record_model_call_safely`) with feature
`admin.coach.read`, so the ledger shows exactly how often it was pressed, and how many of those
calls the gateway served from its own cache.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.providers import LlmResult, get_llm_provider
from app.services.behavior import compute_behavior
from app.services.model_ledger import record_model_call_safely

_SYSTEM = """\
You are the operator's read on one football product's admin console. You see only
assembled aggregates — never a user's identity, never a raw row. Your task:

1. Read the figures you are handed and name exactly three optimizations, the furthest-reaching
   first. Each must cite a number that appears in the figures or a named field of the data —
   no generalities, no invented figures, no hype.
2. If the trend is flat or falling, put the audience you already hold above any new feature.
3. If the seeded flag is true, the figures are a deterministic demo cohort, not organic traffic —
   say so once, plainly, and reason about direction, not absolutes.
4. Answer in plain English, two to four short paragraphs. No headings, no bullets, no emoji.
"""

_PROMPT = """\
The numbers below are assembled fresh from the raw rows on this console's last {window_days} days.
Seeded cohort: {seeded}. Views: {views} across {sessions} sessions. Doors seen: {doors_seen}.
Bounce (<6s from the page view): {bounce_rate}. Median dwell: {median_dwell_ms} ms.

Page leaders and laggards (path · views · bounce · median dwell):
{pages_block}

Funnels (share of sessions continuing from A to B, in order):
{funnels_block}

Trend (least squares over daily sessions): slope {slope} per day, r² {r_squared};
projected day 1 through day 14: {projected_sessions}.

Rule-based reads the console itself printed this window:
{recs_block}

What does the operator do next, in three moves?
"""


def _pages_block(pages: list[dict[str, Any]]) -> str:
    ordered = sorted(pages, key=lambda row: int(row.get("views", 0)), reverse=True)
    top = ordered[:4]
    worst = sorted(
        (page for page in ordered if int(page.get("views", 0)) >= 20),
        key=lambda page: float(page.get("bounce_rate", 0.0)) * int(page.get("views", 0)) + 0.001,
        reverse=True,
    )[:3]
    lines = [f"  {page.get('path')} · {page.get('views')} views · bounce {round(float(page.get('bounce_rate', 0.0)), 3)} · dwell {page.get('median_dwell_ms')} ms" for page in top]
    lines.append("worst:")
    lines += [f"  {page.get('path')} · {page.get('views')} views · bounce {round(float(page.get('bounce_rate', 0.0)), 3)} · dwell {page.get('median_dwell_ms')} ms" for page in worst]
    return "\n".join(lines) if lines else "  (quiet cohort; nothing to read)"


def _funnels_block(funnels: list[dict[str, Any]]) -> str:
    return "\n".join(f"  {entry.get('id')}: {entry.get('rate')}" for entry in funnels) or "  (no rows)"


def _recs_block(recs: list[dict[str, Any]]) -> str:
    return "\n".join(f"  {rec.get('kind')}: {rec.get('path', '')} {rec.get('value')}" for rec in recs) or "  (none)"


def compute_admin_coach_read(db: Session, *, window_days: int = 90) -> dict[str, Any]:
    """Compute the admin's numbers, then ask the coach for three optimizations — or say it cannot."""
    data = compute_behavior(db, window_days=window_days)
    provider = get_llm_provider()

    pages = data.get("pages", [])
    recs = data.get("recommendations", [])
    totals = data["totals"]
    forecast = data["forecast"]
    projected = forecast.get("projected_sessions", [])

    prompt = _PROMPT.format(
        window_days=data["window_days"],
        seeded=data["source_note"]["seeded_views"] > 0,
        views=totals["views"],
        sessions=totals["sessions"],
        doors_seen=totals["unique_paths"],
        bounce_rate=totals["bounce_rate"],
        median_dwell_ms=totals["median_dwell_ms"],
        pages_block=_pages_block(pages),
        funnels_block=_funnels_block(data["funnels"]),
        slope=forecast["slope_per_day"],
        r_squared=forecast["r_squared"],
        projected_sessions=", ".join(str(v) for v in projected),
        recs_block=_recs_block(recs),
    )

    try:
        result = provider.complete(system=_SYSTEM, prompt=prompt, max_tokens=500, temperature=0.35, prompt_cache_key="admin.coach.read")
    except Exception as error:  # noqa: BLE001 — the provider gateway itself is the risk; the door must stay up.
        failure = LlmResult(
            text="",
            provider=getattr(provider, "name", "unknown"),
            model="unreachable",
            demo_mode=True,
            error=str(error)[:300],
            latency_ms=0,
        )
        record_model_call_safely(result=failure, feature="admin.coach.read")
        return {
            "available": False,
            "window_days": data["window_days"],
            "provider": failure.provider,
            "error": (failure.error or "unreachable gateway")[:160],
        }

    record_model_call_safely(result=result, feature="admin.coach.read")
    if result.error:
        return {
            "available": False,
            "window_days": data["window_days"],
            "provider": result.provider,
            "model": result.model,
            "error": (result.error or "provider error")[:160],
        }
    return {
        "available": True,
        "window_days": data["window_days"],
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


__all__ = ["compute_admin_coach_read"]
