"""§76's spend cap at the coach door — the arithmetic answers, the phrasing call is what is refused.

`/knowledge/ask` refuses with 429 `ai_budget_exhausted` because retrieval is a *separate* door there: a caller
who wants the answer without the model call has somewhere else to go. `/coach/ask` is not that shape. The
answerable part of a coach turn — the recommendation, the reasons, the stored profile figures — is arithmetic
over `user_players` and the training ledger, and the LLM only *phrases* it. Raising 429 here would discard that
arithmetic, which is a worse failure than the one the cap exists to prevent.

So the door is gated at the model call, not at the request: when today's spend has reached
`settings.ai_daily_budget_usd`, the answer is still produced and the call is not made. These cases pin that
behaviour from the ledger side — by planting `model_calls` rows with a real cost — rather than by mocking the
helper, because the integration that matters is settings → ledger → this door.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import SessionLocal
from app.main import app
from app.models import ModelCall

PASSWORD = "TestPass1234!"


@pytest.fixture()
def session() -> Iterator[Session]:
    """A session over a ledger this file owns (the run's database persists from case to case)."""
    row = SessionLocal()
    try:
        row.query(ModelCall).delete()
        row.commit()
        yield row
    finally:
        row.close()


def _account() -> TestClient:
    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/register",
        json={"email": f"budget-{uuid4().hex[:8]}@example.test", "password": PASSWORD, "display_name": "Budget", "role": "player", "accepts_data_policy": True},
    )
    assert response.status_code == 201, response.text
    client.headers.update({"Authorization": f"Bearer {response.json()['access_token']}"})
    return client


def _player(client: TestClient) -> str:
    response = client.post(
        "/api/v1/players",
        json={"name": "Budget Player", "position": "CM", "age": 24, "level": "intermediate", "preferred_foot": "right", "goal": "improve_passing"},
    )
    assert response.status_code in (200, 201), response.text
    return str(response.json()["id"])


def _spend(db: Session, dollars: float, *, today: bool = True) -> None:
    """Plant one paid model-call row, as a real provider spend would have left it."""
    when = datetime.now(UTC) - timedelta(hours=1) if today else datetime.now(UTC) - timedelta(days=3)
    db.add(
        ModelCall(
            id=f"mc_{uuid4().hex[:12]}",
            provider="openai",
            model="gpt-4o-mini",
            feature="coach.ask",
            input_tokens=10,
            output_tokens=5,
            latency_ms=90,
            actual_cost_usd=dollars,
            demo_mode=False,
            success=True,
            created_at=when,
        )
    )
    db.commit()


def test_the_door_answers_arithmetic_when_todays_spend_cap_is_reached(session: Session) -> None:
    """The cap refuses the phrasing call, not the answer: the recommendation and reasons still ship."""
    budget = float(settings.ai_daily_budget_usd)
    _spend(session, budget + 5.0)
    client, player_id = _account(), None
    player_id = _player(client)

    before = session.query(ModelCall).count()
    response = client.post(f"/api/v1/coach/ask?player_id={player_id}", json={"question": "What should I train today?"})

    assert response.status_code == 200, f"the arithmetic answer is what the caller paid for: {response.text}"
    body = response.json()
    assert body["message"], "the stored recommendation survived the cap"
    assert body["reasons"], "the reasons the arithmetic produced survived it too"
    assert any("cap" in reason.lower() or "spend" in reason.lower() for reason in body["reasons"]), f"the answer names why the phrasing step is missing: {body['reasons']}"
    assert session.query(ModelCall).count() == before, "a refused call is not a model call and must not be recorded"


def test_the_door_calls_the_model_when_the_cap_is_not_reached(session: Session) -> None:
    """The un-blocked path is unchanged: the provider is called and the call lands in the ledger."""
    _spend(session, 0.01)
    client = _account()
    player_id = _player(client)

    before = session.query(ModelCall).count()
    response = client.post(f"/api/v1/coach/ask?player_id={player_id}", json={"question": "What should I train today?"})

    assert response.status_code == 200, response.text
    assert session.query(ModelCall).count() == before + 1, "the phrasing call happened and was recorded"


def test_a_demo_mode_budget_never_blocks_the_door(session: Session) -> None:
    """Demo mode is free, so a cap measured in real dollars cannot bind it — the guard must not fire."""
    # Spend planted as demo rows adds nothing to the ledger's *actual* cost, which is what the cap reads.
    db = SessionLocal()
    try:
        db.add(
            ModelCall(
                id=f"mc_{uuid4().hex[:12]}",
                provider="mock",
                model="rule-engine-demo",
                feature="coach.ask",
                latency_ms=1,
                actual_cost_usd=0.0,
                demo_mode=True,
                success=True,
            )
        )
        db.commit()
    finally:
        db.close()

    client = _account()
    player_id = _player(client)
    response = client.post(f"/api/v1/coach/ask?player_id={player_id}", json={"question": "What should I train today?"})
    assert response.status_code == 200, response.text
    assert response.json()["message"]


def test_an_older_spend_row_does_not_reach_todays_cap(session: Session) -> None:
    """The cap is a *day's* cap: spend from three days ago is already outside the window."""
    _spend(session, float(settings.ai_daily_budget_usd) + 50.0, today=False)
    client = _account()
    player_id = _player(client)

    before = session.query(ModelCall).count()
    response = client.post(f"/api/v1/coach/ask?player_id={player_id}", json={"question": "What should I train today?"})

    assert response.status_code == 200, response.text
    assert session.query(ModelCall).count() == before + 1, "yesterday's spend is not today's, so the call proceeds"
