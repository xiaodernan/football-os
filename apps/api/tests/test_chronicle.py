"""The Chronicle — the state graph that writes the chapter the season has earned to date."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.providers import LlmResult
from app.services import chronicle

API = "/api/v1"


class _StubProvider:
    name = "stub"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 800, temperature: float = 0.4, prompt_cache_key: str | None = None) -> LlmResult:  # noqa: ARG002
        if "chronicler" in system:
            return LlmResult(
                text="Ostmoor Albion lead the table after the printed matchday, the cup ledger stands, and the streak ledger never lies.",
                provider="stub",
                model="stub-1",
                demo_mode=False,
                input_tokens=900,
                output_tokens=40,
                cached_input_tokens=850,
                cache_reported=True,
                latency_ms=1,
            )
        assert "copy desk" in system
        return LlmResult(
            text="Ostmoor Albion lead the printed table, every cup line is as the ledger prints it, and the streak ledger says what it says.",
            provider="stub",
            model="stub-1",
            demo_mode=False,
            input_tokens=700,
            output_tokens=38,
            cached_input_tokens=660,
            cache_reported=True,
            latency_ms=1,
        )


class _BrokenProvider:
    name = "stub"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 800, temperature: float = 0.4, prompt_cache_key: str | None = None) -> LlmResult:  # noqa: ARG002
        raise RuntimeError("gateway unreachable")


def _stub_gather(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        chronicle,
        "compute_gazette",
        lambda db, edition=None: {
            "available": True,
            "season": {"label": "2026/27", "kind": "7:3"},
            "edition": 14,
            "total_editions": 24,
            "published_at": "2026-11-12T20:00:00",
            "competition": {"name": "Tier-1", "slug": "tier-1", "path": "/competition/tier-1"},
            "number": {"goals_this_round": 11, "draws": 2, "clean_sheets": 1, "season_average_goals": 2.1, "fixtures": 10},
            "table_after": [
                {"position": 1, "team": {"slug": "ostmoor-albion", "name": "Ostmoor Albion", "path": "/team/ostmoor-albion"}, "played": 14, "won": 7, "drawn": 2, "lost": 5, "goals_for": 21, "goals_against": 15, "goal_difference": 6, "points": 23},
            ],
            "lead": {"home": {"name": "Ostmoor Albion"}, "away": {"name": "Barvhold United"}, "home_goals": 3, "away_goals": 1, "venue": "Albion Park", "kickoff": "2026-11-12T20:00:00"},
            "hot_hand": {"team": {"name": "Ostmoor Albion"}, "goals": 3},
            "table_leader": {"team": {"name": "Ostmoor Albion"}, "points": 23},
            "table_gap": 0,
        },
    )
    monkeypatch.setattr(
        chronicle,
        "compute_champions",
        lambda: {
            "available": True,
            "entries": [
                {"tournament": "2014", "title": "2014 FIFA World Cup", "host": "Brazil", "venues": 12, "total_matches": 64,
                 "goals_scored": 171, "goals_per_match": 2.67, "has_penalties": False,
                 "champion": {"name": "Germany", "note": ""}, "runner_up": {"name": "Argentina", "note": ""},
                 "golden_ball": {"name": "Lionel Messi", "note": "on the losing side"},
                 "final": {"score_regular": [0, 0], "score_extra_time": [1, 0], "score_penalties": [0, 0]},
                 "final_row": None,
                 "biggest_win": {"match": "Germany 7-1 Brazil", "score": [7, 1], "stage": "Semi-finals"},
                 "top_scorers": [{"name": "Lionel Messi", "goals": 4, "penalties": 1}],
                 "top_scorers_note": None,
                 "has_scorers": True},
            ],
            "merged_scorers": [{"name": "Lionel Messi", "goals_2014": 4, "goals_2018": 1, "goals_2022": 7, "total": 12}],
            "joint_top_scorers_note": None,
        },
    )
    monkeypatch.setattr(
        chronicle,
        "compute_dynasties",
        lambda db: {
            "available": True,
            "competition": "Tier-1",
            "judged": 140,
            "longest_win": {"kind": "win", "length": 3, "start_round": "MD 4", "end_round": "MD 6", "team": {"name": "Quernmoor Town", "slug": "quernmoor-town"}},
            "longest_unbeaten": {"kind": "unbeaten", "length": 8, "start_round": "MD 6", "end_round": "MD 13", "team": {"name": "Elndera Naval", "slug": "elndera-naval"}},
            "win_streaks": [{"kind": "win", "length": 3, "start_round": "MD 4", "end_round": "MD 6", "team": {"name": "Quernmoor Town", "slug": "quernmoor-town"}}],
            "unbeaten_runs": [{"kind": "unbeaten", "length": 8, "start_round": "MD 6", "end_round": "MD 13", "team": {"name": "Elndera Naval", "slug": "elndera-naval"}}],
            "ablaze": {"team": {"name": "Dunstead Naval", "slug": "dunstead-naval"}, "current_win_run": 2, "matches": 14},
        },
    )
    monkeypatch.setattr(
        chronicle,
        "compute_records",
        lambda db: {
            "season": {"label": "2026/27"},
            "records": [{"key": "biggest_haul", "available": True, "player": {"name": "T. Corvan", "slug": "t-corvan"}, "goals": 4}],
        },
    )
    monkeypatch.setattr(chronicle, "budget_exhausted", lambda db: False)
    monkeypatch.setattr(chronicle, "record_model_call_safely", lambda *, result, feature, user_id=None: True)


class TestChronicle:
    def test_the_graph_walks_gather_draft_revise_and_answers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _stub_gather(monkeypatch)
        monkeypatch.setattr(chronicle, "get_llm_provider", lambda: _StubProvider())
        body = chronicle.compute_chronicle(db=None)
        assert body["available"] is True
        assert body["revision"] == "applied"
        assert body["provider"] == "stub"
        assert body["input_tokens"] == 1600
        assert body["cached_input_tokens"] == 1510
        assert body["graph_trace"] == ["START", "gather", "draft", "revise", "END"]
        assert "every cup line is as the ledger prints it" in body["answer"]

    def test_an_unreachable_gateway_answers_without_crashing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _stub_gather(monkeypatch)
        monkeypatch.setattr(chronicle, "get_llm_provider", lambda: _BrokenProvider())
        body = chronicle.compute_chronicle(db=None)
        assert body["available"] is False
        assert "gateway unreachable" in body["error"]

    def test_a_provider_error_answer_is_also_reported_unavailable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _stub_gather(monkeypatch)

        class _ErrorStub:
            name = "stub"

            def complete(self, *, system: str, prompt: str, max_tokens: int = 800, temperature: float = 0.4, prompt_cache_key: str | None = None) -> LlmResult:  # noqa: ARG002
                return LlmResult(text="", provider="stub", model="stub-1", demo_mode=False, error="rate_limited")

        monkeypatch.setattr(chronicle, "get_llm_provider", lambda: _ErrorStub())
        body = chronicle.compute_chronicle(db=None)
        assert body["available"] is False
        assert body["error"] == "rate_limited"

    def test_the_door_is_public_and_answers(self) -> None:
        client = TestClient(app)
        response = client.get(f"{API}/world/chronicle/coach-read")
        assert response.status_code == 200
        body = response.json()
        assert "available" in body
        assert body["graph_trace"][0] == "START"
