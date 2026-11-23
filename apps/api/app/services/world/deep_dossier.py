"""The deep dossier — a real 50k–90k token context, walked by a StateGraph.

The owner asked for Codex-scale input: "Codex 一次可以打进 5 万～9 万上下文，我这边输入上下文总是太少".
Every other door in this tree asks a few thousand tokens; the largest shared prefix measured anywhere is
~21.8k (Item 278). This module is the missing size class, not another small prompt with a new name:

    harvest → draft → verify → assemble

* ``harvest`` is deterministic and offline. It reads this repository's 270 hand-authored real finals
  (openfootball, with Chinese companions) and packs a focus-ranked selection into a dossier whose
  measured size lands in a named depth band. The same focus, seed and depth always produce the
  same bytes, so a dossier can be cached, diffed and tested without a provider.
* ``draft`` sends that dossier to the gateway behind the *same* frozen LIBRARY_CHARTER system prefix
  every other AI door uses. Measured 2026-11-22 on `api.aizzz.xyz`: this gateway caches an
  **exact request**, not a leading prefix — the same 70k-token system with a different user turn
  reported 3,367 cached, while an identical repeat reported 62,822 (88.8 %). So the frozen prefix
  earns reuse only when the whole call repeats; a new focus is a cold charge by construction, and
  the library (not the gateway) is what makes a repeat free. The provider is injected.
* ``verify`` is a rule: a decimal the answer quotes must be a decimal the dossier carried. Drift is
  reported, never silently repaired by asking the model to invent a correction.
* ``assemble`` returns the prose, the dossier's measured footprint, the source list and one trace per
  node, so the context size is a published number rather than a claim in a document.

Nothing here changes the deterministic world. The dossier reads committed prose; the model only
writes the reader's chapter. Feature name for the ledger: ``world.deep_dossier.draft``.
"""

from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.providers import LlmResult, get_llm_provider
from app.services.knowledge.library_charter import LIBRARY_CHARTER
from app.services.model_ledger import record_model_call_safely

# Optional LangGraph, same import discipline as deep_read.py and sim_report_graph.py: the module-level
# Any accepts the ``None`` assignment in the fallback without a narrowing error.
_StateGraph: Any = None
_LG_END: Any = "__end__"
try:
    from langgraph.graph import END as _LG_END_
    from langgraph.graph import StateGraph as _StateGraph_

    _StateGraph = _StateGraph_
    _LG_END = _LG_END_
except ImportError:  # pragma: no cover - the edge-table walk is the same graph without the dependency.
    _StateGraph = None

#: Named bands, in estimated input tokens. The frozen charter alone is ~49k tokens (it grew with
#: the 270 real finals), so even the smallest band is already in the owner's 50k–90k class; 95k is
#: the hard ceiling so a dossier can never quietly grow past the window it was tested at.
DEPTH_TARGETS: dict[str, int] = {"standard": 55000, "deep": 72000, "epic": 88000}
MAX_TARGET = 95000
MAX_SOURCE_CHARS = 12000
MAX_SOURCES = 120

#: 270+ committed chapters: `data/knowledge/history/*.md`, ~1.5 MB of real finals in en+zh.
def _resolve_history_dir() -> Path:
    """Find the chapter shelf in a checkout, in a container, or under an explicit mount.

    A hard-coded `parents[5]` works in the source tree but raises `IndexError` at import time in the
    API image (`/app/app/services/world/…` has no sixth parent), which took the whole container down
    before it could bind :8100. Probe every plausible root instead and keep a harmless fallback:
    `load_dossier` already guards on `is_dir()`, so an absent shelf degrades to an empty dossier
    rather than an unbootable service. The compose plane mounts the shelf at `/data/knowledge`.
    """
    candidates: list[Path] = []
    mounted = os.environ.get("FOOTBALL_KNOWLEDGE_DIR")
    if mounted:
        candidates.append(Path(mounted) / "history")
        candidates.append(Path(mounted))
    candidates.append(Path("/data/knowledge/history"))
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidates.append(parent / "data" / "knowledge" / "history")
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return candidates[-1]


HISTORY_DIR = _resolve_history_dir()

_CJK = re.compile(r"[\u4e00-\u9fff]")
_DECIMAL = re.compile(r"(?<![\w.])(\d+\.\d+)(?![\w.])")

_SYSTEM = """\
You are the archivist of a football world that keeps a library of real finals and a league the
simulation engine computed. You are handed a DOSSIER assembled from that library — chapter after
chapter of stored history, each with its own date, venue, score and scorers. Write the epic chapter
those passages earn: a long-form read that connects the documented finals into one through-line,
names the clubs, players, venues, scores and years exactly as the dossier prints them, and says what
each detail meant at the time.

Rules that apply to every word:
1. The dossier is the whole world. Never invent a club, a player, a venue, a date, a score, a crowd
   figure or a competition. If a fact is not printed in the dossier, it does not exist.
2. Quote no decimal that the dossier does not carry. Rounded prose about a stored integer is fine;
   a new decimal is not.
3. Do not predict a future final, a winner or a record. You describe the stored past only.
4. Write in the language the reader's locale asks for. Plain prose, no headings, no bullets, no emoji,
   no markdown. Six to nine paragraphs, each grounded in a passage you actually received.
"""

_INTENT = {
    "en": "Answer in English.",
    "zh": "请用中文回答。",
    "zh-TW": "請用繁體中文回答。",
    "fr": "Répondez en français.",
    "ar": "أجب بالعربية.",
    "he": "השב בעברית.",
}

_QUESTION = """\
DOSSIER — {depth} band, seed {seed}, {source_count} source chapters, about {estimated_tokens} input tokens.
Reader's focus: {focus}

{dossier}

{intent}
Write the epic chapter the dossier earns, grounded in the passages above and nowhere else.
"""

# Byte 0 of every call is the same frozen charter every AI door uses; the graph never prepends
# focus-, seed- or locale-specific text to it. On 2026-11-22 this gateway was measured to cache the
# *whole request* rather than this prefix: changing only the user turn dropped cached tokens from
# 62,822 to 3,367. The constant still matters — it makes answers comparable and gives an exact
# repeat something to hit — but it does not make a new focus cheap.
_SYSTEM_PREFIX = LIBRARY_CHARTER + "\n\n" + _SYSTEM


def estimate_tokens(text: str) -> int:
    """A conservative, deterministic token estimate for mixed CJK/Latin prose.

    CJK characters average about 1.5 per token and Latin prose about 4 characters per token on the
    gateway's tokenizer. No network call and no tokenizer wheel: the figure is a *conservative lower
    bound on the bytes we send*, reproducible offline in a test, not the gateway's charge. A live
    epic run measured 88,397 here against 131,386 gateway `input_tokens` (factor 1.49) — the estimate
    deliberately undercounts so a band never advertises more context than it actually delivered.
    The gateway's own `input_tokens` is published beside it in the response.
    """
    cjk = len(_CJK.findall(text))
    return int(cjk / 1.5 + (len(text) - cjk) / 4)


@dataclass
class Dossier:
    """The offline half of the graph: bytes, sources and a reproducible footprint."""

    focus: str
    depth: str
    seed: int
    target_tokens: int
    text: str = ""
    sources: list[str] = field(default_factory=list)
    chars: int = 0
    estimated_tokens: int = 0
    system_estimated_tokens: int = 0

    @property
    def total_estimated_tokens(self) -> int:
        return self.estimated_tokens + self.system_estimated_tokens


def build_dossier(focus: str, *, depth: str = "deep", seed: int = 0) -> Dossier:
    """Pack the committed finals into a deterministic dossier of the requested size band.

    Order is derived from a sha256 of (seed, focus, filename), not from directory order or mtime:
    the same call on another machine, in another checkout, yields byte-identical bytes. A chapter
    is truncated at MAX_SOURCE_CHARS so one long file cannot swallow the whole budget, and the
    dossier stops at the first band that reaches the target — never at a size that would cross the
    published ceiling.
    """
    if depth not in DEPTH_TARGETS:
        raise ValueError(f"unknown depth {depth!r}; expected one of {sorted(DEPTH_TARGETS)}")
    target = min(DEPTH_TARGETS[depth], MAX_TARGET)
    dossier = Dossier(focus=focus, depth=depth, seed=seed, target_tokens=target)
    dossier.system_estimated_tokens = estimate_tokens(_SYSTEM_PREFIX)

    files = sorted(HISTORY_DIR.glob("*.md")) if HISTORY_DIR.is_dir() else []

    def rank(path: Path) -> str:
        digest = hashlib.sha256(f"{seed}|{focus}|{path.name}".encode()).hexdigest()
        return digest

    ordered = sorted(files, key=rank)
    blocks: list[str] = []
    total = 0
    for path in ordered[:MAX_SOURCES]:
        body = path.read_text(encoding="utf-8", errors="replace")[:MAX_SOURCE_CHARS]
        block = f"=== SOURCE {len(blocks) + 1:03d} · {path.stem} ===\n{body.strip()}"
        gained = estimate_tokens(block)
        if total + gained > MAX_TARGET + estimate_tokens(_QUESTION.format(
            depth=depth, seed=seed, source_count=len(blocks) + 1,
            estimated_tokens=total + gained, focus=focus, dossier="", intent="",
        )):
            break
        blocks.append(block)
        dossier.sources.append(path.stem)
        total += gained
        if total + dossier.system_estimated_tokens >= target:
            break

    dossier.text = "\n\n".join(blocks)
    dossier.chars = len(dossier.text)
    dossier.estimated_tokens = estimate_tokens(dossier.text)
    return dossier


@dataclass
class DossierState:
    """The shared object every node reads and returns; trace and source list are append-only."""

    focus: str
    depth: str
    seed: int
    locale: str
    dossier: Dossier | None = None
    prose: str = ""
    topic_prompt: str = ""
    verified: bool = True
    drifted_decimals: list[str] = field(default_factory=list)
    trace: list[dict[str, Any]] = field(default_factory=list)
    result: LlmResult | None = None
    error: str = ""
    provider_override: Any | None = None


def _trace(state: DossierState, node: str, detail: str) -> None:
    state.trace.append({"node": node, "detail": detail})


def _harvest(state: DossierState) -> DossierState:
    state.dossier = build_dossier(state.focus, depth=state.depth, seed=state.seed)
    _trace(state, "harvest", (
        f"{len(state.dossier.sources)} source chapter(s), {state.dossier.chars} chars, "
        f"{state.dossier.total_estimated_tokens} estimated input tokens"
    ))
    return state


def _draft(state: DossierState) -> DossierState:
    dossier = state.dossier
    assert dossier is not None, "harvest must run before draft"
    intent = _INTENT.get(state.locale, _INTENT["en"])
    state.topic_prompt = _QUESTION.format(
        depth=dossier.depth, seed=dossier.seed, source_count=len(dossier.sources),
        estimated_tokens=dossier.total_estimated_tokens, focus=dossier.focus,
        dossier=dossier.text, intent=intent,
    )
    provider = state.provider_override if state.provider_override is not None else get_llm_provider()
    try:
        state.result = provider.complete(
            system=_SYSTEM_PREFIX, prompt=state.topic_prompt, max_tokens=1100, temperature=0.35,
        )
        state.prose = state.result.text or ""
    except Exception as error:  # noqa: BLE001 — the door stays up when the model is down.
        state.error = str(error)[:300]
        state.result = LlmResult(
            text="", provider=getattr(provider, "name", "unknown"), model="unreachable",
            demo_mode=True, error=state.error, latency_ms=0,
        )
    _trace(state, "draft", f"provider={getattr(state.result, 'provider', 'unknown')} chars={len(state.prose)}")
    return state


def _verify(state: DossierState) -> DossierState:
    """A decimal in the prose must be a decimal the dossier carried."""
    dossier = state.dossier
    assert dossier is not None, "harvest must run before verify"
    allowed = set(_DECIMAL.findall(dossier.text))
    quoted = set(_DECIMAL.findall(state.prose))
    state.drifted_decimals = sorted(quoted - allowed)
    state.verified = not state.drifted_decimals
    _trace(state, "verify", (
        "all quoted decimals grounded" if state.verified
        else f"{len(state.drifted_decimals)} ungrounded decimal(s): {state.drifted_decimals[:4]}"
    ))
    return state


def _assemble(state: DossierState) -> DossierState:
    _trace(state, "assemble", "chapter, dossier metrics and trace published")
    return state


# The same edge table is walked directly when LangGraph is not installed, so tests and deployments
# without the optional extra see identical output — including trace order.
_EDGES: tuple[tuple[str, Callable[[DossierState], DossierState]], ...] = (
    ("harvest", _harvest),
    ("draft", _draft),
    ("verify", _verify),
    ("assemble", _assemble),
)


def run_dossier_graph(
    focus: str, *, depth: str = "deep", seed: int = 0, locale: str = "en",
    provider: Any | None = None,
) -> DossierState:
    """Walk the dossier graph; ``provider`` is injectable so tests never need the live gateway."""
    state = DossierState(focus=focus, depth=depth, seed=seed, locale=locale, provider_override=provider)
    if _StateGraph is None:  # pragma: no cover - exercised here when langgraph is absent.
        for _node, action in _EDGES:
            state = action(state)
        return state

    graph: Any = _StateGraph(DossierState)
    for node, action in _EDGES:
        # Named closures with __name__: mypy accepts the add_node callback and LangGraph prints the
        # node's name in its own trace, the same discipline sim_report_graph uses.
        def step(s: DossierState, _action: Callable[[DossierState], DossierState] = action) -> DossierState:
            return _action(s)

        step.__name__ = node
        graph.add_node(node, step)
    graph.set_entry_point("harvest")
    graph.add_edge("harvest", "draft")
    graph.add_edge("draft", "verify")
    graph.add_edge("verify", "assemble")
    graph.add_edge("assemble", _LG_END)
    compiled: Any = graph.compile()
    try:
        out = compiled.invoke(state)
        if isinstance(out, DossierState):
            return out
        if isinstance(out, dict):
            # LangGraph may hand back the state as a mapping; rebuild the dataclass so every
            # node mutation (trace, dossier, result) survives the boundary — same as deep_read.
            return DossierState(**out)
    except Exception as error:  # noqa: BLE001 — the edge table is the same graph without the dependency.
        state.trace.append({"node": "langgraph", "kind": "rule", "fallback": True, "error": str(error)[:120]})
        for _node, action in _EDGES:
            state = action(state)
    return state


def compute_deep_dossier(
    focus: str, *, depth: str = "deep", seed: int = 0, locale: str = "en",
    provider: Any | None = None,
) -> dict[str, Any]:
    """The door's payload. Dossier metrics are published even when no provider is configured."""
    if not focus.strip():
        return {"available": False, "error": "focus is empty"}
    state = run_dossier_graph(focus=focus.strip(), depth=depth, seed=seed, locale=locale, provider=provider)
    dossier = state.dossier
    assert dossier is not None, "the graph always harvests before returning"
    result = state.result
    if result is not None:
        record_model_call_safely(result=result, feature="world.deep_dossier.draft")
    demo = bool(result and result.demo_mode)
    return {
        "available": bool(state.prose) and not demo,
        "focus": dossier.focus,
        "depth": dossier.depth,
        "seed": dossier.seed,
        "target_tokens": dossier.target_tokens,
        "estimated_input_tokens": dossier.total_estimated_tokens,
        "dossier_tokens": dossier.estimated_tokens,
        "dossier_chars": dossier.chars,
        "source_count": len(dossier.sources),
        "sources": dossier.sources[:12],
        "chapter": state.prose,
        "verified": state.verified,
        "drifted_decimals": state.drifted_decimals[:8],
        "trace": state.trace,
        "provider": result.provider if result else "unknown",
        "model": result.model if result else "unknown",
        "demo_mode": demo,
        "input_tokens": result.input_tokens if result else 0,
        "cached_input_tokens": result.cached_input_tokens if result else 0,
        "cache_reported": result.cache_reported if result else False,
        "output_tokens": result.output_tokens if result else 0,
        "error": state.error or ((result.error or "") if result else ""),
    }
