"""The Honours Spine's coach-read — one honest paragraph on the lineage of finals."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.providers import LlmResult
from app.services import honours_coach

API = "/api/v1"


class _StubProvider:
    name = "stub"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 380, temperature: float = 0.3, prompt_cache_key: str | None = None) -> LlmResult:  # noqa: ARG002
        assert "Finals" in prompt
        assert "worldcup" in prompt
        return LlmResult(
            text="Brazil leads the lineage with five worldcup crowns, while the penalties deciders show the finals that never resolve inside ninety-plus extra minutes.",
            provider="stub",
            model="stub-1",
            demo_mode=False,
            input_tokens=610,
            output_tokens=44,
            cached_input_tokens=600,
            cache_reported=True,
            latency_ms=2,
        )


class _BrokenProvider:
    name = "stub"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 380, temperature: float = 0.3, prompt_cache_key: str | None = None) -> LlmResult:  # noqa: ARG002
        raise RuntimeError("gateway unreachable")


def _stub_honours(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        honours_coach,
        "compute_honours",
        lambda: {
            "available": True,
            "source": "openfootball worldcup.json + openfootball euro.json (CC-BY 4.0)",
            "attribution": "CC-BY 4.0",
            "provenance": {"data_origin": "public-real", "is_demo_data": False, "license": "CC-BY 4.0"},
            "entries": [
                {
                    "tournament": "2022",
                    "kind": "worldcup",
                    "title": "2022 FIFA World Cup",
                    "host": "Qatar",
                    "date": "2022-12-18",
                    "venue": "Lusail Iconic Stadium",
                    "champion": "Argentina",
                    "champion_note": None,
                    "runner_up": "France",
                    "score_regular": [2, 2],
                    "score_extra_time": [3, 3],
                    "score_penalties": [4, 2],
                    "has_penalties": True,
                    "went_extra_time": True,
                    "on_field": [3, 3],
                    "goals_scored": 172,
                    "venues": 8,
                    "biggest_win": {"match": "Spain 7-0 Costa Rica", "score": [7, 0], "stage": "Matchday 4", "matchday_date": "2022-11-23", "venue": "Al Thumama Stadium, Doha"},
                    "total_matches": 64,
                }
            ],
            "champion_lines": [
                {"champion": "Brazil", "wins": 5, "years": ["2002", "1994", "1970", "1962", "1958"], "kinds": ["worldcup"]},
                {"champion": "Italy", "wins": 5, "years": ["euro2021", "2006", "1982", "1938", "1934"], "kinds": ["euro", "worldcup"]},
            ],
            "totals": {"entries": 24, "matches": 1066, "goals_on_field": 2979},
        },
    )


class TestHonoursCoachRead:
    def test_the_door_answers_with_the_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _stub_honours(monkeypatch)
        monkeypatch.setattr(honours_coach, "get_llm_provider", lambda: _StubProvider())
        from app.services.honours_coach import compute_honours_coach_read

        body = compute_honours_coach_read()
        assert body["available"] is True
        assert body["provider"] == "stub"
        assert body["edition"] == "2026/27"
        assert body["input_tokens"] == 610

    def test_an_unreachable_gateway_answers_without_crashing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _stub_honours(monkeypatch)
        monkeypatch.setattr(honours_coach, "get_llm_provider", lambda: _BrokenProvider())
        from app.services.honours_coach import compute_honours_coach_read

        body = compute_honours_coach_read()
        assert body["available"] is False
        assert "gateway unreachable" in body["error"]

    def test_a_provider_error_answer_is_also_reported_available_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class _ErrorStub:
            name = "stub"

            def complete(self, *, system: str, prompt: str, max_tokens: int = 380, temperature: float = 0.3, prompt_cache_key: str | None = None) -> LlmResult:  # noqa: ARG002
                return LlmResult(text="", provider="stub", model="stub-1", demo_mode=False, error="rate_limited")

        _stub_honours(monkeypatch)
        monkeypatch.setattr(honours_coach, "get_llm_provider", lambda: _ErrorStub())
        from app.services.honours_coach import compute_honours_coach_read

        body = compute_honours_coach_read()
        assert body["available"] is False
        assert body["error"] == "rate_limited"

    def test_the_door_is_public_and_answers(self) -> None:
        client = TestClient(app)
        response = client.get(f"{API}/world/honours/coach-read")
        assert response.status_code == 200
        body = response.json()
        assert "available" in body
        assert body["edition"] == "2026/27"
