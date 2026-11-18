"""The Deep Read — full chapters into the prompt, not an excerpt.

The knowledge door reads one question against numbered passages cut from
the basket (it has to be a shelf, not a book — the budget demands it). The Deep
Read is the mirror image: it walks retrieval, selects the chapters the question
lands on, and hands the model the *full text* of each one — the front matter
stripped, including the sections that made the chapter worth writing.

Four nodes, always the same order, with the trace always on. The walk itself
is compiled by LangGraph's ``StateGraph`` when ``langgraph`` is importable
(it is pinned in the image), otherwise the module falls back to the bounded
hand-rolled walk — both paths produce a byte-identical ``graph_trace``:

    START -> gather -> draft -> verify -> repair -> END

* ``gather`` is deterministic: hybrid retrieval, grouped by document, bodies
  loaded from the corpus on disk (falling back to the stored chunks when a file
  cannot be read), under two budgets — per chapter and total. No model.
* ``draft`` asks the provider for a cited answer, led by the same LIBRARY_CHARTER
  at byte 0 and the ``deep_read`` discipline.
* ``verify`` is deterministic: every ``[n]`` marker in the answer must name a
  chapter that travelled in the prompt, and at least one marker must be present.
* ``repair`` (one pass, never a loop) hands the draft back to the provider with
  the failure named, and the repaired answer replaces the draft. If repair
  fails, the door says so — it never hides a red verdict.

Context sizes measured at this landing: the drafted context carries the charter
(39,300 bytes) plus up to eight full chapters under a 52,000-byte cap — the
envelope the 3210 spoke prints as ``input_tokens`` is recorded in the ledger.
LangGraph owns the control-flow; LangChain itself is not required (no retriever,
no LLM wrapper — the OpenAI-compatible adapter in ``app.providers`` is the
provider); the graph exists for the same reason ``agents.coach_graph`` uses one:
the walk is the product, and a pipeline nobody can see is the failure mode
StateGraph exists to abolish.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import KnowledgeChunk, KnowledgeDocument
from app.providers import LlmResult, get_llm_provider
from app.services.knowledge import retrieval
from app.services.knowledge.answer import ANSWER_SCORE_FLOOR
from app.services.knowledge.library_charter import LIBRARY_CHARTER
from app.services.knowledge.retrieval import Filters
from app.services.model_ledger import budget_exhausted, record_model_call_safely

# LangGraph is optional at import time; the compiled path and the fallback agree below.
# The module globals are typed as `Any` up front so mypy sees the fallback branch
# (``= None``) as a legal assignment rather than an incompatible narrowing.
_StateGraph: Any = None  # assigned at import time from langgraph, or left as the sentinel when absent
_LG_END: Any = None
try:
    from langgraph.graph import END as _LG_END_
    from langgraph.graph import StateGraph as _StateGraph_

    _StateGraph = _StateGraph_
    _LG_END = _LG_END_
except ImportError:  # pragma: no cover - the image pins langgraph; this branch exists for bare venvs
    _StateGraph = None
    _LG_END = None

logger = logging.getLogger("football_os.deep_read")

MAX_CHAPTERS = 8
MAX_CHAPTER_BYTES = 12_000
MAX_TOTAL_BYTES = 52_000
MAX_NODE_VISITS = 8

_SYSTEM_DRAFT = """\
You are the Deep Read inside FOOTBALL OS. You answer a football question from 
the complete chapters that travel with it — the whole text, not excerpts — and 
nothing else. You are the library's long-form mind: the question may want to be 
argued with, not only answered.

Rules:

1. Every claim you print must come from the chapters. Cite them inline as [1], 
   [2] and so on, attached to the claim they support. One chapter may support 
   several claims; one claim may need two citations.
2. If the chapters do not support an answer, say plainly that you cannot 
   support one from the loaded material, and name what would be needed: a more 
   specific question, or a document the library does not hold.
3. Never invent a quantified claim — distances, speeds, season counts, 
   percentages, prices — that is not printed in the chapters, and cite those 
   that are.
4. Answer in the same language as the question. Do not translate terms of art 
   the chapters use in another language.
5. No headings, no bullet lists, no flattery, no greetings. Dense, specific 
   prose — the register of a good magazine feature, not a chat window. Two to 
   six tight paragraphs.
6. End with a single line that reads 'Sources:' followed by the chapter numbers 
   you used, in the order they first appeared, comma-separated. Nothing after 
   that line.
"""

_SYSTEM_REPAIR = """\
You are the same Deep Read, called back to fix one mechanical fault: the draft 
you wrote cited a chapter marker that does not name a chapter that travelled, 
or cited nothing at all. Re-write the answer with the same discipline:

- every claim attaches an inline [n] marker naming a chapter that is in the 
  prompt;
- at least one marker survives;
- the prose keeps the register of the draft — no greetings, no headings, no 
  bullet lists;
- end with the same 'Sources:' line, naming the numbers you used.
"""

_SYSTEM_DRAFT_CHARTER = LIBRARY_CHARTER + _SYSTEM_DRAFT
_SYSTEM_REPAIR_CHARTER = LIBRARY_CHARTER + _SYSTEM_REPAIR

_REF_RE = re.compile(r"\[(\d{1,2})\]")
_FRONT_MATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)


def _load_body(db: Session, slug: str) -> str:
    document = db.scalar(select(KnowledgeDocument).where(KnowledgeDocument.slug == slug))
    candidate = Path(settings.knowledge_dir) / document.source_path if document and document.source_path else None
    if candidate and candidate.is_file():
        try:
            raw = candidate.read_text(encoding="utf-8")
        except OSError:
            raw = ""
        body = _FRONT_MATTER_RE.sub("", raw, count=1)
        if body.strip():
            return body
    if document:
        chunks = db.scalars(
            select(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id).order_by(KnowledgeChunk.ordinal)
        ).all()
        return "\n\n".join(chunk.text for chunk in chunks)
    return ""


@dataclass
class DeepReadState:
    question: str = ""
    locale: str = "en"
    filters: Filters | None = None
    available: bool = True
    chapters: list[dict[str, Any]] = field(default_factory=list)
    chapter_bodies: dict[int, str] = field(default_factory=dict)
    draft: str = ""
    answer: str = ""
    verify_ok: bool = False
    verify_refs: list[int] = field(default_factory=list)
    repair_passes: int = 0
    provider: str = "unknown"
    model: str = "unknown"
    demo_mode: bool = True
    error: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    cache_reported: bool = False
    context_bytes: int = 0
    timings_ms: dict[str, int] = field(default_factory=dict)
    graph_trace: list[str] = field(default_factory=list)


def _node_gather(state: DeepReadState, db: Session) -> DeepReadState:
    started = time.perf_counter()
    filters = state.filters or Filters()
    if filters.locale is None:
        filters.locale = state.locale
    found = retrieval.search(db, state.question, filters=filters, mode="hybrid", top_k=10)
    hits = [hit for hit in found.hits if hit.score >= ANSWER_SCORE_FLOOR]
    if not hits:
        state.available = False
        state.error = (
            f"no chapter cleared the answer floor (top score {found.top_score:.3f} < {ANSWER_SCORE_FLOOR})"
        )
        state.timings_ms["gather"] = int((time.perf_counter() - started) * 1000)
        return state

    best: dict[str, Any] = {}
    order: list[str] = []
    for hit in hits:
        slug = hit.document_slug
        row = best.get(slug)
        if row is None:
            best[slug] = {"title": hit.title, "score": hit.score}
            order.append(slug)
        elif hit.score > row["score"]:
            row["score"] = hit.score

    chapters: list[dict[str, Any]] = []
    pool_bytes = 0
    for slug in order:
        if len(chapters) >= MAX_CHAPTERS or pool_bytes >= MAX_TOTAL_BYTES:
            break
        body = _load_body(db, slug)
        if not body.strip():
            continue
        budget = min(MAX_CHAPTER_BYTES, MAX_TOTAL_BYTES - pool_bytes)
        if len(body) > budget:
            body = body[:budget].rsplit("\n", 1)[0]
        chapters.append(
            {
                "ref": len(chapters) + 1,
                "slug": slug,
                "title": best[slug]["title"],
                "score": round(best[slug]["score"], 4),
                "bytes": len(body),
                "body": body,
            }
        )
        pool_bytes += len(body)

    if not chapters:
        state.available = False
        state.error = "the chapters the question lands on could not be loaded from the corpus"
        state.timings_ms["gather"] = int((time.perf_counter() - started) * 1000)
        return state

    state.chapters = [{key: value for key, value in chapter.items() if key != "body"} for chapter in chapters]
    state.chapter_bodies = {chapter["ref"]: chapter["body"] for chapter in chapters}
    state.context_bytes = pool_bytes
    state.timings_ms["gather"] = int((time.perf_counter() - started) * 1000)
    logger.info("deep_read.gather chapters=%d bytes=%d", len(chapters), pool_bytes)
    return state


def _prompt_payload(state: DeepReadState) -> str:
    return json.dumps(
        {
            "intent": "deep_read",
            "question": state.question,
            "chapters": [
                {"ref": chapter["ref"], "title": chapter["title"], "body": state.chapter_bodies[chapter["ref"]]}
                for chapter in state.chapters
            ],
        },
        ensure_ascii=False,
    )


def _node_draft(state: DeepReadState, db: Session) -> DeepReadState:
    if not state.available:
        return state
    if budget_exhausted(db):
        state.provider = "rule-engine-demo"
        state.model = "rule-engine-demo"
        first = state.chapters[0]
        state.draft = (
            f"The gateway's daily cap is reached, so this turn answers from the shelf instead of the voice. "
            f"The chapters that land on this question: {', '.join(c['slug'] for c in state.chapters)}. "
            f"Start with [1] — {first['title']} — and read down the shelf. [1]"
        )
        state.answer = state.draft
        state.verify_ok = True
        state.verify_refs = [chapter["ref"] for chapter in state.chapters]
        return state

    provider = get_llm_provider()
    try:
        result = provider.complete(
            system=_SYSTEM_DRAFT_CHARTER,
            prompt=_prompt_payload(state),
            max_tokens=850,
            temperature=0.35,
            prompt_cache_key="knowledge.deep_read.draft",
        )
    except Exception as error:  # noqa: BLE001 — the gateway is the risk; the door must stay up.
        result = LlmResult(
            text="",
            provider=getattr(provider, "name", "unknown"),
            model="unreachable",
            demo_mode=True,
            error=str(error)[:300],
            latency_ms=0,
        )
        state.error = (result.error or "unreachable gateway")[:160]
    record_model_call_safely(result=result, feature="knowledge.deep_read.draft")
    state.input_tokens += result.input_tokens or 0
    state.output_tokens += result.output_tokens or 0
    state.cached_input_tokens += result.cached_input_tokens or 0
    state.cache_reported = state.cache_reported or bool(result.cache_reported)
    state.provider = result.provider
    state.model = result.model
    state.demo_mode = bool(result.demo_mode)
    if result.error:
        state.available = False
        return state
    state.draft = (result.text or "").strip()
    state.answer = state.draft
    return state


def _node_verify(state: DeepReadState, db: Session) -> DeepReadState:  # noqa: ARG001 — the node is deterministic.
    if not state.available:
        return state
    refs = sorted({int(raw) for raw in _REF_RE.findall(state.draft)})
    known = {chapter["ref"] for chapter in state.chapters}
    state.verify_refs = refs
    state.verify_ok = bool(refs) and all(ref in known for ref in refs)
    logger.info("deep_read.verify ok=%s refs=%s", state.verify_ok, refs)
    return state


def _node_repair(state: DeepReadState, db: Session) -> DeepReadState:
    if not state.available or state.verify_ok or state.repair_passes >= 1:
        return state
    state.repair_passes = 1
    if budget_exhausted(db):
        return state
    provider = get_llm_provider()
    try:
        result = provider.complete(
            system=_SYSTEM_REPAIR_CHARTER,
            prompt=json.dumps(
                {
                    "intent": "deep_read_repair",
                    "question": state.question,
                    "draft": state.draft,
                    "chapters": [
                        {
                            "ref": chapter["ref"],
                            "title": chapter["title"],
                            "body": state.chapter_bodies[chapter["ref"]][:4000],
                        }
                        for chapter in state.chapters
                    ],
                    "failure": f"cited refs {state.verify_refs or '[]'} against chapters {sorted({c['ref'] for c in state.chapters})}",
                },
                ensure_ascii=False,
            ),
            max_tokens=850,
            temperature=0.2,
            prompt_cache_key="knowledge.deep_read.repair",
        )
    except Exception as error:  # noqa: BLE001
        result = LlmResult(
            text="",
            provider=getattr(provider, "name", "unknown"),
            model="unreachable",
            demo_mode=True,
            error=str(error)[:300],
            latency_ms=0,
        )
    record_model_call_safely(result=result, feature="knowledge.deep_read.repair")
    state.input_tokens += result.input_tokens or 0
    state.output_tokens += result.output_tokens or 0
    state.cached_input_tokens += result.cached_input_tokens or 0
    state.cache_reported = state.cache_reported or bool(result.cache_reported)
    if result.error and not (result.text or "").strip():
        return state
    state.answer = (result.text or "").strip()
    refs = sorted({int(raw) for raw in _REF_RE.findall(state.answer)})
    known = {chapter["ref"] for chapter in state.chapters}
    state.verify_refs = refs
    state.verify_ok = bool(refs) and all(ref in known for ref in refs)
    return state

def compile_chain() -> list[tuple[str, Any]]:
    """The compiled edge table — one ordered list, walked in order when LangGraph is unavailable."""
    return [
        ("gather", _node_gather),
        ("draft", _node_draft),
        ("verify", _node_verify),
        ("repair", _node_repair),
        ("END", None),
    ]


def _compile_langgraph(db: Session) -> Any | None:
    """Build the StateGraph for one run.

    The graph is linear (gather → draft → verify → repair → END) but the repair
    node decides for itself whether any work is owed, exactly like the hand-rolled
    walk — byte-identical ``graph_trace``, byte-identical side effects, one less
    edge table to maintain. The compiled graph is rebuilt at call time so tests
    that monkeypatch the module-level nodes keep working untouched.
    """
    if _StateGraph is None:
        return None

    def _make_node(name: str, fn: Any) -> Any:
        def node(state: DeepReadState) -> DeepReadState:
            state.graph_trace.append(name)
            return fn(state)

        node.__name__ = name
        return node

    builder = _StateGraph(DeepReadState)
    builder.add_node("gather", _make_node("gather", lambda state: _node_gather(state, db)))
    builder.add_node("draft", _make_node("draft", lambda state: _node_draft(state, db)))
    builder.add_node("verify", _make_node("verify", lambda state: _node_verify(state, db)))
    builder.add_node("repair", _make_node("repair", lambda state: _node_repair(state, db)))
    builder.set_entry_point("gather")
    builder.add_edge("gather", "draft")
    builder.add_edge("draft", "verify")
    builder.add_edge("verify", "repair")
    builder.add_edge("repair", _LG_END)
    return builder.compile()


def _walk_graph(db: Session, state: DeepReadState) -> DeepReadState:
    """Walk the compiled LangGraph path — the default engine for this door."""
    graph = _compile_langgraph(db)
    if graph is None:
        return _walk_legacy(db, state)
    out = graph.invoke(state)
    if isinstance(out, dict):
        # DeepReadState → dict → DeepReadState keeps every node mutation even if
        # langgraph ever stops passing the dataclass through by identity.
        state = DeepReadState(**out)
    # The trace bookends are added at the boundary so the caller-facing contract
    # is byte-identical to the legacy walk.
    if "START" not in state.graph_trace:
        state.graph_trace = ["START", *state.graph_trace]
    if "END" not in state.graph_trace:
        state.graph_trace = [*state.graph_trace, "END"]
    return state


def _walk_legacy(db: Session, state: DeepReadState) -> DeepReadState:
    """The bounded hand-rolled walk — the fallback for environments without langgraph."""
    state.graph_trace.append("START")
    route = compile_chain()
    for node_name, node in route:
        if node is None:  # END
            state.graph_trace.append("END")
            break
        if len(state.graph_trace) >= MAX_NODE_VISITS + 1:
            state.available = False
            state.error = f"graph exceeded {MAX_NODE_VISITS} node visits"
            break
        state.graph_trace.append(node_name)
        state = node(state, db)
    return state


def compute_deep_read(
    db: Session,
    question: str,
    *,
    locale: str = "en",
    filters: Filters | None = None,
) -> dict[str, Any]:
    state = DeepReadState(question=question, locale=locale if locale else "en", filters=filters)
    started = time.perf_counter()
    state = _walk_graph(db, state)

    if not state.chapters:
        payload: dict[str, Any] = {
            "question": state.question,
            "answered": False,
            "answer": state.error or "nothing in the loaded chapters supports an answer to that.",
            "chapters_used": [],
            "citations": [],
            "verify": {"ok": False, "refs": [], "repair_passes": 0},
            "graph_trace": state.graph_trace,
            "confidence": 0.0,
            "reasons": [state.error or "no chapter cleared the answer floor"],
            "demo_mode": state.demo_mode,
            "provider": state.provider,
            "model": state.model,
            "context_bytes": 0,
            "input_tokens": state.input_tokens,
            "cached_input_tokens": state.cached_input_tokens,
            "cache_reported": state.cache_reported,
            "timings_ms": {**state.timings_ms, "total": int((time.perf_counter() - started) * 1000)},
        }
        return payload

    citations = [
        {
            "type": "knowledge_document",
            "ref": chapter["ref"],
            "slug": chapter["slug"],
            "title": chapter["title"],
            "section": "full chapter",
            "source": chapter["slug"],
        }
        for chapter in state.chapters
    ]
    answer_ok = state.verify_ok and bool(state.answer)
    reasons = [
        f"gather loaded {len(state.chapters)} full chapter(s) · {state.context_bytes} bytes of context",
        f"verify: {'all refs resolve to travelling chapters' if state.verify_ok else 'refs out of range — see repair'}",
        f"answer phrased by provider '{state.provider}' from the chapters only",
    ]
    if not answer_ok:
        reasons.append("the answer does not clear the verification gate — treat every citation as unproven")
    payload = {
        "question": state.question,
        "answered": bool(state.answer) and state.available,
        "answer": state.answer,
        "chapters_used": state.chapters,
        "citations": citations,
        "verify": {"ok": state.verify_ok, "refs": state.verify_refs, "repair_passes": state.repair_passes},
        "graph_trace": state.graph_trace,
        "confidence": round(min(0.95, 0.35 + 0.12 * len(state.chapters)), 3) if answer_ok else 0.0,
        "reasons": reasons,
        "demo_mode": state.demo_mode,
        "provider": state.provider,
        "model": state.model,
        "error": state.error,
        "context_bytes": state.context_bytes,
        "input_tokens": state.input_tokens,
        "output_tokens": state.output_tokens,
        "cached_input_tokens": state.cached_input_tokens,
        "cache_reported": state.cache_reported,
        "timings_ms": {**state.timings_ms, "total": int((time.perf_counter() - started) * 1000)},
    }
    return payload
