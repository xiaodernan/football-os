"""Tests for M12 model router (§45-§46).

Verifies that the model router exposes provider status, cost tracking, and refuses unsafe runtime switches.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

PASSWORD = "TestPass1234!"


def _client() -> TestClient:
    """Create an authenticated client."""
    client = TestClient(app)
    email = f"router-{uuid4().hex[:8]}@example.test"
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "display_name": "Router Tester",
            "role": "player",
            "accepts_data_policy": True,
        },
    )
    assert response.status_code == 201, f"Registration failed: {response.json()}"
    client.headers.update({"Authorization": f"Bearer {response.json()['access_token']}"})
    return client


class TestModelRouter:
    """Model router endpoint tests."""

    def test_provider_status(self) -> None:
        """Should report all provider types and demo mode status."""
        client = _client()
        resp = client.get("/api/v1/model-router/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "llm" in data
        assert "embedding" in data
        assert "reranker" in data
        assert "vision" in data
        assert "storage" in data
        assert "demo_mode" in data
        assert "budget_limit" in data

    def test_provider_status_demo_mode(self) -> None:
        """In demo mode, LLM should be 'mock'."""
        client = _client()
        resp = client.get("/api/v1/model-router/status")
        assert resp.status_code == 200
        data = resp.json()
        # In this test environment, we're in demo mode
        assert data["demo_mode"] is True
        assert data["llm"] == "mock"

    def test_switch_refused(self) -> None:
        """Runtime provider switching should be refused (env-driven only)."""
        client = _client()
        resp = client.post(
            "/api/v1/model-router/switch",
            json={"provider_type": "llm", "provider_name": "openai"},
        )
        assert resp.status_code == 403
        data = resp.json()
        assert "environment variable" in data["detail"].lower()

    def test_costs_endpoint(self) -> None:
        """Should report today's spending and budget."""
        client = _client()
        resp = client.get("/api/v1/model-router/costs")
        assert resp.status_code == 200
        data = resp.json()
        assert "spent_today_usd" in data
        assert "budget_limit_usd" in data
        assert "remaining_usd" in data
        assert "budget_exhausted" in data
        assert isinstance(data["spent_today_usd"], int | float)
        assert isinstance(data["budget_exhausted"], bool)

    def test_budget_not_exhausted_in_test(self) -> None:
        """Fresh test user should have budget remaining."""
        client = _client()
        resp = client.get("/api/v1/model-router/costs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["budget_exhausted"] is False
        assert data["remaining_usd"] > 0
