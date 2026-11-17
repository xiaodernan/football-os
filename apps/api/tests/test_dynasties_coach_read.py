"""The Dynasties' coach-read — one honest paragraph on the world's streak ledger."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.providers import LlmResult
from app.services import dynasties_coach

API = "/api/v1"


class _StubProvider:
    name = "stub"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 320, temperature: float = 0.3) -> LlmResult:  # noqa: ARG002
        assert "streak" in prompt
        assert "tier-1" in prompt
        return LlmResult(
            text="Ravhurst City hold the longest run of wins, Elndera Naval the longest unbeaten run, and someone is ablaze at the latest matchday.",
            provider="stub",
            model="stub-1",
            demo_mode=False,
            input_tokens=340,
            output_tokens=36,
            cached_input_tokens=320,
            cache_reported=True,
            latency_ms=1,
        )


class _BrokenProvider:
    name = "stub"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 320, temperature: float = 0.3) -> LlmResult:  # noqa: ARG002
        raise RuntimeError("gateway unreachable")


def _stub_ledger(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        dynasties_coach,
        "compute_dynasties",
        lambda db: {
            "available": True,
            "season": {"label": "2026/27", "kind": "7:3"},
            "competition": "Premier League",
            "competition_slug": "premier-league",
            "judged": 140,
            "longest_win": {
                "kind": "win", "length": 6, "start_kickoff_at": "2026-08-03T18:30:00Z", "end_kickoff_at": "2026-09-21T18:30:00Z",
                "start_round": "Matchday 1", "end_round": "Matchday 6",
                "team": {"id": "t1", "slug": "ravhurst-city", "name": "Ravhurst City", "path": "/team/ravhurst-city"},
            },
            "longest_unbeaten": {
                "kind": "unbeaten", "length": 11, "start_kickoff_at": "2026-08-03T18:30:00Z", "end_kickoff_at": "2026-10-12T18:30:00Z",
                "start_round": "Matchday 1", "end_round": "Matchday 11",
                "team": {"id": "t2", "slug": "elndera-naval", "name": "Elndera Naval", "path": "/team/elndera-naval"},
            },
            "win_streaks": [
                {
                    "kind": "win", "length": 6, "start_round": "Matchday 1", "end_round": "Matchday 6",
                    "team": {"id": "t1", "slug": "ravhurst-city", "name": "Ravhurst City", "path": "/team/ravhurst-city"},
                }
            ],
            "unbeaten_runs": [
                {
                    "kind": "unbeaten", "length": 11, "start_round": "Matchday 1", "end_round": "Matchday 11",
                    "team": {"id": "t2", "slug": "elndera-naval", "name": "Elndera Naval", "path": "/team/elndera-naval"},
                }
            ],
            "ablaze": {"team": {"id": "t1", "slug": "ravhurst-city", "name": "Ravhurst City", "path": "/team/ravhurst-city"}, "current_win_run": 4, "matches": 18},
        },
    )


class TestDynastiesCoachRead:
    def test_the_door_answers_with_the_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _stub_ledger(monkeypatch)
        monkeypatch.setattr(dynasties_coach, "get_llm_provider", lambda: _StubProvider())
        from app.services.dynasties_coach import compute_dynasties_coach_read

        body = compute_dynasties_coach_read(db=None)  # type: ignore[arg-type]
        assert body["available"] is True
        assert body["provider"] == "stub"
        assert body["edition"] == "2026/27"
        assert body["input_tokens"] == 340

    def test_an_unreachable_gateway_answers_without_crashing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _stub_ledger(monkeypatch)
        monkeypatch.setattr(dynasties_coach, "get_llm_provider", lambda: _BrokenProvider())
        from app.services.dynasties_coach import compute_dynasties_coach_read

        body = compute_dynasties_coach_read(db=None)  # type: ignore[arg-type]
        assert body["available"] is False
        assert "gateway unreachable" in body["error"]

    def test_a_provider_error_answer_is_also_reported_available_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class _ErrorStub:
            name = "stub"

            def complete(self, *, system: str, prompt: str, max_tokens: int = 320, temperature: float = 0.3) -> LlmResult:  # noqa: ARG002
                return LlmResult(text="", provider="stub", model="stub-1", demo_mode=False, error="rate_limited")

        _stub_ledger(monkeypatch)
        monkeypatch.setattr(dynasties_coach, "get_llm_provider", lambda: _ErrorStub())
        from app.services.dynasties_coach import compute_dynasties_coach_read

        body = compute_dynasties_coach_read(db=None)  # type: ignore[arg-type]
        assert body["available"] is False
        assert body["error"] == "rate_limited"

    def test_the_door_is_public_and_answers(self) -> None:
        client = TestClient(app)
        response = client.get(f"{API}/world/dynasties/coach-read")
        assert response.status_code == 200
        body = response.json()
        assert "available" in body
        assert body["edition"] == "2026/27"
