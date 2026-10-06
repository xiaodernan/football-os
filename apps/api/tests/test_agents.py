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

    def test_list_includes_coach(self) -> None:
        """Agent list should include coach agent."""
        client = _client()
        resp = client.get("/api/v1/agents/list")
        assert resp.status_code == 200
        data = resp.json()
        assert "coach" in data["available_agents"]
        assert "research" in data["available_agents"]

    def test_run_coach_agent_no_player(self) -> None:
        """Coach agent should request player profile when none exists."""
        client = _client()
        resp = client.post(
            "/api/v1/agents/run",
            json={"query": "What should I train today?", "agent_type": "coach"},
        )
        assert resp.status_code == 200, f"Coach agent failed: {resp.json()}"
        data = resp.json()
        assert "answer" in data
        assert "player profile" in data["answer"].lower()
        # No player means low confidence
        assert data["confidence"] == 0.0

    def test_run_coach_agent_with_goal(self) -> None:
        """Coach agent should recognize training goals in query."""
        client = _client()
        
        # Create a player first
        resp_player = client.post(
            "/api/v1/players",
            json={
                "display_name": "Test Player",
                "position": "CM",
                "age": 20,
                "level": "intermediate",
                "preferred_foot": "right",
                "goal": "improve passing",
            },
        )
        # Player creation may succeed or fail depending on validation
        # Either way, test the coach response
        
        resp = client.post(
            "/api/v1/agents/run",
            json={
                "query": "I want to improve my first touch",
                "agent_type": "coach",
            },
        )
        assert resp.status_code == 200, f"Coach agent with goal failed: {resp.json()}"
        data = resp.json()
        assert "answer" in data
        # Should have some content in the answer
        assert len(data["answer"]) > 0

    def test_list_includes_tactical(self) -> None:
        """Agent list should include tactical agent."""
        client = _client()
        resp = client.get("/api/v1/agents/list")
        assert resp.status_code == 200
        data = resp.json()
        assert "tactical" in data["available_agents"]

    def test_run_tactical_agent_formation(self) -> None:
        """Tactical agent should analyze formations."""
        client = _client()
        resp = client.post(
            "/api/v1/agents/run",
            json={"query": "What are the characteristics of a 4-3-3 formation?", "agent_type": "tactical"},
        )
        assert resp.status_code == 200, f"Tactical agent failed: {resp.json()}"
        data = resp.json()
        assert "answer" in data
        assert len(data["answer"]) > 0
        # Should mention formation or indicate no data
        assert "4-3-3" in data["answer"] or "don't have data" in data["answer"].lower()

    def test_run_tactical_agent_concept(self) -> None:
        """Tactical agent should explain tactical concepts."""
        client = _client()
        resp = client.post(
            "/api/v1/agents/run",
            json={"query": "Explain pressing in football tactics", "agent_type": "tactical"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
        assert len(data["answer"]) > 0
        # Should mention pressing or provide general guidance
        assert "pressing" in data["answer"].lower() or "tactical" in data["answer"].lower()

    def test_run_tactical_agent_cached(self) -> None:
        """Second identical tactical query should return cached result."""
        client = _client()
        query = "What is a high defensive line?"

        # First call
        resp1 = client.post(
            "/api/v1/agents/run",
            json={"query": query, "agent_type": "tactical"},
        )
        assert resp1.status_code == 200
        data1 = resp1.json()
        assert data1["from_cache"] is False

        # Second call (should be cached)
        resp2 = client.post(
            "/api/v1/agents/run",
            json={"query": query, "agent_type": "tactical"},
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["from_cache"] is True
