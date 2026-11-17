"""The manual's ask door — a state graph that answers questions about the product itself."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.providers import LlmResult
from app.services import manual_ask

API = "/api/v1"


class _StubProvider:
    name = "stub"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 520, temperature: float = 0.35, prompt_cache_key: str | None = None) -> LlmResult:  # noqa: ARG002
        assert "The dossier" not in prompt  # the manual, deliberately, contains no invented facts beyond THE MANUAL constant
        assert "Q:" in prompt or "The doors tour" in prompt or "Glossary" in prompt
        return LlmResult(
            text="Start with the five-step quickstart: create the account, name the captain, walk the world.",
            provider="stub",
            model="stub-1",
            demo_mode=False,
            input_tokens=2200,
            output_tokens=35,
            cached_input_tokens=2100,
            cache_reported=True,
            latency_ms=1,
        )


class _BrokenProvider:
    name = "stub"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 520, temperature: float = 0.35, prompt_cache_key: str | None = None) -> LlmResult:  # noqa: ARG002
        raise RuntimeError("gateway unreachable")


def _stub_graph(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(manual_ask, "budget_exhausted", lambda db: False)
    monkeypatch.setattr(manual_ask, "record_model_call_safely", lambda *, result, feature, user_id=None: True)


class TestManualAsk:
    def test_the_door_answers_with_everything_the_panel_prints(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _stub_graph(monkeypatch)
        monkeypatch.setattr(manual_ask, "get_llm_provider", lambda: _StubProvider())
        body = manual_ask.compute_manual_ask(None, question="Where do I start if I am new here?", locale="en")
        assert body["available"] is True
        assert body["provider"] == "stub"
        assert body["intent"] == "getting_started"
        assert "quickstart" in body["answer"].lower()
        assert body["cached_input_tokens"] == 2100
        assert body["graph_trace"] == ["START", "classify_intent", "retrieve_sections", "spend_gate", "phrase_answer", "END"]

    def test_the_tour_question_routes_to_the_tour_intent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _stub_graph(monkeypatch)
        monkeypatch.setattr(manual_ask, "get_llm_provider", lambda: _StubProvider())
        body = manual_ask.compute_manual_ask(None, question="What doors can I explore in the world?", locale="en")
        assert body["available"] is True
        assert body["intent"] == "tour"

    def test_an_unreachable_gateway_answers_without_crashing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _stub_graph(monkeypatch)
        monkeypatch.setattr(manual_ask, "get_llm_provider", lambda: _BrokenProvider())
        body = manual_ask.compute_manual_ask(None, question="How do the doors fit together?", locale="en")
        assert body["available"] is False
        assert "gateway unreachable" in body["error"]

    def test_the_budget_gate_spends_nothing_and_says_so(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(manual_ask, "budget_exhausted", lambda db: True)
        monkeypatch.setattr(manual_ask, "record_model_call_safely", lambda *, result, feature, user_id=None: True)
        body = manual_ask.compute_manual_ask(None, question="Where do I start if I am a total beginner?", locale="en")
        assert body["available"] is False
        assert body["demo_mode"] is True
        assert "budget cap" in body["answer"].lower() or "daily" in body["answer"].lower()
        assert body["graph_trace"][-1] == "END"
        assert body["provider"] == "rule-engine-demo"

    def test_the_door_is_public_and_answers(self) -> None:
        client = TestClient(app)
        response = client.post(f"{API}/manual/ask", json={"question": "What is a streak in this world?", "locale": "en"})
        assert response.status_code == 200
        body = response.json()
        assert "available" in body
        assert body["graph_trace"][0] == "START"
        assert body["intent"] in ("glossary", "general", "faq", "rules")
