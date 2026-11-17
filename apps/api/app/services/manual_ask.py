"""The manual's ask door — a state graph that answers questions about the product itself.

Spec §7 (the in-project manual) meets §45/§46 (the model does real work). The reader walks `/manual`;
this door lets them ask the manual the question they actually have instead of reading every word.

Four walks, compiled in order, recursion-bounded, trace always on:

    START -> classify_intent -> retrieve_sections -> spend_gate -> phrase_answer -> END

* `classify_intent` — deterministic keyword table over English (the catalogue's own words in the
  manual are English; zh readers get their questions answered the same, just routed by transliteration
  fallback to `general` focus). No model. Cold path is local and free.
* `retrieve_sections` — the MANUAL_CONTEXT constant (already baked into the prompt, so this walk only
  tags WHICH SECTIONS the question is about; it does not re-retrieve anything — the manual's whole text
  travels in the static prefix and the gateway caches it).
* `spend_gate` — the fleet's shared daily AI spend cap; past it, the door answers without the model and
  says so, loudly.
* `phrase_answer` — one provider call; the model sees exactly the manual's own English and the reader's
  question; every product claim it may make lives inside the printed spec. If they disagree, the model
  forfeits — the text is the manual, not its amplification.

Feature name for the model ledger: `manual.ask`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.providers import LlmResult, get_llm_provider
from app.services.manual_spec import MANUAL_CONTEXT
from app.services.model_ledger import budget_exhausted, record_model_call_safely

logger = logging.getLogger("football_os.manual_ask")

MAX_NODE_VISITS = 8
MAX_QUESTION_CHARS = 280

_SYSTEM = """\
You are the voice of the FOOTBALL OS manual. You see two inputs: the reader's question, and THE MANUAL,
the exact English text printed on /manual. Your task:

1. Answer the reader's question about this product in plain English, in the language the reader used —
   mirror it: English question, English answer; Chinese question, Chinese answer; Spanish question,
   Spanish answer. Never translate the text out of the reader's language.
2. Every claim about this product must live inside THE MANUAL: the five-step quickstart, the twenty-one
   doors tour, the rules, the frequently asked four, the glossary, or the closing note. If THE MANUAL
   does not cover the question, say exactly that: the manual does not cover this; point at the closest
   section it does cover (by its own heading) and say what the reader can explore.
3. Cite the section by its bold heading as printed, e.g. "The doors tour", "Frequently asked",
   "Glossary — seed" — the words the page uses, not your paraphrase of it.
4. Never invent a door, a figure, a setting, a password, or a roadmap not in THE MANUAL; the manual is
   all you know. If THE MANUAL does not name a door, a feature, or a person, it does not exist here.
5. One short paragraph. No bullet lists, no headings, no emoji.
"""

_PROMPT = """\
THE MANUAL — every section printed on /manual, in order:

{context}

THE QUESTION:
{question}

THE FOCUS THE CLASSIFIER TAGGED: {intent} — lean here first, but do not force your answer into a heading
that does not carry the evidence; the sections above are the only evidence you may use.
"""


@dataclass
class ManualAskState:
    question: str = ""
    locale: str = "en"
    intent: str = "general"
    answer: str = ""
    provider: str = "unknown"
    model: str = "unknown"
    demo_mode: bool = True
    error: str | None = None
    available: bool = False
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    cache_reported: bool = False
    latency_ms: float = 0.0
    graph_trace: list[str] = field(default_factory=list)


# ── the intent table — deterministic, keyword-routed, ordered by specificity ─────────
_INTENT_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("getting_started", ("where do i start", "how do i start", "quickstart", "new here", "getting started", "first time", "where should i begin", "what should i do first")),
    ("tour", ("tour", "what doors", "which doors", "door", "what can i explore", "explore", "navigate", "tour1", "tour2", "tour3")),
    ("glossary", ("what does", "what is a", "what is an", "glossary", "define", "means", "term")),
    ("rules", ("rule", "rules", "can i", "may i", "allowed", "permitted", "forbidden", "terms")),
    ("admin", ("admin", "password", "123", "console", "panel", "monitoring", "ledger", "analytics")),
    ("faq", ("faq", "question", "questions")),
    ("get_value", ("cost", "price", "free", "pay", "credit", "coin", "money")),
)


def _node_classify_intent(state: ManualAskState, db: Session) -> ManualAskState:  # noqa: ARG001 — the signature matches the graph nodes' shape.
    question = state.question.lower()
    for intent, needles in _INTENT_RULES:
        if any(needle in question for needle in needles):
            state.intent = intent
            return state
    state.intent = "general"
    return state


def _node_retrieve_sections(state: ManualAskState, db: Session) -> ManualAskState:  # noqa: ARG001 — the signature matches the graph nodes' shape.
    # The whole manual travels in the prompt (static prefix, cached at the gateway); this walk only
    # records the focus the classifier tagged, for the page to print. No retrieval mechanism invented.
    return state


def _node_spend_gate(state: ManualAskState, db: Session) -> ManualAskState:
    if budget_exhausted(db):
        state.error = "manual-budget-exhausted"
        state.provider = "rule-engine-demo"
        state.model = "rule-engine-demo"
        state.answer = (
            "The daily AI spend cap is reached for today, so the model did not phrase this answer. "
            "THE MANUAL still stands inside: try the quickstart (\u0027The five-step quickstart\u0027), the doors "
            "tour (\u0027The doors tour\u0027), or the glossary (\u0027Glossary\u0027) — every heading there is a door "
            "you can walk. The press returns when the meter resets."
        )
        state.demo_mode = True
        return state
    return state


def _node_phrase_answer(state: ManualAskState, db: Session) -> ManualAskState:
    if state.error == "manual-budget-exhausted":
        return state

    provider = get_llm_provider()
    prompt = _PROMPT.format(context=MANUAL_CONTEXT, question=state.question, intent=state.intent)
    try:
        result = provider.complete(
            system=_SYSTEM,
            prompt=prompt,
            max_tokens=520,
            temperature=0.35,
            prompt_cache_key="football-os/manual-ask",
        )
    except Exception as error:  # noqa: BLE001 — the gateway may die; the door must not.
        failure = LlmResult(
            text="",
            provider=getattr(provider, "name", "unknown"),
            model="unreachable",
            demo_mode=True,
            error=str(error)[:300],
            latency_ms=0,
        )
        record_model_call_safely(result=failure, feature="manual.ask")
        state.provider = failure.provider
        state.model = failure.model
        state.error = (failure.error or "unreachable gateway")[:160]
        return state

    record_model_call_safely(result=result, feature="manual.ask")
    state.input_tokens = result.input_tokens or 0
    state.output_tokens = result.output_tokens or 0
    state.cached_input_tokens = result.cached_input_tokens or 0
    state.cache_reported = bool(result.cache_reported)
    state.latency_ms = result.latency_ms or 0.0
    state.provider = result.provider
    state.model = result.model
    state.demo_mode = bool(result.demo_mode)

    if result.error:
        state.error = (result.error or "provider error")[:160]
        return state

    state.answer = (result.text or "").strip()
    state.available = True
    return state


def compile_chain() -> list[tuple[str, Any]]:
    return [
        ("classify_intent", _node_classify_intent),
        ("retrieve_sections", _node_retrieve_sections),
        ("spend_gate", _node_spend_gate),
        ("phrase_answer", _node_phrase_answer),
        ("END", None),
    ]


def compute_manual_ask(db: Session, *, question: str, locale: str = "en") -> dict[str, Any]:
    question = (question or "").strip()[:MAX_QUESTION_CHARS]
    if len(question) < 3:
        return {
            "available": False,
            "error": "the question is empty or too short — ask the manual anything about this product, in one sentence",
            "graph_trace": ["START", "END"],
        }

    state = ManualAskState(question=question, locale=locale)
    state.graph_trace.append("START")
    for node_name, node in compile_chain():
        if node is None:  # END
            state.graph_trace.append("END")
            break
        if len(state.graph_trace) >= MAX_NODE_VISITS + 1:
            state.error = f"graph walk exceeded {MAX_NODE_VISITS} node visits"
            break
        state.graph_trace.append(node_name)
        state = node(state, db)

    payload: dict[str, Any] = {
        "available": state.available,
        "intent": state.intent,
        "graph_trace": state.graph_trace,
        "provider": state.provider,
        "model": state.model,
        "demo_mode": state.demo_mode,
        "input_tokens": state.input_tokens,
        "cached_input_tokens": state.cached_input_tokens,
        "cache_reported": state.cache_reported,
        "output_tokens": state.output_tokens,
        "latency_ms": round(state.latency_ms, 1),
        "error": state.error,
    }
    if state.available:
        payload["answer"] = state.answer
    else:
        payload["answer"] = state.answer or None
    return payload


__all__ = ["MAX_NODE_VISITS", "compute_manual_ask", "compile_chain"]
