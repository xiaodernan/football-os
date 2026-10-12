"""Tests for M12 metrics and observability (§58-§60).

Verifies that metrics endpoints expose system health, database performance, and provider usage.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

PASSWORD = "TestPass1234!"


def _client() -> TestClient:
    """Create an authenticated client."""
    client = TestClient(app)
    email = f"metrics-{uuid4().hex[:8]}@example.test"
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "display_name": "Metrics Tester",
            "role": "player",
            "accepts_data_policy": True,
        },
    )
    assert response.status_code == 201, f"Registration failed: {response.json()}"
    client.headers.update({"Authorization": f"Bearer {response.json()['access_token']}"})
    return client


class TestMetricsEndpoints:
    """Metrics endpoint tests."""

    def test_system_metrics(self) -> None:
        """Should report system-level metrics."""
        client = _client()
        resp = client.get("/api/v1/metrics/system")
        assert resp.status_code == 200
        data = resp.json()
        assert "uptime_seconds" in data
        assert "request_count" in data
        assert "error_count" in data
        assert "avg_latency_ms" in data
        assert "active_users_today" in data
        assert "total_users" in data
        assert isinstance(data["total_users"], int)
        assert data["total_users"] > 0

    def test_database_metrics(self) -> None:
        """Should report database-level metrics."""
        client = _client()
        resp = client.get("/api/v1/metrics/database")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_model_calls" in data
        assert "model_calls_today" in data
        assert "total_video_assets" in data
        assert "avg_model_call_latency_ms" in data
        assert "success_rate" in data
        assert isinstance(data["total_model_calls"], int)
        assert 0.0 <= data["success_rate"] <= 1.0

    def test_provider_metrics(self) -> None:
        """Should report AI provider usage metrics."""
        client = _client()
        resp = client.get("/api/v1/metrics/providers")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_calls" in data
        assert "calls_by_provider" in data
        assert "total_cost_usd" in data
        assert "cost_today_usd" in data
        assert "avg_latency_ms" in data
        assert "demo_mode_percentage" in data
        assert isinstance(data["calls_by_provider"], dict)
        assert isinstance(data["total_cost_usd"], int | float)
        assert 0.0 <= data["demo_mode_percentage"] <= 100.0

    def test_provider_breakdown(self) -> None:
        """Provider metrics should show mock provider in demo mode."""
        client = _client()
        resp = client.get("/api/v1/metrics/providers")
        assert resp.status_code == 200
        data = resp.json()
        # In test environment, we're in demo mode with mock provider
        if data["total_calls"] > 0:
            assert "mock" in data["calls_by_provider"] or len(data["calls_by_provider"]) > 0

    def test_cache_stats_name_every_tier_the_process_runs(self) -> None:
        """The door must report Redis, not only the two in-memory caches.

        `RedisCache` landed in M12 and degrades to the in-memory tier when no instance
        answers. `/metrics/cache` still returned `get_cache_stats()` alone — the two
        TTLCache instances — so an operator reading the door would have seen a
        description of the process that omitted a cache tier the process actually has.
        Reporting it is also how an operator learns whether it is *serving*, which on a
        host whose Redis needs a password is the interesting half of the answer.
        """
        client = _client()
        resp = client.get("/api/v1/metrics/cache")
        assert resp.status_code == 200
        data = resp.json()

        assert "response_cache" in data
        assert "compute_cache" in data
        assert "redis" in data, "the Redis tier exists in the process and must appear in its own metrics"
        assert isinstance(data["redis"]["redis_available"], bool)
        assert "hit_rate" in data["redis"]["fallback"]

    def test_cache_stats_refuse_an_anonymous_caller(self) -> None:
        """Cache statistics describe the process, so they stay behind the auth gate."""
        client = TestClient(app)
        resp = client.get("/api/v1/metrics/cache")
        assert resp.status_code == 401

    def test_metrics_auth_gated(self) -> None:
        """Metrics endpoints should require authentication."""
        client = TestClient(app)
        resp = client.get("/api/v1/metrics/system")
        assert resp.status_code == 401
