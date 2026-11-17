"""The Upset Register's coach-read — one honest paragraph on where the favourite's edge fell short."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.providers import LlmResult
from app.services import upsets_coach

API = "/api/v1"


class _StubProvider:
    name = "stub"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 320, temperature: float = 0.3) -> LlmResult:  # noqa: ARG002
        assert "gap" in prompt
        assert "tier-1" in prompt
        return LlmResult(
            text="The favourite's edge surrendered in 4 of 36 judged fixtures; the widest falls turned a rating gap of 12.4 into a goal of the underdog.",
            provider="stub",
            model="stub-1",
            demo_mode=False,
            input_tokens=210,
            output_tokens=44,
            cached_input_tokens=190,
            cache_reported=True,
            latency_ms=1,
        )


class _BrokenProvider:
    name = "stub"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 320, temperature: float = 0.3) -> LlmResult:  # noqa: ARG002
        raise RuntimeError("gateway unreachable")


def _stub_register(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        upsets_coach,
        "compute_upsets",
        lambda db: {
            "available": True,
            "season": {"label": "2026/27", "kind": "7:3"},
            "competition": "Premier League",
            "competition_slug": "premier-league",
            "judged": 36,
            "upset_count": 4,
            "fortress_count": 2,
            "mean_upset_gap": 9.6,
            "upset_rate_pct": 11.11,
            "fortress_gap": 8.0,
            "biggest_upset": {
                "slug": "fd-99",
                "path": "/match/fd-99",
                "kickoff_at": "2026-10-04T15:00:00Z",
                "round_label": "Matchday 12",
                "home": {"id": "t1", "slug": "ravhurst-city", "name": "Ravhurst City", "path": "/team/ravhurst-city"},
                "away": {"id": "t2", "slug": "lowmore-athletic", "name": "Lowmore Athletic", "path": "/team/lowmore-athletic"},
                "home_goals": 0,
                "away_goals": 1,
                "favorite": "home",
                "rating_gap": 12.4,
                "kind": "upset",
            },
            "fortress": None,
            "upsets": [
                {
                    "slug": "fd-99",
                    "path": "/match/fd-99",
                    "kickoff_at": "2026-10-04T15:00:00Z",
                    "round_label": "Matchday 12",
                    "home": {"id": "t1", "slug": "ravhurst-city", "name": "Ravhurst City"},
                    "away": {"id": "t2", "slug": "lowmore-athletic", "name": "Lowmore Athletic"},
                    "home_goals": 0,
                    "away_goals": 1,
                    "favorite": "home",
                    "rating_gap": 12.4,
                    "kind": "upset",
                }
            ],
            "fortresses": [],
            "recent_upsets": [],
        },
    )


class TestUpsetsCoachRead:
    def test_the_door_answers_with_the_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _stub_register(monkeypatch)
        monkeypatch.setattr(upsets_coach, "get_llm_provider", lambda: _StubProvider())
        from app.services.upsets_coach import compute_upsets_coach_read

        body = compute_upsets_coach_read(db=None)  # type: ignore[arg-type]
        assert body["available"] is True
        assert body["provider"] == "stub"
        assert body["edition"] == "2026/27"
        assert body["input_tokens"] == 210
        assert body["answer"].startswith("The favourite")

    def test_an_unreachable_gateway_answers_without_crashing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _stub_register(monkeypatch)
        monkeypatch.setattr(upsets_coach, "get_llm_provider", lambda: _BrokenProvider())
        from app.services.upsets_coach import compute_upsets_coach_read

        body = compute_upsets_coach_read(db=None)  # type: ignore[arg-type]
        assert body["available"] is False
        assert "gateway unreachable" in body["error"]

    def test_a_provider_error_answer_is_also_reported_available_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class _ErrorStub:
            name = "stub"

            def complete(self, *, system: str, prompt: str, max_tokens: int = 320, temperature: float = 0.3) -> LlmResult:  # noqa: ARG002
                return LlmResult(text="", provider="stub", model="stub-1", demo_mode=False, error="rate_limited")

        _stub_register(monkeypatch)
        monkeypatch.setattr(upsets_coach, "get_llm_provider", lambda: _ErrorStub())
        from app.services.upsets_coach import compute_upsets_coach_read

        body = compute_upsets_coach_read(db=None)  # type: ignore[arg-type]
        assert body["available"] is False
        assert body["error"] == "rate_limited"

    def test_the_door_is_public_and_answers(self) -> None:
        client = TestClient(app)
        response = client.get(f"{API}/world/upsets/coach-read")
        assert response.status_code == 200
        body = response.json()
        assert "available" in body
        assert body["edition"] == "2026/27"
