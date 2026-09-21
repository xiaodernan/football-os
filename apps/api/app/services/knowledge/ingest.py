"""Ingestion: markdown corpus → cleaned chunks → embeddings → queryable rows (spec §29).

Idempotent by content hash, so booting the API re- ingests only what changed. A file that
fails to parse is a hard error in the report rather than a silent skip — a half-loaded
knowledge base is worse than an obviously broken boot.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import new_public_id
from app.models import EMBEDDING_DIM, KnowledgeChunk, KnowledgeDocument, utcnow
from app.providers import get_embedding_provider
from app.services.knowledge import chunking
from app.services.knowledge.chunking import ParsedDocument
from app.services.knowledge.text import term_frequencies

VALID_APPLIES_TO = ("goalkeeper", "defender", "midfielder", "forward", "all")


@dataclass
class IngestReport:
    source_root: str = ""
    documents_seen: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    removed: int = 0
    chunks_written: int = 0
    embedding_model: str = ""
    embedding_dim: int = EMBEDDING_DIM
    elapsed_ms: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_root": self.source_root,
            "documents_seen": self.documents_seen,
            "created": self.created,
            "updated": self.updated,
            "unchanged": self.unchanged,
            "removed": self.removed,
            "chunks_written": self.chunks_written,
            "embedding_model": self.embedding_model,
            "embedding_dim": self.embedding_dim,
            "elapsed_ms": self.elapsed_ms,
            "errors": self.errors,
        }


def knowledge_root(explicit: str | Path | None = None) -> Path:
    return Path(explicit or settings.knowledge_dir).resolve()


def discover(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*.md") if p.is_file() and p.name.lower() != "readme.md")


def parse_file(path: Path) -> ParsedDocument:
    document = chunking.parse_document(path.read_text(encoding="utf-8"), path=str(path))
    unknown = [p for p in document.applies_to if p not in VALID_APPLIES_TO]
    if unknown:
        raise chunking.KnowledgeDocumentError(f"unknown applies_to values: {', '.join(unknown)}")
    if not document.sections:
        raise chunking.KnowledgeDocumentError("document has no body sections")
    return document


def sync_knowledge(db: Session, root: str | Path | None = None, *, force: bool = False) -> IngestReport:
    """Upsert every markdown document under `root` and delete rows whose source vanished."""
    started = time.perf_counter()
    base = knowledge_root(root)
    provider = get_embedding_provider()
    report = IngestReport(source_root=str(base), embedding_model=provider.name)
    if not base.is_dir():
        report.errors.append(f"knowledge directory not found: {base}")
        report.elapsed_ms = int((time.perf_counter() - started) * 1000)
        return report

    paths = discover(base)
    report.documents_seen = len(paths)
    seen_slugs: set[str] = set()

    for path in paths:
        try:
            document = parse_file(path)
        except (chunking.KnowledgeDocumentError, UnicodeDecodeError, OSError) as exc:
            report.errors.append(f"{path.name}: {exc}")
            continue
        if document.slug in seen_slugs:
            report.errors.append(f"{path.name}: duplicate document id '{document.slug}'")
            continue
        seen_slugs.add(document.slug)

        existing = db.scalar(select(KnowledgeDocument).where(KnowledgeDocument.slug == document.slug))
        if existing is not None and not force and existing.content_hash == document.content_hash:
            report.unchanged += 1
            continue

        chunks = chunking.chunk_document(document)
        if not chunks:
            report.errors.append(f"{path.name}: produced no chunks")
            continue
        vectors = provider.embed([chunk.text for chunk in chunks])
        if len(vectors) != len(chunks):
            report.errors.append(f"{path.name}: embedding count {len(vectors)} != chunk count {len(chunks)}")
            continue
        dim = len(vectors[0])
        report.embedding_dim = dim

        rows: list[KnowledgeChunk] = []
        for chunk, vector in zip(chunks, vectors, strict=True):
            rows.append(
                KnowledgeChunk(
                    id=new_public_id("kch"),
                    ordinal=chunk.ordinal,
                    heading=chunk.heading[:300],
                    text=chunk.text,
                    haystack=chunk.text.lower(),
                    category=document.category,
                    applies_to=list(document.applies_to),
                    difficulty=document.difficulty,
                    tags=list(document.tags),
                    terms={str(k): float(v) for k, v in term_frequencies(chunk.text).items()},
                    char_count=chunk.char_count,
                    token_estimate=chunk.token_estimate,
                    text_hash=chunk.text_hash,
                    embedding=[float(v) for v in vector],
                    embedding_model=provider.name,
                )
            )

        if existing is None:
            existing = KnowledgeDocument(id=new_public_id("kdoc"), slug=document.slug)
            db.add(existing)
            report.created += 1
        else:
            report.updated += 1

        existing.title = document.title
        existing.category = document.category
        existing.tags = list(document.tags)
        existing.applies_to = list(document.applies_to)
        existing.difficulty = document.difficulty
        existing.source_label = document.source_label[:400]
        existing.editorial_confidence = document.confidence
        existing.last_reviewed = document.last_reviewed
        existing.source_path = str(path.relative_to(base)).replace("\\", "/")
        existing.content_hash = document.content_hash
        existing.embedding_model = provider.name
        existing.char_count = len(document.body_markdown)
        existing.chunk_count = len(rows)
        existing.data_origin = "project-authored"
        existing.is_demo_data = False
        existing.ingested_at = utcnow()
        # Replace, never append. One flush would insert the new ordinals before deleting the old
        # rows with the same (document_id, ordinal), tripping uq_chunk_document_ordinal — so the
        # stale rows are cleared and flushed first.
        existing.chunks = []
        db.flush()
        existing.chunks = rows
        report.chunks_written += len(rows)

    for stored in db.scalars(select(KnowledgeDocument)).all():
        if stored.slug not in seen_slugs:
            db.delete(stored)
            report.removed += 1

    db.commit()
    report.elapsed_ms = int((time.perf_counter() - started) * 1000)
    return report


def corpus_stats(db: Session) -> dict[str, Any]:
    """What is actually loaded — the API and the eval harness quote these numbers."""
    from sqlalchemy import func

    documents = db.scalars(select(KnowledgeDocument).order_by(KnowledgeDocument.slug)).all()
    categories: dict[str, int] = {}
    for document in documents:
        categories[document.category] = categories.get(document.category, 0) + 1
    return {
        "documents": len(documents),
        "chunks": int(db.scalar(select(func.count(KnowledgeChunk.id))) or 0),
        "categories": categories,
        "embedding_models": sorted({d.embedding_model for d in documents if d.embedding_model}),
        "characters": sum(d.char_count for d in documents),
        "sources": sorted({d.source_label for d in documents if d.source_label}),
    }
