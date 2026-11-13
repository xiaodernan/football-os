"""M17 answer cache: a repeated question costs a lookup, not a provider call.

The door these tests guard is the only one in the product that calls a real language model on a
read path. On the gateway this project runs against, one call carries a ~4 400-token preamble that
the gateway adds whether or not the caller sends anything, so a repeat is expensive in a way the
request body does not show. The cache is keyed on the question, the passages, the model and the
contract; these tests pin each of those four and the coalescing that makes two simultaneous first
asks cost one call.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.providers import LlmResult
from app.services import knowledge
from app.services.knowledge import answer_cache


@pytest.fixture()
def db() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _counters() -> Iterator[None]:
    answer_cache.reset_stats()
    yield
    answer_cache.reset_stats()


# --- the key -------------------------------------------------------------------------------


def test_normalisation_collapses_what_is_not_meaning() -> None:
    assert answer_cache.normalise_question("  How SHOULD a six press?  ") == answer_cache.normalise_question("how should a six press")
    assert answer_cache.normalise_question("ｗｈａｔ　ｉｓ　ａ　ｂｌｏｃｋ") == "what is a block"  # NFKC widths
    assert answer_cache.normalise_question("why press?") != answer_cache.normalise_question("why press late")


def test_the_same_question_over_different_passages_is_a_different_answer() -> None:
    common = {"question": "how do I press", "model": "gpt-6-sol", "locale": "en"}
    first = answer_cache.cache_key(chunk_ids=["c1", "c2"], **common)
    second = answer_cache.cache_key(chunk_ids=["c1", "c3"], **common)
    assert first != second, "the citation set is part of the answer's identity, not decoration"


def test_chunk_order_and_duplicates_do_not_split_one_answer() -> None:
    common = {"question": "how do I press", "model": "gpt-6-sol", "locale": "en"}
    assert answer_cache.cache_key(chunk_ids=["b", "a"], **common) == answer_cache.cache_key(chunk_ids=["a", "b", "a"], **common)


def test_a_new_model_is_a_new_answer() -> None:
    common = {"question": "how do I press", "chunk_ids": ["c1"], "locale": "en"}
    assert answer_cache.cache_key(model="gpt-6-sol", **common) != answer_cache.cache_key(model="another-model", **common)


# --- the store -----------------------------------------------------------------------------


def test_put_then_get_round_trips() -> None:
    key = "knowledge:answer:test-round-trip"
    answer_cache.put(key, text="Hold width until the ball travels.", model="gpt-6-sol", provider="openai")
    stored = answer_cache.get(key)
    assert stored is not None
    assert stored["text"] == "Hold width until the ball travels."
    assert stored["model"] == "gpt-6-sol"
    assert stored["version"] == answer_cache.CACHE_VERSION


def test_a_blank_answer_is_never_stored() -> None:
    key = "knowledge:answer:test-blank"
    answer_cache.put(key, text="   ", model="gpt-6-sol", provider="openai")
    assert answer_cache.get(key) is None


def test_an_entry_from_an_older_contract_is_unreachable() -> None:
    from app.core.redis_cache import get_redis_cache

    key = "knowledge:answer:test-version"
    get_redis_cache().set(key, {"version": "knowledge-answer-v0", "text": "old wording"}, ttl=60)
    assert answer_cache.get(key) is None, "a contract bump must not serve prose written under the old one"


def test_switching_the_tier_off_is_immediate(monkeypatch: pytest.MonkeyPatch) -> None:
    key = "knowledge:answer:test-off"
    answer_cache.put(key, text="stored while on", model="m", provider="p")
    monkeypatch.setattr(answer_cache, "enabled", lambda: False)
    assert answer_cache.get(key) is None
    answer_cache.put("knowledge:answer:test-off-2", text="not stored while off", model="m", provider="p")
    monkeypatch.undo()
    assert answer_cache.get("knowledge:answer:test-off-2") is None


def test_the_ttl_is_the_configured_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(answer_cache, "ttl_seconds", lambda: 1.0)
    key = "knowledge:answer:test-ttl"
    answer_cache.put(key, text="short lived", model="m", provider="p")
    assert answer_cache.get(key) is not None
    time.sleep(1.2)
    assert answer_cache.get(key) is None, "an expired phrasing must be re-bought, not served stale"


# --- coalescing ----------------------------------------------------------------------------


def test_two_threads_on_one_key_enter_one_at_a_time() -> None:
    key = "knowledge:answer:test-lane"
    entered: list[int] = []
    holding = threading.Event()
    released = threading.Event()

    def first() -> None:
        with answer_cache.single_flight(key):
            entered.append(1)
            holding.set()
            released.wait(2)

    def second() -> None:
        holding.wait(2)
        with answer_cache.single_flight(key):
            entered.append(2)

    one = threading.Thread(target=first)
    two = threading.Thread(target=second)
    one.start()
    two.start()
    holding.wait(2)
    time.sleep(0.1)
    assert entered == [1], "the second caller must be held outside the lane"
    released.set()
    one.join(3)
    two.join(3)
    assert entered == [1, 2]


def test_the_lane_table_does_not_grow() -> None:
    for index in range(50):
        with answer_cache.single_flight(f"knowledge:answer:test-grow-{index}"):
            pass
    assert answer_cache.inflight_size() == 0, "a lane is removed when its last participant leaves"


# --- the door ------------------------------------------------------------------------------


class _CountingProvider:
    """A provider that answers in one canned sentence and counts how often it was asked."""

    name = "openai"
    model = "gpt-6-sol"

    def __init__(self) -> None:
        self.calls = 0
        self.prompts: list[str] = []

    def complete(self, *, system: str, prompt: str, max_tokens: int = 800, temperature: float = 0.4) -> LlmResult:
        self.calls += 1
        self.prompts.append(prompt)
        return LlmResult(
            text="Hold your width until the ball travels, then attack the space behind the recovering full-back [1].",
            provider=self.name,
            model=self.model,
            demo_mode=False,
            input_tokens=4500,
            output_tokens=40,
            cached_input_tokens=4400,
        )


def _ask_twice(db: Session, monkeypatch: pytest.MonkeyPatch, question: str) -> tuple[Any, Any, _CountingProvider]:
    provider = _CountingProvider()
    monkeypatch.setattr("app.services.knowledge.answer.get_llm_provider", lambda: provider)
    first = knowledge.ask(db, question, top_k=5, persist=False)
    second = knowledge.ask(db, question, top_k=5, persist=False)
    return first, second, provider


def test_the_second_ask_over_the_same_passages_makes_no_provider_call(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    question = "cache probe: how should the far-side forward move when the ball is switched"
    first, second, provider = _ask_twice(db, monkeypatch, question)

    assert provider.calls == 1, f"one phrasing, one call; got {provider.calls}"
    assert first.cached is False
    assert second.cached is True
    assert second.text == first.text
    assert any("reused" in reason for reason in second.reasons)


def test_a_cached_answer_still_carries_this_call_s_own_citations(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    question = "cache probe: how do I defend a 1v1 without getting beaten"
    first, second, _ = _ask_twice(db, monkeypatch, question)

    assert second.citations, "a cached phrasing is never served without fresh citations"
    assert [c["chunk_id"] for c in second.citations] == [c["chunk_id"] for c in first.citations]
    assert all("phrased_by" in citation for citation in second.citations)


def test_a_different_question_is_a_different_call(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _CountingProvider()
    monkeypatch.setattr("app.services.knowledge.answer.get_llm_provider", lambda: provider)
    knowledge.ask(db, "how do I defend a 1v1 without getting beaten", top_k=5, persist=False)
    knowledge.ask(db, "when should my team press", top_k=5, persist=False)
    assert provider.calls >= 2, "two different questions must not share one phrasing"


def test_the_cache_can_be_switched_off_for_a_run(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(answer_cache, "enabled", lambda: False)
    question = "when should my team press"
    provider = _CountingProvider()
    monkeypatch.setattr("app.services.knowledge.answer.get_llm_provider", lambda: provider)
    knowledge.ask(db, question, top_k=5, persist=False)
    knowledge.ask(db, question, top_k=5, persist=False)
    assert provider.calls == 2, "with the tier off every ask is a real call"
