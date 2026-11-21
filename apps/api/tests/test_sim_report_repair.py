"""The verify→repair conditional edge: drift is caught and corrected, not kept."""

from __future__ import annotations

from types import SimpleNamespace

from app.providers import LlmResult
from app.services import sim_report_graph
from app.services.sim_report_graph import (
    ReportState,
    _node_repair,
    _node_verify,
    _verify_route,
    run_report_graph,
)


class _DriftingProvider:
    """Returns one honest sentence and one that quotes a figure the engine never stored (9.9 xG)."""

    name = "drifting"

    def complete(self, *, system, prompt, max_tokens=360, temperature=0.3, prompt_cache_key=None):  # type: ignore[no-untyped-def]
        return LlmResult(
            text="The pressing side controlled the rhythm for long spells. The xG was 9.9 which proves dominance.",
            provider="drifting",
            model="drift-1",
            demo_mode=False,
            input_tokens=100,
            output_tokens=30,
            cached_input_tokens=90,
            cache_reported=True,
            latency_ms=1,
        )


def _match() -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        slug="drift-test",
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
            },
            "events": [],
        },
    )


def test_verify_routes_to_repair_on_drift_and_to_assemble_when_clean():
    clean = ReportState(ident="x", verified={"statistics": True})
    assert _verify_route(clean) == "assemble"
    drifted = ReportState(ident="x", verified={"statistics": False})
    assert _verify_route(drifted) == "repair"


def test_repair_drops_the_drifted_sentence_and_marks_it_verified():
    state = ReportState(ident="x")
    state.facts = sim_report_graph._facts(_match())  # type: ignore[arg-type]
    state.events = []
    state.score_text = "2-1"
    state.sections = {"statistics": "The pressing side controlled the rhythm. The xG was 9.9 which proves dominance."}
    state = _node_verify(state)
    assert state.verified["statistics"] is False
    state = _node_repair(state)
    assert state.verified["statistics"] is True
    assert "9.9" not in state.sections["statistics"]
    assert "controlled the rhythm" in state.sections["statistics"]
    assert state.repairs == 1


def test_all_drifted_sentences_fall_back_to_an_honest_notice():
    state = ReportState(ident="x", locale="zh")
    state.facts = sim_report_graph._facts(_match())  # type: ignore[arg-type]
    state.events = []
    state.score_text = "2-1"
    state.sections = {"statistics": "xG 9.9 表明 dominance."}
    state = _node_verify(state)
    state = _node_repair(state)
    assert "9.9" not in state.sections["statistics"]
    assert "移除" in state.sections["statistics"]  # the Chinese honest notice


def test_graph_walk_repairs_drift_end_to_end():
    state = run_report_graph(_match(), provider=_DriftingProvider())  # type: ignore[arg-type]
    nodes = [row["node"] for row in state.trace]
    assert "verify" in nodes
    assert "repair" in nodes  # the conditional edge actually fired
    assert state.repairs >= 1
    assert "9.9" not in state.sections.get("_answer", "")
    assert all(state.verified.values())


def test_clean_provider_never_takes_the_repair_edge():
    class _Clean(_DriftingProvider):
        def complete(self, **kwargs):  # type: ignore[no-untyped-def]
            return LlmResult(
                text="The press controlled the mid third for most of the night.",
                provider="clean",
                model="clean-1",
                demo_mode=False,
                input_tokens=100,
                output_tokens=20,
                cached_input_tokens=90,
                cache_reported=True,
                latency_ms=1,
            )

    state = run_report_graph(_match(), provider=_Clean())  # type: ignore[arg-type]
    assert state.repairs == 0
    assert "repair" not in [row["node"] for row in state.trace]
