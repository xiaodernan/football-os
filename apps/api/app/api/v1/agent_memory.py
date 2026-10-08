"""Agent memory endpoints (M11 §34)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import current_user
from app.models import User
from app.services.agent_memory import delete_memory, get_memory, list_memories, set_memory

router = APIRouter(prefix="/agents/memory", tags=["agent-memory"])


class MemorySetRequest(BaseModel):
    key: str
    value: dict[str, Any]
    session_id: str | None = None
    ttl_seconds: int | None = None


class MemoryGetResponse(BaseModel):
    key: str
    value: dict[str, Any] | None


class MemoryListResponse(BaseModel):
    memories: list[dict[str, Any]]


@router.post("/set")
def memory_set(
    body: MemorySetRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Store or overwrite one named fact for this agent type."""
    row = set_memory(
        db,
        user_id=user.id,
        agent_type="research",  # default agent type; parameterize later
        key=body.key,
        value=body.value,
        session_id=body.session_id,
        ttl_seconds=body.ttl_seconds,
    )
    db.commit()
    return {"status": "stored", "key": row.key}


@router.get("/get", response_model=MemoryGetResponse)
def memory_get(
    key: str = Query(...),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> MemoryGetResponse:
    """Retrieve one named fact."""
    value = get_memory(db, user_id=user.id, agent_type="research", key=key)
    if value is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "no_such_memory", "message": f"no stored memory answers to {key!r} for this agent", "key": key})
    return MemoryGetResponse(key=key, value=value)


@router.get("/list", response_model=MemoryListResponse)
def memory_list(
    session_id: str | None = Query(None),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> MemoryListResponse:
    """List all non-expired memories for this agent."""
    memories = list_memories(db, user_id=user.id, agent_type="research", session_id=session_id)
    return MemoryListResponse(memories=memories)


@router.delete("/delete")
def memory_delete(
    key: str = Query(...),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Delete one named fact."""
    removed = delete_memory(db, user_id=user.id, agent_type="research", key=key)
    db.commit()
    if not removed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"code": "no_such_memory", "message": f"no stored memory answers to {key!r} for this agent", "key": key})
    return {"status": "deleted"}
