"""spec §30's joint half: a question is answered by the passages and *named* by the graph.

Every case here is aimed at the clause the audit still records as open — that `retrieval.py` never
reads the graph, and that no golden retrieval question named a committed team or competition. The
shape being protected is narrow on purpose: the graph adds facts to an answer the retriever already
cleared, and adds nothing at all to a refusal. If the hop could rescue a refusal, it would be moving
`MIN_DISCRIMINATIVE_MATCHES` / `MIN_DISCRIMINATIVE_COVERAGE` without re-measuring them.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.services.knowledge import graph_join, retrieval
from app.services.knowledge.text import content_words
from app.services.knowledge_graph import project

GOLDEN_PATH = Path(__file__).resolve().parents[1] / "evals" / "golden_joint.json"

#: The population floor is the count the file itself carries; a case that goes missing makes this red
#: instead of quietly narrowing the scan below it.
MIN_JOINT_CASES = 8
MIN_JOINT_NEAR_MISSES = 3
#: The reach claim, not a measurement of how many *can* answer: at least one golden question must be
#: answered by the retriever and carry a graph line in the same response.
MIN_JOINT_ANSWERS = 1


@pytest.fixture()
def session() -> Iterator[Session]:
    with SessionLocal() as live:
        yield live


def _golden() -> dict[str, Any]:
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


class TestGoldenSet:
    def test_the_joint_golden_set_is_populated(self) -> None:
        data = _golden()
        queries = data["queries"]
        near = data["near_misses"]
        assert len(queries) >= MIN_JOINT_CASES, f"{GOLDEN_PATH.name} carries {len(queries)} joint cases, floor {MIN_JOINT_CASES}"
        assert len(near) >= MIN_JOINT_NEAR_MISSES, f"{GOLDEN_PATH.name} carries {len(near)} near misses, floor {MIN_JOINT_NEAR_MISSES}"
        assert queries != json.loads((GOLDEN_PATH.parent / "golden_rag.json").read_text(encoding="utf-8"))["queries"], (
            "the joint set is a copy of the RAG set: it must name nodes, which no golden_rag query does"
        )

    def test_every_golden_label_is_a_row_the_committed_world_stores(self, session: Session) -> None:
        from app.services.world import sync_world

        sync_world(session)
        for case in _golden()["queries"]:
            for node in case["expected_nodes"]:
                row = project.resolve(session, node["kind"], node["slug"])
                assert row is not None, f"case {case['id']!r} names {node['kind']}/{node['slug']}, which the synced world does not store"
                label = project.node(node["kind"], row).label
                assert label == node["label"], f"case {case['id']!r}: stored label {label!r} is not the case's {node['label']!r}"
                assert label.lower() in case["query"].lower(), f"case {case['id']!r} does not actually name {label!r}"

    def test_every_golden_question_anchors_its_declared_node(self, session: Session) -> None:
        from app.services.world import sync_world

        sync_world(session)
        for case in _golden()["queries"]:
            found = {(item.kind, item.slug) for item in graph_join.anchors(session, case["query"])}
            for node in case["expected_nodes"]:
                assert (node["kind"], node["slug"]) in found, (
                    f"case {case['id']!r} names {node['kind']}/{node['slug']} but the anchor returned {sorted(found)}"
                )

    def test_a_football_word_that_is_not_a_full_label_anchors_nothing(self, session: Session) -> None:
        from app.services.world import sync_world

        sync_world(session)
        for case in _golden()["near_misses"]:
            found = graph_join.anchors(session, case["query"])
            assert found == [], f"near miss {case['id']!r} ({case['why']}) anchored {[(a.kind, a.label) for a in found]}"


class TestSeam:
    def test_an_empty_or_punctuation_question_anchors_nothing(self, session: Session) -> None:
        assert graph_join.anchors(session, "") == []
        assert graph_join.anchors(session, "??? !!!") == []

    def test_anchor_ceiling_and_fact_shape(self, session: Session) -> None:
        from app.services.world import sync_world

        sync_world(session)
        query = "how do Braeford Athletic, Cordale Town and Corgard Town press high"
        found = graph_join.anchors(session, query)
        assert len(found) <= graph_join.MAX_ANCHORS, f"the anchor ceiling {graph_join.MAX_ANCHORS} was exceeded by {len(found)}"
        assert found, "a question naming three stored clubs anchored nothing"
        with_figures = [item for item in found if any("=" in line for line in item.facts)]
        assert with_figures, f"no anchor reported a stored figure: {[item.as_dict() for item in found]}"
        for item in found:
            assert item.path.startswith("/"), item.as_dict()
            assert item.relations == item.relations and item.relations > 0, item.as_dict()
            line = item.reason()
            assert line.startswith(graph_join.REASON_PREFIX), line
            assert graph_join.DEMO_MARK in line, f"a synthetic node was reported without the demo disclosure: {line}"


class TestFloorsUntouched:
    def test_the_measurement_derived_floors_are_what_the_rag_eval_derived(self) -> None:
        assert retrieval.MIN_DISCRIMINATIVE_MATCHES == 2
        assert retrieval.MIN_DISCRIMINATIVE_COVERAGE == 0.40
        assert not hasattr(graph_join, "answerable"), "the joint half grew its own answerability decision"

    def test_the_graph_is_consulted_only_on_the_answered_branch(self, session: Session) -> None:
        from app.services.knowledge import sync_knowledge
        from app.services.world import sync_world

        sync_knowledge(session)
        sync_world(session)
        answered_with_graph = 0
        for case in _golden()["queries"]:
            result = retrieval.search(session, case["query"])
            answer = graph_join_anchored(session, case["query"])
            if not answer["answered"]:
                assert not answer["graph_lines"], (
                    f"refusal {case['id']!r} (top score {answer['top_score']}) still carried a graph line: {answer['graph_lines']}"
                )
                continue
            assert result.answerable, f"{case['id']!r} was answered by ask() although the retriever said not answerable"
            answered_with_graph += 1
            assert answer["graph_lines"], f"answered {case['id']!r} carried no graph line: {answer['reasons']}"
        assert answered_with_graph >= MIN_JOINT_ANSWERS, (
            f"only {answered_with_graph} of {len(_golden()['queries'])} joint cases cleared the retriever, floor {MIN_JOINT_ANSWERS}"
        )

    def test_a_refusal_that_names_a_stored_node_still_refuses(self, session: Session) -> None:
        """The sole witness for 'the graph is consulted only after the retriever cleared'.

        Each control question names a club the world stores, so the anchor half *does* find a node.
        If the hop were wired into the refusal branch, these would come back answered or with a
        `graph:` line; the ordinary out-of-scope questions could not show that, because they anchor
        nothing whether or not the graph is asked.
        """
        from app.services.knowledge import sync_knowledge
        from app.services.world import sync_world

        sync_knowledge(session)
        sync_world(session)
        controls = _golden()["refusal_controls"]
        assert controls, "the joint set lost its refusal controls, so the answered-branch guard has no witness"
        for case in controls:
            found = {(item.kind, item.slug) for item in graph_join.anchors(session, case["query"])}
            for node in case["expected_nodes"]:
                assert (node["kind"], node["slug"]) in found, f"control {case['id']!r} should anchor {node['slug']}, got {sorted(found)}"
            answer = graph_join_anchored(session, case["query"])
            assert not answer["answered"], f"control {case['id']!r} was answered from the corpus, so it no longer witnesses a refusal"
            assert not answer["graph_lines"], (
                f"refusal {case['id']!r} carried a graph line ({answer['graph_lines']}); the hop widened a response the floors refused"
            )


class TestHopSubstrate:
    """Why spec §30's *recall* half is not built: the corpus and the world share no name to hop on.

    A hop needs one more thing than the anchoring half does. `graph_join` can report a node because the
    *question* names it; widening retrieval has to reach a **passage** through a node, which is only
    possible if some stored passage carries that node's label. Measured over the committed corpus and the
    synced world: no chunk body carries a player, team or competition label at all, and only two of the
    330 labels share even one word with any body — the two populations are near-disjoint vocabularies. So
    the substrate the recall half asks for is a missing relation (nothing in `verbs` links a knowledge
    document to a world entity), not a threshold to widen, and the floors in `retrieval.py` are not what
    is holding it back.

    `match` is excluded from the label population on measurement, not preference: its stored label is
    composed from `round_label` and `status`, so the only "entity" vocabulary it contributes is the words
    *match* and *game* — which is exactly what pulled a passage in when the hop was attempted, in prose
    about warm-ups. `article` and `drill` are excluded because the anchor half cannot speak through them:
    `graph_join.ANCHOR_TYPES` is the world-search sources whose rows are nodes, and neither is one.
    """

    #: The floors below are counts the scan itself reports; a population that narrows to nothing must go
    #: red here rather than turn the absence claim into a reading of an empty set.
    SUBSTRATE_KINDS = ("player", "team", "competition")
    #: Both floors are the counts the scan above reported at this landing, read out of its own failure
    #: message with the floors set above them: 330 labels over 138 passages.
    MIN_SUBSTRATE_LABELS = 330
    MIN_SUBSTRATE_CHUNKS = 138

    def test_no_committed_passage_carries_a_stored_entity_label(self, session: Session) -> None:
        from app.models import KnowledgeChunk
        from app.services.knowledge import sync_knowledge
        from app.services.knowledge.chunking import strip_header
        from app.services.knowledge_graph import project, verbs
        from app.services.world import sync_world

        sync_knowledge(session)
        sync_world(session)
        specs = [spec for spec in verbs.NODES if spec.kind in self.SUBSTRATE_KINDS]
        assert len(specs) == len(self.SUBSTRATE_KINDS), f"{verbs.NODES} declares no spec for {self.SUBSTRATE_KINDS}"

        labels = {
            project.node(spec.kind, row).label
            for spec in specs
            for row in session.scalars(select(spec.model)).all()
        }
        chunks = [(row.id, strip_header(row.text)) for row in session.scalars(select(KnowledgeChunk)).all()]
        assert len(labels) >= self.MIN_SUBSTRATE_LABELS, (
            f"the label scan read {len(labels)} entity label(s) from kinds {self.SUBSTRATE_KINDS} against "
            f"{len(chunks)} passage(s), floor {self.MIN_SUBSTRATE_LABELS}: an absence measured against almost no "
            "labels is not a measurement"
        )
        assert len(chunks) >= self.MIN_SUBSTRATE_CHUNKS, (
            f"the passage scan read {len(chunks)} chunk(s), floor {self.MIN_SUBSTRATE_CHUNKS}: an absence "
            "measured against almost no passages is not a measurement either"
        )

        chunk_terms = [(chunk_id, set(content_words(body))) for chunk_id, body in chunks]
        carried: list[str] = []
        shared_one_word: list[str] = []
        for label in sorted(labels):
            terms = set(content_words(label))
            if not terms:
                continue
            hits = [f"{label} in {chunk_id}" for chunk_id, in_body in chunk_terms if terms <= in_body]
            if hits:
                carried.extend(hits)
            elif any(terms & in_body for _, in_body in chunk_terms):
                shared_one_word.append(label)
        print(
            f"SUBSTRATE labels={len(labels)} chunks={len(chunks)} whole_label_hits={len(carried)} "
            f"labels_sharing_one_word={len(shared_one_word)} {sorted(shared_one_word)}"
        )
        assert not carried, (
            f"{len(carried)} passage(s) now carry a stored entity label ({carried[:3]}): the §30 recall hop has "
            "substrate it did not have when this case was written — build it against those rows, and re-measure the "
            "floors this case's docstring says it does not touch"
        )
        assert shared_one_word, (
            "not one entity label shares even a single word with a passage body, so this scan is comparing two "
            "populations that do not overlap at all and the absence above proves nothing about naming"
        )


def graph_join_anchored(session: Session, question: str) -> dict[str, Any]:
    """`ask()` with the graph half read out of the reasons, so the invariant is one shape to check."""
    from app.services.knowledge import answer as answer_module

    result = answer_module.ask(session, question, persist=False)
    payload = result.to_dict()
    payload["graph_lines"] = [line for line in payload["reasons"] if line.startswith(graph_join.REASON_PREFIX)]
    return payload
