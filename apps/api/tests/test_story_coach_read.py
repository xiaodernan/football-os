"""The Story's coach-read — one honest paragraph from the three computed chapters."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.providers import LlmResult
from app.services import story_coach

API = "/api/v1"


class _StubProvider:
    name = "stub"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 360, temperature: float = 0.3) -> LlmResult:  # noqa: ARG002
        assert "Season 2026/27" in prompt
        assert "Chapter I" in prompt
        assert "Chapter II" in prompt
        assert "Chapter III" in prompt
        return LlmResult(
            text="The season splits clean: the table's leader pulled clear of the chaser on points, and the avalanche fell at home before a full house.",
            provider="stub",
            model="stub-1",
            demo_mode=False,
            input_tokens=120,
            output_tokens=31,
            cached_input_tokens=0,
            cache_reported=False,
            latency_ms=1,
        )


class _BrokenProvider:
    name = "stub"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 360, temperature: float = 0.3) -> LlmResult:  # noqa: ARG002
        raise RuntimeError("gateway unreachable")


def _stub_story(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        story_coach,
        "compute_story",
        lambda db: {
            "season": {"label": "2026/27", "kind": "7:3"},
            "chapters": [
                {"key": "title_race", "available": True, "competition": "Premier League", "competition_slug": "premier-league",
                 "champion": {"name": "Ravhurst City", "points": 31, "won": 10, "drawn": 1, "lost": 1, "played": 12, "goals_for": 30, "goals_against": 11, "goal_difference": 19},
                 "runner_up": {"name": "Lyndera Albion", "points": 27, "won": 9, "drawn": 0, "lost": 2, "played": 11, "goals_for": 27, "goals_against": 13, "goal_difference": 14},
                 "margin": 4, "gd_margin": 5},
                {"key": "avalanche", "available": True, "competition": "Premier League", "competition_slug": "premier-league",
                 "round_label": "Matchday 5", "kickoff_at": "2026-09-20T14:00:00Z", "venue_name": "Stormont Park", "venue_city": "Ravhurst",
                 "home": {"name": "Ravhurst City", "goals": 6}, "away": {"name": "Harlow", "goals": 1}, "winner_name": "Ravhurst City",
                 "winner_path": "/team/ravhurst-city", "margin": 5, "match_path": "/match/md05"},
                {"key": "unbeaten_run", "available": True, "competition": "Premier League", "competition_slug": "premier-league",
                 "team": {"name": "Lyndera Albion"}, "run": 9, "alive": True},
            ],
        },
    )


class TestStoryCoachRead:
    def test_the_door_answers_with_the_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _stub_story(monkeypatch)
        monkeypatch.setattr(story_coach, "get_llm_provider", lambda: _StubProvider())
        from app.services.story_coach import compute_story_coach_read

        body = compute_story_coach_read(db=None)  # type: ignore[arg-type]
        assert body["available"] is True
        assert body["provider"] == "stub"
        assert body["edition"] == "2026/27"
        assert body["input_tokens"] == 120

    def test_an_unreachable_gateway_answers_without_crashing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _stub_story(monkeypatch)
        monkeypatch.setattr(story_coach, "get_llm_provider", lambda: _BrokenProvider())
        from app.services.story_coach import compute_story_coach_read

        body = compute_story_coach_read(db=None)  # type: ignore[arg-type]
        assert body["available"] is False
        assert "gateway unreachable" in body["error"]

    def test_a_provider_error_answer_is_also_reported_available_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class _ErrorStub:
            name = "stub"

            def complete(self, *, system: str, prompt: str, max_tokens: int = 360, temperature: float = 0.3) -> LlmResult:  # noqa: ARG002
                return LlmResult(text="", provider="stub", model="stub-1", demo_mode=False, error="rate_limited")

        _stub_story(monkeypatch)
        monkeypatch.setattr(story_coach, "get_llm_provider", lambda: _ErrorStub())
        from app.services.story_coach import compute_story_coach_read

        body = compute_story_coach_read(db=None)  # type: ignore[arg-type]
        assert body["available"] is False
        assert body["error"] == "rate_limited"

    def test_the_door_is_public_and_answers(self) -> None:
        client = TestClient(app)
        response = client.get(f"{API}/world/story/coach-read")
        assert response.status_code == 200
        body = response.json()
        assert "available" in body
        assert body["edition"] == "2026/27"
