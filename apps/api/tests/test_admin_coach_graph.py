"""The admin coach is now a verified StateGraph: drift is caught and repaired, not printed."""

from __future__ import annotations

from app.providers import LlmResult
from app.services import behavior_coach as bc
from app.services.behavior_coach import CoachState, _node_repair, _node_verify, _verify_route


def _state(answer: str) -> CoachState:
    s = CoachState(window_days=90)
    s.answer = answer
    s.allowed_figures = {"0.55", "0.42", "32.28", "58.0", "89.1"}
    return s


class _DriftingProvider:
    name = "drifting"

    def complete(self, *, system, prompt, max_tokens=500, temperature=0.4, prompt_cache_key=None):  # type: ignore[no-untyped-def]
        # "9.9" is a fabricated cost/cache figure the console never printed.
        return LlmResult(
            text="Hold the sprint: cache share is 9.9% so the gateway is cold. Keep the cohort engaged.",
            provider="drifting", model="drift-1", demo_mode=False,
            input_tokens=100, output_tokens=30, cached_input_tokens=90, cache_reported=True, latency_ms=1,
        )


def test_verify_routes_to_repair_only_on_drift():
    assert _verify_route(_node_verify(_state("Cache share is 32.28% today."))) == "assemble"
    assert _verify_route(_node_verify(_state("Cache share is 9.9% today."))) == "repair"


def test_verify_flags_a_figure_the_console_never_printed():
    s = _node_verify(_state("Cache share is 9.9% today."))
    assert s.verified is False
    assert any("9.9" in t.get("unmatched", []) for t in s.trace if t["node"] == "verify")


def test_repair_drops_only_the_drifted_sentence():
    s = _node_repair(_state("Hold the sprint: cache share is 9.9% so the gateway is cold. Keep the cohort engaged."))
    assert s.verified is True
    assert "9.9" not in s.answer
    assert "Keep the cohort engaged" in s.answer
    assert s.repairs == 1


def test_all_drifted_sentences_fall_back_to_an_honest_refusal():
    s = _node_repair(_state("Cache share is 9.9% and 7.7%."))
    assert "9.9" not in s.answer and "7.7" not in s.answer
    assert "cannot support" in s.answer


def test_graph_end_to_end_repairs_model_drift(monkeypatch):
    monkeypatch.setattr(bc, "compute_behavior", lambda *a, **k: _behavior())
    monkeypatch.setattr(bc, "compute_model_census", lambda *a, **k: _census())
    monkeypatch.setattr(bc, "get_llm_provider", lambda: _DriftingProvider())
    body = bc.compute_admin_coach_read(db=None, window_days=90)
    assert body["available"] is True, body
    assert body["verified"] is True
    assert body["repairs"] >= 1
    assert "9.9" not in body["answer"]
    assert any(row["node"] == "repair" for row in body["trace"])


def _behavior():
    return {
        "window_days": 90,
        "source_note": {"seeded_views": 0},
        "totals": {"views": 1000, "sessions": 200, "unique_paths": 10, "bounce_rate": 0.55, "median_dwell_ms": 5800},
        "forecast": {"slope_per_day": 0.12, "r_squared": 0.7, "projected_sessions": [10, 12]},
        "funnels": [{"id": "tutorial_to_manual", "rate": 0.42}],
        "pages": [], "recommendations": [],
    }


def _census():
    return {
        "totals": {"calls": 100, "failures": 2, "failure_rate": 0.02, "demo_mode_share": 0.1,
                   "cached_share_reported": 0.891, "actual_cost_usd": 0.5, "estimated_cost_usd": 0.6,
                   "median_latency_ms": 120, "input_tokens": 1000, "output_tokens": 200,
                   "reported_rows": 5},
        "by_feature": [],
        "errors": [],
    }
