"""Latency percentile tests (spec §58, M12 Performance).

`/metrics/system` answered `p95_latency_ms: None` with a comment saying a percentile would need
computing. These cases plant ledger rows with known latencies and assert the nearest-rank figure,
the sample bounds, and the per-feature filter — the arithmetic, not a mocked shape.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.main import app
from app.models import ModelCall
from app.services.latency_profile import SAMPLE_SIZE, profile


@pytest.fixture()
def session() -> Iterator[Session]:
    """A session over a ledger this file owns (the run's database persists from case to case)."""
    row = SessionLocal()
    try:
        row.query(ModelCall).delete()
        row.commit()
        yield row
    finally:
        row.close()


def _call(db: Session, *, latency_ms: int, feature: str = "knowledge_answer", days_ago: int = 0) -> ModelCall:
    row = ModelCall(
        id=f"mc_{uuid4().hex[:12]}",
        provider="openai",
        model="gpt-4o-mini",
        feature=feature,
        input_tokens=10,
        output_tokens=5,
        latency_ms=latency_ms,
        demo_mode=True,
        success=True,
        created_at=datetime.now(UTC) - timedelta(days=days_ago),
    )
    db.add(row)
    db.commit()
    return row


def _latencies(count: int, *, feature: str = "knowledge_answer") -> list[int]:
    """0..count-1 milliseconds, in order, so the percentile's rank is known by hand."""
    return list(range(count))


def test_an_empty_ledger_answers_zeros_not_an_error(session: Session) -> None:
    answer = profile(session)
    assert answer["sample_size"] == 0 and answer["sampled_from"] == 0
    assert answer["p95_latency_ms"] == 0.0 and answer["max_latency_ms"] == 0.0
    assert answer["sample_is_newest"] is False, "an empty sample is not a full one"
    assert "nearest-rank" in answer["limitation"]


def test_percentiles_are_nearest_rank_over_the_planted_rows(session: Session) -> None:
    for value in _latencies(100):
        _call(session, latency_ms=value)
    answer = profile(session)
    assert answer["sample_size"] == 100 and answer["sampled_from"] == 100
    # Nearest rank over 100 rows of 0..99ms: n = ceil(P/100 × N), take the n-th smallest.
    # p50 → n=50 → the 50th smallest is 49; p95 → n=95 → 94; p99 → n=99 → 98. An interpolated
    # value (49.5, 94.05) would be a latency no call actually took, which is why it is not used.
    assert answer["p50_latency_ms"] == 49.0
    assert answer["p95_latency_ms"] == 94.0
    assert answer["p99_latency_ms"] == 98.0
    assert answer["max_latency_ms"] == 99.0


def test_the_sample_is_capped_and_the_answer_says_so(session: Session) -> None:
    for value in _latencies(SAMPLE_SIZE + 250):
        _call(session, latency_ms=value)
    answer = profile(session)
    assert answer["sample_size"] == SAMPLE_SIZE, "only the newest SAMPLE_SIZE rows are read"
    assert answer["sampled_from"] == SAMPLE_SIZE + 250
    assert answer["sample_is_newest"] is True, "a full sample makes the estimate speakable"
    # The newest rows are the *largest* values, so the capped sample is the slow end of the window.
    assert answer["max_latency_ms"] == float(SAMPLE_SIZE + 249)


def test_the_window_excludes_rows_older_than_it(session: Session) -> None:
    _call(session, latency_ms=10, days_ago=1)
    _call(session, latency_ms=9000, days_ago=90)
    answer = profile(session, days=30)
    assert answer["sampled_from"] == 1 and answer["max_latency_ms"] == 10.0


def test_the_feature_filter_reads_only_that_feature(session: Session) -> None:
    _call(session, latency_ms=10, feature="knowledge_answer")
    _call(session, latency_ms=800, feature="coach_recommendation")
    answer = profile(session, feature="coach_recommendation")
    assert answer["feature"] == "coach_recommendation"
    assert answer["sample_size"] == 1 and answer["max_latency_ms"] == 800.0


class TestLatencyDoor:
    def test_the_door_answers_the_profile_whole(self, admin_client: TestClient) -> None:
        resp = admin_client.get("/api/v1/metrics/latency")
        assert resp.status_code == 200
        body = resp.json()
        assert {"p50_latency_ms", "p95_latency_ms", "p99_latency_ms", "sample_size", "sampled_from", "limitation"} <= set(body)

    def test_the_system_door_now_carries_a_p95_figure(self, admin_client: TestClient) -> None:
        """The row this landing replaced: p95_latency_ms used to answer None with a comment."""
        resp = admin_client.get("/api/v1/metrics/system")
        assert resp.status_code == 200
        assert isinstance(resp.json()["p95_latency_ms"], float)

    def test_the_door_is_auth_gated(self) -> None:
        assert TestClient(app).get("/api/v1/metrics/latency").status_code == 401

    def test_the_window_and_feature_are_clamped(self, admin_client: TestClient) -> None:
        assert admin_client.get("/api/v1/metrics/latency?days=0").status_code == 422
        assert admin_client.get("/api/v1/metrics/latency?days=999").status_code == 422
