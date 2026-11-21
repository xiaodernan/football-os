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

import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.providers import LlmResult, get_llm_provider
from app.services.behavior import compute_behavior
from app.services.knowledge.library_charter import LIBRARY_CHARTER
from app.services.model_census import compute_model_census
from app.services.model_ledger import record_model_call_safely

# Optional LangGraph — the same graph walks the edge table when the dependency is absent, the way
# sim_report_graph and deep_read do. StateGraph is the point: the coach's assembly is inspectable.
_StateGraph: Any = None
_LG_END: Any = "__end__"
try:
    from langgraph.graph import END as _LG_END_
    from langgraph.graph import StateGraph as _StateGraph_

    _StateGraph = _StateGraph_
    _LG_END = _LG_END_
except ImportError:  # pragma: no cover - depends on the deployment's optional extras
    _StateGraph = None

MAX_NODE_VISITS = 6
# A decimal figure the model quotes must be one the console actually printed (bounce rate, slope,
# cache share, cost per call). Integers like "three moves" are prose, not statistics.
_NUMBER_RE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)")


@dataclass
class CoachState:
    """Shared state for the admin-coach walk. Trace and verified flags are append-only."""

    window_days: int
    data: dict[str, Any] = field(default_factory=dict)
    census: dict[str, Any] = field(default_factory=dict)
    prompt: str = ""
    draft: str = ""
    answer: str = ""
    allowed_figures: set[str] = field(default_factory=set)
    verified: bool = True
    repairs: int = 0
    trace: list[dict[str, Any]] = field(default_factory=list)
    # Model/telemetry result, kept from the single phrasing call.
    result: LlmResult | None = None
    error: str = ""

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


def _allowed_figures(state: CoachState) -> set[str]:
    """Every decimal the model may quote, drawn from the two blocks it was handed."""
    data, census = state.data, state.census
    figures: set[str] = set()
    totals = data.get("totals", {})
    for key in ("bounce_rate", "median_dwell_ms", "sessions", "views", "unique_paths"):
        value = totals.get(key)
        if value is not None:
            figures.add(f"{value:g}" if isinstance(value, float) else str(value))
    forecast = data.get("forecast", {})
    for key in ("slope_per_day", "r_squared"):
        value = forecast.get(key)
        if value is not None:
            figures.add(f"{value:g}" if isinstance(value, float) else str(value))
    for value in forecast.get("projected_sessions", []):
        figures.add(f"{value:g}" if isinstance(value, float) else str(value))
    for entry in data.get("funnels", []):
        value = entry.get("rate")
        if value is not None:
            figures.add(f"{float(value):.4f}".rstrip("0").rstrip("."))
    ct = census.get("totals", {})
    for key in ("failure_rate", "demo_mode_share", "cached_share_reported", "actual_cost_usd", "estimated_cost_usd", "median_latency_ms", "calls", "failures"):
        value = ct.get(key)
        if value is not None:
            figures.add(f"{value:g}" if isinstance(value, float) else str(value))
    # The console prints percentages rounded to 2 decimals (cache share, demo share) and 1 decimal
    # (low-cache features). Those are honest renderings of the same stored figures.
    for key in ("demo_mode_share", "cached_share_reported", "failure_rate"):
        value = ct.get(key)
        if isinstance(value, int | float):
            figures.add(f"{round(float(value) * 100, 2):g}")
            figures.add(f"{round(float(value) * 100, 1):g}")
    for row in census.get("by_feature", []):
        value = row.get("cached_share_reported")
        if isinstance(value, int | float):
            figures.add(f"{round(float(value) * 100, 1):g}")
    return figures


def _node_gather(state: CoachState, db: Session | None) -> CoachState:
    started = time.perf_counter()
    state.data = compute_behavior(db, window_days=state.window_days)  # type: ignore[arg-type]
    state.census = compute_model_census(db, window_days=7)  # type: ignore[arg-type]
    state.allowed_figures = _allowed_figures(state)
    data = state.data
    totals, forecast = data["totals"], data["forecast"]
    state.prompt = _PROMPT.format(
        window_days=data["window_days"],
        seeded=data["source_note"]["seeded_views"] > 0,
        views=totals["views"],
        sessions=totals["sessions"],
        doors_seen=totals["unique_paths"],
        bounce_rate=totals["bounce_rate"],
        median_dwell_ms=totals["median_dwell_ms"],
        pages_block=_pages_block(data.get("pages", [])),
        funnels_block=_funnels_block(data.get("funnels", [])),
        slope=forecast["slope_per_day"],
        r_squared=forecast["r_squared"],
        projected_sessions=", ".join(str(v) for v in forecast.get("projected_sessions", [])),
        recs_block=_recs_block(data.get("recommendations", [])),
        census_block="\n".join(_census_block(state.census)),
    )
    state.trace.append({"node": "gather", "kind": "rule", "latency_ms": int((time.perf_counter() - started) * 1000)})
    return state


def _node_draft(state: CoachState) -> CoachState:
    started = time.perf_counter()
    provider = get_llm_provider()
    try:
        result = provider.complete(system=LIBRARY_CHARTER + _SYSTEM, prompt=state.prompt, max_tokens=500, temperature=0.35)
    except Exception as error:  # noqa: BLE001 — the gateway is the risk; the door must stay up.
        result = LlmResult(
            text="", provider=getattr(provider, "name", "unknown"), model="unreachable",
            demo_mode=True, error=str(error)[:300], latency_ms=0,
        )
    record_model_call_safely(result=result, feature="admin.coach.read")
    state.result = result
    state.error = (result.error or "")[:160]
    state.answer = (result.text or "").strip()
    state.trace.append({
        "node": "draft", "kind": "model", "provider": result.provider, "model": result.model,
        "latency_ms": result.latency_ms or int((time.perf_counter() - started) * 1000),
        "error": (result.error or "")[:120],
    })
    return state


def _node_verify(state: CoachState) -> CoachState:
    started = time.perf_counter()
    quoted = {m.group(1) for m in _NUMBER_RE.finditer(state.answer)}
    bad = sorted(q for q in quoted if "." in q and q not in state.allowed_figures)
    state.verified = not bad
    state.trace.append({"node": "verify", "kind": "rule", "ok": state.verified, "unmatched": bad})
    if not state.answer:
        state.error = state.error or "empty answer"
    state.trace.append({"node": "verify.summary", "kind": "rule", "ok": state.verified, "latency_ms": int((time.perf_counter() - started) * 1000)})
    return state


def _node_repair(state: CoachState) -> CoachState:
    """Drop sentences quoting a figure the console never printed; keep the honest ones."""
    started = time.perf_counter()
    sentences = [p for p in re.split(r"(?<=[.!?。！？])\s+", state.answer.strip()) if p]
    kept = [p for p in sentences if all(m.group(1) in state.allowed_figures for m in _NUMBER_RE.finditer(p) if "." in m.group(1))]
    state.answer = " ".join(kept).strip() or "I cannot support an optimization from the figures this console printed this window."
    state.verified = True
    state.repairs += 1
    state.trace.append({"node": "repair", "kind": "rule", "dropped": len(sentences) - len(kept), "latency_ms": int((time.perf_counter() - started) * 1000)})
    return state


NODES: dict[str, Callable[[CoachState], CoachState]] = {
    "gather": lambda s: s,  # bound with db in the walk
    "draft": _node_draft,
    "verify": _node_verify,
    "repair": _node_repair,
}
EDGES: list[tuple[str, str]] = [
    ("gather", "draft"),
    ("draft", "verify"),
    ("verify", _LG_END),  # default; conditional overrides on drift
    ("repair", _LG_END),
]


def _verify_route(state: CoachState) -> str:
    return "repair" if (state.answer and not state.verified) else "assemble"


def _compile_graph(db: Session | None) -> Any | None:
    if _StateGraph is None:
        return None
    builder = _StateGraph(CoachState)
    for name, fn in NODES.items():
        node = (lambda s: _node_gather(s, db)) if name == "gather" else fn
        node.__name__ = name
        builder.add_node(name, node)
    builder.set_entry_point("gather")
    for source, target in EDGES:
        if source == "verify":
            continue
        if target == _LG_END:
            builder.set_finish_point(source)
        else:
            builder.add_edge(source, target)
    builder.add_conditional_edges("verify", _verify_route, {"repair": "repair", "assemble": _LG_END})
    return builder.compile()


def compute_admin_coach_read(db: Session, *, window_days: int = 90) -> dict[str, Any]:
    """Walk the coach's StateGraph: gather → draft → verify → (repair) → the console's answer."""
    state = CoachState(window_days=window_days)
    graph = _compile_graph(db)
    if graph is not None:
        try:
            out = graph.invoke(state)
            if isinstance(out, CoachState):
                state = out
            elif isinstance(out, dict):
                state = CoachState(**out)
        except Exception as error:  # noqa: BLE001 — fall back to the edge-table walk, same contract.
            state = CoachState(window_days=window_days, trace=[{"node": "langgraph", "kind": "rule", "fallback": True, "error": str(error)[:120]}])
    else:
        state = _node_gather(state, db)
        node = "gather"
        visited = 0
        while visited < MAX_NODE_VISITS:
            visited += 1
            if node == _LG_END:
                break
            if node == "gather":
                pass  # already gathered
            elif node in NODES:
                state = NODES[node](state)
            if node == "verify":
                node = _verify_route(state)
                if node == "assemble":
                    break  # assemble routes straight to END
                continue
            node = next((t for s, t in EDGES if s == node), _LG_END)

    result = state.result
    if result is None or result.error:
        return {
            "available": False,
            "window_days": state.data.get("window_days", window_days),
            "provider": result.provider if result else "unknown",
            "model": result.model if result else "unknown",
            "error": (state.error or "unreachable gateway")[:160],
            "trace": state.trace,
        }
    return {
        "available": True,
        "window_days": state.data.get("window_days", window_days),
        "provider": result.provider,
        "model": result.model,
        "demo_mode": result.demo_mode,
        "input_tokens": result.input_tokens,
        "cached_input_tokens": result.cached_input_tokens,
        "cache_reported": result.cache_reported,
        "output_tokens": result.output_tokens,
        "latency_ms": result.latency_ms,
        "answer": state.answer,
        "verified": state.verified,
        "repairs": state.repairs,
        "trace": state.trace,
    }


__all__ = ["CoachState", "NODES", "EDGES", "compute_admin_coach_read"]
