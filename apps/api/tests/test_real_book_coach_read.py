"""The Real Book's coach-read — one honest press on whichever edition the reader has open."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.providers import LlmResult
from app.services import real_book_coach

API = "/api/v1"


class _StubProvider:
    name = "stub"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 360, temperature: float = 0.3, prompt_cache_key: str | None = None) -> LlmResult:  # noqa: ARG002
        assert "edition" in prompt.lower()
        assert "snapshot" in prompt.lower()
        return LlmResult(
            text="Uruguay in 1950 at Maracanã - the silentest stadium ever to fall silent. Rome 1934 - the first chapter, already with everything a World Cup needs. 1962 - Garrincha in Santiago, Pelé out by injury, Brazil just the same.",
            provider="stub",
            model="stub-1",
            demo_mode=False,
            input_tokens=88,
            output_tokens=24,
            cached_input_tokens=0,
            cache_reported=False,
            latency_ms=1,
        )


class _BrokenProvider:
    name = "stub"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 360, temperature: float = 0.3, prompt_cache_key: str | None = None) -> LlmResult:  # noqa: ARG002
        raise RuntimeError("gateway unreachable")


class TestRealBookCoachRead:
    def test_the_door_answers_with_the_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(real_book_coach, "get_llm_provider", lambda: _StubProvider())
        from app.services.real_book_coach import compute_real_book_coach_read

        body = compute_real_book_coach_read("1950")
        assert body["available"] is True
        assert body["provider"] == "stub"
        assert body["edition"] == "1950 FIFA World Cup — the Maracanazo"
        assert body["input_tokens"] == 88

    def test_an_unreachable_gateway_answers_without_crashing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(real_book_coach, "get_llm_provider", lambda: _BrokenProvider())
        from app.services.real_book_coach import compute_real_book_coach_read

        body = compute_real_book_coach_read("1930")
        assert body["available"] is False
        assert "gateway unreachable" in body["error"]

    def test_a_provider_error_answer_is_also_reported_available_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class _ErrorStub:
            name = "stub"

            def complete(self, *, system: str, prompt: str, max_tokens: int = 360, temperature: float = 0.3, prompt_cache_key: str | None = None) -> LlmResult:  # noqa: ARG002
                return LlmResult(text="", provider="stub", model="stub-1", demo_mode=False, error="rate_limited")

        monkeypatch.setattr(real_book_coach, "get_llm_provider", lambda: _ErrorStub())
        from app.services.real_book_coach import compute_real_book_coach_read

        body = compute_real_book_coach_read("1966")
        assert body["available"] is False

    def test_the_door_is_public_and_answers(self) -> None:
        client = TestClient(app)
        response = client.get(f"{API}/world/real-book/coach-read", params={"tournament": "2022"})
        assert response.status_code == 200
        body = response.json()
        assert "available" in body
        assert body["edition"] == "2022 FIFA World Cup"
