"""RAG evaluation harness (spec §63 'RAG Evaluation', §64 'Citation correctness').

One implementation, two doors: `python -m evals.run_rag_eval` prints a report for a human
to read, and `tests/test_knowledge_rag.py` imports `evaluate()` and fails the suite when a
threshold slips. Retrieval quality is therefore a gate, not a vibe.

Metrics
    recall@k — share of golden queries with at least one acceptable document in the top k
    mrr@k    — mean reciprocal rank of the first acceptable document
    citation_integrity — every returned quote is a verbatim substring of the stored chunk
    refusal_accuracy   — out-of-scope questions produce no answer and no citations
    hybrid_delta       — hybrid recall minus keyword-only recall (fusion must not hurt)
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

GOLDEN_PATH = Path(__file__).resolve().parent / "golden_rag.json"

THRESHOLDS = {
    "recall_at_k": 0.85,
    "mrr_at_k": 0.60,
    "citation_integrity": 1.0,
    "refusal_accuracy": 1.0,
    "hybrid_delta": 0.0,
}


@dataclass
class EvalReport:
    mode: str
    k: int
    backend: str
    scanned: int
    documents: int
    chunks: int
    recall_at_k: float = 0.0
    mrr_at_k: float = 0.0
    citation_integrity: float = 0.0
    refusal_accuracy: float = 0.0
    keyword_recall_at_k: float = 0.0
    semantic_recall_at_k: float = 0.0
    citations_checked: int = 0
    failures: list[str] = field(default_factory=list)
    per_query: list[dict[str, Any]] = field(default_factory=list)

    @property
    def hybrid_delta(self) -> float:
        return round(self.recall_at_k - self.keyword_recall_at_k, 4)

    def scores(self) -> dict[str, float]:
        return {
            "recall_at_k": round(self.recall_at_k, 4),
            "mrr_at_k": round(self.mrr_at_k, 4),
            "citation_integrity": round(self.citation_integrity, 4),
            "refusal_accuracy": round(self.refusal_accuracy, 4),
            "hybrid_delta": self.hybrid_delta,
        }

    def passed(self) -> bool:
        return not self.failures

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "k": self.k,
            "retrieval_backend": self.backend,
            "corpus": {"documents": self.documents, "chunks": self.chunks, "scanned_per_query": self.scanned},
            "thresholds": THRESHOLDS,
            "scores": self.scores(),
            "keyword_recall_at_k": round(self.keyword_recall_at_k, 4),
            "semantic_recall_at_k": round(self.semantic_recall_at_k, 4),
            "citations_checked": self.citations_checked,
            "passed": self.passed(),
            "failures": self.failures,
            "per_query": self.per_query,
        }


def _golden() -> dict[str, Any]:
    return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))


def evaluate(db: Any, *, mode: str = "hybrid", persist: bool = False) -> EvalReport:
    """Run the golden set against a database that already holds the corpus."""
    from sqlalchemy import func, select

    from app.models import KnowledgeChunk, KnowledgeDocument
    from app.services.knowledge import ask, search
    from app.services.knowledge.retrieval import Filters

    golden = _golden()
    k = int(golden.get("recall_at", 5))
    report = EvalReport(
        mode=mode,
        k=k,
        backend="",
        scanned=0,
        documents=int(db.scalar(select(func.count(KnowledgeDocument.id))) or 0),
        chunks=int(db.scalar(select(func.count(KnowledgeChunk.id))) or 0),
    )
    if report.documents == 0:
        report.failures.append("corpus is empty — ingestion did not run")
        return report

    text_by_chunk = {row[0]: row[1] for row in db.execute(select(KnowledgeChunk.id, KnowledgeChunk.text)).all()}

    keyword_recalled = 0
    semantic_recalled = 0
    recalled = 0
    reciprocal_ranks: list[float] = []
    citations_checked = 0
    citations_valid = 0

    for case in golden["queries"]:
        expected = set(case["expected_documents"])
        found = search(db, case["query"], filters=Filters(), mode=mode, top_k=k)
        ranked_slugs = [hit.document_slug for hit in found.hits]
        report.backend = found.backend
        report.scanned = found.scanned

        hits_expected = bool(expected & set(ranked_slugs))
        recalled += 1 if hits_expected else 0
        rank = next((i + 1 for i, slug in enumerate(ranked_slugs) if slug in expected), 0)
        reciprocal_ranks.append(1.0 / rank if rank else 0.0)

        if mode == "hybrid":
            keyword_recalled += 1 if expected & {
                h.document_slug for h in search(db, case["query"], filters=Filters(), mode="keyword", top_k=k).hits
            } else 0
            semantic_recalled += 1 if expected & {
                h.document_slug for h in search(db, case["query"], filters=Filters(), mode="semantic", top_k=k).hits
            } else 0

        answer = ask(db, case["query"], filters=Filters(), mode=mode, top_k=k, persist=persist)
        for citation in answer.citations:
            citations_checked += 1
            stored = text_by_chunk.get(citation["chunk_id"], "")
            quote = citation["quote"].rstrip("…")
            if quote and quote in stored:
                citations_valid += 1
            else:
                report.failures.append(f"{case['id']}: citation quote is not verbatim in the stored chunk")

        report.per_query.append(
            {
                "id": case["id"],
                "query": case["query"],
                "expected": sorted(expected),
                "ranked": ranked_slugs,
                "recalled": hits_expected,
                "rank": rank,
                "answered": answer.answered,
                "confidence": round(answer.confidence, 3),
                "top_score": round(found.top_score, 4),
            }
        )
        if not hits_expected:
            report.failures.append(f"{case['id']}: no acceptable document in top {k} — got {ranked_slugs}")
        if not answer.answered:
            report.failures.append(f"{case['id']}: golden query was refused")

    total = len(golden["queries"])
    report.recall_at_k = recalled / total if total else 0.0
    report.mrr_at_k = sum(reciprocal_ranks) / total if total else 0.0
    report.citation_integrity = citations_valid / citations_checked if citations_checked else 0.0
    report.citations_checked = citations_checked
    if mode == "hybrid":
        report.keyword_recall_at_k = keyword_recalled / total if total else 0.0
        report.semantic_recall_at_k = semantic_recalled / total if total else 0.0

    refused_ok = 0
    for case in golden["out_of_scope"]:
        answer = ask(db, case["query"], filters=Filters(), mode=mode, top_k=k, persist=persist)
        if not answer.answered and not answer.citations:
            refused_ok += 1
        else:
            report.failures.append(
                f"{case['id']}: out-of-scope question was answered with {len(answer.citations)} citation(s)"
            )
    scope_total = len(golden["out_of_scope"])
    report.refusal_accuracy = refused_ok / scope_total if scope_total else 1.0

    for metric, minimum in THRESHOLDS.items():
        if getattr(report, metric) < minimum:
            report.failures.append(f"metric {metric}={report.scores()[metric]} is below the {minimum} gate")
    return report


def main() -> int:
    from app.core.db import SessionLocal, init_db
    from app.services.knowledge import sync_knowledge

    parser = argparse.ArgumentParser(description="Run the FOOTBALL OS RAG evaluation")
    parser.add_argument("--mode", default="hybrid", choices=["hybrid", "keyword", "semantic"])
    parser.add_argument("--json", action="store_true", help="print the machine-readable report")
    args = parser.parse_args()

    init_db()
    with SessionLocal() as db:
        report_ingest = sync_knowledge(db)
        if not report_ingest.ok:
            print("ingestion errors:", "; ".join(report_ingest.errors), file=sys.stderr)
            return 2
        report = evaluate(db, mode=args.mode)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(f"corpus: {report.documents} documents / {report.chunks} chunks / backend={report.backend}")
        for metric, value in report.scores().items():
            gate = THRESHOLDS.get(metric)
            print(f"  {metric:<18} {value:<8} gate >= {gate}")
        print(f"  keyword recall@{report.k}  {report.keyword_recall_at_k:.3f}")
        print(f"  semantic recall@{report.k} {report.semantic_recall_at_k:.3f}")
        print(f"  citations checked: {report.citations_checked}")
        for row in report.per_query:
            flag = "ok " if row["recalled"] else "MISS"
            print(f"  {flag} {row['id']:<16} rank={row['rank'] or '-'} conf={row['confidence']} top={row['top_score']}")
        print("FAILURES:" if report.failures else "all gates passed")
        for failure in report.failures:
            print("  -", failure)
    return 0 if report.passed() else 1


if __name__ == "__main__":
    raise SystemExit(main())
