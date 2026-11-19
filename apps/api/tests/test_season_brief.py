"""The Season Brief — the model reads the athlete's own fingerprint or the door refuses."""

from __future__ import annotations

import json
from typing import Any

import app.services.season_brief as season_brief
from app.models import CoachMessage
from app.providers import LlmResult


def _good_payload() -> dict[str, Any]:
    def mk(day: int, focus: str) -> dict[str, Any]:
        return {
            "day": day,
            "focus": focus,
            "minutes": 45,
            "blocks": [
                "wall two-touch ladder at match speed",
                "receiving across the body into a 1m box",
                "8-cone slalom at pace, one touch",
            ],
        }

    themes = ["first_touch", "passing", "ball_mastery"]
    arc = [mk(1, themes[0]), mk(2, themes[1]), mk(3, themes[0]), mk(4, themes[2]), mk(5, themes[1]), mk(6, themes[2])]
    return {
        "headline": "Your first touch decides the week — own it from day one.",
        "themes": themes,
        "arc": arc,
        "one_more": "Then layer in scanning to receive open and play both sides.",
        "evidence": ["sessions=0", "completed=0", "xp_28d=0"],
        "echo": "CM",
    }


class _FakeProvider:
    name = "fake-provider"

    def __init__(self, responder):
        self._responder = responder
        self.calls: list[dict[str, Any]] = []

    def complete(self, *, system, prompt, max_tokens=800, temperature=0.4, prompt_cache_key=None):
        self.calls.append({"system": system, "prompt": prompt, "max_tokens": max_tokens, "temperature": temperature, "prompt_cache_key": prompt_cache_key})
        return self._responder(system=system, prompt=prompt, prompt_cache_key=prompt_cache_key)


def _provider_returning(payload: dict[str, Any], **expected):
    def responder(*, system, prompt, prompt_cache_key=None, **kwargs):
        return LlmResult(
            text=json.dumps(payload, ensure_ascii=False),
            provider="fake-provider",
            model="fake-model",
            demo_mode=False,
            input_tokens=1200,
            output_tokens=400,
            cached_input_tokens=1100,
            cache_reported=True,
        )

    return _FakeProvider(responder)


def test_brief_authors_under_contract_and_persists(auth_client, monkeypatch) -> None:
    fake = _provider_returning(_good_payload())
    monkeypatch.setattr(season_brief, "get_llm_provider", lambda: fake)

    player = auth_client.post(
        "/api/v1/players",
        json={"name": "CM Stub", "position": "CM", "age": 24, "level": "intermediate", "preferred_foot": "right", "goal": "become_box_to_box"},
    )
    assert player.status_code == 201

    response = auth_client.post("/api/v1/trainings/season-brief")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["answered"] is True
    assert body["themes"] == ["first_touch", "passing", "ball_mastery"]
    assert len(body["arc"]) == 6
    assert body["verify"]["ok"] is True
    assert body["provider"] == "fake-provider"
    assert body["graph_trace"][0] == "START"
    assert body["graph_trace"][-1] == "END"
    assert "draft" in body["graph_trace"]
    assert fake.calls[0]["prompt_cache_key"] in (None, "trainings.season_brief.draft")

    # The brief was persisted as a coach message with the structured payload.
    from app.core.db import SessionLocal

    session = SessionLocal()
    try:
        rows = session.query(CoachMessage).filter(CoachMessage.kind == "season_brief").all()
        assert len(rows) >= 1
        assert rows[-1].structured["verify"]["ok"] is True
    finally:
        session.close()


def test_bogus_theme_is_refused_after_repair_once(auth_client, monkeypatch) -> None:
    payload = _good_payload()
    payload["themes"] = ["ultra_press_power", "passing", "ball_mastery"]
    payload["arc"][0]["focus"] = "ultra_press_power"

    # Both draft and repair return the same refused payload.
    fake = _provider_returning(payload)
    monkeypatch.setattr(season_brief, "get_llm_provider", lambda: fake)

    player = auth_client.post(
        "/api/v1/players",
        json={"name": "CM Bogus", "position": "CM", "age": 21, "level": "intermediate", "preferred_foot": "right", "goal": "become_box_to_box"},
    )
    assert player.status_code == 201

    response = auth_client.post("/api/v1/trainings/season-brief")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["answered"] is False
    assert body["verify"]["ok"] is False
    assert any("whitelist" in failure for failure in body["verify"]["failures"])
    # Repair is bounded at one pass.
    assert body["verify"]["repair_passes"] == 1


def test_repair_recovers_a_first_bad_draft(auth_client, monkeypatch) -> None:
    good = _good_payload()
    first = _good_payload()
    first.pop("echo")  # missing echo forces a repair

    def responder(*, system, prompt, prompt_cache_key=None, **kwargs):
        if "season_brief_repair" in (prompt or "") or "Repair" in (system or ""):
            return LlmResult(text=json.dumps(good, ensure_ascii=False), provider="fake", model="fake", demo_mode=False, input_tokens=10, output_tokens=10)
        return LlmResult(text=json.dumps(first, ensure_ascii=False), provider="fake", model="fake", demo_mode=False, input_tokens=10, output_tokens=10)

    fake = _FakeProvider(responder)
    monkeypatch.setattr(season_brief, "get_llm_provider", lambda: fake)

    player = auth_client.post(
        "/api/v1/players",
        json={"name": "CM Repair", "position": "CM", "age": 22, "level": "beginner", "preferred_foot": "left", "goal": "become_box_to_box"},
    )
    assert player.status_code == 201

    response = auth_client.post("/api/v1/trainings/season-brief")
    body = response.json()
    assert response.status_code == 200, response.text
    assert body["answered"] is True
    assert body["verify"]["ok"] is True
    assert body["verify"]["repair_passes"] == 1


def test_season_brief_without_a_player_is_a_conflict(auth_client) -> None:
    response = auth_client.post("/api/v1/trainings/season-brief")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "no_player"


def test_season_brief_requires_authentication(client) -> None:
    response = client.post("/api/v1/trainings/season-brief")
    assert response.status_code == 401


def test_cache_key_carries_the_user_shard(auth_client, monkeypatch) -> None:
    fake = _provider_returning(_good_payload())
    monkeypatch.setattr(season_brief, "get_llm_provider", lambda: fake)

    player = auth_client.post(
        "/api/v1/players",
        json={"name": "Shard Check", "position": "CM", "age": 25, "level": "advanced", "preferred_foot": "right", "goal": "become_box_to_box"},
    )
    assert player.status_code == 201

    response = auth_client.post("/api/v1/trainings/season-brief")
    assert response.status_code == 200
    # The middleware and the real provider compose the shard on the wire (see
    # tests/test_prompt_cache_scope.py); the service passes the static base key.
    assert fake.calls[0]["prompt_cache_key"] in (None, "trainings.season_brief.draft")
