"""The reusable world-coach phrasing graph verifies figures before shipping."""

from __future__ import annotations

from app.providers import LlmResult
from app.services import verified_phrasing as vp
from app.services.verified_phrasing import (
    PhraseState,
    _node_repair,
    _node_verify,
    _verify_route,
    allowed_figures_from,
    phrase_and_verify,
)


class _Drifting:
    name = "drift"

    def complete(self, *, system, prompt, max_tokens=380, temperature=0.3, prompt_cache_key=None):  # type: ignore[no-untyped-def]
        return LlmResult(
            text="Eight Finals were decided, 2.5 goals each. A phantom 9.9 rating appeared.",
            provider="drift", model="d", demo_mode=False,
            input_tokens=100, output_tokens=20, cached_input_tokens=90, cache_reported=True, latency_ms=1,
        )


def test_allowed_figures_come_from_the_prompt_only():
    figs = allowed_figures_from("Goals: 24 across 8 finals. Rating 7.5, xG 2.1")
    assert {"24", "8", "7.5", "2.1"} <= figs


def test_verify_flags_a_decimal_not_in_the_facts():
    s = PhraseState(system="s", prompt="p", feature="f", answer="A 9.9 rating.",
                    allowed_figures={"24", "7.5"})
    s = _node_verify(s)
    assert s.verified is False
    assert any("9.9" in t.get("unmatched", []) for t in s.trace if t["node"] == "verify")


def test_repair_drops_only_the_drifted_sentence():
    s = PhraseState(system="s", prompt="p", feature="f",
                    answer="Eight finals were decided. A phantom 9.9 rating appeared.",
                    allowed_figures={"8"})
    s = _node_verify(s)
    s = _node_repair(s)
    assert s.verified is True
    assert "9.9" not in s.answer
    assert "Eight finals were decided" in s.answer
    assert s.repairs == 1


def test_route_only_repairs_on_drift():
    ok = PhraseState(system="s", prompt="p", feature="f", answer="ok", verified=True)
    bad = PhraseState(system="s", prompt="p", feature="f", answer="bad", verified=False)
    assert _verify_route(ok) == "assemble"
    assert _verify_route(bad) == "repair"


def test_end_to_end_repares_drift(monkeypatch):
    monkeypatch.setattr(vp, "get_llm_provider", lambda: _Drifting())
    state = phrase_and_verify(system="s", prompt="Goals: 24. Rating 7.5", feature="world.test.read")
    assert state.result and state.result.provider == "drift"
    assert state.repairs >= 1
    assert "9.9" not in state.answer
    assert any(row["node"] == "repair" for row in state.trace)
