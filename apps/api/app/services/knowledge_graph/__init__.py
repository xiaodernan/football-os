"""The football knowledge graph (spec §30): typed relations projected from the rows that carry them.

Two layers, kept apart the way the world tier keeps its plan from its sync:

* `verbs` — the vocabulary. Which kinds a reader may name, which relation each foreign key answers to,
  which clauses the graph deliberately does not traverse, and the ceilings a walk guards. It validates
  its own declarations at import, so a relation the schema does not support cannot be shipped.
* `project` — the reading. One query builder for every edge shape, plus the depth-capped walk.

There is no graph table: the relations are already stored, and a copy of them would be a ledger that
drifts from the rows it describes.
"""

from __future__ import annotations

from app.services.knowledge_graph.project import (
    edges_of,
    links,
    neighborhood,
    resolve,
)
from app.services.knowledge_graph.types import GraphRefusal, Link, Node
from app.services.knowledge_graph.verbs import (
    EDGE_MODEL_BY_TABLE,
    EDGES,
    MAX_DEPTH,
    MAX_EDGES,
    NODE_KINDS,
    REFUSALS,
    Edge,
    consumed_clauses,
    private_tables,
    public_clauses,
    rules,
    verb_names,
    verbs_for,
)

__all__ = [
    "EDGES",
    "EDGE_MODEL_BY_TABLE",
    "MAX_DEPTH",
    "MAX_EDGES",
    "NODE_KINDS",
    "REFUSALS",
    "Edge",
    "GraphRefusal",
    "Link",
    "Node",
    "consumed_clauses",
    "edges_of",
    "links",
    "neighborhood",
    "private_tables",
    "public_clauses",
    "resolve",
    "rules",
    "verb_names",
    "verbs_for",
]
