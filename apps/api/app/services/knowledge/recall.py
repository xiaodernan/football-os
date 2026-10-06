"""The recall hop (spec §30): a stored edge pulls a passage into an already-answered context.

`graph_join.py` reports which stored nodes the question named; this module lets those nodes widen
the passages half. For every anchored node it walks the projection's edges and pulls the first
passage whose text carries the neighbour's name — so an answer about a club can carry its league,
or an answer about a player can carry the club the graph already knows they played for, without
either the retriever or the graph pretending to be the other.

Two rules keep the widening honest:

- The hop runs only after the retrieval floors have answered, and it may never rescue a refusal.
  A pull that could flip `answerable` from false to true would move those floors through the back
  door, which is why `answer.ask()` consults this module strictly inside its answered branch.
- A neighbour is hoppable only when the passage carries the name itself — the looser every-word
  rule measured degenerate in the landing probe: a match label collapses to its one common word
  ("Final · 1-0" → "final") and then any passage that merely says "final" gets attributed to it.

Chunk ids are random per ingestion, so output order is keyed to where a passage sits in its
document (slug, ordinal) — the same phrase always picks the same passage across re-ingestions.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Final

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import KnowledgeDocument
from app.services.knowledge import graph_join, retrieval
from app.services.knowledge.chunking import strip_header
from app.services.knowledge.retrieval import Filters, Hit
from app.services.knowledge_graph import project

MAX_HOP_CHUNKS: Final = 2
VIA_GRAPH: Final = "graph"
HOP_PREFIX: Final = f"{graph_join.REASON_PREFIX} hop"


@dataclass(frozen=True)
class Pull:
    """One hop: the edge it walked, the passage it reached, and why that passage counts."""

    hit: Hit
    anchor_kind: str
    anchor_label: str
    verb: str
    neighbour_kind: str
    neighbour_label: str

    def reason(self, ref: int) -> str:
        return (
            f"{HOP_PREFIX} — the question names {self.anchor_kind} “{self.anchor_label}”; "
            f"its stored edge {self.verb} reaches {self.neighbour_kind} “{self.neighbour_label}”, "
            f"and passage [{ref}] carries that name [{graph_join.DEMO_MARK}]"
        )


def _normalise(text: str) -> str:
    return " ".join(text.casefold().split())


def pulls(
    db: Session,
    items: list[graph_join.Anchor],
    *,
    filters: Filters | None = None,
    exclude: Iterable[str] = (),
    scored: Sequence[Hit] = (),
    limit: int = MAX_HOP_CHUNKS,
) -> list[Pull]:
    """First matching passage per anchored neighbour, capped at `limit`, in document order.

    `exclude` is what the reader already sees (the first-pass render window): a hop never
    duplicates it. `scored` is the retriever's own hit list, so a passage it ranked but the
    window did not render keeps its real citation when the hop rescues it. One pull per
    (anchor, neighbour) pair: the same team reached through two edge verbs is one passage.
    """
    if not items:
        return []
    population = retrieval._candidates(db, filters or Filters())
    if not population:
        return []
    known = {hit.chunk_id: hit for hit in scored}
    document_ids = {chunk.document_id for chunk in population}
    documents = {
        doc.id: doc for doc in db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.id.in_(document_ids))).all()
    }
    by_id = {chunk.id: chunk for chunk in population}
    normed = {chunk.id: _normalise(strip_header(chunk.text)) for chunk in population}
    ordered = sorted(population, key=lambda chunk: (documents[chunk.document_id].slug, chunk.ordinal))
    taken = set(exclude)
    found: list[Pull] = []
    for anchor in items:
        _, links = project.edges_of(db, anchor.kind, anchor.slug)
        pairs = sorted({(link.verb, link.other.kind, link.other.label) for link in links})
        claimed: set[tuple[str, str]] = set()
        for verb, kind, label in pairs:
            if (kind, label) in claimed:
                continue
            claimed.add((kind, label))
            phrase = _normalise(label)
            if not phrase:
                continue
            match = next((chunk.id for chunk in ordered if phrase in normed[chunk.id] and chunk.id not in taken), None)
            if match is None:
                continue
            taken.add(match)
            hit = known.get(match)
            if hit is None:
                chunk = by_id[match]
                document = documents.get(chunk.document_id)
                hit = Hit(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    document_slug=document.slug if document else "",
                    title=document.title if document else "",
                    heading=chunk.heading,
                    ordinal=chunk.ordinal,
                    category=chunk.category,
                    text=chunk.text,
                    similarity=0.0,
                    lexical=0.0,
                    score=0.0,
                    source=document.source_label if document else "",
                    applies_to=list(chunk.applies_to or []),
                    difficulty=chunk.difficulty,
                    tags=list(chunk.tags or []),
                )
            found.append(
                Pull(
                    hit=hit,
                    anchor_kind=anchor.kind,
                    anchor_label=anchor.label,
                    verb=verb,
                    neighbour_kind=kind,
                    neighbour_label=label,
                )
            )
            if len(found) >= limit:
                return found
    return found
