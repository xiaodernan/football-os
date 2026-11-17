"""The Spotlight's coach-read — one honest paragraph on the three recognitions the world cannot hide from."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.providers import LlmResult
from app.services import spotlight_coach

API = "/api/v1"


class _StubProvider:
    name = "stub"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 320, temperature: float = 0.3) -> LlmResult:  # noqa: ARG002
        assert "hitman" in prompt
        assert "fortress" in prompt
        return LlmResult(
            text="The hitman's harvest stands on the sample behind it, the fortress owes it to its clean sheets at home, and the new blood has already put minutes on the books.",
            provider="stub",
            model="stub-1",
            demo_mode=False,
            input_tokens=330,
            output_tokens=40,
            cached_input_tokens=310,
            cache_reported=True,
            latency_ms=1,
        )


class _BrokenProvider:
    name = "stub"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 320, temperature: float = 0.3) -> LlmResult:  # noqa: ARG002
        raise RuntimeError("gateway unreachable")


def _stub_spotlight(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        spotlight_coach,
        "compute_spotlight",
        lambda db: {
            "season": {"label": "2026/27", "kind": "7:3"},
            "spotlights": [
                {
                    "key": "hitman",
                    "available": True,
                    "player": {"id": "p1", "slug": "kendrin-maso", "name": "Kendrin Maso", "position": "ST", "overall": 84, "age": 27, "nation": "England", "path": "/player/kendrin-maso", "stat": 1.4, "stat_label": "1.40", "data_origin": "synthetic", "is_demo_data": True},
                    "per_90": 1.4,
                    "goals": 21,
                    "minutes": 1350,
                    "competition": {"id": "c1", "slug": "premier-league", "name": "Premier League"},
                },
                {
                    "key": "fortress",
                    "available": True,
                    "team": {"id": "t1", "slug": "ravhurst-city", "name": "Ravhurst City", "path": "/team/ravhurst-city"},
                    "clean_sheets": 9,
                    "played": 14,
                    "conceded": 3,
                    "competition": None,
                },
                {
                    "key": "new_blood",
                    "available": True,
                    "player": {"id": "p2", "slug": "tiro-chevel", "name": "Tiro Chevel", "position": "CM", "overall": 71, "age": 18, "nation": "France", "path": "/player/tiro-chevel", "stat": 900.0, "stat_label": None, "data_origin": "synthetic", "is_demo_data": True},
                    "age": 18,
                    "minutes": 900,
                    "position": "CM",
                    "competition": {"id": "c1", "slug": "premier-league", "name": "Premier League"},
                },
            ],
        },
    )


class TestSpotlightCoachRead:
    def test_the_door_answers_with_the_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _stub_spotlight(monkeypatch)
        monkeypatch.setattr(spotlight_coach, "get_llm_provider", lambda: _StubProvider())
        from app.services.spotlight_coach import compute_spotlight_coach_read

        body = compute_spotlight_coach_read(db=None)  # type: ignore[arg-type]
        assert body["available"] is True
        assert body["provider"] == "stub"
        assert body["edition"] == "2026/27"
        assert body["input_tokens"] == 330

    def test_an_unreachable_gateway_answers_without_crashing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _stub_spotlight(monkeypatch)
        monkeypatch.setattr(spotlight_coach, "get_llm_provider", lambda: _BrokenProvider())
        from app.services.spotlight_coach import compute_spotlight_coach_read

        body = compute_spotlight_coach_read(db=None)  # type: ignore[arg-type]
        assert body["available"] is False
        assert "gateway unreachable" in body["error"]

    def test_a_provider_error_answer_is_also_reported_available_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class _ErrorStub:
            name = "stub"

            def complete(self, *, system: str, prompt: str, max_tokens: int = 320, temperature: float = 0.3) -> LlmResult:  # noqa: ARG002
                return LlmResult(text="", provider="stub", model="stub-1", demo_mode=False, error="rate_limited")

        _stub_spotlight(monkeypatch)
        monkeypatch.setattr(spotlight_coach, "get_llm_provider", lambda: _ErrorStub())
        from app.services.spotlight_coach import compute_spotlight_coach_read

        body = compute_spotlight_coach_read(db=None)  # type: ignore[arg-type]
        assert body["available"] is False
        assert body["error"] == "rate_limited"

    def test_the_door_is_public_and_answers(self) -> None:
        client = TestClient(app)
        response = client.get(f"{API}/world/spotlight/coach-read")
        assert response.status_code == 200
        body = response.json()
        assert "available" in body
        assert body["edition"] == "2026/27"
