"""`/graph` — the football knowledge graph as a public read surface (spec §30).

Three doors, all public: the world is fictional, so a relation between a synthetic player and a
synthetic team is nobody's private data. That is the whole reason this tier can be a read surface at
all, and it is why the projection refuses to touch a table that reaches a user or an organisation —
the moment it did, `/graph` would be an unauthenticated window into a club's records.

Every payload carries `data_origin`, `is_demo_data` and the disclaimer, the same envelope the world
routes use, so no client can render a node without rendering what it is. `edges[].evidence` names the
carrier row each edge was read from, so a caller can check an edge against the table it came from
rather than taking the projection's word for it.

`/graph/rules` prints the caps, the vocabulary and §30's declined verbs, derived from the same
declarations the walk uses — including `public_clauses` and `clauses_with_a_verb`, which are counted
by the live metadata scan the census test holds against the partition.
"""

from __future__ import annotations

from typing import Any, Final

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import limit
from app.models import WORLD_DISCLAIMER
from app.services.club import answers
from app.services.knowledge_graph import project, verbs
from app.services.world import world_ready

router = APIRouter(prefix="/graph", tags=["knowledge-graph"])

_ANSWERS: Final[dict[str, int]] = answers.ANSWERS


def _envelope(**payload: Any) -> dict[str, Any]:
    return {
        "data_origin": "synthetic",
        "is_demo_data": True,
        "demo_data": True,
        "disclaimer": WORLD_DISCLAIMER,
        **payload,
    }


def _refusal(error: project.GraphRefusal) -> HTTPException:
    """The status a code earns, from the one project-wide table — never a guess at this door."""
    return HTTPException(_ANSWERS.get(error.code, status.HTTP_400_BAD_REQUEST), detail=error.to_dict())


@router.get("/rules")
def read_rules(db: Session = Depends(get_db)) -> dict[str, Any]:
    """The vocabulary, the ceilings and the relations the schema does not support.

    Nothing here is typed by hand: the caps are the constants the walk guards with, the clause counts
    come from the live metadata scan, and `refusal_answers` is the same table `_refusal` raises with.
    """
    public = verbs.public_clauses()
    covered = verbs.consumed_clauses() & set(public)
    return _envelope(
        **verbs.rules(answers.published(verbs.REFUSALS)),
        world_ready=world_ready(db),
        public_clauses=len(public),
        clauses_with_a_verb=len(covered),
        clauses_declined=len(verbs.DECLINED_CLAUSES),
        private_tables_excluded=len(verbs.private_tables()),
        # One object per clause, with the clause spelled into a string: a dict keyed by a `(table, column,
        # target)` triple does not survive JSON, and a caller who read the coerced key back would have to
        # re-split it to learn which table the column sits on.
        declined_clauses=[
            {"clause": f"{table}.{column} -> {target}", "reason": reason}
            for (table, column, target), reason in sorted(verbs.DECLINED_CLAUSES.items())
        ],
    )


@router.get("/nodes/{kind}/{slug}")
def read_node(
    kind: str,
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
    verb: str = Query(default="", max_length=40),
    direction: str = Query(default="both", max_length=8),
) -> dict[str, Any]:
    """One node and every typed edge touching it, read from the rows that carry those relations."""
    limit(request, 120, 60, scope="graph_node")
    try:
        row, found = project.edges_of(db, kind, slug, verb=verb, direction=direction)
    except project.GraphRefusal as error:
        raise _refusal(error) from error
    touching = verbs.verbs_for(kind)
    return _envelope(
        node=project.node(kind, row).as_dict(),
        verb=verb,
        direction=direction,
        edges=[link.as_dict() for link in found],
        outgoing_count=sum(1 for link in found if link.direction == "out"),
        incoming_count=sum(1 for link in found if link.direction == "in"),
        verbs_here=sorted({edge.verb for edge in touching} | {edge.reverse for edge in touching}),
    )


@router.get("/nodes/{kind}/{slug}/neighborhood")
def read_neighborhood(
    kind: str,
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
    depth: int = Query(default=1, ge=1, le=verbs.MAX_DEPTH + 2),
) -> dict[str, Any]:
    """A breadth-first walk, capped by the ceilings `/graph/rules` prints.

    `le=MAX_DEPTH + 2` is deliberate and not a guard: it lets a caller ask *past* the ceiling so the
    answer is this tier's own refusal — with the ceiling named in it — rather than a framework 422
    about a query parameter. `graph_depth_not_supported` is what refuses.
    """
    limit(request, 30, 60, scope="graph_neighborhood")
    try:
        walked = project.neighborhood(db, kind, slug, depth=depth)
    except project.GraphRefusal as error:
        raise _refusal(error) from error
    return _envelope(**walked)
