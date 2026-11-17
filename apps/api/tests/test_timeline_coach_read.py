"""The Timeline's coach-read — one honest paragraph on the season's story arc."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.providers import LlmResult
from app.services import timeline_coach

API = "/api/v1"


class _StubProvider:
    name = "stub"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 320, temperature: float = 0.3, prompt_cache_key: str | None = None) -> LlmResult:  # noqa: ARG002
        assert "Champion:" in prompt
        assert "tier-1" in prompt
        return LlmResult(
            text="Ravhurst City led from matchday one, the avalanche arrived on matchday nine, and the ceiling fell short on the very last Sunday.",
            provider="stub",
            model="stub-1",
            demo_mode=False,
            input_tokens=350,
            output_tokens=42,
            cached_input_tokens=340,
            cache_reported=True,
            latency_ms=1,
        )


class _BrokenProvider:
    name = "stub"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 320, temperature: float = 0.3, prompt_cache_key: str | None = None) -> LlmResult:  # noqa: ARG002
        raise RuntimeError("gateway unreachable")


def _stub_season(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        timeline_coach,
        "compute_timeline",
        lambda db: {
            "available": True,
            "season": {"label": "2026/27", "kind": "7:3"},
            "competition": "Premier League",
            "competition_slug": "premier-league",
            "matchdays": 18,
            "rounds": [],
            "chart": [],
            "champion": {"id": "t1", "slug": "ravhurst-city", "name": "Ravhurst City", "path": "/team/ravhurst-city", "points": 45, "played": 18, "won": 14, "drawn": 3, "lost": 1, "goal_difference": 30},
            "beats": {
                "opening": {"available": True, "matchday": 1, "label": "Matchday 1", "fixtures": 10, "goals": 27, "leader": {"id": "t1", "slug": "ravhurst-city", "name": "Ravhurst City", "path": "/team/ravhurst-city"}, "eventual_champion_led": True},
                "avalanche": {"available": True, "matchday": 9, "label": "Matchday 9", "goals": 41, "fixtures": 10},
                "takeover": {"available": True, "matchday": 7, "label": "Matchday 7", "lead_matchdays": 12},
                "settled": {"available": True, "matchday": 17, "label": "Matchday 17", "points": 41, "gap": 12, "decided_on_tiebreak": False},
            },
        },
    )


class TestTimelineCoachRead:
    def test_the_door_answers_with_the_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _stub_season(monkeypatch)
        monkeypatch.setattr(timeline_coach, "get_llm_provider", lambda: _StubProvider())
        from app.services.timeline_coach import compute_timeline_coach_read

        body = compute_timeline_coach_read(db=None)  # type: ignore[arg-type]
        assert body["available"] is True
        assert body["provider"] == "stub"
        assert body["edition"] == "2026/27"
        assert body["input_tokens"] == 350

    def test_an_unreachable_gateway_answers_without_crashing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _stub_season(monkeypatch)
        monkeypatch.setattr(timeline_coach, "get_llm_provider", lambda: _BrokenProvider())
        from app.services.timeline_coach import compute_timeline_coach_read

        body = compute_timeline_coach_read(db=None)  # type: ignore[arg-type]
        assert body["available"] is False
        assert "gateway unreachable" in body["error"]

    def test_a_provider_error_answer_is_also_reported_available_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class _ErrorStub:
            name = "stub"

            def complete(self, *, system: str, prompt: str, max_tokens: int = 320, temperature: float = 0.3, prompt_cache_key: str | None = None) -> LlmResult:  # noqa: ARG002
                return LlmResult(text="", provider="stub", model="stub-1", demo_mode=False, error="rate_limited")

        _stub_season(monkeypatch)
        monkeypatch.setattr(timeline_coach, "get_llm_provider", lambda: _ErrorStub())
        from app.services.timeline_coach import compute_timeline_coach_read

        body = compute_timeline_coach_read(db=None)  # type: ignore[arg-type]
        assert body["available"] is False
        assert body["error"] == "rate_limited"

    def test_the_door_is_public_and_answers(self) -> None:
        client = TestClient(app)
        response = client.get(f"{API}/world/timeline/coach-read")
        assert response.status_code == 200
        body = response.json()
        assert "available" in body
        assert body["edition"] == "2026/27"
