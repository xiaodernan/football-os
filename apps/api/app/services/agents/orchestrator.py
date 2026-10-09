"""Football Orchestrator — the unified agent runtime (spec §32 M11).

The orchestrator is the unified entry point for multi-agent tasks. It replaces the
keyword-based routing in the composite endpoint with a proper routing engine that
can be extended with LLM-based routing, supports context passing between agents,
and provides observability into the orchestration flow.

MVP principle: build the runtime first, enable agents gradually.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from app.services.agents.base import BaseAgent


class AgentStatus(Enum):
    """Status of an agent execution within an orchestration."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class AgentStep:
    """One agent execution step within an orchestration."""

    agent_type: str
    query: str
    status: AgentStatus = AgentStatus.PENDING
    result: dict[str, Any] | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    confidence: float = 0.0
    citations: list[dict[str, str]] = field(default_factory=list)


@dataclass
class OrchestrationPlan:
    """Execution plan for a composite task."""

    steps: list[str]  # Ordered list of agent types to invoke
    context: dict[str, Any] = field(default_factory=dict)
    max_retries: int = 1
    timeout_seconds: int = 30


@dataclass
class OrchestrationResult:
    """Result of a full orchestration run."""

    answer: str
    steps: list[AgentStep]
    confidence: float
    started_at: datetime
    completed_at: datetime
    plan: OrchestrationPlan


class RoutingRule:
    """A single routing rule: if condition matches, include agent_type in plan."""

    def __init__(
        self,
        agent_type: str,
        keywords: list[str],
        weight: float = 1.0,
        requires: list[str] | None = None,
    ) -> None:
        self.agent_type = agent_type
        self.keywords = [k.lower() for k in keywords]
        self.weight = weight
        self.requires = requires or []

    def matches(self, query: str, context: dict[str, Any]) -> bool:
        query_lower = query.lower()
        # Check if any keyword matches
        keyword_match = any(kw in query_lower for kw in self.keywords)
        # Check if required context is present
        requires_match = all(ctx in context for ctx in self.requires)
        return keyword_match and requires_match

    def score(self, query: str, context: dict[str, Any]) -> float:
        """Return a confidence score for this rule matching."""
        if not self.matches(query, context):
            return 0.0
        query_lower = query.lower()
        matches = sum(1 for kw in self.keywords if kw in query_lower)
        return (matches / len(self.keywords)) * self.weight


class FootballOrchestrator:
    """The unified agent runtime for M11 multi-agent football AI.

    Responsibilities:
    - Plan: decompose a composite query into an ordered agent execution plan
    - Execute: run agents in sequence with context passing and error handling
    - Observe: track execution status, timing, confidence
    - Extend: routing rules can be added/removed without changing core logic

    The orchestrator is the "agent runtime" — it manages the lifecycle of
    multi-agent executions and provides a single entry point for composite tasks.
    """

    # Default routing rules — can be extended without modifying this class
    DEFAULT_RULES: list[RoutingRule] = [
        RoutingRule("tactical", ["tactic", "formation", "pattern", "pressing", "width", "space", "shape", "system"], weight=1.0),
        RoutingRule("scout", ["player", "scout", "find", "search", "candidate", "signing", "transfer"], weight=1.0),
        RoutingRule("coach", ["train", "improve", "practice", "drill", "plan", "session", "fitness", "development"], weight=1.0),
        RoutingRule("simulation", ["simulate", "predict", "what if", "match outcome", "probability", "odds"], weight=1.0),
        RoutingRule("video", ["video", "clip", "footage", "upload", "analyse", "analysis", "detection"], weight=1.0),
        RoutingRule("research", ["research", "history", "evolution", "origin", "explain", "concept", "principle", "why", "how"], weight=0.8),
    ]

    def __init__(
        self,
        db: Session,
        user_id: str,
        session_id: str | None = None,
        rules: list[RoutingRule] | None = None,
    ) -> None:
        self.db = db
        self.user_id = user_id
        self.session_id = session_id
        self.rules = rules or self.DEFAULT_RULES
        self._agent_cache: dict[str, BaseAgent] = {}

    def _get_agent(self, agent_type: str) -> BaseAgent:
        """Get or create an agent instance (cached per orchestration)."""
        if agent_type not in self._agent_cache:
            # Lazy import to avoid circular imports
            from app.services.agents import get_agent

            self._agent_cache[agent_type] = get_agent(
                db=self.db,
                user_id=self.user_id,
                agent_type=agent_type,
                session_id=self.session_id,
            )
        return self._agent_cache[agent_type]

    def plan(self, query: str, context: dict[str, Any] | None = None) -> OrchestrationPlan:
        """Decompose a query into an ordered execution plan."""
        ctx = context or {}
        scored_rules = [(rule.score(query, ctx), rule) for rule in self.rules]
        scored_rules = [(s, r) for s, r in scored_rules if s > 0]
        scored_rules.sort(key=lambda x: x[0], reverse=True)

        steps = [r.agent_type for _, r in scored_rules]
        if not steps:
            steps = ["research"]  # Default fallback

        return OrchestrationPlan(
            steps=steps,
            context=ctx,
            max_retries=1,
            timeout_seconds=30,
        )

    def _build_agent_query(self, agent_type: str, original_query: str, context: dict[str, Any]) -> str:
        """Build a context-aware query for a specific agent."""
        prefixes = {
            "tactical": "Analyze tactical aspects: ",
            "scout": "Search for players: ",
            "coach": "Training recommendation: ",
            "simulation": "Simulation question: ",
            "video": "Video analysis: ",
            "research": "",
        }
        prefix = prefixes.get(agent_type, "")
        return f"{prefix}{original_query}"

    def _extract_context_from_step(self, step: AgentStep) -> dict[str, Any]:
        """Extract context from a completed step to pass to subsequent agents."""
        if not step.result:
            return {}
        result = step.result
        return {
            f"{step.agent_type}_answer": result.get("answer", ""),
            f"{step.agent_type}_citations": result.get("citations", []),
            f"{step.agent_type}_confidence": result.get("confidence", 0.0),
        }

    def execute(self, query: str, context: dict[str, Any] | None = None) -> OrchestrationResult:
        """Execute a full orchestration run."""
        started_at = datetime.now(UTC)
        plan = self.plan(query, context)
        steps: list[AgentStep] = []
        accumulated_context = context or {}

        for agent_type in plan.steps:
            step = AgentStep(agent_type=agent_type, query=self._build_agent_query(agent_type, query, accumulated_context))
            step.started_at = datetime.now(UTC)
            step.status = AgentStatus.RUNNING
            steps.append(step)

            try:
                agent = self._get_agent(agent_type)
                agent_query = step.query
                result = agent.run(query=agent_query)

                step.result = result
                step.status = AgentStatus.COMPLETED
                step.confidence = result.get("confidence", 0.0)
                step.citations = result.get("citations", [])
                step.completed_at = datetime.now(UTC)

                # Accumulate context for next agents
                accumulated_context.update(self._extract_context_from_step(step))

            except Exception as exc:
                step.status = AgentStatus.FAILED
                step.error = str(exc)
                step.completed_at = datetime.now(UTC)
                # Continue with other agents (fail-soft)

        # Aggregate results
        completed_steps = [s for s in steps if s.status == AgentStatus.COMPLETED]
        if completed_steps:
            answer_parts = []
            total_confidence = 0.0
            for step in completed_steps:
                if step.result and step.result.get("answer"):
                    answer_parts.append(f"**{step.agent_type.title()} Agent:**\n{step.result['answer']}")
                total_confidence += step.confidence
            answer = "\n\n---\n\n".join(answer_parts)
            confidence = total_confidence / len(completed_steps)
        else:
            answer = "No agents were able to process this query."
            confidence = 0.0

        completed_at = datetime.now(UTC)

        return OrchestrationResult(
            answer=answer,
            steps=steps,
            confidence=confidence,
            started_at=started_at,
            completed_at=completed_at,
            plan=plan,
        )


# Backwards-compatible function for the composite endpoint
def run_composite_task(
    db: Session,
    user_id: str,
    query: str,
    session_id: str | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute a composite task using the FootballOrchestrator.

    This is the function called by the /agents/composite endpoint.
    """
    # Lazy import to avoid circular imports
    from app.services.agents.orchestrator import FootballOrchestrator

    orchestrator = FootballOrchestrator(db, user_id, session_id)
    result = orchestrator.execute(query, context)

    return {
        "answer": result.answer,
        "steps": [
            {
                "agent_type": s.agent_type,
                "query": s.query,
                "result_summary": s.result.get("answer", "")[:200] + "..." if s.result and s.result.get("answer") and len(s.result["answer"]) > 200 else s.result.get("answer", "") if s.result else "",
                "status": s.status.value,
                "confidence": s.confidence,
                "error": s.error,
            }
            for s in result.steps
        ],
        "confidence": result.confidence,
        "from_cache": False,
    }
