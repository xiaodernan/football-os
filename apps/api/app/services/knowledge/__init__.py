"""Football knowledge base: corpus, ingestion, hybrid retrieval and cited answers (spec §28-§29, M2)."""

from __future__ import annotations

from app.services.knowledge.answer import ask
from app.services.knowledge.ingest import corpus_stats, sync_knowledge
from app.services.knowledge.retrieval import Filters, search

__all__ = ["Filters", "ask", "corpus_stats", "search", "sync_knowledge"]
