"""Agent memory API tests (M11 §34)."""

from __future__ import annotations

import time
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

PASSWORD = "testpass123"


def _client() -> TestClient:
    """Create a fresh client with an authenticated session."""
    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/register",
        json={"email": f"memory-{uuid4().hex[:8]}@example.test", "password": PASSWORD, "display_name": "Memory Tester", "role": "player", "accepts_data_policy": True},
    )
    assert response.status_code == 201, response.text
    client.headers.update({"Authorization": f"Bearer {response.json()['access_token']}"})
    return client


class TestAgentMemoryCrud:
    def test_set_and_get(self) -> None:
        client = _client()

        resp = client.post(
            "/api/v1/agents/memory/set",
            json={"key": "last_search", "value": {"query": "best strikers", "results": 5}},
        )
        assert resp.status_code == 200
        assert resp.json()["key"] == "last_search"

        resp = client.get("/api/v1/agents/memory/get?key=last_search")
        assert resp.status_code == 200
        data = resp.json()
        assert data["key"] == "last_search"
        assert data["value"]["query"] == "best strikers"

    def test_overwrite(self) -> None:
        client = _client()

        client.post(
            "/api/v1/agents/memory/set",
            json={"key": "counter", "value": {"n": 1}},
        )
        client.post(
            "/api/v1/agents/memory/set",
            json={"key": "counter", "value": {"n": 2}},
        )

        resp = client.get("/api/v1/agents/memory/get?key=counter")
        assert resp.status_code == 200
        assert resp.json()["value"]["n"] == 2

    def test_list_memories(self) -> None:
        client = _client()

        client.post(
            "/api/v1/agents/memory/set",
            json={"key": "fact_a", "value": {"x": 1}},
        )
        client.post(
            "/api/v1/agents/memory/set",
            json={"key": "fact_b", "value": {"y": 2}},
        )

        resp = client.get("/api/v1/agents/memory/list")
        assert resp.status_code == 200
        memories = resp.json()["memories"]
        keys = {m["key"] for m in memories}
        assert "fact_a" in keys
        assert "fact_b" in keys

    def test_delete_memory(self) -> None:
        client = _client()

        client.post(
            "/api/v1/agents/memory/set",
            json={"key": "to_delete", "value": {"temp": True}},
        )
        resp = client.delete("/api/v1/agents/memory/delete?key=to_delete")
        assert resp.status_code == 200

        resp = client.get("/api/v1/agents/memory/get?key=to_delete")
        assert resp.status_code == 404

    def test_get_missing_returns_404(self) -> None:
        client = _client()

        resp = client.get("/api/v1/agents/memory/get?key=nonexistent")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "no_such_memory"

    def test_delete_missing_returns_404(self) -> None:
        client = _client()

        resp = client.delete("/api/v1/agents/memory/delete?key=nonexistent")
        assert resp.status_code == 404


class TestAgentMemoryTtl:
    def test_expired_memory_not_visible(self) -> None:
        """A memory with short TTL should disappear after expiration."""
        client = _client()

        # Set with 1 second TTL
        client.post(
            "/api/v1/agents/memory/set",
            json={"key": "short_lived", "value": {"expires": True}, "ttl_seconds": 1},
        )

        # Should be visible immediately
        resp = client.get("/api/v1/agents/memory/get?key=short_lived")
        assert resp.status_code == 200

        # Wait for expiration
        time.sleep(1.5)

        # Should be gone now
        resp = client.get("/api/v1/agents/memory/get?key=short_lived")
        assert resp.status_code == 404

    def test_non_expired_memory_visible(self) -> None:
        """A memory with long TTL should remain visible."""
        client = _client()

        client.post(
            "/api/v1/agents/memory/set",
            json={"key": "long_lived", "value": {"persists": True}, "ttl_seconds": 3600},
        )

        resp = client.get("/api/v1/agents/memory/get?key=long_lived")
        assert resp.status_code == 200
        assert resp.json()["value"]["persists"] is True
