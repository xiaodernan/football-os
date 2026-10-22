"""Tests for M12 metrics and observability (§58-§60).

Verifies that metrics endpoints expose system health, database performance, and provider usage.
"""

from __future__ import annotations

import time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app

PASSWORD = "TestPass1234!"

METRICS_PATHS = (
    "/api/v1/metrics/system",
    "/api/v1/metrics/database",
    "/api/v1/metrics/providers",
    "/api/v1/metrics/cost-optimisation",
    "/api/v1/metrics/latency",
    "/api/v1/metrics/cache",
)


def _player_client() -> TestClient:
    """A freshly registered player — registration is the account's first session."""
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


class TestTheOperatorStanding:
    """Every metrics row describes the platform, so every door asks for the operator's standing.

    The module named administrators as its audience while each door was guarded only by a session,
    so any registered player could read the platform's account totals, AI spend, provider mix,
    latency profile and cache tiers. These cases hold both ends of the fix: the player is refused
    at all six doors, and the admin still reaches each one.
    """

    @pytest.mark.parametrize("path", METRICS_PATHS)
    def test_a_player_is_refused_and_an_admin_is_answered(self, path: str, admin_client: TestClient) -> None:
        refused = _player_client().get(path)
        assert refused.status_code == 403, f"a player read {path} and got {refused.status_code}: {refused.text[:300]}"
        detail = refused.json()["detail"]
        assert detail["code"] == "insufficient_role", f"{path} answered {detail['code']!r}, not the platform's role refusal"
        assert detail["held"] == "player"
        assert detail["required"] == ["admin"], f"{path} names {detail['required']} as the standing, not the operators"

        answered = admin_client.get(path)
        assert answered.status_code == 200, f"the operator was refused at {path}: {answered.text[:300]}"


class TestMetricsEndpoints:
    """Metrics endpoint tests."""

    def test_system_metrics(self, admin_client: TestClient) -> None:
        """Should report system-level metrics."""
        resp = admin_client.get("/api/v1/metrics/system")
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

    def test_system_metrics_reports_the_uptime_this_process_actually_has(self, admin_client: TestClient) -> None:
        """Should report how long the process has been running, not the zero it used to answer.

        The row's own docstring promises uptime, and the implementation carried `uptime_seconds=0.0` with a
        comment asking for process start time tracking that never happened — so the door answered the same
        number on a freshly booted process and on one that had served requests for a week. An uptime that
        reads zero is not a small number; it is the one figure an operator uses to tell "just restarted"
        from "never falls over", and it was lying about both.
        """
        first = admin_client.get("/api/v1/metrics/system").json()["uptime_seconds"]
        time.sleep(0.1)
        second = admin_client.get("/api/v1/metrics/system").json()["uptime_seconds"]
        assert first > 0.0, "the door promises uptime; a process that has imported its own modules has some"
        assert second > first, "uptime is the process age, so it cannot stand still between two calls"

    def test_active_users_today_counts_a_user_who_never_spent_a_model_call(self, admin_client: TestClient) -> None:
        """Should count a user who is active, not one who spent a model call.

        The row counted `DISTINCT ModelCall.user_id` over today, which answers a different question than
        its name: how many accounts bought an AI call. Someone who logs in and spends the day on training,
        tactics or boards is active today and invisible here, so an operator watching this number would
        read a busy product as an empty one. `User.last_login_at` is the column that records what the row
        promises, and registration — which hands back a usable token and is therefore the account's first
        session — was the one path that never stamped it.
        """
        before = admin_client.get("/api/v1/metrics/system").json()["active_users_today"]

        # A brand-new account: it has logged in and has issued no model call at all.
        _player_client()
        after = admin_client.get("/api/v1/metrics/system").json()["active_users_today"]

        assert after > before, "an account that just registered is active today, and it bought no call"

    def test_database_metrics(self, admin_client: TestClient) -> None:
        """Should report database-level metrics."""
        resp = admin_client.get("/api/v1/metrics/database")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_model_calls" in data
        assert "model_calls_today" in data
        assert "total_video_assets" in data
        assert "avg_model_call_latency_ms" in data
        assert "success_rate" in data
        assert isinstance(data["total_model_calls"], int)
        assert 0.0 <= data["success_rate"] <= 1.0

    def test_provider_metrics(self, admin_client: TestClient) -> None:
        """Should report AI provider usage metrics."""
        resp = admin_client.get("/api/v1/metrics/providers")
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

    def test_provider_breakdown(self, admin_client: TestClient) -> None:
        """Provider metrics should show mock provider in demo mode."""
        resp = admin_client.get("/api/v1/metrics/providers")
        assert resp.status_code == 200
        data = resp.json()
        # In test environment, we're in demo mode with mock provider
        if data["total_calls"] > 0:
            assert "mock" in data["calls_by_provider"] or len(data["calls_by_provider"]) > 0

    def test_cache_stats_name_every_tier_the_process_runs(self, admin_client: TestClient) -> None:
        """The door must report Redis, not only the two in-memory caches.

        `RedisCache` landed in M12 and degrades to the in-memory tier when no instance
        answers. `/metrics/cache` still returned `get_cache_stats()` alone — the two
        TTLCache instances — so an operator reading the door would have seen a
        description of the process that omitted a cache tier the process actually has.
        Reporting it is also how an operator learns whether it is *serving*, which on a
        host whose Redis needs a password is the interesting half of the answer.
        """
        resp = admin_client.get("/api/v1/metrics/cache")
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
