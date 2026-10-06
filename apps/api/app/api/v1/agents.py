"""Agent orchestrator endpoints (M11 §31-§33).

Provides a unified interface to interact with registered agents. Each endpoint is
auth-gated and scoped to the calling user. Agents persist their state via the
agent_memory system (§34), so conversations can resume across sessions.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import current_user
from app.models import User
from app.services.agents import get_agent, list_available_agents

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
    steps: list[dict[str, Any]]  # Each step: {agent_type, query, result_summary}
    confidence: float | None = None
    from_cache: bool = False


@router.post("/composite", response_model=CompositeTaskResponse)
def agent_composite(
    body: CompositeTaskRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> CompositeTaskResponse:
    """Execute a composite task that chains multiple agents.

    Example: 'Analyze Arsenal's recent matches, identify their attacking patterns,
    compare with my player profile, and recommend training to bridge the gap.'

    This orchestrates: TacticalAgent (patterns) → ScoutAgent (match data) →
    CoachAgent (training recommendations).
    """
    query_lower = body.query.lower()
    steps = []

    # Step 1: Determine which agents to invoke based on query content
    needs_tactics = any(word in query_lower for word in ["tactic", "formation", "pattern", "pressing", "width", "space"])
    needs_scout = any(word in query_lower for word in ["player", "scout", "find", "search", "candidate"])
    needs_coach = any(word in query_lower for word in ["train", "improve", "practice", "drill", "plan", "session"])
    needs_simulation = any(word in query_lower for word in ["simulate", "predict", "what if", "match outcome"])
    needs_video = any(word in query_lower for word in ["video", "clip", "footage", "upload", "analyse"])
    needs_research = any(word in query_lower for word in ["research", "history", "evolution", "origin", "explain", "concept", "principle"])
    
    # If nothing specific matched, default to research
    if not any([needs_tactics, needs_scout, needs_coach, needs_simulation, needs_video, needs_research]):
        needs_research = True

    # Step 2: Execute agents in sequence, passing context between them
    final_answer_parts = []
    overall_confidence = 0.0
    agent_count = 0

    if needs_tactics:
        try:
            tactical_agent = get_agent(db=db, user_id=user.id, agent_type="tactical", session_id=body.session_id)
            tactical_query = f"Analyze tactical aspects: {body.query}"
            tactical_result = tactical_agent.run(query=tactical_query)
            steps.append({
                "agent_type": "tactical",
                "query": tactical_query,
                "result_summary": tactical_result["answer"][:200] + "..." if len(tactical_result["answer"]) > 200 else tactical_result["answer"],
            })
            final_answer_parts.append(f"**Tactical Analysis:**\n{tactical_result['answer']}")
            overall_confidence += tactical_result.get("confidence", 0.0)
            agent_count += 1
            db.commit()
        except Exception as exc:
            steps.append({"agent_type": "tactical", "error": str(exc)})

    if needs_scout:
        try:
            scout_agent = get_agent(db=db, user_id=user.id, agent_type="scout", session_id=body.session_id)
            scout_query = f"Search for players: {body.query}"
            scout_result = scout_agent.run(query=scout_query)
            steps.append({
                "agent_type": "scout",
                "query": scout_query,
                "result_summary": scout_result["answer"][:200] + "..." if len(scout_result["answer"]) > 200 else scout_result["answer"],
            })
            final_answer_parts.append(f"**Player Search:**\n{scout_result['answer']}")
            overall_confidence += scout_result.get("confidence", 0.0)
            agent_count += 1
            db.commit()
        except Exception as exc:
            steps.append({"agent_type": "scout", "error": str(exc)})

    if needs_coach:
        try:
            coach_agent = get_agent(db=db, user_id=user.id, agent_type="coach", session_id=body.session_id)
            coach_query = f"Training recommendation: {body.query}"
            coach_result = coach_agent.run(query=coach_query)
            steps.append({
                "agent_type": "coach",
                "query": coach_query,
                "result_summary": coach_result["answer"][:200] + "..." if len(coach_result["answer"]) > 200 else coach_result["answer"],
            })
            final_answer_parts.append(f"**Training Recommendation:**\n{coach_result['answer']}")
            overall_confidence += coach_result.get("confidence", 0.0)
            agent_count += 1
            db.commit()
        except Exception as exc:
            steps.append({"agent_type": "coach", "error": str(exc)})

    if needs_simulation:
        try:
            sim_agent = get_agent(db=db, user_id=user.id, agent_type="simulation", session_id=body.session_id)
            sim_query = f"Simulation question: {body.query}"
            sim_result = sim_agent.run(query=sim_query)
            steps.append({
                "agent_type": "simulation",
                "query": sim_query,
                "result_summary": sim_result["answer"][:200] + "..." if len(sim_result["answer"]) > 200 else sim_result["answer"],
            })
            final_answer_parts.append(f"**Simulation Insight:**\n{sim_result['answer']}")
            overall_confidence += sim_result.get("confidence", 0.0)
            agent_count += 1
            db.commit()
        except Exception as exc:
            steps.append({"agent_type": "simulation", "error": str(exc)})

    if needs_video:
        try:
            video_agent = get_agent(db=db, user_id=user.id, agent_type="video", session_id=body.session_id)
            video_query = f"Video analysis: {body.query}"
            video_result = video_agent.run(query=video_query)
            steps.append({
                "agent_type": "video",
                "query": video_query,
                "result_summary": video_result["answer"][:200] + "..." if len(video_result["answer"]) > 200 else video_result["answer"],
            })
            final_answer_parts.append(f"**Video Analysis:**\n{video_result['answer']}")
            overall_confidence += video_result.get("confidence", 0.0)
            agent_count += 1
            db.commit()
        except Exception as exc:
            steps.append({"agent_type": "video", "error": str(exc)})

    if needs_research:
        try:
            research_agent = get_agent(db=db, user_id=user.id, agent_type="research", session_id=body.session_id)
            research_result = research_agent.run(query=body.query)
            steps.append({
                "agent_type": "research",
                "query": body.query,
                "result_summary": research_result["answer"][:200] + "..." if len(research_result["answer"]) > 200 else research_result["answer"],
            })
            final_answer_parts.append(f"**Research Answer:**\n{research_result['answer']}")
            overall_confidence += research_result.get("confidence", 0.0)
            agent_count += 1
            db.commit()
        except Exception as exc:
            steps.append({"agent_type": "research", "error": str(exc)})

    # Step 3: Aggregate results
    if final_answer_parts:
        answer = "\n\n---\n\n".join(final_answer_parts)
    else:
        answer = "No agents were able to process this query. Try rephrasing with keywords related to tactics, scouting, training, simulation, or video analysis."

    confidence = overall_confidence / agent_count if agent_count > 0 else 0.0

    return CompositeTaskResponse(
        answer=answer,
        steps=steps,
        confidence=confidence,
        from_cache=False,
    )


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
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    result = agent.run(query=body.query)
    db.commit()
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
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"memories": agent.list_context()}
