"""Every committed corpus file ends up as exactly one corpus row, nothing more and nothing less.

Two classes of drift this suite catches:

1. **Ghost rows** — the registry holds a document whose file vanished from the tree (deleted or renamed).
2. **Stale registry** — the ingest boot skipped ingestion, leaving a fresh boot against an empty table (this case
   pins it by requiring the fresh `sync_knowledge` run to be clean, which a dirty subsystem cannot produce).

A basket commit that lands without a boot is invisible to the running process until restart. That gap is a
runtime property, not a table property, and is what `scripts/` restarts the fleet to cure. This suite exists so the
curated heart of the corpus — every committed file — reconciles against the registry exactly, on every test run.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Set

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models import KnowledgeDocument
from app.services.knowledge import sync_knowledge
from app.services.knowledge.ingest import discover, knowledge_root, parse_file


@pytest.fixture()
def db() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _committed_slugs(root) -> Set[str]:
    slugs: Set[str] = set()
    for path in discover(root):
        parsed = parse_file(path)
        slugs.add(parsed.slug)
    return slugs


def test_committed_corpus_reconciles_against_the_registry(db: Session) -> None:
    root = knowledge_root()
    committed = discover(root)
    assert committed, "no corpus shipped under the committed knowledge directory"

    report = sync_knowledge(db)
    assert report.ok, "the corpus failed to ingest: " + "; ".join(report.errors)

    stored_count = db.scalar(select(func.count(KnowledgeDocument.id))) or 0
    assert stored_count == len(committed), (
        f"the corpus ingested {stored_count} document(s), the tree ships {len(committed)}"
    )

    committed_slugs = _committed_slugs(root)
    stored_slugs = {row for row in db.scalars(select(KnowledgeDocument.slug))}
    assert stored_slugs - committed_slugs == set(), (
        f"the registry holds slug(s) the committed basket no longer ships: {sorted(stored_slugs - committed_slugs)}"
    )
    assert committed_slugs - stored_slugs == set(), (
        f"the committed basket ships slug(s) the registry never ingests: {sorted(committed_slugs - stored_slugs)}"
    )
