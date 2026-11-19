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
from app.services.knowledge.library_charter import LIBRARY_CHARTER
from app.services.model_census import compute_model_census
from app.services.model_ledger import record_model_call_safely

_SYSTEM = """\
You are the operator's read on one football product's admin console. You see two blocks and they are not interchangeable:

1. The visitor cohort block — what the audience is doing on the pages
   (views, bounce, dwell, funnels, slope).
2. The model ledger block — of the fleet's AI calls over the last 7 days:
   calls, costs, failures, demo-mode share, and the gateway-reported cache share.

Rules of the road:

1. Read the figures you are handed and name exactly three optimizations, the furthest-reaching
   first. Each must cite a number that appears in the figures or a named field of the data —
   no generalities, no invented figures, no hype.
2. At least one of your three optimizations must name the model ledger block — cache share, cost,
   failures or demo-mode share — and the line of it you acted on. Do not race straight to the cohort.
3. If the trend is flat or falling, put the audience you already hold above any new feature.
4. If the seeded flag is true, the figures are a deterministic demo cohort, not organic traffic —
   say so once, plainly, and reason about direction, not absolutes.
5. Answer in plain English, two to four short paragraphs. No headings, no bullets, no emoji.
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

The cost and health of the model layer itself, over the most recent 7 days:
{census_block}

What does the operator do next, in three moves, in light of both blocks?
"""


def _census_block(census: dict[str, Any]) -> str:
    t = census["totals"]
    cost_per_call = (t["actual_cost_usd"] / t["calls"]) if t["calls"] else 0.0
    in_thousands = t["input_tokens"] / 1000.0
    cost_per_1k_in = (t["actual_cost_usd"] / in_thousands) if in_thousands else 0.0
    demo = t["demo_mode_share"]
    low_cache = [row for row in census["by_feature"] if row["cached_share_reported"] < 0.85 and row["reported_rows"] > 0]
    low = [f"  {row['feature']}: {round(row['cached_share_reported'] * 100, 1)}% cached ({row['reported_rows']} reported row(s), {row['calls']} calls)" for row in low_cache[:5]]
    lines = [
        f"  calls over the last 7 days: {t['calls']}",
        f"  failures: {t['failures']} (failure rate {t['failure_rate']})",
        f"  demo-mode share (budget cap stands in for the model): {round(demo * 100, 2)}%",
        f"  gateway-reported cache share: {round(t['cached_share_reported'] * 100, 2)}% of reported input tokens ({t['reported_rows']} reported row(s))",
        f"  actual cost: ${t['actual_cost_usd']:.4f} (est. ${t['estimated_cost_usd']:.4f})",
        f"  cost per call: ${cost_per_call:.5f}; cost per 1k input tokens: ${cost_per_1k_in:.4f}",
        f"  median latency_ms: {t['median_latency_ms']}",
        "  lowest-cache features by reported rows:",
        *low,
    ]
    return "\n".join(lines)


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
    census = compute_model_census(db, window_days=7)
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
        census_block="\n".join(_census_block(census)),
    )

    try:
        result = provider.complete(system=LIBRARY_CHARTER + _SYSTEM, prompt=prompt, max_tokens=500, temperature=0.35)
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
