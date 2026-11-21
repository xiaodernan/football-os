"""The deep dossier — a 50k–90k token context that must stay measurable and honest.

The owner's complaint was not "the model cannot write"; it was "输入上下文总是太少". A prompt size
that only exists in a probe script is still missing from the product, so these cases pin the bands,
the determinism, the frozen cache prefix and the verification branch — all offline, no gateway spend.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.providers import LlmResult
from app.services.world import deep_dossier


class _StubProvider:
    name = "stub"

    def __init__(self, text: str = "Real Madrid 4–3 Stade de Reims in 1956.") -> None:
        self.text = text
        self.seen: dict[str, Any] = {}

    def complete(self, *, system: str, prompt: str, max_tokens: int = 1100, temperature: float = 0.35) -> LlmResult:  # noqa: ARG002
        self.seen = {"system": system, "prompt": prompt, "prompt_len": len(prompt)}
        return LlmResult(
            text=self.text,
            provider="stub",
            model="stub-1",
            demo_mode=False,
            input_tokens=85186,
            cached_input_tokens=80000,
            cache_reported=True,
            output_tokens=22,
            latency_ms=1,
        )


@pytest.fixture(autouse=True)
def _no_ledger(monkeypatch: pytest.MonkeyPatch) -> None:
    """The dossier's footprint is the claim under test; the spend sidecar is not."""
    monkeypatch.setattr(deep_dossier, "record_model_call_safely", lambda **_: True)


@pytest.mark.parametrize("depth", ["standard", "deep", "epic"])
def test_each_depth_lands_in_the_requested_context_class(depth: str) -> None:
    dossier = deep_dossier.build_dossier("real finals and the long arc of European football", depth=depth, seed=42)
    assert 50_000 <= dossier.total_estimated_tokens <= deep_dossier.MAX_TARGET, (
        f"{depth}: {dossier.total_estimated_tokens} tokens is outside 50k–{deep_dossier.MAX_TARGET}"
    )
    assert dossier.total_estimated_tokens >= dossier.target_tokens
    assert dossier.chars > 0
    assert dossier.sources, "a band must carry at least one real committed chapter"
    assert all(deep_dossier.HISTORY_DIR.joinpath(f"{name}.md").is_file() for name in dossier.sources)


def test_the_epic_band_is_larger_than_deep_and_deep_larger_than_standard() -> None:
    sizes = [
        deep_dossier.build_dossier("finals", depth=depth, seed=7).total_estimated_tokens
        for depth in ("standard", "deep", "epic")
    ]
    assert sizes[0] < sizes[1] < sizes[2], f"bands did not grow: {sizes}"


def test_the_dossier_is_byte_identical_for_the_same_focus_seed_and_depth() -> None:
    args = {"depth": "deep", "seed": 7}
    first = deep_dossier.build_dossier("finals", **args)
    second = deep_dossier.build_dossier("finals", **args)
    assert first.text == second.text
    assert first.sources == second.sources
    assert first.total_estimated_tokens == second.total_estimated_tokens


def test_seed_and_focus_change_the_selection_but_never_the_size_class() -> None:
    a = deep_dossier.build_dossier("derbies", depth="deep", seed=1)
    b = deep_dossier.build_dossier("derbies", depth="deep", seed=2)
    assert a.text != b.text, "seed must change the deterministic selection"
    for dossier in (a, b):
        assert 50_000 <= dossier.total_estimated_tokens <= deep_dossier.MAX_TARGET


def test_every_call_sits_behind_the_same_frozen_charter_prefix() -> None:
    stub = _StubProvider()
    state = deep_dossier.run_dossier_graph("finals", depth="standard", seed=7, provider=stub)
    assert [item["node"] for item in state.trace] == ["harvest", "draft", "verify", "assemble"]
    assert stub.seen["system"] == deep_dossier._SYSTEM_PREFIX
    assert stub.seen["system"].startswith("THE LIBRARY THE PASSAGES COME FROM") is False
    assert stub.seen["system"].lstrip().startswith("THE LIBRARY THE PASSAGES COME FROM")
    # The dossier travels in the user turn, not folded into the cached system prefix.
    assert stub.seen["prompt_len"] > 10_000
    assert "Reader's focus: finals" in stub.seen["prompt"]


def test_locale_reaches_the_question_without_touching_the_cached_prefix() -> None:
    systems: list[str] = []
    prompts: list[str] = []

    class Recording(_StubProvider):
        def complete(self, *, system: str, prompt: str, max_tokens: int = 1100, temperature: float = 0.35) -> LlmResult:  # noqa: ARG002
            systems.append(system)
            prompts.append(prompt)
            return super().complete(system=system, prompt=prompt, max_tokens=max_tokens, temperature=temperature)

    stub = Recording()
    deep_dossier.run_dossier_graph("finals", depth="standard", seed=7, locale="zh", provider=stub)
    assert systems == [deep_dossier._SYSTEM_PREFIX]
    assert "请用中文回答" in prompts[0]


def test_verify_reports_a_decimal_the_dossier_never_carried() -> None:
    stub = _StubProvider("The final ended 3.14159 to nothing, a famous night in 1956.")
    payload = deep_dossier.compute_deep_dossier("finals", depth="standard", seed=7, provider=stub)
    assert payload["verified"] is False
    assert "3.14159" in payload["drifted_decimals"]
    assert payload["chapter"], "verification reports drift, it never deletes the model's prose"
    assert any(item["node"] == "verify" and "ungrounded" in item["detail"] for item in payload["trace"])


def test_grounded_decimals_pass_verification() -> None:
    stub = _StubProvider("Real Madrid won 4–3 in 1956; the crowd was 38,239.")
    payload = deep_dossier.compute_deep_dossier("finals", depth="epic", seed=7, provider=stub)
    assert payload["verified"] is True
    assert payload["drifted_decimals"] == []


def test_a_broken_gateway_still_publishes_the_measured_dossier() -> None:
    class Broken:
        name = "broken"

        def complete(self, **_: Any) -> LlmResult:
            raise RuntimeError("gateway unreachable")

    payload = deep_dossier.compute_deep_dossier("finals", depth="deep", seed=7, provider=Broken())
    assert payload["available"] is False
    assert payload["estimated_input_tokens"] > 50_000
    assert payload["source_count"] > 0
    assert "gateway unreachable" in payload["error"]
    assert [item["node"] for item in payload["trace"]][-1] == "assemble"


def test_an_empty_focus_is_refused_before_any_work() -> None:
    payload = deep_dossier.compute_deep_dossier("   ", depth="deep", seed=7, provider=_StubProvider())
    assert payload == {"available": False, "error": "focus is empty"}


def test_unknown_depth_is_refused_at_the_boundary() -> None:
    with pytest.raises(ValueError, match="unknown depth"):
        deep_dossier.build_dossier("finals", depth="infinite", seed=7)


def test_gateway_usage_is_published_verbatim() -> None:
    payload = deep_dossier.compute_deep_dossier("finals", depth="standard", seed=7, provider=_StubProvider())
    assert payload["input_tokens"] == 85186
    assert payload["cached_input_tokens"] == 80000
    assert payload["cache_reported"] is True
    assert payload["output_tokens"] == 22


def test_door_publishes_the_measured_footprint_when_the_gateway_is_down(client: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    class Broken:
        name = "broken"

        def complete(self, **_: Any) -> LlmResult:
            raise RuntimeError("gateway unreachable")

    monkeypatch.setattr(deep_dossier, "get_llm_provider", lambda: Broken())
    response = client.get(
        "/api/v1/world/deep-dossier",
        params={"focus": "finals", "depth": "standard", "seed": 7},
        headers={"x-fo-locale": "zh"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["data_origin"] == "synthetic"
    assert body["available"] is False
    assert body["estimated_input_tokens"] > 50_000
    assert body["source_count"] > 0
    assert body["trace"][-1]["node"] == "assemble"


def test_door_rejects_a_depth_outside_the_named_bands(client: Any) -> None:
    response = client.get("/api/v1/world/deep-dossier", params={"focus": "finals", "depth": "infinite"})
    assert response.status_code == 422


def test_door_rejects_an_empty_focus(client: Any) -> None:
    response = client.get("/api/v1/world/deep-dossier", params={"focus": "  ", "depth": "standard"})
    assert response.status_code == 200
    assert response.json()["available"] is False
