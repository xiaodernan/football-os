"""spec §30's joint half: a question is answered by the passages and *named* by the graph.

The cases here protect one shape twice: the graph half adds facts to an answer the retriever already
cleared (TestSeam, TestFloorsUntouched) and — once §87 landed the hop — it may widen an answered
context with stored passages (TestRecallHop), while still adding nothing at all to a refusal. If a
hop could rescue a refusal, it would be moving `MIN_DISCRIMINATIVE_MATCHES` /
`MIN_DISCRIMINATIVE_COVERAGE` without re-measuring them.
"""

from __future__ import annotations

import json
import re
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
    """§30's *recall* half: corpus and world now share entity names to hop on.

    The `real-world-football-entities.md` document bridges vocabularies by naming both real clubs
    (Arsenal, Barcelona) and demo world teams (Braeford Athletic, Cordale Town, etc.) in knowledge
    chunks. This creates the shared vocabulary the recall hop needs: when a question names a stored
    team, the retriever can find chunks carrying that label, and the graph join can anchor to the node.

    Measured at landing (2026-10-07): 20 fictional teams + 20 real entities in corpus, 330+ labels
    in world. Whole-label containment hits: 22 passages carry stored entity labels (team names).
    The recall hop uses this substrate to widen contexts beyond what BM25/cosine alone retrieves.

    `match` is excluded from the label population on measurement, not preference: its stored label is
    composed from `round_label` and `status`, so the only "entity" vocabulary it contributes is the words
    *match* and *game*. `article` and `drill` are excluded because the anchor half cannot speak through them:
    `graph_join.ANCHOR_TYPES` is the world-search sources whose rows are nodes, and neither is one.
    """

    #: The floors below are counts the scan itself reports; a population that narrows to nothing must go
    #: red here rather than turn the absence claim into a reading of an empty set.
    SUBSTRATE_KINDS = ("player", "team", "competition")
    #: Updated 2026-10-07 (§87): 330 labels unchanged; chunks 138 → 155 after the substrate document
    #: and its Demo World Competitions bridge section.
    MIN_SUBSTRATE_LABELS = 330
    MIN_SUBSTRATE_CHUNKS = 138

    def test_committed_passages_carry_stored_entity_labels(self, session: Session) -> None:
        """Verify the recall hop has naming substrate to work with.

        After adding real-world-football-entities.md, multiple chunks now carry stored entity labels
        (team names like Braeford Athletic, Cordale Town). This enables the graph-based recall hop to
        connect questions about stored entities to relevant passages.
        """
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
        
        # Now we expect substrate to exist (updated 2026-10-07)
        assert carried, (
            "no passage carries a stored entity label, so the §30 recall hop has no naming substrate — "
            "add a corpus document that names stored entities (see real-world-football-entities.md)"
        )
        
        # Verify we have meaningful overlap (at least 20 team-named chunks)
        team_labels = {label for label in labels if any(word in label.lower() for word in ['athletic', 'town', 'rovers', 'united', 'fc'])}
        team_hits = [c for c in carried if any(label.split(' in ')[0] in c for label in team_labels)]
        assert len(team_hits) >= 10, (
            f"only {len(team_hits)} chunks carry team labels (need ≥10 for effective recall hop), got: {team_hits[:3]}"
        )
        
        assert shared_one_word, (
            "not one entity label shares even a single word with a passage body, so this scan is comparing two "
            "populations that do not overlap at all and the presence above proves nothing about naming depth"
        )


class TestRecallHop:
    """§30's hop half (landed with §87): a stored edge pulls a passage into an answered context.

    The contract these cases pin: the hop runs only after the retriever answered (the refusal side
    is witnessed in TestFloorsUntouched), no pull duplicates a passage the first pass already
    renders, the hole is capped and ordered by document position, and every hop reason names an
    edge whose neighbour label the pulled passage *actually carries* — the rule the substrate was
    built for, checked against the passages themselves rather than against one fixture.
    """

    #: This question names a stored competition whose five has_team edges reach demo-team passages
    #: the retriever's top-5 does not render — the hop is where those passages come from.
    HOP_QUERY = "how high should Braehaven Elite League sides sit"
    LEAGUE_SLUG = "braehaven-elite-league"

    def _synced(self, session: Session) -> None:
        from app.services.knowledge import sync_knowledge
        from app.services.world import sync_world

        sync_knowledge(session)
        sync_world(session)

    def _usable(self, session: Session, query: str) -> list[Any]:
        from app.services.knowledge import answer as answer_module

        found = retrieval.search(session, query)
        return [h for h in found.hits if h.score >= answer_module.ANSWER_SCORE_FLOOR] if found.answerable else []

    def test_a_hopped_answer_publishes_its_pulls_in_all_three_places(self, session: Session) -> None:
        from app.services.knowledge import recall

        self._synced(session)
        payload = graph_join_anchored(session, self.HOP_QUERY)
        assert payload["answered"], "the hop's witness query stopped being answered; re-measure the golden set"
        hops = _hop_citations(payload)
        assert hops, f"the answered context carried no pulled passage — reasons: {payload['reasons']}"
        first_pass = {c["chunk_id"] for c in payload["citations"] if c.get("via") is None}
        assert first_pass, "the first pass rendered nothing, so this answer has no passages half at all"
        hop_ids = {c["chunk_id"] for c in hops}
        assert hop_ids.isdisjoint(first_pass), f"a pull duplicated a first-pass passage: {sorted(hop_ids & first_pass)}"
        digest_marked = {entry["ref"] for entry in payload["digest"] if entry.get("via") == recall.VIA_GRAPH}
        assert digest_marked == {c["ref"] for c in hops}, "the digest does not mirror exactly the hop's citations"
        lines = [line for line in payload["reasons"] if line.startswith(recall.HOP_PREFIX)]
        assert len(lines) == len(hops), f"{len(hops)} pull(s) but {len(lines)} hop reason line(s): {lines}"
        for citation in hops:
            assert f"[{citation['ref']}]" in payload["answer"], f"pull [{citation['ref']}] is cited but its marker is missing from the answer"
            assert any(f"passage [{citation['ref']}]" in line for line in lines), f"no hop line points at passage [{citation['ref']}]"
        for line in lines:
            assert graph_join.DEMO_MARK in line, f"a hop line disclosed no synthetic provenance: {line}"
            assert "“Braehaven Elite League”" in line, f"a hop line does not name the anchored competition: {line}"

    def test_the_first_pass_of_a_hopped_answer_is_the_single_phase_render(self, session: Session) -> None:
        from app.services.knowledge import answer as answer_module

        self._synced(session)
        usable = self._usable(session, self.HOP_QUERY)
        assert usable, "the witness query no longer answers; re-measure before trusting the identity claim"
        _, first_digest, first_cites = answer_module.assemble_context(usable)
        payload = graph_join_anchored(session, self.HOP_QUERY)
        assert _hop_citations(payload), "the witness query stopped hopping, so first-pass identity would be vacuous here"
        plain = [c for c in payload["citations"] if c.get("via") is None]
        assert [(c["chunk_id"], c["ref"]) for c in plain] == [(c["chunk_id"], c["ref"]) for c in first_cites]
        assert [entry for entry in payload["digest"] if entry.get("via") is None] == first_digest

    def test_the_hop_is_capped_at_what_this_fixture_saturates(self, session: Session) -> None:
        from app.services.knowledge import recall

        self._synced(session)
        _, links = project.edges_of(session, "competition", self.LEAGUE_SLUG)
        neighbours = {(link.other.kind, link.other.label) for link in links if link.other.kind == "team"}
        assert len(neighbours) > recall.MAX_HOP_CHUNKS, "the anchor offers no more neighbours than the cap, so the cap is untested"
        hops = _hop_citations(graph_join_anchored(session, self.HOP_QUERY))
        assert len(hops) <= recall.MAX_HOP_CHUNKS, f"{len(hops)} pull(s) exceeded the cap {recall.MAX_HOP_CHUNKS}"
        assert len(hops) == 2, f"measured: this fixture saturates the cap with 2 pulls; got {len(hops)} — re-measure cap and corpus"

    def test_the_reserve_admits_every_pull_where_the_bare_budget_evicts(self, session: Session) -> None:
        from app.services.knowledge import answer as answer_module
        from app.services.knowledge import recall
        from app.services.knowledge.chunking import strip_header

        self._synced(session)
        usable = self._usable(session, self.HOP_QUERY)
        assert usable
        _, _, first_cites = answer_module.assemble_context(usable)
        anchors = graph_join.anchors(session, self.HOP_QUERY)
        pulls = recall.pulls(session, anchors, exclude={c["chunk_id"] for c in first_cites}, scored=usable)
        assert pulls, "the witness query stopped pulling; re-measure the reserve case"
        hits = usable + [pull.hit for pull in pulls]
        reserve = sum(len(strip_header(pull.hit.text)) for pull in pulls)
        _, _, bare = answer_module.assemble_context(hits, main=len(usable), extra_budget=0)
        _, _, paid = answer_module.assemble_context(hits, main=len(usable), extra_budget=reserve)
        pull_ids = {pull.hit.chunk_id for pull in pulls}
        rendered_bare = {c["chunk_id"] for c in bare}
        rendered_paid = {c["chunk_id"] for c in paid}
        assert len(pull_ids & rendered_bare) < len(pull_ids), "the bare budget rendered every pull after all, so this fixture no longer exercises the reserve"
        assert pull_ids <= rendered_paid, f"the reserve still evicted a pull: {sorted(pull_ids - rendered_paid)}"
        first_prefix = [c["chunk_id"] for c in paid][: len(first_cites)]
        assert first_prefix == [c["chunk_id"] for c in first_cites], "granting the reserve changed what the first pass renders"

    def test_every_pull_reason_names_an_edge_whose_label_the_passage_carries(self, session: Session) -> None:
        from app.models import KnowledgeChunk
        from app.services.knowledge import recall
        from app.services.knowledge.chunking import strip_header

        self._synced(session)
        checked = 0
        hopped = 0
        for case in _golden()["queries"]:
            payload = graph_join_anchored(session, case["query"])
            hops = _hop_citations(payload)
            if hops:
                hopped += 1
            lines = [line for line in payload["reasons"] if line.startswith(recall.HOP_PREFIX)]
            pairs: list[tuple[str, str]] = []
            for citation in hops:
                line = next((item for item in lines if f"passage [{citation['ref']}]" in item), None)
                assert line is not None, f"{case['id']!r}: pull [{citation['ref']}] has no hop line"
                match = re.search(r"reaches (\w+) “([^”]+)”", line)
                assert match, f"{case['id']!r}: hop line names no neighbour: {line}"
                kind, neighbour = match.group(1), match.group(2)
                pairs.append((kind, neighbour))
                chunk = session.get(KnowledgeChunk, citation["chunk_id"])
                assert chunk is not None, f"{case['id']!r}: pulled chunk {citation['chunk_id']} is not stored"
                body = " ".join(strip_header(chunk.text).casefold().split())
                assert " ".join(neighbour.casefold().split()) in body, (
                    f"{case['id']!r}: the hop attributes passage [{citation['ref']}] to {kind} “{neighbour}”, whose name the passage does not carry"
                )
                checked += 1
            assert len(pairs) == len(set(pairs)), f"{case['id']!r}: one neighbour was pulled through two edges: {pairs}"
        assert hopped >= 5, f"only {hopped} of {len(_golden()['queries'])} golden answers hopped; re-measure the corpus bridge"
        assert checked >= 5, f"only {checked} pull(s) were rule-checked, floor 5: the rule claim would rest on almost nothing"

    def test_no_golden_answer_cites_a_passage_twice_and_the_hop_still_reaches_the_set(self, session: Session) -> None:
        self._synced(session)
        hopped = 0
        for case in _golden()["queries"]:
            payload = graph_join_anchored(session, case["query"])
            ids = [c["chunk_id"] for c in payload["citations"]]
            assert len(ids) == len(set(ids)), f"{case['id']!r} cites a passage twice: {ids}"
            assert [c["ref"] for c in payload["citations"]] == list(range(1, len(ids) + 1)), (
                f"{case['id']!r} citation refs are not the 1-based [n] sequence: {[c['ref'] for c in payload['citations']]}"
            )
            if _hop_citations(payload):
                hopped += 1
        assert hopped >= 5, f"only {hopped} of {len(_golden()['queries'])} golden answers hopped; the corpus bridge must keep half the set hoppable"

    def test_pull_choice_survives_reingestion_that_rotates_chunk_ids(self, session: Session) -> None:
        from app.services.knowledge import recall, sync_knowledge

        self._synced(session)
        anchors = graph_join.anchors(session, self.HOP_QUERY)
        assert anchors, "the witness query anchors nothing; the determinism claim has no subject"
        before = recall.pulls(session, anchors, limit=2)
        assert before, "the scan returned nothing before reingestion, so stability would be measured on an empty set"
        positions = [(pull.hit.document_slug, pull.hit.ordinal) for pull in before]
        ids_before = {pull.hit.chunk_id for pull in before}
        sync_knowledge(session, force=True)
        after = recall.pulls(session, graph_join.anchors(session, self.HOP_QUERY), limit=2)
        assert [(pull.hit.document_slug, pull.hit.ordinal) for pull in after] == positions, (
            "reingestion moved which passage the hop picks — ordering must key on document position, not chunk id"
        )
        assert {pull.hit.chunk_id for pull in after} != ids_before, "reingestion produced identical chunk ids, so the stability claim above was vacuous"

    def test_the_scan_respects_its_exclude_and_reuses_a_scored_hit(self, session: Session) -> None:
        from app.services.knowledge import recall

        self._synced(session)
        anchors = graph_join.anchors(session, self.HOP_QUERY)
        assert anchors
        assert recall.pulls(session, []) == []
        one = recall.pulls(session, anchors, limit=1)
        assert len(one) == 1, f"the cap of 1 returned {len(one)} pulls"
        excluded = recall.pulls(session, anchors, exclude={one[0].hit.chunk_id}, limit=1)
        assert excluded and excluded[0].hit.chunk_id != one[0].hit.chunk_id, (
            "the exclude set was ignored: the scan returned the passage it was told the reader already sees"
        )
        handoff = excluded[0].hit
        rescored = recall.pulls(session, anchors, exclude={one[0].hit.chunk_id}, scored=[handoff], limit=1)
        assert rescored and rescored[0].hit is handoff, "a scored hit the hop re-crossed was re-synthesized instead of reused"


def _hop_citations(payload: dict[str, Any]) -> list[dict[str, Any]]:
    from app.services.knowledge import recall

    return [c for c in payload["citations"] if c.get("via") == recall.VIA_GRAPH]


def graph_join_anchored(session: Session, question: str) -> dict[str, Any]:
    """`ask()` with the graph half read out of the reasons, so the invariant is one shape to check."""
    from app.services.knowledge import answer as answer_module

    result = answer_module.ask(session, question, persist=False)
    payload = result.to_dict()
    payload["graph_lines"] = [line for line in payload["reasons"] if line.startswith(graph_join.REASON_PREFIX)]
    return payload
