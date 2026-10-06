"""Agent benchmark gate (spec §64).

This test imports the benchmark harness and fails the suite when any threshold slips.
Agent quality is therefore a gate, not a vibe. Run with:

    python -m pytest tests/test_agents_benchmark.py -v
"""

import pytest
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from evals.run_agent_benchmark import evaluate


@pytest.fixture(scope="module")
def db_session() -> Session:
    """Provide a database session for the benchmark."""
    with SessionLocal() as db:
        yield db


def test_agent_benchmark_overall(db_session: Session) -> None:
    """The full agent benchmark must pass all thresholds."""
    report = evaluate(db_session)
    assert report.passed(), f"Benchmark failed: {report.failures}"


def test_agent_benchmark_answer_rate(db_session: Session) -> None:
    """Agents must answer at least 80% of cases."""
    report = evaluate(db_session)
    assert report.overall_answer_rate >= 0.80, (
        f"Answer rate {report.overall_answer_rate:.2f} below 80% gate"
    )


def test_agent_benchmark_confidence(db_session: Session) -> None:
    """Average confidence across answered cases must be at least 0.55."""
    report = evaluate(db_session)
    assert report.avg_confidence >= 0.55, (
        f"Average confidence {report.avg_confidence:.2f} below 0.55 gate"
    )


def test_agent_benchmark_citation_integrity(db_session: Session) -> None:
    """Citation quotes must be verbatim in stored chunks (90%+)."""
    report = evaluate(db_session)
    assert report.citation_integrity >= 0.90, (
        f"Citation integrity {report.citation_integrity:.2f} below 90% gate"
    )


def test_agent_benchmark_refusal_accuracy(db_session: Session) -> None:
    """Out-of-scope questions must be refused (100%)."""
    report = evaluate(db_session)
    assert report.refusal_accuracy == 1.0, (
        f"Refusal accuracy {report.refusal_accuracy:.2f} below 100% gate"
    )


def test_agent_benchmark_multi_step_completion(db_session: Session) -> None:
    """Composite tasks must execute expected agents (75%+)."""
    report = evaluate(db_session)
    assert report.multi_step_completion >= 0.75, (
        f"Multi-step completion {report.multi_step_completion:.2f} below 75% gate"
    )


def test_agent_benchmark_per_category(db_session: Session) -> None:
    """Each category must have measurable performance."""
    report = evaluate(db_session)
    for summary in report.per_category_summary:
        assert summary["cases"] > 0, f"Category {summary['category']} has no cases"
        # At least some cases should be answered in each category
        assert summary["answer_rate"] >= 0.5, (
            f"Category {summary['category']} answer rate {summary['answer_rate']:.2f} too low"
        )


def test_agent_benchmark_reproducible(db_session: Session) -> None:
    """Running the benchmark twice should produce consistent results."""
    report1 = evaluate(db_session)
    report2 = evaluate(db_session)
    # Scores should match exactly on same data
    assert report1.scores() == report2.scores(), "Benchmark results are not reproducible"
