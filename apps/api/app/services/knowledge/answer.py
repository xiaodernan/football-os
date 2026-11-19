"""Context assembly and cited answers (spec §29 'Citation', §62, §77).

Demo mode is not a stub: without a language-model key the answer is an *extractive*
digest of the cited chunks, which is real content the user can act on, and the payload
says plainly that no model was called. When a key exists, the model phrases the answer
but may only use the assembled context, and the citations stay the same objects.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.core.security import new_public_id
from app.models import KnowledgeQuery
from app.providers import LlmResult, get_embedding_provider, get_llm_provider
from app.services.knowledge import answer_cache, graph_join, recall, retrieval
from app.services.knowledge.chunking import strip_header
from app.services.knowledge.library_charter import LIBRARY_CHARTER
from app.services.knowledge.retrieval import Filters, Hit
from app.services.knowledge.text import content_words
from app.services.model_ledger import record_model_call_safely

MAX_CONTEXT_CHUNKS = 12
CONTEXT_CHAR_BUDGET = 16000
ANSWER_SCORE_FLOOR = 0.12
STRONG_REFERENCE_SCORE = 0.60

# ── the house contract — constant, byte-stable, and measured on the wire (2026-11-14) ──────────────
# This is the one piece of the knowledge_ask request that is identical on every call, which is exactly
# what the gateway's automatic prefix cache needs. The prefix below was probed live against
# wkapi.pro / gpt-6-sol: a warm repeat with this block present printed `cached_tokens = 4992` of 5171
# prompt tokens (≈ 96.5 %), and the block itself is ~760 tokens. The block is the contract, not cache
# bait: every clause is the standard the knowledge surface needs. It never sees the request, so no
# per-question bytes can drift into it — a rewrite that slices this into request-time code is caught
# by tests/test_knowledge_prefix.py. Cached-token reporting at this gateway is itself flaky
# (four of six warm repeats printed a figure on 2026-11-13; ~4 of 8 at the probe on 2026-11-14):
# cached_input_tokens = 0 with cache_reported = false is *no report*, never "a cache miss".
SYSTEM_PROMPT = (
    "You are the football knowledge assistant inside FOOTBALL OS. You answer questions about the "
    "sport — tactics, rules, training science, history and culture — strictly from the numbered "
    "passages that travel with the user's question. You are not a medical professional, you are not "
    "a coach's licence, and you are not a governing body. You answer with the discipline of a "
    "reference shelf, not the confidence of a pundit.\n\n"

    "Every claim you make must come from the numbered passages. Cite them inline as [1], [2] and so "
    "on, attached directly to the claim they support. One passage may support several claims; one "
    "claim may need two citations. Never cite a passage for a claim it does not contain. A "
    "fabricated citation is the one failure this surface does not forgive.\n\n"

    "If the passages do not support an answer, say plainly that you cannot support one from the "
    "loaded material. Do not fill the gap from general knowledge, from common sense about the sport, "
    "or from memory of matches you have no access to. When you refuse, name what would be needed: a "
    "more specific question, or a document the library does not hold.\n\n"

    "Never invent or stretch a quantified claim: distances, velocities, frequencies, season counts, "
    "player ages, injury durations, percentages, prices. The only quantitative facts you may state "
    "are those printed in the passages themselves, and they must be cited as well.\n\n"

    "If the user asks about concussion, cardiac symptoms, heat stroke, severe dehydration or "
    "anything that risks life or limb, tell them to consult a qualified professional who can assess "
    "them in person, and cite what the passages offer about the risk only as background. Never call "
    "anything you return medical advice, and never diagnose.\n\n"

    "Answer in the same language as the user's question. If the question mixes scripts — Chinese "
    "characters with Latin letters, for instance — answer in the dominant script of the content, "
    "not of the greeting. Do not translate terms of art that the passages themselves use in another "
    "language; tactics vocabulary stays what the passages call it.\n\n"

    "If the question carries who is asking — a player, a captain, a coach, an analyst, a new parent "
    "watching football — keep the detail of the passages in view of that framing. Do not change the "
    "substance for the audience; change only the phrasing's altitude.\n\n"

    "Two to five sentences of body prose, written tight. A reader is likely on a phone: short "
    "paragraphs, no headers, no bullet lists. End with a single line that reads 'Sources:' followed "
    "by the references you used, in the order they first appeared, comma-separated. Nothing after "
    "that line.\n\n"

    "Plain, precise football language. Terms of art are welcome where the passages use them — "
    "demi-space, pressing trigger, build-up, rest defence, transition — never as decoration. No "
    "greetings, no encouragement, no 'Great question', no apology for refusing.\n\n"

    "Refuse briefly and honestly: financial advice wrapped as coaching; legal advice; anything about "
    "a real, identifiable private person; medicine presented as diagnosis; matters no loaded passage "
    "touches (a club's current owners, this week's transfer window, tonight's line-ups). One honest "
    "sentence, then stop.\n\n"

    "The knowledge base is this project's own corpus. The passages are authoritative because they "
    "are what loaded, not because they are universal truth. If two passages disagree, present the "
    "disagreement instead of resolving it by guessing. The player's position and level shape how you "
    "phrase the answer; they never change what the passages say.\n\n"

    "Answer only from the passages. Cite inline. Admit the gaps. Never invent. Prefer the passages "
    "to your memory of the game."
)

# The composed ask path: the library's own index leads the one static prefix the gateway already
# caches — the knowledge door's naming rail and the door-specific discipline clause follow it;
# the charter's bytes are byte-identical from byte 0 across every door that bakes it.
SYSTEM_CHARTER = LIBRARY_CHARTER + SYSTEM_PROMPT

REFUSAL = (
    "I could not find a passage in the loaded football knowledge base that supports an answer to "
    "that. Nothing was generated from outside the corpus — try a more specific question, or browse "
    "the library by category."
)

REFUSAL_ZH = (
    "我没有在已加载的足球知识库里找到能支撑这个问题答案的段落。没有任何内容来自语料之外——"
    "试试更具体的问题，或者按分类浏览知识库。"
)

DISCLAIMER_ZH = (
    "答案只来自下列列出的足球知识段落。这是训练指导性意见，不是医疗建议或球探认证；涉及规则的条款由 IFAB 维护——请查阅最新的规则文本。"
)


@dataclass
class AnswerResult:
    question: str
    answered: bool
    text: str
    digest: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    confidence: float
    reasons: list[str]
    demo_mode: bool
    provider: str
    model: str
    retrieval_backend: str
    mode: str
    scanned: int
    top_score: float
    timings_ms: dict[str, int] = field(default_factory=dict)
    disclaimer: str = ""
    #: True when the prose came out of `answer_cache` instead of a provider. The citations are
    #: always rebuilt from this call's own retrieval, so this flag describes the phrasing only.
    cached: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "answered": self.answered,
            "answer": self.text,
            "digest": self.digest,
            "citations": self.citations,
            "confidence": round(self.confidence, 3),
            "reasons": self.reasons,
            "demo_mode": self.demo_mode,
            "provider": self.provider,
            "model": self.model,
            "retrieval_backend": self.retrieval_backend,
            "mode": self.mode,
            "scanned_chunks": self.scanned,
            "top_score": round(self.top_score, 4),
            "timings_ms": self.timings_ms,
            "disclaimer": self.disclaimer,
            "answered_from_cache": self.cached,
        }


def _sentences(text: str, limit: int = 2) -> list[str]:
    body = text.split("\n", 1)[1] if "\n" in text else text
    parts = [p.strip() for p in body.replace("\n", " ").split(". ") if p.strip()]
    out: list[str] = []
    for part in parts[:limit]:
        out.append(part if part.endswith(".") else part + ".")
    return out


def _lead_body(hit: Hit) -> str:
    """The chunk text without the 'Title — Section' prefix the chunker added."""
    return strip_header(hit.text)


def assemble_context(
    hits: list[Hit],
    *,
    main: int | None = None,
    extra_budget: int = 0,
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    """Numbered passages + the extractive digest + citation objects, all from the same rows.

    Two-phase assembly: `hits[:main]` render under the plain character budget — bit-identical to
    the single-phase render this function has always done — and the remainder (the recall hop's
    pulls) render under `budget + extra_budget`, where extra_budget is the summed pull body
    length, so a budget can never evict a passage it was explicitly widened for. The default
    (main=None) renders one segment.
    """
    passages: list[str] = []
    digest: list[dict[str, Any]] = []
    citations: list[dict[str, Any]] = []
    used = 0
    window = len(hits) if main is None else main
    segments: list[tuple[list[Hit], int]] = [(hits[: min(window, MAX_CONTEXT_CHUNKS)], CONTEXT_CHAR_BUDGET)]
    if window < len(hits):
        segments.append((hits[window:], CONTEXT_CHAR_BUDGET + extra_budget))
    for segment, budget in segments:
        for hit in segment:
            body = _lead_body(hit)
            if used + len(body) > budget and passages:
                break
            ref = len(digest) + 1
            used += len(body)
            passages.append(f"[{ref}] {hit.title} — {hit.heading}\n{body}")
            digest.append({"ref": ref, "title": hit.title, "section": hit.heading, "sentences": _sentences(body, 3)})
            citation = hit.citation()
            citation["ref"] = ref
            citations.append(citation)
    return "\n\n".join(passages), digest, citations


def _confidence(hits: list[Hit], query: str, evidence_quality: float) -> tuple[float, list[str]]:
    """Explainable, not learned: score strength + term coverage + how many chunks agree.

    `evidence_quality` keeps a lexical hash embedding from claiming the same certainty a
    real semantic model would earn; the multiplier is reported in the reasons.
    """
    if not hits:
        return 0.0, ["no retrieved chunk cleared the answer floor"]
    top = hits[0]
    score_factor = min(1.0, top.score / STRONG_REFERENCE_SCORE)
    query_terms = set(content_words(query))
    coverages = []
    for hit in hits[:3]:
        chunk_terms = set(content_words(hit.text))
        coverages.append(len(query_terms & chunk_terms) / len(query_terms) if query_terms else 0.0)
    coverage = sum(coverages) / len(coverages)
    breadth = min(1.0, len(hits) / 3.0)
    raw = 0.15 + 0.50 * score_factor + 0.20 * coverage + 0.15 * breadth
    confidence = max(0.0, min(0.97, raw)) * evidence_quality
    reasons = [
        f"rerank score {top.score:.3f} → {score_factor:.0%} of the strong-match reference ({STRONG_REFERENCE_SCORE})",
        f"{coverage:.0%} of the question's content words appear in the top {len(coverages)} passage(s)",
        f"{len(hits)} independent passage(s) retrieved ({breadth:.0%} of the 3-passage agreement reference)",
        f"weighted sum ×{evidence_quality:.2f} evidence-quality factor for the '{'lexical hash' if evidence_quality < 1 else 'semantic model'}' embedding",
    ]
    return confidence, reasons


def ask(
    db: Session,
    question: str,
    *,
    filters: Filters | None = None,
    mode: str = "hybrid",
    top_k: int = 5,
    user_id: str | None = None,
    persist: bool = True,
) -> AnswerResult:
    filters = filters or Filters()
    locale = filters.locale or "en"
    filters.locale = locale
    started = time.perf_counter()
    found = retrieval.search(db, question, filters=filters, mode=mode, top_k=top_k)
    timings = dict(found.timings_ms)
    provider = get_llm_provider()
    demo_mode = bool(getattr(provider, "name", "mock") == "mock")
    embedding_name = get_embedding_provider().name
    evidence_quality = 1.0 if embedding_name != "hash-local" else 0.85

    scored = [hit for hit in found.hits if hit.score >= ANSWER_SCORE_FLOOR]
    usable = scored if found.answerable else []
    confidence, confidence_reasons = _confidence(usable, question, evidence_quality)
    context, digest, citations = assemble_context(usable) if usable else ("", [], [])

    reasons = [f"retrieval: {reason}" for reason in found.reasons] + confidence_reasons
    if usable:
        anchors = graph_join.anchors(db, question)
        reasons += graph_join.reason_lines(anchors)
        # The recall hop widens the context only after the floors have answered. `exclude` is
        # what the first pass already renders, so a pull can never duplicate a visible passage.
        hopped = recall.pulls(
            db,
            anchors,
            filters=filters,
            exclude={citation["chunk_id"] for citation in citations},
            scored=usable,
        )
        if hopped:
            context, digest, citations = assemble_context(
                usable + [pull.hit for pull in hopped],
                main=len(usable),
                extra_budget=sum(len(_lead_body(pull.hit)) for pull in hopped),
            )
            refs = {citation["chunk_id"]: citation["ref"] for citation in citations}
            hopped_ids = {pull.hit.chunk_id for pull in hopped}
            hopped_refs = {refs[chunk_id] for chunk_id in hopped_ids if chunk_id in refs}
            citations = [
                {**citation, "via": recall.VIA_GRAPH} if citation["chunk_id"] in hopped_ids else citation
                for citation in citations
            ]
            digest = [{**entry, "via": recall.VIA_GRAPH} if entry["ref"] in hopped_refs else entry for entry in digest]
            reasons += [pull.reason(refs[pull.hit.chunk_id]) for pull in hopped if pull.hit.chunk_id in refs]
    timings["ask_total"] = int((time.perf_counter() - started) * 1000)

    if not usable:
        result = AnswerResult(
            question=question,
            answered=False,
            text=REFUSAL_ZH if locale == "zh" else REFUSAL,
            digest=[],
            citations=[],
            confidence=min(0.25, confidence),
            reasons=reasons
            + (
                [f"no passage cleared the answer floor (top score {found.top_score:.3f} < {ANSWER_SCORE_FLOOR})"]
                if not scored
                else [
                    "the top passage shares too little of the question's rare vocabulary to answer honestly: "
                    f"{len(found.discriminative_matches)}/{len(found.discriminative_terms)} rare term(s) matched "
                    f"(need >= {retrieval.MIN_DISCRIMINATIVE_MATCHES}) at coverage {found.discriminative_coverage:.2f} "
                    f"(floor {retrieval.MIN_DISCRIMINATIVE_COVERAGE})"
                ]
            ),
            demo_mode=demo_mode,
            provider=provider.name,
            model=getattr(provider, "model", "template-demo"),
            retrieval_backend=found.backend,
            mode=mode,
            scanned=found.scanned,
            top_score=found.top_score,
            timings_ms=timings,
            disclaimer=("Nothing was generated from outside the loaded knowledge base."
                        if locale != "zh" else "答案的每一句话都来自已加载的足球知识库；语料之外没有生成任何内容。"),
        )
        if persist:
            _record(db, result, user_id=user_id, hit_ids=[])
        return result

    cache_served = False
    if demo_mode:
        text = _extractive_answer(question, digest)
        model_name = "extractive-no-model"
        reasons.append("no language-model key is configured, so the answer is an extractive digest of the cited passages")
    else:
        # The phrasing is a function of the question, the passages, the model and the contract — so
        # it is cacheable on exactly those four, and the citations stay this call's own. A hit costs
        # one Redis GET and zero tokens; a miss takes the per-key lane so two readers asking the same
        # new question at the same moment buy one answer rather than two.
        cache_key = answer_cache.cache_key(
            question=question,
            chunk_ids=[str(citation.get("chunk_id") or "") for citation in citations],
            model=str(getattr(provider, "model", "unknown")),
            locale=locale,
        )
        stored = answer_cache.get(cache_key)
        if stored is None:
            with answer_cache.single_flight(cache_key):
                stored = answer_cache.get(cache_key)
                if stored is None:
                    llm: LlmResult = provider.complete(
                        system=SYSTEM_CHARTER,
                        prompt=json.dumps({"intent": "knowledge_ask", "question": question, "context": context}, ensure_ascii=False),
                        max_tokens=700,
                        temperature=0.3,
                    )
                    text = llm.text.strip() or _extractive_answer(question, digest)
                    model_name = llm.model
                    record_model_call_safely(result=llm, feature="knowledge_ask", user_id=user_id)
                    demo_mode = llm.demo_mode
                    reasons.append(f"answer phrased by provider '{llm.provider}' using {len(digest)} cited passage(s) only")
                    citations = [{**c, "phrased_by": llm.model} for c in citations]
                    # A demo-mode completion is a labelled fallback, not a phrasing: caching it would
                    # pin today's failure in place after the key is fixed. An empty string is not an
                    # answer either, and `put` refuses both.
                    if not llm.demo_mode:
                        answer_cache.put(cache_key, text=text, model=llm.model, provider=llm.provider)
        if stored is not None:
            text = str(stored["text"])
            model_name = str(stored.get("model") or getattr(provider, "model", "unknown"))
            cache_served = True
            reasons.append(
                "the same question over the same passages was answered before, so the stored phrasing "
                "was reused and no provider call was made for this answer"
            )
            citations = [{**c, "phrased_by": model_name} for c in citations]

    result = AnswerResult(
        question=question,
        answered=True,
        text=text,
        digest=digest,
        citations=citations,
        confidence=confidence,
        reasons=reasons,
        demo_mode=demo_mode,
        provider=provider.name,
        model=model_name,
        retrieval_backend=found.backend,
        mode=mode,
        scanned=found.scanned,
        top_score=found.top_score,
        timings_ms=timings,
        disclaimer=("Grounded in the cited passages below. Coaching practice, not medical or scouting certification; check the current wording of any law."
                    if locale != "zh" else DISCLAIMER_ZH),
        cached=cache_served,
    )
    if persist:
        _record(db, result, user_id=user_id, hit_ids=[c["chunk_id"] if "chunk_id" in c else "" for c in citations])
    return result


def _extractive_answer(question: str, digest: list[dict[str, Any]]) -> str:
    lines = [f"What the loaded knowledge base says about “{question.strip('?').strip()}”:"]
    for entry in digest:
        body = " ".join(entry["sentences"])
        lines.append(f"[{entry['ref']}] {entry['title']} — {entry['section']}: {body}")
    lines.append("Each line quotes a stored passage; nothing here was generated from outside the corpus.")
    return "\n".join(lines)


def _record(db: Session, result: AnswerResult, *, user_id: str | None, hit_ids: list[str]) -> None:
    db.add(
        KnowledgeQuery(
            id=new_public_id("kq"),
            user_id=user_id,
            question=result.question,
            mode=result.mode,
            filters={"retrieval_backend": result.retrieval_backend, "scanned": result.scanned},
            hit_chunk_ids=[h for h in hit_ids if h],
            hit_scores=[c.get("score", 0.0) for c in result.citations],
            answered=result.answered,
            confidence=result.confidence,
            retrieval_backend=result.retrieval_backend,
            latency_ms=result.timings_ms.get("total", 0),
        )
    )
    db.commit()
