"""Football Knowledge endpoints: library, search and cited answers (spec §28-§29, §62).

Every AI-shaped response carries the same envelope the coach surface uses:
`demo_mode / provider / model / confidence / reasons / sources / disclaimer`, plus the
citations the answer was built from. Retrieval statistics (backend, scanned count,
per-leg timings) travel with the results so a surprising ranking can be diagnosed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Final

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db, has_pgvector
from app.core.security import current_user, limit, new_public_id, role_refusal, standing_check
from app.core.vector_type import EMBEDDING_DIM
from app.models import AuditLog, KnowledgeChunk, KnowledgeDocument, User
from app.providers import provider_status
from app.schemas import KnowledgeAskIn, KnowledgeIngestIn, KnowledgeSearchIn
from app.services import knowledge
from app.services.model_ledger import budget_exhausted

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

DISCLAIMER = (
    "Answers are assembled from the cited football knowledge passages only. Coaching guidance, not medical "
    "advice or scouting certification; laws of the game are maintained by IFAB — check the current wording."
)

#: The standing `/knowledge/ingest` asks for, validated against the platform's own vocabulary *at import*.
#: It used to read `("admin", "staff", "operator")`, and two of those three name nothing: `core/security.ROLES`
#: holds seven account standings and `services/club/access.ROLES` holds six *tenant* standings, neither of which
#: contains `staff` or `operator`. `staff` is real in §39 as an announcement **audience** — a predicate over a
#: club roster — which is exactly the kind of word that reads like a role and answers a different question. The
#: door was therefore policy for `admin` plus a sentence about two standings no account can hold, and the day
#: somebody adds a `staff` role the sentence would start granting access without anybody editing the door.
INGEST_STANDING: Final = standing_check(("admin",))


def _budget_guard(db: Session) -> None:
    if budget_exhausted(db):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "ai_budget_exhausted", "message": "Today's AI spend cap is reached. Retrieval still works."},
        )


def _envelope(result: dict[str, Any], *, extra_sources: list[dict[str, str]] | None = None) -> dict[str, Any]:
    sources = [
        {
            "type": "knowledge_document",
            "ref": citation.get("slug", ""),
            "label": citation.get("title", ""),
            "section": citation.get("section", ""),
            "provenance": citation.get("source", ""),
        }
        for citation in result.get("citations", [])
    ]
    return {
        **result,
        "demo_mode": result.get("demo_mode", settings.is_demo_mode),
        "confidence": result.get("confidence", 0.0),
        "reasons": result.get("reasons", []),
        "sources": sources + (extra_sources or []),
        "generated_at": datetime.now(UTC).isoformat(),
        "disclaimer": result.get("disclaimer") or DISCLAIMER,
    }


def _document_dict(document: KnowledgeDocument, chunk_count: int | None = None) -> dict[str, Any]:
    return {
        "slug": document.slug,
        "title": document.title,
        "category": document.category,
        "tags": list(document.tags or []),
        "applies_to": list(document.applies_to or []),
        "difficulty": document.difficulty,
        "source": document.source_label,
        "editorial_confidence": document.editorial_confidence,
        "last_reviewed": document.last_reviewed,
        "data_origin": document.data_origin,
        "is_demo_data": document.is_demo_data,
        "char_count": document.char_count,
        "chunk_count": chunk_count if chunk_count is not None else document.chunk_count,
        "embedding_model": document.embedding_model,
        "ingested_at": document.ingested_at.isoformat() if document.ingested_at else None,
    }


@router.get("/status")
def status_snapshot(db: Session = Depends(get_db)) -> dict[str, Any]:
    stats = knowledge.corpus_stats(db)
    return {
        **stats,
        "pgvector": has_pgvector(db),
        "database_dialect": db.bind.dialect.name if db.bind else "unknown",
        "embedding_dim": EMBEDDING_DIM,
        "providers": provider_status(),
        "modes": ["semantic", "keyword", "hybrid"],
        "answer_floor": knowledge.answer.ANSWER_SCORE_FLOOR,
        "source_root": settings.knowledge_dir,
        "demo_mode": settings.is_demo_mode,
    }


@router.get("/documents")
def list_documents(
    db: Session = Depends(get_db),
    category: str | None = Query(default=None, max_length=40),
    q: str | None = Query(default=None, max_length=120),
) -> dict[str, Any]:
    stmt = select(KnowledgeDocument).order_by(KnowledgeDocument.category, KnowledgeDocument.title)
    if category:
        stmt = stmt.where(KnowledgeDocument.category == category)
    if q:
        needle = f"%{q.lower()}%"
        stmt = stmt.where(func.lower(KnowledgeDocument.title).like(needle) | func.lower(KnowledgeDocument.source_label).like(needle))
    documents = list(db.scalars(stmt).all())
    counts: dict[str, int] = {str(row[0]): int(row[1]) for row in db.execute(select(KnowledgeChunk.document_id, func.count(KnowledgeChunk.id)).group_by(KnowledgeChunk.document_id)).all()}
    return {
        "total": len(documents),
        "categories": sorted({d.category for d in documents}),
        "items": [_document_dict(d, counts.get(d.id, 0)) for d in documents],
    }


@router.get("/documents/{slug}")
def get_document(slug: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    document = db.scalar(select(KnowledgeDocument).where(KnowledgeDocument.slug == slug))
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "not_found", "message": "No such knowledge document"})
    chunks = db.scalars(select(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id).order_by(KnowledgeChunk.ordinal)).all()
    return {
        **_document_dict(document),
        "sections": [
            {
                "ordinal": chunk.ordinal,
                "heading": chunk.heading,
                "text": chunk.text,
                "char_count": chunk.char_count,
                "tags": list(chunk.tags or []),
            }
            for chunk in chunks
        ],
    }


@router.post("/search")
def search(
    body: KnowledgeSearchIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    limit(request, 60, 3600, scope="knowledge_search")
    _budget_guard(db)
    result = knowledge.search(
        db,
        body.query,
        filters=knowledge.Filters(
            category=body.category,
            position=body.position,
            difficulty=body.difficulty,
            tag=body.tag,
            document_slug=body.document_slug,
        ),
        mode=body.mode,
        top_k=body.top_k,
    ).to_dict()
    return _envelope(
        {
            **result,
            "model": provider_status()["reranker"],
            "provider": "hybrid-retrieval",
            "confidence": min(0.95, result["top_score"] * 3),
        }
    )


@router.post("/ask")
def ask(
    body: KnowledgeAskIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    limit(request, 24, 3600, scope="knowledge_ask")
    _budget_guard(db)
    result = knowledge.ask(
        db,
        body.question,
        filters=knowledge.Filters(
            category=body.category,
            position=body.position,
            difficulty=body.difficulty,
            tag=body.tag,
            document_slug=body.document_slug,
        ),
        mode=body.mode,
        top_k=body.top_k,
        user_id=user.id,
    )
    return _envelope(result.to_dict())


@router.post("/ingest")
def ingest(
    body: KnowledgeIngestIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    """Re-run ingestion over the corpus. Self-hosted / admin surface, always authenticated."""
    limit(request, 6, 3600, scope="knowledge_ingest")
    if user.role not in INGEST_STANDING:
        raise role_refusal(held=user.role, required=INGEST_STANDING, message="Only an admin account may re-ingest the corpus")
    report = knowledge.sync_knowledge(db, body.root, force=body.force)
    audit = AuditLog(
        id=new_public_id("aud"),
        user_id=user.id,
        action="knowledge.ingest",
        detail={"force": body.force, "report": report.to_dict()},
    )
    db.add(audit)
    db.commit()
    return {"report": report.to_dict(), "stats": knowledge.corpus_stats(db), "audit_id": audit.id, "ok": report.ok}
