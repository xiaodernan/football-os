"""A closed gateway must not turn every coach door into a network timeout.

When the account behind OPENAI_API_KEY stops working, the key is often left in the environment.
Without a circuit, each request still pays a connection timeout before the door falls back. After
three consecutive failed calls the provider door serves the labelled demo template for a bounded
cooldown, and retries the real provider once that window has passed.
"""

from __future__ import annotations

import time

import pytest

from app.core.config import settings
from app.providers import (
    LlmResult,
    _GuardedLLMProvider,
    _llm_breaker,
    get_llm_provider,
    provider_status,
)


class _Failing:
    name = "openai"

    def complete(self, **kwargs: object) -> LlmResult:
        return LlmResult(text="", provider="openai", model="gpt-6.2-sol", demo_mode=False,
                         error="insufficient_user_quota")


class _Healthy:
    name = "openai"

    def complete(self, **kwargs: object) -> LlmResult:
        return LlmResult(text="A real answer.", provider="openai", model="gpt-6.2-sol",
                         demo_mode=False)


@pytest.fixture(autouse=True)
def clean_breaker() -> None:
    _llm_breaker.reset()


def test_three_failures_open_the_circuit_to_labelled_demo() -> None:
    guarded = _GuardedLLMProvider(_Failing())  # type: ignore[arg-type]
    for _ in range(3):
        guarded.complete(system="s", prompt="p")
    assert _llm_breaker.is_open
    # A key still present in the environment must not override the open circuit.
    original = settings.openai_api_key
    object.__setattr__(settings, "openai_api_key", "sk-leftover")
    try:
        assert get_llm_provider().name == "mock"
    finally:
        object.__setattr__(settings, "openai_api_key", original)


def test_a_silent_demo_fallback_from_a_real_provider_trips_the_circuit() -> None:
    class _SilentFallback:
        name = "openai"

        def complete(self, **kwargs: object) -> LlmResult:
            return LlmResult(text="[DEMO MODE]", provider="mock", model="template-demo",
                             demo_mode=True)

    guarded = _GuardedLLMProvider(_SilentFallback())  # type: ignore[arg-type]
    for _ in range(3):
        guarded.complete(system="s", prompt="p")
    assert _llm_breaker.is_open


def test_one_success_closes_the_circuit() -> None:
    guarded = _GuardedLLMProvider(_Failing())  # type: ignore[arg-type]
    for _ in range(3):
        guarded.complete(system="s", prompt="p")
    assert _llm_breaker.is_open
    guarded = _GuardedLLMProvider(_Healthy())  # type: ignore[arg-type]
    result = guarded.complete(system="s", prompt="p")
    assert result.text == "A real answer."
    assert not _llm_breaker.is_open
    assert _llm_breaker.failures == 0


def test_the_circuit_retries_after_its_cooldown() -> None:
    _llm_breaker.fail()
    _llm_breaker.fail()
    _llm_breaker.fail()
    assert _llm_breaker.is_open
    _llm_breaker.opened_at = time.monotonic() - _llm_breaker.cooldown_s - 1
    assert not _llm_breaker.is_open
    assert _llm_breaker.failures == 0


def test_the_status_door_reports_the_circuit() -> None:
    status = provider_status()
    assert status["llm_circuit_open"] is False
    assert status["llm_circuit_failures"] == 0
    _llm_breaker.fail()
    _llm_breaker.fail()
    _llm_breaker.fail()
    status = provider_status()
    assert status["llm_circuit_open"] is True
    assert status["llm_circuit_failures"] == 3
    assert status["llm"] == "mock"


def test_an_exception_on_the_gateway_is_counted_as_a_failure() -> None:
    class _Raises:
        name = "openai"

        def complete(self, **kwargs: object) -> LlmResult:
            raise OSError("connection refused")

    guarded = _GuardedLLMProvider(_Raises())  # type: ignore[arg-type]
    with pytest.raises(OSError):
        guarded.complete(system="s", prompt="p")
    assert _llm_breaker.failures == 1
