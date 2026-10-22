"""Tests for M12 model router (§45-§46).

The provider tier answers questions about the whole platform — which provider serves each surface, what
today's AI spend is against the daily budget — so its doors ask for the operator standing, exactly as the
metrics tier does. The status row promises "today's spending"; it is read from the same ledger the costs
door totals, not from a constant.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.db import SessionLocal
from app.main import app
from app.models import ModelCall

PASSWORD = "TestPass1234!"
SWITCH = {"provider_type": "llm", "provider_name": "openai"}
DOORS = [
    ("get", "/api/v1/model-router/status", None, 200),
    ("get", "/api/v1/model-router/costs", None, 200),
    ("post", "/api/v1/model-router/switch", SWITCH, 503),
]


def _player_client() -> TestClient:
    """A freshly registered player — registration is the account's first session."""
    client = TestClient(app)
    email = f"router-{uuid4().hex[:8]}@example.test"
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "display_name": "Router Tester",
            "role": "player",
            "accepts_data_policy": True,
        },
    )
    assert response.status_code == 201, f"Registration failed: {response.json()}"
    client.headers.update({"Authorization": f"Bearer {response.json()['access_token']}"})
    return client


class TestModelRouter:
    """Model router endpoint tests."""

    def test_provider_status(self, admin_client: TestClient) -> None:
        """Should report all provider types and demo mode status."""
        resp = admin_client.get("/api/v1/model-router/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "llm" in data
        assert "embedding" in data
        assert "reranker" in data
        assert "vision" in data
        assert "storage" in data
        assert "demo_mode" in data
        assert "budget_limit" in data

    def test_provider_status_demo_mode(self, admin_client: TestClient) -> None:
        """In demo mode, LLM should be 'mock'."""
        resp = admin_client.get("/api/v1/model-router/status")
        assert resp.status_code == 200
        data = resp.json()
        # In this test environment, we're in demo mode
        assert data["demo_mode"] is True
        assert data["llm"] == "mock"

    def test_switch_refused(self, admin_client: TestClient) -> None:
        """Runtime provider switching should be refused (env-driven only)."""
        resp = admin_client.post(
            "/api/v1/model-router/switch",
            json={"provider_type": "llm", "provider_name": "openai"},
        )
        assert resp.status_code == 503
        data = resp.json()
        assert data["detail"]["code"] == "provider_switch_unavailable"
        assert "environment variable" in data["detail"]["message"].lower()

    def test_costs_endpoint(self, admin_client: TestClient) -> None:
        """Should report today's spending and budget."""
        resp = admin_client.get("/api/v1/model-router/costs")
        assert resp.status_code == 200
        data = resp.json()
        assert "spent_today_usd" in data
        assert "budget_limit_usd" in data
        assert "remaining_usd" in data
        assert "budget_exhausted" in data
        assert isinstance(data["spent_today_usd"], int | float)
        assert isinstance(data["budget_exhausted"], bool)

    def test_budget_not_exhausted_in_test(self, admin_client: TestClient) -> None:
        """Fresh test user should have budget remaining."""
        resp = admin_client.get("/api/v1/model-router/costs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["budget_exhausted"] is False
        assert data["remaining_usd"] > 0


class TestTheOperatorStanding:
    """Every row describes the platform, so every door asks for the operator's standing.

    `/costs` publishes today's spend over every account's calls, `/status` publishes the provider
    configuration and the budget, and `/switch` is documented as an admin-only configuration change. All
    three were guarded by a session alone, so any registered player read the platform's spend and could
    reach the switch refusal. These cases hold both ends: the player is refused at all three doors, and
    the admin still reaches each one.
    """

    @pytest.mark.parametrize(("method", "path", "payload", "admin_status"), DOORS)
    def test_a_player_is_refused_and_an_admin_is_answered(
        self,
        method: str,
        path: str,
        payload: dict[str, str] | None,
        admin_status: int,
        admin_client: TestClient,
    ) -> None:
        refused = _player_client().request(method, path, json=payload)
        assert refused.status_code == 403, f"a player reached {method.upper()} {path} and got {refused.status_code}: {refused.text[:300]}"
        detail = refused.json()["detail"]
        assert detail["code"] == "insufficient_role", f"{path} answered {detail['code']!r}, not the platform's role refusal"
        assert detail["held"] == "player"
        assert detail["required"] == ["admin"], f"{path} names {detail['required']} as the standing, not the operators"

        answered = admin_client.request(method, path, json=payload)
        assert answered.status_code == admin_status, f"the operator was refused at {path}: {answered.text[:300]}"

    @pytest.mark.parametrize(("method", "path", "payload", "admin_status"), DOORS)
    def test_an_anonymous_caller_is_refused(
        self,
        method: str,
        path: str,
        payload: dict[str, str] | None,
        admin_status: int,
    ) -> None:
        response = TestClient(app).request(method, path, json=payload)
        assert response.status_code == 401, f"an anonymous caller reached {method.upper()} {path} and got {response.status_code}: {response.text[:300]}"
        assert response.json()["detail"]["code"] == "unauthenticated", f"{path} answered {response.json()['detail']['code']!r}"


class TestTheSpendRow:
    """`/status` promises today's spending, so the row must be the ledger's number."""

    def test_the_status_row_agrees_with_the_cost_door(self, admin_client: TestClient) -> None:
        call_id = f"mc_{uuid4().hex[:12]}"
        with SessionLocal() as session:
            session.add(
                ModelCall(
                    id=call_id,
                    provider="openai",
                    model="gpt-4o-mini",
                    feature="model-router.test",
                    input_tokens=10,
                    output_tokens=5,
                    latency_ms=90,
                    actual_cost_usd=1.25,
                    demo_mode=False,
                    success=True,
                    created_at=datetime.now(UTC),
                )
            )
            session.commit()
        try:
            status = admin_client.get("/api/v1/model-router/status")
            costs = admin_client.get("/api/v1/model-router/costs")
            assert status.status_code == 200, f"the status door answered {status.status_code}: {status.text[:300]}"
            assert costs.status_code == 200, f"the costs door answered {costs.status_code}: {costs.text[:300]}"
            spent = status.json()["budget_spent_today"]
            assert spent >= 1.25, f"the status row reports {spent}, less than the 1.25 just written to the ledger"
            assert spent == costs.json()["spent_today_usd"], f"the two doors disagree about today's spend: {spent} against {costs.json()['spent_today_usd']}"
        finally:
            with SessionLocal() as session:
                session.query(ModelCall).filter(ModelCall.id == call_id).delete()
                session.commit()
