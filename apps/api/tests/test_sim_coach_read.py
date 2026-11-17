"""The Simulator's coach-read — one honest paragraph about one stored match."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.providers import LlmResult
from app.services import sim_coach


class _StubProvider:
    name = "stub"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 360, temperature: float = 0.3, prompt_cache_key: str | None = None) -> LlmResult:  # noqa: ARG002
        assert "Seed" in prompt
        assert "possession-block-v1" in prompt or "seed" in prompt.lower()
        return LlmResult(
            text="A controlled tactical battle on a seeded pitch: the higher press won the mid third for most of the night.",
            provider="stub",
            model="stub-1",
            demo_mode=False,
            input_tokens=640,
            output_tokens=44,
            cached_input_tokens=600,
            cache_reported=True,
            latency_ms=1,
        )


class _BrokenProvider:
    name = "stub"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 360, temperature: float = 0.3, prompt_cache_key: str | None = None) -> LlmResult:  # noqa: ARG002
        raise RuntimeError("gateway unreachable")


def _fake_match() -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        slug="sim-test-1",
        owner_id="usr_owner",
        model_version="possession-block-v1@1.0.0",
        seed=123456,
        minutes=90,
        substitutions=0,
        tactical_shift_minute=0,
        home_momentum=0.6,
        away_momentum=0.4,
        home_goals=2,
        away_goals=1,
        winner_side="home",
        report={
            "sides": {
                "home": {"name": "Ravhurst City", "system_name": "4-3-3 press", "formation": "4-3-3", "possession_pct": 58.0, "shots": 14, "shots_on_target": 6, "expected_goals": 2.1},
                "away": {"name": "Lyndera Albion", "system_name": "5-4-1 block", "formation": "5-4-1", "possession_pct": 42.0, "shots": 8, "shots_on_target": 2, "expected_goals": 0.9},
            }
        },
    )


def _stub_owner() -> SimpleNamespace:
    return SimpleNamespace(id="usr_owner")


class TestSimulationCoachRead:
    def test_the_door_answers_with_the_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sim_coach, "_get_match", lambda db, owner, ident: _fake_match())
        monkeypatch.setattr(sim_coach, "get_llm_provider", lambda: _StubProvider())
        from app.services.sim_coach import compute_simulation_coach_read

        body = compute_simulation_coach_read(db=None, owner=_stub_owner(), ident="sim-test-1")  # type: ignore[arg-type]
        assert body["available"] is True
        assert body["provider"] == "stub"
        assert body["input_tokens"] == 640

    def test_an_unreachable_gateway_answers_without_crashing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sim_coach, "_get_match", lambda db, owner, ident: _fake_match())
        monkeypatch.setattr(sim_coach, "get_llm_provider", lambda: _BrokenProvider())
        from app.services.sim_coach import compute_simulation_coach_read

        body = compute_simulation_coach_read(db=None, owner=_stub_owner(), ident="sim-test-1")  # type: ignore[arg-type]
        assert body["available"] is False
        assert "gateway unreachable" in body["error"]

    def test_foreign_match_is_not_served(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sim_coach, "_get_match", lambda db, owner, ident: None)
        from app.services.sim_coach import compute_simulation_coach_read

        body = compute_simulation_coach_read(db=None, owner=_stub_owner(), ident="not-mine")  # type: ignore[arg-type]
        assert body["available"] is False
        assert body["error"] == "no_such_simulation"
