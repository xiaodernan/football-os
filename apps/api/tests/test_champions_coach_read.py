"""The Champions' coach-read — one honest paragraph on the three World Cups the product carries."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.providers import LlmResult
from app.services import champions_coach

API = "/api/v1"


class _StubProvider:
    name = "stub"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 320, temperature: float = 0.3, prompt_cache_key: str | None = None) -> LlmResult:  # noqa: ARG002
        assert "2014" in prompt
        assert "scorer" in prompt.lower() or "scorers" in prompt.lower()
        return LlmResult(
            text="Three cups three champions: Germany in 2014 past Argentina, France in 2018 past Croatia, Argentina in 2022 past France on penalties.",
            provider="stub",
            model="stub-1",
            demo_mode=False,
            input_tokens=430,
            output_tokens=40,
            cached_input_tokens=420,
            cache_reported=True,
            latency_ms=1,
        )


class _BrokenProvider:
    name = "stub"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 320, temperature: float = 0.3, prompt_cache_key: str | None = None) -> LlmResult:  # noqa: ARG002
        raise RuntimeError("gateway unreachable")


def _stub_champions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        champions_coach,
        "compute_champions",
        lambda: {
            "available": True,
            "source": "openfootball worldcup.json (CC-BY 4.0)",
            "attribution": "CC-BY 4.0",
            "provenance": {"data_origin": "public-real", "is_demo_data": False, "license": "CC-BY 4.0"},
            "entries": [
                {
                    "tournament": "2014", "title": "2014 FIFA World Cup", "host": "Brazil", "venues": 12, "total_matches": 64,
                    "goals_scored": 171, "goals_per_match": 2.67, "has_penalties": False,
                    "champion": "Germany", "runner_up": "Argentina", "golden_ball": {"name": "Lionel Messi", "note": "won the golden ball of the final"},
                    "final": {"score_regular": [0, 0], "score_extra_time": [1, 0], "score_penalties": [0, 0]},
                    "final_row": {"date": "2014-07-13", "team1": "Germany", "team2": "Argentina", "on_field": [1, 0], "et": [1, 0], "penalties": [0, 0], "ht": [0, 0]},
                    "biggest_win": {"match": "Brazil 1-7 Germany", "score": [1, 7], "stage": "Semi-finals"},
                    "top_scorers": [{"name": "Lionel Messi", "goals": 4, "club": "Barcelona"}],
                    "top_scorers_note": None, "has_scorers": True,
                },
                {
                    "tournament": "2022", "title": "2022 FIFA World Cup", "host": "Qatar", "venues": 8, "total_matches": 64,
                    "goals_scored": 172, "goals_per_match": 2.69, "has_penalties": True,
                    "champion": "Argentina", "runner_up": "France", "golden_ball": {"name": "Lionel Messi", "note": "won the golden ball of the final"},
                    "final": {"score_regular": [2, 2], "score_extra_time": [3, 3], "score_penalties": [4, 2]},
                    "final_row": {"date": "2022-12-18", "team1": "Argentina", "team2": "France", "on_field": [3, 3], "et": [3, 3], "penalties": [4, 2], "ht": [2, 0]},
                    "biggest_win": {"match": "Spain 7-0 Costa Rica", "score": [7, 0], "stage": "Matchday 4"},
                    "top_scorers": [{"name": "Lionel Messi", "goals": 7, "club": "Paris Saint-Germain"}],
                    "top_scorers_note": "2022 edition: Messi and Mbappé joint top scorers at 7 (Mbappé's count merged to one name).", "has_scorers": True,
                },
                {
                    "tournament": "2018", "title": "2018 FIFA World Cup", "host": "Russia", "venues": 12, "total_matches": 64,
                    "goals_scored": 169, "goals_per_match": 2.64, "has_penalties": False,
                    "champion": "France", "runner_up": "Croatia", "golden_ball": {"name": "Luka Modric", "note": "won the golden ball, Croatia lost the final"},
                    "final": {"score_regular": [4, 2], "score_extra_time": [4, 2], "score_penalties": [0, 0]},
                    "final_row": {"date": "2018-07-15", "team1": "France", "team2": "Croatia", "on_field": [4, 2], "et": None, "penalties": None, "ht": [2, 1]},
                    "biggest_win": {"match": "Russia 5-0 Saudi Arabia", "score": [5, 0], "stage": "Matchday 1"},
                    "top_scorers": [{"name": "Harry Kane", "goals": 6, "club": "Tottenham Hotspur"}],
                    "top_scorers_note": None, "has_scorers": True,
                },
            ],
            "merged_scorers": [
                {"name": "Lionel Messi", "goals_2014": 4, "goals_2018": 1, "goals_2022": 7, "total": 12},
                {"name": "Harry Kane", "goals_2014": 0, "goals_2018": 6, "goals_2022": 3, "total": 9},
            ],
            "joint_top_scorers_note": "2022 edition: Messi and Mbappé joint top scorers at 7 (Mbappé's count merged to one name).",
        },
    )


class TestChampionsCoachRead:
    def test_the_door_answers_with_the_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _stub_champions(monkeypatch)
        monkeypatch.setattr(champions_coach, "get_llm_provider", lambda: _StubProvider())
        from app.services.champions_coach import compute_champions_coach_read

        body = compute_champions_coach_read()
        assert body["available"] is True
        assert body["provider"] == "stub"
        assert body["edition"] == "2026/27"
        assert body["input_tokens"] == 430

    def test_an_unreachable_gateway_answers_without_crashing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _stub_champions(monkeypatch)
        monkeypatch.setattr(champions_coach, "get_llm_provider", lambda: _BrokenProvider())
        from app.services.champions_coach import compute_champions_coach_read

        body = compute_champions_coach_read()
        assert body["available"] is False
        assert "gateway unreachable" in body["error"]

    def test_a_provider_error_answer_is_also_reported_available_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class _ErrorStub:
            name = "stub"

            def complete(self, *, system: str, prompt: str, max_tokens: int = 320, temperature: float = 0.3, prompt_cache_key: str | None = None) -> LlmResult:  # noqa: ARG002
                return LlmResult(text="", provider="stub", model="stub-1", demo_mode=False, error="rate_limited")

        _stub_champions(monkeypatch)
        monkeypatch.setattr(champions_coach, "get_llm_provider", lambda: _ErrorStub())
        from app.services.champions_coach import compute_champions_coach_read

        body = compute_champions_coach_read()
        assert body["available"] is False
        assert body["error"] == "rate_limited"

    def test_the_door_is_public_and_answers(self) -> None:
        client = TestClient(app)
        response = client.get(f"{API}/world/champions/coach-read")
        assert response.status_code == 200
        body = response.json()
        assert "available" in body
        assert body["edition"] == "2026/27"
