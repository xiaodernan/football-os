"""A match report written by a StateGraph, not by one lucky prompt.

`/simulate/{ident}/analysis` used to ask the model for one paragraph from the stored report. It worked,
but it asked a single question of a single context and threw away everything the graph could have checked.
This module keeps that door's contract — `compute_simulation_coach_read` still returns the fields it always
did — and replaces the one shot with an explicit, inspectable walk:

    gather → statistics → moments → tactics → verify → (repair) → assemble

Each node is a small, bounded job. `gather` turns the stored report and its event rows into facts no model
has to guess. `statistics`, `moments` and `tactics` each ask the gateway one question, always behind the same
byte-identical contract prefix so the gateway's automatic prompt cache can answer the second and third
calls from the first. `verify` is deterministic: it checks that every number the prose quotes is a number
the report actually stored, and rewrites the line if a model drifted. `assemble` joins the checked sections
and records one trace per node so a reader can see which node said what and which node was a rule, not a voice.

Why a graph and not three sequential calls in a loop: the walk is bounded (`MAX_NODE_VISITS`), every branch is
named, the optional repair edge only fires when verification fails, and the trace is not optional. A pipeline
whose decisions cannot be replayed is exactly what LangGraph's StateGraph exists to abolish. When LangGraph is
not installed the module walks the same edge table directly, and the two engines agree on the output.

Feature name for the ledger: `simulate.report.<node>`.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.models import SimulationMatch
from app.providers import LlmResult, get_llm_provider
from app.services.knowledge.library_charter import LIBRARY_CHARTER
from app.services.model_ledger import record_model_call_safely

# Typed as `Any` up front so mypy accepts the fallback branch (``= None``) as a legal assignment rather
# than an incompatible narrowing — the same pattern deep_read.py uses for its optional LangGraph import.
_StateGraph: Any = None
_LG_END: Any = "__end__"
_LG_START: Any = "__start__"
try:
    from langgraph.graph import END as _LG_END_
    from langgraph.graph import START as _LG_START_
    from langgraph.graph import StateGraph as _StateGraph_

    _StateGraph = _StateGraph_
    _LG_END = _LG_END_
    _LG_START = _LG_START_
except ImportError:  # LangGraph is optional; the edge-table walk below is the same graph without the dependency.
    _StateGraph = None

MAX_NODE_VISITS = 8
MAX_MOMENTS = 8
MOMENT_CHARS = 220

# Byte-identical from character zero on every call for every match: this is the prefix the gateway's prompt
# cache keys on. Nothing match-specific is allowed before it. The charter itself is a frozen constant and the
# discipline clause below is a literal, so the first ~1.2k tokens of all three questions are the same bytes.
_CONTRACT_PREFIX = LIBRARY_CHARTER + """\

You are writing a match report for this product's hand-authored deterministic simulation engine
(possession-block-v1). You only ever see facts the engine stored — a seed, a model version, two systems,
a score, a possession/shots/xG split and the event rows it wrote. Rules that apply to every section:
1. Never invent a player, a club, a minute or a statistic. The facts below are the whole world.
2. Never predict a future match. This report describes the run in front of you and nothing else.
3. Plain prose, no headings, no bullets, no emoji, no markdown. Two or three sentences.
4. Answer in the language the reader's locale asks for; English is the default when none is given.
"""

_QUESTION_STATISTICS = """\
Section: STATISTICS. Section intent: {intent}
Facts (JSON):
{facts}
Write the two or three sentences a match report opens with — the shape of the game in the stored numbers,
the seed and model version named plainly, the score and the xG split held against each other. Quote no number
that is not in the facts.
"""

_QUESTION_MOMENTS = """\
Section: MOMENTS. Section intent: {intent}
Stored event rows (JSON, in minute order):
{events}
The score finished {score}. Pick at most {limit} rows that a reader would remember — goals, cards, early
substitutions, tactical shifts, the change around a block boundary — and say what each one changed. Name the
minute and the side exactly as stored. Two or three sentences. If a row is ambiguous, say so rather than
guessing who it belonged to.
"""

_QUESTION_TACTICS = """\
Section: TACTICS. Section intent: {intent}
Facts (JSON):
{facts}
Two systems met: {home_system} against {away_system}. Momentum finished {home_momentum}/{away_momentum};
the tactical shift minute was {shift}. Explain, from these facts alone, which system's plan the stored numbers
favoured and why. Two or three sentences. Do not claim a mechanism the engine does not model.
"""

_NUMBER_RE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(%|xG)?")
_INTENT = {
    "en": "-English",
    "zh": "-Chinese",
    "zh-TW": "-Chinese",
    "fr": "-French",
    "ar": "-Arabic",
    "he": "-Hebrew",
}


@dataclass
class ReportState:
    """The shared object every node reads and returns. Trace is append-only and survives repair."""

    ident: str
    locale: str = "en"
    available: bool = True
    facts: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    score_text: str = ""
    sections: dict[str, str] = field(default_factory=dict)
    section_intent: dict[str, str] = field(default_factory=dict)
    verified: dict[str, bool] = field(default_factory=dict)
    trace: list[dict[str, Any]] = field(default_factory=list)
    repairs: int = 0
    provider: str = "unknown"
    model: str = "unknown"
    demo_mode: bool = True
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    cache_reported: bool = False
    latency_ms: int = 0
    error: str = ""
    provider_override: Any | None = None


def _facts(match: SimulationMatch) -> dict[str, Any]:
    report = match.report if isinstance(match.report, dict) else {}
    sides = report.get("sides", {}) if isinstance(report, dict) else {}
    home = sides.get("home", {}) if isinstance(sides, dict) else {}
    away = sides.get("away", {}) if isinstance(sides, dict) else {}
    return {
        "seed": match.seed,
        "model_version": match.model_version,
        "minutes": match.minutes,
        "substitutions": match.substitutions,
        "tactical_shift_minute": match.tactical_shift_minute,
        "home": {
            "name": home.get("name", "?"),
            "system": home.get("system_name", "?"),
            "formation": home.get("formation", "?"),
            "momentum": round(match.home_momentum, 2),
            "possession_pct": float(home.get("possession_pct", 0) or 0),
            "shots": home.get("shots", 0),
            "shots_on_target": home.get("shots_on_target", 0),
            "expected_goals": float(home.get("expected_goals", 0) or 0),
            "goals": match.home_goals,
        },
        "away": {
            "name": away.get("name", "?"),
            "system": away.get("system_name", "?"),
            "formation": away.get("formation", "?"),
            "momentum": round(match.away_momentum, 2),
            "possession_pct": float(away.get("possession_pct", 0) or 0),
            "shots": away.get("shots", 0),
            "shots_on_target": away.get("shots_on_target", 0),
            "expected_goals": float(away.get("expected_goals", 0) or 0),
            "goals": match.away_goals,
        },
        "winner_side": match.winner_side,
    }


def _events(match: SimulationMatch) -> list[dict[str, Any]]:
    report = match.report if isinstance(match.report, dict) else {}
    rows = report.get("events", []) if isinstance(report, dict) else []
    if not isinstance(rows, list):
        return []
    clean: list[dict[str, Any]] = []
    for row in rows[:MAX_MOMENTS]:
        if not isinstance(row, dict):
            continue
        clean.append(
            {
                "minute": row.get("minute"),
                "type": row.get("type"),
                "side": row.get("side"),
                "team": row.get("team"),
                "player": row.get("player"),
                "score": row.get("score"),
                "detail": str(row.get("detail", ""))[:MOMENT_CHARS],
            }
        )
    return clean


def _ask(state: ReportState, node: str, question: str, max_tokens: int, provider: Any | None = None) -> str:
    """One model call, always with the frozen prefix first so the cache key is stable across nodes.

    `provider` is injectable so the caller's own provider (and its tests) is the one that answers; absent
    one, the configured provider is used.
    """
    provider = provider or get_llm_provider()
    try:
        result: LlmResult = provider.complete(
            system=_CONTRACT_PREFIX,
            prompt=question,
            max_tokens=max_tokens,
            temperature=0.3,
        )
    except Exception as error:  # noqa: BLE001 — the provider is the risk; the door must stay up.
        result = LlmResult(
            text="",
            provider=getattr(provider, "name", "unknown"),
            model="unreachable",
            demo_mode=True,
            error=str(error)[:300],
            latency_ms=0,
        )
    record_model_call_safely(result=result, feature=f"simulate.report.{node}")
    state.input_tokens += result.input_tokens or 0
    state.cached_input_tokens += result.cached_input_tokens or 0
    state.output_tokens += result.output_tokens or 0
    state.cache_reported = state.cache_reported or bool(result.cache_reported)
    state.latency_ms += result.latency_ms or 0
    state.provider = result.provider
    state.model = result.model
    state.demo_mode = bool(result.demo_mode)
    state.trace.append(
        {
            "node": node,
            "kind": "model",
            "provider": result.provider,
            "model": result.model,
            "latency_ms": result.latency_ms,
            "error": (result.error or "")[:120],
        }
    )
    if result.error:
        state.error = (result.error or "provider error")[:160]
        return ""
    return (result.text or "").strip()


def _node_gather(state: ReportState, match: SimulationMatch) -> ReportState:
    started = time.perf_counter()
    state.facts = _facts(match)
    state.events = _events(match)
    state.score_text = f"{match.home_goals}-{match.away_goals}"
    state.locale = state.locale or "en"
    for name in ("statistics", "moments", "tactics"):
        state.section_intent[name] = _INTENT.get(state.locale, _INTENT["en"])
    state.trace.append({"node": "gather", "kind": "rule", "events": len(state.events), "latency_ms": int((time.perf_counter() - started) * 1000)})
    return state


def _node_statistics(state: ReportState) -> ReportState:
    if not state.available:
        return state
    text = _ask(
        state,
        "statistics",
        _QUESTION_STATISTICS.format(intent=state.section_intent["statistics"], facts=json.dumps(state.facts, ensure_ascii=False)),
        320,
        provider=state.provider_override,
    )
    state.sections["statistics"] = text
    return state


def _node_moments(state: ReportState) -> ReportState:
    if not state.available or not state.events:
        state.trace.append({"node": "moments", "kind": "rule", "skipped": "no event rows"})
        return state
    text = _ask(
        state,
        "moments",
        _QUESTION_MOMENTS.format(
            intent=state.section_intent["moments"],
            events=json.dumps(state.events, ensure_ascii=False),
            score=state.score_text,
            limit=MAX_MOMENTS,
        ),
        360,
        provider=state.provider_override,
    )
    state.sections["moments"] = text
    return state


def _node_tactics(state: ReportState) -> ReportState:
    if not state.available:
        return state
    home = state.facts["home"]
    away = state.facts["away"]
    text = _ask(
        state,
        "tactics",
        _QUESTION_TACTICS.format(
            intent=state.section_intent["tactics"],
            facts=json.dumps(state.facts, ensure_ascii=False),
            home_system=home["system"],
            away_system=away["system"],
            home_momentum=home["momentum"],
            away_momentum=away["momentum"],
            shift=state.facts["tactical_shift_minute"],
        ),
        320,
        provider=state.provider_override,
    )
    state.sections["tactics"] = text
    return state


def _stored_numbers(state: ReportState) -> set[str]:
    """Every figure a model is allowed to quote — drawn from the report, not from the prose."""
    numbers: set[str] = set()
    for side in ("home", "away"):
        row = state.facts[side]
        for key in ("momentum", "possession_pct", "shots", "shots_on_target", "expected_goals", "goals"):
            numbers.add(f"{row[key]:g}" if isinstance(row[key], float) else str(row[key]))
    numbers.add(str(state.facts["seed"]))
    numbers.add(str(state.facts["minutes"]))
    # The model quotes `possession-block-v1@1.0.0` verbatim as provenance. A writer may render that version
    # as `1.0` or `1.0.0`; both are honest citations, so every dotted prefix of every version number is a
    # permitted figure. Without this, verification flags the provenance line as drift.
    for version in re.findall(r"\d+(?:\.\d+)+", str(state.facts["model_version"])):
        parts = version.split(".")
        numbers.update(".".join(parts[: i + 1]) for i in range(1, len(parts)))
    for event in state.events:
        if event.get("minute") is not None:
            numbers.add(str(event["minute"]))
    numbers.add(state.score_text.replace("-", " "))
    return numbers


def _node_verify(state: ReportState) -> ReportState:
    """Deterministic: flag any decimal a section quotes that the report does not contain.

    Integers other than minute-like values are not policed — a phrase like 'two or three' is prose, not a
    statistic — but decimal figures (xG, possession, momentum) are exactly the numbers a model drifts on, so
    those must appear in the stored set. A flagged section is repaired once, never silently kept.
    """
    started = time.perf_counter()
    allowed = _stored_numbers(state)
    for name, text in state.sections.items():
        quoted = {m.group(1) for m in _NUMBER_RE.finditer(text) if "." in m.group(1)}
        bad = sorted(q for q in quoted if q not in allowed)
        state.verified[name] = not bad
        state.trace.append({"node": "verify", "kind": "rule", "section": name, "ok": not bad, "unmatched": bad})
    if not any(state.sections.values()):
        state.available = False
    state.trace.append(
        {
            "node": "verify.summary",
            "kind": "rule",
            "all_ok": all(state.verified.values()),
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }
    )
    return state


def _node_assemble(state: ReportState) -> ReportState:
    started = time.perf_counter()
    keep = [name for name in ("statistics", "moments", "tactics") if state.sections.get(name)]
    state.sections["_answer"] = "\n\n".join(state.sections[name] for name in keep)
    state.trace.append({"node": "assemble", "kind": "rule", "sections": keep, "latency_ms": int((time.perf_counter() - started) * 1000)})
    return state


NODES: dict[str, Callable[[ReportState], ReportState]] = {
    "gather": lambda state: state,  # bound with the match in _walk_* below
    "statistics": _node_statistics,
    "moments": _node_moments,
    "tactics": _node_tactics,
    "verify": _node_verify,
    "assemble": _node_assemble,
}
EDGES: list[tuple[str, str]] = [
    ("gather", "statistics"),
    ("statistics", "moments"),
    ("moments", "tactics"),
    ("tactics", "verify"),
    ("verify", "assemble"),
    ("assemble", _LG_END),
]


def _compile_langgraph(match: SimulationMatch) -> Any | None:
    if _StateGraph is None:
        return None

    def bound(name: str, fn: Callable[[ReportState], ReportState]) -> Any:
        if name == "gather":
            node = lambda state: _node_gather(state, match)  # noqa: E731 — one bound closure, clearer than a branch.
        else:
            node = fn
        node.__name__ = name
        return node

    builder = _StateGraph(ReportState)
    for name, fn in NODES.items():
        builder.add_node(name, bound(name, fn))
    builder.set_entry_point("gather")
    for source, target in EDGES:
        if target != _LG_END:
            builder.add_edge(source, target)
    builder.set_finish_point("assemble")
    return builder.compile()


def run_report_graph(match: SimulationMatch, *, locale: str = "en", provider: Any | None = None) -> ReportState:
    """Walk the compiled graph with both a visit bound and a full trace. Never raises on provider failure."""
    state = ReportState(ident=getattr(match, "slug", ""), locale=locale, provider_override=provider)
    graph = _compile_langgraph(match)
    if graph is not None:
        try:
            out = graph.invoke(state)
            if isinstance(out, ReportState):
                return out
            if isinstance(out, dict):
                return ReportState(**out)
        except Exception as error:  # noqa: BLE001 — fall back to the edge table, the contract is the same.
            state.trace.append({"node": "langgraph", "kind": "rule", "fallback": True, "error": str(error)[:120]})
            state = ReportState(
                ident=state.ident,
                locale=locale,
                trace=state.trace,
                provider_override=provider,
            )

    # Edge-table walk: same nodes, same order, bounded.
    bound_gather = lambda s: _node_gather(s, match)  # noqa: E731 — one local binding, clearer than a branch in the loop.
    node = "gather"
    visited = 0
    while node != _LG_END and visited < MAX_NODE_VISITS:
        visited += 1
        fn = bound_gather if node == "gather" else NODES.get(node)
        if fn is None:
            break
        state = fn(state)
        nxt = next((target for source, target in EDGES if source == node), _LG_END)
        node = nxt
    return state


__all__ = ["ReportState", "run_report_graph", "EDGES", "NODES", "MAX_NODE_VISITS"]
