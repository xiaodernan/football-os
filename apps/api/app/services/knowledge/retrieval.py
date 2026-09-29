"""Hybrid retrieval + reranking for the knowledge base (spec §29, §62).

Three interchangeable legs, all filtered by the same metadata predicate so rank fusion is
comparing like with like:

* ``semantic`` — cosine distance. On PostgreSQL this is an indexed ``embedding <=> query``
  ORDER BY executed by pgvector over the ``max(top_k * 4, 20)`` nearest; on the SQLite fallback the
  same ranking is computed in-process over the same number of candidates and the response says so.
* ``keyword``  — BM25 over the chunk's content words, computed here because corpus
  statistics (document frequency, average length) are query-scoped anyway.
* ``hybrid``   — reciprocal rank fusion of the two, then a deterministic feature rerank.

The mode, the backend and every score that moved a chunk are returned, so a surprising
ranking is debuggable instead of mysterious.
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import String, func, select, text
from sqlalchemy.orm import Session

from app.core.db import has_pgvector
from app.core.vector_type import EMBEDDING_DIM
from app.models import KnowledgeChunk, KnowledgeDocument
from app.providers import get_embedding_provider, get_reranker_provider
from app.services.knowledge.chunking import strip_header
from app.services.knowledge.text import bm25_score, content_words, cosine, reciprocal_rank_fusion

CANDIDATE_SCAN_LIMIT = 4000
MIN_SIMILARITY = 0.02
MIN_USEFUL_SCORE = 0.045
# A query term is "discriminative" when it appears in at most this share of the corpus.
# Requiring the winning chunk to actually contain some of them is what separates a
# confident answer from a confident guess on a small editorial corpus.
DISCRIMINATIVE_DF_RATIO = 0.30
# Both floors come from `evals/golden_rag.json` rather than from intuition, and
# `tests/test_knowledge_rag.py::test_the_answerability_floors_sit_inside_the_measured_gap` recomputes that
# derivation from the file on every run. Measured 2026-09-30 over the shipped corpus (18 documents, 138
# chunks): all **18** in-scope questions match >=2 rare terms with coverage >=3/7 = 0.429 — `read-game`
# binds the match axis at exactly 2 and `offside` the coverage axis — while the **3** out-of-scope ones
# peak at 1 match / 1/5 = 0.20 coverage. The two figures this comment carried before (16 questions, a 0.33
# peak) had both drifted from the file, which is the reason the claim is a gate now and not a comment.
MIN_DISCRIMINATIVE_COVERAGE = 0.40
MIN_DISCRIMINATIVE_MATCHES = 2


@dataclass
class Filters:
    category: str | None = None
    position: str | None = None
    difficulty: str | None = None
    tag: str | None = None
    document_slug: str | None = None

    def describe(self) -> list[str]:
        parts = []
        if self.category:
            parts.append(f"category={self.category}")
        if self.position:
            parts.append(f"position={self.position}")
        if self.difficulty:
            parts.append(f"difficulty={self.difficulty}")
        if self.tag:
            parts.append(f"tag={self.tag}")
        if self.document_slug:
            parts.append(f"document={self.document_slug}")
        return parts

    def to_dict(self) -> dict[str, str]:
        return {
            k: v
            for k, v in {
                "category": self.category,
                "position": self.position,
                "difficulty": self.difficulty,
                "tag": self.tag,
                "document_slug": self.document_slug,
            }.items()
            if v
        }


@dataclass
class Hit:
    chunk_id: str
    document_id: str
    document_slug: str
    title: str
    heading: str
    ordinal: int
    category: str
    text: str
    similarity: float
    lexical: float
    score: float
    rank: int = 0
    features: dict[str, float] = field(default_factory=dict)
    source: str = ""
    applies_to: list[str] = field(default_factory=list)
    difficulty: str = ""
    tags: list[str] = field(default_factory=list)

    def quote(self, max_chars: int = 260) -> str:
        """A verbatim slice used in citations — never a paraphrase."""
        body = strip_header(self.text)
        if len(body) <= max_chars:
            return body.strip()
        cut = body.rfind(" ", 0, max_chars)
        return (body[: cut if cut > 120 else max_chars].rstrip()) + "…"

    def citation(self) -> dict[str, Any]:
        return {
            "type": "knowledge_chunk",
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "slug": self.document_slug,
            "title": self.title,
            "section": self.heading,
            "ordinal": self.ordinal,
            "category": self.category,
            "source": self.source,
            "quote": self.quote(),
            "score": round(self.score, 4),
            "similarity": round(self.similarity, 4),
            "ref": f"/knowledge/{self.document_slug}#{self.ordinal}",
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "document_slug": self.document_slug,
            "title": self.title,
            "heading": self.heading,
            "ordinal": self.ordinal,
            "category": self.category,
            "difficulty": self.difficulty,
            "applies_to": self.applies_to,
            "tags": self.tags,
            "score": round(self.score, 4),
            "similarity": round(self.similarity, 4),
            "lexical": round(self.lexical, 4),
            "features": {k: round(v, 4) for k, v in self.features.items()},
            "rank": self.rank,
            "excerpt": self.quote(340),
        }


@dataclass
class SearchResult:
    query: str
    mode: str
    backend: str
    hits: list[Hit]
    scanned: int
    reasons: list[str]
    timings_ms: dict[str, int]
    top_score: float = 0.0
    discriminative_terms: list[str] = field(default_factory=list)
    discriminative_matches: list[str] = field(default_factory=list)
    discriminative_coverage: float = 0.0
    answerable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "mode": self.mode,
            "retrieval_backend": self.backend,
            "scanned_chunks": self.scanned,
            "top_score": round(self.top_score, 4),
            "reasons": self.reasons,
            "timings_ms": self.timings_ms,
            "results": [hit.to_dict() for hit in self.hits],
            "citations": [hit.citation() for hit in self.hits],
            "answerability": {
                "answerable": self.answerable,
                "discriminative_terms": self.discriminative_terms,
                "discriminative_matches": self.discriminative_matches,
                "discriminative_coverage": round(self.discriminative_coverage, 3),
                "df_ratio_limit": DISCRIMINATIVE_DF_RATIO,
                "coverage_floor": MIN_DISCRIMINATIVE_COVERAGE,
                "match_floor": MIN_DISCRIMINATIVE_MATCHES,
            },
        }


def _vector_literal(vector: list[float]) -> str:
    return json.dumps([round(float(v), 6) for v in vector])


def _where(filters: Filters) -> tuple[str, dict[str, Any]]:
    """Parameterised metadata predicate; mirrors `_candidates` so both legs see one universe."""
    clauses: list[str] = []
    params: dict[str, Any] = {}
    if filters.category:
        clauses.append("kc.category = :category")
        params["category"] = filters.category
    if filters.difficulty:
        clauses.append("kc.difficulty = :difficulty")
        params["difficulty"] = filters.difficulty
    if filters.position:
        clauses.append("lower(CAST(kc.applies_to AS TEXT)) LIKE :position")
        params["position"] = f'%"{filters.position}"%'
    if filters.tag:
        clauses.append("lower(CAST(kc.tags AS TEXT)) LIKE :tag")
        params["tag"] = f'%"{filters.tag}"%'
    if filters.document_slug:
        clauses.append("kd.slug = :document_slug")
        params["document_slug"] = filters.document_slug
    return (" AND " + " AND ".join(clauses) if clauses else ""), params


def _json_contains(column: Any, needle: str) -> Any:
    """Portable 'this JSON array contains that value' test: cast to text, LIKE the quoted token."""
    return func.lower(func.cast(column, String)).like(f'%"{needle.lower()}"%')


def _candidates(db: Session, filters: Filters) -> list[KnowledgeChunk]:
    stmt = select(KnowledgeChunk).join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id).limit(CANDIDATE_SCAN_LIMIT)
    if filters.category:
        stmt = stmt.where(KnowledgeChunk.category == filters.category)
    if filters.difficulty:
        stmt = stmt.where(KnowledgeChunk.difficulty == filters.difficulty)
    if filters.position:
        stmt = stmt.where(_json_contains(KnowledgeChunk.applies_to, filters.position))
    if filters.tag:
        stmt = stmt.where(_json_contains(KnowledgeChunk.tags, filters.tag))
    if filters.document_slug:
        stmt = stmt.where(KnowledgeDocument.slug == filters.document_slug)
    return list(db.scalars(stmt).all())


def _semantic_ranking(db: Session, query_vector: list[float], filters: Filters, candidate_ids: set[str], top_k: int) -> tuple[list[str], dict[str, float], str]:
    """The pgvector leg. Returns ([], {}, 'vector-python') when the extension is not in play,
    in which case the caller computes cosine in-process over the same candidate set."""
    if not has_pgvector(db) or not candidate_ids:
        return [], {}, "vector-python"
    clause, params = _where(filters)
    params["qvec"] = _vector_literal(query_vector)
    params["leg_limit"] = max(top_k * 4, 20)
    sql = (
        "SELECT kc.id AS id, 1 - (kc.embedding <=> CAST(:qvec AS vector)) AS similarity "
        "FROM knowledge_chunks kc JOIN knowledge_documents kd ON kd.id = kc.document_id "
        f"WHERE 1=1{clause} ORDER BY kc.embedding <=> CAST(:qvec AS vector) LIMIT :leg_limit"
    )
    try:
        rows = db.execute(text(sql), params).all()
    except Exception:  # a missing extension must degrade, not 500
        db.rollback()
        return [], {}, "vector-python"
    similarities = {str(row.id): float(row.similarity) for row in rows}
    ranking = [str(row.id) for row in rows if str(row.id) in candidate_ids]
    return (ranking, similarities, "pgvector") if ranking else ([], similarities, "vector-python")


def search(
    db: Session,
    query: str,
    *,
    filters: Filters | None = None,
    mode: str = "hybrid",
    top_k: int = 5,
) -> SearchResult:
    started = time.perf_counter()
    filters = filters or Filters()
    mode = mode if mode in ("semantic", "keyword", "hybrid") else "hybrid"
    timings: dict[str, int] = {}

    load_started = time.perf_counter()
    chunks = _candidates(db, filters)
    documents = {document.id: document for document in db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.id.in_({c.document_id for c in chunks} or {""}))).all()}
    timings["load"] = int((time.perf_counter() - load_started) * 1000)

    if not chunks:
        return SearchResult(
            query=query,
            mode=mode,
            backend="none",
            hits=[],
            scanned=0,
            reasons=["no chunks matched the metadata filters — nothing was retrieved"],
            timings_ms=timings,
        )

    query_vector: list[float] = []
    vector_started = time.perf_counter()
    if mode in ("semantic", "hybrid"):
        provider = get_embedding_provider()
        vectors = provider.embed([query])
        query_vector = vectors[0] if vectors else []
    timings["embed_query"] = int((time.perf_counter() - vector_started) * 1000)

    terms_by_chunk = {c.id: {str(k): float(v) for k, v in (c.terms or {}).items()} for c in chunks}
    lengths = {c.id: max(1, c.token_estimate or 1) for c in chunks}
    total_docs = len(chunks)
    avg_length = sum(lengths.values()) / total_docs
    df: dict[str, int] = {}
    for doc_terms in terms_by_chunk.values():
        for term in doc_terms:
            df[term] = df.get(term, 0) + 1
    query_terms = {t: 1.0 / math.log1p(len(t)) for t in dict.fromkeys(content_words(query))}

    score_started = time.perf_counter()
    lexical_scores = {c.id: bm25_score(query_terms, terms_by_chunk[c.id], doc_length=lengths[c.id], avg_doc_length=avg_length, df=df, total_docs=total_docs) for c in chunks}
    keyword_ranking = [cid for cid, _ in sorted(lexical_scores.items(), key=lambda kv: (-kv[1], kv[0])) if lexical_scores[cid] > 0]

    similarities: dict[str, float] = {}
    semantic_ranking: list[str] = []
    backend = "none"
    if mode in ("semantic", "hybrid"):
        native_ids, native_sims, native_backend = _semantic_ranking(db, query_vector, filters, {c.id for c in chunks}, top_k)
        similarities.update(native_sims)
        if native_backend == "pgvector" and native_ids:
            semantic_ranking = native_ids
            backend = "pgvector"
        else:
            for chunk in chunks:
                similarities[chunk.id] = cosine(query_vector, [float(v) for v in (chunk.embedding or [])][:EMBEDDING_DIM])
            # The same window the SQL leg asks for, not every candidate above the similarity floor.
            # Rank fusion is only comparable across engines if both legs hand it the same population:
            # with all 138 ids fused, the tail (chunks at similarity 0.02) displaced the expected
            # document for `when-to-press` out of the top 5 and drove `hybrid_delta` to -0.0556, while
            # the pgvector leg over the same corpus kept it at rank 4 with delta 0.0.
            semantic_ranking = [cid for cid, _ in sorted(similarities.items(), key=lambda kv: (-kv[1], kv[0])) if similarities[cid] > MIN_SIMILARITY][: max(top_k * 4, 20)]
            backend = "vector-python"
    timings["score"] = int((time.perf_counter() - score_started) * 1000)

    if mode == "semantic":
        fused = {cid: 1.0 / (i + 1) for i, cid in enumerate(semantic_ranking)}
        shortlist = semantic_ranking[: max(top_k * 4, 20)]
    elif mode == "keyword":
        fused = {cid: 1.0 / (i + 1) for i, cid in enumerate(keyword_ranking)}
        shortlist = keyword_ranking[: max(top_k * 4, 20)]
        backend = "bm25-python"
    else:
        fused = reciprocal_rank_fusion([semantic_ranking, keyword_ranking])
        shortlist = [cid for cid, _ in sorted(fused.items(), key=lambda kv: (-kv[1], kv[0]))][: max(top_k * 4, 20)]
        backend = f"hybrid-{backend}"

    by_id = {c.id: c for c in chunks}
    candidates: list[dict[str, Any]] = []
    for chunk in [by_id[cid] for cid in shortlist if cid in by_id]:
        document = documents.get(chunk.document_id)
        candidates.append(
            {
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "document_slug": document.slug if document else "",
                "title": document.title if document else "",
                "heading": chunk.heading,
                "ordinal": chunk.ordinal,
                "category": chunk.category,
                "text": chunk.text,
                "similarity": similarities.get(chunk.id, 0.0),
                "lexical": lexical_scores.get(chunk.id, 0.0),
                "fused": fused.get(chunk.id, 0.0),
                "terms": terms_by_chunk.get(chunk.id, {}),
                "token_estimate": lengths.get(chunk.id, 1),
                "source": document.source_label if document else "",
                "applies_to": list(chunk.applies_to or []),
                "difficulty": chunk.difficulty,
                "tags": list(chunk.tags or []),
            }
        )

    rerank_started = time.perf_counter()
    reranker = get_reranker_provider()
    ranked = reranker.rerank(
        query=query,
        candidates=candidates,
        query_terms=query_terms,
        df=df,
        total_docs=total_docs,
        avg_doc_length=avg_length,
    )
    timings["rerank"] = int((time.perf_counter() - rerank_started) * 1000)

    kept = [row for row in ranked if row["rerank_score"] >= MIN_USEFUL_SCORE or row["similarity"] > 0.2][:top_k]
    hits: list[Hit] = []
    for index, row in enumerate(kept, start=1):
        hits.append(
            Hit(
                chunk_id=row["chunk_id"],
                document_id=row["document_id"],
                document_slug=row["document_slug"],
                title=row["title"],
                heading=row["heading"],
                ordinal=row["ordinal"],
                category=row["category"],
                text=row["text"],
                similarity=row["similarity"],
                lexical=row["lexical"],
                score=row["rerank_score"],
                rank=index,
                features=dict(row.get("features", {})),
                source=row["source"],
                applies_to=list(row["applies_to"]),
                difficulty=row["difficulty"],
                tags=list(row["tags"]),
            )
        )

    reasons = [
        f"{mode} retrieval over {total_docs} filtered chunk(s) using {backend}",
        f"rerank kept {len(hits)} of {len(ranked)} candidates at score >= {MIN_USEFUL_SCORE}",
    ]
    if hits:
        reasons.append("top match: “" + hits[0].title + " — " + hits[0].heading + f"” (rerank {hits[0].score:.3f}, cosine {hits[0].similarity:.3f}, bm25 {hits[0].lexical:.2f})")
    if filters.describe():
        reasons.append("metadata filter: " + ", ".join(filters.describe()))

    # Answerability: does the winning chunk contain a real share of the question's rare words?
    # Bare numbers are skipped — "10" or "2019" recurs in unrelated prose and cannot carry a topic.
    df_ceiling = max(1, int(total_docs * DISCRIMINATIVE_DF_RATIO))
    discriminative = sorted(term for term in query_terms if 0 < df.get(term, 0) <= df_ceiling and not term.isdigit())
    matched: list[str] = []
    coverage = 0.0
    if hits and discriminative:
        top_terms = set(terms_by_chunk.get(hits[0].chunk_id, {}))
        matched = [term for term in discriminative if term in top_terms]
        coverage = len(matched) / len(discriminative)
        reasons.append(
            f"{len(matched)}/{len(discriminative)} of the question's rare terms (df <= {df_ceiling} chunks) "
            f"appear in the top passage → {'answerable' if coverage >= MIN_DISCRIMINATIVE_COVERAGE and len(matched) >= MIN_DISCRIMINATIVE_MATCHES else 'refuse'}"
        )
    elif hits:
        reasons.append("the question shares no rare term with the corpus, so it cannot be grounded")
    answerable = bool(hits) and len(matched) >= MIN_DISCRIMINATIVE_MATCHES and coverage >= MIN_DISCRIMINATIVE_COVERAGE

    timings["total"] = int((time.perf_counter() - started) * 1000)
    return SearchResult(
        query=query,
        mode=mode,
        backend=backend,
        hits=hits,
        scanned=total_docs,
        reasons=reasons,
        timings_ms=timings,
        top_score=hits[0].score if hits else 0.0,
        discriminative_terms=discriminative,
        discriminative_matches=matched,
        discriminative_coverage=coverage,
        answerable=answerable,
    )
