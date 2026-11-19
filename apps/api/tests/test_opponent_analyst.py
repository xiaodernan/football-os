"""The Opposition Analyst — a plan authored from the shape pair or honestly refused."""

from __future__ import annotations

import json
from typing import Any

import app.services.opponent_analyst as opponent_analyst
from app.providers import LlmResult


def _good_payload() -> dict[str, Any]:
    def phase(name: str, trigger: str, action: str) -> dict[str, str]:
        return {"name": name, "trigger": trigger, "action": action}

    return {
        "headline": "Their 4-3-3 pressed us into hurry — we bait the bait, and play the third pass.",
        "phases": [
            phase("Out of possession", "their first step to the ball", "hold our shape; keeper-first build-up through the middle"),
            phase("Bait and break", "winger presses our fullback", "hit the space behind him with an immediate one-touch release"),
            phase("Sustained attack", "the ball crosses halfway", "overload the weak side with third-man runs"),
            phase("Defensive transition", "the ball turns over", "immediate five-second counter-press on the zone where we lost it"),
        ],
        "blocks": [
            "double pivot splits to the edges of the box at goal kicks",
            "weak-foot switches by the fullback over the top",
            "third-man runs from the eight into the half-space",
            "near-post run across the six-yard box",
        ],
        "counters": [
            "high press with the front three man-to-man",
            "midfield swarm (closing the eight's reception lane)",
        ],
        "one_more": "Once this sticks, add the keeper-to-fullback curl pass in the third phase.",
        "evidence": [
            "opponent_shape=4-3-3 pressing high",
            "own_shape=4-2-3-1 rest defence",
            "levers=weak-foot crosses and fullback overlaps",
        ],
        "echo": "4-3-3",
    }


class _FakeProvider:
    name = "fake-provider"

    def __init__(self, responder):
        self._responder = responder
        self.calls: list[dict[str, Any]] = []

    def complete(self, *, system, prompt, max_tokens=800, temperature=0.4, prompt_cache_key=None):
        self.calls.append({"system": system, "prompt": prompt, "prompt_cache_key": prompt_cache_key})
        return self._responder(system=system, prompt=prompt, prompt_cache_key=prompt_cache_key)


def _provider_returning(payload: dict[str, Any]):
    return _FakeProvider(
        lambda system, prompt, prompt_cache_key=None, **kwargs: LlmResult(
            text=json.dumps(payload, ensure_ascii=False),
            provider="fake-provider",
            model="fake-model",
            demo_mode=False,
            input_tokens=1500,
            output_tokens=420,
            cached_input_tokens=1200,
            cache_reported=True,
        )
    )


def test_opponent_brief_lands_under_contract_and_persists(auth_client, monkeypatch) -> None:
    fake = _provider_returning(_good_payload())
    monkeypatch.setattr(opponent_analyst, "get_llm_provider", lambda: fake)

    player = auth_client.post(
        "/api/v1/players",
        json={"name": "CM Stub", "position": "CM", "age": 24, "level": "intermediate", "preferred_foot": "right", "goal": "become_box_to_box"},
    )
    assert player.status_code == 201

    response = auth_client.post(
        "/api/v1/tactics/opponent-brief",
        json={
            "opponent_shape": "4-3-3 pressing high",
            "own_shape": "4-2-3-1 rest defence",
            "levers": "weak-foot crosses and fullback overlaps",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["answered"] is True
    assert len(body["phases"]) == 4
    assert body["verify"]["ok"] is True
    assert body["provider"] == "fake-provider"
    assert body["graph_trace"][0] == "START"
    assert body["graph_trace"][-1] == "END"
    assert fake.calls[0]["prompt_cache_key"] in (None, "tactics.opponent_analyst.draft")
    assert len(body["evidence"]) >= 3


def test_echo_must_echo_the_opponent_shape(auth_client, monkeypatch) -> None:
    payload = _good_payload()
    payload["echo"] = "5-2-2-1"
    fake = _provider_returning(payload)
    monkeypatch.setattr(opponent_analyst, "get_llm_provider", lambda: fake)

    player = auth_client.post(
        "/api/v1/players",
        json={"name": "CM Fantom", "position": "CM", "age": 23, "level": "beginner", "preferred_foot": "left", "goal": "become_box_to_box"},
    )
    assert player.status_code == 201

    response = auth_client.post(
        "/api/v1/tactics/opponent-brief",
        json={"opponent_shape": "4-3-3 pressing high", "own_shape": "4-2-3-1 rest defence"},
    )
    body = response.json()
    assert body["answered"] is False
    assert body["verify"]["repair_passes"] == 1
    assert any("echo" in v.lower() for v in body["verify"]["failures"])


def test_repair_recovers_a_first_bad_draft(auth_client, monkeypatch) -> None:
    good = _good_payload()
    first = _good_payload()
    first.pop("echo")

    def responder(*, system, prompt, prompt_cache_key=None, **kwargs):
        if "opponent_analyst_repair" in (prompt or "") or "Repair" in (system or ""):
            return LlmResult(text=json.dumps(good, ensure_ascii=False), provider="fake", model="fake", demo_mode=False, input_tokens=10, output_tokens=10)
        return LlmResult(text=json.dumps(first, ensure_ascii=False), provider="fake", model="fake", demo_mode=False, input_tokens=10, output_tokens=10)

    fake = _FakeProvider(responder)
    monkeypatch.setattr(opponent_analyst, "get_llm_provider", lambda: fake)

    player = auth_client.post(
        "/api/v1/players",
        json={"name": "CM Repair", "position": "CM", "age": 22, "level": "beginner", "preferred_foot": "right", "goal": "become_box_to_box"},
    )
    assert player.status_code == 201

    response = auth_client.post(
        "/api/v1/tactics/opponent-brief",
        json={"opponent_shape": "4-3-3 pressing high", "own_shape": "4-2-3-1 rest defence"},
    )
    body = response.json()
    assert body["answered"] is True
    assert body["verify"]["repair_passes"] == 1
    assert body["graph_trace"].count("repair") == 1


def test_opponent_brief_without_a_player_is_a_conflict(auth_client) -> None:
    response = auth_client.post(
        "/api/v1/tactics/opponent-brief",
        json={"opponent_shape": "4-3-3 pressing high", "own_shape": "4-2-3-1 rest defence"},
    )
    assert response.status_code == 409


def test_opponent_brief_requires_authentication(client) -> None:
    response = client.post(
        "/api/v1/tactics/opponent-brief",
        json={"opponent_shape": "4-3-3 pressing high", "own_shape": "4-2-3-1 rest defence"},
    )
    assert response.status_code == 401
