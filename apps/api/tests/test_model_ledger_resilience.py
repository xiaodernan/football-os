"""§46's ledger, kept a sidecar on purpose: a reader's turn survives a damaged one.

On 2026-11-15 the `coach/ask` door ran end to end against the real gateway and the answer
came back composed from the model's words — then failed to persist because the local
`model_calls` table the ledger shares with that commit was missing columns in a carried
template, and the commit took the whole turn down with it. The ledger is a recording of
the turn, not a part of it, so the recording can fail without the reader losing the
answer. These cases pin that from both halves:

* the safe variant — it returns a bool instead of raising, writes when it can, and rolls
  back without leaking anything on a damaged table;
* the doors — a damaged ledger no longer 500s the turn: `/coach/ask` and
  `/knowledge/ask` both answer 200 with their answer whatever the ledger does.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.models import ModelCall
from app.providers import LlmResult
from app.services import model_ledger


@pytest.fixture()
def session() -> Iterator[Session]:
    with SessionLocal() as live:
        yield live


def _result() -> LlmResult:
    return LlmResult(
        text="phrasing of a stored turn",
        provider="openai",
        model="gpt-6-sol",
        demo_mode=False,
        input_tokens=97,
        output_tokens=11,
        reasoning_tokens=0,
        cached_input_tokens=0,
        latency_ms=42,
        cache_reported=False,
    )


class TestTheSafeVariant:
    def test_it_writes_when_it_can(self, session: Session) -> None:
        before = session.query(ModelCall).count()
        assert model_ledger.record_model_call_safely(result=_result(), feature="resilience_test", user_id=None) is True
        assert session.query(ModelCall).count() == before + 1

    def test_it_rolls_back_and_falses_on_a_dead_ledger(self, session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(*_args, **_kwargs):  # noqa: ANN001, ANN002, ANN003
            raise OperationalError("INSERT INTO model_calls", {}, Exception("no such table: model_calls"))

        monkeypatch.setattr(model_ledger, "record_model_call", boom)
        before = session.query(ModelCall).count()
        assert model_ledger.record_model_call_safely(result=_result(), feature="resilience_test", user_id=None) is False
        assert session.query(ModelCall).count() == before


class TestTheDoors:
    def test_the_coach_answer_survives_a_dead_ledger(self, auth_client, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
        player = auth_client.post(
            "/api/v1/players",
            json={"name": "Ledger Walking", "position": "CM", "age": 24, "level": "intermediate", "preferred_foot": "right", "goal": "improve_passing"},
        )
        assert player.status_code in (200, 201), player.text
        player_id = player.json()["id"]

        def boom(*_args, **_kwargs):  # noqa: ANN001, ANN002, ANN003
            raise OperationalError("INSERT INTO model_calls", {}, Exception("no such table: model_calls"))

        monkeypatch.setattr(model_ledger, "record_model_call", boom)
        response = auth_client.post(
            "/api/v1/coach/ask",
            json={"question": "What should I do today? I have 20 minutes.", "available_minutes": 20, "player_id": player_id},
            timeout=30,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["confidence"] > 0
        assert body["provider"]

    def test_the_knowledge_answer_survives_a_dead_ledger(self, auth_client, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
        def boom(*_args, **_kwargs):  # noqa: ANN001, ANN002, ANN003
            raise OperationalError("INSERT INTO model_calls", {}, Exception("no such table: model_calls"))

        monkeypatch.setattr(model_ledger, "record_model_call", boom)
        response = auth_client.post("/api/v1/knowledge/ask", json={"question": "when should my team press"}, timeout=30)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["answered"] is True
        assert body["answer"]
