"""A reusable StateGraph that phrases a computed snapshot and verifies its figures before shipping.

The world-book coach doors share one shape: compute a ledger, hand its exact rows to the model, and
print whatever comes back — with no check that the model kept to the numbers it was shown. This module
is that check, once, for every door that wants it:

    draft -> verify -> (repair) -> END

`draft` is one model call behind the byte-identical charter prefix (so the gateway caches it across
doors). `verify` is deterministic: every decimal the prose quotes must appear among the figures in
the facts it was handed. `repair` is a conditional edge that drops any sentence with a drifted figure
rather than asking the model to invent a correction — the same discipline the report and admin-coach
graphs use. The caller keeps its own return shape; this helper only owns the `answer` string and the
verification metadata.

Feature name is supplied by the caller so the ledger still attributes each call to its door.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.providers import LlmResult, get_llm_provider
from app.services.knowledge.library_charter import LIBRARY_CHARTER
from app.services.model_ledger import record_model_call_safely

MAX_NODE_VISITS = 6
_NUMBER_RE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)")

_StateGraph: Any = None
_LG_END: Any = "__end__"
try:
    from langgraph.graph import END as _LG_END_
    from langgraph.graph import StateGraph as _StateGraph_

    _StateGraph = _StateGraph_
    _LG_END = _LG_END_
except ImportError:  # pragma: no cover - optional extra
    _StateGraph = None


@dataclass
class PhraseState:
    system: str
    prompt: str
    feature: str
    max_tokens: int = 380
    temperature: float = 0.3
    answer: str = ""
    allowed_figures: set[str] = field(default_factory=set)
    verified: bool = True
    repairs: int = 0
    trace: list[dict[str, Any]] = field(default_factory=list)
    result: LlmResult | None = None
    error: str = ""
    provider_override: Any | None = None
    record: bool = True


def allowed_figures_from(prompt: str) -> set[str]:
    """Every numeric token the model was shown — the only figures it may quote."""
    return {m.group(1) for m in _NUMBER_RE.finditer(prompt)}


def _node_draft(state: PhraseState) -> PhraseState:
    started = time.perf_counter()
    provider = state.provider_override or get_llm_provider()
    try:
        result = provider.complete(
            system=LIBRARY_CHARTER + state.system,
            prompt=state.prompt,
            max_tokens=state.max_tokens,
            temperature=state.temperature,
        )
    except Exception as error:  # noqa: BLE001 — the gateway is the risk; the door must stay up.
        result = LlmResult(
            text="", provider=getattr(provider, "name", "unknown"), model="unreachable",
            demo_mode=True, error=str(error)[:300], latency_ms=0,
        )
    if state.record:
        record_model_call_safely(result=result, feature=state.feature)
    state.result = result
    state.error = (result.error or "")[:160]
    state.answer = (result.text or "").strip()
    state.trace.append({
        "node": "draft", "kind": "model", "provider": result.provider, "model": result.model,
        "latency_ms": result.latency_ms or int((time.perf_counter() - started) * 1000),
        "error": (result.error or "")[:120],
    })
    return state


def _node_verify(state: PhraseState) -> PhraseState:
    started = time.perf_counter()
    # Only decimal figures are policed — integers in prose ("one paragraph") are not statistics.
    quoted = {m.group(1) for m in _NUMBER_RE.finditer(state.answer) if "." in m.group(1)}
    bad = sorted(q for q in quoted if q not in state.allowed_figures)
    state.verified = not bad
    state.trace.append({"node": "verify", "kind": "rule", "ok": state.verified, "unmatched": bad})
    state.trace.append({"node": "verify.summary", "kind": "rule", "ok": state.verified,
                        "latency_ms": int((time.perf_counter() - started) * 1000)})
    return state


def _node_repair(state: PhraseState) -> PhraseState:
    started = time.perf_counter()
    sentences = [p for p in re.split(r"(?<=[.!?。！？])\s+", state.answer.strip()) if p]
    kept = [
        s for s in sentences
        if all(m.group(1) in state.allowed_figures for m in _NUMBER_RE.finditer(s) if "." in m.group(1))
    ]
    state.answer = " ".join(kept).strip() or "The stored figures do not support a summary of this ledger this window."
    state.verified = True
    state.repairs += 1
    state.trace.append({"node": "repair", "kind": "rule", "dropped": len(sentences) - len(kept),
                        "latency_ms": int((time.perf_counter() - started) * 1000)})
    return state


NODES: dict[str, Callable[[PhraseState], PhraseState]] = {
    "draft": _node_draft, "verify": _node_verify, "repair": _node_repair,
}
EDGES: list[tuple[str, str]] = [("draft", "verify"), ("verify", _LG_END), ("repair", _LG_END)]


def _verify_route(state: PhraseState) -> str:
    return "repair" if (state.answer and not state.verified) else "assemble"


def _compile() -> Any | None:
    if _StateGraph is None:
        return None
    builder = _StateGraph(PhraseState)
    for name, fn in NODES.items():
        node = fn
        node.__name__ = name
        builder.add_node(name, node)
    builder.set_entry_point("draft")
    for source, target in EDGES:
        if source == "verify":
            continue
        if target == _LG_END:
            builder.set_finish_point(source)
        else:
            builder.add_edge(source, target)
    builder.add_conditional_edges("verify", _verify_route, {"repair": "repair", "assemble": _LG_END})
    return builder.compile()


def phrase_and_verify(*, system: str, prompt: str, feature: str, max_tokens: int = 380,
                      temperature: float = 0.3, provider: Any | None = None,
                      record: bool = True) -> PhraseState:
    """Run the graph and return the verified state; the caller maps fields onto its own envelope.

    `provider` is injectable so a door keeps its own monkeypatch point (its tests patch
    `get_llm_provider` in the calling module); absent one, the configured provider is used.
    `record=False` leaves ledger attribution to the caller (used by the thin LlmResult wrapper).
    """
    state = PhraseState(system=system, prompt=prompt, feature=feature,
                        max_tokens=max_tokens, temperature=temperature,
                        allowed_figures=allowed_figures_from(prompt), provider_override=provider,
                        record=record)
    graph = _compile()
    if graph is not None:
        try:
            out = graph.invoke(state)
            if isinstance(out, PhraseState):
                return out
            if isinstance(out, dict):
                return PhraseState(**out)
        except Exception as error:  # noqa: BLE001 — fall back to the edge table, same contract.
            state = PhraseState(system=system, prompt=prompt, feature=feature,
                                max_tokens=max_tokens, temperature=temperature,
                                allowed_figures=state.allowed_figures, provider_override=provider,
                                record=record,
                                trace=[{"node": "langgraph", "kind": "rule", "fallback": True,
                                        "error": str(error)[:120]}])
    node = "draft"
    visited = 0
    while node != _LG_END and visited < MAX_NODE_VISITS:
        visited += 1
        if node in NODES:
            state = NODES[node](state)
        if node == "verify":
            node = _verify_route(state)
            if node == "assemble":
                break
            continue
        node = next((t for s, t in EDGES if s == node), _LG_END)
    return state


def phrase_verified_complete(*, provider: Any, system: str, prompt: str, feature: str,
                             max_tokens: int = 380, temperature: float = 0.3) -> LlmResult:
    """A drop-in for `provider.complete(...)` that returns a figure-verified LlmResult.

    The returned object carries the repaired prose in `.text` and the verification metadata in
    `.structured` (`verified`, `repairs`, `trace`), so a door can swap one call and keep its entire
    ledger/return envelope. Ledger attribution stays with the caller (record=False here).
    """
    state = phrase_and_verify(system=system, prompt=prompt, feature=feature,
                              max_tokens=max_tokens, temperature=temperature,
                              provider=provider, record=False)
    result = state.result
    if result is None:
        return LlmResult(text="", provider=getattr(provider, "name", "unknown"), model="unreachable",
                         demo_mode=True, error=state.error or "unreachable gateway", latency_ms=0)
    # Replace the prose with the verified/repaired text; keep every token/usage field the caller reads.
    return LlmResult(
        text=state.answer,
        provider=result.provider,
        model=result.model,
        demo_mode=result.demo_mode,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        reasoning_tokens=result.reasoning_tokens,
        cached_input_tokens=result.cached_input_tokens,
        cache_reported=result.cache_reported,
        latency_ms=result.latency_ms,
        estimated_cost_usd=result.estimated_cost_usd,
        actual_cost_usd=result.actual_cost_usd,
        structured={"verified": state.verified, "repairs": state.repairs, "trace": state.trace},
        error=result.error,
    )


__all__ = ["PhraseState", "NODES", "EDGES", "allowed_figures_from", "phrase_and_verify",
           "phrase_verified_complete"]
