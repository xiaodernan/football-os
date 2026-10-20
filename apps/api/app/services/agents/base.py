"""Base agent class for M11 multi-agent system (spec §31-§33).

Every agent inherits from BaseAgent, which provides memory access, session tracking,
and a standard interaction interface. Agents are stateless between calls — all context
comes from persisted memories scoped to user + agent_type + optional session_id.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.services.agent_memory import get_memory, list_memories, set_memory


class BaseAgent(ABC):
    """Abstract base for all M11 agents.

    Subclasses must implement `run()` which receives a user query and returns a
    structured response. The base class provides memory helpers so agents can persist
    intermediate results, maintain conversation state, or cache expensive computations.
    """

    def __init__(self, db: Session, user_id: str, agent_type: str, session_id: str | None = None) -> None:
        self.db = db
        self.user_id = user_id
        self.agent_type = agent_type
        self.session_id = session_id
        #: Every store the last `run()` touched, in the order it touched them. The orchestrator
        #: snapshots this list before a step and stores the slice in that step's trace, so a
        #: composite answer can say *what was looked up*, not only what it said.
        self.tool_calls: list[dict[str, Any]] = []

    def record_tool_call(
        self,
        tool: str,
        *,
        args: dict[str, Any] | None = None,
        ok: bool = True,
        detail: str | None = None,
    ) -> None:
        """Record one tool invocation for the orchestrator's trace.

        A tool call is a read or write against a store this agent does not own — the knowledge
        corpus, the tactical catalogue, the player rows, the training catalogue. Agents whose answer
        is a static explanation (simulation, video) record none, and their step's empty list is the
        honest reading: nothing was looked up.
        """
        self.tool_calls.append(
            {
                "tool": tool,
                "args": args or {},
                "ok": bool(ok),
                "detail": detail,
                "at": datetime.now(UTC).isoformat(),
            }
        )

    # ------------------------------------------------------------------
    # Memory helpers — thin wrappers around the agent_memory service
    # ------------------------------------------------------------------

    def remember(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        """Persist one fact for this agent."""
        set_memory(
            self.db,
            user_id=self.user_id,
            agent_type=self.agent_type,
            key=key,
            value=value if isinstance(value, dict) else {"data": value},
            session_id=self.session_id,
            ttl_seconds=ttl_seconds,
        )

    def recall(self, key: str) -> Any | None:
        """Retrieve one named fact, or None if missing/expired."""
        return get_memory(self.db, user_id=self.user_id, agent_type=self.agent_type, key=key)

    def list_context(self) -> list[dict[str, Any]]:
        """Return all non-expired memories for this agent+session."""
        return list_memories(self.db, user_id=self.user_id, agent_type=self.agent_type, session_id=self.session_id)

    # ------------------------------------------------------------------
    # Abstract interaction interface
    # ------------------------------------------------------------------

    @abstractmethod
    def run(self, query: str, **kwargs: Any) -> dict[str, Any]:
        """Execute one agent turn. Returns a JSON-serialisable response dict."""
        ...
