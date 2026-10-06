"""M11 multi-agent system (spec §31-§33).

Agent registry and factory functions. Each agent type is identified by a string key
(e.g. "research", "coach", "tactical") and maps to a concrete BaseAgent subclass.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.agents.base import BaseAgent
from app.services.agents.coach import CoachAgent
from app.services.agents.research import ResearchAgent
from app.services.agents.scout import ScoutAgent
from app.services.agents.simulation import SimulationAgent
from app.services.agents.tactical import TacticalAgent

AGENT_REGISTRY: dict[str, type[BaseAgent]] = {
    "research": ResearchAgent,
    "coach": CoachAgent,
    "tactical": TacticalAgent,
    "scout": ScoutAgent,
    "simulation": SimulationAgent,
}


def get_agent(db: Session, user_id: str, agent_type: str, session_id: str | None = None) -> BaseAgent:
    """Factory: return an agent instance by type name."""
    agent_cls = AGENT_REGISTRY.get(agent_type)
    if not agent_cls:
        raise ValueError(f"Unknown agent type: {agent_type!r}. Available: {sorted(AGENT_REGISTRY)}")
    return agent_cls(db=db, user_id=user_id, agent_type=agent_type, session_id=session_id)


def list_available_agents() -> list[str]:
    """Return sorted list of registered agent type names."""
    return sorted(AGENT_REGISTRY)
