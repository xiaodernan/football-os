"""Tests for M11 agent orchestrator (§31-§33).

Verifies that agents can be listed, invoked, and that they persist state via agent memory.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

PASSWORD = "TestPass1234!"  # Must be at least 10 characters


def _client() -> TestClient:
    """Create an authenticated client for a fresh user."""
    client = TestClient(app)
    email = f"agent-{uuid4().hex[:8]}@example.test"
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "display_name": "Agent Tester",
            "role": "player",
            "accepts_data_policy": True,
        },
    )
    assert response.status_code == 201, f"Registration failed: {response.json()}"
    client.headers.update({"Authorization": f"Bearer {response.json()['access_token']}"})
    return client


class TestAgentOrchestrator:
    """Agent list and run endpoints."""

    def test_list_agents(self) -> None:
        """Should return at least the research agent."""
        client = _client()
        resp = client.get("/api/v1/agents/list")
        assert resp.status_code == 200
        data = resp.json()
        assert "research" in data["available_agents"]

    def test_run_research_agent(self) -> None:
        """Research agent should answer a football question."""
        client = _client()
        resp = client.post(
            "/api/v1/agents/run",
            json={"query": "What is offside?", "agent_type": "research"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
        assert data["from_cache"] is False
        assert "stored_key" in data

    def test_run_cached_answer(self) -> None:
        """Second identical query should return cached result."""
        client = _client()
        query = "What is a penalty kick?"

        # First call
        resp1 = client.post(
            "/api/v1/agents/run",
            json={"query": query, "agent_type": "research"},
        )
        assert resp1.status_code == 200, f"First call failed: {resp1.json()}"
        data1 = resp1.json()
        assert data1["from_cache"] is False

        # Second call (should be cached)
        resp2 = client.post(
            "/api/v1/agents/run",
            json={"query": query, "agent_type": "research"},
        )
        assert resp2.status_code == 200, f"Second call failed: {resp2.json()}"
        data2 = resp2.json()
        assert data2["from_cache"] is True

    def test_run_unknown_agent(self) -> None:
        """Should return 400 for unregistered agent type."""
        client = _client()
        resp = client.post(
            "/api/v1/agents/run",
            json={"query": "test", "agent_type": "nonexistent"},
        )
        assert resp.status_code == 400

    def test_agent_context(self) -> None:
        """Should list memories persisted by the agent."""
        client = _client()

        # Run a query to create some memories
        client.post(
            "/api/v1/agents/run",
            json={"query": "What is a corner kick?", "agent_type": "research"},
        )

        # Check context
        resp = client.get("/api/v1/agents/context?agent_type=research")
        assert resp.status_code == 200
        data = resp.json()
        assert "memories" in data
        # Should have at least the answer and conversation history
        assert len(data["memories"]) >= 1
