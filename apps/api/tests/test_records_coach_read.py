"""The Record Book's coach-read — one honest paragraph spoken from the eight computed marks."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.providers import LlmResult
from app.services import records_coach

API = "/api/v1"


class _StubProvider:
    name = "stub"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 360, temperature: float = 0.3, prompt_cache_key: str | None = None) -> LlmResult:  # noqa: ARG002
        assert "biggest_haul" in prompt
        return LlmResult(
            text="The world's biggest haul landed on the same night the goal-fest arrived, and the fortress held the cards fixture at bay.",
            provider="stub",
            model="stub-1",
            demo_mode=False,
            input_tokens=210,
            output_tokens=41,
            cached_input_tokens=190,
            cache_reported=True,
            latency_ms=1,
        )


class _BrokenProvider:
    name = "stub"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 360, temperature: float = 0.3, prompt_cache_key: str | None = None) -> LlmResult:  # noqa: ARG002
        raise RuntimeError("gateway unreachable")


def _stub_records(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        records_coach,
        "compute_records",
        lambda db: {
            "season": {"label": "2026/27", "kind": "7:3"},
            "records": [
                {"key": "biggest_haul", "available": True,
                 "player": {"name": "Suriel Vecchio", "team": {"name": "Ravhurst City"}},
                 "goals": 4, "rating": 9.1, "assists": 2,
                 "match": {"home": {"name": "Ravhurst City"}, "away": {"name": "Harlow"}, "home_goals": 5, "away_goals": 1}},
                {"key": "goal_fest", "available": True, "goals": 9,
                 "match": {"home": {"name": "Ravhurst City"}, "away": {"name": "Harlow"}, "home_goals": 5, "away_goals": 4}},
                {"key": "offence_club", "available": True,
                 "team": {"name": "Ravhurst City"}, "goals_for": 38, "competition": "Premier League", "competition_slug": "premier-league"},
                {"key": "defence_club", "available": True,
                 "team": {"name": "Lyndera Albion"}, "goals_against": 11, "played": 12, "competition": "Premier League", "competition_slug": "premier-league"},
                {"key": "castle", "available": True,
                 "team": {"name": "Lyndera Albion"}, "clean_sheets": 6, "competition": "Premier League", "competition_slug": "premier-league"},
                {"key": "cards_fixture", "available": True, "weighted_cards": 17,
                 "match": {"home": {"name": "Ostmoor Albion"}, "away": {"name": "Quernmoor Town"}}},
                {"key": "keeper_wall", "available": True,
                 "player": {"name": "Deleon Marsh"}, "saves": 14, "rating": 8.4,
                 "match": {"home": {"name": "Lyndera Albion"}, "away": {"name": "Ravhurst City"}, "home_goals": 0, "away_goals": 0}},
                {"key": "highest_rated", "available": True,
                 "player": {"name": "Suriel Vecchio"}, "rating": 9.4, "minutes": 90, "goals": 3, "assists": 1},
            ],
        },
    )


class TestRecordsCoachRead:
    def test_the_door_answers_with_the_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _stub_records(monkeypatch)
        monkeypatch.setattr(records_coach, "get_llm_provider", lambda: _StubProvider())
        from app.services.records_coach import compute_records_coach_read

        body = compute_records_coach_read(db=None)  # type: ignore[arg-type]
        assert body["available"] is True
        assert body["provider"] == "stub"
        assert body["edition"] == "2026/27"
        assert body["input_tokens"] == 210

    def test_an_unreachable_gateway_answers_without_crashing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _stub_records(monkeypatch)
        monkeypatch.setattr(records_coach, "get_llm_provider", lambda: _BrokenProvider())
        from app.services.records_coach import compute_records_coach_read

        body = compute_records_coach_read(db=None)  # type: ignore[arg-type]
        assert body["available"] is False
        assert "gateway unreachable" in body["error"]

    def test_a_provider_error_answer_is_also_reported_available_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class _ErrorStub:
            name = "stub"

            def complete(self, *, system: str, prompt: str, max_tokens: int = 360, temperature: float = 0.3, prompt_cache_key: str | None = None) -> LlmResult:  # noqa: ARG002
                return LlmResult(text="", provider="stub", model="stub-1", demo_mode=False, error="rate_limited")

        _stub_records(monkeypatch)
        monkeypatch.setattr(records_coach, "get_llm_provider", lambda: _ErrorStub())
        from app.services.records_coach import compute_records_coach_read

        body = compute_records_coach_read(db=None)  # type: ignore[arg-type]
        assert body["available"] is False
        assert body["error"] == "rate_limited"

    def test_the_door_is_public_and_answers(self) -> None:
        client = TestClient(app)
        response = client.get(f"{API}/world/records/coach-read")
        assert response.status_code == 200
        body = response.json()
        assert "available" in body
        assert body["edition"] == "2026/27"
