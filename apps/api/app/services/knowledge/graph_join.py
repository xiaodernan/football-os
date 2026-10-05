"""Joint retrieval (spec §30): the graph half of an answer, read beside the passages half.

`retrieval.py` decides whether a question can be answered at all — BM25 and cosine legs over the
corpus, guarded by two floors derived from `evals/golden_rag.json`. This module answers a different
question: *which stored things does this sentence name?* It reports the nodes the projection already
addresses and the relations those rows already carry, so one answer can cite a passage and a foreign
key without either half pretending to be the other.

Why the graph cannot widen recall here: `answer.ask()` consults this module only on the branch the
retriever already cleared, so a refusal is a refusal whether or not the question names a club. A hop
that could rescue a refusal would be moving those floors through the back door.

Anchoring requires the node's **whole** label in the question, not a partial overlap. `search_world`
scores any shared word, so "when should my team press" would otherwise anchor whatever club happens
to carry "press" in its summary — name coverage is the difference between naming an entity and
mentioning a football word.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from sqlalchemy.orm import Session

# Bound to the module, not to its names: `world.search` imports `knowledge.text`, so a package that
# is entered from either side finds the other half-executed.
import app.services.world.search as world_search
from app.services.knowledge.text import content_words
from app.services.knowledge_graph import project
from app.services.knowledge_graph.project import Link

#: The world-search sources whose result type is also a graph node kind. `news` is left out: the
#: graph's `article` nodes are `NewsArticle` rows, and a KB chunk is not one of them.
ANCHOR_TYPES: Final[tuple[str, ...]] = ("teams", "competitions", "players", "matches")
MAX_ANCHORS: Final = 3
MAX_CANDIDATES: Final = 30
MAX_FACTS_PER_ANCHOR: Final = 4
MAX_FIGURES_PER_FACT: Final = 3
DEMO_MARK: Final = "synthetic demo world"
REASON_PREFIX: Final = "graph:"


@dataclass(frozen=True)
class Anchor:
    """A node the question named, plus the stored relations that make the naming worth reporting."""

    kind: str
    slug: str
    label: str
    path: str
    relations: int
    facts: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "slug": self.slug,
            "label": self.label,
            "path": self.path,
            "relations": self.relations,
            "facts": list(self.facts),
            "data_origin": "synthetic",
            "is_demo_data": True,
        }

    def reason(self) -> str:
        head = (
            f"{REASON_PREFIX} the question names {self.kind} “{self.label}” at {self.path}, "
            f"which the projection reads with {self.relations} stored relation(s)"
        )
        if self.facts:
            return f"{head}: {'; '.join(self.facts)} [{DEMO_MARK}]"
        return f"{head} and none of them carries a figure [{DEMO_MARK}]"


def _figures(link: Link) -> list[str]:
    return [f"{key}={value}" for key, value in sorted(link.facts.items()) if value not in (None, "", False)][
        :MAX_FIGURES_PER_FACT
    ]


def _fact_lines(links: list[Link]) -> tuple[str, ...]:
    ordered = sorted(links, key=lambda link: (link.verb, link.other.kind, link.other.label))
    lines: list[str] = []
    for link in ordered[:MAX_FACTS_PER_ANCHOR]:
        figures = _figures(link)
        tail = f" ({', '.join(figures)})" if figures else ""
        lines.append(f"{link.verb} {link.other.kind} “{link.other.label}”{tail}")
    return tuple(lines)


def anchors(db: Session, question: str, *, limit: int = MAX_ANCHORS) -> list[Anchor]:
    """The committed nodes whose full label the sentence names, with the edges the rows already carry."""
    query_terms = set(content_words(question))
    if not query_terms:
        return []
    found = []
    for hit in world_search.search_world(db, question, types=ANCHOR_TYPES, limit=MAX_CANDIDATES):
        name_terms = set(content_words(hit.title))
        if not name_terms or not name_terms.issubset(query_terms):
            continue
        if not hit.slug:
            continue
        row = project.resolve(db, hit.type, hit.slug)
        if row is None:
            continue
        node = project.node(hit.type, row)
        _, links = project.edges_of(db, hit.type, hit.slug)
        found.append(
            Anchor(
                kind=node.kind,
                slug=node.slug,
                label=node.label,
                path=node.path,
                relations=len(links),
                facts=_fact_lines(links),
            )
        )
        if len(found) >= max(1, limit):
            break
    return found


def reason_lines(items: list[Anchor]) -> list[str]:
    return [item.reason() for item in items]


__all__ = [
    "ANCHOR_TYPES",
    "Anchor",
    "DEMO_MARK",
    "MAX_ANCHORS",
    "REASON_PREFIX",
    "anchors",
    "reason_lines",
]
