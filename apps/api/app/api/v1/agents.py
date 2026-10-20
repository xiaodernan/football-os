"""Agent orchestrator endpoints (M11 §31-§33).

Provides a unified interface to interact with registered agents. Each endpoint is
auth-gated and scoped to the calling user. Agents persist their state via the
agent_memory system (§34), so conversations can resume across sessions.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import current_user
from app.models import User
from app.services.agents import get_agent, list_available_agents, run_composite_task, traces

router = APIRouter(prefix="/agents", tags=["agents"])


class AgentRunRequest(BaseModel):
    query: str
    agent_type: str = "research"
    session_id: str | None = None


class AgentRunResponse(BaseModel):
    answer: str
    citations: list[dict[str, str]] | None = None
    confidence: float | None = None
    from_cache: bool = False
    stored_key: str | None = None


class AgentListResponse(BaseModel):
    available_agents: list[str]


class CompositeTaskRequest(BaseModel):
    """Complex multi-step query requiring multiple agent types."""

    query: str
    session_id: str | None = None


class CompositeTaskResponse(BaseModel):
    """Result from orchestrating multiple agents."""

    answer: str
    steps: list[dict[str, Any]]  # Each step: {agent_type, query, result_summary, tool_calls, ...}
    confidence: float | None = None
    from_cache: bool = False
    trace_id: str | None = None
    status: str | None = None


class TraceListResponse(BaseModel):
    """This account's stored orchestration runs, newest first."""

    traces: list[dict[str, Any]]


@router.post("/composite", response_model=CompositeTaskResponse)
def agent_composite(
    body: CompositeTaskRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> CompositeTaskResponse:
    """Execute a composite task using the FootballOrchestrator.

    Example: 'Analyze Arsenal's recent matches, identify their attacking patterns,
    compare with my player profile, and recommend training to bridge the gap.'

    The FootballOrchestrator plans the execution, routes to appropriate agents,
    passes context between them, and aggregates results. The run's trace is stored
    under `orchestrator` in agent memory and is retrievable at `/agents/traces/{id}`
    — including when every step failed, which is exactly the run worth reading.
    """
    result = run_composite_task(
        db=db,
        user_id=user.id,
        query=body.query,
        session_id=body.session_id,
    )
    db.commit()

    return CompositeTaskResponse(
        answer=result["answer"],
        steps=result["steps"],
        confidence=result["confidence"],
        from_cache=result["from_cache"],
        trace_id=result.get("trace_id"),
        status=result.get("status"),
    )


@router.get("/traces", response_model=TraceListResponse)
def agent_traces(
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> TraceListResponse:
    """List this account's stored orchestration traces, newest first."""
    return TraceListResponse(traces=[traces.summary(trace) for trace in traces.list_traces(db, user_id=user.id, limit=limit)])


@router.get("/traces/{trace_id}")
def agent_trace(
    trace_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return one stored trace.

    A trace that never existed, expired, or belongs to another account answers the same 404 —
    absence must not confirm which ids exist.
    """
    trace = traces.get_trace(db, user_id=user.id, trace_id=trace_id)
    if trace is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "no_such_trace", "message": f"no stored trace {trace_id!r}"},
        )
    return trace


@router.get("/list", response_model=AgentListResponse)
def agents_list() -> AgentListResponse:
    """List all registered agent types."""
    return AgentListResponse(available_agents=list_available_agents())


@router.post("/run", response_model=AgentRunResponse)
def agent_run(
    body: AgentRunRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> AgentRunResponse:
    """Execute one agent turn. The agent reads its memories, processes the query, and persists results."""
    try:
        agent = get_agent(db=db, user_id=user.id, agent_type=body.agent_type, session_id=body.session_id)
    except ValueError as exc:
        #: §51's shape: the message is the registry's own sentence (it already names what it holds),
        #: and the code is what the answer table binds to 422 — a caller's own word for a type this
        #: catalogue does not have, the same answer `unknown_role` gives an unknown tactical role.
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": "unknown_agent_type", "message": str(exc)}) from exc

    result = agent.run(query=body.query)
    db.commit()
    # AgentRunResponse declares string-valued citations; the knowledge layer's citation objects
    # carry numbers (ordinal, score) — coerce at this boundary, not in the shared citation shape,
    # which the /knowledge endpoints and the web types read as numbers.
    if result.get("citations"):
        result["citations"] = [{key: str(value) for key, value in citation.items()} for citation in result["citations"]]
    return AgentRunResponse(**result)


@router.get("/context")
def agent_context(
    agent_type: str = Query("research"),
    session_id: str | None = Query(None),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, list[dict[str, Any]]]:
    """List all non-expired memories for this agent+session."""
    try:
        agent = get_agent(db=db, user_id=user.id, agent_type=agent_type, session_id=session_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"code": "unknown_agent_type", "message": str(exc)}) from exc

    return {"memories": agent.list_context()}
