"""Cost optimisation advisor tests (spec §46, §76, M12).

Every figure the advisor prints is recomputed from the ledger on the request, so these cases plant
rows in `model_calls` and assert the arithmetic rather than a mocked shape: spend, per-feature share,
cost per 1k tokens, failure waste, and the recommendations that fire only above their thresholds.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.main import app
from app.models import ModelCall, User
from app.services.cost_advisor import recommend


@pytest.fixture()
def session() -> Iterator[Session]:
    """A session over a ledger this file owns.

    The run's database persists from case to case, and `model_calls` is the one table every AI door
    writes to — so without the clear below, a case asserting a failure rate would be counting the
    demo calls the suite's own knowledge tests made (measured: 37 of them). No case anywhere depends
    on another case's ledger rows, so the clear is safe and the arithmetic exact.
    """
    row = SessionLocal()
    try:
        row.query(ModelCall).delete()
        row.commit()
        yield row
    finally:
        row.close()


def _user(db: Session, name: str) -> User:
    tag = uuid4().hex[:8]
    row = User(id=f"usr_{name}_{tag}"[:40], email=f"{name}-{tag}@cost.test", password_hash="not-a-password", display_name=name)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _call(
    db: Session,
    *,
    feature: str = "knowledge_answer",
    provider: str = "openai",
    model: str = "gpt-4o-mini",
    cost: float = 0.0,
    success: bool = True,
    demo: bool = True,
    in_tokens: int = 100,
    out_tokens: int = 50,
    reasoning: int = 0,
    days_ago: int = 0,
) -> ModelCall:
    row = ModelCall(
        id=f"mc_{uuid4().hex[:12]}",
        provider=provider,
        model=model,
        feature=feature,
        user_id=None,
        input_tokens=in_tokens,
        output_tokens=out_tokens,
        reasoning_tokens=reasoning,
        latency_ms=120,
        estimated_cost_usd=cost,
        actual_cost_usd=cost,
        success=success,
        demo_mode=demo,
        created_at=datetime.now(UTC) - timedelta(days=days_ago),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _codes(answer: dict[str, Any]) -> list[str]:
    return [item["code"] for item in answer["recommendations"]]


def test_an_empty_ledger_answers_zeros_and_no_recommendations(session: Session) -> None:
    answer = recommend(session)
    assert answer["totals"]["spend_usd"] == 0.0
    assert answer["totals"]["calls"] == 0
    assert answer["totals"]["demo_share"] == 0.0
    assert answer["by_feature"] == [] and answer["by_model"] == []
    assert answer["recommendations"] == []
    assert "ledger" in answer["limitation"], "the answer says where its figures come from and that it changes nothing"


def test_the_window_excludes_rows_older_than_it(session: Session) -> None:
    _call(session, cost=1.0, days_ago=1)
    _call(session, cost=7.0, days_ago=60)
    answer = recommend(session, days=30)
    assert answer["totals"]["spend_usd"] == 1.0, "the 60-day row is outside a 30-day window"
    assert answer["window_days"] == 30


def test_by_feature_carries_its_own_share_and_failure_rate(session: Session) -> None:
    _call(session, feature="knowledge_answer", cost=3.0)
    _call(session, feature="knowledge_answer", cost=1.0, success=False)
    _call(session, feature="coach_recommendation", cost=1.0)
    answer = recommend(session)
    assert [row["feature"] for row in answer["by_feature"]] == ["knowledge_answer", "coach_recommendation"]
    first = answer["by_feature"][0]
    assert first["spend_usd"] == 4.0 and first["calls"] == 2 and first["failed_calls"] == 1
    assert first["failure_rate"] == 0.5, "half this feature's calls failed, and the rate says so"


def test_cost_per_1k_tokens_is_the_rate_a_routing_decision_reads(session: Session) -> None:
    _call(session, provider="openai", model="gpt-4o", cost=4.0, in_tokens=500, out_tokens=500)
    _call(session, provider="openai", model="gpt-4o-mini", cost=0.5, in_tokens=2500, out_tokens=2500)
    rows = {row["model"]: row for row in recommend(session)["by_model"]}
    assert rows["gpt-4o"]["cost_per_1k_tokens_usd"] == 4.0, "4.00 over 1000 tokens"
    assert rows["gpt-4o-mini"]["cost_per_1k_tokens_usd"] == 0.1, "0.50 over 5000 tokens"


def test_failure_waste_fires_only_above_its_threshold(session: Session) -> None:
    # 1 of 20 failed is 5% — at the boundary, not above it.
    for _ in range(19):
        _call(session, cost=0.1)
    _call(session, cost=2.0, success=False)
    assert "failure_waste" not in _codes(recommend(session))
    # 2 of 21 failed crosses it, and the recommendation names the waste in dollars.
    _call(session, cost=3.0, success=False)
    answer = recommend(session)
    assert "failure_waste" in _codes(answer)
    waste = next(item for item in answer["recommendations"] if item["code"] == "failure_waste")
    assert waste["spend_usd"] == 5.0, "the two failed calls cost 2.00 and 3.00"


def test_reasoning_share_fires_when_thinking_is_most_of_the_output(session: Session) -> None:
    _call(session, cost=1.0, out_tokens=100, reasoning=90)
    assert "reasoning_share" in _codes(recommend(session))
    totals = recommend(session)["totals"]
    assert totals["reasoning_share"] == 0.9


def test_a_cheaper_model_two_times_over_fires_with_the_gap_in_dollars(session: Session) -> None:
    for _ in range(5):
        _call(session, model="gpt-4o", cost=2.0, in_tokens=500, out_tokens=500)
        _call(session, model="gpt-4o-mini", cost=0.2, in_tokens=500, out_tokens=500)
    answer = recommend(session)
    assert "cheaper_model_available" in _codes(answer)
    item = next(r for r in answer["recommendations"] if r["code"] == "cheaper_model_available")
    # gpt-4o pays 2.00/1k and mini pays 0.20/1k: routing the 10.00 at the dearest rate to the cheapest
    # would save 9.00.
    assert item["spend_usd"] == 9.0


def test_demo_share_is_the_free_share_printed_beside_the_paid_one(session: Session) -> None:
    _call(session, cost=0.0, demo=True)
    _call(session, cost=2.0, demo=False)
    totals = recommend(session)["totals"]
    assert totals["demo_calls"] == 1 and totals["calls"] == 2
    assert totals["demo_share"] == 0.5


class TestCostOptimisationDoor:
    def test_the_door_answers_the_advisor_whole(self, admin_client: TestClient) -> None:
        resp = admin_client.get("/api/v1/metrics/cost-optimisation")
        assert resp.status_code == 200
        body = resp.json()
        assert set(body) == {"window_days", "totals", "by_feature", "by_model", "recommendations", "limitation"}
        assert body["totals"]["budget_usd_per_day"] > 0, "the budget the pace recommendation reads is published"

    def test_the_door_is_auth_gated(self) -> None:
        assert TestClient(app).get("/api/v1/metrics/cost-optimisation").status_code == 401

    def test_the_window_is_clamped_to_a_year(self, admin_client: TestClient) -> None:
        assert admin_client.get("/api/v1/metrics/cost-optimisation?days=400").status_code == 422
        assert admin_client.get("/api/v1/metrics/cost-optimisation?days=0").status_code == 422

    def test_the_cache_stats_door_reports_every_tier(self, admin_client: TestClient) -> None:
        resp = admin_client.get("/api/v1/metrics/cache")
        assert resp.status_code == 200
        body = resp.json()
        # Was `{"response_cache", "compute_cache"}` until Redis landed; an exact set is
        # the right assertion for a door whose job is to enumerate what the process runs,
        # and it is what caught the third tier being absent.
        assert set(body) == {"response_cache", "compute_cache", "redis"}
        assert body["response_cache"]["hits"] >= 0 and body["response_cache"]["hit_rate"] >= 0.0
        assert isinstance(body["redis"]["redis_available"], bool)
