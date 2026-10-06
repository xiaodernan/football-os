"""Agent memory service (M11 §34).

Persist and retrieve named facts for each agent type, scoped to a user with optional
TTL-based expiration. Every operation is idempotent: setting the same key overwrites.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import AgentMemory


def _now() -> datetime:
    return datetime.now(UTC)


def set_memory(
    db: Session,
    *,
    user_id: str,
    agent_type: str,
    key: str,
    value: Any,
    session_id: str | None = None,
    ttl_seconds: int | None = None,
) -> AgentMemory:
    """Store or overwrite one named fact. Returns the row that was written."""
    expires_at: datetime | None = None
    if ttl_seconds:
        from datetime import timedelta
        expires_at = (_now() + timedelta(seconds=ttl_seconds)).replace(microsecond=0)

    existing = db.scalar(
        select(AgentMemory).where(
            AgentMemory.user_id == user_id,
            AgentMemory.agent_type == agent_type,
            AgentMemory.key == key,
        )
    )
    if existing:
        existing.value_json = value
        existing.session_id = session_id
        existing.expires_at = expires_at
        db.flush([existing])
        return existing

    row = AgentMemory(
        user_id=user_id,
        agent_type=agent_type,
        key=key,
        value_json=value,
        session_id=session_id,
        expires_at=expires_at,
    )
    db.add(row)
    db.flush([row])
    return row


def get_memory(db: Session, *, user_id: str, agent_type: str, key: str) -> dict[str, Any] | None:
    """Return the value for one key, or None if missing/expired."""
    row = db.scalar(
        select(AgentMemory).where(
            AgentMemory.user_id == user_id,
            AgentMemory.agent_type == agent_type,
            AgentMemory.key == key,
        )
    )
    if row is None:
        return None
    if row.expires_at:
        expires_aware = row.expires_at.replace(tzinfo=UTC) if row.expires_at.tzinfo is None else row.expires_at
        if expires_aware < _now():
            return None
    return row.value_json


def list_memories(
    db: Session,
    *,
    user_id: str,
    agent_type: str,
    session_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return all non-expired memories for this user+agent, optionally filtered by session."""
    stmt = select(AgentMemory).where(
        AgentMemory.user_id == user_id,
        AgentMemory.agent_type == agent_type,
    )
    if session_id:
        stmt = stmt.where(AgentMemory.session_id == session_id)

    rows = db.scalars(stmt).all()
    now = _now()
    result: list[dict[str, Any]] = []
    for row in rows:
        if row.expires_at:
            expires_aware = row.expires_at.replace(tzinfo=UTC) if row.expires_at.tzinfo is None else row.expires_at
            if expires_aware < now:
                continue
        result.append({
            "key": row.key,
            "value": row.value_json,
            "session_id": row.session_id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        })
    return result


def delete_memory(db: Session, *, user_id: str, agent_type: str, key: str) -> bool:
    """Delete one key. Returns True if a row was removed."""
    stmt = delete(AgentMemory).where(
        AgentMemory.user_id == user_id,
        AgentMemory.agent_type == agent_type,
        AgentMemory.key == key,
    )
    result = db.execute(stmt)
    return result.rowcount > 0


def prune_expired(db: Session) -> int:
    """Delete all expired rows. Returns count of rows removed."""
    # Use database-level comparison to avoid timezone issues
    from sqlalchemy import text
    result = db.execute(text("DELETE FROM agent_memories WHERE expires_at IS NOT NULL AND expires_at < :now"), {"now": _now().isoformat()})
    return result.rowcount
