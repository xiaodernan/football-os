"""M11 §33's stored orchestration trace — the smallest composite task, end to end.

PLAN.md's Item 5 asks for "an orchestrator, one specialist, one tool call and a stored trace ...
measured against §64's benchmark". The orchestrator and the specialists landed with M11; the trace did
not. `/agents/composite` returned its steps to the caller and kept nothing, so a run that answered
could not be audited afterwards and the benchmark had no run to cite.

This file is the gate for the stored half, and it holds three claims a reader would otherwise have to
take on faith:

* a run leaves a trace a later request can read, naming the agents that ran, what each one looked up
  and how long each one took;
* a trace belongs to the account that ran it — a foreign id and an id that was never issued earn the
  same answer, so the door cannot confirm which ids exist;
* a run where every step failed still leaves a trace, because that is the run worth reading.

The benchmark-side claim — that each §64 composite case leaves a retrievable trace — is measured in
`tests/test_agents_benchmark.py` as the harness's `trace_integrity` metric.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import agents as agents_package

PASSWORD = "TestPass1234!"

#: A query that names no agent's keywords, so the orchestrator's fallback plan runs exactly one
#: specialist: `research`. One agent, one `knowledge.ask`, one trace — §33's smallest composite task.
SMALLEST_TASK = "What is the offside rule?"


def _client(tag: str = "") -> TestClient:
    """Create an authenticated client for a fresh user."""
    client = TestClient(app)
    email = f"trace-{tag}{uuid4().hex[:8]}@example.test"
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "display_name": "Trace Tester",
            "role": "player",
            "accepts_data_policy": True,
        },
    )
    assert response.status_code == 201, f"Registration failed: {response.json()}"
    client.headers.update({"Authorization": f"Bearer {response.json()['access_token']}"})
    return client


class TestStoredTrace:
    def test_the_smallest_composite_task_leaves_one_readable_trace(self) -> None:
        """One specialist, at least one tool call, one stored trace — Item 5's smallest task."""
        client = _client()
        response = client.post("/api/v1/agents/composite", json={"query": SMALLEST_TASK})
        assert response.status_code == 200, f"composite failed: {response.json()}"
        body = response.json()

        trace_id = body.get("trace_id")
        assert trace_id and trace_id.startswith("trc_"), f"no trace id on the answer: {trace_id!r}"
        assert body.get("status") == "completed", f"status read {body.get('status')!r}"

        # The response's own steps carry the tool calls the trace will hold.
        assert len(body["steps"]) == 1, f"the fallback plan ran {len(body['steps'])} steps"
        assert body["steps"][0]["agent_type"] == "research"
        assert body["steps"][0]["tool_calls"], "the research step recorded no tool call"

        fetched = client.get(f"/api/v1/agents/traces/{trace_id}")
        assert fetched.status_code == 200, f"stored trace unreadable: {fetched.json()}"
        trace = fetched.json()

        assert trace["trace_id"] == trace_id
        assert trace["query"] == SMALLEST_TASK
        assert trace["status"] == "completed"
        assert trace["plan"]["steps"] == ["research"]
        assert len(trace["steps"]) == 1

        step = trace["steps"][0]
        assert step["agent_type"] == "research"
        assert step["status"] == "completed"
        tools = [call["tool"] for call in step["tool_calls"]]
        assert "knowledge.ask" in tools, f"the research step's tools read {tools!r}"
        assert [call["tool"] for call in body["steps"][0]["tool_calls"]] == tools

        # Timings are ordered, and the step's duration is the arithmetic of its own two stamps.
        started = datetime.fromisoformat(step["started_at"])
        completed = datetime.fromisoformat(step["completed_at"])
        assert started <= completed
        assert step["duration_ms"] == round((completed - started).total_seconds() * 1000)
        assert datetime.fromisoformat(trace["started_at"]) <= datetime.fromisoformat(trace["completed_at"])

    def test_a_foreign_or_never_issued_trace_answers_the_same_404(self) -> None:
        """Absence must not confirm which ids exist."""
        owner = _client("owner-")
        response = owner.post("/api/v1/agents/composite", json={"query": SMALLEST_TASK})
        assert response.status_code == 200
        trace_id = response.json()["trace_id"]

        stranger = _client("stranger-")
        foreign = stranger.get(f"/api/v1/agents/traces/{trace_id}")
        missing = stranger.get("/api/v1/agents/traces/trc_never-issued-nor-ever-will-be")

        assert foreign.status_code == 404, f"a foreign trace read {foreign.status_code}: {foreign.json()}"
        assert missing.status_code == 404, f"a missing trace read {missing.status_code}"
        assert foreign.json()["detail"]["code"] == "no_such_trace"
        assert missing.json()["detail"]["code"] == "no_such_trace"

        # The owner can still read it: the stranger's 404 is ownership, not absence.
        assert owner.get(f"/api/v1/agents/traces/{trace_id}").status_code == 200

    def test_the_list_door_lists_only_the_callers_runs(self) -> None:
        alice = _client("alice-")
        bob = _client("bob-")

        first = alice.post("/api/v1/agents/composite", json={"query": SMALLEST_TASK}).json()["trace_id"]
        second = alice.post("/api/v1/agents/composite", json={"query": "Explain the history of pressing"}).json()["trace_id"]
        bob_only = bob.post("/api/v1/agents/composite", json={"query": SMALLEST_TASK}).json()["trace_id"]

        listed = alice.get("/api/v1/agents/traces").json()["traces"]
        ids = [trace["trace_id"] for trace in listed]
        assert first in ids and second in ids, f"alice's runs are missing from {ids!r}"
        assert bob_only not in ids, "alice's list leaked another account's run"

        assert all(trace["trace_id"] not in ids for trace in bob.get("/api/v1/agents/traces").json()["traces"])

        # The list shape carries what a reader needs to choose one, without the answer bodies.
        entry = next(trace for trace in listed if trace["trace_id"] == first)
        assert entry["step_count"] == 1
        assert entry["agents"] == ["research"]
        assert entry["tool_call_count"] >= 1
        assert "answer" not in entry

    def test_a_run_where_every_step_failed_is_still_traced(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The run worth reading is the one that failed; it must not be the run that is dropped."""
        monkeypatch.delitem(agents_package.AGENT_REGISTRY, "tactical")
        client = _client("failed-")
        response = client.post(
            "/api/v1/agents/composite",
            json={"query": "Analyze our tactical pressing shape and formation width"},
        )
        assert response.status_code == 200, response.json()
        body = response.json()
        assert body["status"] == "failed", f"status read {body['status']!r}"
        trace_id = body["trace_id"]

        trace = client.get(f"/api/v1/agents/traces/{trace_id}")
        assert trace.status_code == 200, f"the failed run left no trace: {trace.json()}"
        steps = trace.json()["steps"]
        assert steps, "the failed trace holds no step"
        assert all(step["status"] == "failed" for step in steps), steps
        assert all(step["error"] for step in steps), f"a failed step recorded no error: {steps!r}"

    def test_a_trace_needs_a_session(self) -> None:
        """Both trace doors are auth-gated like every other agents door."""
        anonymous = TestClient(app)
        assert anonymous.get("/api/v1/agents/traces").status_code == 401
        assert anonymous.get("/api/v1/agents/traces/trc_whatever").status_code == 401
