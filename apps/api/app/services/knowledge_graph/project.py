"""Reading the graph: every edge is a query over the rows that already exist (spec §30).

One function projects every edge shape, because `verbs.Edge` describes each of them in the same fields:
which row carries the relation, which column points at the source, which points at the target, what
column identifies the target (`slug` for a drill reached from a training session, `id` otherwise), what
column narrows a polymorphic carrier (`news_article_links.entity_type`), and which stored columns of
the carrier row travel with the edge as `facts`. A column edge is the case where the carrier *is* the
source row, and saying that once in the declaration is why one query builder serves both families.

Two things the projection never does:

* **Read a private table.** `verbs.private_tables()` is the closure over foreign keys that reaches a
  user or an organisation, and `verbs._validate()` refuses the import if any declared edge carries a
  private row. A route cannot ask for a relation nobody declared, and a declaration cannot be aimed at
  a career, a club or a minor's development plan without the module failing to load. §40's
  minimisation and §61's privacy boundary are structural here, not a filter a later commit forgets.
* **Shorten an answer silently.** A walk over `MAX_EDGES` edges or `MAX_NODES` nodes refuses instead of
  returning a shorter list that reads like the whole one: the caller gets the ceiling it hit and the
  two ways to stay under it (name a verb, or walk depth 1).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.services.knowledge_graph import verbs
from app.services.world.plan import web_path


class GraphRefusal(ValueError):
    """A question this tier will not answer. The code decides the status; see `answers.py`."""

    def __init__(self, code: str, message: str, **details: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, **self.details}


@dataclass(frozen=True)
class Node:
    """One addressable thing: what it is, where its page is, and what it is made of."""

    kind: str
    id: str
    slug: str
    label: str
    path: str
    data_origin: str
    is_demo_data: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "slug": self.slug,
            "label": self.label,
            "path": self.path,
            "data_origin": self.data_origin,
            "is_demo_data": self.is_demo_data,
        }


@dataclass(frozen=True)
class Link:
    """One traversed edge: the verb read from the node it was reached from, and the row that proved it."""

    verb: str
    direction: str
    other: Node
    facts: dict[str, Any]
    evidence: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "verb": self.verb,
            "direction": self.direction,
            "other": self.other.as_dict(),
            "facts": dict(self.facts),
            "evidence": dict(self.evidence),
        }


_SPEC_BY_KIND: Final[dict[str, verbs.NodeSpec]] = {spec.kind: spec for spec in verbs.NODES}
_MODEL_BY_TABLE: Final[dict[str, Any]] = verbs.EDGE_MODEL_BY_TABLE


def _spec(kind: str) -> verbs.NodeSpec:
    if kind not in _SPEC_BY_KIND:
        raise GraphRefusal(
            "unknown_node_kind",
            f"{kind!r} is not a kind this graph addresses",
            known=sorted(_SPEC_BY_KIND),
        )
    return _SPEC_BY_KIND[kind]


def _label(kind: str, row: Any) -> str:
    """The human word for a row, from that row's own stored columns.

    A match has no name column: `round_label` says when and the two goal columns say what happened,
    and a fixture that has not been played is not given a 0-0. Its two sides are not guessed at here
    either — the `home_team_is` and `away_team_is` edges name them.
    """
    if kind == "match":
        if row.status == "completed":
            return f"{row.round_label} · {row.home_goals}-{row.away_goals}"
        if row.status == "scheduled":
            return f"{row.round_label} · not played"
        raise GraphRefusal(
            "graph_status_unmodelled",
            f"a stored match carries status {row.status!r}, which this label builder does not know",
            status=row.status,
        )
    return str(getattr(row, _spec(kind).label_column))


def _node(kind: str, row: Any) -> Node:
    return Node(
        kind=kind,
        id=str(row.id),
        slug=str(row.slug),
        label=_label(kind, row),
        path=web_path(kind, str(row.slug)),
        data_origin=str(row.data_origin),
        is_demo_data=bool(row.is_demo_data),
    )


def node(kind: str, row: Any) -> Node:
    """The printable form of a stored row, or the refusal for a kind nobody declared."""
    return _node(kind, row)


def resolve(db: Session, kind: str, slug: str) -> Any:
    """The stored row for one node, or None when the world has no such slug."""
    model = _spec(kind).model
    return db.execute(select(model).where(model.__table__.c.slug == slug)).scalars().first()


def _pairs(db: Session, edge: verbs.Edge, node_id: str, direction: str) -> list[tuple[Any, Any]]:
    """(carrier row, other row) for one edge aimed at one node."""
    carrier_model = _MODEL_BY_TABLE[edge.carrier]
    carrier = carrier_model.__table__
    other_kind = edge.target_kind if direction == "out" else edge.source_kind
    other_model = _spec(other_kind).model
    other = other_model.__table__
    if direction == "out":
        on = other.c[edge.target_key_column] == carrier.c[edge.target_column]
        where = carrier.c[edge.source_column] == node_id
    else:
        on = other.c.id == carrier.c[edge.source_column]
        where = carrier.c[edge.target_column] == node_id
    if other is carrier:
        # The carrier row *is* the other side. A column edge whose carrier is one of its two node tables
        # (`real_players.team_id`, `real_matches.home_team_id`) has no separate row to join to, and
        # joining the table to itself on its own key is an `ambiguous column name` error rather than an
        # identity — measured on the first run of this projection.
        # The name is `self_stmt`, not `stmt`: the join below already declares `stmt`, and a second binding
        # of the same name in one function is the shape `mypy`'s `no-redef` refuses — correctly, since the
        # two statements are different shapes (one table, or a table joined to another).
        self_stmt = select(carrier_model).select_from(carrier).where(where)
        if edge.type_column:
            self_stmt = self_stmt.where(carrier.c[edge.type_column] == edge.type_value)
        rows = [(row, row) for row in db.execute(self_stmt).scalars().all()]
        return rows
    stmt: Select = (
        select(carrier_model, other_model)
        # The left side is named, not inferred: with two entities in the select and an explicit ON,
        # SQLAlchemy refuses to guess which table the join walks out from (`Don't know how to join to
        # RealPlayer`) on the edges whose carrier reaches the target through more than one clause.
        .select_from(carrier_model)
        .join(other_model, on)
        .where(where)
    )
    if edge.type_column:
        stmt = stmt.where(carrier.c[edge.type_column] == edge.type_value)
    return [(row[0], row[1]) for row in db.execute(stmt).all()]


def _facts(carrier_row: Any, edge: verbs.Edge) -> dict[str, Any]:
    return {name: getattr(carrier_row, name) for name in edge.facts}


def links(db: Session, row: Any, kind: str, verb: str = "", direction: str = "both") -> list[Link]:
    """Every typed edge touching one node, read from the rows that carry them."""
    found: list[Link] = []
    for edge in verbs.verbs_for(kind):
        for each in _directions(edge, kind, direction):
            name = edge.verb if each == "out" else edge.reverse
            if verb and name != verb:
                continue
            other_kind = edge.target_kind if each == "out" else edge.source_kind
            for carrier_row, other_row in _pairs(db, edge, str(row.id), each):
                found.append(
                    Link(
                        verb=name,
                        direction=each,
                        other=_node(other_kind, other_row),
                        facts=_facts(carrier_row, edge),
                        evidence={
                            "carrier": edge.carrier,
                            "row": str(carrier_row.id),
                            "column": edge.target_column if each == "out" else edge.source_column,
                        },
                    )
                )
    return found


def _directions(edge: verbs.Edge, kind: str, direction: str) -> tuple[str, ...]:
    out = []
    if direction in ("out", "both") and edge.source_kind == kind:
        out.append("out")
    if direction in ("in", "both") and edge.target_kind == kind:
        out.append("in")
    return tuple(out)


def edges_of(db: Session, kind: str, slug: str, verb: str = "", direction: str = "both") -> tuple[Any, list[Link]]:
    """The node's own row and its typed edges; both refusals a bad question earns are raised here."""
    if direction not in ("out", "in", "both"):
        raise GraphRefusal(
            "unknown_direction",
            f"{direction!r} is not a direction this graph reads; ask for out, in or both",
            asked=direction,
        )
    if verb and verb not in verbs.verb_names():
        raise GraphRefusal(
            "unknown_edge_verb",
            f"{verb!r} is not a verb this graph publishes",
            verbs=sorted(verbs.verb_names()),
        )
    row = resolve(db, kind, slug)
    if row is None:
        raise GraphRefusal(
            "no_such_node",
            f"No {kind} with slug {slug!r} in the generated world",
            kind=kind,
            slug=slug,
        )
    return row, links(db, row, kind, verb=verb, direction=direction)


def neighborhood(db: Session, kind: str, slug: str, depth: int = 1) -> dict[str, Any]:
    """A depth-capped breadth-first walk. Over a ceiling it refuses rather than trimming the answer."""
    if not 1 <= depth <= verbs.MAX_DEPTH:
        raise GraphRefusal(
            "graph_depth_not_supported",
            f"This graph promises depth 1 to {verbs.MAX_DEPTH}; {depth} is not one of them",
            max_depth=verbs.MAX_DEPTH,
            asked=depth,
        )
    start = resolve(db, kind, slug)
    if start is None:
        raise GraphRefusal(
            "no_such_node",
            f"No {kind} with slug {slug!r} in the generated world",
            kind=kind,
            slug=slug,
        )

    root_key = (kind, str(start.id))
    nodes: dict[tuple[str, str], Node] = {root_key: _node(kind, start)}
    rows: dict[tuple[str, str], Any] = {root_key: start}
    edges: list[dict[str, Any]] = []
    frontier: list[tuple[str, str]] = [root_key]
    for level in range(depth):
        nxt: list[tuple[str, str]] = []
        for key in frontier:
            each_kind, each_row = key[0], rows[key]
            for link in links(db, each_row, each_kind):
                if len(edges) + 1 > verbs.MAX_EDGES:
                    raise GraphRefusal(
                        "graph_too_broad",
                        f"This walk would answer with more than {verbs.MAX_EDGES} edges; name one verb, or ask depth 1",
                        max_edges=verbs.MAX_EDGES,
                        reached_from=f"{each_kind}/{each_row.slug}",
                    )
                other_key = (link.other.kind, link.other.id)
                edges.append({"from": f"{each_kind}/{each_row.slug}", "to": link.other.slug, "hop": level + 1, **link.as_dict()})
                if other_key not in nodes:
                    nodes[other_key] = link.other
                    other_row = resolve(db, link.other.kind, link.other.slug)
                    if other_row is None:  # an edge to a row that no longer resolves: never true of a stored clause
                        raise GraphRefusal(
                            "graph_dangling_edge",
                            f"an edge from {each_kind}/{each_row.slug} names {link.other.kind}/{link.other.slug}, which is not in the world",
                            carrier=link.evidence["carrier"],
                            row=link.evidence["row"],
                        )
                    rows[other_key] = other_row
                    nxt.append(other_key)
        if len(nodes) > verbs.MAX_NODES:
            raise GraphRefusal(
                "graph_too_broad",
                f"This walk reaches more than {verbs.MAX_NODES} nodes; name one verb, or ask depth 1",
                max_nodes=verbs.MAX_NODES,
                reached=f"{each_kind}/{each_row.slug}",
            )
        frontier = nxt
    return {
        "node": nodes[root_key].as_dict(),
        "depth": depth,
        "nodes": [node.as_dict() for node in nodes.values()],
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
    }


__all__ = ["GraphRefusal", "Link", "Node", "edges_of", "links", "neighborhood", "node", "resolve"]
