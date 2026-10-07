"""Agent memory API tests (M11 §34)."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.db import SessionLocal
from app.main import app
from app.models import AgentMemory, User
from app.services.agent_memory import prune_expired, set_memory

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


class TestPruneExpired:
    """`prune_expired` must delete exactly what the read side refuses — measured at a pinned clock.

    Before the fix (frozen 2026-01-15 12:00 UTC, measured via `.scratch/r89_mypy_probe.py`) the SQLite
    bind processor stored `expires_at` as `"2026-01-15 14:00:00.000000"` while the raw-`text()` bound
    passed `"2026-01-15T12:00:00+00:00"`; lexicographic ' ' < 'T' made a row expiring later *today*
    compare smaller than now, and prune removed it (removed=2, nothing left). The red this case paints on
    that code is SQLite-format-specific: PostgreSQL coerces the isoformat string to timestamptz and was
    already right.
    """

    def test_prune_removes_only_rows_the_read_side_refuses(self, monkeypatch) -> None:
        frozen = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
        monkeypatch.setattr("app.services.agent_memory._now", lambda: frozen)
        user = f"prune-{uuid4().hex[:8]}"
        with SessionLocal() as db:
            db.add(User(id=user, email=f"{user}@example.test", password_hash="x", display_name="Prune Tester"))
            db.commit()
            set_memory(db, user_id=user, agent_type="coach", key="live", value={"a": 1}, ttl_seconds=7200)
            set_memory(db, user_id=user, agent_type="coach", key="dead", value={"b": 2}, ttl_seconds=-60)
            db.commit()
            removed = prune_expired(db)
            db.commit()
            remaining = {
                row.key
                for row in db.scalars(select(AgentMemory).where(AgentMemory.user_id == user)).all()
            }
        assert removed == 1, (
            "a memory expiring later today was pruned — the comparison bound's format no longer matches storage"
        )
        assert remaining == {"live"}
