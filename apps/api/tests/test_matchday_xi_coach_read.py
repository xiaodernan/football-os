"""The Matchday XI's coach-read — one honest paragraph on the eleven the world would send."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.providers import LlmResult
from app.services import matchday_xi_coach

API = "/api/v1"


class _StubProvider:
    name = "stub"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 360, temperature: float = 0.3) -> LlmResult:  # noqa: ARG002
        assert "XI" in prompt
        assert "Formation" in prompt
        return LlmResult(
            text="Ravhurst's 4-3-3 starts at the back behind a captain the world gave the most minutes, and it runs through him.",
            provider="stub",
            model="stub-1",
            demo_mode=False,
            input_tokens=180,
            output_tokens=38,
            cached_input_tokens=160,
            cache_reported=True,
            latency_ms=1,
        )


class _BrokenProvider:
    name = "stub"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 360, temperature: float = 0.3) -> LlmResult:  # noqa: ARG002
        raise RuntimeError("gateway unreachable")


def _stub_xi(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        matchday_xi_coach,
        "compute_matchday_xi",
        lambda db: {
            "available": True,
            "season": "2026/27",
            "competition": {"id": "cmp_1", "slug": "premier-league", "name": "Premier League", "tier": 1},
            "formation": "4-3-3",
            "slots": [
                {"number": 1, "position": "GK", "id": "p1", "slug": "gk-arlow", "name": "Arlow Sandhe", "path": "/player/gk-arlow", "overall": 86, "minutes": 1000, "age": 28, "nation": "England",
                 "team": {"id": "t1", "slug": "ravhurst-city", "name": "Ravhurst City", "path": "/team/ravhurst-city"}, "substituted": False},
                {"number": 2, "position": "RB", "id": "p2", "slug": "rb-ori", "name": "Ori Salamas", "path": "/player/rb-ori", "overall": 80, "minutes": 900, "age": 26, "nation": "England",
                 "team": {"id": "t1", "slug": "ravhurst-city", "name": "Ravhurst City", "path": "/team/ravhurst-city"}, "substituted": False},
            ],
            "captain": {"number": 8, "position": "CM", "name": "Cyrus Weller", "slug": "cm-cyrus", "path": "/player/cm-cyrus"},
            "next_fixture": {"slug": "fd-1", "path": "/match/fd-1", "kickoff_at": "2026-09-12T14:00:00Z", "round_label": "Matchday 1",
                              "home_team_id": "t1", "away_team_id": "t2"},
        },
    )


class TestMatchdayXiCoachRead:
    def test_the_door_answers_with_the_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _stub_xi(monkeypatch)
        monkeypatch.setattr(matchday_xi_coach, "get_llm_provider", lambda: _StubProvider())
        from app.services.matchday_xi_coach import compute_matchday_xi_coach_read

        body = compute_matchday_xi_coach_read(db=None)  # type: ignore[arg-type]
        assert body["available"] is True
        assert body["provider"] == "stub"
        assert body["edition"] == "2026/27"
        assert body["input_tokens"] == 180

    def test_an_unreachable_gateway_answers_without_crashing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _stub_xi(monkeypatch)
        monkeypatch.setattr(matchday_xi_coach, "get_llm_provider", lambda: _BrokenProvider())
        from app.services.matchday_xi_coach import compute_matchday_xi_coach_read

        body = compute_matchday_xi_coach_read(db=None)  # type: ignore[arg-type]
        assert body["available"] is False
        assert "gateway unreachable" in body["error"]

    def test_a_provider_error_answer_is_also_reported_available_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class _ErrorStub:
            name = "stub"

            def complete(self, *, system: str, prompt: str, max_tokens: int = 360, temperature: float = 0.3) -> LlmResult:  # noqa: ARG002
                return LlmResult(text="", provider="stub", model="stub-1", demo_mode=False, error="rate_limited")

        _stub_xi(monkeypatch)
        monkeypatch.setattr(matchday_xi_coach, "get_llm_provider", lambda: _ErrorStub())
        from app.services.matchday_xi_coach import compute_matchday_xi_coach_read

        body = compute_matchday_xi_coach_read(db=None)  # type: ignore[arg-type]
        assert body["available"] is False
        assert body["error"] == "rate_limited"

    def test_the_door_is_public_and_answers(self) -> None:
        client = TestClient(app)
        response = client.get(f"{API}/world/matchday-xi/coach-read")
        assert response.status_code == 200
        body = response.json()
        assert "available" in body
        assert body["edition"] == "2026/27"
