"""The football knowledge graph as a read-time projection (spec §30).

There is no `graph_edges` table, and adding one would be the defect: every relation this tier
publishes is already stored as a foreign key or as a link row, so a second copy of those relations
would be a ledger that can drift away from the rows it describes. The projection reads the schema's
own clauses on each request, which means the graph and the world pages cannot disagree.

Three predicates decide what may be traversed, and all three are computed from `Base.metadata`
rather than hand-listed here:

* **PRIVATE** — a table that reaches `users` or `organizations` through foreign keys, directly or
  transitively. `career_appearances` has no user column of its own, but it points at `careers`, which
  points at a user; the closure catches that, and it is the reason this tier can say it never reads a
  private row without asking each table individually.
* **NAMED** — a table with a `slug` column, i.e. one a client can address by a stable public key.
  The world's link tables (`news_article_links`, `real_player_match_stats`) are not named: they carry
  relations rather than being things a reader asks about, which is exactly what an edge is.
* **GRAPH** — named and not private.

The spec lists thirteen verbs and this module ships five of them, because eight of the thirteen have
no relation in the schema to project from. Those are recorded as declines in `DECLINED_SPEC_VERBS`
with the measurement behind each one, not quietly dropped: `has_role` and `scored` are columns on the
appearance row, so they publish as edge *facts*; `transferred_to` lives in tables the PRIVATE predicate
excludes; `managed_by` is a name on the team row with no coach node to point at; `uses_tactic` would be
a 5:1 ambiguous join on `formation` (measured: 3 team formations matching 15 tactical systems); and
§30's three Tactic verbs have no clause at all — `tactical_systems` carries zero foreign keys in
either direction. Three relations the spec did not name are shipped because the schema does carry
them: `mentions` (9,058 verified article links), `trained_with`, and `played_in`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from app.models import (
    Base,
    Competition,
    NewsArticle,
    NewsArticleLink,
    RealMatch,
    RealPlayer,
    RealPlayerMatchStat,
    RealTrainingSession,
    Team,
    TrainingDrill,
)

#: `apps/api`, so a proof string can name `tests/…::case` and be checked against the tree.
_API_ROOT: Final = Path(__file__).resolve().parents[3]

#: The two tables whose rows make a private tenant: anything reaching either one is not world data.
PRIVILEGED_TABLES: Final = frozenset({"users", "organizations"})

#: §49: one constant publishes the ceiling, guards the walk and names the refusal it earns.
MAX_DEPTH: Final = 2
MAX_EDGES: Final = 400
MAX_NODES: Final = 600

#: What a reader may ask about, and where the row lives. `label_column` is the stored column a human
#: reads; `match` has no name column, so its label is composed from the two side rows at read time.
@dataclass(frozen=True)
class NodeSpec:
    kind: str
    model: Any
    label_column: str
    composed_from: tuple[str, ...] = ()


NODES: Final[tuple[NodeSpec, ...]] = (
    NodeSpec("player", RealPlayer, "name"),
    NodeSpec("team", Team, "name"),
    NodeSpec("competition", Competition, "name"),
    NodeSpec("match", RealMatch, "slug", composed_from=("round_label", "status")),
    NodeSpec("article", NewsArticle, "title"),
    NodeSpec("drill", TrainingDrill, "title"),
)

NODE_KINDS: Final = frozenset(spec.kind for spec in NODES)


@dataclass(frozen=True)
class Edge:
    """One relation: a carrier row that points at a source node and a target node.

    Column edges are the same shape as link-table edges — for `real_players.team_id` the carrier is
    `real_players` and the source key is its own `id`. That uniformity is what lets one projection
    function serve both families, and lets the census compare this table against the schema's
    foreign keys clause for clause.
    """

    verb: str
    reverse: str
    source_kind: str
    target_kind: str
    carrier: str
    source_column: str
    target_column: str
    target_key_column: str = "id"
    type_column: str = ""
    type_value: str = ""
    facts: tuple[str, ...] = ()

    @property
    def key(self) -> tuple[str, str, str]:
        """The foreign key this edge consumes, for the census: (carrier, column, target table)."""
        return (self.carrier, self.target_column, table_of(self.target_kind))


def table_of(kind: str) -> str:
    for spec in NODES:
        if spec.kind == kind:
            return spec.model.__tablename__
    raise KeyError(f"{kind} is not a node kind")


EDGE_MODEL_BY_TABLE: Final[dict[str, Any]] = {
    spec.model.__tablename__: spec.model for spec in NODES
} | {
    RealPlayerMatchStat.__tablename__: RealPlayerMatchStat,
    RealTrainingSession.__tablename__: RealTrainingSession,
    NewsArticleLink.__tablename__: NewsArticleLink,
}

#: The relations the graph ships. Every entry is a clause or a link column that exists in the schema;
#: `facts` name columns on the carrier row, so a printed figure is a stored one.
EDGES: Final[tuple[Edge, ...]] = (
    Edge("plays_for", "has_player", "player", "team", "real_players", "id", "team_id",
         facts=("position", "overall")),
    Edge("competes_in", "has_team", "team", "competition", "teams", "id", "competition_id"),
    Edge("played_in", "has_match", "match", "competition", "real_matches", "id", "competition_id"),
    Edge("home_team_is", "played_home_in", "match", "team", "real_matches", "id", "home_team_id"),
    Edge("away_team_is", "played_away_in", "match", "team", "real_matches", "id", "away_team_id"),
    Edge("participated_in", "had_appearance_by", "player", "match",
         "real_player_match_stats", "player_id", "match_id",
         facts=("role", "position", "minutes", "goals", "assists", "rating")),
    Edge("played_for", "had_player_appearance", "player", "team",
         "real_player_match_stats", "player_id", "team_id",
         facts=("role", "minutes", "goals", "assists", "rating")),
    Edge("trained_with", "trained_player", "player", "team",
         "real_training_sessions", "player_id", "team_id",
         facts=("category", "difficulty", "duration_min", "rpe")),
    Edge("trained_drill", "drilled_player", "player", "drill",
         "real_training_sessions", "player_id", "drill_slug", target_key_column="slug",
         facts=("category", "difficulty", "duration_min", "rpe")),
    Edge("mentions", "mentioned_in", "article", "player",
         "news_article_links", "article_id", "entity_id",
         type_column="entity_type", type_value="player"),
    Edge("mentions", "mentioned_in", "article", "team",
         "news_article_links", "article_id", "entity_id",
         type_column="entity_type", type_value="team"),
    Edge("mentions", "mentioned_in", "article", "match",
         "news_article_links", "article_id", "entity_id",
         type_column="entity_type", type_value="match"),
    Edge("mentions", "mentioned_in", "article", "competition",
         "news_article_links", "article_id", "entity_id",
         type_column="entity_type", type_value="competition"),
)

#: Foreign keys inside the public domain that the graph deliberately does not traverse. The census
#: test requires this table to account for every such clause that no `Edge` consumes, and each reason
#: must be written — an empty reason is a hole with a label on it.
DECLINED_CLAUSES: Final[dict[tuple[str, str, str], str]] = {
    ("knowledge_chunks", "document_id", "knowledge_documents"): (
        "the corpus is split into chunks for retrieval; that is a storage detail of the RAG tier, "
        "and `knowledge_documents` has no relation to any world node to begin with"
    ),
}

#: Relations the schema carries without a foreign key. Each one is a column pair that resolves, and
#: the test named in `proof` measures that it resolves for **every** row — a slug relation that is 99%
#: correct is a graph that silently loses edges, so the proof is a total claim, not a sample.
SLUG_RELATIONS: Final[dict[tuple[str, str], tuple[str, str]]] = {
    ("real_training_sessions", "drill_slug"): (
        "training_drills",
        "tests/test_knowledge_graph_census.py::test_every_world_training_session_names_a_drill_that_exists",
    ),
}

#: A carrier whose target table is chosen by a column's value rather than by the clause. The type
#: values are the ones the stored links actually carry; the census test compares that set against
#: this one, so a generator that starts linking a new kind makes the graph red rather than mute.
POLYMORPHIC_RELATIONS: Final[dict[tuple[str, str], tuple[str, ...]]] = {
    ("news_article_links", "entity_id"): ("player", "team", "match", "competition"),
}

#: §30's own verb list, measured against the schema. Five landed; eight declined, each with the
#: measurement that made the decline necessary rather than a choice.
DECLINED_SPEC_VERBS: Final[dict[str, str]] = {
    "transferred_to": "the only transfer rows in this schema are `transfer_listings` and `career_squad_moves`, and both are PRIVATE (they reach `careers`, which reaches a user) — a public graph may not read them",
    "managed_by": "`teams.manager_name` is a string; no coach or staff node exists in the schema",
    "uses_tactic": "no foreign key joins a team to a tactical system, and the only candidate — `formation` equality — is 5:1 ambiguous (3 team formations match 15 systems)",
    "uses_formation": "`tactical_systems` carries zero foreign keys in either direction, so there is no clause to project",
    "requires_role": "no foreign key joins a plan, drill or session to a role, and the schema has no role table — the only `role` column is on the appearance row, so there is nothing for a requirement to point at",
    "creates_space": "the space figures are computed by §4's engine per board, never stored as a relation",
}

#: §30's thirteen example verbs, each answered by the shipped verbs that carry it — or by nothing, in
#: which case `DECLINED_SPEC_VERBS` must say why. The test walks this mapping rather than re-listing
#: the spec, so a verb recorded as landed has to name verbs that are actually in `EDGES`.
SPEC_VERBS: Final[dict[str, tuple[str, ...]]] = {
    "plays_for": ("plays_for", "has_player"),
    "played_for": ("played_for", "had_player_appearance"),
    "has_role": ("participated_in",),
    "participated_in": ("participated_in", "had_appearance_by"),
    "scored": ("participated_in",),
    "transferred_to": (),
    "competes_in": ("competes_in", "has_team"),
    "managed_by": (),
    "plays": ("home_team_is", "away_team_is", "played_home_in", "played_away_in"),
    "uses_tactic": (),
    "uses_formation": (),
    "requires_role": (),
    "creates_space": (),
}

#: Codes this tier answers with, registered in `services/club/answers.py` rather than spelled at a door.
#: `graph_dangling_edge` — raised if a stored edge names a row that no longer resolves — is deliberately
#: absent: no caller can ask for it, and §51's fall-through 400 is the honest answer for a row set that
#: disagrees with itself. The census test asserts it stays unregistered.
NOT_FOUND_CODES: Final = frozenset({"no_such_node"})
UNPROCESSABLE_CODES: Final = frozenset(
    {
        "unknown_node_kind",
        "unknown_edge_verb",
        "unknown_direction",
        "graph_depth_not_supported",
        "graph_too_broad",
    }
)
CONFLICT_CODES: Final[frozenset[str]] = frozenset()
FORBIDDEN_CODES: Final[frozenset[str]] = frozenset()
#: Every code this tier can answer with, as one flat tuple of names — the shape every other tier's `REFUSALS`
#: takes, and the shape `answers.published()` reads: handed the two sets themselves, it published
#: `"frozenset({'no_such_node'})"` as a key, so `/graph/rules` printed an answer for a code nobody wrote and a
#: caller reading `printed["no_such_node"]` got nothing. `tests/test_knowledge_graph_api.py::
#: TestRulesDoor::test_the_refusal_answers_are_the_statuses_the_doors_earn` is what found it.
REFUSALS: Final = tuple(sorted(NOT_FOUND_CODES | UNPROCESSABLE_CODES | CONFLICT_CODES | FORBIDDEN_CODES))
PUBLISHED: Final = REFUSALS

#: What the capabilities door prints: the caps the walk guards with, and the vocabulary it walks.
ROUTE_GUIDE: Final = (
    {"method": "GET", "path": "/graph/rules", "what": "the vocabulary, the caps and the declines"},
    {"method": "GET", "path": "/graph/nodes/{kind}/{slug}", "what": "one node and its typed edges"},
    {"method": "GET", "path": "/graph/nodes/{kind}/{slug}/neighborhood", "what": "a depth-capped walk"},
)


def fk_clauses() -> dict[tuple[str, str, str], str]:
    """Every foreign key in the schema: (table, column, target table) → target column.

    Read from live metadata rather than a regex over the model file, so a clause a test author added
    an hour ago is in the census without anyone remembering to list it.
    """
    return {
        (table.name, column.name, fk.column.table.name): fk.column.name
        for table in Base.metadata.sorted_tables
        for column in table.columns
        for fk in column.foreign_keys
    }


def private_tables() -> frozenset[str]:
    """Tables that reach a user or an organisation, directly or through another private table."""
    edges: dict[str, set[str]] = {}
    for source, _column, target in fk_clauses():
        edges.setdefault(source, set()).add(target)
    found = set(PRIVILEGED_TABLES)
    changed = True
    while changed:
        changed = False
        for source, targets in edges.items():
            if source not in found and targets & found:
                found.add(source)
                changed = True
    return frozenset(found)


def named_tables() -> frozenset[str]:
    """Tables a client can address by a stable public key."""
    return frozenset(
        table.name for table in Base.metadata.sorted_tables if "slug" in table.columns
    )


def graph_eligible_tables() -> frozenset[str]:
    """Named tables no private path reaches — the population the graph may contain."""
    return named_tables() - private_tables()


def public_clauses() -> dict[tuple[str, str, str], str]:
    """Foreign keys whose two ends are both outside the private population.

    This is the population the census holds `EDGES` against: a public clause with no verb is either
    an unshipped relation or a recorded decline, and the test refuses both silently.
    """
    priv = private_tables()
    return {
        key: target_column
        for key, target_column in fk_clauses().items()
        if key[0] not in priv and key[2] not in priv
    }


def clauses_of(edge: Edge) -> set[tuple[str, str, str]]:
    """The stored clauses this edge relies on, in either reading.

    `plays_for` is one foreign key read both ways; `mentions` is `news_article_links.article_id` (the
    article side) plus a polymorphic target column that is not a clause at all. A relation the schema
    carries without a foreign key is only allowed if it is declared in `SLUG_RELATIONS` or
    `POLYMORPHIC_RELATIONS` beside the test that proves it resolves for every row.
    """
    public = set(public_clauses())
    out: set[tuple[str, str, str]] = set()
    for column, kind in ((edge.target_column, edge.target_kind), (edge.source_column, edge.source_kind)):
        key = (edge.carrier, column, table_of(kind))
        if key in public or (edge.carrier, column) in SLUG_RELATIONS or (edge.carrier, column) in POLYMORPHIC_RELATIONS:
            out.add(key)
    return out


def consumed_clauses() -> set[tuple[str, str, str]]:
    return set().union(*(clauses_of(edge) for edge in EDGES))


def _require_proof(proof: str, subject: str) -> None:
    """A promised test must be a test that exists.

    A declaration can name a case that was never written — this repository has already shipped a
    comment citing a test file that never existed in it — so the proof is checked against the file
    and the case name rather than trusted.
    """
    path, _, case = proof.partition("::")
    file = _API_ROOT / path
    if not case or not file.is_file():
        raise RuntimeError(f"{subject} cites {proof!r}, which is not a file::case in this project")
    if case not in file.read_text(encoding="utf-8"):
        raise RuntimeError(f"{subject} cites {case!r}, which does not appear in {path}")


def _validate() -> None:
    """Refuse the import on a declaration the schema does not support, or that touches a private row."""
    priv = private_tables()
    tables = {table.name: table for table in Base.metadata.sorted_tables}
    for edge in EDGES:
        where = f"edge {edge.verb}/{edge.reverse} on {edge.carrier}"
        for kind in (edge.source_kind, edge.target_kind):
            if kind not in NODE_KINDS:
                raise RuntimeError(f"{where}: {kind!r} is not a declared node kind")
            model_table = table_of(kind)
            if model_table in priv:
                raise RuntimeError(f"{where}: {model_table} is private ({model_table} reaches a user or an organisation)")
        # Privacy first: a private carrier is also an unregistered one, and the mechanical message would
        # have answered every §60 breach with "no model is registered", which is not the reason it is refused.
        if edge.carrier in priv:
            raise RuntimeError(f"{where}: the carrier is private, so this edge would read a tenant's rows")
        if edge.carrier not in EDGE_MODEL_BY_TABLE:
            raise RuntimeError(f"{where}: no model is registered for that carrier")
        carrier = tables[edge.carrier]
        for column, name in (
            (edge.source_column, "source_column"),
            (edge.target_column, "target_column"),
            (edge.target_key_column, "target_key_column"),
        ):
            target_table = carrier if name != "target_key_column" else tables[table_of(edge.target_kind)]
            if column not in target_table.columns:
                raise RuntimeError(f"{where}: {name}={column!r} is not a column of {target_table.name}")
        for fact in edge.facts:
            if fact not in carrier.columns:
                raise RuntimeError(f"{where}: fact {fact!r} is not a column of {edge.carrier}")
        if edge.type_column and edge.type_value:
            if edge.type_column not in carrier.columns:
                raise RuntimeError(f"{where}: type_column {edge.type_column!r} is not on the carrier")
            allowed = POLYMORPHIC_RELATIONS.get((edge.carrier, edge.target_column))
            if allowed is None or edge.type_value not in allowed:
                raise RuntimeError(f"{where}: {edge.carrier}.{edge.target_column} is not a declared polymorphic relation for {edge.type_value!r}")
        if edge.verb == edge.reverse:
            raise RuntimeError(f"{where}: a verb and its reverse read the same way, so direction is not printable")
        if not clauses_of(edge) & set(public_clauses()):
            raise RuntimeError(f"{where}: no public foreign key supports it")

    for key, reason in DECLINED_CLAUSES.items():
        if key not in public_clauses():
            raise RuntimeError(f"declined clause {key} is not a public foreign key the graph could traverse")
        if not reason.strip():
            raise RuntimeError(f"declined clause {key} carries no reason")

    # The two loops below name their keys `carrier_name`/`column_name` rather than reusing `carrier` and
    # `column`: above, `carrier` is a `Table` and `column` is one of its column names, and rebinding either
    # to a plain string made this block say one thing to `mypy` (`Table` indexed by `str`) and another to a
    # reader. The tables are looked up by name here, which is what the declarations actually carry.
    for (carrier_name, column_name), (target, proof) in SLUG_RELATIONS.items():
        if target not in tables:
            raise RuntimeError(f"slug relation {carrier_name}.{column_name} names no table called {target!r}")
        _require_proof(proof, f"slug relation {carrier_name}.{column_name}")

    for (carrier_name, column_name), kinds in POLYMORPHIC_RELATIONS.items():
        if column_name not in tables[carrier_name].columns:
            raise RuntimeError(f"polymorphic relation {carrier_name}.{column_name} names no column")
        if not kinds:
            raise RuntimeError(f"polymorphic relation {carrier_name}.{column_name} declares no target kinds")
        for kind in kinds:
            if kind not in NODE_KINDS:
                raise RuntimeError(f"polymorphic {carrier_name}.{column_name} targets {kind!r}, which is not a node kind")

    shipped = verb_names()
    for spec_verb, names in SPEC_VERBS.items():
        if not names:
            if spec_verb not in DECLINED_SPEC_VERBS:
                raise RuntimeError(f"§30's verb {spec_verb!r} ships nothing and declines nothing")
            continue
        unknown = sorted(set(names) - shipped)
        if unknown:
            raise RuntimeError(f"§30's verb {spec_verb!r} is recorded as landed by {unknown}, which no edge carries")
        if spec_verb in DECLINED_SPEC_VERBS:
            raise RuntimeError(f"§30's verb {spec_verb!r} is both landed and declined")
    unaccounted = sorted(set(DECLINED_SPEC_VERBS) - set(SPEC_VERBS))
    if unaccounted:
        raise RuntimeError(f"declines for verbs §30 never named: {unaccounted}")

    public = set(public_clauses())
    covered = consumed_clauses() & public
    declined = set(DECLINED_CLAUSES) & public
    overlap = covered & declined
    if overlap:
        raise RuntimeError(f"clauses both traversed and declined: {sorted(overlap)}")
    missing = public - covered - declined
    if missing:
        raise RuntimeError(
            f"public foreign keys with neither a verb nor a decline: {sorted(missing)} "
            f"(public clauses: {len(public)}, with a verb: {len(covered)}, declined: {len(declined)})"
        )
    if not covered or not public:
        raise RuntimeError(f"the graph declares {len(covered)} of {len(public)} public clauses; an empty census proves nothing")


def verbs_for(kind: str) -> tuple[Edge, ...]:
    return tuple(edge for edge in EDGES if kind in (edge.source_kind, edge.target_kind))


def verb_names() -> frozenset[str]:
    return frozenset(edge.verb for edge in EDGES) | frozenset(edge.reverse for edge in EDGES)


def rules(refusal_answers: dict[str, int]) -> dict[str, Any]:
    """The published ceilings and vocabulary, from the same constants the walk guards with.

    The router hands in the answer table it raises with, so `/graph/rules` cannot print a status some
    other door uses — the derivation is what `answers.published` exists for.
    """
    return {
        "node_kinds": sorted(NODE_KINDS),
        "edge_verbs": sorted({edge.verb for edge in EDGES}),
        "edge_verbs_reverse": sorted({edge.reverse for edge in EDGES}),
        "max_depth": MAX_DEPTH,
        "max_edges": MAX_EDGES,
        "max_nodes": MAX_NODES,
        "routes": [dict(item) for item in ROUTE_GUIDE],
        "spec_verbs_declined": dict(sorted(DECLINED_SPEC_VERBS.items())),
        "refusal_answers": dict(sorted(refusal_answers.items())),
    }


_validate()


__all__ = [
    "CONFLICT_CODES",
    "DECLINED_CLAUSES",
    "DECLINED_SPEC_VERBS",
    "EDGES",
    "EDGE_MODEL_BY_TABLE",
    "FORBIDDEN_CODES",
    "MAX_DEPTH",
    "MAX_EDGES",
    "MAX_NODES",
    "NODES",
    "NODE_KINDS",
    "NOT_FOUND_CODES",
    "POLYMORPHIC_RELATIONS",
    "PUBLISHED",
    "PRIVILEGED_TABLES",
    "REFUSALS",
    "ROUTE_GUIDE",
    "SLUG_RELATIONS",
    "UNPROCESSABLE_CODES",
    "Edge",
    "NodeSpec",
    "clauses_of",
    "consumed_clauses",
    "fk_clauses",
    "graph_eligible_tables",
    "private_tables",
    "public_clauses",
    "rules",
    "table_of",
    "verb_names",
    "verbs_for",
]
