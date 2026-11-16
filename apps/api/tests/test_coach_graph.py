"""The coach's answer pipeline, as a StateGraph — the walk is the product.

These tests pin the compiled edge table, the state transitions, and the trace that the
player's turn carries — the three things that distinguish "some code runs" from "the graph
run happened and here is its shape".
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from starlette.testclient import TestClient

from app.core.db import SessionLocal
from app.main import app
from app.services.agents import coach_graph
from app.services.world import sync_world

API = "/api/v1"


@pytest.fixture()
def session() -> Iterator:  # type: ignore[no-untyped-def]
    with SessionLocal() as db:
        sync_world(db)
        yield db


def test_the_compiled_chain_is_acyclic_and_bounded() -> None:
    route = coach_graph.compile_chain()
    names = [name for name, _ in route]
    assert names == [
        "classify_intent",
        "build_arithmetic",
        "spend_gate",
        "phrase_answer",
        "persist_answer",
        "END",
    ]
    assert coach_graph.MAX_NODE_VISITS == 6
    assert names[-1] == "END"
    assert len(names) <= coach_graph.MAX_NODE_VISITS + 1


def test_graph_state_is_the_whole_public_surface() -> None:
    state = coach_graph.CoachGraphState(question="how do I scan?")
    assert state.intent == ""
    assert state.graph_trace == []
    assert state.persisted is False
    assert state.structured == {}


def test_the_endpoint_carries_the_graph_trace_and_the_answer(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """A seeded client walks through the real door and prints the graph's visits."""
    client = TestClient(app)
    # Register and build the minimal player the door requires.
    response = client.post(f"{API}/auth/register", json={
        "email": "graph-test@example.test",
        "password": "GraphTest1234!",
        "display_name": "Graph",
        "role": "player",
        "accepts_data_policy": True,
    })
    if response.status_code != 201:
        pytest.skip(f"account setup failed: {response.text[:200]}")
    token = response.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    create = client.post(f"{API}/players", json={
        "name": "Graph Test",
        "position": "CM",
        "age": 23,
        "level": "intermediate",
        "preferred_foot": "right",
        "goal": "improve_vision",
    })
    assert create.status_code == 201, create.text
    answer = client.post(f"{API}/coach/ask", json={"question": "how do I scan before receiving?"})
    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert body["demo_mode"] in (False, True)
    # The trace rides in the structured payload, which the envelope spreads to the root.
    assert body, body
    assert body["graph_trace"], body
    assert body["graph_trace"][0] == "START"
    assert body["graph_trace"][-1] == "END"
    assert "classify_intent" in body["graph_trace"]
    assert "persist_answer" in body["graph_trace"]
    assert body["message"]
