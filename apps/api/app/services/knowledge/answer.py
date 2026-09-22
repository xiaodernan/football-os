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
from app.services.knowledge import retrieval
from app.services.knowledge.chunking import strip_header
from app.services.knowledge.retrieval import Filters, Hit
from app.services.knowledge.text import content_words
from app.services.model_ledger import record_model_call

MAX_CONTEXT_CHUNKS = 4
CONTEXT_CHAR_BUDGET = 3200
ANSWER_SCORE_FLOOR = 0.12
STRONG_REFERENCE_SCORE = 0.60

SYSTEM_PROMPT = (
    "You are the football knowledge assistant inside FOOTBALL OS. Answer only from the numbered "
    "passages provided, cite them inline as [1], [2], keep the player's position and level in mind, "
    "and say what you cannot support from the passages instead of inventing it. Never present "
    "coaching practice as a research finding, and never invent statistics."
)

REFUSAL = (
    "I could not find a passage in the loaded football knowledge base that supports an answer to "
    "that. Nothing was generated from outside the corpus — try a more specific question, or browse "
    "the library by category."
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


def assemble_context(hits: list[Hit]) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    """Numbered passages + the extractive digest + citation objects, all from the same rows."""
    passages: list[str] = []
    digest: list[dict[str, Any]] = []
    citations: list[dict[str, Any]] = []
    used = 0
    for index, hit in enumerate(hits[:MAX_CONTEXT_CHUNKS], start=1):
        body = _lead_body(hit)
        if used + len(body) > CONTEXT_CHAR_BUDGET and passages:
            break
        used += len(body)
        passages.append(f"[{index}] {hit.title} — {hit.heading}\n{body}")
        digest.append({"ref": index, "title": hit.title, "section": hit.heading, "sentences": _sentences(body, 3)})
        citation = hit.citation()
        citation["ref"] = index
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
    timings["ask_total"] = int((time.perf_counter() - started) * 1000)

    if not usable:
        result = AnswerResult(
            question=question,
            answered=False,
            text=REFUSAL,
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
            disclaimer="Nothing was generated from outside the loaded knowledge base.",
        )
        if persist:
            _record(db, result, user_id=user_id, hit_ids=[])
        return result

    if demo_mode:
        text = _extractive_answer(question, digest)
        model_name = "extractive-no-model"
        reasons.append("no language-model key is configured, so the answer is an extractive digest of the cited passages")
    else:
        llm: LlmResult = provider.complete(
            system=SYSTEM_PROMPT,
            prompt=json.dumps({"intent": "knowledge_ask", "question": question, "context": context}, ensure_ascii=False),
            max_tokens=700,
            temperature=0.3,
        )
        text = llm.text.strip() or _extractive_answer(question, digest)
        model_name = llm.model
        record_model_call(db, result=llm, feature="knowledge_ask", user_id=user_id)
        demo_mode = llm.demo_mode
        reasons.append(f"answer phrased by provider '{llm.provider}' using {len(digest)} cited passage(s) only")
        citations = [{**c, "phrased_by": llm.model} for c in citations]

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
        disclaimer=("Grounded in the cited passages below. Coaching practice, not medical or scouting certification; check the current wording of any law."),
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
