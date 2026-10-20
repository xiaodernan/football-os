"""Stored orchestration traces (M11 §33).

§33's composite task is the first place one request runs more than one agent, and until this module the
run lived only in the response body: `/agents/composite` returned its steps, dropped them on the way
out, and no later reader could say which agents ran, what each one looked up, or how long it took. A
benchmark could measure the answer and nothing about the run that produced it.

A trace is per-account agent state, so it is stored on the tier §34 already built for that
(`agent_memories`, under the `orchestrator` agent type and a `trace:` key prefix) rather than in a new
table: it is user-scoped by construction, it expires like every other fragment, and it needs no
migration. The prefix is what separates a trace from an orchestrator's ordinary memories — a reader
listing `/agents/context?agent_type=orchestrator` sees both, and this module is where that boundary is
written.

The trace is written *after* the run, including when every step failed: a failed run is exactly the
one an operator needs to read. Its TTL is 30 days, long enough for the §64 benchmark's runs to be
cited by the document that quotes their scores.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.agent_memory import get_memory, list_memories, set_memory

#: The agent type traces are filed under in `agent_memories`.
TRACE_AGENT_TYPE = "orchestrator"

#: A trace key reads `trace:{trace_id}`; nothing else in this namespace may begin with it.
TRACE_KEY_PREFIX = "trace:"

#: 30 days. A run's audit value is highest while the benchmark document that cites it is being read.
TRACE_TTL_SECONDS = 30 * 24 * 60 * 60


def trace_key(trace_id: str) -> str:
    """The memory key one trace id is filed under."""
    return f"{TRACE_KEY_PREFIX}{trace_id}"


def store_trace(
    db: Session,
    *,
    user_id: str,
    trace: dict[str, Any],
    session_id: str | None = None,
) -> str:
    """Persist one orchestration trace and return its id."""
    trace_id = str(trace["trace_id"])
    set_memory(
        db,
        user_id=user_id,
        agent_type=TRACE_AGENT_TYPE,
        key=trace_key(trace_id),
        value=trace,
        session_id=session_id,
        ttl_seconds=TRACE_TTL_SECONDS,
    )
    return trace_id


def get_trace(db: Session, *, user_id: str, trace_id: str) -> dict[str, Any] | None:
    """Return one trace for this account, or None if it never existed, expired, or is another account's.

    The three Nones are deliberately one value: a foreign trace must answer exactly like one that was
    never issued, or the door confirms which ids exist.
    """
    value = get_memory(db, user_id=user_id, agent_type=TRACE_AGENT_TYPE, key=trace_key(trace_id))
    return value if isinstance(value, dict) else None


def list_traces(db: Session, *, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
    """Return this account's traces, newest first, at most `limit` of them."""
    memories = list_memories(db, user_id=user_id, agent_type=TRACE_AGENT_TYPE)
    traces = [
        memory["value"]
        for memory in memories
        if str(memory.get("key", "")).startswith(TRACE_KEY_PREFIX) and isinstance(memory.get("value"), dict)
    ]
    traces.sort(key=lambda trace: str(trace.get("started_at") or ""), reverse=True)
    return traces[: max(0, limit)]


def summary(trace: dict[str, Any]) -> dict[str, Any]:
    """The list door's shape: enough to choose a trace, without the answer bodies."""
    steps = trace.get("steps") or []
    return {
        "trace_id": trace.get("trace_id"),
        "query": trace.get("query"),
        "session_id": trace.get("session_id"),
        "status": trace.get("status"),
        "started_at": trace.get("started_at"),
        "completed_at": trace.get("completed_at"),
        "confidence": trace.get("confidence"),
        "step_count": len(steps),
        "agents": [step.get("agent_type") for step in steps],
        "tool_call_count": sum(len(step.get("tool_calls") or []) for step in steps),
    }


__all__ = [
    "TRACE_AGENT_TYPE",
    "TRACE_KEY_PREFIX",
    "TRACE_TTL_SECONDS",
    "trace_key",
    "store_trace",
    "get_trace",
    "list_traces",
    "summary",
]
