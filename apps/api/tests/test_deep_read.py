"""The Deep Read — full chapters into the prompt, verified by the walk."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.providers import LlmResult
from app.services import deep_read

API = "/api/v1"


class _StubProvider:
    name = "stub"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 800, temperature: float = 0.4, prompt_cache_key: str | None = None) -> LlmResult:  # noqa: ARG002
        assert system.startswith("\n\nTHE LIBRARY THE PASSAGES COME FROM"), "the charter must lead at byte 0"
        assert prompt_cache_key in ("knowledge.deep_read.draft", "knowledge.deep_read.repair")
        return LlmResult(
            text="Reading the game is a two-structure problem before it is a passing question [1]. The midfielder names the pockets, the legs that fill them [1][2]. Sources: 1, 2",
            provider="stub",
            model="stub-1",
            demo_mode=False,
            input_tokens=21000,
            output_tokens=80,
            cached_input_tokens=19800,
            cache_reported=True,
            latency_ms=1,
        )


class _BrokenProvider:
    name = "stub"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 800, temperature: float = 0.4, prompt_cache_key: str | None = None) -> LlmResult:  # noqa: ARG002
        raise RuntimeError("gateway unreachable")


def _stub_gather(monkeypatch: pytest.MonkeyPatch) -> None:
    chapters = [
        {"ref": 1, "slug": "how-to-read-a-game", "title": "Reading a match: the questions to ask in each phase", "score": 0.61, "bytes": 9000},
        {"ref": 2, "slug": "pressing-in-two-stages", "title": "Pressing in two stages — when the first bank is the cap, the second is the trap", "score": 0.44, "bytes": 6000},
    ]

    def _gather(state: deep_read.DeepReadState, db: object) -> deep_read.DeepReadState:  # noqa: ARG001
        state.available = True
        state.chapters = chapters
        state.chapter_bodies = {chapter["ref"]: "x" * chapter["bytes"] for chapter in chapters}
        state.context_bytes = sum(chapter["bytes"] for chapter in chapters)
        state.timings_ms["gather"] = 1
        return state

    monkeypatch.setattr(deep_read, "_node_gather", _gather)
    monkeypatch.setattr(deep_read, "budget_exhausted", lambda db: False)
    monkeypatch.setattr(deep_read, "record_model_call_safely", lambda *, result, feature, user_id=None: True)


def test_the_walk_prints_its_trace_and_loads_full_chapters(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_gather(monkeypatch)
    monkeypatch.setattr(deep_read, "get_llm_provider", lambda: _StubProvider())
    payload = deep_read.compute_deep_read(None, "how do I read a game as a midfielder")
    assert payload["answered"] is True
    assert payload["graph_trace"] == ["START", "gather", "draft", "verify", "repair", "END"]
    assert payload["verify"]["ok"] is True
    assert payload["chapters_used"] and len(payload["chapters_used"]) == 2
    # the charter is the payload's floor: 39,702 bytes before the chapters sat on top
    assert payload["context_bytes"] == 15000
    assert payload["input_tokens"] == 21000
    assert payload["cached_input_tokens"] == 19800
    assert payload["cache_reported"] is True


def test_an_unreachable_gateway_refuses_honestly(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_gather(monkeypatch)
    monkeypatch.setattr(deep_read, "get_llm_provider", lambda: _BrokenProvider())
    payload = deep_read.compute_deep_read(None, "how do I read a game as a midfielder")
    assert payload["answered"] is False
    assert payload["error"] == "gateway unreachable"


def test_a_draft_without_markers_triggers_one_repair_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_gather(monkeypatch)

    class _RepairProvider(_StubProvider):
        def complete(self, *, system, prompt, max_tokens=800, temperature=0.2, prompt_cache_key=None):  # noqa: ARG002
            assert system.startswith("\n\nTHE LIBRARY THE PASSAGES COME FROM")
            if prompt_cache_key == "knowledge.deep_read.repair":
                return LlmResult(
                    text="Repaired answer [1]. Sources: 1",
                    provider="stub",
                    model="stub-1",
                    demo_mode=False,
                    input_tokens=20000,
                    output_tokens=30,
                    cached_input_tokens=19000,
                    cache_reported=True,
                    latency_ms=1,
                )
            assert system.startswith("\n\nTHE LIBRARY THE PASSAGES COME FROM")
            return LlmResult(
                text="This draft cites nothing at all.",
                provider="stub",
                model="stub-1",
                demo_mode=False,
                input_tokens=21000,
                output_tokens=20,
                cached_input_tokens=20000,
                cache_reported=True,
                latency_ms=1,
            )

    monkeypatch.setattr(deep_read, "get_llm_provider", lambda: _RepairProvider())
    payload = deep_read.compute_deep_read(None, "read")
    assert payload["graph_trace"] == ["START", "gather", "draft", "verify", "repair", "END"]
    assert payload["verify"]["repair_passes"] == 1
    assert payload["verify"]["ok"] is True


def test_a_budget_exhausted_gateway_answers_from_the_shelf(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_gather(monkeypatch)
    monkeypatch.setattr(deep_read, "budget_exhausted", lambda db: True)
    payload = deep_read.compute_deep_read(None, "read")
    assert payload["demo_mode"] is True or payload["provider"] == "rule-engine-demo"
    assert payload["graph_trace"] == ["START", "gather", "draft", "verify", "repair", "END"]


def test_the_door_is_public_to_authenticated_users() -> None:
    with TestClient(app) as client:
        anonymous = client.post(f"{API}/knowledge/deep-ask", json={"question": "how do I read a game?"})
        assert anonymous.status_code == 401
