"""Deep Read through a real compiled StateGraph — and the honest fallback."""

from __future__ import annotations

import pytest

from app.providers import LlmResult
from app.services import deep_read

API = "/api/v1"


class _StubProvider:
    name = "stub"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 800, temperature: float = 0.4, prompt_cache_key: str | None = None) -> LlmResult:  # noqa: ARG002
        assert prompt_cache_key in ("knowledge.deep_read.draft", "knowledge.deep_read.repair")
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
        return LlmResult(
            text="Reading the game is a two-structure problem before it is a passing question [1]. Sources: 1",
            provider="stub",
            model="stub-1",
            demo_mode=False,
            input_tokens=21000,
            output_tokens=80,
            cached_input_tokens=19800,
            cache_reported=True,
            latency_ms=1,
        )


def _stubbed(monkeypatch: pytest.MonkeyPatch) -> None:
    chapters = [
        {"ref": 1, "slug": "how-to-read-a-game", "title": "Reading a match", "score": 0.61, "bytes": 9000},
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
    monkeypatch.setattr(deep_read, "get_llm_provider", lambda: _StubProvider())


def test_the_compiled_stategraph_reports_its_nodes(monkeypatch: pytest.MonkeyPatch) -> None:
    _stubbed(monkeypatch)
    if deep_read._StateGraph is None:  # pragma: no cover - the image pins langgraph
        pytest.skip("langgraph is not installed here")
    graph = deep_read._compile_langgraph(None)
    nodes = set(graph.get_graph().nodes)
    assert {"gather", "draft", "verify", "repair"} <= nodes


def test_stategraph_and_fallback_produce_the_same_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    _stubbed(monkeypatch)
    if deep_read._StateGraph is None:  # pragma: no cover
        pytest.skip("langgraph is not installed here")
    stategraph_payload = deep_read.compute_deep_read(None, "how do I read a game as a midfielder")
    monkeypatch.setattr(deep_read, "_StateGraph", None)
    fallback_payload = deep_read.compute_deep_read(None, "how do I read a game as a midfielder")
    assert stategraph_payload["answered"] is fallback_payload["answered"] is True
    assert stategraph_payload["graph_trace"] == fallback_payload["graph_trace"] == [
        "START",
        "gather",
        "draft",
        "verify",
        "repair",
        "END",
    ]
    assert stategraph_payload["provider"] == fallback_payload["provider"] == "stub"
    assert stategraph_payload["verify"]["ok"] is True
