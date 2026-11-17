"""The Gazette's coach-read — one honest paragraph on the latest edition's printing."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.providers import LlmResult
from app.services import gazette_coach

API = "/api/v1"


class _StubProvider:
    name = "stub"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 320, temperature: float = 0.3, prompt_cache_key: str | None = None) -> LlmResult:  # noqa: ARG002
        assert "edition" in prompt
        assert "tier-1" in prompt
        return LlmResult(
            text="The paper says it plainly: the edition brought louder football than the season's average, with the table shifting at the top.",
            provider="stub",
            model="stub-1",
            demo_mode=False,
            input_tokens=370,
            output_tokens=38,
            cached_input_tokens=350,
            cache_reported=True,
            latency_ms=1,
        )


class _BrokenProvider:
    name = "stub"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 320, temperature: float = 0.3, prompt_cache_key: str | None = None) -> LlmResult:  # noqa: ARG002
        raise RuntimeError("gateway unreachable")


def _stub_edition(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        gazette_coach,
        "compute_gazette",
        lambda db: {
            "available": True,
            "season": {"label": "2026/27", "kind": "7:3"},
            "edition": 14,
            "total_editions": 14,
            "published_at": "2026-11-08T20:45:00+00:00",
            "competition": {"name": "Lyndera Superleague", "slug": "lyndera-superleague", "path": "/competition/lyndera-superleague"},
            "scorecard": [
                {
                    "id": "m1", "slug": "fd-1", "path": "/match/fd-1", "kickoff": "2026-11-08T20:45:00+00:00", "venue": "Wyrford Field", "city": "Wyrford",
                    "home": {"id": "t1", "slug": "east-bloc", "name": "East Bloc"}, "away": {"id": "t2", "slug": "wyn-crofter", "name": "Wyn Crofter"},
                    "home_goals": 3, "away_goals": 2, "score": "3-2",
                }
            ],
            "table_after": [{"team_id": "t1", "points": 30, "played": 14, "name": "East Bloc"}],
            "table_leader": {"id": "t1", "slug": "east-bloc", "name": "East Bloc", "path": "/team/east-bloc"},
            "table_gap": 2,
            "lead": {
                "id": "m1", "slug": "fd-1", "path": "/match/fd-1", "kickoff": "2026-11-08T20:45:00+00:00", "venue": "Wyrford Field", "city": "Wyrford",
                "home": {"id": "t1", "slug": "east-bloc", "name": "East Bloc"}, "away": {"id": "t2", "slug": "wyn-crofter", "name": "Wyn Crofter"},
                "home_goals": 3, "away_goals": 2, "score": "3-2",
            },
            "hot_hand": {"team": {"slug": "east-bloc", "name": "East Bloc", "path": "/team/east-bloc", "id": "t1"}, "goals": 3},
            "number": {"goals_this_round": 17, "draws": 1, "clean_sheets": 1, "season_average_goals": 2.1, "fixtures": 9},
            "archive": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14],
        },
    )


class TestGazetteCoachRead:
    def test_the_door_answers_with_the_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _stub_edition(monkeypatch)
        monkeypatch.setattr(gazette_coach, "get_llm_provider", lambda: _StubProvider())
        from app.services.gazette_coach import compute_gazette_coach_read

        body = compute_gazette_coach_read(db=None)  # type: ignore[arg-type]
        assert body["available"] is True
        assert body["provider"] == "stub"
        assert body["edition"] == "2026/27"
        assert body["input_tokens"] == 370

    def test_an_unreachable_gateway_answers_without_crashing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _stub_edition(monkeypatch)
        monkeypatch.setattr(gazette_coach, "get_llm_provider", lambda: _BrokenProvider())
        from app.services.gazette_coach import compute_gazette_coach_read

        body = compute_gazette_coach_read(db=None)  # type: ignore[arg-type]
        assert body["available"] is False
        assert "gateway unreachable" in body["error"]

    def test_a_provider_error_answer_is_also_reported_available_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class _ErrorStub:
            name = "stub"

            def complete(self, *, system: str, prompt: str, max_tokens: int = 320, temperature: float = 0.3, prompt_cache_key: str | None = None) -> LlmResult:  # noqa: ARG002
                return LlmResult(text="", provider="stub", model="stub-1", demo_mode=False, error="rate_limited")

        _stub_edition(monkeypatch)
        monkeypatch.setattr(gazette_coach, "get_llm_provider", lambda: _ErrorStub())
        from app.services.gazette_coach import compute_gazette_coach_read

        body = compute_gazette_coach_read(db=None)  # type: ignore[arg-type]
        assert body["available"] is False
        assert body["error"] == "rate_limited"

    def test_the_door_is_public_and_answers(self) -> None:
        client = TestClient(app)
        response = client.get(f"{API}/world/gazette/coach-read")
        assert response.status_code == 200
        body = response.json()
        assert "available" in body
        assert body["edition"] == "2026/27"
