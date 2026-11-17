"""The almanac's coach-read — one honest press, every press grounded in the almanac's own figures."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from starlette.testclient import TestClient

from app.core.db import SessionLocal
from app.main import app
from app.providers import LlmResult
from app.services import almanac_coach
from app.services.world import sync_world

API = "/api/v1"


@pytest.fixture()
def session() -> Iterator:  # type: ignore[no-untyped-def]
    with SessionLocal() as db:
        sync_world(db)
        yield db


class _StubProvider:
    name = "stub"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 420, temperature: float = 0.4, prompt_cache_key: str | None = None) -> LlmResult:  # noqa: ARG002
        assert "the golden boot" in system.lower() or "nothing invented" in system.lower() or "in three" in system.lower()
        assert "Snapshot" in prompt or "snapshot" in prompt
        return LlmResult(
            text="A golden boot era. A title race with only one name on the plaque. A reader who came once will come back.",
            provider="stub",
            model="stub-1",
            demo_mode=False,
            input_tokens=77,
            output_tokens=21,
            cached_input_tokens=0,
            cache_reported=False,
            latency_ms=1,
        )


class _BrokenProvider:
    name = "stub"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 420, temperature: float = 0.4, prompt_cache_key: str | None = None) -> LlmResult:  # noqa: ARG002
        raise RuntimeError("gateway unreachable")


class TestAlmanacCoachRead:
    def test_the_door_answers_with_the_provider(self, session, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setattr(almanac_coach, "get_llm_provider", lambda: _StubProvider())
        from app.services.almanac_coach import compute_almanac_coach_read

        body = compute_almanac_coach_read(session)
        assert body["available"] is True
        assert body["provider"] == "stub"
        assert body["model"] == "stub-1"
        assert body["input_tokens"] == 77
        assert body["edition"] == "2026/27"

    def test_an_unreachable_gateway_answers_without_crashing(self, session, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setattr(almanac_coach, "get_llm_provider", lambda: _BrokenProvider())
        from app.services.almanac_coach import compute_almanac_coach_read

        body = compute_almanac_coach_read(session)
        assert body["available"] is False
        assert "gateway unreachable" in body["error"]

    def test_a_provider_error_answer_is_also_reported_available_false(self, session, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
        class _ErrorStub:
            name = "stub"

            def complete(self, *, system: str, prompt: str, max_tokens: int = 420, temperature: float = 0.4, prompt_cache_key: str | None = None) -> LlmResult:  # noqa: ARG002
                return LlmResult(text="", provider="stub", model="stub-1", demo_mode=False, error="rate_limited")

        monkeypatch.setattr(almanac_coach, "get_llm_provider", lambda: _ErrorStub())
        from app.services.almanac_coach import compute_almanac_coach_read

        body = compute_almanac_coach_read(session)
        assert body["available"] is False

    def test_the_door_is_public_and_rate_limited_says_so(self) -> None:
        client = TestClient(app)
        response = client.get(f"{API}/world/almanac/coach-read")
        assert response.status_code == 200
        body = response.json()
        assert "available" in body
        assert body["edition"] == "2026/27"
