"""M2 Football Knowledge + RAG: ingestion, hybrid retrieval, citations and refusal (spec §29, §62).

These run on both supported databases. The pgvector leg is asserted by capability, not by
skipping: when the extension is present retrieval must report it, and when it is not the same
queries must still answer through the in-process fallback.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal, has_pgvector
from app.core.vector_type import EMBEDDING_DIM
from app.models import KnowledgeChunk, KnowledgeDocument, KnowledgeQuery
from app.services import knowledge
from app.services.knowledge.chunking import KnowledgeDocumentError, chunk_document, parse_document


@pytest.fixture()
def db() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# --- corpus contract -----------------------------------------------------------------------


def test_every_corpus_document_has_required_frontmatter_and_parses_into_chunks() -> None:
    root = Path(__file__).resolve().parents[3] / "data" / "knowledge"
    files = [p for p in sorted(root.rglob("*.md")) if p.name.lower() != "readme.md"]
    assert len(files) >= 12, "the shipped corpus is the thing retrieval is graded on"
    for path in files:
        document = parse_document(path.read_text(encoding="utf-8"), path=str(path.relative_to(root)))
        assert document.title and document.category and document.source_label
        chunks = chunk_document(document)
        assert chunks, path
        assert all(len(c.text.strip()) > 120 for c in chunks), path
        # every chunk carries its heading so a citation is readable out of context
        assert all(" — " in c.text.split("\n", 1)[0] for c in chunks), path


def test_parse_document_rejects_a_frontmatter_that_omits_provenance() -> None:
    with pytest.raises(KnowledgeDocumentError):
        parse_document("---\ntitle: Orphan\ncategory: tactics\n---\n\nBody text goes here.\n", path="x.md")


# --- ingestion ------------------------------------------------------------------------------


def test_ingestion_is_idempotent_and_rewrites_only_changed_documents(db: Session) -> None:
    first = knowledge.sync_knowledge(db)
    assert first.ok and first.documents_seen >= 12, first.errors
    assert first.created + first.updated + first.unchanged == first.documents_seen
    assert first.chunks_written == 0, "the session fixture already loaded the corpus"
    assert first.embedding_dim == EMBEDDING_DIM
    stats = knowledge.corpus_stats(db)
    assert stats["documents"] == first.documents_seen
    assert stats["chunks"] >= stats["documents"] * 4
    forced = knowledge.sync_knowledge(db, force=True)
    assert forced.ok and forced.chunks_written == stats["chunks"], forced.to_dict()
    assert forced.created == 0 and forced.updated == forced.documents_seen
    assert knowledge.corpus_stats(db)["chunks"] == stats["chunks"], "replacement must not stack rows"


def test_stored_chunks_carry_embeddings_of_the_declared_dimension(db: Session) -> None:
    rows = db.scalars(select(KnowledgeChunk).limit(25)).all()
    assert rows
    for chunk in rows:
        assert chunk.embedding is not None and len(chunk.embedding) == EMBEDDING_DIM
        assert chunk.haystack and chunk.terms


def test_corpus_is_labelled_as_project_authored_not_demo_data(db: Session) -> None:
    documents = db.scalars(select(KnowledgeDocument)).all()
    assert documents
    for document in documents:
        assert document.data_origin == "project-authored"
        assert document.is_demo_data is False
        assert document.source_label


# --- retrieval ------------------------------------------------------------------------------


@pytest.mark.parametrize("mode", ["semantic", "keyword", "hybrid"])
def test_all_three_retrieval_modes_retrieve_the_handball_document(db: Session, mode: str) -> None:
    result = knowledge.search(db, "is it handball if the ball hits my arm", mode=mode, top_k=5)
    assert result.hits, result.reasons
    assert any("handball" in hit.document_slug for hit in result.hits), [hit.document_slug for hit in result.hits]


def test_hybrid_report_explains_its_ranking_and_backend(db: Session) -> None:
    result = knowledge.search(db, "how do I press as a team when they build up from the keeper", top_k=5)
    payload = result.to_dict()
    assert payload["results"][0]["rank"] == 1
    assert payload["results"][0]["features"], "rerank features must be inspectable, not a black-box score"
    assert any("rare terms" in reason for reason in result.reasons), result.reasons
    assert payload["answerability"]["answerable"] is True


def test_pgvector_is_used_when_the_extension_is_present(db: Session) -> None:
    result = knowledge.search(db, "zonal marking at corners", top_k=5)
    if has_pgvector(db):
        assert result.backend == "hybrid-pgvector"
    else:
        assert result.backend == "hybrid-vector-python"


@pytest.mark.parametrize(
    ("filters", "expected_category"),
    [
        (knowledge.Filters(category="rules"), "rules"),
        (knowledge.Filters(category="tactics"), "tactics"),
    ],
)
def test_metadata_filters_confine_every_hit(db: Session, filters: knowledge.Filters, expected_category: str) -> None:
    result = knowledge.search(db, "what does the law say", filters=filters, top_k=5)
    assert result.hits
    assert {hit.category for hit in result.hits} == {expected_category}
    assert result.scanned < db.scalar(select(func.count(KnowledgeChunk.id)))


def test_position_and_tag_filters_narrow_the_corpus(db: Session) -> None:
    goalkeeper = knowledge.search(db, "distribution under pressure", filters=knowledge.Filters(position="goalkeeper"))
    assert all("goalkeeper" in hit.applies_to for hit in goalkeeper.hits)
    pressed = knowledge.search(db, "pressing", filters=knowledge.Filters(tag="pressing"))
    assert pressed.hits and all("pressing" in hit.tags for hit in pressed.hits)


def test_scoping_to_one_document_is_the_filter_the_detail_page_needs(db: Session) -> None:
    result = knowledge.search(db, "when does this not apply", filters=knowledge.Filters(document_slug="scanning-before-receiving"), top_k=5)
    assert result.hits
    assert {hit.document_slug for hit in result.hits} == {"scanning-before-receiving"}
    empty = knowledge.search(db, "pressing", filters=knowledge.Filters(document_slug="no-such-document"))
    assert empty.hits == [] and empty.scanned == 0


def test_citation_quotes_are_verbatim_slices_of_the_stored_chunk(db: Session) -> None:
    result = knowledge.search(db, "how should I warm up before sprint training", top_k=5)
    for hit in result.hits:
        stored = db.get(KnowledgeChunk, hit.chunk_id)
        assert stored is not None
        quote = hit.citation()["quote"].rstrip("…")
        assert quote and quote in stored.text
        assert hit.citation()["ref"].startswith("/knowledge/")


def test_an_unanswerable_question_refuses_instead_of_guessing(db: Session) -> None:
    for question in (
        "which boot brand does the number 10 wear",
        "what is the best expected goals model for the 2019 champions league",
        "who won the ballon d or yesterday",
    ):
        answer = knowledge.ask(db, question, persist=False)
        assert answer.answered is False, question
        assert answer.citations == []
        assert answer.confidence <= 0.25
        assert any("rare term" in reason or "answer floor" in reason for reason in answer.reasons), answer.reasons


# --- answers --------------------------------------------------------------------------------


def test_ask_citations_use_ref_for_the_marker_and_slug_for_the_link(db: Session) -> None:
    """`ref` is the 1-based `[n]` marker; the web tier links with `slug` + `ordinal`."""
    answer = knowledge.ask(db, "how do I defend a 1v1 without getting beaten", top_k=5, persist=False)
    for index, citation in enumerate(answer.citations, start=1):
        assert citation["ref"] == index
        assert f"[{index}]" in answer.text
        assert citation["slug"] and isinstance(citation["ordinal"], int)


def test_ask_returns_an_extractive_digest_with_citations_in_demo_mode(db: Session) -> None:
    answer = knowledge.ask(db, "how do I defend a 1v1 without getting beaten", top_k=5, persist=False)
    assert answer.answered is True
    assert answer.demo_mode is True
    assert answer.model == "extractive-no-model"
    assert len(answer.citations) >= 1
    assert "[1]" in answer.text
    assert answer.timings_ms
    for citation in answer.citations:
        assert citation["quote"]


def test_ask_persists_an_audit_row_per_question(db: Session) -> None:
    before = db.scalar(select(func.count(KnowledgeQuery.id)))
    question = "what should I scan for before receiving"
    knowledge.ask(db, question, user_id=None, persist=True)
    after = db.scalar(select(func.count(KnowledgeQuery.id)))
    assert after == before + 1
    row = db.scalars(select(KnowledgeQuery).where(KnowledgeQuery.question == question)).first()
    assert row is not None and row.answered
    assert row.hit_chunk_ids and row.confidence > 0
    assert db.get(KnowledgeChunk, row.hit_chunk_ids[0]) is not None, "the audit trail must point at real chunks"


def test_rag_eval_gates_pass_on_this_database(db: Session) -> None:
    from evals.run_rag_eval import evaluate

    report = evaluate(db)
    assert report.passed, report.to_dict()
    scores = report.scores()
    assert scores["citation_integrity"] == 1.0
    assert scores["refusal_accuracy"] == 1.0
    assert scores["recall_at_k"] >= 0.85


# --- HTTP surface ---------------------------------------------------------------------------


def test_knowledge_status_reports_the_loaded_corpus(client) -> None:  # type: ignore[no-untyped-def]
    payload = client.get("/api/v1/knowledge/status").json()
    assert payload["documents"] >= 12 and payload["chunks"] > 50
    assert payload["embedding_dim"] == EMBEDDING_DIM
    assert payload["modes"] == ["semantic", "keyword", "hybrid"]
    assert payload["database_dialect"] in {"sqlite", "postgresql"}
    assert payload["providers"]["reranker"]


def test_document_library_and_detail_route(client) -> None:  # type: ignore[no-untyped-def]
    listing = client.get("/api/v1/knowledge/documents").json()
    assert listing["total"] >= 12
    slug = next(item["slug"] for item in listing["items"] if item["category"] == "rules")
    detail = client.get(f"/api/v1/knowledge/documents/{slug}").json()
    assert detail["sections"]
    assert detail["data_origin"] == "project-authored"
    assert client.get("/api/v1/knowledge/documents/no-such-thing").status_code == 404


def test_search_endpoint_requires_authentication(client) -> None:  # type: ignore[no-untyped-def]
    response = client.post("/api/v1/knowledge/search", json={"query": "scanning", "mode": "keyword"})
    assert response.status_code in (401, 403)


def test_authenticated_search_and_ask_carry_the_ai_envelope(auth_client) -> None:  # type: ignore[no-untyped-def]
    search = auth_client.post(
        "/api/v1/knowledge/search",
        json={"query": "how do I keep my balance when decelerating quickly", "mode": "hybrid", "top_k": 3},
    )
    assert search.status_code == 200, search.text
    body = search.json()
    assert body["demo_mode"] is True and body["sources"]
    assert body["disclaimer"] and body["generated_at"]
    assert body["answerability"]["coverage_floor"]

    ask = auth_client.post("/api/v1/knowledge/ask", json={"question": "when should my team press"})
    assert ask.status_code == 200, ask.text
    answer = ask.json()
    assert answer["answered"] is True
    assert answer["citations"] and answer["confidence"] > 0.3
    assert all(source["type"] == "knowledge_document" for source in answer["sources"])


def test_ingest_endpoint_is_staff_only(auth_client) -> None:  # type: ignore[no-untyped-def]
    response = auth_client.post("/api/v1/knowledge/ingest", json={})
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "forbidden"
