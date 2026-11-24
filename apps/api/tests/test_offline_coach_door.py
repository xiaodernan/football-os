"""The closed-gateway promise, checked at the HTTP door rather than in a provider unit.

With no key configured (the owner's cost-control directive of 2026-11-24), a public coach-read
must still answer, instantly and with a labelled demo template — never a network call, never an
unverified model sentence. This is the end-to-end guard for that promise.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import settings
from app.providers import _llm_breaker

API = "/api/v1"


def test_a_public_coach_door_answers_in_labelled_demo_without_a_key(client: TestClient) -> None:
    original = settings.openai_api_key
    _llm_breaker.reset()
    object.__setattr__(settings, "openai_api_key", "")
    try:
        response = client.get(f"{API}/world/story/coach-read")
    finally:
        object.__setattr__(settings, "openai_api_key", original)
        _llm_breaker.reset()
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "mock"
    assert body["model"] == "template-demo"
    assert body["demo_mode"] is True
    assert body["answer"].startswith("[DEMO MODE")
    assert body["latency_ms"] >= 0
