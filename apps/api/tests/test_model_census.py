"""The admin console's AI ledger census — aggregates-only, at the same passphrase boundary."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from starlette.testclient import TestClient

from app.core.db import SessionLocal
from app.main import app
from app.models import ModelCall

API = "/api/v1"
PASSPHRASE = "123"


@pytest.fixture()
def session() -> Iterator[Any]:
    row = SessionLocal()
    try:
        row.query(ModelCall).delete()
        row.commit()
        yield row
    finally:
        row.rollback()
        row.close()


def _call(
    db: Any,
    *,
    feature: str,
    provider: str = "openai",
    in_tokens: int = 120,
    out_tokens: int = 40,
    cached: int = 0,
    reported: bool = True,
    success: bool = True,
    demo: bool = False,
    latency_ms: int = 90,
    cost: float = 0.0,
    days_ago: int = 0,
    error: str | None = None,
) -> None:
    row = ModelCall(
        id=f"mc_{feature}_{days_ago}_{in_tokens}_{cached}_{latency_ms}_{cost}".replace(".", "_")[:40],
        provider=provider,
        model="gpt-6.1-terra",
        feature=feature,
        user_id=None,
        input_tokens=in_tokens,
        output_tokens=out_tokens,
        reasoning_tokens=0,
        cached_input_tokens=cached,
        cache_reported=reported,
        latency_ms=latency_ms,
        estimated_cost_usd=cost,
        actual_cost_usd=cost,
        success=success,
        demo_mode=demo,
        error=error,
        created_at=datetime.now(UTC) - timedelta(days=days_ago),
    )
    db.add(row)
    db.commit()


class TestModelCensus:
    def test_the_passphrase_still_rules(self) -> None:
        client = TestClient(app)
        assert client.get(f"{API}/admin/model-census").status_code == 401
        assert client.get(f"{API}/admin/model-census", headers={"x-admin-passphrase": "wrong"}).status_code == 401

    def test_an_empty_ledger_answers_zeros_and_stays_honest(self, session: Any) -> None:
        from app.services.model_census import compute_model_census

        body = compute_model_census(session, window_days=30)
        assert body["available"] is True
        assert body["totals"]["calls"] == 0
        assert body["totals"]["cached_share_reported"] == 0.0
        assert body["by_feature"] == []
        assert body["errors"] == []
        assert len(body["daily"]) == 30

    def test_the_census_counts_reported_rows_only_for_cache_share(self, session: Any) -> None:
        _call(session, feature="world.a.read", in_tokens=1000, cached=900, reported=True, days_ago=1)
        _call(session, feature="world.b.read", in_tokens=1000, cached=100, reported=False, days_ago=1)
        _call(session, feature="world.a.read", in_tokens=500, cached=0, reported=False, success=False, error="rate_limited", days_ago=0)

        from app.services.model_census import compute_model_census

        body = compute_model_census(session, window_days=7)
        assert body["totals"]["calls"] == 3
        assert body["totals"]["reported_rows"] == 1
        assert body["totals"]["cached_share_reported"] == 0.9
        assert body["totals"]["failures"] == 1
        assert body["totals"]["failure_rate"] == round(1 / 3, 4)
        features = {row["feature"]: row for row in body["by_feature"]}
        assert features["world.a.read"]["calls"] == 2
        assert features["world.a.read"]["failures"] == 1
        assert features["world.b.read"]["cached_share_reported"] == 0.0
        assert body["errors"] and body["errors"][0]["sample"].startswith("world.a.read:")

    def test_rows_older_than_the_window_are_not_censused(self, session: Any) -> None:
        _call(session, feature="world.old.read", in_tokens=999, cached=999, days_ago=60)

        from app.services.model_census import compute_model_census

        body = compute_model_census(session, window_days=7)
        assert body["totals"]["calls"] == 0

    def test_the_door_answers_for_the_passphrase(self, session: Any) -> None:
        client = TestClient(app)
        response = client.get(f"{API}/admin/model-census", headers={"x-admin-passphrase": PASSPHRASE})
        assert response.status_code == 200
        body = response.json()
        assert body["available"] is True
        assert "totals" in body and "daily" in body and "errors" in body
