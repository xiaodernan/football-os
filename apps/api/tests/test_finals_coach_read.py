"""The Finals' coach-read — one honest paragraph on the cup ledger of this world."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.providers import LlmResult
from app.services import finals_coach

API = "/api/v1"


class _StubProvider:
    name = "stub"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 380, temperature: float = 0.3) -> LlmResult:  # noqa: ARG002
        assert "Finals" in prompt
        assert "cup" in prompt
        return LlmResult(
            text="Elndera Naval lifted one, and the loudest of the eight was Ildmoor Harbour Cup 4-2 at Neutral venue.",
            provider="stub",
            model="stub-1",
            demo_mode=False,
            input_tokens=520,
            output_tokens=47,
            cached_input_tokens=500,
            cache_reported=True,
            latency_ms=1,
        )


class _BrokenProvider:
    name = "stub"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 380, temperature: float = 0.3) -> LlmResult:  # noqa: ARG002
        raise RuntimeError("gateway unreachable")


def _stub_ledger(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        finals_coach,
        "compute_finals",
        lambda db: {
            "available": True,
            "season": {"label": "2026/27", "kind": "7:3"},
            "finals": [
                {
                    "competition": {"id": "wcmp_a", "name": "Haldhurst Invitation Cup", "slug": "haldhurst-invitation-cup", "path": "/competition/haldhurst-invitation-cup"},
                    "fixture": {"id": "wmat_a", "slug": "fd-a", "path": "/match/fd-a", "kickoff": "2027-01-06T20:15:00+00:00", "venue": "Cordale Yard", "city": "Neutral venue", "season": "2026"},
                    "home": {"id": "t1", "slug": "braeford-athletic", "name": "Braeford Athletic", "path": "/team/braeford-athletic"},
                    "away": {"id": "t2", "slug": "cordale-town", "name": "Cordale Town", "path": "/team/cordale-town"},
                    "home_goals": 1,
                    "away_goals": 0,
                    "winner": "home",
                    "winning_team": {"id": "t1", "slug": "braeford-athletic", "name": "Braeford Athletic", "path": "/team/braeford-athletic"},
                    "mvp": {"id": "p1", "slug": "zeeth-veitmann", "name": "Zeeth Veitmann", "path": "/player/zeeth-veitmann", "overall": 48, "position": "CM", "rating": 7.24, "goals": 1, "assists": 0},
                }
            ],
            "stats": {"finals": 8, "goals": 17},
            "loudest": {
                "competition": {"id": "wcmp_b", "name": "Ildmoor Harbour Cup", "slug": "ildmoor-harbour-cup", "path": "/competition/ildmoor-harbour-cup"},
                "goals": 6,
                "home_goals": 4,
                "away_goals": 2,
                "venue": "Ildmoor Quay",
            },
            "cup_wins": [
                {"team": {"id": "t1", "slug": "elndera-naval", "name": "Elndera Naval", "path": "/team/elndera-naval"}, "cups": 1, "names": ["Haldhaven Grand Cup"]},
                {"team": {"id": "t2", "slug": "braeford-athletic", "name": "Braeford Athletic", "path": "/team/braeford-athletic"}, "cups": 1, "names": ["Haldhurst Invitation Cup"]},
            ],
        },
    )


class TestFinalsCoachRead:
    def test_the_door_answers_with_the_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _stub_ledger(monkeypatch)
        monkeypatch.setattr(finals_coach, "get_llm_provider", lambda: _StubProvider())
        from app.services.finals_coach import compute_finals_coach_read

        body = compute_finals_coach_read(db=None)  # type: ignore[arg-type]
        assert body["available"] is True
        assert body["provider"] == "stub"
        assert body["edition"] == "2026/27"
        assert body["input_tokens"] == 520

    def test_an_unreachable_gateway_answers_without_crashing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _stub_ledger(monkeypatch)
        monkeypatch.setattr(finals_coach, "get_llm_provider", lambda: _BrokenProvider())
        from app.services.finals_coach import compute_finals_coach_read

        body = compute_finals_coach_read(db=None)  # type: ignore[arg-type]
        assert body["available"] is False
        assert "gateway unreachable" in body["error"]

    def test_a_provider_error_answer_is_also_reported_available_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class _ErrorStub:
            name = "stub"

            def complete(self, *, system: str, prompt: str, max_tokens: int = 380, temperature: float = 0.3) -> LlmResult:  # noqa: ARG002
                return LlmResult(text="", provider="stub", model="stub-1", demo_mode=False, error="rate_limited")

        _stub_ledger(monkeypatch)
        monkeypatch.setattr(finals_coach, "get_llm_provider", lambda: _ErrorStub())
        from app.services.finals_coach import compute_finals_coach_read

        body = compute_finals_coach_read(db=None)  # type: ignore[arg-type]
        assert body["available"] is False
        assert body["error"] == "rate_limited"

    def test_the_door_is_public_and_answers(self) -> None:
        client = TestClient(app)
        response = client.get(f"{API}/world/finals/coach-read")
        assert response.status_code == 200
        body = response.json()
        assert "available" in body
        assert body["edition"] == "2026/27"
