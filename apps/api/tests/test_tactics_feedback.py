"""M4 cited tactical analysis: every statement must resolve to a stored passage, or be reported as not made.

These tests are the review of `build_feedback`. The interesting assertions are the negative ones: a topic
whose retrieval misses the corpus's answerability gates has to come back in `ungrounded` with its measured
numbers and a reason, and a payload that cites something must cite a chunk that exists at the exact
anchor the link points at.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import KnowledgeChunk, KnowledgeDocument
from app.services.tactics.feedback import FIT_SHORTFALL, FIT_TOLERANCE, TOPICS, build_feedback, fit_rows
from app.services.tactics.sync import sync_tactics

API = "/api/v1/tactics"


@pytest.fixture()
def store() -> Iterator:  # type: ignore[no-untyped-def]
    session = SessionLocal()
    try:
        report = sync_tactics(session)
        assert report.ok, report.errors
        yield session
    finally:
        session.close()


class TestFitArithmetic:
    def test_a_player_meeting_every_demand_is_not_told_they_are_short(self) -> None:
        demands = {"pressing": 78, "build_up": 82, "off_ball_movement": 84}
        attributes = {key: value + FIT_TOLERANCE for key, value in demands.items()}
        fit = fit_rows(demands, attributes)
        assert fit["shortfalls"] == []
        assert fit["verdict"] == "fits the demands of this shape"
        assert all(row["verdict"] == "exceeds" for row in fit["rows"])

    def test_the_thresholds_are_the_published_ones_and_no_adjective_moves_them(self) -> None:
        demands = {"pressing": 80}
        short = fit_rows(demands, {"pressing": 80 - FIT_SHORTFALL})
        borderline = fit_rows(demands, {"pressing": 80 - FIT_SHORTFALL + 1})
        assert short["rows"][0]["verdict"] == "short"
        assert borderline["rows"][0]["verdict"] == "matches"
        assert short["rows"][0]["rule"] == f"short at ≤ -{FIT_SHORTFALL}, exceeds at ≥ +{FIT_TOLERANCE}, otherwise matches"

    def test_a_missing_attribute_reads_as_zero_not_as_a_crash(self) -> None:
        fit = fit_rows({"pressing": 78, "transition": 84}, {"pressing": 78})
        assert {row["attribute"]: row["have"] for row in fit["rows"]} == {"pressing": 78, "transition": 0}
        assert fit["shortfalls"] == ["transition"]
        assert fit["mean_gap"] == pytest.approx(-42.0)
        assert fit["covered_attributes"] == 2

    def test_the_mean_gap_is_recomputable_from_the_rows(self) -> None:
        fit = fit_rows({"pressing": 78, "build_up": 82, "vision_like": 60}, {"pressing": 90, "build_up": 60, "vision_like": 60})
        assert fit["mean_gap"] == pytest.approx(sum(row["gap"] for row in fit["rows"]) / len(fit["rows"]), abs=0.01)


class TestCitedAnalysis:
    def test_the_analysis_cites_or_refuses_every_topic_it_was_asked_about(self, client, store) -> None:  # type: ignore[no-untyped-def]
        from app.models import TacticalSystem

        row = store.scalar(select(TacticalSystem).where(TacticalSystem.slug == "4-3-3-press-high"))
        assert row is not None
        result = build_feedback(store, {"slug": row.slug, "name": row.name, "formation": row.formation, "temperament_key": row.temperament_key, "board": row.board})
        asked = {topic.key for topic in TOPICS}
        assert {point["topic"] for point in result.points} | {item["topic"] for item in result.ungrounded} == asked
        assert result.points, "with the corpus ingested, at least one topic must be citable"

    def test_a_citation_resolves_to_the_stored_chunk_it_quotes(self, client, store) -> None:  # type: ignore[no-untyped-def]
        from app.models import TacticalSystem

        row = store.scalar(select(TacticalSystem).where(TacticalSystem.slug == "3-5-2-direct-transition"))
        result = build_feedback(store, {"slug": row.slug, "name": row.name, "board": row.board})
        for point in result.points:
            citation = point["citation"]
            document = store.scalar(select(KnowledgeDocument).where(KnowledgeDocument.slug == citation["slug"]))
            assert document is not None, citation
            chunk = store.scalar(select(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id, KnowledgeChunk.ordinal == citation["ordinal"]))
            assert chunk is not None, citation
            assert citation["quote"].rstrip("…") in chunk.text, citation
            # `ref` is an in-app anchor, not a URL: /knowledge/{slug}#{ordinal} must resolve on the site.
            assert citation["ref"] == f"/knowledge/{citation['slug']}#{citation['ordinal']}"

    def test_an_ungrounded_topic_says_which_gate_it_missed(self, client, store) -> None:  # type: ignore[no-untyped-def]
        from app.models import TacticalSystem

        row = store.scalar(select(TacticalSystem).limit(1))
        result = build_feedback(store, {"slug": row.slug, "name": row.name, "board": row.board})
        for item in result.ungrounded:
            assert item["reason"], item
            if "answerability" in item:
                gates = item["answerability"]
                assert gates["answerable"] is False or gates["top_score"] < 1.0
                assert item["value"] > 0, "a refused topic still reports what was measured"

    def test_the_payload_labels_itself_extractive_and_carries_no_invented_source(self, client) -> None:  # type: ignore[no-untyped-def]
        body = client.get(f"{API}/4-3-3-press-high/feedback").json()
        assert body["data_origin"] == "project-authored" and body["is_demo_data"] is False
        assert body["demo_mode"] is True
        assert "extractive" in body["model"].lower()
        assert body["provider"].startswith("none")
        assert body["method"], "the reader has to be told how the statements were produced"
        assert body["citations"] == [point["citation"] for point in body["points"]]
        for point in body["points"]:
            assert point["metric"]["formula"], point
            assert f"{point['metric']['value']:.1f}" in point["statement"] or str(point["metric"]["value"]) in point["statement"]

    def test_the_feedback_endpoint_is_public_and_the_unknown_system_is_a_404(self, client) -> None:  # type: ignore[no-untyped-def]
        assert client.get(f"{API}/4-3-3-low-block/feedback").status_code == 200
        missing = client.get(f"{API}/4-3-3-not-a-real-temperament/feedback")
        assert missing.status_code == 404
        assert missing.json()["detail"]["code"] == "not_found"


class TestFitEndpoint:
    def test_fit_requires_a_session(self, client) -> None:  # type: ignore[no-untyped-def]
        assert client.get(f"{API}/4-3-3-press-high/fit").status_code == 401

    def test_fit_compares_the_accounts_player_against_the_shapes_demands(self, auth_client, player_id) -> None:  # type: ignore[no-untyped-def]
        response = auth_client.get(f"{API}/3-4-2-1-press-high/fit")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["player"]["id"] == player_id
        assert body["fit"]["rows"], "the shape fields six demanding roles"
        assert {row["attribute"] for row in body["fit"]["rows"]} <= {
            "pressing",
            "build_up",
            "off_ball_movement",
            "defensive_awareness",
            "space_occupation",
            "transition",
        }
        assert "progression ledger" in body["note"] and "No model decided" in body["note"]
        assert body["data_origin"] == "project-authored"

    def test_an_account_without_a_player_gets_the_documented_409(self, auth_client) -> None:  # type: ignore[no-untyped-def]
        # `auth_client` registers an account; only the `player_id` fixture creates a player.
        response = auth_client.get(f"{API}/4-3-3-press-high/fit")
        assert response.status_code == 409, response.text
        assert response.json()["detail"]["code"] == "no_player"
