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
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.services.knowledge import graph_join, retrieval
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


def graph_join_anchored(session: Session, question: str) -> dict[str, Any]:
    """`ask()` with the graph half read out of the reasons, so the invariant is one shape to check."""
    from app.services.knowledge import answer as answer_module

    result = answer_module.ask(session, question, persist=False)
    payload = result.to_dict()
    payload["graph_lines"] = [line for line in payload["reasons"] if line.startswith(graph_join.REASON_PREFIX)]
    return payload
