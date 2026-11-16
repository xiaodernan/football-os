"""The Admin coach-read door — one honest press per call, gated by the same shared passphrase."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.providers import LlmResult
from app.services import behavior_coach

API = "/api/v1"
PASSPHRASE = "123"


class _StubProvider:
    name = "stub"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 500, temperature: float = 0.4) -> LlmResult:  # noqa: ARG002
        assert "three optimizations" in system.lower()
        assert "seeded" in prompt.lower()
        return LlmResult(
            text="First, straighten the handoff. Second, narrow the door. Third, hold the sprint.",
            provider="stub",
            model="stub-1",
            demo_mode=False,
            input_tokens=42,
            output_tokens=17,
            cached_input_tokens=0,
            cache_reported=False,
            latency_ms=1,
        )


class _BrokenProvider:
    name = "stub"

    def complete(self, *, system: str, prompt: str, max_tokens: int = 500, temperature: float = 0.4) -> LlmResult:  # noqa: ARG002
        raise RuntimeError("gateway unreachable")


class TestAdminCoachRead:
    def test_the_passphrase_still_rules(self) -> None:
        client = TestClient(app)
        assert client.get(f"{API}/admin/coach-read").status_code == 401
        assert client.get(f"{API}/admin/coach-read", headers={"x-admin-passphrase": "wrong"}).status_code == 401

    def test_the_coach_answers_with_everything_the_panel_prints(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(behavior_coach, "get_llm_provider", lambda: _StubProvider())
        client = TestClient(app)
        response = client.get(f"{API}/admin/coach-read", headers={"x-admin-passphrase": PASSPHRASE})
        assert response.status_code == 200
        body = response.json()
        assert body["available"] is True
        assert body["provider"] == "stub"
        assert body["model"] == "stub-1"
        assert body["answer"] == "First, straighten the handoff. Second, narrow the door. Third, hold the sprint."
        assert body["cache_reported"] is False
        assert body["cached_input_tokens"] == 0
        assert body["window_days"] == 90

    def test_an_unreachable_gateway_answers_without_crashing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(behavior_coach, "get_llm_provider", lambda: _BrokenProvider())
        client = TestClient(app)
        response = client.get(f"{API}/admin/coach-read", headers={"x-admin-passphrase": PASSPHRASE})
        assert response.status_code == 200
        body = response.json()
        assert body["available"] is False
        assert "gateway unreachable" in body["error"]

    def test_a_provider_error_answer_is_also_reported_available_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class _ErrorStub:
            name = "stub"

            def complete(self, *, system: str, prompt: str, max_tokens: int = 500, temperature: float = 0.4) -> LlmResult:  # noqa: ARG002
                return LlmResult(text="", provider="stub", model="stub-1", demo_mode=False, error="rate_limited")

        monkeypatch.setattr(behavior_coach, "get_llm_provider", lambda: _ErrorStub())
        client = TestClient(app)
        response = client.get(f"{API}/admin/coach-read", headers={"x-admin-passphrase": PASSPHRASE})
        assert response.status_code == 200
        assert response.json()["available"] is False

    def test_the_answer_on_the_rows_this_host_actually_holds(self) -> None:
        client = TestClient(app)
        response = client.get(f"{API}/admin/coach-read", headers={"x-admin-passphrase": PASSPHRASE})
        assert response.status_code == 200
        body = response.json()
        assert body["window_days"] == 90
        assert body["available"] in (True, False)
