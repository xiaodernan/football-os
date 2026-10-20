"""Agent benchmark gate (spec §64).

This test imports the benchmark harness and fails the suite when any threshold slips.
Agent quality is therefore a gate, not a vibe. Run with:

    python -m pytest tests/test_agents_benchmark.py -v

The report is computed once per module and read by every assertion below. Before this fixture the
eight cases each called `evaluate()`, so one gate file ran the whole 27-case benchmark eight times —
the reason a targeted `-k benchmark` run took half a minute and the full suite's slowest leg was a
test that had already answered its question seven times.
"""

from collections.abc import Iterator

import pytest
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from evals.run_agent_benchmark import BenchmarkReport, evaluate


@pytest.fixture(scope="module")
def db_session() -> Iterator[Session]:
    """Provide a database session for the benchmark."""
    with SessionLocal() as db:
        yield db


@pytest.fixture(scope="module")
def report(db_session: Session) -> BenchmarkReport:
    """The benchmark, measured once."""
    return evaluate(db_session)


def test_agent_benchmark_overall(report: BenchmarkReport) -> None:
    """The full agent benchmark must pass all thresholds."""
    assert report.passed(), f"Benchmark failed: {report.failures}"


def test_agent_benchmark_answer_rate(report: BenchmarkReport) -> None:
    """Agents must answer at least 80% of cases."""
    assert report.overall_answer_rate >= 0.80, (
        f"Answer rate {report.overall_answer_rate:.2f} below 80% gate"
    )


def test_agent_benchmark_confidence(report: BenchmarkReport) -> None:
    """Average confidence across answered cases must be at least 0.55."""
    assert report.avg_confidence >= 0.55, (
        f"Average confidence {report.avg_confidence:.2f} below 0.55 gate"
    )


def test_agent_benchmark_citation_integrity(report: BenchmarkReport) -> None:
    """Citation quotes must be verbatim in stored chunks (90%+)."""
    assert report.citation_integrity >= 0.90, (
        f"Citation integrity {report.citation_integrity:.2f} below 90% gate"
    )


def test_agent_benchmark_refusal_accuracy(report: BenchmarkReport) -> None:
    """Out-of-scope questions must be refused (100%)."""
    assert report.refusal_accuracy == 1.0, (
        f"Refusal accuracy {report.refusal_accuracy:.2f} below 100% gate"
    )


def test_agent_benchmark_multi_step_completion(report: BenchmarkReport) -> None:
    """Composite tasks must execute expected agents (75%+)."""
    assert report.multi_step_completion >= 0.75, (
        f"Multi-step completion {report.multi_step_completion:.2f} below 75% gate"
    )


def test_agent_benchmark_trace_integrity(report: BenchmarkReport) -> None:
    """Every composite run must leave a trace that replays the steps its answer named.

    This is Item 5's measured claim: the smallest composite task is not "done" because an endpoint
    answered. It is done when the run it names can be read back — the same agents, in the same order,
    with the tool calls each one recorded. A rate below 1.0 means an answer exists that no trace can
    account for, which is exactly the state §33 was in before this gate.
    """
    assert report.trace_integrity == 1.0, (
        f"Trace integrity {report.trace_integrity:.2f} below 100% gate: {report.failures}"
    )


def test_agent_benchmark_per_category(report: BenchmarkReport) -> None:
    """Each category must have measurable performance."""
    for summary in report.per_category_summary:
        assert summary["cases"] > 0, f"Category {summary['category']} has no cases"
        # At least some cases should be answered in each category
        assert summary["answer_rate"] >= 0.5, (
            f"Category {summary['category']} answer rate {summary['answer_rate']:.2f} too low"
        )


def test_agent_benchmark_reproducible(db_session: Session, report: BenchmarkReport) -> None:
    """Running the benchmark twice should produce consistent results."""
    again = evaluate(db_session)
    assert report.scores() == again.scores(), "Benchmark results are not reproducible"
