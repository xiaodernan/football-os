"""The Noise Dossier's coach-read — one honest paragraph on the caller the seed defeats."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.providers import LlmResult
from app.services import noise_coach

API = "/api/v1"


class _StubProvider:
    name = "stub"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 320, temperature: float = 0.3) -> LlmResult:  # noqa: ARG002
        assert "Accuracy" in prompt
        assert "tier-1" in prompt
        return LlmResult(
            text="The caller rose 4% above the chance line, but the seed kept the last laugh in the five largest gaps it misread.",
            provider="stub",
            model="stub-1",
            demo_mode=False,
            input_tokens=240,
            output_tokens=40,
            cached_input_tokens=220,
            cache_reported=True,
            latency_ms=1,
        )


class _BrokenProvider:
    name = "stub"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 320, temperature: float = 0.3) -> LlmResult:  # noqa: ARG002
        raise RuntimeError("gateway unreachable")


def _stub_dossier(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        noise_coach,
        "compute_noise",
        lambda db: {
            "available": True,
            "season": {"label": "2026/27", "kind": "7:3"},
            "competition": "Premier League",
            "competition_slug": "premier-league",
            "judged": 56,
            "correct": 22,
            "wrong": 34,
            "accuracy_pct": 39.29,
            "chance_pct": 33.33,
            "draw_window": 4.0,
            "draw_calls": 12,
            "draw_hits": 3,
            "draw_hit_pct": 25.0,
            "best_streak": 5,
            "upsets": [
                {
                    "slug": "fd-88",
                    "path": "/match/fd-88",
                    "kickoff_at": "2026-10-19T16:00:00Z",
                    "home": {"id": "t1", "slug": "ravhurst-city", "name": "Ravhurst City"},
                    "away": {"id": "t2", "slug": "lowmore-athletic", "name": "Lowmore Athletic"},
                    "home_goals": 1,
                    "away_goals": 2,
                    "called": "home",
                    "actual": "away",
                    "hit": False,
                    "rating_gap": 11.2,
                }
            ],
        },
    )


class TestNoiseCoachRead:
    def test_the_door_answers_with_the_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _stub_dossier(monkeypatch)
        monkeypatch.setattr(noise_coach, "get_llm_provider", lambda: _StubProvider())
        from app.services.noise_coach import compute_noise_coach_read

        body = compute_noise_coach_read(db=None)  # type: ignore[arg-type]
        assert body["available"] is True
        assert body["provider"] == "stub"
        assert body["edition"] == "2026/27"
        assert body["input_tokens"] == 240

    def test_an_unreachable_gateway_answers_without_crashing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _stub_dossier(monkeypatch)
        monkeypatch.setattr(noise_coach, "get_llm_provider", lambda: _BrokenProvider())
        from app.services.noise_coach import compute_noise_coach_read

        body = compute_noise_coach_read(db=None)  # type: ignore[arg-type]
        assert body["available"] is False
        assert "gateway unreachable" in body["error"]

    def test_a_provider_error_answer_is_also_reported_available_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class _ErrorStub:
            name = "stub"

            def complete(self, *, system: str, prompt: str, max_tokens: int = 320, temperature: float = 0.3) -> LlmResult:  # noqa: ARG002
                return LlmResult(text="", provider="stub", model="stub-1", demo_mode=False, error="rate_limited")

        _stub_dossier(monkeypatch)
        monkeypatch.setattr(noise_coach, "get_llm_provider", lambda: _ErrorStub())
        from app.services.noise_coach import compute_noise_coach_read

        body = compute_noise_coach_read(db=None)  # type: ignore[arg-type]
        assert body["available"] is False
        assert body["error"] == "rate_limited"

    def test_the_door_is_public_and_answers(self) -> None:
        client = TestClient(app)
        response = client.get(f"{API}/world/noise/coach-read")
        assert response.status_code == 200
        body = response.json()
        assert "available" in body
        assert body["edition"] == "2026/27"
